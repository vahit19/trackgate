"""Command line: physics audit of one tracking feed.

    python -m tracking_audit.cli physics --tracking data/1925299_tracking.jsonl \
        --match data/1925299_match.json [--pose data/1925299_pose.jsonl.zip] --out results/1925299.json
"""
import argparse
import json
import os

from .io import read_skillcorner, read_skillcorner_match
from .physics import TrackingAudit
from .pose import PoseAudit


def physics(args):
    m = read_skillcorner_match(args.match)
    t = TrackingAudit(m["pitch_length"], m["pitch_width"])
    for fr in read_skillcorner(args.tracking):
        t.add(fr)
    result = {"match": m["label"], "date": m["date"], "tracking": t.summary()}
    if args.pose:
        p = PoseAudit()
        for fr in read_skillcorner(args.pose):
            p.add(fr)
        result["pose"] = p.summary()
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    c = result["tracking"]["checks"]
    print(result["match"], "| detected share", round(result["tracking"]["detected_share"], 3),
          "| speed", c["speed"]["count"], "teleport", c["teleport"]["count"],
          "accel", c["accel"]["count"], "off-pitch", c["off_pitch"]["count"])


def compare(args):
    from . import crossvendor as cv
    from .triage import queue
    pff = cv.load_pff(args.continuous)
    events = cv.load_statsbomb(args.snapshot_events, args.snapshot_frames, args.home)
    params = cv.align(events, pff)
    moments = []
    rows = cv.compare_best_local(events, pff, params, moments=moments)
    result = {"summary": cv.summarise(rows), "snapshot_perspective": cv.compare_best_local.last_perspective,
              "alignment": {f"p{p}_{'home' if th else 'away'}": v for (p, th), v in params.items()},
              "review_queue": queue(moments, args.video_url, {}, top=args.top)}
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    a = result["summary"]["all"]
    print(f'positions {a["n"]} | median gap {a["median_m"]:.2f} m | >5 m {100 * a["share_over_5m"]["rate"]:.1f}%')


def main():
    ap = argparse.ArgumentParser(prog="tracking-audit")
    sub = ap.add_subparsers(dest="cmd", required=True)
    cp = sub.add_parser("compare", help="agreement between a continuous feed and a snapshot feed of the same game")
    cp.add_argument("--continuous", required=True, help="PFF-format tracking (.jsonl.bz2)")
    cp.add_argument("--snapshot-events", required=True, help="StatsBomb-format events (.json)")
    cp.add_argument("--snapshot-frames", required=True, help="StatsBomb-format 360 frames (.json)")
    cp.add_argument("--home", required=True, help="home team name as written in the snapshot feed")
    cp.add_argument("--video-url", default=None)
    cp.add_argument("--top", type=int, default=15)
    cp.add_argument("--out", required=True)
    cp.set_defaults(func=compare)
    ph = sub.add_parser("physics", help="ground-truth-free physics checks on one feed")
    ph.add_argument("--tracking", required=True)
    ph.add_argument("--match", required=True)
    ph.add_argument("--pose")
    ph.add_argument("--out", required=True)
    ph.set_defaults(func=physics)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
