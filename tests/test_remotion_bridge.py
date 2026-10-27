import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core import remotion_renderer as rr
from core.animations import choose_animation


class PropsTest(unittest.TestCase):
    def test_counter_props(self):
        payload = rr.build_props(choose_animation("subió 300%", "Inflación"), 3.5)
        self.assertEqual(payload["composition"], "counter")
        p = payload["props"]
        self.assertEqual((p["value"], p["suffix"], p["durationSec"]), (300.0, "%", 3.5))
        self.assertTrue(p["palette"]["accent"].startswith("#"))

    def test_compare_and_steps_carry_items(self):
        self.assertEqual(len(rr.build_props(choose_animation("A 40% contra B 25%", "T"), 4)["props"]["items"]), 2)
        self.assertEqual(len(rr.build_props(choose_animation("primero a, segundo b", "T"), 4)["props"]["items"]), 2)

    def test_concept_is_not_a_remotion_composition(self):
        self.assertIsNone(rr.build_props({"kind": "concept", "title": "x"}, 4))

    def test_payload_is_json_serializable(self):
        json.dumps(rr.build_props(choose_animation("subió 300%", "T"), 4))


class SafetyTest(unittest.TestCase):
    def test_disabled_by_default(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("REMOTION", None)
            self.assertFalse(rr.enabled())
            self.assertIsNone(rr.render(choose_animation("subió 300%", "T"), Path(tempfile.gettempdir()) / "x.mp4"))

    def test_enabled_without_node_modules_returns_none(self):
        with mock.patch.dict(os.environ, {"REMOTION": "1"}), mock.patch.object(rr, "available", return_value=False):
            self.assertIsNone(rr.render(choose_animation("subió 300%", "T"), Path(tempfile.gettempdir()) / "x.mp4"))

    def test_failing_node_returns_none(self):
        failed = mock.Mock(returncode=1, stdout="", stderr="boom")
        with mock.patch.dict(os.environ, {"REMOTION": "1"}), mock.patch.object(rr, "available", return_value=True), \
                mock.patch.object(rr.subprocess, "run", return_value=failed):
            self.assertIsNone(rr.render(choose_animation("subió 300%", "T"), Path(tempfile.gettempdir()) / "y.mp4"))

    def test_timeout_returns_none(self):
        with mock.patch.dict(os.environ, {"REMOTION": "1"}), mock.patch.object(rr, "available", return_value=True), \
                mock.patch.object(rr.subprocess, "run", side_effect=rr.subprocess.TimeoutExpired("node", 1)):
            self.assertIsNone(rr.render(choose_animation("subió 300%", "T"), Path(tempfile.gettempdir()) / "z.mp4"))


class ProjectFilesTest(unittest.TestCase):
    """Comprobaciones estáticas del proyecto Remotion (no se puede compilar sin npm)."""

    def test_every_composition_has_a_component_file_and_is_registered(self):
        root = (rr.REMOTION_DIR / "src" / "Root.tsx").read_text(encoding="utf-8")
        for name in rr.COMPOSITIONS:
            self.assertIn(f'id="{name}"', root)
            self.assertTrue((rr.REMOTION_DIR / "src" / f"{name.capitalize()}.tsx").is_file())

    def test_package_json_is_valid_and_pins_one_remotion_family(self):
        pkg = json.loads((rr.REMOTION_DIR / "package.json").read_text(encoding="utf-8"))
        for dep in ("remotion", "@remotion/bundler", "@remotion/renderer", "@remotion/cli", "react", "react-dom"):
            self.assertIn(dep, pkg["dependencies"])


if __name__ == "__main__":
    unittest.main()
