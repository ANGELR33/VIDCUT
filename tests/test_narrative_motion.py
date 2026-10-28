import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core import narrative_motion


class NarrativeMotionTests(unittest.TestCase):
    def test_rejects_invalid_duration_before_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = narrative_motion.render_scene(
                {"kind": "concept", "duration": 30}, Path(tmp) / "scene.mov", 1280, 720
            )
        self.assertIsNone(result)

    def test_unavailable_renderer_fails_open(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(narrative_motion, "available", return_value=False):
            result = narrative_motion.render_scene(
                {"kind": "cyber_diagram", "duration": 4}, Path(tmp) / "scene.mov", 1280, 720
            )
        self.assertIsNone(result)

    def test_render_uses_dynamic_props_and_promotes_valid_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "scene.mov"

            def fake_run(cmd, **kwargs):
                props_path = Path(cmd[2])
                partial = Path(cmd[3])
                props = json.loads(props_path.read_text(encoding="utf-8"))
                self.assertEqual(cmd[4], "NarrativeScene")
                self.assertEqual(props["kind"], "cyber_diagram")
                self.assertEqual(props["spokenPhrase"], "encuentra una conexión")
                self.assertEqual(props["width"], 1280)
                partial.write_bytes(b"x" * 25000)

                class Result:
                    returncode = 0
                    stdout = "RENDER_OK"
                    stderr = ""
                return Result()

            with mock.patch.object(narrative_motion, "available", return_value=True), \
                 mock.patch.object(narrative_motion.subprocess, "run", side_effect=fake_run):
                result = narrative_motion.render_scene(
                    {"kind": "cyber_diagram", "duration": 4, "title": "Conexiones",
                     "label_a": "Documentos", "label_b": "Hallazgo",
                     "spoken_phrase": "encuentra una conexión"},
                    out, 1280, 720, fps=30,
                )
            self.assertIsNotNone(result)
            self.assertTrue(result.is_file())
            self.assertGreater(result.stat().st_size, 20000)
            self.assertFalse(result.with_name(result.stem + ".partial.mov").exists())


if __name__ == "__main__":
    unittest.main()
