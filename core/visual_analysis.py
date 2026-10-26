"""Análisis visual local para que los overlays respeten el encuadre.

No envía fotogramas a servicios externos: detecta cortes de plano con
PySceneDetect y usa el clasificador facial incluido en OpenCV para ubicar al
hablante. Ambos resultados son sugerencias; cuando no hay detección válida se
mantiene el comportamiento editorial existente (``auto``).
"""

from __future__ import annotations

from pathlib import Path
from statistics import median
from threading import Event
from typing import Iterable, List, Optional

from cancellation import CancellationRequested
from core.models import InfoCard


class VisualAnalyzer:
    def __init__(self, cancel_event: Optional[Event] = None):
        self.cancel_event = cancel_event

    def detect_scene_cuts(self, video_path: Path, min_scene_len_sec: float = 1.2) -> List[float]:
        """Devuelve cambios de plano para diagnóstico y decisiones editoriales.

        AdaptiveDetector usa un promedio móvil, por lo que evita confundir
        movimiento rápido de cámara con un corte. Una ausencia de PySceneDetect
        o un archivo peculiar nunca detiene el render.
        """
        if self.cancel_event and self.cancel_event.is_set():
            raise CancellationRequested()
        try:
            from scenedetect import AdaptiveDetector, detect
            scenes = detect(str(video_path), AdaptiveDetector(min_scene_len=min_scene_len_sec))
            if self.cancel_event and self.cancel_event.is_set():
                raise CancellationRequested()
            return [round(end.get_seconds(), 3) for _start, end in scenes[:-1]]
        except CancellationRequested:
            raise
        except Exception as exc:
            print(f"[VisualAnalyzer] No se detectaron cambios de plano: {exc}")
            return []

    def place_cards_away_from_speaker(self, video_path: Path, cards: Iterable[InfoCard]) -> int:
        """Sugiere un lado para cada tarjeta automática según la cara dominante.

        Se inspecciona un solo cuadro por tarjeta, cerca de la frase detectada,
        para no transformar este paso en un segundo render. Solo se modifican
        tarjetas con posición ``auto`` para respetar ajustes manuales o del LLM.
        """
        try:
            import cv2
        except Exception as exc:
            print(f"[VisualAnalyzer] OpenCV no está disponible: {exc}")
            return 0

        if not hasattr(cv2, "CascadeClassifier") or not hasattr(cv2, "data") or not hasattr(cv2.data, "haarcascades"):
            return 0

        cascade_dir = Path(cv2.data.haarcascades)
        classifiers = []
        for name in ["haarcascade_frontalface_alt2.xml", "haarcascade_frontalface_default.xml", "haarcascade_profileface.xml"]:
            cp = cascade_dir / name
            if cp.exists():
                clf = cv2.CascadeClassifier(str(cp))
                if not clf.empty():
                    classifiers.append(clf)

        if not classifiers:
            return 0
        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            return 0

        def detect_best_face(frame_gray):
            faces = []
            for clf in classifiers:
                f_list = clf.detectMultiScale(frame_gray, scaleFactor=1.1, minNeighbors=4, minSize=(32, 32))
                if len(f_list):
                    faces.extend(list(f_list))
            # Detección de perfil invertido (rostro mirando a la izquierda)
            if len(classifiers) >= 3:
                flipped = cv2.flip(frame_gray, 1)
                flip_faces = classifiers[2].detectMultiScale(flipped, scaleFactor=1.1, minNeighbors=4, minSize=(32, 32))
                W_img = frame_gray.shape[1]
                for (fx, fy, fw, fh) in flip_faces:
                    faces.append((W_img - fx - fw, fy, fw, fh))
            return max(faces, key=lambda f: int(f[2]) * int(f[3])) if faces else None

        placed = 0
        try:
            for card in cards:
                if self.cancel_event and self.cancel_event.is_set():
                    raise CancellationRequested()
                if not card.enabled or card.screen_position != "auto":
                    continue
                capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, card.start_sec + 0.25) * 1000)
                ok, frame = capture.read()
                if not ok or frame is None:
                    continue
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                best = detect_best_face(gray)
                if best is None:
                    continue
                x, _y, w, h = best
                center = (float(x) + float(w) / 2) / max(1, frame.shape[1])
                if center < 0.44:
                    card.screen_position = "lower_right"
                elif center > 0.56:
                    card.screen_position = "lower_left"
                else:
                    card.screen_position = "upper_right"
                placed += 1
        finally:
            capture.release()
        return placed

    def dominant_face_focus(self, video_path: Path, start_sec: float, end_sec: float,
                            samples: int = 8) -> float:
        """Devuelve el centro horizontal del rostro dominante de un clip.

        Muestrea múltiples fotogramas y utiliza clasificadores frontal y de perfil
        con suavizado y filtro de mediana para encuadrar verticalmente con precisión.
        """
        try:
            import cv2
        except Exception:
            return 0.5
        if not hasattr(cv2, "CascadeClassifier") or not hasattr(cv2, "data") or not hasattr(cv2.data, "haarcascades"):
            return 0.5
        cascade_dir = Path(cv2.data.haarcascades)
        classifiers = []
        for name in ["haarcascade_frontalface_alt2.xml", "haarcascade_frontalface_default.xml", "haarcascade_profileface.xml"]:
            cp = cascade_dir / name
            if cp.exists():
                clf = cv2.CascadeClassifier(str(cp))
                if not clf.empty():
                    classifiers.append(clf)

        if not classifiers:
            return 0.5
        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            return 0.5
        centers: List[float] = []
        try:
            span = max(0.15, float(end_sec) - float(start_sec))
            for index in range(max(1, samples)):
                if self.cancel_event and self.cancel_event.is_set():
                    raise CancellationRequested()
                at = float(start_sec) + span * (index + 0.5) / max(1, samples)
                capture.set(cv2.CAP_PROP_POS_MSEC, at * 1000)
                ok, frame = capture.read()
                if not ok or frame is None:
                    continue
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = []
                for clf in classifiers:
                    f_list = clf.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(32, 32))
                    if len(f_list):
                        faces.extend(list(f_list))
                if len(classifiers) >= 3:
                    flipped = cv2.flip(gray, 1)
                    flip_faces = classifiers[2].detectMultiScale(flipped, scaleFactor=1.1, minNeighbors=4, minSize=(32, 32))
                    W_img = frame.shape[1]
                    for (fx, fy, fw, fh) in flip_faces:
                        faces.append((W_img - fx - fw, fy, fw, fh))

                if faces:
                    x, _y, w, h = max(faces, key=lambda f: int(f[2]) * int(f[3]))
                    centers.append((float(x) + float(w) / 2) / max(1, frame.shape[1]))
        finally:
            capture.release()
        return max(0.0, min(1.0, float(median(centers)))) if centers else 0.5
