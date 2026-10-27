"""Pruebas del afinado de palabras y de los embeddings visuales. Usan modelos simulados: sin red ni descargas."""

import asyncio
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core import visual_embeddings as ve
from core.asset_providers import LocalOriginalAssetProvider
from core.models import ActionType, BRollCue, TimelineSegment, VideoEditingPlan
from core.orchestrator import AssetOrchestrator
from core.asset_providers import AssetProvider
from core.word_refiner import merge_refined, refine_words, sanity_check


def w(word, start, end):
    return {"word": word, "start": start, "end": end}


ORIGINAL = [w("Hola", 0.0, 0.4), w("eh", 1.0, 1.4), w("mundo", 2.0, 2.5), w("feliz", 3.0, 3.5)]


class MergeAndSanityTest(unittest.TestCase):
    def test_adopts_refined_times_for_matching_words(self):
        refined = [w("hola", 0.05, 0.45), w("eh", 1.1, 1.3), w("mundo", 2.1, 2.6), w("feliz", 3.1, 3.6)]
        merged, changed = merge_refined(ORIGINAL, refined)
        self.assertEqual(changed, 4)
        self.assertEqual((merged[1]["start"], merged[1]["end"]), (1.1, 1.3))
        self.assertEqual(merged[0]["word"], "Hola")  # conserva el texto original

    def test_unmatched_words_keep_original_timing(self):
        refined = [w("hola", 0.1, 0.5), w("mundo", 2.1, 2.6), w("feliz", 3.1, 3.6)]  # falta "eh"
        merged, changed = merge_refined(ORIGINAL, refined)
        self.assertEqual(changed, 3)
        self.assertEqual((merged[1]["start"], merged[1]["end"]), (1.0, 1.4))

    def test_words_without_times_are_ignored(self):
        refined = [w("hola", None, None), w("eh", 1.1, 1.3), w("mundo", 2.1, 2.6), w("feliz", 3.1, 3.6)]
        merged, changed = merge_refined(ORIGINAL, refined)
        self.assertEqual(changed, 3)
        self.assertEqual(merged[0]["start"], 0.0)

    def test_sanity_rejects_unreliable_alignments(self):
        good, _ = merge_refined(ORIGINAL, [w("hola", 0.05, 0.45), w("eh", 1.1, 1.3), w("mundo", 2.1, 2.6), w("feliz", 3.1, 3.6)])
        self.assertTrue(sanity_check(ORIGINAL, good, 4)[0])
        far = [dict(x, start=x["start"] + 5, end=x["end"] + 5) for x in ORIGINAL]
        self.assertFalse(sanity_check(ORIGINAL, far, 4)[0])
        self.assertFalse(sanity_check(ORIGINAL, ORIGINAL, 1)[0])  # coincidieron muy pocas
        shuffled = [w("Hola", 0.0, 0.4), w("eh", 3.0, 3.4), w("mundo", 2.0, 2.5), w("feliz", 3.0, 3.5)]
        self.assertFalse(sanity_check(ORIGINAL, shuffled, 4)[0])


class RefineWordsTest(unittest.TestCase):
    def test_uses_refined_words_when_sane(self):
        aligner = lambda audio, words, lang: [w("hola", 0.05, 0.45), w("eh", 1.1, 1.3), w("mundo", 2.1, 2.6), w("feliz", 3.1, 3.6)]
        words, report = refine_words("a.wav", ORIGINAL, aligner=aligner)
        self.assertTrue(report["adopted"])
        self.assertEqual(words[1]["start"], 1.1)

    def test_falls_back_to_original_when_alignment_is_unreliable(self):
        aligner = lambda audio, words, lang: [dict(x, start=x["start"] + 9, end=x["end"] + 9) for x in words]
        words, report = refine_words("a.wav", ORIGINAL, aligner=aligner)
        self.assertFalse(report["adopted"])
        self.assertEqual(words, ORIGINAL)

    def test_falls_back_when_the_library_or_model_fails(self):
        def boom(*a):
            raise ImportError("No module named 'whisperx'")
        words, report = refine_words("a.wav", ORIGINAL, aligner=boom)
        self.assertEqual(words, ORIGINAL)
        self.assertIn("ImportError", report["reason"])

    def test_original_list_is_never_mutated(self):
        snapshot = json.dumps(ORIGINAL)
        refine_words("a.wav", ORIGINAL, aligner=lambda *a: [w("hola", 0.05, 0.45), w("eh", 1.1, 1.3), w("mundo", 2.1, 2.6), w("feliz", 3.1, 3.6)])
        self.assertEqual(json.dumps(ORIGINAL), snapshot)


