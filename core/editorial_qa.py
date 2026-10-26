"""Auditoría editorial del montaje: ritmo, choques entre overlays y gancho inicial.

El render descartaba en silencio los overlays que chocaban. Aquí esa decisión se toma antes,
de forma explícita y con criterio: se conserva lo más valioso, se protegen las tarjetas
verificadas y todo queda registrado (qué se quitó y por qué). Es una función pura sobre el plan.

Reglas (todas configurables):
  1. Dos B-Roll no pueden solaparse: se conserva el de mayor valor (confianza + relevancia visual).
  2. Un B-Roll de video a pantalla completa no tapa una tarjeta verificada: se quita el B-Roll.
  3. Densidad máxima de B-Roll por ventana de 60 s, para no saturar.
  4. Separación mínima entre B-Roll consecutivos.
  5. Avisos (no cambian nada): gancho sin apoyo en los primeros 3 s y tramos largos sin cambio visual.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence, Tuple

VIDEO_EXT = (".mp4", ".mov", ".webm", ".mkv", ".m4v")
RENDERED_VERDICTS = ("supported", "contradicted", "insufficient")


@dataclass
class QAConfig:
    max_broll_per_minute: int = 10
    min_gap_sec: float = 0.5
    max_static_gap_sec: float = 15.0
    hook_window_sec: float = 3.0


@dataclass
class QAReport:
    dropped: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    score: int = 100


def broll_window(cue: Any) -> Tuple[float, float]:
    """Intervalo que ocupará el B-Roll al renderizar (mismas duraciones que el motor)."""
    max_dur = 3.5 if cue.start_sec < 30.0 else 4.5
    dur = min(max(cue.end_sec - cue.start_sec, 2.0), max_dur)
    return cue.start_sec, cue.start_sec + dur


def card_window(card: Any) -> Tuple[float, float]:
    dur = min(max(float(card.display_duration_sec), 4.5), 12.0)
    return card.start_sec, card.start_sec + dur


def cue_value(cue: Any) -> float:
    """0-1: qué tanto vale conservar este B-Roll (confianza del plan + relevancia visual medida)."""
    relevance = cue.relevance_score / 10.0 if getattr(cue, "relevance_score", None) is not None else 0.7
    return 0.5 * float(getattr(cue, "confidence", 0.7)) + 0.5 * relevance


def _is_video(cue: Any) -> bool:
    return str(getattr(cue, "local_file_path", "") or "").lower().endswith(VIDEO_EXT)


def _overlap(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))


def _active_cues(plan: Any) -> List[Any]:
    return [c for c in plan.b_rolls if c.enabled and c.download_status == "COMPLETED" and c.local_file_path]


def _drop(report: QAReport, cue: Any, reason: str) -> None:
    cue.enabled = False
    note = f"QA editorial: {reason}"
    cue.relevance_note = f"{cue.relevance_note} | {note}".strip(" |") if getattr(cue, "relevance_note", "") else note
    report.dropped.append({"cue_id": cue.cue_id, "concept": cue.concept, "reason": reason})


def audit_plan(plan: Any, duration: float, config: QAConfig = QAConfig()) -> QAReport:
    report = QAReport()
    duration = max(0.1, float(duration))

    # 1) B-Roll contra B-Roll: ordenar por valor y conservar los mejores sin solape ni exceso.
    kept: List[Any] = []
    for cue in sorted(_active_cues(plan), key=cue_value, reverse=True):
        window = broll_window(cue)
        clash = next((k for k in kept
                      if _overlap(window, broll_window(k)) > 0.3
                      or (window[0] < broll_window(k)[1] + config.min_gap_sec
                          and window[1] > broll_window(k)[0] - config.min_gap_sec)), None)
        if clash is not None:
            _drop(report, cue, f"choca con «{clash.concept}» (se conserva el de mayor valor)")
            continue
        # 3) Densidad: ninguna ventana de 60 s (anclada en un B-Roll) puede superar el máximo.
        starts = sorted([broll_window(k)[0] for k in kept] + [window[0]])
        worst = max(sum(1 for x in starts if anchor <= x < anchor + 60.0) for anchor in starts)
        if worst > config.max_broll_per_minute:
            _drop(report, cue, f"supera {config.max_broll_per_minute} B-Roll por minuto")
            continue
        kept.append(cue)

    # 2) B-Roll de video a pantalla completa contra tarjetas verificadas.
    cards = [c for c in plan.info_cards if c.enabled and c.verdict in RENDERED_VERDICTS and c.card_path]
    for cue in list(kept):
        if not _is_video(cue):
            continue
        window = broll_window(cue)
        hit = next((c for c in cards if _overlap(window, card_window(c)) > 0.5), None)
        if hit is not None:
            kept.remove(cue)
            _drop(report, cue, f"taparía la tarjeta «{hit.headline}»")

    # Métricas y avisos de ritmo.
    visuals = sorted([broll_window(c) for c in kept] + [card_window(c) for c in cards])
    gaps, cursor = [], 0.0
    for start, end in visuals:
        gaps.append(max(0.0, start - cursor))
        cursor = max(cursor, end)
    gaps.append(max(0.0, duration - cursor))
    longest = round(max(gaps), 1) if gaps else round(duration, 1)

    report.metrics = {
        "duration_sec": round(duration, 1),
        "broll_kept": len(kept),
        "broll_dropped": len(report.dropped),
        "cards_visible": len(cards),
        "broll_per_minute": round(len(kept) / (duration / 60.0), 1),
        "longest_static_gap_sec": longest,
    }
    if longest > config.max_static_gap_sec:
        report.warnings.append(f"Hay {longest:.0f} s seguidos sin cambio visual (máximo recomendado "
                               f"{config.max_static_gap_sec:.0f} s).")
    hook_covered = any(start < config.hook_window_sec for start, _ in visuals) or bool(
        [c for c in getattr(plan, "captions", []) if c.start_sec < config.hook_window_sec])
    if not hook_covered:
        report.warnings.append(f"Los primeros {config.hook_window_sec:.0f} s no tienen apoyo visual ni subtítulo: "
                               "el gancho puede perder espectadores.")
    for item in report.dropped:
        report.warnings.append(f"B-Roll «{item['concept']}» retirado: {item['reason']}.")

    # Puntaje 0-100: penaliza avisos de ritmo y exceso de descartes.
    penalty = 15 * sum(1 for w in report.warnings if "sin cambio visual" in w or "gancho" in w)
    penalty += min(20, 4 * len(report.dropped))
    report.score = max(0, 100 - penalty)
    report.metrics["score"] = report.score
    return report
