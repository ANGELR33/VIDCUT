import shutil
import tempfile
import unittest
from pathlib import Path

from core.visual_scene_engine import VisualSceneEngine
from core.models import ActionType, TimelineSegment, VisualScene, VideoEditingPlan
from core.timeline import TimelineMapper


class VisualSceneEngineTests(unittest.TestCase):
    def test_accepts_known_scene_types(self):
        for kind in ("automation", "comparison", "cause_effect", "concept", "timeline", "flow", "network", "stat", "sequence", "route", "layers", "title_card", "code_terminal", "cyber_diagram", "pixel_team"):
            scene = VisualSceneEngine.validate({"kind": kind, "duration": 4, "title": "Demo"})
            self.assertEqual(scene["kind"], kind)

    def test_rejects_unknown_scene_type(self):
        with self.assertRaises(ValueError):
            VisualSceneEngine.validate({"kind": "untrusted-render-command"})

    def test_rejects_duration_out_of_bounds(self):
        with self.assertRaises(ValueError):
            VisualSceneEngine.validate({"kind": "concept", "duration": 60})

    def test_rejects_non_finite_or_non_numeric_duration(self):
        for duration in (float("nan"), float("inf"), float("-inf"), "not-a-number", None):
            with self.subTest(duration=duration):
                with self.assertRaises(ValueError):
                    VisualSceneEngine.validate({"kind": "concept", "duration": duration})

    def test_fps_must_be_with_supported_range(self):
        for fps in (0, 11, 31, "bad", None):
            with self.subTest(fps=fps):
                with self.assertRaises(ValueError):
                    VisualSceneEngine(fps=fps)

    def test_render_rejects_oversized_resolution_before_allocating_frames(self):
        engine = VisualSceneEngine(fps=12)
        with tempfile.TemporaryDirectory(prefix="vidcut-visual-test-") as tmp:
            with self.assertRaisesRegex(ValueError, "máxima"):
                engine.render({"kind": "concept", "duration": 1},
                              Path(tmp) / "oversized.mov", width=7680, height=4320)

    def test_render_requires_mov_for_alpha_output(self):
        engine = VisualSceneEngine(fps=12)
        with tempfile.TemporaryDirectory(prefix="vidcut-visual-test-") as tmp:
            with self.assertRaisesRegex(ValueError, r"\.mov"):
                engine.render({"kind": "concept", "duration": 1},
                              Path(tmp) / "scene.mp4", width=320, height=240)

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg is required for render smoke test")
    def test_all_scene_types_render_transparent_mov(self):
        kinds = ("automation", "comparison", "cause_effect", "concept",
                 "timeline", "flow", "network", "stat", "sequence", "route", "layers",
                 "title_card", "code_terminal", "cyber_diagram", "pixel_team")
        with tempfile.TemporaryDirectory(prefix="vidcut-visual-test-") as tmp:
            engine = VisualSceneEngine(fps=12)
            for kind in kinds:
                with self.subTest(kind=kind):
                    output = Path(tmp) / f"{kind}.mov"
                    result = engine.render(
                        {"kind": kind, "duration": 1, "title": f"Demo {kind}",
                         "label_a": "VALOR / ORIGEN", "label_b": "RESULTADO"},
                        output, width=640, height=360
                    )
                    self.assertEqual(result, output)
                    self.assertTrue(output.exists())
                    self.assertGreater(output.stat().st_size, 1000)


    def test_visual_scene_model_is_part_of_editing_plan(self):
        scene = VisualScene(
            scene_id="visual_1", start_sec=3, end_sec=7, kind="automation",
            title="Manual a automático", label_a="PERSONA", label_b="SISTEMA",
            spoken_phrase="La IA automatiza tareas", reasoning="Muestra el cambio", confidence=0.9
        )
        self.assertEqual(scene.kind, "automation")
        self.assertTrue(scene.enabled)
        self.assertEqual(VideoEditingPlan.model_fields["visual_scenes"].default_factory(), [])

    def test_scene_timing_maps_through_silence_cuts(self):
        mapper = TimelineMapper([
            TimelineSegment(start_sec=0, end_sec=5, action=ActionType.KEEP),
            TimelineSegment(start_sec=10, end_sec=20, action=ActionType.KEEP),
        ])
        mapped = mapper.map_first(12, 16)
        self.assertEqual(mapped, (7.0, 11.0))

    def test_limits_text_lengths(self):
        scene = VisualSceneEngine.validate({
            "kind": "concept", "title": "T" * 500, "label_a": "A" * 200, "label_b": "B" * 200
        })
        self.assertEqual(len(scene["title"]), 100)
        self.assertEqual(len(scene["label_a"]), 48)
        self.assertEqual(len(scene["label_b"]), 48)


if __name__ == "__main__":
    unittest.main()
