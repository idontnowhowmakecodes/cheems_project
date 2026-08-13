# UI (User Interface Bridge)

Este módulo conforma el Controlador Principal de la aplicación, que sirve de **Puente (Bridge)** entre el backend matemático escrito en Python y el frontend renderizado con tecnologías web.

## Componentes

- **`bridge.py`**: Interfaz de API (Clase `Bridge`) expuesta a Javascript mediante PyWebView. Expone métodos como `start_recording()`, `advance_item()`, `stop_recording()`, y la recuperación continua del fotograma de cámara base64 (`get_camera_frame()`), para que el cliente JS los invoque de forma nativa e interaccione de manera bidireccional con Python.
- Orquesta las capas de `camera`, `tracking` y la gestión de la sesión clínica en curso.
