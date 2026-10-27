import unittest

from core.animations import choose_animation, parse_number


class ParseTest(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(parse_number("1.200.000"), 1200000.0)
        self.assertEqual(parse_number("3,5"), 3.5)
        self.assertEqual(parse_number("300"), 300.0)
        self.assertIsNone(parse_number("abc"))


class ChooseTest(unittest.TestCase):
    def test_percentage_becomes_counter(self):
        a = choose_animation("la inflación subió 300%", "Inflación")
        self.assertEqual((a["kind"], a["value"], a["suffix"]), ("counter", 300.0, "%"))

    def test_money_keeps_prefix(self):
        a = choose_animation("ganó $50 millones el año pasado")
        self.assertEqual(a["kind"], "counter")
        self.assertEqual(a["prefix"], "$")

    def test_a_year_alone_is_not_a_counter(self):
        self.assertEqual(choose_animation("esto pasó en 1998", "Historia")["kind"], "concept")

    def test_vs_becomes_compare_with_same_units(self):
        a = choose_animation("Argentina 40% contra Chile 25%", "Comparación")
        self.assertEqual(a["kind"], "compare")
        self.assertEqual([i["value"] for i in a["items"]], [40.0, 25.0])

    def test_vs_with_different_units_does_not_compare(self):
        self.assertNotEqual(choose_animation("10 años contra 25%")["kind"], "compare")

    def test_ordinals_become_steps(self):
        a = choose_animation("primero ahorra, segundo invierte, tercero espera", "Plan")
        self.assertEqual(a["kind"], "steps")
        self.assertEqual(a["items"], ["ahorra", "invierte", "espera"])

    def test_no_data_is_concept_and_never_invents_numbers(self):
        a = choose_animation("la Torre Eiffel es muy famosa", "Torre Eiffel")
        self.assertEqual(a, {"kind": "concept", "title": "Torre Eiffel"})

    def test_largest_value_wins_with_scale(self):
        a = choose_animation("pasó de 5 millones a 2 mil usuarios")
        self.assertEqual(a["value"], 5.0)
        self.assertEqual(a["suffix"], " M")


import asyncio
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest import mock

from core import animation_renderer as ar
from core.models import BRollCue, VideoEditingPlan
from core.orchestrator import AssetOrchestrator


class RendererPureTest(unittest.TestCase):
    def test_number_format_is_spanish_style(self):
        self.assertEqual(ar.format_number(1234567), "1.234.567")
        self.assertEqual(ar.format_number(3.5, 1), "3,5")

    def test_easing_is_bounded_and_monotonic_start_end(self):
        self.assertEqual(ar.ease_out_cubic(0), 0.0)
        self.assertEqual(ar.ease_out_cubic(2), 1.0)
        self.assertAlmostEqual(ar.ease_out_back(1), 1.0)

    def test_concept_is_not_supported_here(self):
        self.assertFalse(ar.supports({"kind": "concept", "title": "x"}))

    @unittest.skipUnless(ar.find_font(), "requiere una fuente")
    def test_frames_animate_over_time(self):
        spec = choose_animation("la inflación subió 300%", "Inflación")
        early, late = ar.frame_at(spec, 0.4), ar.frame_at(spec, 3.0)
        self.assertEqual(early.size, (1280, 720))
        self.assertNotEqual(early.tobytes(), late.tobytes())

    @unittest.skipUnless(ar.find_font(), "requiere una fuente")
    def test_every_kind_renders_a_frame(self):
        for phrase in ("subió 300%", "Argentina 40% contra Chile 25%", "primero ahorra, segundo invierte"):
            spec = choose_animation(phrase, "Tema")
            self.assertIn(spec["kind"], ar.RENDERERS)
            ar.frame_at(spec, 2.5)


class _NoProvider:
    async def search_and_download(self, cue, target_dir):
        return None


@unittest.skipUnless(shutil.which("ffmpeg") and ar.find_font(), "requiere FFmpeg y una fuente")
class OrchestratorAnimationTest(unittest.TestCase):
    def run_cue(self, phrase, env=None):
        tmp = Path(tempfile.mkdtemp())
        try:
            with mock.patch.dict(os.environ, env or {}):
                orch = AssetOrchestrator(target_dir=tmp)
                orch.providers = [_NoProvider()]
                cue = BRollCue(cue_id="c1", start_sec=1, end_sec=5, concept="Inflación", search_query_en="x",
                               reasoning="x", confidence=0.9, spoken_phrase=phrase)
                plan = VideoEditingPlan(video_summary="x", total_original_duration_sec=10, timeline=[], b_rolls=[cue])
                asyncio.run(orch.process_all_brolls(plan))
                dur = None
                if cue.local_file_path:
                    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                                "default=nw=1:nk=1", cue.local_file_path],
                                               capture_output=True, text=True).stdout)
                return cue, dur, orch.decisions
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_data_phrase_gets_an_animation_with_the_cue_length(self):
        cue, dur, decisions = self.run_cue("la inflación subió 300%")
        self.assertEqual(cue.download_status, "COMPLETED")
        self.assertTrue(cue.local_file_path.endswith("_anim.mp4"))
        self.assertAlmostEqual(dur, 4.0, delta=0.3)
        self.assertEqual(decisions[-1]["outcome"], "generated")

    def test_phrase_without_data_falls_back_to_the_concept_card(self):
        cue, _, _ = self.run_cue("la inflación es un problema")
        self.assertTrue(cue.local_file_path.endswith("_card.mp4"))

    def test_with_animate_data_off_the_fallback_still_animates(self):
        cue, _, _ = self.run_cue("la inflación subió 300%", {"ANIMATE_DATA": "0"})
        self.assertTrue(cue.local_file_path.endswith("_anim.mp4"))  # sin proveedores, el respaldo también anima


if __name__ == "__main__":
    unittest.main()
