"""Actividad no clínica para registrar imitación de gestos."""

from uuid import uuid4

import cv2
import numpy as np

from cheems_project.camera.video_source import VideoSource
from cheems_project.database.sqlite_repository import SessionRepository
from cheems_project.domain.models import GestureFrame, SessionResult
from cheems_project.metrics.gesture_metrics import GestureMetrics
from cheems_project.tracking.gesture_tracker import GestureTracker
from cheems_project.ui.hotkey_controller import ControlAction, HotkeyController


HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12), (9, 13), (13, 14), (14, 15),
    (15, 16), (13, 17), (0, 17), (17, 18), (18, 19), (19, 20),
)


class GestureImitationActivity:
    """Coordina cámara, tracking, métricas y persistencia de una sesión."""

    def __init__(
        self,
        camera_source: str,
        tracker: GestureTracker,
        repository: SessionRepository,
    ) -> None:
        """Recibe dependencias para facilitar pruebas y futuras interfaces."""
        self._camera_source = camera_source
        self._tracker = tracker
        self._repository = repository

    def run(self, instruction: str) -> SessionResult | None:
        """Ejecuta una vista previa y registra solo tras una orden explícita."""
        session_id = str(uuid4())
        metrics = GestureMetrics()
        controls = HotkeyController()
        summary: dict[str, object] = {}
        session_started = False
        try:
            with VideoSource(self._camera_source) as camera:
                while True:
                    frame = camera.read()
                    tracking_frame = self._tracker.process(frame)
                    status = "Vista previa: F7 inicia | 7 respaldo"
                    if session_started:
                        status = "Registrando: F8 marca intento | F9 finaliza"
                        metrics.update(tracking_frame)
                        self._repository.record_frame(session_id, tracking_frame)
                    self._draw_overlay(frame, tracking_frame, instruction, status)
                    cv2.imshow("cheems_project Peru - Gestos", frame)
                    action = controls.poll()

                    if action is ControlAction.START and not session_started:
                        self._repository.start_session(session_id, instruction, self._camera_source)
                        self._repository.record_event(session_id, tracking_frame.timestamp_ms, "session_started")
                        session_started = True
                    elif action is ControlAction.MARK_ATTEMPT and session_started:
                        self._repository.record_event(session_id, tracking_frame.timestamp_ms, "attempt_marked")
                    elif action is ControlAction.FINISH and session_started:
                        break
                    elif action is ControlAction.CANCEL:
                        break
            summary = metrics.summary()
        except RuntimeError as error:
            summary = metrics.summary()
            summary["runtime_error"] = str(error)
            raise
        finally:
            self._tracker.close()
            cv2.destroyAllWindows()
            # Incluso ante un fallo se conserva el estado parcial de la sesión.
            if session_started:
                self._repository.finish_session(session_id, summary or metrics.summary())
        if not session_started:
            return None
        return SessionResult(session_id=session_id, summary=summary)

    @staticmethod
    def _draw_overlay(
        frame: np.ndarray,
        result: GestureFrame,
        instruction: str,
        status: str,
    ) -> None:
        """Dibuja landmarks y etiquetas descriptivas sobre el frame."""
        height, width = frame.shape[:2]
        for hand in result.hands:
            pixels = [
                (int(point.x * width), int(point.y * height))
                for point in hand.landmarks
            ]
            for start, end in HAND_CONNECTIONS:
                cv2.line(frame, pixels[start], pixels[end], (255, 255, 255), 2)
            for point in pixels:
                cv2.circle(frame, point, 3, (0, 0, 255), -1)
            wrist_x, wrist_y = pixels[0]
            cv2.putText(
                frame,
                f"{hand.side}: {hand.gesture}",
                (wrist_x, max(wrist_y - 15, 25)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )
        cv2.putText(frame, instruction, (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.putText(frame, status, (15, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
        cv2.putText(frame, "Q o Esc cancela sin guardar", (15, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
