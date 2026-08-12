"""Adaptador seguro de OpenCV para una fuente de video."""

import cv2
import numpy as np


class VideoSource:
    """Abre, lee y libera una cámara local o URL de DroidCam."""

    def __init__(self, source: str) -> None:
        """Guarda una fuente compatible con `cv2.VideoCapture`."""
        self._source = source
        self._capture: cv2.VideoCapture | None = None

    def open(self) -> None:
        """Abre el stream y falla de forma explícita si no está disponible."""
        self._capture = cv2.VideoCapture(self._source)
        if not self._capture.isOpened():
            self.close()
            raise RuntimeError(f"No se pudo abrir la fuente de video: {self._source}")

    def read(self) -> np.ndarray:
        """Lee un frame BGR de la fuente abierta."""
        if self._capture is None:
            raise RuntimeError("La fuente de video no está abierta.")
        success, frame = self._capture.read()
        if not success or frame is None:
            raise RuntimeError("No se pudo leer un frame de video.")
        return frame

    def close(self) -> None:
        """Libera la cámara si fue abierta."""
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def __enter__(self) -> "VideoSource":
        """Abre la fuente al entrar a un bloque `with`."""
        self.open()
        return self

    def __exit__(self, *_: object) -> None:
        """Libera la fuente al salir de un bloque `with`."""
        self.close()
