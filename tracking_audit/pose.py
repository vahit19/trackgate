"""Skeleton checks that need no ground truth.

A player's bones do not change length during a match. For each player we
take the median length of each bone as that player's reference and measure
how far every frame strays from it. If joint positions really were within
the vendor's stated error, a bone's length error could not exceed the
combined error of its two end joints (sqrt(e1^2 + e2^2) at the 90th
percentile). We compare the observed 90th-percentile length deviation with
that bound, per bone.

We also flag physically impossible joint motion: a wrist or ankle moving
faster than 30 m/s between consecutive pose frames.
"""
import math
from array import array
from collections import defaultdict

from .stats import quantile, wilson

BONES = [
    ("lShoulder", "lElbow"), ("rShoulder", "rElbow"),
    ("lElbow", "lWrist"), ("rElbow", "rWrist"),
    ("lHip", "lKnee"), ("rHip", "rKnee"),
    ("lKnee", "lAnkle"), ("rKnee", "rAnkle"),
    ("lShoulder", "rShoulder"), ("lHip", "rHip"),
]
PAIRS = [(0, 1), (2, 3), (4, 5), (6, 7)]  # left/right twins in BONES
FAST_JOINTS = ["lWrist", "rWrist", "lAnkle", "rAnkle"]
MAX_JOINT_SPEED = 30.0
MIN_FRAMES_PER_PLAYER = 250


def _dist(a, b):
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


class PoseAudit:
    def __init__(self):
        self.lengths = defaultdict(lambda: array("f"))  # (pid, bone_idx) -> lengths
        self.claimed = defaultdict(lambda: array("f"))  # bone_idx -> sqrt(e1^2+e2^2) in cm
        self.prev = {}  # pid -> (period, t, joints)
        self.frames = 0
        self.player_frames = 0
        self.joint_moves = 0
        self.fast = 0
        self.fast_examples = []

    def add(self, fr):
        self.frames += 1
        t, period = fr["t"], fr["period"]
        for p in fr["players"]:
            j = p.get("joints")
            if not j:
                continue
            pid = p["id"]
            self.player_frames += 1
            for bi, (a, b) in enumerate(BONES):
                if a in j and b in j:
                    self.lengths[(pid, bi)].append(_dist(j[a], j[b]))
                    ea, eb = j[a][3], j[b][3]
                    if ea is not None and eb is not None and len(self.claimed[bi]) < 200000:
                        self.claimed[bi].append(math.hypot(ea, eb))
            prev = self.prev.get(pid)
            if prev and prev[0] == period and t is not None and prev[1] is not None and 0 < t - prev[1] <= 0.05:
                dt = t - prev[1]
                for name in FAST_JOINTS:
                    if name in j and name in prev[2]:
                        self.joint_moves += 1
                        v = _dist(j[name], prev[2][name]) / dt
                        if v > MAX_JOINT_SPEED:
                            self.fast += 1
                            if len(self.fast_examples) < 10:
                                self.fast_examples.append({"t": t, "player_id": pid, "joint": name, "m_per_s": round(v, 1)})
            self.prev[pid] = (period, t, j)

    def summary(self):
        bones = []
        players = {pid for (pid, _) in self.lengths}
        for bi, (a, b) in enumerate(BONES):
            devs = []
            n_players = 0
            for pid in players:
                arr = self.lengths.get((pid, bi))
                if not arr or len(arr) < MIN_FRAMES_PER_PLAYER:
                    continue
                n_players += 1
                med = quantile(list(arr), 0.5)
                devs.extend(abs(x - med) * 100 for x in arr)  # cm
            if not devs:
                continue
            claimed = quantile(list(self.claimed[bi]), 0.5) if self.claimed[bi] else float("nan")
            p90 = quantile(devs, 0.9)
            exceed = sum(1 for d in devs if d > claimed) if claimed == claimed else 0
            bones.append({
                "bone": f"{a}-{b}", "players": n_players, "samples": len(devs),
                "p50_dev_cm": quantile(devs, 0.5), "p90_dev_cm": p90,
                "claimed_p90_bound_cm": claimed,
                "share_beyond_claimed": exceed / len(devs),
                "p90_over_claimed": p90 / claimed if claimed == claimed and claimed else float("nan"),
            })
        asym = []
        for li, ri in PAIRS:
            diffs = []
            for pid in players:
                la, ra = self.lengths.get((pid, li)), self.lengths.get((pid, ri))
                if la and ra and len(la) >= MIN_FRAMES_PER_PLAYER and len(ra) >= MIN_FRAMES_PER_PLAYER:
                    diffs.append(abs(quantile(list(la), 0.5) - quantile(list(ra), 0.5)) * 100)
            if diffs:
                asym.append({"pair": f"{BONES[li][0][1:]}-{BONES[li][1][1:]}", "players": len(diffs),
                             "median_cm": quantile(diffs, 0.5), "max_cm": max(diffs)})
        p, lo, hi = wilson(self.fast, self.joint_moves)
        return {
            "pose_frames": self.frames, "player_frames_with_joints": self.player_frames, "players": len(players),
            "bones": bones, "left_right_median_gap": asym,
            "impossible_joint_speed": {"count": self.fast, "of": self.joint_moves, "rate": p, "lo95": lo, "hi95": hi,
                                       "examples": self.fast_examples[:5]},
        }
