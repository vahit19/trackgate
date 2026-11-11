"""Checks that need no ground truth: a person on a pitch cannot break physics.

Limits are deliberately generous so that every flag is a clear error:
- speed above 12.5 m/s (faster than Usain Bolt's 100 m peak, ~12.4 m/s),
- acceleration above 12 m/s^2 between consecutive samples,
- a jump of more than 2.5 m within one sample at 10 Hz (a "teleport"),
- a player more than 5 m outside the pitch.
Speeds use only consecutive frames of the same player within one period.
"""
from collections import defaultdict

from .stats import wilson

MAX_SPEED = 12.5
MAX_ACCEL = 12.0
MAX_JUMP_10HZ = 2.5
OFF_PITCH_MARGIN = 5.0


class TrackingAudit:
    def __init__(self, pitch_length, pitch_width):
        self.half_l = pitch_length / 2 + OFF_PITCH_MARGIN
        self.half_w = pitch_width / 2 + OFF_PITCH_MARGIN
        self.last = {}  # player -> (frame, t, x, y, speed, detected)
        self.n = defaultdict(int)
        self.k = defaultdict(int)
        self.examples = defaultdict(list)
        self.by_detect = {True: defaultdict(int), False: defaultdict(int)}
        self.by_detect_n = {True: 0, False: 0}
        self.per_player = defaultdict(lambda: defaultdict(int))

    def _flag(self, kind, frame, pid, detail, detected):
        self.k[kind] += 1
        self.by_detect[detected][kind] += 1
        self.per_player[pid][kind] += 1
        if len(self.examples[kind]) < 20:
            self.examples[kind].append({"frame": frame, "player_id": pid, **detail})

    def add(self, fr):
        f, t, period = fr["frame"], fr["t"], fr["period"]
        for p in fr["players"]:
            pid, x, y, det = p["id"], p["x"], p["y"], p["detected"]
            self.n["player_frames"] += 1
            self.n["detected" if det else "extrapolated"] += 1
            self.by_detect_n[det] += 1
            if abs(x) > self.half_l or abs(y) > self.half_w:
                self._flag("off_pitch", f, pid, {"x": x, "y": y}, det)
            prev = self.last.get(pid)
            if prev and prev[0] == period and f - prev[1] == 1 and t is not None and prev[2] is not None and t > prev[2]:
                dt = t - prev[2]
                d = ((x - prev[3]) ** 2 + (y - prev[4]) ** 2) ** 0.5
                v = d / dt
                self.n["speed_samples"] += 1
                if v > MAX_SPEED:
                    self._flag("speed", f, pid, {"m_per_s": round(v, 2)}, det)
                if dt <= 0.15 and d > MAX_JUMP_10HZ:
                    self._flag("teleport", f, pid, {"metres": round(d, 2), "dt": round(dt, 3)}, det)
                if prev[5] is not None:
                    a = abs(v - prev[5]) / dt
                    self.n["accel_samples"] += 1
                    if a > MAX_ACCEL:
                        self._flag("accel", f, pid, {"m_per_s2": round(a, 1)}, det)
                self.last[pid] = (period, f, t, x, y, v)
            else:
                self.last[pid] = (period, f, t, x, y, None)

    def summary(self):
        out = {"player_frames": self.n["player_frames"],
               "detected_share": wilson(self.n["detected"], self.n["player_frames"])[0],
               "checks": {}}
        denom = {"off_pitch": "player_frames", "speed": "speed_samples", "teleport": "speed_samples", "accel": "accel_samples"}
        for kind, dn in denom.items():
            p, lo, hi = wilson(self.k[kind], self.n[dn])
            out["checks"][kind] = {
                "count": self.k[kind], "of": self.n[dn], "rate": p, "lo95": lo, "hi95": hi,
                "count_detected": self.by_detect[True][kind], "count_extrapolated": self.by_detect[False][kind],
                "examples": self.examples[kind][:5],
            }
        return out
