"""Pruebas de la sincronización del B-Roll con la transcripción. Sin red ni modelos."""

import unittest

from core.broll_sync import resync_broll_to_captions
from core.models import BRollCue, CaptionItem


def cue(start, end=None, phrase="", concept="Torre Eiffel", query="eiffel tower", cue_id="b1"):
    return BRollCue(cue_id=cue_id, start_sec=start, end_sec=end or start + 3, concept=concept,
                    search_query_en=query, reasoning="x", spoken_phrase=phrase)


def cap(start, text):
    return CaptionItem(start_sec=start, end_sec=start + 3, text=text)


CAPS = [
    cap(0.0, "Hoy hablamos de viajes"),
    cap(10.0, "Fuimos a la Torre Eiffel en París"),
    cap(14.0, "Después comimos algo rico"),
]


class ResyncTest(unittest.TestCase):
    def test_moves_cue_to_the_matching_phrase_and_keeps_duration(self):
        c = cue(8.0, 11.0, phrase="Fuimos a la Torre Eiffel")
        moved = resync_broll_to_captions([c], CAPS)
        self.assertEqual(len(moved), 1)
        self.assertEqual(c.start_sec, 10.0)
        self.assertEqual(c.end_sec, 13.0)
        self.assertEqual(moved[0]["source"], "spoken_phrase")

    def test_falls_back_to_concept_when_no_phrase(self):
        c = cue(7.0, 10.0)
        resync_broll_to_captions([c], [cap(10.0, "visitamos la torre eiffel hoy")])
        self.assertEqual(c.start_sec, 10.0)

    def test_leaves_cue_alone_when_nothing_matches(self):
        c = cue(8.0, 11.0, phrase="Fuimos a la Torre Eiffel")
        moved = resync_broll_to_captions([c], [cap(8.0, "completamente distinto aquí")])
        self.assertEqual(moved, [])
        self.assertEqual(c.start_sec, 8.0)

    def test_ignores_tiny_shifts(self):
        c = cue(9.8, 12.8, phrase="Fuimos a la Torre Eiffel")
        self.assertEqual(resync_broll_to_captions([c], CAPS), [])
        self.assertEqual(c.start_sec, 9.8)

    def test_ignores_captions_outside_the_window(self):
        c = cue(40.0, 43.0, phrase="Fuimos a la Torre Eiffel")
        self.assertEqual(resync_broll_to_captions([c], CAPS), [])

    def test_never_goes_negative_and_handles_empty_inputs(self):
        c = cue(2.0, 5.0, phrase="Hoy hablamos de viajes")
        resync_broll_to_captions([c], CAPS)
        self.assertGreaterEqual(c.start_sec, 0.0)
        self.assertEqual(resync_broll_to_captions([], CAPS), [])
        self.assertEqual(resync_broll_to_captions([c], []), [])


if __name__ == "__main__":
    unittest.main()
