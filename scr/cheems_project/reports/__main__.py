"""Comando para generar reportes PNG desde la base SQLite."""

import argparse
from pathlib import Path

from cheems_project.config import default_config
from cheems_project.database.sqlite_repository import SessionRepository
from cheems_project.reports.gesture_report import GestureSessionReport


def parse_arguments() -> argparse.Namespace:
    """Lee la sesión elegida y la ruta opcional de salida."""
    parser = argparse.ArgumentParser(description="Genera un reporte de sesión cheems_project")
    parser.add_argument("--session-id", help="UUID de una sesión guardada")
    parser.add_argument("--output", type=Path, help="Ruta del archivo PNG de salida")
    return parser.parse_args()


def main() -> None:
    """Genera el reporte de la última sesión o de un UUID indicado."""
    arguments = parse_arguments()
    config = default_config("")
    repository = SessionRepository(config.database_path)
    try:
        session_id = arguments.session_id or repository.latest_session_id()
        session, observations, events = repository.load_report_data(session_id)
        output_path = arguments.output or (
            config.project_dir / "reports" / f"sesion_{session_id}.png"
        )
        generated_path = GestureSessionReport().generate(
            session,
            observations,
            events,
            output_path,
        )
        print(f"Reporte generado: {generated_path}")
    except LookupError as error:
        print(f"No se pudo generar el reporte: {error}")
    finally:
        repository.close()


if __name__ == "__main__":
    main()
