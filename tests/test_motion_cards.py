import asyncio
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core import motion_cards as mc
from core.models import BRollCue, VideoEditingPlan
from core.orchestrator import AssetOrchestrator


class PureTest(unittest.TestCase):
    def test_palette_is_stable_per_concept(self):
        self.assertEqual(mc.palette_for("Inflación"), mc.palette_for("inflación"))

    def test_wrap_limits_lines(self):
        out = mc.wrap_text("una frase muchisimo mas larga de lo que cabe en tres lineas de texto", 12, 3)
        self.assertEqual(len(out.split("\n")), 3)
        self.assertTrue(out.endswith("…"))

    def test_switch(self):
        self.assertTrue(mc.enabled())
        with mock.patch.dict(os.environ, {"MOTION_FALLBACK": "0"}):
            self.assertFalse(mc.enabled())

    def test_empty_text_returns_none(self):
        self.assertIsNone(mc.make_concept_card("  ", Path(tempfile.gettempdir()) / "x.mp4"))


@unittest.skipUnless(shutil.which("ffmpeg") and mc.find_font(), "requiere FFmpeg y una fuente")
class RenderTest(unittest.TestCase):
    def test_card_is_a_playable_video_of_requested_length(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            out = mc.make_concept_card("Inflación en Argentina", tmp / "c.mp4", duration=2.0)
            self.assertIsNotNone(out)
            d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                      "default=nw=1:nk=1", str(out)], capture_output=True, text=True).stdout)
            self.assertAlmostEqual(d, 2.0, delta=0.3)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class FakeProvider:
    async def search_and_download(self, cue, target_dir):
        return None


@unittest.skipUnless(shutil.which("ffmpeg") and mc.find_font(), "requiere FFmpeg y una fuente")
class OrchestratorFallbackTest(unittest.TestCase):
    def run_plan(self, env):
        tmp = Path(tempfile.mkdtemp())
        try:
            with mock.patch.dict(os.environ, env):
                orch = AssetOrchestrator(target_dir=tmp)
                orch.providers = [FakeProvider()]
                cue = BRollCue(cue_id="c1", start_sec=1.0, end_sec=4.0, concept="Inflación", search_query_en="inflation",
                               confidence=0.9, reasoning="x")
                plan = VideoEditingPlan(video_summary="x", total_original_duration_sec=10, timeline=[], b_rolls=[cue])
                asyncio.run(orch.process_all_brolls(plan))
                return cue.download_status, cue.local_file_path, (tmp / "c1_card.mp4").exists()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_no_provider_result_generates_a_card(self):
        status, path, exists = self.run_plan({"MOTION_FALLBACK": "1"})
        self.assertEqual(status, "COMPLETED")
        self.assertTrue(path.endswith("_card.mp4"))
        self.assertTrue(exists)

    def test_disabled_keeps_old_behaviour(self):
        status, path, _ = self.run_plan({"MOTION_FALLBACK": "0"})
        self.assertEqual(status, "FAILED")


if __name__ == "__main__":
    unittest.main()
