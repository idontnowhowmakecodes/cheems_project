"""Pruebas unitarias para el módulo ADOS-2 en CHEEMS."""

import unittest
from cheems.core.patient import Patient
from cheems.tests.ados2.models import ADOS2Module, ADOS2SubAlgorithm, ADOS2Domain, ADOS2ItemScore
from cheems.tests.ados2.scoring import ADOS2Scorer
from cheems.tests.ados2.css import calculate_css
from cheems.core.ados2_session import ADOS2Session


class TestADOS2Module(unittest.TestCase):
    """Pruebas base para ADOS-2."""

    def test_code_conversion(self):
        """Verifica la conversión de códigos 3->2 y 7,8,9->0."""
        self.assertEqual(ADOS2Scorer.convert_code(3), 2)
        self.assertEqual(ADOS2Scorer.convert_code(7), 0)
        self.assertEqual(ADOS2Scorer.convert_code(8), 0)
        self.assertEqual(ADOS2Scorer.convert_code(9), 0)
        self.assertEqual(ADOS2Scorer.convert_code(2), 2)
        self.assertEqual(ADOS2Scorer.convert_code(1), 1)
        self.assertEqual(ADOS2Scorer.convert_code(0), 0)

    def test_domain_totals(self):
        """Verifica la suma de dominios con conversión."""
        scores = [
            ADOS2ItemScore("A1", 3, ADOS2Domain.SA),  # 2
            ADOS2ItemScore("A2", 8, ADOS2Domain.SA),  # 0
            ADOS2ItemScore("A3", 1, ADOS2Domain.SA),  # 1  -> Total SA = 3
            ADOS2ItemScore("B1", 2, ADOS2Domain.RRB), # 2
            ADOS2ItemScore("B2", 7, ADOS2Domain.RRB), # 0  -> Total RRB = 2
            ADOS2ItemScore("C1", 2, ADOS2Domain.NONE),# Ignored
        ]
        sa, rrb = ADOS2Scorer.calculate_domain_totals(scores)
        self.assertEqual(sa, 3)
        self.assertEqual(rrb, 2)

    def test_classification(self):
        """Verifica las clasificaciones por sub-algoritmo."""
        # M1 Some Words: spectrum=7, autism=11
        self.assertEqual(ADOS2Scorer.classify(ADOS2SubAlgorithm.M1_SOME_WORDS, 6), "No Espectro")
        self.assertEqual(ADOS2Scorer.classify(ADOS2SubAlgorithm.M1_SOME_WORDS, 7), "Espectro Autista")
        self.assertEqual(ADOS2Scorer.classify(ADOS2SubAlgorithm.M1_SOME_WORDS, 10), "Espectro Autista")
        self.assertEqual(ADOS2Scorer.classify(ADOS2SubAlgorithm.M1_SOME_WORDS, 11), "Autismo")
        self.assertEqual(ADOS2Scorer.classify(ADOS2SubAlgorithm.M1_SOME_WORDS, 15), "Autismo")

        # Toddler
        self.assertEqual(ADOS2Scorer.classify(ADOS2SubAlgorithm.TODDLER_21_30_SOME, 9), "Poca o Ninguna Preocupación")
        self.assertEqual(ADOS2Scorer.classify(ADOS2SubAlgorithm.TODDLER_21_30_SOME, 10), "Preocupación Leve a Moderada")
        self.assertEqual(ADOS2Scorer.classify(ADOS2SubAlgorithm.TODDLER_21_30_SOME, 14), "Preocupación Moderada a Severa")

    def test_css_calculation(self):
        """Verifica el cálculo de CSS."""
        # M1 Some Words (12-1200 months), total=8 -> css=5
        self.assertEqual(calculate_css(ADOS2SubAlgorithm.M1_SOME_WORDS, 8, 36), 5)
        # total=4 -> css=1
        self.assertEqual(calculate_css(ADOS2SubAlgorithm.M1_SOME_WORDS, 4, 36), 1)
        # Toddler no tiene CSS
        self.assertEqual(calculate_css(ADOS2SubAlgorithm.TODDLER_21_30_SOME, 10, 24), -1)

    def test_ados2_session(self):
        """Verifica el flujo de sesión ADOS-2."""
        patient = Patient(patient_id="1", full_name="Test", age_months=36)
        session = ADOS2Session(patient, ADOS2Module.MODULE_1, ADOS2SubAlgorithm.M1_SOME_WORDS)
        
        # M1 items: M1-A1, M1-B1, M1-D1
        while not session.is_completed:
            item = session.current_item
            if item.code == "M1-A1":
                session.record_item_result(item.code, 3) # SA, converted to 2
            elif item.code == "M1-B1":
                session.record_item_result(item.code, 2) # SA, 2
            elif item.code == "M1-D1":
                session.record_item_result(item.code, 8) # RRB, converted to 0
            session.advance_item()
            
        res = session.evaluate_session()
        self.assertTrue(res["is_completed"])
        self.assertEqual(res["totals"]["sa"], 4)
        self.assertEqual(res["totals"]["rrb"], 0)
        self.assertEqual(res["totals"]["overall"], 4)
        self.assertEqual(res["classification"], "No Espectro")
        self.assertEqual(res["css_score"], 1)

if __name__ == "__main__":
    unittest.main()
