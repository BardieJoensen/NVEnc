import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import target_quality as tq


class Pure(unittest.TestCase):
    def test_merge_and_cap(self):
        # fps 10: min 20 frames, max 100 frames
        sc = tq.merge_scenes([5, 30, 200, 210, 500], 600, 10)
        self.assertEqual(sc[0][0], 0)
        self.assertEqual(sc[-1][1], 600)
        for (a, b), (c, d) in zip(sc, sc[1:]):
            self.assertEqual(b, c)
        for a, b in sc:
            self.assertGreaterEqual(b - a, 20)
            self.assertLessEqual(b - a, 100)

    def test_merge_noop_when_long(self):
        self.assertEqual(tq.merge_scenes([50], 100, 10), [(0, 50), (50, 100)])

    def test_sample_range(self):
        self.assertEqual(tq.sample_range(0, 30, 48), (0, 30))
        self.assertEqual(tq.sample_range(0, 100, 48), (26, 74))

    def test_solve(self):
        pts = [(24, 96.0), (30, 92.0), (36, 86.0)]
        self.assertAlmostEqual(tq.solve_qvbr(pts, 92.0), 30.0)
        self.assertAlmostEqual(tq.solve_qvbr(pts, 89.0), 33.0)
        self.assertEqual(tq.solve_qvbr(pts, 50.0), 40.0)    # clamp high
        self.assertEqual(tq.solve_qvbr(pts, 99.9), 20.0)    # clamp low via extrapolation
        tq.solve_qvbr([(24, 90.0), (30, 91.0), (36, 85.0)], 88)  # non-monotone noise
        # flat scene: nothing helps -> highest QVBR
        self.assertEqual(tq.solve_qvbr([(24, 90.0), (30, 90.0), (36, 90.0)], 85.0), 40.0)

    def test_predict_and_pick(self):
        self.assertAlmostEqual(tq.predict_size([(24, 4000), (36, 1000)], 30), 2000, delta=1)
        sc = [{"len": 100, "score_pts": [(24, 96), (30, 92), (36, 86)], "size_pts": [(24, 4000), (30, 2000), (36, 1000)]},
              {"len": 100, "score_pts": [(24, 90), (30, 84), (36, 78)], "size_pts": [(24, 8000), (30, 4000), (36, 2000)]}]
        t, want = tq.pick_target(sc, 30)
        _, size = tq.plan_for_target(sc, t)
        self.assertAlmostEqual(size / want, 1.0, delta=0.03)

    def test_zones(self):
        a = tq.zone_args([(0, 10), (10, 20), (20, 30)], [30, 26.5, 34], 30)
        self.assertEqual(a, ["--dynamic-rc", "start=10,end=19,qvbr=26.5,max-bitrate=50000",
                             "--dynamic-rc", "start=20,end=29,qvbr=34,max-bitrate=50000"])
        self.assertEqual(tq.trim_arg([(0, 10), (20, 30)]), "0:9,20:29")


if __name__ == "__main__":
    unittest.main()
