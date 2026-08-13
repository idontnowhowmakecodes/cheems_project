"""Lanzador de Ventana de Escritorio para el Sistema CHEEMS usando PyWebView."""

import sys
from pathlib import Path
from typing import Optional
import webview

from cheems.ui.bridge import CheemsDesktopBridge


def launch_desktop_app(
    html_path: Optional[Path] = None,
    title: str = "CHEEMS Perú — Evaluación Clínica del Neurodesarrollo",
    width: int = 1280,
    height: int = 860,
    debug: bool = False,
) -> None:
    """Abre la aplicación en una ventana nativa de escritorio."""
    if html_path is None:
        html_path = Path(__file__).resolve().parent.parent / "frontend" / "index.html"

    if not html_path.exists():
        raise FileNotFoundError(f"No se encontró el frontend en: {html_path}")

    bridge = CheemsDesktopBridge()

    window = webview.create_window(
        title=title,
        url=str(html_path.resolve()),
        js_api=bridge,
        width=width,
        height=height,
        min_size=(960, 640),
        background_color="#0b131e",
    )

    # Iniciar ciclo de eventos de escritorio (Edge Chromium / Webview2 en Windows)
    webview.start(debug=debug)


if __name__ == "__main__":
    launch_desktop_app(debug=True)