class FakeEncoder:
    """Vector por palabra clave en el nombre del archivo o en el texto: determinista y sin modelos."""

    AXES = ("eiffel", "gato", "mar")
    calls = 0

    def _vec(self, text):
        low = text.lower()
        return [1.0 if k in low else 0.0 for k in self.AXES] + [0.01]

    def encode_text(self, text):
        return self._vec(text)

    def encode_image(self, path):
        FakeEncoder.calls += 1
        return self._vec(Path(path).name)


class EmbeddingsMathTest(unittest.TestCase):
    def test_cosine_and_duplicates(self):
        self.assertAlmostEqual(ve.cosine([1, 0], [1, 0]), 1.0)
        self.assertAlmostEqual(ve.cosine([1, 0], [0, 1]), 0.0)
        self.assertEqual(ve.cosine([0, 0], [1, 1]), 0.0)
        dup, sim = ve.is_duplicate([1, 0.01], [[1, 0.0], [0, 1]], threshold=0.93)
        self.assertTrue(dup)
        self.assertGreater(sim, 0.99)
        self.assertFalse(ve.is_duplicate([1, 0], [[0, 1]], threshold=0.93)[0])
        self.assertFalse(ve.is_duplicate([1, 0], [], threshold=0.93)[0])

    def test_everything_is_off_by_default(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            for name in ("SEMANTIC_LIBRARY", "VISUAL_DEDUPE"):
                os.environ.pop(name, None)
            self.assertFalse(ve.semantic_library_enabled())
            self.assertFalse(ve.dedupe_enabled())
            self.assertIsNone(ve.get_encoder())


class LibraryIndexTest(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="library-test-"))
        for name in ("torre_eiffel_noche.jpg", "mi_gato_duerme.jpg", "playa_mar.png", "notas.txt"):
            (self.temp / name).write_bytes(b"x")
        FakeEncoder.calls = 0

    def tearDown(self):
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_search_finds_by_meaning_and_ignores_non_media(self):
        index = ve.LibraryIndex(self.temp, FakeEncoder())
        index.build()
        self.assertEqual(len(index.vectors), 3)
        hits = index.search("eiffel tower at night", top_k=1, min_score=0.5)
        self.assertEqual(hits[0][0].name, "torre_eiffel_noche.jpg")

    def test_min_score_filters_weak_matches(self):
        index = ve.LibraryIndex(self.temp, FakeEncoder())
        index.build()
        self.assertEqual(index.search("rascacielos de tokio", min_score=0.5), [])

    def test_cache_avoids_recomputing_and_detects_changes(self):
        first = ve.LibraryIndex(self.temp, FakeEncoder())
        first.build()
        self.assertEqual(FakeEncoder.calls, 3)
        second = ve.LibraryIndex(self.temp, FakeEncoder())
        second.build()
        self.assertEqual(FakeEncoder.calls, 3)
        self.assertEqual(second.stats["cached"], 3)
        (self.temp / "mi_gato_duerme.jpg").write_bytes(b"xxxxx")  # cambió el tamaño
        third = ve.LibraryIndex(self.temp, FakeEncoder())
        third.build()
        self.assertEqual(FakeEncoder.calls, 4)


