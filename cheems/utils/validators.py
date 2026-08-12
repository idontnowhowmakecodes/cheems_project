"""Validadores de datos para el sistema CHEEMS y el Test STAT."""

import re
from typing import Tuple


def validate_patient_age(age_months: int) -> Tuple[bool, str]:
    """Valida si la edad del paciente en meses está dentro del rango para STAT (12 a 36 meses / 1 a 3 años)."""
    if not isinstance(age_months, int):
        return False, "La edad debe ser un número entero de meses."
    if age_months < 12:
        return False, f"Edad ({age_months}m) menor a 12 meses. El STAT está validado para niños de 12 a 36 meses."
    if age_months > 36:
        return False, f"Edad ({age_months}m) mayor a 36 meses (3 años). Fuera del rango estandarizado del STAT."
    return True, "Edad dentro del rango válido (12-36m)."


def validate_camera_source(source: str) -> bool:
    """Valida la sintaxis del origen de cámara (RTSP, HTTP/WebRTC o dispositivo local)."""
    if source.isdigit():
        return True  # Índice de cámara de OpenCV p. ej. '0'
    if source.startswith(("http://", "https://", "rtsp://", "rtsps://")):
        return True
    return False
