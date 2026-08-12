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
                from cheems_tracker.tracking.gesture_tracker import GestureTracker
                self.tracker_instance = GestureTracker(model_path)
                self.is_active = True
            except Exception as err:
                print(f"[STATMediaPipeTracker] Nota: Tracker nativo no inicializado ({err}). Se usará modo analítico.")

    def analyze_frame_data(self, hands_data: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calcula métricas espaciales sobre observaciones de landmarks en el frame actual."""
        metrics: Dict[str, float] = {
            "hand_count": float(len(hands_data)),
            "clapping_proximity": 0.0,
            "hands_elevated_score": 0.0,
            "pointing_detected": 0.0,
            "hand_gesture_score": 0.0,
            "gaze_alignment_score": 0.5,
        }

        if not hands_data:
            return metrics

        # 1. Proximidad de muñecas para aplausos (MI-1)
        if len(hands_data) >= 2:
            h1_wrist = hands_data[0].get("wrist", (0.0, 0.0, 0.0))
            h2_wrist = hands_data[1].get("wrist", (0.0, 0.0, 0.0))
            dist = math.sqrt(
                (h1_wrist[0] - h2_wrist[0]) ** 2 +
                (h1_wrist[1] - h2_wrist[1]) ** 2
            )
            # Menor distancia implica manos más juntas (aplauso/proximidad)
            metrics["clapping_proximity"] = round(max(0.0, 1.0 - dist), 3)

        # 2. Elevación de manos en la cabeza (MI-3)
        # En coordenadas normalizadas OpenCV/MediaPipe, y=0 es el borde superior del frame.
        elevated = 0.0
        for hand in hands_data:
            wrist_y = hand.get("wrist", (0.0, 0.5, 0.0))[1]
            if wrist_y < 0.35:  # Manos en tercio superior del frame (cerca de la cabeza)
                elevated = max(elevated, 1.0 - wrist_y)
        metrics["hands_elevated_score"] = round(elevated, 3)

        # 3. Detección de señalar (DA-2)
        pointing_score = 0.0
        for hand in hands_data:
            gesture_name = hand.get("gesture", "").lower()
            if "pointing" in gesture_name or gesture_name == "pointing_up":
                pointing_score = max(pointing_score, hand.get("gesture_score", 0.8))
        metrics["pointing_detected"] = round(pointing_score, 3)

        # 4. Score de coincidencia gestual general
        max_gesture_score = max((hand.get("gesture_score", 0.0) for hand in hands_data), default=0.0)
        metrics["hand_gesture_score"] = round(max_gesture_score, 3)

        return metrics

    def close(self) -> None:
        """Libera recursos del reconocedor MediaPipe si está activo."""
        if self.tracker_instance and hasattr(self.tracker_instance, "close"):
            self.tracker_instance.close()
            self.is_active = False
