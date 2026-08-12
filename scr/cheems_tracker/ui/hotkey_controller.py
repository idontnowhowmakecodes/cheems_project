"""Controlador de teclas rápidas para sesiones observacionales."""

from enum import Enum

import cv2


class ControlAction(Enum):
    """Acciones disponibles para el operador durante una actividad."""

    NONE = "none"
    START = "start"
    MARK_ATTEMPT = "mark_attempt"
    FINISH = "finish"
    CANCEL = "cancel"


class HotkeyController:
    """Traduce teclas de OpenCV en acciones de control tipadas."""

    _KEY_MAP = {
        118: ControlAction.START,
        ord("7"): ControlAction.START,
        119: ControlAction.MARK_ATTEMPT,
        ord("8"): ControlAction.MARK_ATTEMPT,
        120: ControlAction.FINISH,
        ord("9"): ControlAction.FINISH,
        ord("q"): ControlAction.CANCEL,
        27: ControlAction.CANCEL,
    }

    def poll(self) -> ControlAction:
        """Lee una tecla sin bloquear la visualización de video."""
        # waitKeyEx conserva códigos extendidos como F7, F8 y F9.
        key_code = cv2.waitKeyEx(1)
        return self._KEY_MAP.get(key_code, ControlAction.NONE)
