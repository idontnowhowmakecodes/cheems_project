# Camera

Este módulo gestiona la captura y procesamiento inicial del flujo de video desde dispositivos físicos (cámaras web, DroidCam, u otras fuentes compatibles).

## Responsabilidades
- Abrir, leer y cerrar *streams* de video usando OpenCV (`cv2.VideoCapture`).
- Procesamiento en hilos separados (multithreading) para no bloquear la interfaz gráfica principal de la aplicación.
- Re-conexión y manejo seguro de errores ante desconexiones de hardware.
- (Opcional) Escritura concurrente a archivos de video para la revisión posterior.
