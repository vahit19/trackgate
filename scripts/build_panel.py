"""Builds panel/index.html (TrackGate) from results/worldcup/*.json.
The page carries its data inline, so it works offline and as a hosted page."""
import datetime as dt
import glob
import json
import os
import re
import statistics

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def dedupe(queue):
    """StatsBomb logs several events on one freeze frame, and one incident spans
    several frames; keep one review item per incident."""
    out = []
    for q in queue:
        # one review item per incident: skip moments within 20 s of a worse one already kept
        if any(k["period"] == q["period"] and abs(k["statsbomb_t"] - q["statsbomb_t"]) < 20 for k in out):
            continue
        out.append(q)
    return out


def main():
    games = []
    tot = {"n": 0, "o5": 0.0, "o2": 0.0, "est_n": 0, "est_o5": 0.0, "persp": {"event_team": 0, "other_team": 0}}
    for f in sorted(glob.glob(os.path.join(ROOT, "results", "worldcup", "*.json"))):
        if not re.search(r"\d+\.json$", f):
            continue
        r = json.load(open(f, encoding="utf-8"))
        a, by = r["summary"]["all"], r["summary"]["by_pff_visibility"]

        def flag(k):
            v = by.get(k)
            return None if not v else {"n": v["n"], "over5": v["share_over_5m"], "over2": v["share_over_2m"]}

        g = {
            "id": r["pff_game_id"], "match": r["match"], "date": r["date"], "events": r["events_with_360"],
            "n": a["n"], "median_m": a["median_m"], "p90_m": a["p90_m"],
            "over5": a["share_over_5m"], "over2": a["share_over_2m"],
            "vis": flag("VISIBLE"), "est": flag("ESTIMATED"),
            "perspective": r.get("statsbomb_perspective", {}),
            "hist": r["summary"].get("histogram_0_5m_bins"),
            "queue": dedupe([{k: q.get(k) for k in ("period", "statsbomb_t", "event", "players", "median_m", "max_m", "estimated_players", "video", "pairs")}
                             for q in r.get("triage_queue", [])])[:10],
        }
        games.append(g)
        tot["n"] += a["n"]
        tot["o5"] += a["share_over_5m"]["rate"] * a["n"]
        tot["o2"] += a["share_over_2m"]["rate"] * a["n"]
        if g["est"]:
            tot["est_n"] += g["est"]["n"]
            tot["est_o5"] += g["est"]["over5"]["rate"] * g["est"]["n"]
        for k in tot["persp"]:
            tot["persp"][k] += g["perspective"].get(k, 0)
    data = {
        "generated": dt.date.today().isoformat(),
        "games": games,
        "totals": {"n": tot["n"], "over5": tot["o5"] / tot["n"], "over2": tot["o2"] / tot["n"],
                   "median_m": statistics.median(g["median_m"] for g in games),
                   "est_over5": tot["est_o5"] / max(1, tot["est_n"]), "perspective": tot["persp"]},
    }
    tpl = open(os.path.join(ROOT, "panel", "template.html"), encoding="utf-8").read()
    html = tpl.replace("/*DATA*/null", json.dumps(data, separators=(",", ":")))
    # real agent runs, replayed when a viewer's network cannot reach the live agent (scripts/record_runs.py)
    rec = os.path.join(ROOT, "panel", "recorded_runs.json")
    runs = json.load(open(rec, encoding="utf-8")) if os.path.exists(rec) else []
    html = html.replace("/*RECORDED*/[]", json.dumps(runs, separators=(",", ":")))
    out = os.path.join(ROOT, "panel", "index.html")
    open(out, "w", encoding="utf-8").write(html)
    # the same page as a complete document for hosting outside Claude (our server, GitHub Pages)
    icon = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Crect width='24' height='24' rx='6' fill='%231fd29b'/%3E"
            "%3Cg fill='none' stroke='%2304130e' stroke-width='2.4' stroke-linecap='round'%3E%3Ccircle cx='12' cy='12' r='6'/%3E%3Cpath d='M12 6v12M6 12h12'/%3E%3C/g%3E%3C/svg%3E")
    page = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            '<meta name="description" content="TrackGate tests whether two player-tracking feeds agree before the data is trusted for officiating, betting or broadcast.">'
            f'<link rel="icon" href="{icon}">' + html + "</html>\n")
    os.makedirs(os.path.join(ROOT, "deploy", "site"), exist_ok=True)
    open(os.path.join(ROOT, "deploy", "site", "index.html"), "w", encoding="utf-8").write(page)
    print(out, len(games), "games", json.dumps(data["totals"]))


if __name__ == "__main__":
    main()
