# cheems_project Perú — MVP etapa 1

Esta etapa registra una actividad de gestos de manos con MediaPipe y DroidCam.
Los resultados son métricas descriptivas de landmarks y no constituyen diagnóstico
ni reemplazan la evaluación de un profesional.

## Ejecución

```powershell
cd C:\Users\jose1\Documents\Codex\2026-08-04\qu\outputs\cheems_project_peru
& "C:\Users\jose1\AppData\Local\Programs\Python\Python311\python.exe" -m pip install -e .
& "C:\Users\jose1\AppData\Local\Programs\Python\Python311\python.exe" -m cheems_project --instruction "Imita el gesto indicado por el terapeuta"
```

Controles durante la vista previa:

- `F7` o `7`: iniciar y comenzar a guardar datos.
- `F8` o `8`: marcar un intento observado por el terapeuta.
- `F9` o `9`: finalizar y guardar la sesión.
- `Q` o `Esc`: cancelar; si aún no inició, no se guarda ningún dato.

Las sesiones se guardan en `data/cheems_project.db`.

## Reportes

Después de finalizar una sesión, genera su panel PNG con:

```powershell
& "C:\Users\jose1\AppData\Local\Programs\Python\Python311\python.exe" -m cheems_project.reports
```

El comando usa la sesión terminada más reciente y guarda el reporte en `reports/`.
Para una sesión específica usa `--session-id <UUID>`.

## Arquitectura

- `camera`: adquisición de video.
- `tracking`: adaptadores de MediaPipe.
- `metrics`: cálculos sobre landmarks.
- `activities`: flujo de una actividad guiada.
- `database`: persistencia SQLite.
- `domain`: modelos de datos independientes de la interfaz.

La interfaz PySide6 se añadirá en una etapa posterior sin cambiar estas capas.
