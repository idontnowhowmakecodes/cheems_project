# Tracking

Este módulo es el núcleo del Procesamiento de Visión Artificial e Inteligencia Artificial Asistida de la aplicación.

## Componentes principales

- **MediaPipeProcessor**: Clase central (usualmente en `mediapipe_processor.py`) que carga e invoca los modelos nativos en TFLite de MediaPipe Tasks API (por ej. `FaceLandmarker`, `PoseLandmarker`). Se encarga de procesar un fotograma (frame), detectar los *landmarks* anatómicos, y calcular las métricas puras fotograma a fotograma (alineación de cara, visibilidad de brazos).
- **MetricsAccumulator**: Módulo (`metrics_accumulator.py`) que recibe las métricas instantáneas por fotograma y las almacena en una memoria circular continua (ej. últimos 90 fotogramas). Es responsable de calcular estadísticas y promedios matemáticos estables en el tiempo para descartar ruidos.
- **AiSuggester**: Clase (`ai_suggester.py`) encargada de aplicar reglas lógicas y heurísticas clínicas sobre los promedios matemáticos generados, traduciendo porcentajes de atención y métricas motoras a un veredicto sugerido final de PASS/FAIL (pasa/no pasa), que se presentará en la UI al especialista.
