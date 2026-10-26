from typing import List, Optional, Tuple

from core.models import ActionType, CaptionItem, TimelineSegment


class TimelineMapper:
    """
    Convierte tiempos del video ORIGINAL a tiempos del video RECORTADO.

    Tras eliminar silencios todo lo posterior se desplaza hacia atrás. Subtítulos, B-Rolls y
    tarjetas vienen con tiempos originales, así que deben pasar por aquí o quedarían
    desincronizados respecto al audio.
    """

    def __init__(self, keep_segments: List[TimelineSegment]):
        self.keep = sorted(keep_segments, key=lambda s: s.start_sec)
        self._offsets: List[float] = []
        acc = 0.0
        for seg in self.keep:
            self._offsets.append(acc)
            acc += seg.end_sec - seg.start_sec
        self.total_duration = acc

    @classmethod
    def from_plan_segments(cls, segments: List[TimelineSegment], fallback_duration: float) -> "TimelineMapper":
        keep = [s for s in segments if s.action == ActionType.KEEP and s.end_sec > s.start_sec]
        if not keep:
            keep = [TimelineSegment(start_sec=0.0, end_sec=fallback_duration, action=ActionType.KEEP)]
        return cls(keep)

    def map_range(self, start: float, end: float) -> List[Tuple[float, float]]:
        """Devuelve los tramos [inicio, fin] en tiempo recortado que sobreviven a los cortes."""
        pieces: List[Tuple[float, float]] = []
        for seg, offset in zip(self.keep, self._offsets):
            lo, hi = max(start, seg.start_sec), min(end, seg.end_sec)
            if hi - lo > 0.01:
                pieces.append((offset + (lo - seg.start_sec), offset + (hi - seg.start_sec)))
        return pieces

    def map_first(self, start: float, end: float) -> Optional[Tuple[float, float]]:
        """Primer tramo que sobrevive; útil para overlays que no deben saltar un corte."""
        pieces = self.map_range(start, end)
        return pieces[0] if pieces else None

    def remap_captions(self, captions: List[CaptionItem]) -> List[CaptionItem]:
        out: List[CaptionItem] = []
        for cap in captions:
            for s, e in self.map_range(cap.start_sec, cap.end_sec):
                if e - s >= 0.2:
                    out.append(CaptionItem(start_sec=round(s, 3), end_sec=round(e, 3),
                                           text=cap.text, highlight_words=cap.highlight_words,
                                           speaker_id=cap.speaker_id, censor_words=cap.censor_words))
        return out
