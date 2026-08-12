"""Pruebas unitarias para el stub de ADOS-2 en CHEEMS."""

import unittest
from cheems.tests.ados2.models import ADOS2Module
from cheems.tests.ados2.scoring import ADOS2Scorer


class TestADOS2Module(unittest.TestCase):
    """Pruebas base para ADOS-2."""

    def test_ados2_cutoff_base(self):
        """Verifica el cálculo de corte base para ADOS-2."""
        classification, total = ADOS2Scorer.calculate_cutoff(ADOS2Module.MODULE_1, sa_score=8, rbr_score=3)
        self.assertEqual(total, 11)
        self.assertEqual(classification, "Autismo")

        class_non, total_non = ADOS2Scorer.calculate_cutoff(ADOS2Module.MODULE_1, sa_score=2, rbr_score=1)
        self.assertEqual(total_non, 3)
        self.assertEqual(class_non, "Sin Espectro")


if __name__ == "__main__":
    unittest.main()
