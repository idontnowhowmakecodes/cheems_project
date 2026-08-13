# -*- mode: python ; coding: utf-8 -*-
"""Especificación de PyInstaller para compilar el ejecutable CHEEMS en Windows."""

import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Rutas del proyecto
project_root = os.path.abspath(".")
frontend_dir = os.path.join(project_root, "cheems", "frontend")
models_dir = os.path.join(project_root, "models")

# Archivos de datos a empaquetar
datas = [
    (frontend_dir, os.path.join("cheems", "frontend")),
]

if os.path.exists(models_dir):
    datas.append((models_dir, "models"))

# Recolectar datos adicionales de paquetes
datas += collect_data_files("mediapipe")
datas += collect_data_files("cryptography")

# Hidden imports necesarios para PyWebView y backend
hiddenimports = [
    "webview",
    "webview.platforms.winforms",
    "webview.platforms.edgechromium",
    "cryptography",
    "cryptography.hazmat.primitives.ciphers.aead",
    "cheems",
    "cheems.core",
    "cheems.core.session",
    "cheems.core.ados2_session",
    "cheems.core.patient",
    "cheems.core.report",
    "cheems.database.sqlite_repository",
    "cheems.security.crypto",
    "cheems.tracking.stat_tracker",
    "cheems.tracking.gesture_tracker",
    "cheems.tests.stat.scoring",
    "cheems.tests.ados2.scoring",
    "cheems.tests.ados2.css",
    "cheems.ui.app_window",
    "cheems.ui.bridge",
]
hiddenimports += collect_submodules("cheems")

a = Analysis(
    ["cheems/main.py"],
    pathex=[project_root],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "IPython", "jupyter"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CHEEMS_Clinico",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Modo ventana de escritorio limpia (sin consola negra de fondo)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="CHEEMS_Clinico",
)
