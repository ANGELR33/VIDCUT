"""Pruebas de auditoría editorial, ajuste de Shorts y confianza de fuentes. Sin red ni modelos."""

import asyncio
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.editorial_qa import QAConfig, audit_plan
from core.models import (ActionType, BRollCue, CaptionItem, HighlightClip, InfoCard, TimelineSegment,
                         VideoEditingPlan)
from core.short_snapper import snap_highlights
from core.source_trust import assess_sources, tier


def cue(cid, start, end=None, conf=0.8, score=None, video=True, concept=None):
    return BRollCue(cue_id=cid, start_sec=start, end_sec=end or start + 3, concept=concept or cid,
                    search_query_en="q", reasoning="x", confidence=conf, relevance_score=score,
                    download_status="COMPLETED",
                    local_file_path=f"/tmp/{cid}.mp4" if video else f"/tmp/{cid}.jpg")


def card(cid, start, verdict="supported", dur=7.0):
    return InfoCard(card_id=cid, start_sec=start, end_sec=start + 5, headline=f"Dato {cid}", verdict=verdict,
                    card_path="/tmp/card.png", display_duration_sec=dur)


def plan(cues=(), cards=(), caps=(), duration=120.0):
    return VideoEditingPlan(
        video_summary="v", total_original_duration_sec=duration,
        timeline=[TimelineSegment(start_sec=0, end_sec=duration, action=ActionType.KEEP)],
        b_rolls=list(cues), info_cards=list(cards), captions=list(caps))


class EditorialQATest(unittest.TestCase):
    def test_overlapping_broll_keeps_the_most_valuable(self):
        a, b = cue("a", 10.0, conf=0.9, score=9), cue("b", 11.0, conf=0.6, score=5)
        report = audit_plan(plan([a, b]), 120)
        self.assertTrue(a.enabled)
        self.assertFalse(b.enabled)
        self.assertEqual(report.dropped[0]["cue_id"], "b")
        self.assertIn("QA editorial", b.relevance_note)

    def test_min_gap_between_consecutive_broll(self):
        a, b = cue("a", 10.0), cue("b", 13.2, conf=0.5)  # a termina 13.0, hueco 0.2 s < 0.5
        audit_plan(plan([a, b]), 120)
        self.assertTrue(a.enabled)
        self.assertFalse(b.enabled)

    def test_separated_broll_are_all_kept(self):
        cues = [cue(f"c{i}", 5.0 + i * 8) for i in range(5)]
        report = audit_plan(plan(cues), 120)
        self.assertEqual(report.metrics["broll_kept"], 5)
        self.assertEqual(report.dropped, [])

    def test_density_cap(self):
        cues = [cue(f"c{i}", 1.0 + i * 4.0, conf=0.9 - i * 0.01) for i in range(12)]
        report = audit_plan(plan(cues), 120, QAConfig(max_broll_per_minute=4))
        self.assertLessEqual(report.metrics["broll_kept"], 4)

    def test_fullscreen_video_never_covers_a_verified_card(self):
        v = cue("v", 20.0, video=True)
        c = card("c1", 21.0)
        report = audit_plan(plan([v], [c]), 120)
        self.assertFalse(v.enabled)
        self.assertIn("tarjeta", report.dropped[0]["reason"])

    def test_photo_broll_may_coexist_with_a_card(self):
        p = cue("p", 20.0, video=False)
        audit_plan(plan([p], [card("c1", 21.0)]), 120)
        self.assertTrue(p.enabled)

    def test_pacing_and_hook_warnings(self):
        report = audit_plan(plan([cue("late", 60.0)]), 120)
        text = " ".join(report.warnings)
        self.assertIn("sin cambio visual", text)
        self.assertIn("gancho", text)
        self.assertLess(report.score, 100)

    def test_caption_in_first_seconds_counts_as_hook(self):
        cap = CaptionItem(start_sec=0.5, end_sec=3.0, text="hola")
        report = audit_plan(plan([], caps=[cap], duration=10), 10)
        self.assertFalse(any("gancho" in w for w in report.warnings))


class ShortSnapperTest(unittest.TestCase):
    CAPS = [CaptionItem(start_sec=float(s), end_sec=float(s) + 5.0, text=f"frase {s}") for s in range(0, 100, 5)]

    def clip(self, cid, start, end, score=50):
        return HighlightClip(clip_id=cid, start_sec=start, end_sec=end, title="t", hook="h", virality_score=score)

    def test_start_and_end_move_to_phrase_boundaries(self):
        c = self.clip("s1", 12.4, 37.3)
        changes = snap_highlights([c], self.CAPS, 100.0)
        self.assertEqual(c.start_sec, 10.0)
        self.assertEqual(c.end_sec, 40.0)
        self.assertEqual(changes[0]["action"], "snapped")

    def test_never_exceeds_max_duration(self):
        c = self.clip("s1", 10.0, 85.0)
        snap_highlights([c], self.CAPS, 100.0)
        self.assertLessEqual(c.end_sec - c.start_sec, 70.0)

    def test_too_short_clip_is_extended_to_minimum(self):
        c = self.clip("s1", 10.0, 18.0)
        snap_highlights([c], self.CAPS, 100.0)
        self.assertGreaterEqual(c.end_sec - c.start_sec, 15.0)

    def test_near_duplicates_keep_the_higher_score(self):
        a, b = self.clip("a", 10.0, 40.0, 80), self.clip("b", 11.0, 41.0, 60)
        highlights = [a, b]
        changes = snap_highlights(highlights, self.CAPS, 100.0)
        self.assertEqual([c.clip_id for c in highlights], ["a"])
        self.assertTrue(any(c["action"] == "dropped" and c["clip_id"] == "b" for c in changes))

    def test_without_captions_nothing_moves(self):
        c = self.clip("s1", 12.4, 37.3)
        snap_highlights([c], [], 100.0)
        self.assertEqual((c.start_sec, c.end_sec), (12.4, 37.3))

    def test_end_is_clamped_to_video_duration(self):
        c = self.clip("s1", 70.0, 98.0)
        snap_highlights([c], self.CAPS, 99.0)
        self.assertLessEqual(c.end_sec, 99.0)


