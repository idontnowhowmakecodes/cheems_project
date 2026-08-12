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

# Las inyecciones sys.modules (compatibilidad cheems_tracker -> cheems_project)
# han sido eliminadas tras la unificación en Fase 3.

from cheems.core.patient import Patient
from cheems.core.report import STATReportGenerator, ADOS2ReportGenerator
from cheems.core.session import STATSession
from cheems.core.ados2_session import ADOS2Session
from cheems.tests.ados2.models import ADOS2Module, ADOS2SubAlgorithm
from cheems.utils.exporters import export_stat_to_html, export_stat_to_json, export_stat_to_pdf, export_ados2_to_json
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
        from cheems.database.sqlite_repository import SessionRepository
    except ImportError:
        from cheems.database.sqlite_repository import SessionRepository

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
            from cheems.camera.video_source import VideoSource
            from cheems.ui.hotkey_controller import ControlAction, HotkeyController
        except ImportError:
            from cheems.camera.video_source import VideoSource
            from cheems.ui.hotkey_controller import ControlAction, HotkeyController

        controls = HotkeyController()
        print("\n Controles por Teclado en Segundo Plano:")
        print("   - F7 o 7: Marcar ítem actual como FAIL (Fallado)")
        print("   - F8 o 8: Marcar ítem actual como PASS (Aprobado)")
        print("   - F9 o 9: Confirmar actividad y AVANZAR al siguiente ítem del STAT")
        print("   - Q o Esc: Cancelar evaluación\n")

        current_item_verdict = None

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

                    if action is ControlAction.MARK_PASS:
                        current_item_verdict = True
                        print(f"  [+] Actividad [{item.code}] -> Estado marcado como: PASS (Aprobado)")
                    elif action is ControlAction.MARK_FAIL:
                        current_item_verdict = False
                        print(f"  [+] Actividad [{item.code}] -> Estado marcado como: FAIL (Fallado)")
                    elif action is ControlAction.FINISH:
                        if current_item_verdict is None:
                            print("  [!] Debe marcar PASS (F8/8) o FAIL (F7/7) antes de avanzar.")
                            continue
                            
                        session.record_item_result(item.code, therapist_passed=current_item_verdict, notes="Registrado in-situ.")
                        repository.record_event(session.session_id, 0, f"item_completed_{item.code}")
                        print(f"  [✔] Actividad [{item.code}] COMPLETADA -> {'PASS' if current_item_verdict else 'FAIL'}")
                        session.advance_item()
                        current_item_verdict = None
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


def run_ados2_flow(patient: Patient, output_json: str) -> None:
    """Flujo base para ADOS-2 (Simulación)."""
    print("\n[Paso 1] Test ADOS-2 Seleccionado.")
    print(f"[Paso 2] Ejecutando ADOS-2 (Modo Simulación) con paciente: {patient.full_name}")
    
    # Elegir módulo y sub-algoritmo (Hardcoded para MVP)
    module = ADOS2Module.MODULE_1
    sub_algo = ADOS2SubAlgorithm.M1_SOME_WORDS
    if patient.age_months < 31:
        module = ADOS2Module.TODDLER
        sub_algo = ADOS2SubAlgorithm.TODDLER_21_30_SOME
        
    print(f"[Paso 3] Módulo seleccionado: {module.value}, Sub-algoritmo: {sub_algo.value}")
    
    session = ADOS2Session(patient=patient, module=module, sub_algorithm=sub_algo)
    
    # Simulamos la evaluación de los ítems
    import random
    while not session.is_completed:
        item = session.current_item
        if not item:
            break
        # Generar código simulado (0, 1, 2, 3, 7, 8)
        sim_code = random.choices([0, 1, 2, 3, 7, 8], weights=[0.4, 0.2, 0.2, 0.1, 0.05, 0.05])[0]
        session.record_item_result(item.code, raw_code=sim_code, notes="Simulado.")
        print(f"  Actividad [{item.code}] {item.name:<30} -> Puntuación Original: {sim_code}")
        session.advance_item()

    print("\n" + "=" * 70)
    print("[Paso 4] CÁLCULO ALGORÍTMICO Y REPORTE ADOS-2")
    print("=" * 70)
    
    evaluation_result = session.evaluate_session()
    report_markdown = ADOS2ReportGenerator.generate_markdown_report(evaluation_result)
    print(report_markdown)
    
    json_path = Path(output_json).with_name("ados2_evaluation_result.json")
    export_ados2_to_json(evaluation_result, json_path)
    print(f"\n[+] Reporte JSON exportado en: {json_path.resolve()}")


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

    patient = Patient(patient_id=args.patient_id, full_name=args.patient_name, age_months=args.patient_age, evaluator=args.evaluator)

    # Validación de paciente
    is_valid, msg = patient.validate_for_test(test_choice)
    if not is_valid:
        print(f"Error de validación: {msg}")
        sys.exit(1)

    if test_choice == "stat":
        run_stat_flow(patient, args.source, args.mode, args.output_json, args.output_pdf)
    else:
        run_ados2_flow(patient, args.output_json)


if __name__ == "__main__":
    main()
