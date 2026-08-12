"""Algoritmo base de puntuación para ADOS-2."""

from typing import Dict, Tuple
from cheems.tests.ados2.models import ADOS2Module


class ADOS2Scorer:
    """Calculador base de cortes para ADOS-2."""

    @staticmethod
    def calculate_cutoff(module: ADOS2Module, sa_score: int, rbr_score: int) -> Tuple[str, int]:
        """Calcula la puntuación total y clasificación previa de ADOS-2."""
        total = sa_score + rbr_score
        classification = "Sin Espectro"
        if total >= 10:
            classification = "Autismo"
        elif total >= 7:
            classification = "Espectro Autista"
        return classification, total
