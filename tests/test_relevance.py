import os
"""Pruebas del filtro de relevancia del B-Roll. No usan red ni modelos reales."""

import asyncio
import json
import shutil
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from core.asset_providers import AssetProvider, content_tokens, has_word, required_token_matches
from core.models import BRollCue, TimelineSegment, ActionType, VideoEditingPlan
from core.orchestrator import AssetOrchestrator, enrich_query
from core.relevance_gate import is_relevant, parse_score


def make_cue(cue_id="broll_1", query="eiffel tower", confidence=0.8, phrase="Fuimos a la Torre Eiffel"):
    return BRollCue(
        cue_id=cue_id, start_sec=1.0, end_sec=4.0, concept="Torre Eiffel",
        search_query_en=query, reasoning="lugar mencionado",
        spoken_phrase=phrase, confidence=confidence,
    )


def make_plan(cues, topic="Paris travel"):
    return VideoEditingPlan(
        video_summary="viaje", topic_en=topic, total_original_duration_sec=10.0,
        timeline=[TimelineSegment(start_sec=0.0, end_sec=10.0, action=ActionType.KEEP)],
        b_rolls=cues,
    )


class FileProvider(AssetProvider):
    """Proveedor falso: escribe un archivo y lo devuelve."""

    def __init__(self, tag, calls):
        self.tag, self.calls = tag, calls

    async def search_and_download(self, cue, target_dir):
        self.calls.append(self.tag)
        path = target_dir / f"{cue.cue_id}_{self.tag}.jpg"
        path.write_bytes(b"fake")
        return path


class EmptyProvider(AssetProvider):
    async def search_and_download(self, cue, target_dir):
        return None


class FakeJudge:
    """Juez falso: puntaje según el nombre del archivo."""

    def __init__(self, scores, threshold=6.0):
        self.scores, self.threshold = scores, threshold

    async def score(self, media_path, concept, phrase="", topic=""):
        for tag, value in self.scores.items():
            if tag in media_path.name:
                return value, f"puntaje {value}"
        return None, "sin evaluar"


class SubstringBugTest(unittest.TestCase):
    def test_short_words_do_not_match_inside_other_words(self):
        self.assertFalse(has_word("coffee shop morning", "fe"))
        self.assertFalse(has_word("social media marketing", "ia"))
        self.assertFalse(has_word("rain forest", "ai"))
        self.assertFalse(has_word("metadata", "meta"))
        self.assertTrue(has_word("meta data", "meta"))
        self.assertTrue(has_word("ai chips nvidia", "ai"))
        self.assertTrue(has_word("la fe y la oración", "fe"))
        self.assertTrue(has_word("rueda de prensa hoy", "rueda de prensa"))

    def test_required_matches_scale_with_query_length(self):
        self.assertEqual(required_token_matches(1), 1)
        self.assertEqual(required_token_matches(2), 1)
        self.assertEqual(required_token_matches(3), 2)
        self.assertEqual(required_token_matches(6), 2)

    def test_content_tokens_dedupes_and_filters(self):
        self.assertEqual(content_tokens("Eiffel tower eiffel 4k", {"4k"}), ["eiffel", "tower"])


class ScoreParsingTest(unittest.TestCase):
    def test_parses_json_and_clamps(self):
        self.assertEqual(parse_score('{"score": 8, "reason": "ok"}'), (8.0, "ok"))
        self.assertEqual(parse_score('{"score": 14}')[0], 10.0)
        self.assertEqual(parse_score('texto previo {"score": 3.5, "reason": "x"} fin')[0], 3.5)

    def test_unparseable_returns_none(self):
        self.assertEqual(parse_score(""), (None, ""))
        self.assertEqual(parse_score("no sé")[0], None)
        self.assertEqual(parse_score('{"score": "alto"}')[0], None)

    def test_threshold_and_fail_open(self):
        self.assertTrue(is_relevant(None))
        self.assertTrue(is_relevant(6.0, 6.0))
        self.assertFalse(is_relevant(5.9, 6.0))


class EnrichQueryTest(unittest.TestCase):
    def test_adds_topic_to_short_queries(self):
        self.assertEqual(enrich_query("mercury", "solar system"), "mercury solar system")

    def test_keeps_query_when_topic_already_present_or_long(self):
        self.assertEqual(enrich_query("paris skyline", "Paris travel"), "paris skyline")
        self.assertEqual(enrich_query("a b c d e", "topic"), "a b c d e")
        self.assertEqual(enrich_query("eiffel", ""), "eiffel")


class OrchestratorGateTest(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="relevance-test-"))
        patcher = mock.patch.dict(os.environ, {"MOTION_FALLBACK": "0"})  # estas pruebas miden la regla de omitir
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        shutil.rmtree(self.temp, ignore_errors=True)

    def build(self, providers, scores):
        orch = AssetOrchestrator(target_dir=self.temp, relevance_judge=FakeJudge(scores))
        orch.providers = providers
        return orch

    def test_rejects_irrelevant_and_falls_through_to_next_provider(self):
        calls = []
        orch = self.build([FileProvider("bad", calls), FileProvider("good", calls)], {"bad": 2.0, "good": 8.0})
        plan = asyncio.run(orch.process_all_brolls(make_plan([make_cue()])))
        cue = plan.b_rolls[0]
        self.assertEqual(calls, ["bad", "good"])
        self.assertEqual(cue.download_status, "COMPLETED")
        self.assertTrue(cue.local_file_path.endswith("_good.jpg"))
        self.assertFalse((self.temp / "broll_1_bad.jpg").exists())
        self.assertEqual(cue.relevance_score, 8.0)

    def test_skips_cue_when_nothing_is_relevant(self):
        orch = self.build([FileProvider("bad", []), EmptyProvider()], {"bad": 1.0})
        plan = asyncio.run(orch.process_all_brolls(make_plan([make_cue()])))
        self.assertEqual(plan.b_rolls[0].download_status, "FAILED")
        self.assertIsNone(plan.b_rolls[0].local_file_path)

    def test_low_confidence_cue_is_not_searched(self):
        calls = []
        orch = self.build([FileProvider("good", calls)], {"good": 9.0})
        plan = asyncio.run(orch.process_all_brolls(make_plan([make_cue(confidence=0.3)])))
        self.assertEqual(calls, [])
        self.assertFalse(plan.b_rolls[0].enabled)
        self.assertEqual(plan.b_rolls[0].download_status, "FAILED")

    def test_unscored_asset_is_accepted_fail_open(self):
        orch = self.build([FileProvider("any", [])], {})
        plan = asyncio.run(orch.process_all_brolls(make_plan([make_cue()])))
        self.assertEqual(plan.b_rolls[0].download_status, "COMPLETED")

    def test_decisions_file_records_each_outcome(self):
        orch = self.build([FileProvider("bad", []), FileProvider("good", [])], {"bad": 2.0, "good": 8.0})
        asyncio.run(orch.process_all_brolls(make_plan([make_cue()])))
        decisions = json.loads((self.temp / "broll_decisions.json").read_text(encoding="utf-8"))
        self.assertEqual([d["outcome"] for d in decisions], ["rejected", "accepted"])
        self.assertEqual(decisions[0]["spoken_phrase"], "Fuimos a la Torre Eiffel")

    def test_topic_is_added_to_the_query(self):
        orch = self.build([FileProvider("good", [])], {"good": 9.0})
        plan = asyncio.run(orch.process_all_brolls(make_plan([make_cue(query="mercury")], topic="solar system")))
        self.assertEqual(plan.b_rolls[0].search_query_en, "mercury solar system")


if __name__ == "__main__":
    unittest.main()