class SourceTrustTest(unittest.TestCase):
    def test_tiers(self):
        self.assertEqual(tier("www.who.int"), "high")
        self.assertEqual(tier("minsalud.gov.co"), "high")
        self.assertEqual(tier("hacienda.gob.ar"), "high")
        self.assertEqual(tier("mit.edu"), "high")
        self.assertEqual(tier("es.wikipedia.org"), "medium")
        self.assertEqual(tier("twitter.com"), "excluded")
        self.assertEqual(tier("miblog.example.net"), "low")
        self.assertEqual(tier(""), "excluded")

    def test_data_card_needs_high_or_two_independent_sources(self):
        self.assertTrue(assess_sources("cifra", "supported", ["imf.org"])[0])
        self.assertTrue(assess_sources("cifra", "supported", ["es.wikipedia.org", "bloomberg.com"])[0])
        self.assertFalse(assess_sources("cifra", "supported", ["es.wikipedia.org"])[0])
        self.assertFalse(assess_sources("dato", "supported", ["es.wikipedia.org", "en.wikipedia.org"])[0])
        self.assertFalse(assess_sources("cifra", "supported", ["unblog.example.com"])[0])

    def test_entity_card_accepts_a_reference_source(self):
        self.assertTrue(assess_sources("persona", "supported", ["es.wikipedia.org"])[0])
        self.assertFalse(assess_sources("persona", "supported", ["unblog.example.com"])[0])

    def test_corrections_are_held_to_the_strict_rule(self):
        self.assertFalse(assess_sources("persona", "contradicted", ["es.wikipedia.org"])[0])
        self.assertTrue(assess_sources("persona", "contradicted", ["nasa.gov"])[0])

    def test_social_media_is_never_evidence(self):
        self.assertFalse(assess_sources("persona", "supported", ["facebook.com", "reddit.com"])[0])

    def test_insufficient_is_not_evaluated_and_switch_off_works(self):
        self.assertTrue(assess_sources("cifra", "insufficient", [])[0])
        with mock.patch.dict(os.environ, {"SOURCE_TRUST_STRICT": "0"}):
            self.assertTrue(assess_sources("cifra", "supported", ["twitter.com"])[0])


class FactCheckerIntegrationTest(unittest.TestCase):
    """verify_card debe degradar a 'insufficient' un dato apoyado solo en fuentes débiles."""

    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="trust-test-"))

    def tearDown(self):
        shutil.rmtree(self.temp, ignore_errors=True)

    def run_card(self, kind, urls):
        from core.fact_checker import FactChecker
        checker = FactChecker(llm=None, workdir=self.temp)
        evidence = [{"title": f"t{i}", "url": u, "text": "texto"} for i, u in enumerate(urls)]

        async def fake_evidence(card, progress=None):
            return evidence, None

        verdict = {"verdict": "supported", "summary": "Dato confirmado.", "stat": "", "correction": "",
                   "corrected_value": "", "source_indexes": list(range(1, len(urls) + 1)), "reason": "ok"}
        card = InfoCard(card_id="c1", start_sec=1, end_sec=6, kind=kind, headline="Tema", claim="Algo", image_query=None)
        with mock.patch.object(FactChecker, "_gather_evidence", side_effect=fake_evidence), \
             mock.patch.object(FactChecker, "_judge", return_value=verdict), \
             mock.patch.object(FactChecker, "fetch_real_image", return_value=None):
            return asyncio.run(checker.verify_card(card))

    def test_figure_backed_only_by_wikipedia_is_not_shown(self):
        card = self.run_card("cifra", ["https://es.wikipedia.org/wiki/X"])
        self.assertEqual(card.verdict, "insufficient")
        self.assertEqual(card.sources, [])
        self.assertIn("Fuentes insuficientes", card.note)

    def test_figure_backed_by_an_official_source_is_kept(self):
        card = self.run_card("cifra", ["https://www.imf.org/es/Data"])
        self.assertEqual(card.verdict, "supported")

    def test_entity_backed_by_wikipedia_is_kept(self):
        card = self.run_card("persona", ["https://es.wikipedia.org/wiki/X"])
        self.assertEqual(card.verdict, "supported")


if __name__ == "__main__":
    unittest.main()
