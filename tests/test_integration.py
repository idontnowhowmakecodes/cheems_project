"""Pruebas de integración End-to-End para el flujo clínico completo en CHEEMS."""

import tempfile
import unittest
from pathlib import Path

from cheems.ui.bridge import CheemsDesktopBridge


class TestCheemsIntegration(unittest.TestCase):
    """Verificación de integración completa del sistema (Bridge + Clínico + Criptografía)."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "cheems_integration.db"
        self.bridge = CheemsDesktopBridge(db_path=self.db_path)

    def tearDown(self):
        self.bridge.repository.close()
        self.temp_dir.cleanup()

    def test_stat_full_bridge_workflow(self):
        """Prueba el ciclo de vida completo de una evaluación STAT a través del Bridge."""
        # 1. Iniciar sesión
        start_cfg = {
            "patient_id": "P-INTEG-01",
            "patient_name": "Valeria Castro",
            "patient_age": 28,
            "evaluator": "Dr. Benavides",
            "test_type": "stat",
            "camera_source": "simulation",
        }
        start_res = self.bridge.start_session(start_cfg)
        self.assertTrue(start_res["success"])
        self.assertIsNotNone(start_res["current_item"])
        self.assertEqual(start_res["current_item"]["code"], "P-1")

        # 2. Iterar sobre todos los ítems marcando veredictos
        # Pasamos P-1, pero fallamos los demás para probar riesgo alto
        is_completed = False
        step = 0
        while not is_completed and step < 20:
            step += 1
            passed = (step == 1) # solo el primero pasa
            advance_res = self.bridge.advance_item({
                "passed": passed,
                "notes": f"Nota de prueba paso {step}",
            })
            is_completed = advance_res.get("completed", False)

        self.assertTrue(is_completed)
        evaluation = advance_res.get("evaluation", {})
        self.assertIn("overall_risk", evaluation)
        self.assertEqual(evaluation["overall_risk"], "Riesgo Alto de TEA")

        # 3. Exportar reportes
        pdf_res = self.bridge.export_report({"format": "pdf", "anonymize": True})
        self.assertTrue(pdf_res["success"])
        self.assertTrue(Path(pdf_res["file_path"]).exists())

        json_res = self.bridge.export_report({"format": "json", "anonymize": True})
        self.assertTrue(json_res["success"])
        self.assertTrue(Path(json_res["file_path"]).exists())

    def test_ados2_full_bridge_workflow(self):
        """Prueba el ciclo de vida completo de una evaluación ADOS-2 a través del Bridge."""
        # 1. Iniciar sesión ADOS-2 Módulo 1
        start_cfg = {
            "patient_id": "P-INTEG-02",
            "patient_name": "Rodrigo Silva",
            "patient_age": 36,
            "evaluator": "Dra. Valdivia",
            "test_type": "ados2",
            "module": "Módulo 1",
            "sub_algorithm": "m1_some_words",
            "camera_source": "simulation",
        }
        start_res = self.bridge.start_session(start_cfg)
        self.assertTrue(start_res["success"])

        # 2. Completar los ítems
        is_completed = False
        step = 0
        while not is_completed and step < 20:
            step += 1
            advance_res = self.bridge.advance_item({"passed": True, "notes": "Sin atipicidad"})
            is_completed = advance_res.get("completed", False)

        self.assertTrue(is_completed)
        eval_ados = advance_res.get("evaluation", {})
        self.assertEqual(eval_ados["classification"], "No Espectro")
        self.assertEqual(eval_ados["css_score"], 1)

    def test_camera_connection_and_disconnected_state(self):
        """Verifica que sin cámara conectada no se genere falso positivo de transmisión."""
        frame_data = self.bridge.get_camera_frame()
        self.assertFalse(frame_data["connected"])
        self.assertIsNone(frame_data["image_b64"])
        self.assertIn("Sin cámara", frame_data["message"])

    def test_settings_persistence_bridge(self):
        """Verifica la lectura y guardado de configuraciones de IP y carpetas."""
        initial_cfg = self.bridge.get_settings()
        self.assertIn("camera_source", initial_cfg)
        self.assertIn("recordings_dir", initial_cfg)

        save_res = self.bridge.save_settings({
            "camera_source": "http://192.168.1.50:8080/video",
            "recordings_dir": "data/custom_recordings",
            "provisional_reports_dir": "data/custom_provisional",
            "final_reports_dir": "data/custom_final",
        })
        self.assertTrue(save_res["success"])
        updated_cfg = self.bridge.get_settings()
        self.assertEqual(updated_cfg["camera_source"], "http://192.168.1.50:8080/video")
        self.assertEqual(updated_cfg["recordings_dir"], "data/custom_recordings")


if __name__ == "__main__":
    unittest.main()
