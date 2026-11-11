"""Unit tests on small hand-built inputs. They test the logic; results in the
README come from real data (see scripts/)."""
import math
import unittest

from tracking_audit import crossvendor as cv
from tracking_audit.physics import TrackingAudit
from tracking_audit.stats import wilson, zero_upper
from tracking_audit.triage import numbers_supported, queue


def frame(i, players, period=1, fps=10):
    return {"frame": i, "t": i / fps, "period": period,
            "players": [{"id": pid, "x": x, "y": y, "detected": True, "joints": None} for pid, x, y in players]}


class PhysicsTests(unittest.TestCase):
    def test_normal_running_is_not_flagged(self):
        a = TrackingAudit(105, 68)
        for i in range(50):
            a.add(frame(i, [(1, i * 0.7, 0.0)]))  # 7 m/s
        s = a.summary()["checks"]
        self.assertEqual(s["speed"]["count"], 0)
        self.assertEqual(s["teleport"]["count"], 0)

    def test_teleport_and_speed_are_flagged(self):
        a = TrackingAudit(105, 68)
        a.add(frame(0, [(1, 0.0, 0.0)]))
        a.add(frame(1, [(1, 4.0, 0.0)]))  # 4 m in 0.1 s = 40 m/s
        s = a.summary()["checks"]
        self.assertEqual(s["speed"]["count"], 1)
        self.assertEqual(s["teleport"]["count"], 1)

    def test_off_pitch(self):
        a = TrackingAudit(105, 68)
        a.add(frame(0, [(1, 0.0, 45.0)]))
        self.assertEqual(a.summary()["checks"]["off_pitch"]["count"], 1)

    def test_gap_between_frames_is_not_a_speed_sample(self):
        a = TrackingAudit(105, 68)
        a.add(frame(0, [(1, 0.0, 0.0)]))
        a.add(frame(5, [(1, 4.0, 0.0)]))  # frames not consecutive
        self.assertEqual(a.summary()["checks"]["speed"]["of"], 0)


class StatsTests(unittest.TestCase):
    def test_wilson(self):
        p, lo, hi = wilson(0, 100)
        self.assertEqual(p, 0)
        self.assertLess(hi, 0.05)
        p, lo, hi = wilson(50, 100)
        self.assertTrue(lo < 0.5 < hi)

    def test_zero_upper(self):
        self.assertAlmostEqual(zero_upper(59), 0.0495, places=3)


class CrossVendorTests(unittest.TestCase):
    def setUp(self):
        # PFF frames at 30 fps; ten players per side standing still at known spots.
        self.home = [(-30 + 6 * k, -20 + 4 * k) for k in range(10)]
        self.away = [(30 - 6 * k, 20 - 4 * k) for k in range(10)]
        times = [i / 30 for i in range(30 * 60)]
        frames = [{"home": [(x, y, "VISIBLE") for x, y in self.home],
                   "away": [(x, y, "VISIBLE") for x, y in self.away]} for _ in times]
        self.pff = {1: (times, frames), 2: (times, frames)}

    def sb_events(self, flip, noise=0.0):
        s = -1 if flip else 1
        evs = []
        for k in range(120):
            mates = [(s * x + noise, s * y, False) for x, y in self.home]
            opps = [(s * x + noise, s * y, False) for x, y in self.away]
            evs.append({"t": 5 + k * 0.4, "period": 1, "team_home": True, "poss_home": True,
                        "mates": mates, "opps": opps, "type": "Pass"})
        return evs

    def test_alignment_recovers_flipped_orientation(self):
        sb = self.sb_events(flip=True)
        params = cv.align(sb, self.pff)
        self.assertEqual((params[(1, True)]["sx"], params[(1, True)]["sy"]), (-1, -1))
        rows = cv.compare(sb, self.pff, params)
        self.assertAlmostEqual(max(d for d, _ in rows), 0.0, places=6)

    def test_known_offset_is_measured(self):
        sb = self.sb_events(flip=False, noise=3.0)
        params = cv.align(sb, self.pff)
        s = cv.summarise(cv.compare(sb, self.pff, params))["all"]
        self.assertAlmostEqual(s["median_m"], 3.0, places=6)
        self.assertEqual(s["share_over_2m"]["rate"], 1.0)
        self.assertEqual(s["share_over_5m"]["rate"], 0.0)


class TriageTests(unittest.TestCase):
    def test_invented_numbers_are_caught(self):
        facts = {"median_m": 2.17, "share_over_5m": {"rate": 0.133}}
        self.assertEqual(numbers_supported("Median 2.2 m; 13.3% over 5 m.", facts), [])
        self.assertEqual(numbers_supported("Median 2.2 m; 27% over 5 m.", facts), ["27"])

    def test_queue_orders_and_links(self):
        ms = [{"period": 1, "pff_period_t": 10.0, "median_m": 1.0, "max_m": 2.0},
              {"period": 2, "pff_period_t": 5.0, "median_m": 9.0, "max_m": 30.0}]
        q = queue(ms, "https://example.org/film_room/abc", {1: 100.0, 2: 3000.0}, top=2)
        self.assertEqual(q[0]["median_m"], 9.0)
        self.assertTrue(q[0]["video"].endswith("/3005.000"))


if __name__ == "__main__":
    unittest.main()
