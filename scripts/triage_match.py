"""Triage queue for one World Cup match: the moments where PFF FC and
StatsBomb 360 disagree most, with a link to the second in PFF's film room.

Usage: python scripts/triage_match.py 3812 [--narrate]
Needs the match cached by scripts/run_worldcup.py.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracking_audit import crossvendor as cv  # noqa: E402
from tracking_audit.triage import narrate, queue  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(gid, do_narrate=False):
    res = json.load(open(os.path.join(ROOT, "results", "worldcup", f"{gid}.json"), encoding="utf-8"))
    meta = json.load(open(os.path.join(ROOT, "data", "pff", f"{gid}_meta.json"), encoding="utf-8"))[0]
    sid = res["statsbomb_match_id"]
    pff = cv.load_pff(os.path.join(ROOT, "data", "pff", f"{gid}.jsonl.bz2"))
    events = cv.load_statsbomb(os.path.join(ROOT, "data", "sb", f"{sid}_events.json"),
                               os.path.join(ROOT, "data", "sb", f"{sid}_360.json"), meta["homeTeam"]["name"])
    params = cv.align(events, pff)
    moments = []
    cv.compare_best_local(events, pff, params, moments=moments)
    q = queue(moments, meta.get("videoUrl"), {1: meta["startPeriod1"], 2: meta["startPeriod2"]})
    out = {"match": res["match"], "date": res["date"], "summary": res["summary"], "triage_queue": q}
    if do_narrate:
        facts = {"match": res["match"], "summary": res["summary"],
                 "worst_moments": [{k: m[k] for k in ("event", "median_m", "max_m", "estimated_players")} for m in q[:5]]}
        text, bad = narrate(facts)
        out["note"] = text
        out["note_rejected_numbers"] = bad
    path = os.path.join(ROOT, "results", "worldcup", f"{gid}_triage.json")
    json.dump(out, open(path, "w", encoding="utf-8"), indent=1)
    for m in q[:10]:
        print(f'{m["event"]:<14} median {m["median_m"]:>5} m  max {m["max_m"]:>5} m  est {m["estimated_players"]}  {m["video"]}')
    if do_narrate:
        print("\nNOTE:", out["note"] or f"rejected (unsupported numbers: {bad})")


if __name__ == "__main__":
    main(sys.argv[1], "--narrate" in sys.argv)
