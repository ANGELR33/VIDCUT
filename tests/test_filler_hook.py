"""Pruebas de corte de muletillas y puntuación de ganchos. Sin red ni modelos."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.filler_cutter import (apply_filler_cuts, clean_caption_text, clean_captions, enabled, find_fillers)
from core.hook_scorer import rank_highlights, score_hook, trim_leading_filler
from core.models import ActionType, CaptionItem, HighlightClip, TimelineSegment


def w(word, start, end):
    return {"word": word, "start": start, "end": end}


def keep(a, b):
    return TimelineSegment(start_sec=a, end_sec=b, action=ActionType.KEEP)


class FindFillersTest(unittest.TestCase):
    def test_detects_vocal_hesitations_with_punctuation(self):
        words = [w("Hola", 0.0, 0.4), w("Eh...", 0.5, 0.9), w("vamos", 1.0, 1.4), w("mmm,", 1.5, 1.8)]
        kinds = [(f["text"], f["kind"]) for f in find_fillers(words)]
        self.assertEqual(kinds, [("Eh...", "vacilacion"), ("mmm,", "vacilacion")])

    def test_ignores_very_short_hesitations(self):
        self.assertEqual(find_fillers([w("eh", 0.0, 0.1)]), [])

    def test_detects_function_word_stutter_and_cuts_first_occurrence(self):
        words = [w("el", 1.0, 1.2), w("el", 1.3, 1.5), w("gato", 1.6, 2.0)]
        found = find_fillers(words)
        self.assertEqual(len(found), 1)
        self.assertEqual((found[0]["start"], found[0]["end"]), (1.0, 1.3))
        self.assertEqual(found[0]["kind"], "tartamudeo")

    def test_does_not_touch_emphatic_or_content_repeats(self):
        self.assertEqual(find_fillers([w("no", 0, 0.3), w("no", 0.4, 0.7)]), [])
        self.assertEqual(find_fillers([w("muy", 0, 0.3), w("muy", 0.4, 0.7)]), [])
        self.assertEqual(find_fillers([w("el", 0, 0.2), w("el", 1.5, 1.7)]), [])  # gap largo

    def test_does_not_treat_meaningful_words_as_fillers(self):
        for word in ("este", "pues", "sea", "entonces"):
            self.assertEqual(find_fillers([w(word, 0.0, 0.6)]), [])


class ApplyCutsTest(unittest.TestCase):
    def test_splits_keep_into_keep_cut_keep_and_stays_contiguous(self):
        fillers = [{"start": 4.0, "end": 4.6, "kind": "vacilacion", "text": "eh"}]
        out, report = apply_filler_cuts([keep(0.0, 10.0)], fillers, 10.0)
        self.assertEqual([s.action for s in out], [ActionType.KEEP, ActionType.CUT_FILLER, ActionType.KEEP])
        self.assertAlmostEqual(out[1].start_sec, 4.05)
        self.assertAlmostEqual(out[1].end_sec, 4.55)
        for a, b in zip(out, out[1:]):
            self.assertAlmostEqual(a.end_sec, b.start_sec)
        self.assertEqual((out[0].start_sec, out[-1].end_sec), (0.0, 10.0))
        self.assertEqual(report["applied"], 1)

    def test_skips_cut_that_would_leave_a_tiny_fragment(self):
        fillers = [{"start": 0.2, "end": 0.8, "kind": "vacilacion", "text": "eh"}]  # deja 0.25 s? corte 0.25-0.75 -> izq 0.25
        out, report = apply_filler_cuts([keep(0.0, 10.0)], fillers, 10.0, min_fragment=0.4)
        self.assertEqual(report["applied"], 0)
        self.assertEqual(report["skipped"]["fragmento_muy_corto"], 1)
        self.assertEqual(len(out), 1)

    def test_does_not_cut_inside_an_existing_silence_cut(self):
        segments = [keep(0.0, 5.0), TimelineSegment(start_sec=5.0, end_sec=8.0, action=ActionType.CUT_SILENCE),
                    keep(8.0, 20.0)]
        fillers = [{"start": 6.0, "end": 6.6, "kind": "vacilacion", "text": "eh"}]
        out, report = apply_filler_cuts(segments, fillers, 20.0)
        self.assertEqual(report["applied"], 0)
        self.assertEqual(report["skipped"]["fuera_de_tramo"], 1)
        self.assertEqual(len(out), 3)

    def test_total_cut_is_capped_keeping_the_longest(self):
        fillers = [{"start": 10.0 + i * 5, "end": 10.0 + i * 5 + (1.0 if i == 0 else 0.3),
                    "kind": "vacilacion", "text": "eh"} for i in range(6)]
        out, report = apply_filler_cuts([keep(0.0, 100.0)], fillers, 100.0, max_ratio=0.01)
        self.assertLessEqual(report["seconds_cut"], 1.0)
        self.assertGreaterEqual(report["skipped"]["limite_6_por_ciento"], 1)

    def test_original_segments_are_not_mutated(self):
        original = [keep(0.0, 10.0)]
        apply_filler_cuts(original, [{"start": 4.0, "end": 4.6, "kind": "vacilacion", "text": "eh"}], 10.0)
        self.assertEqual(len(original), 1)

    def test_switch_can_disable_the_feature(self):
        self.assertTrue(enabled())
        with mock.patch.dict(os.environ, {"FILLER_CUT": "0"}):
            self.assertFalse(enabled())


class CaptionCleaningTest(unittest.TestCase):
    def test_removes_hesitations_and_collapses_stutters(self):
        self.assertEqual(clean_caption_text("Eh... el el gato mmm duerme"), "el gato duerme")

    def test_keeps_emphatic_repeats(self):
        self.assertEqual(clean_caption_text("no no no puede ser"), "no no no puede ser")

    def test_clean_captions_drops_empty_ones_and_prunes_highlights(self):
        caps = [CaptionItem(start_sec=0, end_sec=1, text="eh mmm"),
                CaptionItem(start_sec=1, end_sec=3, text="eh hola mundo", highlight_words=["eh", "mundo"])]
        changed = clean_captions(caps)
        self.assertEqual(changed, 2)
        self.assertEqual(len(caps), 1)
        self.assertEqual(caps[0].text, "hola mundo")
        self.assertEqual(caps[0].highlight_words, ["mundo"])


class HookScoreTest(unittest.TestCase):
    def test_strong_hooks_score_higher_than_empty_openers(self):
        strong = score_hook("¿Sabías que el 90% de los videos fallan en 3 segundos?")["score"]
        weak = score_hook("Hola, bueno, en este video vamos a hablar de varias cosas")["score"]
        self.assertGreater(strong, weak + 30)

    def test_signals_are_reported(self):
        result = score_hook("Nadie te cuenta este secreto: 3 errores que cometes")
        self.assertIn("curiosidad/contraste", result["signals"])
        self.assertIn("cifra", result["signals"])

    def test_empty_text_is_zero_and_scores_are_bounded(self):
        self.assertEqual(score_hook("")["score"], 0)
        for text in ("a", "¿Por qué nadie te dice el secreto de 5 errores? Imagina que tú nunca lo supieras"):
            self.assertTrue(0 <= score_hook(text)["score"] <= 100)


class TrimAndRankTest(unittest.TestCase):
    def caps(self):
        return [CaptionItem(start_sec=10.0, end_sec=11.5, text="Hola, bueno"),
                CaptionItem(start_sec=11.5, end_sec=14.0, text="¿Sabías que esto pasa en 3 días?"),
                CaptionItem(start_sec=14.0, end_sec=40.0, text="porque la mayoría no lo hace")]

    def clip(self, cid="s1", start=10.0, end=40.0, score=50):
        return HighlightClip(clip_id=cid, start_sec=start, end_sec=end, title="t", hook="h", virality_score=score)

    def test_skips_empty_opening_phrases(self):
        c = self.clip()
        shift = trim_leading_filler(c, self.caps())
        self.assertAlmostEqual(shift, 1.5)
        self.assertEqual(c.start_sec, 11.5)

    def test_does_not_trim_a_good_opening_or_below_min_length(self):
        c = self.clip(start=11.5)
        self.assertEqual(trim_leading_filler(c, self.caps()), 0.0)
        short = self.clip(start=10.0, end=20.0)
        self.assertEqual(trim_leading_filler(short, self.caps()), 0.0)

    def test_rank_puts_better_hook_first_even_with_lower_virality(self):
        good = self.clip("good", 11.5, 40.0, score=60)
        bad = self.clip("bad", 10.0, 40.0, score=70)
        highlights = [bad, good]
        details = rank_highlights(highlights, self.caps())
        self.assertEqual(highlights[0].clip_id, "good")
        self.assertEqual(details[0]["clip_id"], "good")


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "requiere FFmpeg")
class FillerRenderTest(unittest.TestCase):
    """Un tramo CUT_FILLER debe desaparecer del video final, no solo del plan."""

    def test_render_removes_the_filler_segment(self):
        from core.models import VideoEditingPlan
        from core.render_engine import VideoRenderEngine
        from core.timeline import TimelineMapper

        tmp = Path(tempfile.mkdtemp(prefix="filler-render-"))
        try:
            video = tmp / "in.mp4"
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                            "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=24",
                            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
                            "-t", "12", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(video)],
                           check=True)
            segments, report = apply_filler_cuts(
                [keep(0.0, 12.0)], find_fillers([w("Hola", 0.0, 0.5), w("eh...", 3.0, 3.8), w("gato", 4.0, 4.5)]), 12.0)
            self.assertEqual(report["applied"], 1)
            plan = VideoEditingPlan(video_summary="x", total_original_duration_sec=12.0, timeline=segments)
            mapper = TimelineMapper.from_plan_segments(plan.timeline, 12.0)
            out = tmp / "out.mp4"
            VideoRenderEngine(fps=24).render(video, plan, mapper, tmp, out, None, lambda m, p: None)
            duration = float(subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(out)],
                capture_output=True, text=True).stdout)
            self.assertAlmostEqual(duration, 12.0 - report["seconds_cut"], delta=0.4)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
