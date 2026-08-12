"""Algoritmo base de puntuación para ADOS-2."""

from typing import List, Tuple
from cheems.tests.ados2.models import ADOS2ItemScore, ADOS2Domain, ADOS2SubAlgorithm


class ADOS2Scorer:
    """Motor de cálculo de cortes para ADOS-2."""

    @staticmethod
    def convert_code(raw_code: int) -> int:
        """Conversión estándar ADOS-2: 3→2, 7/8/9→0."""
        if raw_code == 3:
            return 2
        if raw_code in (7, 8, 9):
            return 0
        return raw_code

    @staticmethod
    def calculate_domain_totals(item_scores: List[ADOS2ItemScore]) -> Tuple[int, int]:
        """Suma SA y RRB tras conversión de códigos."""
        sa = sum(ADOS2Scorer.convert_code(s.raw_code) for s in item_scores if s.domain == ADOS2Domain.SA)
        rrb = sum(ADOS2Scorer.convert_code(s.raw_code) for s in item_scores if s.domain == ADOS2Domain.RRB)
        return sa, rrb

    # Tablas de cutoff por sub-algoritmo (Lord et al., 2012)
    CUTOFFS = {
        ADOS2SubAlgorithm.M1_FEW_NO_WORDS:  {"spectrum": 8,  "autism": 12},
        ADOS2SubAlgorithm.M1_SOME_WORDS:    {"spectrum": 7,  "autism": 11},
        ADOS2SubAlgorithm.M2_UNDER_5:       {"spectrum": 7,  "autism": 10},
        ADOS2SubAlgorithm.M2_5_AND_OLDER:   {"spectrum": 8,  "autism": 11},
        ADOS2SubAlgorithm.M3_DEFAULT:       {"spectrum": 7,  "autism": 9},
        ADOS2SubAlgorithm.M4_DEFAULT:       {"spectrum": 7,  "autism": 10},
    }

    @staticmethod
    def classify(sub_algorithm: ADOS2SubAlgorithm, total: int) -> str:
        """Clasifica en base al cutoff del sub-algoritmo."""
        if sub_algorithm.value.startswith("toddler"):
            return ADOS2Scorer.classify_toddler(sub_algorithm, total)
            
        cutoff = ADOS2Scorer.CUTOFFS.get(sub_algorithm)
        if not cutoff:
            raise ValueError(f"Sub-algoritmo no soportado: {sub_algorithm}")
            
        if total >= cutoff["autism"]:
            return "Autismo"
        if total >= cutoff["spectrum"]:
            return "Espectro Autista"
        return "No Espectro"

    @staticmethod
    def classify_toddler(sub_algorithm: ADOS2SubAlgorithm, total: int) -> str:
        """Módulo Toddler NO clasifica Autismo/Espectro, solo rangos de preocupación."""
        if total >= 14:
            return "Preocupación Moderada a Severa"
        if total >= 10:
            return "Preocupación Leve a Moderada"
        return "Poca o Ninguna Preocupación"
