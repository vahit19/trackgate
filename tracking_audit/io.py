"""Streaming readers for tracking feeds.

A feed is an iterator of frames:
    {"frame": int, "t": float seconds (None if unknown), "period": int,
     "players": [{"id": int, "x": float, "y": float, "detected": bool,
                  "joints": {name: (x, y, z, claimed_p90_cm)} | None}]}

Only SkillCorner's open format is implemented; other vendors (Hawk-Eye,
NHL EDGE, PFF) plug in by yielding the same structure.
"""
import gzip
import io
import json
import zipfile


def _open_text(path):
    if path.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8")
    if path.endswith(".zip"):
        z = zipfile.ZipFile(path)
        name = next(n for n in z.namelist() if n.endswith(".jsonl") or n.endswith(".json"))
        return io.TextIOWrapper(z.open(name), encoding="utf-8")
    return open(path, encoding="utf-8")


def _seconds(ts):
    if not ts:
        return None
    h, m, s = ts.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def read_skillcorner(path):
    with _open_text(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            players = []
            for p in r.get("player_data") or []:
                if p.get("x") is None or p.get("y") is None:
                    continue
                joints = None
                if p.get("joints"):
                    joints = {
                        k: (v["xyz"][0], v["xyz"][1], v["xyz"][2], v.get("p90_mae_cm"))
                        for k, v in p["joints"].items()
                        if v and v.get("xyz")
                    }
                players.append({
                    "id": p["player_id"], "x": p["x"], "y": p["y"],
                    "detected": bool(p.get("is_detected")), "joints": joints,
                })
            yield {"frame": r["frame"], "t": _seconds(r.get("timestamp")), "period": r.get("period"), "players": players}


def read_skillcorner_match(path):
    with open(path, encoding="utf-8") as f:
        m = json.load(f)
    names = {}
    for p in m.get("players", []):
        names[p["id"]] = {
            "name": p.get("short_name") or f'{p.get("first_name", "")} {p.get("last_name", "")}'.strip(),
            "team_id": p.get("team_id"),
        }
    return {
        "id": m.get("id"),
        "label": f'{m.get("home_team", {}).get("name", "?")} v {m.get("away_team", {}).get("name", "?")}',
        "date": (m.get("date_time") or "")[:10],
        "pitch_length": m.get("pitch_length") or 105.0,
        "pitch_width": m.get("pitch_width") or 68.0,
        "players": names,
    }
