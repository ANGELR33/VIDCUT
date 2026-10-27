"""Pruebas del control de derechos del material visual. Sin red ni modelos."""

import asyncio
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.models import ActionType, BRollCue, TimelineSegment, VideoEditingPlan
from core.orchestrator import AssetOrchestrator
from core.rights import classify_rights, policy, policy_allows, render_markdown, summarize
from core.asset_providers import AssetProvider


def prov(url="", license_="", name="", artist="", note=""):
    return {"source_url": url, "license": license_, "source_name": name, "artist": artist, "context_note": note}


class ClassifyRightsTest(unittest.TestCase):
    def test_own_library_is_cleared(self):
        out = classify_rights("LocalOriginalAssetProvider", prov(name="Biblioteca original del canal"))
        self.assertEqual(out["status"], "cleared")

    def test_wikimedia_requires_attribution_with_a_credit_line(self):
        out = classify_rights("OpenStockAssetProvider", prov(
            "https://commons.wikimedia.org/wiki/File:X.jpg", "CC BY-SA 4.0", "Wikimedia Commons", "Ana Pérez", "Torre"))
        self.assertEqual(out["status"], "attribution_required")
        self.assertIn("Ana Pérez", out["attribution"])
        self.assertIn("CC BY-SA 4.0", out["attribution"])

    def test_public_domain_wikimedia_is_cleared(self):
        out = classify_rights("OpenStockAssetProvider", prov("https://commons.wikimedia.org/wiki/File:X.jpg", "Public domain"))
        self.assertEqual(out["status"], "cleared")

    def test_editorial_press_needs_review(self):
        out = classify_rights("WebPhotoAssetProvider", prov("https://www.reuters.com/pictures/x"))
        self.assertEqual(out["status"], "review")

    def test_unknown_domain_from_web_search_is_risky(self):
        out = classify_rights("WebPhotoAssetProvider", prov("https://random-blog.example.net/foto"))
        self.assertEqual(out["status"], "risky")

    def test_web_photo_never_looks_better_than_review_even_on_a_free_domain(self):
        out = classify_rights("WebPhotoAssetProvider", prov("https://commons.wikimedia.org/wiki/File:X.jpg", "Public domain"))
        self.assertIn(out["status"], ("review", "attribution_required"))
        self.assertNotEqual(out["status"], "cleared")

    def test_youtube_clips_are_always_risky(self):
        self.assertEqual(classify_rights("YouTubeReactionAssetProvider", {})["status"], "risky")
        self.assertEqual(classify_rights("YouTubeReactionAssetProvider", prov("https://www.nasa.gov/x"))["status"], "risky")

    def test_missing_provenance_is_never_cleared(self):
        for provider in ("OpenStockAssetProvider", "WebPhotoAssetProvider", "OriginalSourceAssetProvider", "Otro"):
            self.assertNotEqual(classify_rights(provider, None)["status"], "cleared", provider)

    def test_official_source_with_unconfirmed_permission_needs_review(self):
        out = classify_rights("OriginalSourceAssetProvider", prov("https://nvidia.com/news/x.jpg"))
        self.assertEqual(out["status"], "review")


