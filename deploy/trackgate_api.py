"""TrackGate API: relays the analyst's chat to OpenRouter, so the key stays on the server, and
records page events (loads, views, errors) so we can see who used the app and whether anything broke.
Standard library only; one small container behind nginx at /trackgate/api/."""
import collections
import json
import os
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

KEY = os.environ.get("OPENROUTER_API_KEY", "")
MODEL = os.environ.get("TRACKGATE_MODEL", "anthropic/claude-haiku-5.5")
DATA = os.environ.get("TRACKGATE_DATA", "/data")
PORT = int(os.environ.get("PORT", "8095"))
DAILY_CALLS = int(os.environ.get("TRACKGATE_DAILY_CALLS", "1500"))
IP_CALLS, IP_WINDOW = 150, 600         # model calls per IP per 10 minutes (a company office shares one IP)
TOOLS = {"list_games", "game_detail", "simulate_gate", "set_gate", "open_game", "show_moment", "review_status", "acceptance_report"}
ORIGINS = {"https://vahitferyad.com", "https://vahit19.github.io"}
EVENTS = {"load", "view", "js_error", "agent_question", "agent_answer", "agent_error", "decision", "report", "video"}

lock = threading.Lock()
recent = collections.defaultdict(collections.deque)
day = {"d": "", "n": 0}


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class Handler(BaseHTTPRequestHandler):
    server_version = "trackgate"
    sys_version = ""

    def ip(self):
        return self.headers.get("X-Real-IP") or self.client_address[0]

    def record(self, kind, **kw):
        rec = {"t": now(), "kind": kind, "ip": self.ip(), "country": self.headers.get("CF-IPCountry", ""),
               "ua": (self.headers.get("User-Agent") or "")[:200], **kw}
        with lock, open(os.path.join(DATA, "events.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def reply(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        if self.headers.get("Origin") in ORIGINS:
            self.send_header("Access-Control-Allow-Origin", self.headers["Origin"])
            self.send_header("Vary", "Origin")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def body(self, limit):
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > limit:
            raise ValueError("bad size")
        return json.loads(self.rfile.read(n))

    def log_message(self, *a):
        pass

    def do_OPTIONS(self):
        self.send_response(204)
        if self.headers.get("Origin") in ORIGINS:
            self.send_header("Access-Control-Allow-Origin", self.headers["Origin"])
            self.send_header("Access-Control-Allow-Methods", "GET, POST")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_GET(self):
        if self.path.rstrip("/").endswith("/api/health"):
            return self.reply(200, {"ok": bool(KEY), "model": MODEL})
        self.reply(404, {"error": "not found"})

    def do_POST(self):
        p = self.path.split("?")[0].rstrip("/")
        try:
            if p.endswith("/api/event"):
                return self.event()
            if p.endswith("/api/chat"):
                return self.chat()
        except (ValueError, json.JSONDecodeError):
            return self.reply(400, {"error": "bad request"})
        self.reply(404, {"error": "not found"})

    def event(self):
        b = self.body(8_000)
        kind = str(b.get("type", ""))
        if kind not in EVENTS:
            return self.reply(400, {"error": "unknown event"})
        keep = {k: (v[:500] if isinstance(v, str) else v) for k, v in b.items() if k in ("sid", "host", "view", "detail", "ref", "w", "h", "q", "code", "ms", "tools")}
        self.record(kind, **keep)
        self.reply(200, {"ok": True})

    def allowed(self):
        t, ip = time.time(), self.ip()
        with lock:
            d = time.strftime("%Y-%m-%d", time.gmtime())
            if day["d"] != d:
                day.update(d=d, n=0)
            q = recent[ip]
            while q and t - q[0] > IP_WINDOW:
                q.popleft()
            if len(q) >= IP_CALLS or day["n"] >= DAILY_CALLS:
                return False
            q.append(t)
            day["n"] += 1
            return True

    def chat(self):
        b = self.body(200_000)
        msgs, tools, sid = b.get("messages"), b.get("tools") or [], str(b.get("sid", ""))[:40]
        if not isinstance(msgs, list) or not 1 <= len(msgs) <= 60 or not all(isinstance(m, dict) and m.get("role") in ("system", "user", "assistant", "tool") for m in msgs):
            raise ValueError("bad messages")
        tools = [t for t in tools if isinstance(t, dict) and (t.get("function") or {}).get("name") in TOOLS]
        if not KEY:
            return self.reply(503, {"error": "unavailable"})
        if not self.allowed():
            self.record("rate_limited", sid=sid)
            return self.reply(429, {"error": "rate_limited"})
        req = {"model": MODEL, "messages": msgs, "max_tokens": 700, "temperature": 0.2, "usage": {"include": True}}
        if tools:
            req["tools"] = tools
        r = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=json.dumps(req).encode(),
                                   headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json",
                                            "HTTP-Referer": "https://vahitferyad.com/trackgate/", "X-Title": "TrackGate"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(r, timeout=80) as resp:
                out = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            self.record("llm_error", sid=sid, status=e.code, detail=e.read()[:300].decode("utf-8", "replace"))
            return self.reply(503, {"error": "credits" if e.code == 402 else "upstream"})
        except Exception as e:  # timeout, DNS, TLS
            self.record("llm_error", sid=sid, status=0, detail=str(e)[:300])
            return self.reply(503, {"error": "upstream"})
        msg = ((out.get("choices") or [{}])[0]).get("message") or {}
        u = out.get("usage") or {}
        self.record("llm_call", sid=sid, ms=int(1000 * (time.time() - t0)), tokens=u.get("total_tokens"), cost=u.get("cost"),
                    tools=[c.get("function", {}).get("name") for c in msg.get("tool_calls") or []])
        self.reply(200, {"message": {"role": "assistant", "content": msg.get("content") or "", "tool_calls": msg.get("tool_calls") or []}})


if __name__ == "__main__":
    os.makedirs(DATA, exist_ok=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
