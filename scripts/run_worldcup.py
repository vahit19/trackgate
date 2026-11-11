"""Cross-vendor agreement on 2022 World Cup matches (PFF FC vs StatsBomb 360).

Downloads public data on first run, caches it under data/, writes one JSON
result per match to results/worldcup/ and a combined summary.
"""
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracking_audit import crossvendor as cv  # noqa: E402
from tracking_audit.triage import queue  # noqa: E402

# Public PFF FC World Cup 2022 dataset (Google Drive file ids) for the first ten games.
PFF = {
    "3812": ("1KYzyCxauhHZIfY_9nqvnAXi83aWr-23q", "1c1HdSrToX_0RfC92JkVy4ldRJ7M67JI7"),
    "3813": ("1Tc1h8rI985dq2DGmZCMa3W1OsN-E4Yuh", "1efRLjG4KXgwBfVritso4VhyCEN2WGv9L"),
    "3814": ("10iX17cHWFjAwmZoOCZD78mbNElgzdJho", "16to2wc6UeR2AYikZvQbdW_k0xpCIpAQB"),
    "3815": ("1SRuJZoJq1Ix7WuoAhnfRMlxz1NoCJalM", "1m841qX2JpERv3z1Cx-D2T4xQDBYzdofH"),
    "3816": ("1ZP_xXNfn20wHCG84f-nTcwp6RgQOXmQZ", "1wxMkLuN5qNpGzqW9GOtcEfL35h_1D_-F"),
    "3817": ("1-ECKLzbTRw5Utqx-sUUYYRI1wMe_5eWy", "1mcyrcT6KafIlW1VCJdLxbaFSS7M1hCOb"),
    "3818": ("1102koaeA-u-Ahz6wLKmlB-4_QfC16YhW", "1K5lJk3kgfEZJe-4pFYxItSYcvVMuVlTa"),
    "3819": ("1DAI_Bu0XSHmcjY114qqwP1WPDzJ7ettH", "1CG_hsnQrNYtV_rSsAJ_ljLy1h7QiVBal"),
    "3820": ("1FwiVFF7qL3xUaRYANJN4ymDOXcQYfSir", "19qeCd4qs7U1k675z-FrOpWj3tgAO511k"),
    "3821": ("1loJUaSJFjNQUUGWJPJzThEJICR1jO13p", "142pZZGX4yXrtCyZeU3QAYQgf_KTbKNWZ"),
}
SB_RAW = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "results", "worldcup")


def fetch(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "tracking-audit"})
            with urllib.request.urlopen(req, timeout=600) as r, open(path + ".part", "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
            os.replace(path + ".part", path)
            return path
        except Exception as e:  # network hiccups: retry with backoff
            print("retry", url, e, file=sys.stderr)
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"download failed: {url}")


def drive(file_id):
    return f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"


def main(ids):
    os.makedirs(OUT, exist_ok=True)
    sb_matches = json.load(open(fetch(f"{SB_RAW}/matches/43/106.json", os.path.join(DATA, "sb_matches.json")), encoding="utf-8"))
    combined = []
    for gid in ids:
        res_path = os.path.join(OUT, f"{gid}.json")
        if os.path.exists(res_path):
            combined.append(json.load(open(res_path, encoding="utf-8")))
            continue
        meta_id, trk_id = PFF[gid]
        meta = json.load(open(fetch(drive(meta_id), os.path.join(DATA, "pff", f"{gid}_meta.json")), encoding="utf-8"))[0]
        home, away = meta["homeTeam"]["name"], meta["awayTeam"]["name"]
        sb = next((m for m in sb_matches if m["home_team"]["home_team_name"] == home and m["away_team"]["away_team_name"] == away), None)
        if not sb:
            print("no StatsBomb match for", gid, home, away)
            continue
        sid = sb["match_id"]
        ev = fetch(f"{SB_RAW}/events/{sid}.json", os.path.join(DATA, "sb", f"{sid}_events.json"))
        ts = fetch(f"{SB_RAW}/three-sixty/{sid}.json", os.path.join(DATA, "sb", f"{sid}_360.json"))
        trk = fetch(drive(trk_id), os.path.join(DATA, "pff", f"{gid}.jsonl.bz2"))
        t0 = time.time()
        pff = cv.load_pff(trk)
        events = cv.load_statsbomb(ev, ts, home)
        params = cv.align(events, pff)
        moments = []
        rows = cv.compare_best_local(events, pff, params, moments=moments)
        q = queue(moments, meta.get("videoUrl"), {1: meta["startPeriod1"], 2: meta["startPeriod2"]}, top=20)
        result = {
            "pff_game_id": gid, "statsbomb_match_id": sid, "match": f"{home} v {away}", "date": meta["date"][:10],
            "events_with_360": len(events),
            "alignment": {f"p{p}_{'home' if th else 'away'}": v for (p, th), v in params.items()},
            "statsbomb_perspective": cv.compare_best_local.last_perspective,
            "summary": cv.summarise(rows), "triage_queue": q, "seconds": round(time.time() - t0, 1),
        }
        json.dump(result, open(res_path, "w", encoding="utf-8"), indent=1)
        combined.append(result)
        s = result["summary"]["all"]
        print(gid, result["match"], "n", s["n"], "median", round(s["median_m"], 2), "over5", round(s["share_over_5m"]["rate"], 3), flush=True)
    json.dump(combined, open(os.path.join(OUT, "all.json"), "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1:] or list(PFF))
