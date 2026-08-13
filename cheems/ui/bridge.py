"""Bridge API entre JavaScript (PyWebView) y los motores clínicos de CHEEMS."""

import base64
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional
import cv2
import numpy as np
import webview

from cheems.camera.threaded_camera import CameraPool, ThreadedCamera
from cheems.config import AppSettings
from cheems.core.patient import Patient
from cheems.core.session import STATSession
from cheems.core.ados2_session import ADOS2Session
from cheems.database.sqlite_repository import SessionRepository
from cheems.tests.ados2.models import ADOS2Module, ADOS2SubAlgorithm
from cheems.utils.exporters import export_stat_to_html, export_stat_to_json, export_stat_to_pdf, export_ados2_to_json
from cheems.tracking.mediapipe_processor import MediaPipeProcessor
from cheems.tracking.metrics_accumulator import MetricsAccumulator
from cheems.tracking.ai_suggester import AISuggestionEngine


class CheemsDesktopBridge:
    """Controlador API expuesto a la interfaz web mediante PyWebView."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.settings = AppSettings.load()
        self.db_path = db_path or Path(self.settings.database_path)
        self.repository = SessionRepository(self.db_path)
        self.active_session: Optional[Any] = None
        self.active_patient: Optional[Patient] = None

        # Camera pool — manages analysis + context cameras
        self.camera_pool: CameraPool = CameraPool()
        # Legacy single-camera reference kept for backward compat with _open_camera
        self.threaded_cam: Optional[ThreadedCamera] = None

        self.current_camera_source: str = self.settings.camera_source
        self.test_type: Optional[str] = None
        self.last_evaluation: Optional[Dict[str, Any]] = None

        # New biometry stack
        self.mp_processor: Optional[MediaPipeProcessor] = None
        self.accumulator: MetricsAccumulator = MetricsAccumulator()
        self.ai_suggester: AISuggestionEngine = AISuggestionEngine()

    def get_settings(self) -> Dict[str, Any]:
        """Obtiene la configuración actual del sistema."""
        return self.settings.to_dict()

    def save_settings(self, new_settings: Dict[str, Any]) -> Dict[str, Any]:
        """Actualiza y persiste las configuraciones de rutas e IP de cámara."""
        try:
            if "camera_source" in new_settings:
                self.settings.camera_source = str(new_settings["camera_source"]).strip()
            if "camera_sources" in new_settings and isinstance(new_settings["camera_sources"], list):
                self.settings.camera_sources = new_settings["camera_sources"]
            if "recordings_dir" in new_settings:
                self.settings.recordings_dir = str(new_settings["recordings_dir"]).strip()
            if "provisional_reports_dir" in new_settings:
                self.settings.provisional_reports_dir = str(new_settings["provisional_reports_dir"]).strip()
            if "final_reports_dir" in new_settings:
                self.settings.final_reports_dir = str(new_settings["final_reports_dir"]).strip()

            self.settings.save()
            return {"success": True, "message": "Configuración guardada correctamente."}
        except Exception as err:
            return {"success": False, "message": f"Error al guardar configuración: {err}"}

    def add_camera_source(self, name: str, url: str) -> Dict[str, Any]:
        """Agrega una nueva cámara / IP al catálogo persistente."""
        name = name.strip() or "Cámara IP"
        url = url.strip()
        if not url:
            return {"success": False, "message": "Debe especificar una URL o índice de cámara."}

        for cam in self.settings.camera_sources:
            if cam.get("url") == url:
                cam["name"] = name
                self.settings.save()
                return {"success": True, "message": "Cámara actualizada en la lista.", "sources": self.settings.camera_sources}

        self.settings.camera_sources.append({"name": name, "url": url})
        self.settings.save()
        return {"success": True, "message": "Cámara agregada con éxito.", "sources": self.settings.camera_sources}

    def remove_camera_source(self, url: str) -> Dict[str, Any]:
        """Elimina una cámara del catálogo persistente."""
        url = url.strip()
        self.settings.camera_sources = [c for c in self.settings.camera_sources if c.get("url") != url]
        self.settings.save()
        return {"success": True, "message": "Cámara eliminada.", "sources": self.settings.camera_sources}

    def scan_camera_sources(self) -> Dict[str, Any]:
        """Escanea concurrentemente las cámaras guardadas y devuelve cuáles están conectadas y cuál preseleccionar."""
        sources = self.settings.camera_sources
        results: List[Dict[str, Any]] = []

        def check_one(cam_info: Dict[str, str]) -> Dict[str, Any]:
            url = cam_info.get("url", "0")
            name = cam_info.get("name", "Cámara")
            test_res = self._quick_check_source(url)
            return {
                "name": name,
                "url": url,
                "connected": test_res["connected"],
                "resolution": test_res.get("resolution", ""),
                "status_text": "Conectada" if test_res["connected"] else "No responde",
            }

        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(check_one, sources))

        # Encontrar la primera disponible
        auto_selected = None
        for res in results:
            if res["connected"]:
                auto_selected = res["url"]
                break

        if auto_selected is None and len(results) > 0:
            auto_selected = results[0]["url"]

        return {
            "sources": results,
            "auto_selected_url": auto_selected,
        }

    def _quick_check_source(self, source: str) -> Dict[str, Any]:
        """Verificación rápida de conexión sin bloquear la interfaz."""
        target = str(source).strip()
        
        # Pre-check TCP para streams de red (evita bloqueo FFmpeg de 30s)
        if target.startswith("http://") or target.startswith("https://") or target.startswith("rtsp://"):
            import socket
            from urllib.parse import urlparse
            try:
                parsed = urlparse(target)
                host = parsed.hostname
                port = parsed.port or (443 if target.startswith("https") else 80)
                if host:
                    with socket.create_connection((host, port), timeout=0.3):
                        pass
            except Exception:
                return {"connected": False}

        cam = ThreadedCamera(target)
        if not cam.start():
            return {"connected": False}

        t0 = time.time()
        has_frame = False
        res_str = ""
        while time.time() - t0 < 1.2:
            ok, f = cam.get_latest_frame()
            if ok and f is not None:
                has_frame = True
                h, w, _ = f.shape
                res_str = f"{w}x{h}"
                break
            time.sleep(0.05)

        cam.stop()
        return {"connected": has_frame, "resolution": res_str}

    def select_folder(self, title: str = "Seleccionar Carpeta") -> Dict[str, Any]:
        """Abre un diálogo interactivo nativo de Windows para seleccionar un directorio."""
        try:
            if webview.windows and len(webview.windows) > 0:
                result = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
                if result and len(result) > 0:
                    return {"success": True, "path": str(Path(result[0]).resolve())}
        except Exception as err:
            print(f"[!] PyWebView folder dialog note: {err}")

        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            folder = filedialog.askdirectory(title=title)
            root.destroy()
            if folder:
                return {"success": True, "path": str(Path(folder).resolve())}
        except Exception as err2:
            print(f"[!] Tkinter folder dialog fallback note: {err2}")

        return {"success": False, "path": None}

    def test_camera_connection(self, source: Optional[str] = None) -> Dict[str, Any]:
        """Prueba la conexión a una cámara local o IP (DroidCam / Raspberry Pi / RTSP)."""
        target = source if source is not None else self.settings.camera_source
        target = str(target).strip()

        cam = ThreadedCamera(target)
        success = cam.start()
        if not success:
            return {
                "connected": False,
                "error": f"No se pudo conectar a: {target}. Verifique la red o que DroidCam / Raspberry Pi esté activo.",
            }

        t0 = time.time()
        has_frame = False
        frame_shape = None
        while time.time() - t0 < 2.5:
            ok, f = cam.get_latest_frame()
            if ok and f is not None:
                has_frame = True
                frame_shape = f.shape
                break
            time.sleep(0.05)

        cam.stop()

        if has_frame and frame_shape:
            h, w, _ = frame_shape
            return {
                "connected": True,
                "message": f"Conexión exitosa. Señal de video activa ({w}x{h} px).",
                "resolution": f"{w}x{h}",
            }
        else:
            return {
                "connected": False,
                "error": f"La cámara {target} respondió pero no entregó cuadros de video a tiempo.",
            }

    def start_session(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Inicia una sesión clínica de evaluación (STAT o ADOS-2)."""
        try:
            patient_id = config.get("patient_id", "P-001")
            patient_name = config.get("patient_name", "Paciente")
            age_months = int(config.get("patient_age", 24))
            evaluator = config.get("evaluator", "Especialista")
            test_type = config.get("test_type", "stat")
            camera_source = config.get("camera_source", self.settings.camera_source)
            self.current_camera_source = str(camera_source).strip()

            # 1. Guardar paciente en BD con cifrado
            self.repository.save_patient(patient_id, patient_name, age_months, evaluator)

            patient = Patient(
                patient_id=patient_id,
                full_name=patient_name,
                age_months=age_months,
                evaluator=evaluator,
            )
            self.active_patient = patient
            self.test_type = test_type

            # Abrir cámara antes de inicializar MediaPipe (así _close_camera no destruye la instancia nueva)
            self._open_camera(self.current_camera_source)

            # Iniciar Motor de Visión MediaPipe
            models_dir = Path(__file__).resolve().parents[2] / "models"
            self.mp_processor = MediaPipeProcessor(
                models_dir=models_dir,
                draw_landmarks=True,
            )
            self.accumulator.reset_item()

            # 2. Inicializar orquestador según el test
            if test_type == "stat":
                self.active_session = STATSession(
                    patient=patient,
                    camera_source=self.current_camera_source,
                    db_path=self.db_path,
                )
            else:
                # ADOS-2
                module_str = config.get("module", "Módulo 1")
                module_enum = ADOS2Module.MODULE_1
                if "Toddler" in module_str:
                    module_enum = ADOS2Module.TODDLER
                elif "2" in module_str:
                    module_enum = ADOS2Module.MODULE_2

                sub_algo_enum = ADOS2SubAlgorithm.M1_SOME_WORDS
                if module_enum == ADOS2Module.TODDLER:
                    sub_algo_enum = ADOS2SubAlgorithm.TODDLER_21_30_SOME

                self.active_session = ADOS2Session(
                    patient=patient,
                    module=module_enum,
                    sub_algorithm=sub_algo_enum,
                    camera_source=self.current_camera_source,
                )

            # Registrar cámaras de contexto si hay configuradas
            for cam_cfg in self.settings.camera_sources[1:3]:
                url = cam_cfg.get("url", "")
                if url and url != self.current_camera_source:
                    self.camera_pool.add_context_camera(url)

            curr_item = self.active_session.current_item
            item_data = None
            if curr_item:
                item_data = {
                    "code": curr_item.code,
                    "name": curr_item.name,
                    "domain": curr_item.domain.value if hasattr(curr_item.domain, "value") else str(curr_item.domain),
                    "instruction": getattr(curr_item, "instruction", "Evaluar conducta del paciente según el protocolo."),
                }

            return {
                "success": True,
                "session_id": self.active_session.session_id,
                "current_item": item_data,
                "camera_connected": self.threaded_cam.is_connected if self.threaded_cam else False,
            }
        except Exception as err:
            return {"success": False, "error": str(err)}

    def start_recording(self) -> Dict[str, Any]:
        """Inicia la grabación en todas las cámaras activas."""
        if not self.active_session:
            return {"success": False, "error": "No hay sesión activa."}
        try:
            out_dir = Path(self.settings.recordings_dir)
            session_id = self.active_session.session_id
            self.camera_pool.start_all_recordings(session_id, str(out_dir))
            # Compatibilidad con threaded_cam simple
            if self.threaded_cam and not self.camera_pool.analysis_cam:
                from cheems.camera.threaded_camera import VideoSessionRecorder
                out_path = out_dir / f"{session_id}_frontal.mp4"
                out_dir.mkdir(parents=True, exist_ok=True)
                self.threaded_cam.recorder = VideoSessionRecorder(str(out_path))
                self.threaded_cam.recorder.start()
            return {"success": True, "message": "Grabación iniciada."}
        except Exception as err:
            return {"success": False, "error": str(err)}

    def stop_recording(self) -> Dict[str, Any]:
        """Detiene la grabación en todas las cámaras."""
        segments = self.camera_pool.stop_all_recordings()
        if self.threaded_cam and self.threaded_cam.recorder:
            self.threaded_cam.recorder.stop()
        return {"success": True, "segments": segments}

    def pause_recording(self) -> Dict[str, Any]:
        """Pausa la grabación sin cerrar los archivos."""
        self.camera_pool.pause_all_recordings()
        if self.threaded_cam and self.threaded_cam.recorder:
            self.threaded_cam.recorder.pause()
        return {"success": True, "status": "pausada"}

    def resume_recording(self) -> Dict[str, Any]:
        """Reanuda la grabación tras una pausa."""
        self.camera_pool.resume_all_recordings()
        if self.threaded_cam and self.threaded_cam.recorder:
            self.threaded_cam.recorder.resume()
        return {"success": True, "status": "grabando"}

    def cut_recording(self) -> Dict[str, Any]:
        """Corta el segmento actual y abre uno nuevo en todas las cámaras."""
        closed = self.camera_pool.cut_all_segments()
        return {"success": True, "closed_segments": closed}

    def get_recording_status(self) -> Dict[str, Any]:
        """Estado actual de la grabación por cámara."""
        status = self.camera_pool.recording_status()
        if self.threaded_cam and self.threaded_cam.recorder:
            status["analysis"] = self.threaded_cam.recorder.status
        return {"recording_status": status}

    def get_final_ai_verdict(self) -> Dict[str, Any]:
        """Obtiene el veredicto final de la IA acumulado para el ítem actual."""
        if not self.active_session or not self.active_session.current_item:
            return {}

        if not self.mp_processor or not self.mp_processor.is_ready:
            return {}

        final_stats = self.accumulator.get_final_stats()
        verdict = self.ai_suggester.evaluate_final(
            self.active_session.current_item.code, final_stats
        )
        return verdict

    def advance_item(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Registra el veredicto del ítem actual y avanza secuencialmente."""
        if not self.active_session:
            return {"completed": True, "error": "No hay sesión activa"}

        item = self.active_session.current_item
        if not item:
            eval_res = self.active_session.evaluate_session()
            return {"completed": True, "evaluation": eval_res}

        passed = data.get("passed", True)

        # Obtener el veredicto FINAL de la IA antes de guardar
        final_ai_verdict: Optional[Dict[str, Any]] = None
        if self.mp_processor and self.mp_processor.is_ready:
            final_stats = self.accumulator.get_final_stats()
            final_ai_verdict = self.ai_suggester.evaluate_final(
                item.code, final_stats
            )

        ai_passed = data.get("ai_passed", None)
        # Usar veredicto final de IA si está disponible y no fue sobreescrito manualmente
        if final_ai_verdict and final_ai_verdict.get("suggested_verdict") is not None:
            ai_passed = final_ai_verdict["suggested_verdict"]

        ai_str = "PASS" if ai_passed else "FAIL" if ai_passed is not None else "N/A"

        # Construir notas enriquecidas con métricas finales
        base_notes = data.get("notes", "")
        reasoning = final_ai_verdict.get("reasoning", "") if final_ai_verdict else ""
        notes = f"[IA Sugirió: {ai_str}] {base_notes}".strip()
        if reasoning:
            notes += f" | {reasoning}"

        # Reiniciar acumulador para el siguiente ítem
        self.accumulator.reset_item()
        if self.mp_processor:
            self.mp_processor.reset_state()


        if self.test_type == "stat":
            self.active_session.record_item_result(
                item_code=item.code,
                therapist_passed=passed,
                notes=notes,
            )
        else:
            raw_code = 0 if passed else 2
            self.active_session.record_item_result(
                item_code=item.code,
                raw_code=raw_code,
                notes=notes,
            )

        is_finished = self.active_session.advance_item()

        if is_finished:
            # Guardar ruta de grabación en el resultado
            rec_segments = self.camera_pool.stop_all_recordings()
            if self.threaded_cam and self.threaded_cam.recorder:
                self.threaded_cam.recorder.stop()

            eval_res = self.active_session.evaluate_session()
            # Añadir rutas de grabación para el reproductor pre-informe
            out_dir = Path(self.settings.recordings_dir)
            session_id = self.active_session.session_id
            eval_res["recording_path"] = str(out_dir / f"{session_id}_frontal.mp4")
            eval_res["recording_segments"] = rec_segments
            self.last_evaluation = eval_res
            self.repository.finish_session(self.active_session.session_id, eval_res)
            self._close_camera()
            return {"completed": True, "evaluation": eval_res}
        else:
            next_item = self.active_session.current_item
            return {
                "completed": False,
                "next_item": {
                    "code": next_item.code,
                    "name": next_item.name,
                    "domain": next_item.domain.value if hasattr(next_item.domain, "value") else str(next_item.domain),
                    "instruction": getattr(next_item, "instruction", "Evaluar conducta del paciente según el protocolo."),
                },
            }

    def get_camera_frame(self) -> Dict[str, Any]:
        """Captura el frame más reciente, procesa y devuelve Base64 con estado de conexión real."""
        if not self.threaded_cam:
            return {
                "connected": False,
                "image_b64": None,
                "message": "Sin cámara conectada / Reconectando...",
                "metrics": {},
            }

        is_ok, frame = self.threaded_cam.get_latest_frame()
        if not is_ok or frame is None:
            return {
                "connected": False,
                "image_b64": None,
                "message": "Sin señal de video de la cámara.",
                "metrics": {},
            }

        # Obtener frame de la cámara de análisis
        is_ok, frame = (False, None)
        if self.camera_pool.analysis_cam:
            is_ok, frame = self.camera_pool.get_analysis_frame()
        elif self.threaded_cam:
            is_ok, frame = self.threaded_cam.get_latest_frame()

        if not is_ok or frame is None:
            return {
                "connected": False,
                "image_b64": None,
                "message": "Sin señal de video de la cámara.",
                "metrics": {},
            }

        try:
            metrics: Dict[str, float] = {}
            ai_suggestion: Optional[Dict[str, Any]] = None

            # ── Procesamiento MediaPipe ────────────────────────────────────
            if self.mp_processor and self.mp_processor.is_ready:
                processed = self.mp_processor.process_frame(frame)
                metrics = processed.to_flat_metrics()

                # Acumular en buffer continuo del ítem
                self.accumulator.push_frame(metrics)

                # Sugerencia estimada en tiempo real (para UI en vivo)
                if self.active_session and self.active_session.current_item:
                    estimate = self.accumulator.get_realtime_estimate()
                    ai_suggestion = self.ai_suggester.evaluate_realtime(
                        item_code=self.active_session.current_item.code,
                        avg_metrics=estimate,
                        frame_count=self.accumulator.frame_count(),
                    )

            # ── Encode imagen a Base64 ────────────────────────────────────
            # Usar frame anotado si existe
            if self.mp_processor and self.mp_processor.is_ready and hasattr(processed, 'annotated_frame') and processed.annotated_frame is not None:
                display_frame = processed.annotated_frame
            else:
                display_frame = frame

            resized = cv2.resize(display_frame, (640, 480))
            _, buffer = cv2.imencode(".jpg", resized, [cv2.IMWRITE_JPEG_QUALITY, 80])
            b64_str = base64.b64encode(buffer).decode("ascii")
            return {
                "connected": True,
                "image_b64": b64_str,
                "metrics": metrics,
                "ai_suggestion": ai_suggestion,
            }
        except Exception as err:
            return {"connected": False, "image_b64": None, "message": str(err), "metrics": {}}

    def export_report(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Exporta el informe en la carpeta configurada (provisional o final)."""
        if not self.last_evaluation:
            return {"success": False, "message": "No hay resultados disponibles para exportar."}

        format_type = params.get("format", "pdf").lower()
        anonymize = params.get("anonymize", False)
        is_final = params.get("is_final", True)

        out_dir = Path(self.settings.final_reports_dir if is_final else self.settings.provisional_reports_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        session_id = self.last_evaluation.get("session_id", "session")
        base_name = f"informe_{session_id[:8]}"

        try:
            if self.test_type == "stat":
                if format_type == "pdf":
                    path = export_stat_to_pdf(self.last_evaluation, out_dir / f"{base_name}.pdf")
                elif format_type == "html":
                    path = export_stat_to_html(self.last_evaluation, out_dir / f"{base_name}.html")
                else:
                    path = export_stat_to_json(self.last_evaluation, out_dir / f"{base_name}.json", anonymize=anonymize)
            else:
                path = export_ados2_to_json(self.last_evaluation, out_dir / f"{base_name}_ados2.json", anonymize=anonymize)

            return {
                "success": True,
                "message": f"Informe guardado en: {path.resolve()}",
                "file_path": str(path.resolve()),
            }
        except Exception as err:
            return {"success": False, "message": f"Error al generar reporte: {err}"}

    def get_final_ai_verdict(self) -> Dict[str, Any]:
        """Retorna el veredicto final de la IA para el ítem actual, sin avanzar."""
        if not self.active_session or not self.active_session.current_item:
            return {"error": "No hay ítem activo."}
        final_stats = self.accumulator.get_final_stats()
        verdict = self.ai_suggester.evaluate_final(
            self.active_session.current_item.code, final_stats
        )
        verdict["session_duration"] = self.accumulator.duration_seconds()
        verdict["frame_count"] = self.accumulator.frame_count()
        return verdict

    def get_session_recording_path(self) -> Dict[str, Any]:
        """Retorna la ruta de grabación de la sesión actual."""
        if not self.active_session:
            return {"path": None}
        out_dir = Path(self.settings.recordings_dir)
        session_id = self.active_session.session_id
        path = out_dir / f"{session_id}_frontal.mp4"
        return {
            "path": str(path.resolve()) if path.exists() else None,
            "exists": path.exists(),
        }

    def _open_camera(self, source: str) -> None:
        """Abre la cámara de análisis."""
        self._close_camera()
        if source == "simulation":
            return
        try:
            # Intentar usar CameraPool primero
            if self.camera_pool.set_analysis_camera(source):
                self.threaded_cam = self.camera_pool.analysis_cam
            else:
                # Fallback a ThreadedCamera directa
                self.threaded_cam = ThreadedCamera(source)
                self.threaded_cam.start()
        except Exception as err:
            print(f"[!] Error abriendo cámara {source}: {err}")
            self.threaded_cam = None

    def _close_camera(self) -> None:
        self.camera_pool.stop_all()
        if self.threaded_cam and self.threaded_cam not in (
            [self.camera_pool.analysis_cam] + self.camera_pool.context_cams
        ):
            try:
                self.threaded_cam.stop()
            except Exception:
                pass
        self.threaded_cam = None
        if self.mp_processor:
            self.mp_processor.close()
            self.mp_processor = None
