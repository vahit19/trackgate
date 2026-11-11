"""Builds the README results table from results/worldcup/*.json.

--check fails (exit 1) if the table in README.md differs from the results,
so CI catches any number in the README that the data does not support.
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
START, END = "<!-- results:start -->", "<!-- results:end -->"


def pct(x):
    return f"{100 * x:.1f}%"


def table():
    rows = []
    tot = {"n": 0, "over2": 0, "over5": 0, "est_n": 0, "est_over5": 0, "vis_n": 0, "vis_over5": 0}
    files = sorted(f for f in glob.glob(os.path.join(ROOT, "results", "worldcup", "*.json")) if re.search(r"\d+\.json$", f))
    for f in files:
        r = json.load(open(f, encoding="utf-8"))
        a = r["summary"]["all"]
        est = r["summary"]["by_pff_visibility"].get("ESTIMATED", {"n": 0, "share_over_5m": {"rate": 0}})
        vis = r["summary"]["by_pff_visibility"].get("VISIBLE", {"n": 0, "share_over_5m": {"rate": 0}})
        rows.append(f'| {r["match"]} | {r["date"]} | {a["n"]:,} | {a["median_m"]:.2f} | {a["p90_m"]:.2f} | '
                    f'{pct(a["share_over_2m"]["rate"])} | {pct(a["share_over_5m"]["rate"])} | {pct(est["share_over_5m"]["rate"])} |')
        tot["n"] += a["n"]
        tot["over2"] += round(a["share_over_2m"]["rate"] * a["n"])
        tot["over5"] += round(a["share_over_5m"]["rate"] * a["n"])
        tot["est_n"] += est["n"]
        tot["est_over5"] += round(est["share_over_5m"]["rate"] * est["n"])
        tot["vis_n"] += vis["n"]
        tot["vis_over5"] += round(vis["share_over_5m"]["rate"] * vis["n"])
    head = ("| Match | Date | Player positions compared | Median gap (m) | 90th pct gap (m) | Gap > 2 m | Gap > 5 m | "
            "Gap > 5 m when PFF says ESTIMATED |\n|---|---|---:|---:|---:|---:|---:|---:|")
    foot = (f'| **All {len(rows)} matches** | | **{tot["n"]:,}** | | | **{pct(tot["over2"] / tot["n"])}** | '
            f'**{pct(tot["over5"] / tot["n"])}** | **{pct(tot["est_over5"] / max(1, tot["est_n"]))}** |')
    return "\n".join([head] + rows + [foot]), tot, len(rows)


def main():
    t, tot, n = table()
    readme = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
    block = f"{START}\n{t}\n{END}"
    new = re.sub(re.escape(START) + r".*?" + re.escape(END), block, readme, flags=re.S)
    if "--check" in sys.argv:
        if new != readme:
            print("README results table is out of date with results/worldcup/*.json")
            sys.exit(1)
        print("README table matches results")
        return
    open(os.path.join(ROOT, "README.md"), "w", encoding="utf-8").write(new)
    print(t)
    print(json.dumps(tot))


if __name__ == "__main__":
    main()
