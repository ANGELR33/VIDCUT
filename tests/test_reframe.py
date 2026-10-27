import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from core.reframe import crop_x_expression, decimate, smooth_track


class SmoothTest(unittest.TestCase):
    def test_too_few_detections_returns_none(self):
        self.assertIsNone(smooth_track([(0, None), (1, None), (2, 0.5), (3, None), (4, None)]))
        self.assertIsNone(smooth_track([]))

    def test_deadzone_keeps_camera_still_for_small_moves(self):
        track = smooth_track([(i * 0.5, 0.5 + (0.03 if i % 2 else -0.03)) for i in range(10)])
        self.assertTrue(all(abs(x - 0.47) < 1e-6 or abs(x - 0.5) < 0.04 for _, x in track))
        self.assertLess(max(x for _, x in track) - min(x for _, x in track), 0.04)

    def test_speed_is_limited(self):
        track = smooth_track([(0, 0.2), (1, 0.8), (2, 0.8)], max_speed=0.25)
        self.assertLessEqual(track[1][1] - track[0][1], 0.25 + 1e-9)

    def test_gaps_hold_last_position(self):
        track = smooth_track([(0, 0.3), (1, None), (2, None), (3, 0.3)])
        self.assertTrue(all(abs(x - 0.3) < 1e-6 for _, x in track))

    def test_cut_makes_camera_jump(self):
        track = smooth_track([(0, 0.2), (1, 0.2), (2, 0.8), (3, 0.8)], cuts=[1.5])
        self.assertAlmostEqual(track[2][1], 0.8)


class ExprTest(unittest.TestCase):
    def test_decimate_limits_points_and_keeps_ends(self):
        track = [(i * 0.5, (i % 7) / 10) for i in range(60)]
        out = decimate(track, max_points=10)
        self.assertLessEqual(len(out), 10)
        self.assertEqual(out[0], track[0])
        self.assertEqual(out[-1], track[-1])

    def test_static_track_is_a_constant(self):
        self.assertEqual(crop_x_expression([(0, 0.5), (3, 0.5)], 1080 * 2), "540.0")

    def test_expression_is_clamped_to_frame(self):
        e = crop_x_expression([(0, 0.0), (2, 1.0)], 2000)
        self.assertIn("0.0+", e)
        self.assertIn("920.0", e)  # 2000-1080

    @unittest.skipUnless(shutil.which("ffmpeg"), "requiere FFmpeg")
    def test_ffmpeg_accepts_the_expression(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            expr = crop_x_expression([(0, 0.3), (1, 0.7), (2, 0.4)], 2000)
            r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                                "testsrc2=size=2000x1200:rate=12", "-t", "2", "-vf",
                                f"crop=1080:1200:'{expr}':0", str(tmp / "o.mp4")], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class ShortAudioFilterTest(unittest.TestCase):
    def test_voice_clean_switch(self):
        import os
        from unittest import mock
        from core.render_engine import short_audio_filter
        self.assertEqual(short_audio_filter(), "loudnorm=I=-16:LRA=11:TP=-1.5")
        with mock.patch.dict(os.environ, {"VOICE_CLEAN": "1"}):
            f = short_audio_filter()
        self.assertTrue(f.startswith("highpass=f=80"))
        self.assertTrue(f.endswith("loudnorm=I=-16:LRA=11:TP=-1.5"))


if __name__ == "__main__":
    unittest.main()
