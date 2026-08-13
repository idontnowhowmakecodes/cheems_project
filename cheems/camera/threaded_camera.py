"""
Controlador de cámara asíncrono para CHEEMS — v2.

Cambios respecto a v1:
  - VideoSessionRecorder: añade pausa/reanuda/corte de segmento
  - ThreadedCamera: soporta estado de pausa de grabación
  - CameraPool: gestiona hasta 3 cámaras simultáneas (1 análisis + 2 contexto)
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import cv2
import numpy as np


# ─────────────────────────── VideoSessionRecorder ────────────────────────────

class VideoSessionRecorder:
    """
    Grabador de video en tiempo real con soporte de pausa y corte de segmentos.

    Uso:
        rec = VideoSessionRecorder("/ruta/sesion.mp4")
        rec.start()
        rec.write_frame(frame)   # llamar en cada frame
        rec.pause()              # pausa sin cerrar el archivo
        rec.resume()             # reanuda
        rec.cut_segment("/ruta/segmento_2.mp4")  # cierra actual, abre nuevo
        rec.stop()               # finaliza y libera
    """

    def __init__(
        self,
        output_path: str,
        fps: int = 30,
        resolution: Tuple[int, int] = (640, 480),
    ) -> None:
        self.output_path = output_path
        self.fps = fps
        self.resolution = resolution
        self.writer: Optional[cv2.VideoWriter] = None
        self.is_recording: bool = False
        self.is_paused: bool = False
        self.segment_index: int = 0
        self.segments: List[str] = []          # Rutas de todos los segmentos guardados
        self.lock = threading.Lock()

    # ── Ciclo de vida ──────────────────────────────────────────────────────
    def start(self) -> None:
        """Abre el archivo de video e inicia la grabación."""
        with self.lock:
            self._open_writer(self.output_path)
            self.is_recording = True
            self.is_paused = False
            self.segments = [self.output_path]

    def write_frame(self, frame: np.ndarray) -> None:
        """Escribe un frame si está grabando y no está en pausa."""
        with self.lock:
            if self.is_recording and not self.is_paused and self.writer:
                h, w = frame.shape[:2]
                if (w, h) != self.resolution:
                    frame = cv2.resize(frame, self.resolution)
                self.writer.write(frame)

    def stop(self) -> None:
        """Detiene y cierra el archivo de video actual."""
        with self.lock:
            self.is_recording = False
            self.is_paused = False
            self._close_writer()

    # ── Control de Pausa ──────────────────────────────────────────────────
    def pause(self) -> bool:
        """Pausa la escritura sin cerrar el archivo."""
        with self.lock:
            if self.is_recording and not self.is_paused:
                self.is_paused = True
                return True
        return False

    def resume(self) -> bool:
        """Reanuda la grabación desde donde se pausó."""
        with self.lock:
            if self.is_recording and self.is_paused:
                self.is_paused = False
                return True
        return False

    # ── Corte de Segmento ─────────────────────────────────────────────────
    def cut_segment(self, new_output_path: Optional[str] = None) -> str:
        """
        Cierra el segmento actual y abre uno nuevo.

        Args:
            new_output_path: Ruta del nuevo segmento. Si es None, genera
                             automáticamente añadiendo _seg2, _seg3, etc.

        Returns:
            Ruta del segmento recién cerrado.
        """
        with self.lock:
            closed = self.output_path
            self._close_writer()

            self.segment_index += 1
            if new_output_path is None:
                base = Path(self.output_path)
                new_output_path = str(
                    base.parent / f"{base.stem}_seg{self.segment_index + 1}{base.suffix}"
                )

            self.output_path = new_output_path
            self._open_writer(new_output_path)
            self.segments.append(new_output_path)
            self.is_paused = False
            return closed

    # ── Estado ────────────────────────────────────────────────────────────
    @property
    def status(self) -> str:
        if not self.is_recording:
            return "detenida"
        if self.is_paused:
            return "pausada"
        return "grabando"

    # ── Helpers internos ──────────────────────────────────────────────────
    def _open_writer(self, path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self.writer = cv2.VideoWriter(path, fourcc, self.fps, self.resolution)

    def _close_writer(self) -> None:
        if self.writer:
            self.writer.release()
            self.writer = None


# ─────────────────────────── ThreadedCamera ──────────────────────────────────

class ThreadedCamera:
    """
    Lector de video en hilo secundario.

    Soporta streams locales (índice entero), HTTP (DroidCam), y RTSP (Raspberry Pi).
    """

    def __init__(self, source: str, role: str = "analysis") -> None:
        """
        Args:
            source: Índice numérico ("0") o URL del stream ("http://...")
            role:   "analysis" — cámara principal (Face Mesh + Hands + Pose)
                    "context"  — cámara secundaria (solo grabación, sin análisis)
        """
        self.source = source.strip()
        self.role = role
        self.cam_idx: Any = int(self.source) if self.source.isdigit() else self.source

        self.cap: Optional[cv2.VideoCapture] = None
        self.frame: Optional[np.ndarray] = None
        self.is_connected: bool = False
        self.is_running: bool = False
        self.last_frame_time: float = 0.0
        self.lock = threading.Lock()
        self.thread: Optional[threading.Thread] = None
        self.recorder: Optional[VideoSessionRecorder] = None

    def start(self) -> bool:
        """Inicializa la captura y arranca el hilo de lectura continua."""
        self.stop()
        try:
            if isinstance(self.cam_idx, str) and (
                self.cam_idx.startswith("http://")
                or self.cam_idx.startswith("https://")
                or self.cam_idx.startswith("rtsp://")
            ):
                self.cap = cv2.VideoCapture(self.cam_idx, cv2.CAP_FFMPEG)
            else:
                self.cap = cv2.VideoCapture(self.cam_idx)

            if self.cap and self.cap.isOpened():
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                self.is_connected = True
                self.is_running = True
                self.thread = threading.Thread(
                    target=self._capture_loop, daemon=True, name=f"cam-{self.source}"
                )
                self.thread.start()
                return True
        except Exception as err:
            print(f"[ThreadedCamera:{self.source}] Error al iniciar: {err}")

        self.is_connected = False
        return False

    def _capture_loop(self) -> None:
        """Bucle continuo de captura de frames en hilo separado."""
        consecutive_failures = 0
        while self.is_running and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret and frame is not None:
                consecutive_failures = 0
                with self.lock:
                    self.frame = frame
                    self.is_connected = True
                    self.last_frame_time = time.time()

                # Grabar si hay recorder activo (respeta pausa interna del recorder)
                if self.recorder and self.recorder.is_recording:
                    self.recorder.write_frame(frame)
            else:
                consecutive_failures += 1
                if consecutive_failures > 30:
                    with self.lock:
                        self.is_connected = False
                time.sleep(0.02)
            time.sleep(0.01)

    def get_latest_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Devuelve (connected, frame_copy). Frame es None si no hay señal."""
        with self.lock:
            if not self.is_connected or self.frame is None:
                return False, None
            if (time.time() - self.last_frame_time) > 3.0:
                self.is_connected = False
                return False, None
            return True, self.frame.copy()

    def stop(self) -> None:
        """Detiene el hilo y libera los recursos."""
        self.is_running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.5)
        self.thread = None

        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None
        self.is_connected = False
        with self.lock:
            self.frame = None

        if self.recorder:
            self.recorder.stop()


