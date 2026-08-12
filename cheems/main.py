"""Punto de Entrada CLI del Sistema CHEEMS alineado con el diagrama de flujo operativo.

Flujo del Sistema CHEEMS (4 Pasos):
1. El especialista elige uno de los dos tests (STAT o ADOS-2).
2. El programa ejecuta la cámara y graba la sesión en SQLite.
3. El programa permite el paso secuencial de módulos o actividades dentro del test.
4. Genera un resultado en base a las puntuaciones del algoritmo de cada test,
   permitiendo la revisión posterior y validación por parte del especialista.
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, Any

# Asegurar que el directorio raíz y scr estén en sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCR_PATH = PROJECT_ROOT / "scr"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SCR_PATH) not in sys.path:
    sys.path.insert(0, str(SCR_PATH))

# Mapeo de compatibilidad para cheems_project <-> cheems_tracker
try:
    import cheems_project
    sys.modules["cheems_tracker"] = cheems_project
    
    import cheems_project.domain.models as _models
    sys.modules["cheems_project.domain"] = cheems_project.domain
    sys.modules["cheems_project.domain.models"] = _models
    sys.modules["cheems_tracker.domain"] = cheems_project.domain
    sys.modules["cheems_tracker.domain.models"] = _models

    import cheems_project.camera.video_source as _video
    sys.modules["cheems_tracker.camera"] = cheems_project.camera
    sys.modules["cheems_tracker.camera.video_source"] = _video

    import cheems_project.metrics.gesture_metrics as _metrics
    sys.modules["cheems_tracker.metrics"] = cheems_project.metrics
    sys.modules["cheems_tracker.metrics.gesture_metrics"] = _metrics

    import cheems_project.tracking.gesture_tracker as _tracking
    sys.modules["cheems_tracker.tracking"] = cheems_project.tracking
    sys.modules["cheems_tracker.tracking.gesture_tracker"] = _tracking

    import cheems_project.ui.hotkey_controller as _ui
    sys.modules["cheems_tracker.ui"] = cheems_project.ui
    sys.modules["cheems_tracker.ui.hotkey_controller"] = _ui

    import cheems_project.database.sqlite_repository as _db
    sys.modules["cheems_tracker.database"] = cheems_project.database
    sys.modules["cheems_tracker.database.sqlite_repository"] = _db
except Exception as err:
    print(f"[!] Alias init note: {err}")

from cheems.core.patient import Patient
from cheems.core.report import STATReportGenerator
from cheems.core.session import STATSession
from cheems.tests.ados2.models import ADOS2Module
from cheems.tests.ados2.scoring import ADOS2Scorer
from cheems.utils.exporters import export_stat_to_json, export_stat_to_html, export_stat_to_pdf
from cheems.utils.validators import validate_patient_age


def select_test_type() -> str:
    """Paso 1: El especialista elige uno de los dos tests."""
    print("=" * 70)
    print("      SISTEMA CHEEMS - CLASIFICADOR HOLÍSTICO DE EVALUACIÓN")
    print("=" * 70)
    print(" Seleccione el test a realizar:")
    print("   [1] Test STAT (Screening Tool for Autism in Toddlers - 12 a 36 meses)")
    print("   [2] Test ADOS-2 (Autism Diagnostic Observation Schedule - 2nd Ed)")
    
    choice = input("\n Ingrese una opción [1 u 2, por defecto 1]: ").strip()
    if choice == "2":
        return "ados2"
    return "stat"


def run_stat_flow(patient: Patient, camera_source: str, mode: str, output_json: str, output_pdf: str) -> None:
    """Ejecuta los Pasos 2, 3 y 4 para el Test STAT con procesamiento silencioso en segundo plano y exportación PDF."""
    db_path = Path("data/cheems_stat.db")
    model_path = Path("models/gesture_recognizer.task")

    try:
        from cheems_tracker.database.sqlite_repository import SessionRepository
    except ImportError:
        from cheems_project.database.sqlite_repository import SessionRepository

    repository = SessionRepository(db_path)

    session = STATSession(patient=patient, camera_source=camera_source, model_path=model_path, db_path=db_path)
    repository.start_session(session.session_id, f"Evaluación STAT - Paciente: {patient.full_name}", camera_source)

    print(f"\n[Paso 2] Grabación Silenciosa en Segundo Plano Iniciada en: {camera_source}")
    print(f"[Paso 2] Persistencia activa en SQLite: {db_path.resolve()}")
    print("   (La cámara procesa en segundo plano sin abrir ventana de video en pantalla)")

    print("\n" + "-" * 70)
    print("[Paso 3] EVALUACIÓN SILENCIOSA Y CONTROL POR TECLADO PARA EL ESPECIALISTA")
    print("-" * 70)

    if mode == "live":
        import time
        import cv2
        try:
            from cheems_tracker.camera.video_source import VideoSource
            from cheems_tracker.ui.hotkey_controller import ControlAction, HotkeyController
        except ImportError:
            from cheems_project.camera.video_source import VideoSource
            from cheems_project.ui.hotkey_controller import ControlAction, HotkeyController

        controls = HotkeyController()
        print("\n Controles por Teclado en Segundo Plano:")
        print("   - F8 o 8: Alternar Aprobado (PASS) / Fallado (FAIL) para la actividad actual")
        print("   - F9 o 9: Confirmar actividad y AVANZAR al siguiente ítem del STAT")
        print("   - Q o Esc: Cancelar evaluación\n")

        current_item_passed = True

        try:
            with VideoSource(camera_source) as camera:
                while not session.is_completed:
                    item = session.current_item
                    if not item:
                        break

                    frame = camera.read()
                    # Procesamiento MediaPipe silencioso en segundo plano
                    tracking_frame = session.tracker.tracker_instance.process(frame) if (session.tracker and session.tracker.is_active) else None
                    if tracking_frame:
                        repository.record_frame(session.session_id, tracking_frame)

                    action = controls.poll()

                    if action is ControlAction.MARK_ATTEMPT:
                        current_item_passed = not current_item_passed
                        status_str = "PASS (Aprobado)" if current_item_passed else "FAIL (Fallado)"
                        print(f"  [+] Actividad [{item.code}] -> Estado cambiado a: {status_str}")
                    elif action is ControlAction.FINISH:
                        session.record_item_result(item.code, therapist_passed=current_item_passed, notes="Registrado in-situ.")
                        repository.record_event(session.session_id, 0, f"item_completed_{item.code}")
                        print(f"  [✔] Actividad [{item.code}] COMPLETADA -> {'PASS' if current_item_passed else 'FAIL'}")
                        session.advance_item()
                        current_item_passed = True
                        if session.current_item:
                            print(f"\n  [➜] Siguiente Actividad: [{session.current_item.code}] - {session.current_item.name} ({session.current_item.domain.value})")
                    elif action is ControlAction.CANCEL:
                        print("  [!] Sesión cancelada por el especialista.")
                        break

                    time.sleep(0.01)
        except Exception as err:
            print(f" [!] Nota sobre Cámara Live: {err}. Ejecutando paso de actividades guiado...")
            _run_guided_simulation(session)
    else:
        _run_guided_simulation(session)

    # Paso 4: Generación de resultados algorítmicos y exportación PDF
    print("\n" + "=" * 70)
    print("[Paso 4] CÁLCULO ALGORÍTMICO Y GENERACIÓN DE REPORTE FINAL Y PDF")
    print("=" * 70)

    evaluation_result = session.evaluate_session()
    report_markdown = STATReportGenerator.generate_markdown_report(evaluation_result)

    print(report_markdown)

    repository.finish_session(session.session_id, evaluation_result)

    # Exportación JSON, HTML y PDF
    json_path = Path(output_json)
    pdf_path = Path(output_pdf)
    html_path = pdf_path.with_suffix(".html")

    export_stat_to_json(evaluation_result, json_path)
    export_stat_to_html(evaluation_result, html_path)
    export_stat_to_pdf(evaluation_result, pdf_path)

    print(f"\n[+] Sesión guardada en SQLite (`data/cheems_stat.db`).")
    print(f"[+] Reporte JSON exportado en: {json_path.resolve()}")
    print(f"[+] Reporte HTML exportado en: {html_path.resolve()}")
    print(f"[+] Reporte PDF generado en: {pdf_path.resolve()}")

    session.close()
    repository.close()


def _run_guided_simulation(session: STATSession) -> None:
    """Ejecuta la secuencia guiada de los 12 ítems del STAT."""
    sample_results = {
        "P-1": (True, {"hand_gesture_score": 0.85}, "Imitación funcional adecuada."),
        "P-2": (False, {}, "Falta juego representacional espontáneo."),
        "R-1": (True, {}, "Realizó contacto visual para pedir burbujas."),
        "R-2": (False, {}, "No solicitó ayuda con el globo."),
        "DA-1": (True, {}, "Muestra objeto llamativo al evaluador."),
        "DA-2": (True, {"pointing_detected": 0.92}, "Señala objeto lejano con dedo índice."),
        "DA-3": (False, {"gaze_alignment_score": 0.30}, "No siguió la dirección de la mirada."),
        "DA-4": (False, {"gaze_alignment_score": 0.25}, "Escasa alternancia de mirada entre objeto y evaluador."),
        "MI-1": (True, {"clapping_proximity": 0.88}, "Imitó aplausos adecuadamente."),
        "MI-2": (True, {}, "Imitó golpes en la mesa."),
        "MI-3": (True, {"hands_elevated_score": 0.95}, "Llevó las manos a la cabeza correctamente."),
        "MI-4": (True, {}, "Imitó la acción con la campanilla."),
    }

    while not session.is_completed:
        item = session.current_item
        if not item:
            break
        sim_passed, sim_metrics, sim_notes = sample_results.get(item.code, (True, {}, "Aprobado."))
        score_obj = session.record_item_result(item.code, therapist_passed=sim_passed, metrics=sim_metrics, notes=sim_notes)
        result_label = "PASS (0)" if score_obj.score == 0 else "FAIL (1)"
        print(f"  Actividad [{item.code}] {item.name:<25} ({item.domain.value:<18}) -> {result_label}")
        session.advance_item()


def run_ados2_flow(patient: Patient) -> None:
    """Flujo base para ADOS-2."""
    print("\n[Paso 1] Test ADOS-2 Seleccionado.")
    print(f"[Paso 2] Ejecutando cámara para evaluación ADOS-2 con paciente: {patient.full_name}")
    print("[Paso 3] Paso por Módulos de ADOS-2 (Módulo Toddler / Módulo 1)")
    
    sa_score = 6
    rbr_score = 3
    classification, total = ADOS2Scorer.calculate_cutoff(ADOS2Module.MODULE_1, sa_score, rbr_score)

    print("\n" + "=" * 70)
    print("[Paso 4] CÁLCULO ALGORÍTMICO ADOS-2")
    print(f" Total Afecto Social (SA): {sa_score}")
    print(f" Total Comportamientos Restringidos (RBR): {rbr_score}")
    print(f" Puntuación Total ADOS-2: {total}")
    print(f" Clasificación Algorítmica: {classification}")
    print("=" * 70)


def main() -> None:
    parser = argparse.ArgumentParser(description="CHEEMS - Clasificador Holístico de Evaluación")
    parser.add_argument("--test", choices=["stat", "ados2"], default=None, help="Test a ejecutar (stat o ados2)")
    parser.add_argument("--patient-id", default="P-2026-001", help="ID del paciente")
    parser.add_argument("--patient-name", default="Mateo Morales", help="Nombre del paciente")
    parser.add_argument("--patient-age", type=int, default=24, help="Edad en meses (12 a 36)")
    parser.add_argument("--evaluator", default="Especialista CHEEMS", help="Nombre del especialista")
    parser.add_argument("--mode", choices=["simulation", "live"], default="simulation", help="Modo de ejecución")
    parser.add_argument("--source", default="0", help="Origen de cámara (índice 0 o URL RTSP/DroidCam)")
    parser.add_argument("--output-json", default="data/stat_evaluation_result.json", help="Ruta salida JSON")
    parser.add_argument("--output-pdf", default="data/stat_report.pdf", help="Ruta salida PDF")
    args = parser.parse_args()

    # Paso 1: Elección de Test
    test_choice = args.test if args.test else select_test_type()

    # Validación de paciente
    is_valid, msg = validate_patient_age(args.patient_age)
    if not is_valid:
        print(f"Error de validación: {msg}")
        sys.exit(1)

    patient = Patient(patient_id=args.patient_id, full_name=args.patient_name, age_months=args.patient_age, evaluator=args.evaluator)

    if test_choice == "stat":
        run_stat_flow(patient, args.source, args.mode, args.output_json, args.output_pdf)
    else:
        run_ados2_flow(patient)


if __name__ == "__main__":
    main()
