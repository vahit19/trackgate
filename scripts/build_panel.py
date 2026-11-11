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
    """StatsBomb logs several events on one freeze frame (a receipt and the carry
    that follows); keep one review item per moment."""
    seen, out = set(), []
    for q in queue:
        key = (q["period"], round(q["statsbomb_t"], 1), q["median_m"])
        if key in seen:
            continue
        seen.add(key)
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
    out = os.path.join(ROOT, "panel", "index.html")
    open(out, "w", encoding="utf-8").write(html)
    print(out, len(games), "games", json.dumps(data["totals"]))


if __name__ == "__main__":
    main()
