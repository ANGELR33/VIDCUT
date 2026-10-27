import shutil
import tempfile
import unittest
from pathlib import Path

from core.visual_scene_engine import VisualSceneEngine


class VisualSceneEngineTests(unittest.TestCase):
    def test_accepts_known_scene_types(self):
        for kind in ("automation", "comparison", "cause_effect", "concept"):
            scene = VisualSceneEngine.validate({"kind": kind, "duration": 4, "title": "Demo"})
            self.assertEqual(scene["kind"], kind)

    def test_rejects_unknown_scene_type(self):
        with self.assertRaises(ValueError):
            VisualSceneEngine.validate({"kind": "untrusted-render-command"})

    def test_rejects_duration_out_of_bounds(self):
        with self.assertRaises(ValueError):
            VisualSceneEngine.validate({"kind": "concept", "duration": 60})

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg is required for render smoke test")
    def test_render_produces_transparent_mov(self):
        with tempfile.TemporaryDirectory(prefix="vidcut-visual-test-") as tmp:
            output = Path(tmp) / "automation.mov"
            result = VisualSceneEngine(fps=12).render(
                {"kind": "automation", "duration": 1, "title": "Manual a automático",
                 "label_a": "PERSONA", "label_b": "SISTEMA"},
                output, width=640, height=360
            )
            self.assertEqual(result, output)
            self.assertTrue(output.exists())
            self.assertGreater(output.stat().st_size, 1000)

    def test_limits_text_lengths(self):
        scene = VisualSceneEngine.validate({
            "kind": "concept", "title": "T" * 500, "label_a": "A" * 200, "label_b": "B" * 200
        })
        self.assertEqual(len(scene["title"]), 100)
        self.assertEqual(len(scene["label_a"]), 48)
        self.assertEqual(len(scene["label_b"]), 48)


if __name__ == "__main__":
    unittest.main()