# ─────────────────────────── CameraPool ──────────────────────────────────────

class CameraPool:
    """
    Gestiona hasta 3 cámaras simultáneas:
      - 1 cámara de análisis (Face Mesh + grabación)
      - hasta 2 cámaras de contexto (solo grabación lateral)

    La cámara de análisis se designa en la configuración del sistema.
    """

    def __init__(self) -> None:
        self.analysis_cam: Optional[ThreadedCamera] = None
        self.context_cams: List[ThreadedCamera] = []

    def set_analysis_camera(self, source: str) -> bool:
        """Configura y arranca la cámara de análisis principal."""
        if self.analysis_cam:
            self.analysis_cam.stop()
        cam = ThreadedCamera(source, role="analysis")
        if cam.start():
            self.analysis_cam = cam
            return True
        return False

    def add_context_camera(self, source: str) -> bool:
        """Agrega una cámara de contexto lateral (máximo 2)."""
        if len(self.context_cams) >= 2:
            return False
        cam = ThreadedCamera(source, role="context")
        if cam.start():
            self.context_cams.append(cam)
            return True
        return False

    def get_analysis_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Frame de la cámara de análisis."""
        if self.analysis_cam:
            return self.analysis_cam.get_latest_frame()
        return False, None

    def start_all_recordings(self, session_id: str, base_dir: str) -> None:
        """Inicia la grabación en todas las cámaras activas."""
        if self.analysis_cam:
            path = os.path.join(base_dir, f"{session_id}_frontal.mp4")
            self.analysis_cam.recorder = VideoSessionRecorder(path)
            self.analysis_cam.recorder.start()

        for i, cam in enumerate(self.context_cams):
            path = os.path.join(base_dir, f"{session_id}_contexto_{i + 1}.mp4")
            cam.recorder = VideoSessionRecorder(path)
            cam.recorder.start()

    def pause_all_recordings(self) -> None:
        """Pausa todas las grabaciones activas."""
        cams = [self.analysis_cam] + self.context_cams
        for cam in cams:
            if cam and cam.recorder:
                cam.recorder.pause()

    def resume_all_recordings(self) -> None:
        """Reanuda todas las grabaciones pausadas."""
        cams = [self.analysis_cam] + self.context_cams
        for cam in cams:
            if cam and cam.recorder:
                cam.recorder.resume()

    def cut_all_segments(self) -> List[str]:
        """Corta segmento en todas las cámaras. Retorna rutas cerradas."""
        closed = []
        cams = [self.analysis_cam] + self.context_cams
        for cam in cams:
            if cam and cam.recorder and cam.recorder.is_recording:
                closed.append(cam.recorder.cut_segment())
        return closed

    def stop_all_recordings(self) -> Dict[str, List[str]]:
        """Detiene todas las grabaciones y retorna rutas de segmentos."""
        segments: Dict[str, List[str]] = {
            "analysis": [],
            "context": [],
        }
        if self.analysis_cam and self.analysis_cam.recorder:
            self.analysis_cam.recorder.stop()
            segments["analysis"] = self.analysis_cam.recorder.segments

        for cam in self.context_cams:
            if cam.recorder:
                cam.recorder.stop()
                segments["context"].extend(cam.recorder.segments)

        return segments

    def recording_status(self) -> Dict[str, str]:
        """Estado de grabación de cada cámara."""
        status: Dict[str, str] = {}
        if self.analysis_cam:
            rec = self.analysis_cam.recorder
            status["analysis"] = rec.status if rec else "sin grabador"
        for i, cam in enumerate(self.context_cams):
            rec = cam.recorder
            status[f"context_{i + 1}"] = rec.status if rec else "sin grabador"
        return status

    def stop_all(self) -> None:
        """Detiene todas las cámaras completamente."""
        self.stop_all_recordings()
        if self.analysis_cam:
            self.analysis_cam.stop()
            self.analysis_cam = None
        for cam in self.context_cams:
            cam.stop()
        self.context_cams.clear()
