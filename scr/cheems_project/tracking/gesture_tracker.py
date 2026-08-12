"""Adaptador MediaPipe para landmarks y gestos predefinidos de manos."""

import time
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np

from cheems_project.domain.models import GestureFrame, HandObservation, LandmarkPoint


class GestureTracker:
    """Procesa frames y transforma resultados MediaPipe en entidades de dominio."""

    def __init__(self, model_path: Path) -> None:
        """Inicializa el reconocedor con un modelo oficial de MediaPipe."""
        if not model_path.exists():
            raise FileNotFoundError(f"Falta el modelo de gestos: {model_path}")

        self._start_time = time.monotonic()
        self._last_timestamp_ms = -1
        options = mp.tasks.vision.GestureRecognizerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.4,
            min_tracking_confidence=0.5,
        )
        self._recognizer = mp.tasks.vision.GestureRecognizer.create_from_options(options)

    def process(self, frame: np.ndarray) -> GestureFrame:
        """Analiza un frame BGR y devuelve manos y gestos con tiempo monotónico."""
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        # MediaPipe VIDEO exige timestamps estrictamente crecientes.
        timestamp_ms = max(
            int((time.monotonic() - self._start_time) * 1000),
            self._last_timestamp_ms + 1,
        )
        self._last_timestamp_ms = timestamp_ms
        result = self._recognizer.recognize_for_video(image, timestamp_ms)
        hands: list[HandObservation] = []

        for landmarks, handedness, gestures in zip(
            result.hand_landmarks,
            result.handedness,
            result.gestures,
        ):
            hand_category = handedness[0]
            gesture_category = gestures[0]
            points = tuple(
                LandmarkPoint(x=point.x, y=point.y, z=point.z)
                for point in landmarks
            )
            hands.append(
                HandObservation(
                    side=hand_category.category_name,
                    side_score=hand_category.score,
                    gesture=gesture_category.category_name,
                    gesture_score=gesture_category.score,
                    landmarks=points,
                )
            )
        return GestureFrame(timestamp_ms=timestamp_ms, hands=tuple(hands))

    def close(self) -> None:
        """Libera los recursos nativos usados por MediaPipe."""
        self._recognizer.close()
