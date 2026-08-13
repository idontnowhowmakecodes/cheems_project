# Proyecto CHEEMS: Sistema de Asistencia Clínica (ADOS-2 y STAT)

CHEEMS es una aplicación de escritorio diseñada para asistir a especialistas (psicólogos, psiquiatras, terapeutas) en la evaluación de conductas relacionadas con el espectro autista mediante los protocolos estandarizados ADOS-2 y STAT. 

El sistema utiliza algoritmos de **Visión Artificial e Inteligencia Artificial (MediaPipe)** para analizar de forma pasiva y en tiempo real el comportamiento del paciente a través de una cámara, generando estimaciones sobre el contacto visual, señalamiento y movimientos atípicos (estereotipias), proporcionando un reporte objetivo para el especialista.

> **Importante:** CHEEMS es una herramienta de asistencia clínica. Los resultados arrojados por el sistema **no constituyen un diagnóstico médico** y siempre requieren la supervisión, validación y juicio clínico de un profesional capacitado.

---

## 🚀 Características Principales

- **Interfaz Minimalista y Amigable:** Diseñada en tecnologías web (HTML/JS/CSS) utilizando `pywebview` para crear una aplicación de escritorio nativa sin distracciones, ideal para entornos pediátricos.
- **Evaluaciones Estandarizadas:** Soporte nativo para flujos de evaluación de las pruebas ADOS-2 y STAT, ítem por ítem.
- **Seguimiento Biométrico (MediaPipe):**
  - **Contacto Visual:** Calcula la alineación de la mirada hacia el rostro del evaluador.
  - **Gesto de Señalamiento:** Detecta si el paciente realiza gestos de apuntar con el dedo índice.
  - **Movimientos Atípicos:** Detecta automáticamente estereotipias como *Flapping* (aleteo de manos) y *Rocking* (balanceo del tronco).
- **IA Sugerente en Tiempo Real:** Mientras el terapeuta evalúa, la IA recopila datos durante la actividad y propone un veredicto (PASS/FAIL) de forma objetiva basado en métricas.
- **Revisión y Ajuste Clínico:** El especialista puede ver grabaciones de la sesión, revisar las sugerencias de la IA y sobrescribir el veredicto añadiendo sus propias notas antes de la emisión del informe.
- **Reportes Automáticos:** Generación de reportes clínicos profesionales en PDF con los resultados.

---

## ⚙️ Tecnologías Utilizadas

- **Backend / Core:** Python 3.11+
- **Interfaz Gráfica:** PyWebView (con HTML5, CSS3, JavaScript Vainilla)
- **Motor de Visión Artificial:** Google MediaPipe (Tasks API - Face Landmarker, Pose Landmarker) y OpenCV.
- **Base de Datos:** SQLite (para persistencia de pacientes y sesiones).

---

## 📁 Estructura del Proyecto

El código fuente está modularizado en las siguientes carpetas dentro de `cheems/`:

- `activities/`: Lógica para gestionar el flujo específico de cada test (ADOS-2, STAT).
- `camera/`: Control, hilos y acceso a las cámaras del sistema de forma fluida.
- `core/`: Configuración global y orquestación del flujo principal.
- `database/`: Conexión y repositorios para la base de datos SQLite.
- `domain/`: Modelos de datos del dominio (Paciente, Sesión, Item, etc.).
- `frontend/`: Todo el código de la interfaz gráfica (HTML, JS, CSS, assets).
- `metrics/`: Lógica matemática y algorítmica para extraer métricas a partir de los puntos (landmarks) de MediaPipe.
- `reports/`: Generación de informes en formato PDF (borradores y finales).
- `security/`: Funciones para anonimización y protección de datos.
- `tracking/`: Procesador principal de visión (MediaPipeProcessor), acumulación de métricas en ventanas de tiempo y evaluador sugerente de IA (AiSuggester).
- `ui/`: Controlador puente (Bridge) que conecta el Backend de Python con el Frontend de Javascript a través de PyWebView.
- `utils/`: Utilidades generales.

---

## 💻 Ejecución del Proyecto

### Opción A: Ejecutable Precompilado (Recomendado)

Para usuarios que solo desean usar la aplicación sin instalar Python:
1. Ve a la sección de **[Releases](https://github.com/idontnowhowmakecodes/cheems_project/releases)** en GitHub.
2. Descarga el archivo comprimido más reciente (`CHEEMS_Clinico.zip` o similar).
3. Descomprime el archivo y ejecuta `CHEEMS_Clinico.exe`. ¡No requiere instalación!

### Opción B: Desde el Código Fuente (Desarrolladores)

1. Clona el repositorio e instala las dependencias.
2. Asegúrate de tener los modelos de MediaPipe (`.task`) guardados en la carpeta `models/` en la raíz del proyecto.
3. Ejecuta la aplicación desde la raíz del proyecto:

```powershell
python -m cheems.main
```

---

## 📖 Flujo de Uso (Workflow)

1. **Creación/Selección de Paciente:** Iniciar el sistema e ingresar los datos del paciente y el tipo de test a aplicar (ADOS-2 o STAT).
2. **Registro de Ítems:** El sistema guiará al especialista por cada ítem (ej. "Juego con objetos", "Respuesta al nombre"). Durante la actividad, el video se graba y la IA extrae información métrica.
3. **Revisión del Especialista:** Al presionar "Finalizar Actividad", se presenta un modal con la sugerencia de la IA, los promedios matemáticos y un área para que el especialista tome su decisión final e ingrese observaciones clínicas.
4. **Finalización:** Una vez completados todos los ítems de la sesión o si se cancela anticipadamente, se genera un reporte PDF (con opción a anonimización) y se guardan las métricas en la base de datos.
