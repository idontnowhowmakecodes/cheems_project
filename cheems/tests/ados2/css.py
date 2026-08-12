"""Tablas de conversión CSS (Calibrated Severity Score) para ADOS-2 (1-10)."""

from typing import Dict, Tuple

from cheems.tests.ados2.models import ADOS2SubAlgorithm

# El formato es: CSS_TABLES[sub_algorithm][edad_en_meses_minimo, edad_en_meses_maximo] = { (total_min, total_max): css_score }
# Aquí se provee un subconjunto simplificado representativo para MVP. En producción llevaría todas las tablas exactas.

CSS_TABLES: Dict[str, Dict[Tuple[int, int], Dict[Tuple[int, int], int]]] = {
    ADOS2SubAlgorithm.M1_FEW_NO_WORDS: {
        (12, 1200): { # Para cualquier edad
            (0, 5): 1,
            (6, 6): 2,
            (7, 7): 3,
            (8, 8): 4,
            (9, 10): 5,
            (11, 11): 6,
            (12, 13): 7,
            (14, 15): 8,
            (16, 17): 9,
            (18, 99): 10,
        }
    },
    ADOS2SubAlgorithm.M1_SOME_WORDS: {
        (12, 1200): {
            (0, 4): 1,
            (5, 5): 2,
            (6, 6): 3,
            (7, 7): 4,
            (8, 9): 5,
            (10, 10): 6,
            (11, 12): 7,
            (13, 15): 8,
            (16, 17): 9,
            (18, 99): 10,
        }
    },
    ADOS2SubAlgorithm.M2_UNDER_5: {
        (12, 59): {
            (0, 4): 1,
            (5, 5): 2,
            (6, 6): 3,
            (7, 7): 4,
            (8, 8): 5,
            (9, 9): 6,
            (10, 11): 7,
            (12, 13): 8,
            (14, 15): 9,
            (16, 99): 10,
        }
    },
    ADOS2SubAlgorithm.M2_5_AND_OLDER: {
        (60, 1200): {
            (0, 4): 1,
            (5, 5): 2,
            (6, 7): 3,
            (8, 8): 4,
            (9, 9): 5,
            (10, 10): 6,
            (11, 12): 7,
            (13, 14): 8,
            (15, 17): 9,
            (18, 99): 10,
        }
    },
    ADOS2SubAlgorithm.M3_DEFAULT: {
        (12, 1200): {
            (0, 2): 1,
            (3, 4): 2,
            (5, 6): 3,
            (7, 7): 4,
            (8, 8): 5,
            (9, 9): 6,
            (10, 11): 7,
            (12, 13): 8,
            (14, 15): 9,
            (16, 99): 10,
        }
    },
    ADOS2SubAlgorithm.M4_DEFAULT: {
        (12, 1200): {
            (0, 2): 1,
            (3, 4): 2,
            (5, 6): 3,
            (7, 7): 4,
            (8, 8): 5,
            (9, 9): 6,
            (10, 11): 7,
            (12, 13): 8,
            (14, 15): 9,
            (16, 99): 10,
        }
    },
}

def calculate_css(sub_algorithm: ADOS2SubAlgorithm, total: int, age_months: int) -> int:
    """Retorna el CSS 1-10 o -1 si la tabla no está disponible para ese módulo/edad."""
    if sub_algorithm.value.startswith("toddler"):
        return -1  # Toddler no usa CSS, usa rangos de preocupación.
        
    algo_tables = CSS_TABLES.get(sub_algorithm)
    if not algo_tables:
        return -1
        
    table_to_use = None
    for (min_age, max_age), table in algo_tables.items():
        if min_age <= age_months <= max_age:
            table_to_use = table
            break
            
    if not table_to_use:
        return -1
        
    for (min_score, max_score), css in table_to_use.items():
        if min_score <= total <= max_score:
            return css
            
    return -1
