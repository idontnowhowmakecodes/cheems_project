"""Configuración centralizada del MVP."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    """Define rutas locales y origen de video para la aplicación."""

    camera_url: str
    project_dir: Path

    @property
    def model_path(self) -> Path:
        """Devuelve la ruta del modelo oficial de reconocimiento de gestos."""
        return self.project_dir / "models" / "gesture_recognizer.task"

    @property
    def database_path(self) -> Path:
        """Devuelve la ruta de la base de datos SQLite de sesiones."""
        return self.project_dir / "data" / "cheems_project.db"


def default_config(camera_url: str) -> AppConfig:
    """Crea la configuración predeterminada para una fuente de cámara."""
    project_dir = Path(__file__).resolve().parents[2]
    return AppConfig(camera_url=camera_url, project_dir=project_dir)