class PolicyTest(unittest.TestCase):
    def test_default_is_permissive_and_invalid_values_fall_back(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LICENSE_POLICY", None)
            self.assertEqual(policy(), "permissive")
        with mock.patch.dict(os.environ, {"LICENSE_POLICY": "loquesea"}):
            self.assertEqual(policy(), "permissive")

    def test_policy_matrix(self):
        self.assertTrue(all(policy_allows(s, "permissive") for s in ("cleared", "attribution_required", "review", "risky")))
        self.assertTrue(policy_allows("review", "balanced"))
        self.assertFalse(policy_allows("risky", "balanced"))
        self.assertTrue(policy_allows("attribution_required", "strict"))
        self.assertFalse(policy_allows("review", "strict"))
        self.assertFalse(policy_allows("risky", "strict"))

    def test_summary_and_markdown_list_pending_items_and_credits(self):
        items = [
            {"status": "review", "concept": "A", "provider": "WebPhotoAssetProvider", "source_url": "u", "note": "n", "attribution": ""},
            {"status": "attribution_required", "concept": "B", "provider": "OpenStockAssetProvider", "source_url": "v", "note": "n", "attribution": "Foto — Ana (v)"},
        ]
        self.assertEqual(summarize(items)["review"], 1)
        md = render_markdown(items, "balanced")
        self.assertIn("Revisar antes de publicar", md)
        self.assertIn("Foto — Ana (v)", md)
        self.assertIn("no asesoría legal", md)


class WritingProvider(AssetProvider):
    """Proveedor falso con nombre configurable: escribe archivo y procedencia."""

    def __init__(self, url="", license_=""):
        self.url, self.license = url, license_

    async def search_and_download(self, cue, target_dir):
        path = target_dir / f"{cue.cue_id}_{self.__class__.__name__}.jpg"
        path.write_bytes(b"x")
        (target_dir / f"{cue.cue_id}_provenance.json").write_text(
            json.dumps({"source_url": self.url, "license": self.license, "source_name": "x"}), encoding="utf-8")
        return path


class YouTubeReactionAssetProvider(WritingProvider):
    pass


class OpenStockAssetProvider(WritingProvider):
    pass


class PassJudge:
    threshold = 6.0

    async def score(self, *a, **k):
        return 9.0, "ok"


def make_plan():
    cue = BRollCue(cue_id="b1", start_sec=1, end_sec=4, concept="Torre", search_query_en="tower", reasoning="x",
                   confidence=0.9)
    return VideoEditingPlan(video_summary="v", total_original_duration_sec=10.0,
                            timeline=[TimelineSegment(start_sec=0, end_sec=10, action=ActionType.KEEP)], b_rolls=[cue])


class OrchestratorRightsTest(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="rights-test-"))
        patcher = mock.patch.dict(os.environ, {"MOTION_FALLBACK": "0"})  # estas pruebas miden la regla de omitir
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        shutil.rmtree(self.temp, ignore_errors=True)

    def run_with(self, mode, providers):
        with mock.patch.dict(os.environ, {"LICENSE_POLICY": mode}):
            orch = AssetOrchestrator(target_dir=self.temp, relevance_judge=PassJudge())
        orch.providers = providers
        plan = asyncio.run(orch.process_all_brolls(make_plan()))
        return plan.b_rolls[0]

    def test_permissive_keeps_a_risky_clip_but_flags_it(self):
        cue = self.run_with("permissive", [YouTubeReactionAssetProvider()])
        self.assertEqual(cue.download_status, "COMPLETED")
        self.assertEqual(cue.rights_status, "risky")
        report = json.loads((self.temp / "rights_report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["summary"]["risky"], 1)
        self.assertIn("Revisar antes de publicar", (self.temp / "rights_report.md").read_text(encoding="utf-8"))

    def test_balanced_rejects_risky_and_falls_through_to_a_licensed_source(self):
        cue = self.run_with("balanced", [
            YouTubeReactionAssetProvider(),
            OpenStockAssetProvider("https://commons.wikimedia.org/wiki/File:X.jpg", "CC BY-SA 4.0"),
        ])
        self.assertEqual(cue.download_status, "COMPLETED")
        self.assertEqual(cue.rights_status, "attribution_required")
        self.assertTrue(cue.local_file_path.endswith("OpenStockAssetProvider.jpg"))
        self.assertFalse((self.temp / "b1_YouTubeReactionAssetProvider.jpg").exists())
        self.assertIn("CC BY-SA 4.0", (self.temp / "credits.txt").read_text(encoding="utf-8"))

    def test_strict_with_only_risky_sources_leaves_the_cue_empty(self):
        cue = self.run_with("strict", [YouTubeReactionAssetProvider()])
        self.assertEqual(cue.download_status, "FAILED")
        decisions = json.loads((self.temp / "broll_decisions.json").read_text(encoding="utf-8"))
        self.assertEqual(decisions[0]["outcome"], "rejected_rights")


if __name__ == "__main__":
    unittest.main()