class SemanticProviderTest(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="semantic-provider-"))
        self.library = self.temp / "lib"
        self.library.mkdir()
        (self.library / "IMG_0001_eiffel.jpg").write_bytes(b"x")
        (self.library / "IMG_0002_gato.jpg").write_bytes(b"x")
        self.out = self.temp / "out"
        self.out.mkdir()

    def tearDown(self):
        shutil.rmtree(self.temp, ignore_errors=True)

    def cue(self, query):
        return BRollCue(cue_id="b1", start_sec=1, end_sec=4, concept=query, search_query_en=query, reasoning="x")

    def provider(self, encoder):
        p = LocalOriginalAssetProvider(encoder=encoder)
        p.root = self.library
        return p

    def test_finds_a_file_whose_name_shares_no_words_with_the_query(self):
        out = asyncio.run(self.provider(FakeEncoder()).search_and_download(self.cue("eiffel tower paris"), self.out))
        self.assertIsNotNone(out)
        self.assertIn("eiffel", json.loads((self.out / "b1_provenance.json").read_text(encoding="utf-8"))["context_note"])

    def test_without_encoder_keeps_the_old_word_matching_behaviour(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SEMANTIC_LIBRARY", None)
            found = asyncio.run(self.provider(None).search_and_download(self.cue("eiffel tower"), self.out))
        self.assertIsNotNone(found)  # coincide por la palabra "eiffel" en el nombre

    def test_a_broken_encoder_falls_back_instead_of_failing(self):
        class Broken(FakeEncoder):
            def encode_image(self, path):
                raise RuntimeError("sin memoria")
        found = asyncio.run(self.provider(Broken()).search_and_download(self.cue("eiffel tower"), self.out))
        self.assertIsNotNone(found)


class WritingProvider(AssetProvider):
    def __init__(self, filename):
        self.filename = filename

    async def search_and_download(self, cue, target_dir):
        path = target_dir / self.filename
        path.write_bytes(b"x")
        return path


class PassJudge:
    threshold = 6.0

    async def score(self, *a, **k):
        return 9.0, "ok"


class DedupeInOrchestratorTest(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="dedupe-test-"))

    def tearDown(self):
        shutil.rmtree(self.temp, ignore_errors=True)

    def plan(self):
        cues = [BRollCue(cue_id=f"b{i}", start_sec=1 + i * 8, end_sec=4 + i * 8, concept="x", search_query_en="x",
                         reasoning="x", confidence=0.9) for i in range(2)]
        return VideoEditingPlan(video_summary="v", total_original_duration_sec=30.0,
                                timeline=[TimelineSegment(start_sec=0, end_sec=30, action=ActionType.KEEP)], b_rolls=cues)

    def test_second_near_identical_image_is_rejected_and_next_provider_used(self):
        orch = AssetOrchestrator(target_dir=self.temp, relevance_judge=PassJudge(), encoder=FakeEncoder())
        orch.providers = [WritingProvider("eiffel_a.jpg"), WritingProvider("eiffel_b.jpg")]
        # b0 usa eiffel_a; b1 recibiría eiffel_b (idéntica en el espacio de la prueba) => duplicada.
        plan = asyncio.run(orch.process_all_brolls(self.plan()))
        outcomes = [d["outcome"] for d in json.loads((self.temp / "broll_decisions.json").read_text(encoding="utf-8"))]
        self.assertIn("accepted", outcomes)
        self.assertIn("rejected_duplicate", outcomes)

    def test_distinct_images_are_both_accepted(self):
        class Alternating(AssetProvider):
            names = iter(["eiffel_1.jpg", "gato_1.jpg"])

            async def search_and_download(self, cue, target_dir):
                path = target_dir / next(self.names)
                path.write_bytes(b"x")
                return path

        orch = AssetOrchestrator(target_dir=self.temp, relevance_judge=PassJudge(), encoder=FakeEncoder())
        orch.providers = [Alternating()]
        plan = asyncio.run(orch.process_all_brolls(self.plan()))
        self.assertEqual(sum(1 for c in plan.b_rolls if c.download_status == "COMPLETED"), 2)


if __name__ == "__main__":
    unittest.main()
