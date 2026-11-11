"""Cross-vendor agreement: the same match, the same broadcast moments, two providers.

StatsBomb 360 gives player positions at each event (freeze frames, players
visible in the broadcast). PFF FC gives broadcast tracking at ~30 fps with a
VISIBLE / ESTIMATED flag per player. Neither is ground truth; where they
disagree by metres, at least one of them is wrong by metres.

Alignment is fitted from the data, never assumed:
- pitch orientation per (period, team in possession): the sign of x and y
  that best overlays the two feeds,
- clock offset per period: the shift (within +-4 s) that best overlays them.
Players are matched within each team by minimum total distance (Hungarian).
"""
import bz2
import json
import math
from bisect import bisect_left
from collections import defaultdict

import numpy as np
from scipy.optimize import linear_sum_assignment

from .stats import quantile, wilson

PITCH_L, PITCH_W = 105.0, 68.0


def _ts(s):
    h, m, sec = s.split(":")
    return int(h) * 3600 + int(m) * 60 + float(sec)


def load_pff(path, smoothed=False):
    """period -> (times[], frames[]) with frames[i] = {"home": [(x,y,vis)], "away": [...]}"""
    hk, ak = ("homePlayersSmoothed", "awayPlayersSmoothed") if smoothed else ("homePlayers", "awayPlayers")
    per = defaultdict(lambda: ([], []))
    with bz2.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            p, t = r.get("period"), r.get("periodElapsedTime")
            if p is None or t is None or not r.get(hk):
                continue
            fr = {
                "home": [(q["x"], q["y"], q.get("visibility")) for q in r[hk] if q.get("x") is not None],
                "away": [(q["x"], q["y"], q.get("visibility")) for q in (r.get(ak) or []) if q.get("x") is not None],
            }
            per[p][0].append(t)
            per[p][1].append(fr)
    return dict(per)


def load_statsbomb(events_path, three_sixty_path, home_name):
    with open(events_path, encoding="utf-8") as f:
        events = {e["id"]: e for e in json.load(f)}
    with open(three_sixty_path, encoding="utf-8") as f:
        frames = json.load(f)
    out = []
    for fr in frames:
        e = events.get(fr["event_uuid"])
        if not e or e.get("period") not in (1, 2) or not fr.get("freeze_frame"):
            continue
        poss_home = e["possession_team"]["name"] == home_name if e.get("possession_team") else e["team"]["name"] == home_name
        team_home = e["team"]["name"] == home_name
        # StatsBomb orients each freeze frame so the event team attacks left to right
        mates, opps = [], []
        for q in fr["freeze_frame"]:
            x = q["location"][0] / 120 * PITCH_L - PITCH_L / 2
            y = PITCH_W / 2 - q["location"][1] / 80 * PITCH_W
            (mates if q["teammate"] else opps).append((x, y, q.get("actor", False)))
        out.append({"t": _ts(e["timestamp"]), "period": e["period"], "team_home": team_home,
                    "poss_home": poss_home, "mates": mates, "opps": opps, "type": e["type"]["name"]})
    return out


def _nearest(times, t):
    i = bisect_left(times, t)
    if i == 0:
        return 0
    if i == len(times):
        return len(times) - 1
    return i if times[i] - t < t - times[i - 1] else i - 1


def _match(sb_pts, pff_pts, sx, sy, pairs=None, team=None):
    if not sb_pts or not pff_pts:
        return []
    A = np.array([(sx * x, sy * y) for x, y, *_ in sb_pts])
    B = np.array([(x, y) for x, y, _ in pff_pts])
    D = np.sqrt(((A[:, None, :] - B[None, :, :]) ** 2).sum(-1))
    r, c = linear_sum_assignment(D)
    if pairs is not None:
        for i, j in zip(r, c):
            pairs.append([round(float(A[i, 0]), 2), round(float(A[i, 1]), 2), round(float(B[j, 0]), 2),
                          round(float(B[j, 1]), 2), pff_pts[j][2], team])
    return [(float(D[i, j]), pff_pts[j][2]) for i, j in zip(r, c)]


def _cost(sb, pff, period, team_home, sx, sy, offset, sample):
    times, frames = pff[period]
    errs = []
    for ev in sample:
        fr = frames[_nearest(times, ev["t"] + offset)]
        mine, other = ("home", "away") if ev["team_home"] == team_home else ("away", "home")
        errs += [d for d, _ in _match(ev["mates"], fr["home" if ev["team_home"] else "away"], sx, sy)]
        errs += [d for d, _ in _match(ev["opps"], fr["away" if ev["team_home"] else "home"], sx, sy)]
    return float(np.median(errs)) if errs else float("inf")


