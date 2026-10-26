"""Reglas locales que protegen la exportación frente a planes imperfectos."""

from dataclasses import dataclass, field
from typing import List

from core.models import VideoEditingPlan


@dataclass
class QualityReport:
    fixes: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class PlanQualityGate:
    """Ajusta tiempos imposibles sin cambiar decisiones editoriales válidas."""

    def __init__(self, duration: float):
        self.duration = max(0.1, float(duration))

    def apply(self, plan: VideoEditingPlan) -> QualityReport:
        report = QualityReport()

        for card in plan.info_cards:
            original_start = card.start_sec
            card.start_sec = min(max(0.0, card.start_sec), max(0.0, self.duration - 0.1))
            card.end_sec = max(card.start_sec + 0.1, min(card.end_sec, self.duration))
            card.display_duration_sec = min(max(card.display_duration_sec, 4.5), 12.0)
            if card.start_sec != original_start:
                report.fixes.append(f"Tarjeta «{card.headline}» ajustada al rango del video")
            if card.verdict == "supported" and not card.sources:
                report.warnings.append(f"Tarjeta «{card.headline}» está marcada como confirmada sin fuente")

        for cue in plan.b_rolls:
            before = (cue.start_sec, cue.end_sec)
            cue.start_sec = min(max(0.0, cue.start_sec), max(0.0, self.duration - 0.1))
            cue.end_sec = max(cue.start_sec + 1.0, min(cue.end_sec, self.duration))
            if cue.end_sec > self.duration:
                cue.enabled = False
                report.warnings.append(f"B-Roll «{cue.concept}» quedó fuera del video y se desactivó")
            elif before != (cue.start_sec, cue.end_sec):
                report.fixes.append(f"B-Roll «{cue.concept}» ajustado al rango del video")

        for clip in plan.highlights:
            clip.start_sec = min(max(0.0, clip.start_sec), max(0.0, self.duration - 0.1))
            clip.end_sec = max(clip.start_sec + 1.0, min(clip.end_sec, self.duration))
            if clip.end_sec > self.duration:
                clip.end_sec = self.duration
                report.warnings.append(f"Short «{clip.title}» quedó fuera del rango y se recortó")

        return report
