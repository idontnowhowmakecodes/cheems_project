"""Interfaz de línea de comandos para la primera actividad de cheems_project."""

import argparse

from cheems_project.activities.gesture_imitation import GestureImitationActivity
from cheems_project.config import default_config
from cheems_project.database.sqlite_repository import SessionRepository
from cheems_project.tracking.gesture_tracker import GestureTracker


DEFAULT_DROIDCAM_URL = "http://192.168.18.145:4747/video"


def parse_arguments() -> argparse.Namespace:
    """Obtiene parámetros no clínicos definidos por el operador."""
    parser = argparse.ArgumentParser(description="cheems_project Perú — actividad de gestos")
    parser.add_argument("--source", default=DEFAULT_DROIDCAM_URL, help="URL del stream de DroidCam")
    parser.add_argument(
        "--instruction",
        default="Actividad de gestos guiada por el terapeuta",
        help="Texto descriptivo de la instrucción aplicada",
    )
    return parser.parse_args()


def main() -> None:
    """Ejecuta una sesión de gestos y muestra su resumen descriptivo."""
    arguments = parse_arguments()
    config = default_config(arguments.source)
    repository = SessionRepository(config.database_path)
    try:
        tracker = GestureTracker(config.model_path)
        activity = GestureImitationActivity(arguments.source, tracker, repository)
        result = activity.run(arguments.instruction)
        if result is None:
            print("Sesión cancelada antes de iniciar; no se guardaron datos.")
            return
        print(f"Sesión guardada: {result.session_id}")
        print(f"Resumen: {result.summary}")
    except (FileNotFoundError, RuntimeError) as error:
        print(f"No se pudo completar la sesión: {error}")
    finally:
        repository.close()