def align(sb, pff):
    """Fit orientation per (period, event team) and a clock offset per period."""
    params = {}
    for period in (1, 2):
        evs = [e for e in sb if e["period"] == period]
        if not evs or period not in pff:
            continue
        best_off, best_c = 0.0, float("inf")
        for team_home in (True, False):
            group = [e for e in evs if e["team_home"] == team_home][::6][:80]
            if not group:
                continue
            best = min(((_cost(sb, pff, period, team_home, sx, sy, 0.0, group), sx, sy)
                        for sx in (1, -1) for sy in (1, -1)))
            params[(period, team_home)] = {"sx": best[1], "sy": best[2]}
        group = evs[::8][:120]
        for off in np.arange(-4.0, 4.01, 0.2):
            c = np.median([_cost(sb, pff, period, th, params[(period, th)]["sx"], params[(period, th)]["sy"], off,
                                 [e for e in group if e["team_home"] == th])
                           for th in (True, False) if (period, th) in params])
            if c < best_c:
                best_c, best_off = c, float(off)
        for th in (True, False):
            if (period, th) in params:
                params[(period, th)]["offset"] = best_off
    return params


def compare(sb, pff, params):
    rows = []
    for ev in sb:
        key = (ev["period"], ev["team_home"])
        if key not in params or ev["period"] not in pff:
            continue
        pr = params[key]
        times, frames = pff[ev["period"]]
        fr = frames[_nearest(times, ev["t"] + pr["offset"])]
        for d, vis in _match(ev["mates"], fr["home" if ev["team_home"] else "away"], pr["sx"], pr["sy"]):
            rows.append((d, vis))
        for d, vis in _match(ev["opps"], fr["away" if ev["team_home"] else "home"], pr["sx"], pr["sy"]):
            rows.append((d, vis))
    return rows


def summarise(rows):
    def block(ds):
        n = len(ds)
        out = {"n": n, "median_m": quantile(ds, 0.5), "p90_m": quantile(ds, 0.9)}
        for thr in (1, 2, 5):
            k = sum(1 for d in ds if d > thr)
            p, lo, hi = wilson(k, n)
            out[f"share_over_{thr}m"] = {"rate": p, "lo95": lo, "hi95": hi}
        return out
    alld = [d for d, _ in rows]
    by = defaultdict(list)
    for d, v in rows:
        by[v or "UNKNOWN"].append(d)
    # histogram of gaps: 0.5 m bins up to 10 m, last bin = 10 m and beyond
    hist = [0] * 21
    for d in alld:
        hist[min(20, int(d / 0.5))] += 1
    return {"all": block(alld), "by_pff_visibility": {k: block(v) for k, v in by.items()},
            "histogram_0_5m_bins": hist}


def compare_best_local(sb, pff, params, window=1.0, step=0.1, moments=None):
    """Conservative variant: for every event, shift the clock within +-window
    seconds to the moment where the two feeds agree best. Disagreement that
    survives this is not a timing artefact. If `moments` is a list, one record
    per event is appended to it (for the triage queue)."""
    rows = []
    offs = np.arange(-window, window + 1e-9, step)
    perspective = defaultdict(int)
    for ev in sb:
        key = (ev["period"], ev["team_home"])
        if key not in params or ev["period"] not in pff:
            continue
        pr = params[key]
        times, frames = pff[ev["period"]]
        mine, theirs = ("home", "away") if ev["team_home"] else ("away", "home")
        # Some StatsBomb 360 frames (duels, fouls, failed receipts) are recorded from
        # the other team's perspective: the pitch is rotated 180 degrees and the
        # teammate flag refers to that team. Both readings are tried; the reading is a
        # discrete label, not a fit, and how often each wins is reported.
        readings = (("event_team", pr["sx"], pr["sy"], mine, theirs),
                    ("other_team", -pr["sx"], -pr["sy"], theirs, mine))
        best = None
        for o in offs:
            fr = frames[_nearest(times, ev["t"] + pr["offset"] + o)]
            for label, sx, sy, a, b in readings:
                m = _match(ev["mates"], fr[a], sx, sy) + _match(ev["opps"], fr[b], sx, sy)
                if m:
                    score = float(np.median([d for d, _ in m]))
                    if best is None or score < best[0]:
                        best = (score, m, ev["t"] + pr["offset"] + o, label)
        if best:
            rows.extend(best[1])
            perspective[best[3]] += 1
            if moments is not None:
                ds = [d for d, _ in best[1]]
                # positions of both sources at the chosen moment, in PFF's pitch frame
                fr = frames[_nearest(times, best[2])]
                label, sx, sy, a, b = next(rd for rd in readings if rd[0] == best[3])
                pairs = []
                _match(ev["mates"], fr[a], sx, sy, pairs, a)
                _match(ev["opps"], fr[b], sx, sy, pairs, b)
                moments.append({
                    "pairs": pairs,
                    "period": ev["period"], "statsbomb_t": ev["t"], "pff_period_t": round(best[2], 2),
                    "event": ev["type"], "players": len(ds), "median_m": round(best[0], 2), "max_m": round(max(ds), 2),
                    "estimated_players": sum(1 for _, v in best[1] if v == "ESTIMATED"), "perspective": best[3],
                })
    compare_best_local.last_perspective = dict(perspective)
    return rows
