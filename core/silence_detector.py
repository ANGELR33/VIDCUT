import re
import subprocess
from threading import Event
from typing import List, Optional, Tuple

from cancellation import CancellationRequested
from core.models import ActionType, TimelineSegment
from process_runner import run_process

_START = re.compile(r"silence_start:\s*(-?[\d.]+)")
_END = re.compile(r"silence_end:\s*(-?[\d.]+)")


class SilenceDetector:
    """
    Detecta silencios reales analizando el audio con FFmpeg (filtro silencedetect).

    Los timestamps que estima un LLM sobre un video largo son aproximados; el audio no miente.
    Se deja un colchón (padding) a cada lado de cada corte para no comerse el inicio/fin de palabras.
    """

    def __init__(self, noise_db: float = -32.0, padding_sec: float = 0.15,
                 cancel_event: Optional[Event] = None):
        self.noise_db = noise_db
        self.padding_sec = padding_sec
        self.cancel_event = cancel_event

    def detect(self, video_path, min_silence_sec: float) -> Optional[List[Tuple[float, float]]]:
        cmd = [
            "ffmpeg", "-hide_banner", "-nostats", "-i", str(video_path),
            "-vn", "-af", f"silencedetect=noise={self.noise_db}dB:d={min_silence_sec}",
            "-f", "null", "-",
        ]
        try:
            proc = run_process(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8", errors="replace", timeout=900,
                               cancel_event=self.cancel_event)
        except CancellationRequested:
            raise
        except Exception as exc:
            print(f"[SilenceDetector] FFmpeg no pudo analizar el audio: {exc}")
            return None
        if proc.returncode != 0:
            return None

        starts = [float(m) for m in _START.findall(proc.stderr)]
        ends = [float(m) for m in _END.findall(proc.stderr)]
        silences: List[Tuple[float, float]] = []
        for i, s in enumerate(starts):
            e = ends[i] if i < len(ends) else None
            if e is None:
                continue  # silencio abierto hasta el final: se resuelve con la duración total
            silences.append((max(0.0, s), e))
        # silencio final sin cierre
        if len(starts) > len(ends):
            silences.append((starts[-1], float("inf")))
        return silences

    def build_timeline(self, video_path, duration: float, min_silence_sec: float,
                       cancel_event: Optional[Event] = None) -> Optional[List[TimelineSegment]]:
        """Construye segmentos KEEP/CUT_SILENCE contiguos a partir del audio. None si no se pudo detectar."""
        if cancel_event is not None:
            self.cancel_event = cancel_event
        raw = self.detect(video_path, min_silence_sec)
        if raw is None:
            return None

        cuts: List[Tuple[float, float]] = []
        for s, e in raw:
            e = min(e, duration)
            s2, e2 = s + self.padding_sec, e - self.padding_sec
            if e2 - s2 >= 0.2:
                cuts.append((s2, e2))

        segments: List[TimelineSegment] = []
        cursor = 0.0
        for s, e in cuts:
            if s - cursor > 0.05:
                segments.append(TimelineSegment(start_sec=round(cursor, 3), end_sec=round(s, 3),
                                                action=ActionType.KEEP, reasoning="Habla activa"))
            segments.append(TimelineSegment(start_sec=round(s, 3), end_sec=round(e, 3),
                                            action=ActionType.CUT_SILENCE,
                                            reasoning=f"Silencio de {e - s + 2 * self.padding_sec:.1f}s (audio real)"))
            cursor = e
        if duration - cursor > 0.05:
            segments.append(TimelineSegment(start_sec=round(cursor, 3), end_sec=round(duration, 3),
                                            action=ActionType.KEEP, reasoning="Habla activa"))
        if not segments:
            segments.append(TimelineSegment(start_sec=0.0, end_sec=round(duration, 3),
                                            action=ActionType.KEEP, reasoning="Sin silencios largos"))
        return segments
