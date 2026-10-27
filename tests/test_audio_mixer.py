import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from core.audio_mixer import build_filter, find_sfx, mix_audio


class FilterTest(unittest.TestCase):
    def test_graph_has_all_inputs_and_ducking(self):
        g = build_filter(2, [1000, 5000], [0.3, 0.3], True, [{"start": 1.0, "end": 3.0}])
        self.assertIn("adelay=1000|1000", g)
        self.assertIn("[3:a]", g)
        self.assertIn("between(t,1.00,3.00)", g)
        self.assertIn("amix=inputs=4", g)

    def test_no_music_no_duck(self):
        g = build_filter(1, [0], [0.3], False, [])
        self.assertNotIn("[mus]", g)


class MixTest(unittest.TestCase):
    def test_returns_false_without_sounds(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            self.assertFalse(mix_audio(tmp / "a.mp4", tmp / "o.mp4", [{"t": 1, "name": "pop"}], tmp))
            self.assertIsNone(find_sfx(tmp, "pop"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "requiere FFmpeg")
    def test_real_mix_keeps_duration(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            run = lambda *a: subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *a], check=True)
            run("-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24", "-f", "lavfi", "-i", "sine=frequency=300",
                "-t", "6", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(tmp / "in.mp4"))
            run("-f", "lavfi", "-i", "sine=frequency=900:duration=0.4", str(tmp / "pop.wav"))
            run("-f", "lavfi", "-i", "sine=frequency=200:duration=3", str(tmp / "music.wav"))
            ok = mix_audio(tmp / "in.mp4", tmp / "out.mp4", [{"t": 2.0, "name": "pop"}], tmp,
                           music=tmp / "music.wav", duck=[{"start": 0, "end": 3}])
            self.assertTrue(ok)
            d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                      "default=nw=1:nk=1", str(tmp / "out.mp4")], capture_output=True, text=True).stdout)
            self.assertAlmostEqual(d, 6.0, delta=0.5)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
