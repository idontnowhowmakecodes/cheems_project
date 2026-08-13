"""Configuración centralizada y persistente del sistema CHEEMS."""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class AppSettings:
    """Configuraciones del sistema, rutas de almacenamiento y fuentes de video."""

    camera_source: str = "0"
    camera_sources: List[Dict[str, str]] = field(
        default_factory=lambda: [
            {"name": "DroidCam Móvil", "url": "http://192.168.1.122:4747/video"},
            {"name": "Raspberry Pi Zero 2W (Stream 1)", "url": "http://192.168.1.139:4747/video"},
            {"name": "Raspberry Pi Zero 2W (RTSP)", "url": "rtsp://192.168.1.50:8554/stream"},
            {"name": "Cámara Integrada / USB (0)", "url": "0"},
            {"name": "Cámara Externa (1)", "url": "1"},
        ]
    )
    recordings_dir: str = "data/recordings"
    provisional_reports_dir: str = "data/reports/provisional"
    final_reports_dir: str = "data/reports/final"
    database_path: str = "data/cheems_medical.db"
    model_path: str = "models/gesture_recognizer.task"

    @classmethod
    def load(cls, config_file: Path = Path("data/settings.json")) -> "AppSettings":
        """Carga la configuración desde un archivo JSON local o retorna defaults."""
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            except Exception as err:
                print(f"[!] Error al cargar settings.json ({err}), usando valores predeterminados.")
        
        settings = cls()
        settings.save(config_file)
        return settings

    def save(self, config_file: Path = Path("data/settings.json")) -> None:
        """Guarda la configuración actual en formato JSON."""
        config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)

    def to_dict(self) -> Dict[str, Any]:
        """Convierte la configuración a un diccionario."""
        return asdict(self)
