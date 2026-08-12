"""Pruebas unitarias para el módulo del Test STAT en CHEEMS (Standard unittest)."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from cheems.core.patient import Patient
from cheems.core.report import STATReportGenerator
from cheems.core.session import STATSession
from cheems.tests.stat.models import (
    ALL_STAT_ITEMS,
    STATDomainCode,
    STATRiskLevel,
)
from cheems.tests.stat.scoring import STATScorer
from cheems.tracking.stat_tracker import STATMediaPipeTracker
from cheems.utils.exporters import export_stat_to_json
from cheems.utils.validators import validate_patient_age


class TestSTATModule(unittest.TestCase):
    """Suite de pruebas unitarias para el módulo STAT."""

    def test_patient_age_validation(self):
        """Verifica que la edad del paciente esté restringida a 12-36 meses."""
        p1 = Patient(patient_id="1", full_name="Niño Válido 12m", age_months=12)
        p2 = Patient(patient_id="2", full_name="Niño Válido 36m", age_months=36)
        self.assertEqual(p1.age_years, 1.0)
        self.assertEqual(p2.age_years, 3.0)

        with self.assertRaises(ValueError):
            Patient(patient_id="3", full_name="Bebé Muy Joven", age_months=6)

        with self.assertRaises(ValueError):
            Patient(patient_id="4", full_name="Niño Mayor", age_months=48)

        ok, msg = validate_patient_age(24)
        self.assertTrue(ok)
        ok_low, _ = validate_patient_age(5)
        self.assertFalse(ok_low)

    def test_stat_items_count_and_domains(self):
        """Verifica que existan exactamente 12 ítems distribuidos en los 4 dominios del STAT."""
        self.assertEqual(len(ALL_STAT_ITEMS), 12)

        domains = {item.domain for item in ALL_STAT_ITEMS}
        self.assertEqual(
            domains,
            {
                STATDomainCode.PLAY,
                STATDomainCode.REQUESTING,
                STATDomainCode.DIRECTING_ATTENTION,
                STATDomainCode.MOTOR_IMITATION,
            },
        )

    def test_stat_scoring_high_risk(self):
        """Verifica que fallar en 2 o más dominios genere clasificación de Riesgo Alto de TEA."""
        scorer = STATScorer()
        scores = {}

        # Domain PLAY (P-1, P-2) -> Ambos fallados
        scores["P-1"] = scorer.evaluate_item("P-1", therapist_passed=False)
        scores["P-2"] = scorer.evaluate_item("P-2", therapist_passed=False)

        # Domain REQUESTING (R-1, R-2) -> Ambos fallados
        scores["R-1"] = scorer.evaluate_item("R-1", therapist_passed=False)
        scores["R-2"] = scorer.evaluate_item("R-2", therapist_passed=False)

        # Resto aprobados
        for code in ["DA-1", "DA-2", "DA-3", "DA-4", "MI-1", "MI-2", "MI-3", "MI-4"]:
            scores[code] = scorer.evaluate_item(code, therapist_passed=True)

        domain_results = scorer.calculate_domain_results(scores)
        self.assertTrue(domain_results[STATDomainCode.PLAY].domain_failed)
        self.assertTrue(domain_results[STATDomainCode.REQUESTING].domain_failed)
        self.assertFalse(domain_results[STATDomainCode.DIRECTING_ATTENTION].domain_failed)
        self.assertFalse(domain_results[STATDomainCode.MOTOR_IMITATION].domain_failed)

        risk_level, failed_count, _ = scorer.compute_overall_risk(domain_results)
        self.assertEqual(failed_count, 2)
        self.assertEqual(risk_level, STATRiskLevel.HIGH_RISK)

    def test_stat_scoring_low_risk(self):
        """Verifica que fallar en 0 o 1 dominio genere clasificación de Riesgo Bajo de TEA."""
        scorer = STATScorer()
        scores = {}

        for item in ALL_STAT_ITEMS:
            passed = True if item.code != "DA-1" else False
            scores[item.code] = scorer.evaluate_item(item.code, therapist_passed=passed)

        domain_results = scorer.calculate_domain_results(scores)
        failed_domains = [d for d, r in domain_results.items() if r.domain_failed]
        self.assertEqual(len(failed_domains), 0)

        risk_level, failed_count, _ = scorer.compute_overall_risk(domain_results)
        self.assertEqual(failed_count, 0)
        self.assertEqual(risk_level, STATRiskLevel.LOW_RISK)

    def test_stat_tracker_metrics(self):
        """Verifica los cálculos del tracker de métricas espaciales para STAT."""
        tracker = STATMediaPipeTracker()

        # Caso 1: Aplausos (MI-1)
        hands_data = [
            {"wrist": (0.45, 0.50, 0.0), "gesture": "Open_Palm", "gesture_score": 0.90},
            {"wrist": (0.48, 0.50, 0.0), "gesture": "Open_Palm", "gesture_score": 0.88},
        ]
        metrics = tracker.analyze_frame_data(hands_data)
        self.assertGreater(metrics["clapping_proximity"], 0.90)

        # Caso 2: Manos en la cabeza (MI-3)
        hands_elevated = [
            {"wrist": (0.45, 0.20, 0.0), "gesture": "None", "gesture_score": 0.50},
        ]
        metrics_elev = tracker.analyze_frame_data(hands_elevated)
        self.assertGreater(metrics_elev["hands_elevated_score"], 0.70)

        # Caso 3: Señalar (DA-2)
        hands_pointing = [
            {"wrist": (0.50, 0.50, 0.0), "gesture": "Pointing_Up", "gesture_score": 0.95},
        ]
        metrics_point = tracker.analyze_frame_data(hands_pointing)
        self.assertEqual(metrics_point["pointing_detected"], 0.95)

    def test_stat_tracker_pose_anchoring_and_atypical_alerts(self):
        """Verifica el anclaje anatómico con MediaPipe Pose y las alertas de aleteo/balanceo."""
        tracker = STATMediaPipeTracker()

        pose_data = {
            "left_shoulder": (0.30, 0.50, 0.0),
            "right_shoulder": (0.70, 0.50, 0.0),
            "left_ear": (0.40, 0.20, 0.0),
            "right_ear": (0.60, 0.20, 0.0),
            "torso_pitch_oscillation": 0.45,
        }
        hands_data = [
            {"wrist": (0.45, 0.15, 0.0), "gesture": "Open_Palm", "gesture_score": 0.90, "wrist_velocity": 0.80},
        ]

        metrics = tracker.analyze_frame_data(hands_data, pose_data=pose_data)

        self.assertEqual(metrics["pose_anchored"], 1.0)
        self.assertGreater(metrics["hands_elevated_score"], 0.80)
        self.assertGreater(metrics["flapping_detected"], 0.70)
        self.assertGreater(metrics["rocking_detected"], 0.40)

    def test_stat_full_session_flow(self):
        """Verifica el flujo completo de una sesión STAT y su exportación."""
        with TemporaryDirectory() as tmp_dir:
            patient = Patient(patient_id="P-TEST", full_name="Prueba Integración", age_months=20)
            session = STATSession(patient=patient)

            for item in ALL_STAT_ITEMS:
                session.record_item_result(item.code, therapist_passed=True, notes="Prueba unitaria")
                session.advance_item()

            self.assertTrue(session.is_completed)
            res = session.evaluate_session()
            self.assertEqual(res["overall_risk"], STATRiskLevel.LOW_RISK.value)

            markdown_report = STATReportGenerator.generate_markdown_report(res)
            self.assertIn("Informe de Evaluación STAT", markdown_report)
            self.assertIn("Prueba Integración", markdown_report)

            json_path = Path(tmp_dir) / "result.json"
            export_stat_to_json(res, json_path)
            self.assertTrue(json_path.exists())

            with open(json_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                self.assertEqual(loaded["patient"]["patient_id"], "P-TEST")


if __name__ == "__main__":
    unittest.main()
