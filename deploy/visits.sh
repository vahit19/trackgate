#!/usr/bin/env bash
# Who opened TrackGate and did anything break? Summarises the API's event log on the server.
# Usage: bash deploy/visits.sh [days]   (default 7)
set -euo pipefail
HOST=${HOST:-root@116.203.228.141}
KEY=${KEY:-$HOME/.ssh/id_ed25519_nader}
ssh -i "$KEY" -o IdentitiesOnly=yes -o BatchMode=yes "$HOST" "python3 - ${1:-7}" <<'PY'
import collections, datetime, json, sys
days = int(sys.argv[1]); since = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)).strftime("%Y-%m-%dT")
ev = [json.loads(l) for l in open("/opt/trackgate/data/events.jsonl", encoding="utf-8") if l.strip()]
ev = [e for e in ev if e["t"] >= since]
loads = [e for e in ev if e["kind"] == "load"]
print(f"last {days} days: {len(loads)} page loads, {len({e['sid'] for e in loads})} sessions, {len({e['ip'] for e in loads})} visitors")
for e in loads[-30:]:
    print(" ", e["t"], e.get("country", ""), e["ip"], e.get("host", ""), (e.get("ref") or "-")[:50], e["ua"][:60])
bad = [e for e in ev if e["kind"] in ("js_error", "agent_error", "llm_error", "rate_limited")]
print(f"\nproblems: {len(bad)}")
for e in bad[-20:]:
    print(" ", e["t"], e["kind"], e.get("code") or e.get("status") or "", (e.get("detail") or "")[:120])
q = [e for e in ev if e["kind"] == "agent_question"]
print(f"\nanalyst questions: {len(q)}")
for e in q[-15:]:
    print(" ", e["t"], e.get("country", ""), (e.get("q") or "")[:100])
cost = sum(e.get("cost") or 0 for e in ev if e["kind"] == "llm_call")
print(f"\nmodel calls: {sum(1 for e in ev if e['kind'] == 'llm_call')}, cost ${cost:.4f}")
print("actions:", dict(collections.Counter(e["kind"] for e in ev if e["kind"] in ("view", "decision", "report", "video"))))
PY
