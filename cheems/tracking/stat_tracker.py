"""Adaptador de Tracker MediaPipe con extracción de métricas específicas para STAT."""

import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Asegurar que scr esté disponible en sys.path para importar cheems_tracker existente
SCR_PATH = Path(__file__).resolve().parents[2] / "scr"
if str(SCR_PATH) not in sys.path:
    sys.path.insert(0, str(SCR_PATH))


class STATMediaPipeTracker:
    """Procesador de landmarks de MediaPipe orientado a las conductas del Test STAT.
    
    Parámetros y Métricas computadas para STAT:
    1. Distancia inter-manual (Aplaudir - MI-1)
    2. Elevación de manos sobre nivel superior/cabeza (Manos en cabeza - MI-3)
    3. Gesto de señalar con el índice (Señalar - DA-2)
    4. Similitud gestual en imitación motora (Imitación - MI-1 a MI-4)
    5. Alineación de mirada y orientación facial estimada (Atención conjunta - DA-3, DA-4)
    """

    def __init__(self, model_path: Optional[Path] = None) -> None:
        self.tracker_instance = None
        self.is_active = False

        if model_path and model_path.exists():
            try:
                from cheems.tracking.gesture_tracker import GestureTracker
                self.tracker_instance = GestureTracker(model_path)
                self.is_active = True
            except Exception as err:
                print(f"[STATMediaPipeTracker] Nota: Tracker nativo no inicializado ({err}). Se usará modo analítico.")

    def analyze_frame_data(
        self,
        hands_data: List[Dict[str, Any]],
        pose_data: Optional[Dict[str, Any]] = None,
        face_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, float]:
        """Calcula métricas espaciales y anatómicas sobre observaciones de MediaPipe (Hands, Pose, Face)."""
        metrics: Dict[str, float] = {
            "hand_count": float(len(hands_data)),
            "clapping_proximity": 0.0,
            "hands_elevated_score": 0.0,
            "pointing_detected": 0.0,
            "pointing_vector_confidence": 0.0,
            "hand_gesture_score": 0.0,
            "gaze_alignment_score": 0.5,
            "gaze_head_turn_angle": 0.0,
            "table_tapping_oscillation": 0.0,
            "play_functional_score": 0.0,
            "symbolic_interaction_score": 0.0,
            "help_request_gesture_score": 0.0,
            "object_show_score": 0.0,
            "flapping_detected": 0.0,
            "rocking_detected": 0.0,
            "pose_anchored": 1.0 if pose_data else 0.0,
        }

        # 0. Anclaje anatómico con Pose (hombros, orejas, nariz)
        shoulder_width = 0.35  # Valor por defecto normalizado
        left_ear_y = 0.25
        right_ear_y = 0.25
        shoulder_y = 0.50
        
        if pose_data:
            l_sh = pose_data.get("left_shoulder", (0.35, 0.50, 0.0))
            r_sh = pose_data.get("right_shoulder", (0.65, 0.50, 0.0))
            shoulder_width = max(0.1, math.sqrt((l_sh[0] - r_sh[0]) ** 2 + (l_sh[1] - r_sh[1]) ** 2))
            shoulder_y = (l_sh[1] + r_sh[1]) / 2.0
            left_ear_y = pose_data.get("left_ear", (0.40, 0.25, 0.0))[1]
            right_ear_y = pose_data.get("right_ear", (0.60, 0.25, 0.0))[1]

            # Detección de balanceo de tronco (Body Rocking) - Valor Agregado
            torso_pitch = pose_data.get("torso_pitch_oscillation", 0.0)
            if torso_pitch > 0.40:
                metrics["rocking_detected"] = round(torso_pitch, 3)

        if not hands_data:
            return metrics

        # 1. Proximidad de muñecas para aplausos (MI-1) con normalización por ancho de hombros
        if len(hands_data) >= 2:
            h1_wrist = hands_data[0].get("wrist", (0.0, 0.0, 0.0))
            h2_wrist = hands_data[1].get("wrist", (0.0, 0.0, 0.0))
            dist_raw = math.sqrt((h1_wrist[0] - h2_wrist[0]) ** 2 + (h1_wrist[1] - h2_wrist[1]) ** 2)
            dist_normalized = dist_raw / shoulder_width if shoulder_width > 0 else dist_raw
            metrics["clapping_proximity"] = round(max(0.0, min(1.0, 1.0 - (dist_normalized / 2.0))), 3)

        # 2. Elevación de manos en la cabeza (MI-3) con anclaje a orejas/cabeza
        elevated = 0.0
        for hand in hands_data:
            wrist_y = hand.get("wrist", (0.0, 0.5, 0.0))[1]
            ear_y_ref = min(left_ear_y, right_ear_y)
            if pose_data:
                # Anclaje anatómico: muñeca por encima o al nivel de las orejas
                if wrist_y <= ear_y_ref + 0.05:
                    elevated = max(elevated, 1.0 - max(0.0, wrist_y - (ear_y_ref - 0.1)))
            else:
                if wrist_y < 0.35:
                    elevated = max(elevated, 1.0 - wrist_y)
        metrics["hands_elevated_score"] = round(elevated, 3)

        # 3. Detección de señalar (DA-2) y vector de señalar
        pointing_score = 0.0
        pointing_vector = 0.0
        for hand in hands_data:
            gesture_name = hand.get("gesture", "").lower()
            if "pointing" in gesture_name or gesture_name == "pointing_up":
                pointing_score = max(pointing_score, hand.get("gesture_score", 0.8))
                pointing_vector = max(pointing_vector, hand.get("vector_confidence", 0.85))
            
            # Evaluación del gesto de petición (R-2: Palma abierta extendida)
            if gesture_name in ("open_palm", "thumb_up"):
                metrics["help_request_gesture_score"] = max(metrics["help_request_gesture_score"], hand.get("gesture_score", 0.7))
            
            # Evaluación de mostrar objeto (DA-1: Mano extendida elevada sobre el tórax)
            wrist_y = hand.get("wrist", (0.0, 0.5, 0.0))[1]
            if wrist_y < shoulder_y:
                metrics["object_show_score"] = max(metrics["object_show_score"], round(shoulder_y - wrist_y + 0.5, 3))

            # Detección de Aleteo de manos (Flapping) - Valor Agregado
            hand_speed = hand.get("wrist_velocity", 0.0)
            if hand_speed > 0.70:
                metrics["flapping_detected"] = max(metrics["flapping_detected"], round(hand_speed, 3))

        metrics["pointing_detected"] = round(pointing_score, 3)
        metrics["pointing_vector_confidence"] = round(max(pointing_score, pointing_vector), 3)

        # 4. Score de coincidencia gestual general y simulación funcional de juego
        max_gesture_score = max((hand.get("gesture_score", 0.0) for hand in hands_data), default=0.0)
        metrics["hand_gesture_score"] = round(max_gesture_score, 3)
        metrics["play_functional_score"] = round(min(1.0, max_gesture_score * 0.9), 3)
        metrics["symbolic_interaction_score"] = round(min(1.0, max_gesture_score * 0.85), 3)

        # 5. Métricas de rostro y mirada (Face Data / Pose Data)
        if face_data:
            metrics["gaze_alignment_score"] = round(face_data.get("alignment_score", 0.75), 3)
            metrics["gaze_head_turn_angle"] = round(face_data.get("head_turn_yaw", 30.0), 3)

        return metrics

    def close(self) -> None:
        """Libera recursos del reconocedor MediaPipe si está activo."""
        if self.tracker_instance and hasattr(self.tracker_instance, "close"):
            self.tracker_instance.close()
            self.is_active = False

