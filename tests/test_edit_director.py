"""Pruebas del director de edición. Funciones puras, sin red ni FFmpeg."""

import os
import unittest
from unittest import mock

from core.edit_director import DirectorConfig, direct_edit, duck_windows, emphasis_score, enabled
from core.models import CaptionItem


def cap(a, b, text, hl=()):
    return CaptionItem(start_sec=a, end_sec=b, text=text, highlight_words=list(hl))


class EmphasisTest(unittest.TestCase):
    def test_numbers_exclamations_and_keywords_score_higher(self):
        plain = emphasis_score(cap(0, 2, "y entonces pasamos a la siguiente parte del tema de hoy"))
        strong = emphasis_score(cap(0, 2, "¡Son 300 millones!", hl=["300"]))
        self.assertGreater(strong, plain + 2)

    def test_empty_text_is_zero(self):
        self.assertEqual(emphasis_score(cap(0, 1, "  ")), 0.0)


class DirectTest(unittest.TestCase):
    def strong(self, t):
        return cap(t, t + 1.5, "¡Son 300 millones!", hl=["300"])

    def test_weak_captions_get_no_zoom(self):
        caps = [cap(i * 3, i * 3 + 2, "texto normal sin nada especial que destacar aquí") for i in range(10)]
        out = direct_edit(caps, [], 30.0)
        self.assertEqual(out["zooms"], [])

    def test_min_gap_and_per_minute_cap(self):
        caps = [self.strong(t) for t in (10, 11, 12, 20, 30, 40, 50, 60, 70, 80)]
        out = direct_edit(caps, [], 90.0, DirectorConfig(min_emphasis=2.0, min_gap_sec=4.0, max_per_minute=3))
        starts = [z["start"] for z in out["zooms"]]
        self.assertTrue(all(b - a >= 4.0 for a, b in zip(starts, starts[1:])))
        self.assertLessEqual(len(starts), 5)  # 90 s * 3/min = 4.5 -> 5 como máximo

    def test_no_zoom_over_overlay(self):
        caps = [self.strong(10)]
        out = direct_edit(caps, [{"kind": "video", "start": 9.5, "dur": 4.0}], 30.0)
        self.assertEqual(out["zooms"], [])
        self.assertEqual(out["report"]["skipped"]["sobre_overlay"], 1)

    def test_styles_alternate(self):
        caps = [self.strong(t) for t in (5, 15, 25)]
        out = direct_edit(caps, [], 60.0, DirectorConfig(max_per_minute=10))
        self.assertEqual([z["style"] for z in out["zooms"]], ["punch", "slow", "punch"])

    def test_static_stretch_is_flagged(self):
        out = direct_edit([self.strong(1)], [], 60.0)
        self.assertTrue(out["interrupts"])
        self.assertGreaterEqual(out["interrupts"][0]["end"] - out["interrupts"][0]["start"], 12.0)

    def test_sfx_follow_overlays_respect_gap_and_cap(self):
        overlays = [{"kind": "card", "start": 5.0, "dur": 4}, {"kind": "video", "start": 5.5, "dur": 3},
                    {"kind": "video", "start": 20.0, "dur": 3}]
        out = direct_edit([], overlays, 60.0)
        names = {s["name"] for s in out["sfx"]}
        self.assertTrue(names <= {"pop", "whoosh", "impact"})
        times = [s["t"] for s in out["sfx"]]
        self.assertTrue(all(b - a >= 2.5 for a, b in zip(times, times[1:])))

    def test_switch_and_empty_input(self):
        self.assertTrue(enabled())
        with mock.patch.dict(os.environ, {"EDIT_DIRECTOR": "0"}):
            self.assertFalse(enabled())
        out = direct_edit([], [], 0.0)
        self.assertEqual(out["zooms"], [])


class DuckTest(unittest.TestCase):
    def test_merges_close_speech_spans(self):
        spans = duck_windows([cap(1, 2, "a"), cap(2.3, 3, "b"), cap(10, 11, "c")])
        self.assertEqual(len(spans), 2)
        self.assertAlmostEqual(spans[0]["start"], 0.85)


if __name__ == "__main__":
    unittest.main()
