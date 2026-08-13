"""
Procesador MediaPipe Unificado para CHEEMS — MediaPipe Tasks API v1.0+

Usa la Tasks API (mp.tasks.vision) en lugar de mp.solutions (Legacy API).
Modelos requeridos en models/:
  - face_landmarker.task      → Face Mesh con 478 puntos
  - gesture_recognizer.task   → Manos con gestos
  - pose_landmarker_full.task → Pose con 33 puntos

El procesador es stateful solo para cálculos diferenciales de velocidad/frecuencia.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

# ─────────────────────────── Importación condicional de MediaPipe ────────────
try:
    import mediapipe as mp
    from mediapipe.tasks.python import vision as mp_vision
    from mediapipe.tasks.python.core import base_options as base_opts

    _BaseOptions  = base_opts.BaseOptions
    _RunningMode  = mp_vision.RunningMode
    _FaceLandmarker       = mp_vision.FaceLandmarker
    _FaceLandmarkerOpts   = mp_vision.FaceLandmarkerOptions
    _HandLandmarker       = mp_vision.HandLandmarker
    _HandLandmarkerOpts   = mp_vision.HandLandmarkerOptions
    _PoseLandmarker       = mp_vision.PoseLandmarker
    _PoseLandmarkerOpts   = mp_vision.PoseLandmarkerOptions
    _GestureRecognizer    = mp_vision.GestureRecognizer
    _GestureRecognizerOpts = mp_vision.GestureRecognizerOptions
    _MP_AVAILABLE = True
except ImportError:
    _MP_AVAILABLE = False


# ─────────────────────────── Constantes clínicas ─────────────────────────────
GAZE_YAW_THRESHOLD_DEG   = 35.0   # ° de tolerancia horizontal para "mira al frente"
GAZE_PITCH_THRESHOLD_DEG = 30.0   # ° de tolerancia vertical

FLAPPING_FREQ_MIN_HZ = 2.0        # Rango de frecuencia de aleteo (flapping)
FLAPPING_FREQ_MAX_HZ = 8.0

ROCKING_FREQ_MIN_HZ = 0.5         # Rango de frecuencia de balanceo (rocking)
ROCKING_FREQ_MAX_HZ = 2.0

# Índices de Face Landmarker v2 para solvePnP (478 puntos)
_FACE_IDX = [1, 33, 61, 199, 263, 291]

# Modelo 3D canónico de la cara (mm) para solvePnP
_FACE_3D_MODEL = np.array([
    [0.0,     0.0,     0.0   ],  # Nariz
    [-225.0,  170.0,  -135.0],  # Ojo izq.
    [-150.0, -150.0,  -125.0],  # Comisura boca izq.
    [0.0,    -330.0,  -65.0 ],  # Mentón
    [225.0,   170.0,  -135.0],  # Ojo der.
    [150.0,  -150.0,  -125.0],  # Comisura boca der.
], dtype=np.float64)


# ─────────────────────────── Dataclasses de resultado ────────────────────────
@dataclass
class FaceMetrics:
    gaze_yaw_deg: float = 0.0
    gaze_pitch_deg: float = 0.0
    gaze_roll_deg: float = 0.0
    gaze_alignment_score: float = 0.0
    attention_on: bool = False
    face_detected: bool = False


@dataclass
class HandMetrics:
    pointing_score: float = 0.0
    clapping_proximity: float = 0.0
    hands_elevated_score: float = 0.0
    help_request_score: float = 0.0
    object_show_score: float = 0.0
    hand_count: int = 0
    flapping_detected: float = 0.0
    flapping_freq_hz: float = 0.0


@dataclass
class PoseMetrics:
    shoulder_width_norm: float = 0.35
    shoulder_y_norm: float = 0.5
    ear_y_ref: float = 0.25
    rocking_detected: float = 0.0
    rocking_freq_hz: float = 0.0
    pose_detected: bool = False


@dataclass
class ProcessedFrame:
    face: FaceMetrics = field(default_factory=FaceMetrics)
    hands: HandMetrics = field(default_factory=HandMetrics)
    pose: PoseMetrics = field(default_factory=PoseMetrics)
    annotated_frame: Optional[np.ndarray] = None
    timestamp: float = field(default_factory=time.time)

    def to_flat_metrics(self) -> Dict[str, float]:
        """Convierte a dict plano para MetricsAccumulator."""
        return {
            "gaze_alignment_score":  self.face.gaze_alignment_score,
            "gaze_yaw_deg":          self.face.gaze_yaw_deg,
            "gaze_pitch_deg":        self.face.gaze_pitch_deg,
            "attention_on":          1.0 if self.face.attention_on else 0.0,
            "face_detected":         1.0 if self.face.face_detected else 0.0,
            "pointing_score":        self.hands.pointing_score,
            "clapping_proximity":    self.hands.clapping_proximity,
            "hands_elevated_score":  self.hands.hands_elevated_score,
            "help_request_score":    self.hands.help_request_score,
            "object_show_score":     self.hands.object_show_score,
            "hand_count":            float(self.hands.hand_count),
            "flapping_detected":     self.hands.flapping_detected,
            "flapping_freq_hz":      self.hands.flapping_freq_hz,
            "rocking_detected":      self.pose.rocking_detected,
            "rocking_freq_hz":       self.pose.rocking_freq_hz,
            "pose_detected":         1.0 if self.pose.pose_detected else 0.0,
        }


# ─────────────────────────── Procesador Principal ────────────────────────────
class MediaPipeProcessor:
    """
    Procesador unificado que usa la MediaPipe Tasks API (v1.0+).

    Requiere los archivos .task en models/ junto al ejecutable.
    Acepta un frame BGR de OpenCV y retorna ProcessedFrame con todas las métricas.
    """

    def __init__(
        self,
        models_dir: Optional[Path] = None,
        draw_landmarks: bool = False,
    ) -> None:
        self.draw_landmarks = draw_landmarks
        self._face_lm = None
        self._hand_lm = None
        self._pose_lm = None
        self._is_ready = False

        # Estado diferencial para frecuencias
        self._prev_wrist: Optional[Tuple[float, float]] = None
        self._prev_wrist_vel: float = 0.0
        self._wrist_sign_changes: List[float] = []

        self._prev_midpoint_y: Optional[float] = None
        self._prev_torso_vel: float = 0.0
        self._torso_sign_changes: List[float] = []

        self._prev_timestamp: float = time.time()

        if _MP_AVAILABLE:
            if models_dir is None:
                models_dir = Path("models")
            self._init_models(models_dir)

    def _init_models(self, models_dir: Path) -> None:
        """Inicializa Face, Hand y Pose Landmarkers con la Tasks API."""
        ok_count = 0

        face_path = models_dir / "face_landmarker.task"
        hand_path = models_dir / "hand_landmarker.task"
        pose_path = models_dir / "pose_landmarker_full.task"
        gesture_path = models_dir / "gesture_recognizer.task"

        # ── Face Landmarker ────────────────────────────────────────────────
        if face_path.exists():
            try:
                opts = _FaceLandmarkerOpts(
                    base_options=_BaseOptions(model_asset_path=str(face_path)),
                    running_mode=_RunningMode.IMAGE,
                    num_faces=1,
                    min_face_detection_confidence=0.5,
                    min_face_presence_confidence=0.5,
                    min_tracking_confidence=0.5,
                    output_face_blendshapes=False,
                    output_facial_transformation_matrixes=False,
                )
                self._face_lm = _FaceLandmarker.create_from_options(opts)
                ok_count += 1
                print("[MediaPipeProcessor] [OK] Face Landmarker inicializado.")
            except Exception as e:
                print(f"[MediaPipeProcessor] [FAIL] Face Landmarker: {e}")
        else:
            print(f"[MediaPipeProcessor] [WARN] face_landmarker.task no encontrado en {face_path}")

        # ── Hand Landmarker (fallback: gesture_recognizer.task tiene hands) ─
        hand_model = hand_path if hand_path.exists() else gesture_path
        if hand_model.exists():
            try:
                if hand_model.name == "gesture_recognizer.task":
                    opts = _GestureRecognizerOpts(
                        base_options=_BaseOptions(model_asset_path=str(hand_model)),
                        running_mode=_RunningMode.IMAGE,
                        num_hands=2,
                        min_hand_detection_confidence=0.5,
                        min_hand_presence_confidence=0.5,
                        min_tracking_confidence=0.5,
                    )
                    self._hand_lm = _GestureRecognizer.create_from_options(opts)
                else:
                    opts = _HandLandmarkerOpts(
                        base_options=_BaseOptions(model_asset_path=str(hand_model)),
                        running_mode=_RunningMode.IMAGE,
                        num_hands=2,
                        min_hand_detection_confidence=0.5,
                        min_hand_presence_confidence=0.5,
                        min_tracking_confidence=0.5,
                    )
                    self._hand_lm = _HandLandmarker.create_from_options(opts)
                ok_count += 1
                print(f"[MediaPipeProcessor] [OK] Hand Landmarker ({hand_model.name}) inicializado.")
            except Exception as e:
                print(f"[MediaPipeProcessor] [FAIL] Hand Landmarker: {e}")
        else:
            print("[MediaPipeProcessor] [WARN] Ningún modelo de manos disponible.")

        # ── Pose Landmarker ────────────────────────────────────────────────
        if pose_path.exists():
            try:
                opts = _PoseLandmarkerOpts(
                    base_options=_BaseOptions(model_asset_path=str(pose_path)),
                    running_mode=_RunningMode.IMAGE,
                    num_poses=1,
                    min_pose_detection_confidence=0.5,
                    min_pose_presence_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
                self._pose_lm = _PoseLandmarker.create_from_options(opts)
                ok_count += 1
                print("[MediaPipeProcessor] [OK] Pose Landmarker inicializado.")
            except Exception as e:
                print(f"[MediaPipeProcessor] [FAIL] Pose Landmarker: {e}")
        else:
            print(f"[MediaPipeProcessor] [WARN] pose_landmarker_full.task no encontrado en {pose_path}")

        self._is_ready = ok_count > 0
        print(f"[MediaPipeProcessor] {'[OK] Listo' if self._is_ready else '[FAIL] Sin modelos'} ({ok_count}/3 modelos cargados)")

    @property
    def is_ready(self) -> bool:
        return self._is_ready and _MP_AVAILABLE

    def process_frame(self, frame_bgr: np.ndarray) -> ProcessedFrame:
        """Procesa un frame BGR y retorna todas las métricas biométricas."""
        result = ProcessedFrame()

        if not self.is_ready or frame_bgr is None:
            return result

        now = time.time()
        dt = max(0.001, now - self._prev_timestamp)
        self._prev_timestamp = now

        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

        # Construir la imagen MediaPipe
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        # ── Procesamiento MediaPipe ─────────────────────────────────────
        if self._pose_lm:
            try:
                pose_res = self._pose_lm.detect(mp_image)
                result.pose = self._compute_pose_metrics(pose_res, dt)
                if self.draw_landmarks and pose_res.pose_landmarks:
                    for pose_landmarks in pose_res.pose_landmarks:
                        self._draw_landmarks_v2(frame_bgr, pose_landmarks)
            except Exception as e:
                pass

        if self._face_lm:
            try:
                face_res = self._face_lm.detect(mp_image)
                result.face = self._compute_face_metrics(face_res, w, h)
                if self.draw_landmarks and face_res.face_landmarks:
                    for face_landmarks in face_res.face_landmarks:
                        self._draw_landmarks_v2(frame_bgr, face_landmarks)
            except Exception as e:
                pass

        if self._hand_lm:
            try:
                if hasattr(self._hand_lm, "recognize"):
                    hand_res = self._hand_lm.recognize(mp_image)
                else:
                    hand_res = self._hand_lm.detect(mp_image)
                result.hands = self._compute_hand_metrics(
                    hand_res, dt,
                    shoulder_width=result.pose.shoulder_width_norm,
                    shoulder_y=result.pose.shoulder_y_norm,
                    ear_y_ref=result.pose.ear_y_ref,
                )
                if self.draw_landmarks and hand_res.hand_landmarks:
                    for hand_landmarks in hand_res.hand_landmarks:
                        self._draw_landmarks_v2(frame_bgr, hand_landmarks)
            except Exception as e:
                pass

        if self.draw_landmarks:
            result.annotated_frame = frame_bgr

        result.timestamp = now
        return result

    def _draw_landmarks_v2(self, image: np.ndarray, landmark_list: Any):
        """Dibuja landmarks manualmente para ser compatible con la Tasks API"""
        if not landmark_list:
            return
        image_rows, image_cols, _ = image.shape
        idx_to_coordinates = {}
        for idx, landmark in enumerate(landmark_list):
            if landmark.visibility is not None and landmark.visibility < 0.5:
                continue
            if landmark.presence is not None and landmark.presence < 0.5:
                continue
            landmark_px = min(math.floor(landmark.x * image_cols), image_cols - 1), \
                          min(math.floor(landmark.y * image_rows), image_rows - 1)
            idx_to_coordinates[idx] = landmark_px
        
        for idx, landmark_px in idx_to_coordinates.items():
            cv2.circle(image, landmark_px, 1, (0, 255, 255), -1)


    # ─────────────────── Face Metrics (solvePnP) ─────────────────────────
    def _compute_face_metrics(self, face_res: Any, w: int, h: int) -> FaceMetrics:
        m = FaceMetrics()
        if not face_res or not face_res.face_landmarks:
            return m
        m.face_detected = True

        lms = face_res.face_landmarks[0]  # Primera cara

        try:
            pts_2d = np.array([
                [lms[idx].x * w, lms[idx].y * h]
                for idx in _FACE_IDX
            ], dtype=np.float64)

            focal = w
            cam_matrix = np.array([
                [focal, 0,     w / 2],
                [0,     focal, h / 2],
                [0,     0,     1    ],
            ], dtype=np.float64)
            dist_coeffs = np.zeros((4, 1), dtype=np.float64)

            ok, rvec, _ = cv2.solvePnP(
                _FACE_3D_MODEL, pts_2d, cam_matrix, dist_coeffs,
                flags=cv2.SOLVEPNP_ITERATIVE,
            )
            if not ok:
                return m

            rot_mat, _ = cv2.Rodrigues(rvec)
            sy = math.sqrt(rot_mat[0, 0] ** 2 + rot_mat[1, 0] ** 2)
            singular = sy < 1e-6

            if not singular:
                pitch = math.degrees(math.atan2(rot_mat[2, 1], rot_mat[2, 2]))
                yaw   = math.degrees(math.atan2(-rot_mat[2, 0], sy))
                roll  = math.degrees(math.atan2(rot_mat[1, 0], rot_mat[0, 0]))
            else:
                pitch = math.degrees(math.atan2(-rot_mat[1, 2], rot_mat[1, 1]))
                yaw   = math.degrees(math.atan2(-rot_mat[2, 0], sy))
                roll  = 0.0

            m.gaze_yaw_deg   = round(yaw, 2)
            m.gaze_pitch_deg = round(pitch, 2)
            m.gaze_roll_deg  = round(roll, 2)

            yaw_score   = max(0.0, 1.0 - abs(yaw)   / 90.0)
            pitch_score = max(0.0, 1.0 - abs(pitch) / 60.0)
            m.gaze_alignment_score = round(yaw_score * 0.7 + pitch_score * 0.3, 4)
            m.attention_on = (
                abs(yaw)   <= GAZE_YAW_THRESHOLD_DEG and
                abs(pitch) <= GAZE_PITCH_THRESHOLD_DEG
            )
        except Exception:
            pass

        return m

    # ─────────────────── Hand Metrics ─────────────────────────────────────
    def _compute_hand_metrics(
        self,
        hand_res: Any,
        dt: float,
        shoulder_width: float = 0.35,
        shoulder_y: float = 0.5,
        ear_y_ref: float = 0.25,
    ) -> HandMetrics:
        m = HandMetrics()
        if not hand_res or not hand_res.hand_landmarks:
            self._prev_wrist = None
            return m

        lm_list = hand_res.hand_landmarks
        m.hand_count = len(lm_list)
        wrists: List[Tuple[float, float]] = []

        for lm in lm_list:
            wrist = (lm[0].x, lm[0].y)
            wrists.append(wrist)

            # ── Señalamiento: extensión del índice ────────────────────────
            v_index = math.sqrt(
                (lm[8].x - lm[5].x) ** 2 + (lm[8].y - lm[5].y) ** 2
            )
            def fd(a: int, b: int) -> float:
                return math.sqrt((lm[a].x - lm[b].x) ** 2 + (lm[a].y - lm[b].y) ** 2)

            flex_others = (fd(12, 9) + fd(16, 13) + fd(20, 17)) / 3.0
            denom = v_index + flex_others
            if denom > 1e-6:
                m.pointing_score = max(m.pointing_score, round(min(1.0, v_index / denom), 4))

            # ── Palma abierta (petición) ──────────────────────────────────
            fingers_ext = fd(8, 5) + fd(12, 9) + fd(16, 13) + fd(20, 17)
            palm_size = fd(0, 9)
            if palm_size > 1e-6:
                open_score = fingers_ext / (4 * palm_size * 2.5)
                m.help_request_score = max(m.help_request_score, round(min(1.0, open_score), 4))

            # ── Objeto sobre tórax ────────────────────────────────────────
            if wrist[1] < shoulder_y:
                m.object_show_score = max(
                    m.object_show_score,
                    round(min(1.0, (shoulder_y - wrist[1]) / max(shoulder_y, 0.1) + 0.4), 4)
                )

            # ── Manos sobre cabeza ────────────────────────────────────────
            if wrist[1] < ear_y_ref + 0.05:
                elev = 1.0 - max(0.0, wrist[1] - (ear_y_ref - 0.1))
                m.hands_elevated_score = max(m.hands_elevated_score, round(elev, 4))

        # ── Proximidad de muñecas (aplausos) ──────────────────────────────
        if len(wrists) >= 2:
            dist_raw = math.sqrt(
                (wrists[0][0] - wrists[1][0]) ** 2 +
                (wrists[0][1] - wrists[1][1]) ** 2
            )
            dist_norm = dist_raw / max(shoulder_width, 0.05)
            m.clapping_proximity = round(max(0.0, min(1.0, 1.0 - dist_norm / 2.0)), 4)

        # ── Flapping ──────────────────────────────────────────────────────
        m.flapping_detected, m.flapping_freq_hz = self._compute_flapping(wrists, dt)

        return m

    def _compute_flapping(
        self, wrists: List[Tuple[float, float]], dt: float
    ) -> Tuple[float, float]:
        if not wrists:
            return 0.0, 0.0
        now = time.time()
        wrist = wrists[0]

        if self._prev_wrist is None:
            self._prev_wrist = wrist
            return 0.0, 0.0

        vel_y = (wrist[1] - self._prev_wrist[1]) / dt
        if (vel_y > 0) != (self._prev_wrist_vel > 0) and abs(vel_y) > 0.05:
            self._wrist_sign_changes.append(now)

        self._prev_wrist_vel = vel_y
        self._prev_wrist = wrist

        cutoff = now - 3.0
        self._wrist_sign_changes = [t for t in self._wrist_sign_changes if t > cutoff]
        n = len(self._wrist_sign_changes)
        if n < 4:
            return 0.0, 0.0

        freq_hz = n / (2.0 * 3.0)
        is_flapping = FLAPPING_FREQ_MIN_HZ <= freq_hz <= FLAPPING_FREQ_MAX_HZ
        score = min(1.0, (freq_hz - FLAPPING_FREQ_MIN_HZ) / max(FLAPPING_FREQ_MAX_HZ - FLAPPING_FREQ_MIN_HZ, 0.1)) if is_flapping else 0.0
        return round(score, 4), round(freq_hz, 2)

    # ─────────────────── Pose Metrics ─────────────────────────────────────
    def _compute_pose_metrics(self, pose_res: Any, dt: float) -> PoseMetrics:
        m = PoseMetrics()
        if not pose_res or not pose_res.pose_landmarks:
            return m
        m.pose_detected = True

        lm = pose_res.pose_landmarks[0]
        l_sh = (lm[11].x, lm[11].y)  # Hombro izq.
        r_sh = (lm[12].x, lm[12].y)  # Hombro der.
        l_ear_y = lm[7].y             # Oreja izq.
        r_ear_y = lm[8].y             # Oreja der.

        m.shoulder_width_norm = max(0.05, math.sqrt(
            (l_sh[0] - r_sh[0]) ** 2 + (l_sh[1] - r_sh[1]) ** 2
        ))
        m.shoulder_y_norm = (l_sh[1] + r_sh[1]) / 2.0
        m.ear_y_ref = min(l_ear_y, r_ear_y)

        # Rocking
        mid_y = m.shoulder_y_norm
        m.rocking_detected, m.rocking_freq_hz = self._compute_rocking(mid_y, dt)
        return m

    def _compute_rocking(self, mid_y: float, dt: float) -> Tuple[float, float]:
        now = time.time()
        if self._prev_midpoint_y is None:
            self._prev_midpoint_y = mid_y
            return 0.0, 0.0

        vel = (mid_y - self._prev_midpoint_y) / dt
        if (vel > 0) != (self._prev_torso_vel > 0) and abs(vel) > 0.01:
            self._torso_sign_changes.append(now)

        self._prev_torso_vel = vel
        self._prev_midpoint_y = mid_y

        cutoff = now - 4.0
        self._torso_sign_changes = [t for t in self._torso_sign_changes if t > cutoff]
        n = len(self._torso_sign_changes)
        if n < 3:
            return 0.0, 0.0

        freq_hz = n / (2.0 * 4.0)
        is_rocking = ROCKING_FREQ_MIN_HZ <= freq_hz <= ROCKING_FREQ_MAX_HZ
        score = min(1.0, freq_hz / max(ROCKING_FREQ_MAX_HZ, 0.1)) if is_rocking else 0.0
        return round(score, 4), round(freq_hz, 2)

    def reset_state(self) -> None:
        """Reinicia el estado diferencial al iniciar un nuevo ítem."""
        self._prev_wrist = None
        self._prev_wrist_vel = 0.0
        self._wrist_sign_changes.clear()
        self._prev_midpoint_y = None
        self._prev_torso_vel = 0.0
        self._torso_sign_changes.clear()

    def close(self) -> None:
        """Libera recursos de los modelos MediaPipe."""
        for model in [self._face_lm, self._hand_lm, self._pose_lm]:
            if model:
                try:
                    model.close()
                except Exception:
                    pass
        self._is_ready = False
        print("[MediaPipeProcessor] Recursos liberados.")
