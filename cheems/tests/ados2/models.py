"""Modelos base de datos para el Test ADOS-2 (Módulos Toddler, 1, 2, 3)."""

from dataclasses import dataclass
from enum import Enum


class ADOS2Module(str, Enum):
    TODDLER = "toddler"
    MODULE_1 = "module_1"
    MODULE_2 = "module_2"
    MODULE_3 = "module_3"
    MODULE_4 = "module_4"


class ADOS2SubAlgorithm(str, Enum):
    """Sub-algoritmo según nivel de lenguaje y edad."""
    TODDLER_12_20 = "toddler_12_20"
    TODDLER_21_30_FEW = "toddler_21_30_few_words"
    TODDLER_21_30_SOME = "toddler_21_30_some_words"
    M1_FEW_NO_WORDS = "m1_few_no_words"
    M1_SOME_WORDS = "m1_some_words"
    M2_UNDER_5 = "m2_under_5"
    M2_5_AND_OLDER = "m2_5_and_older"
    M3_DEFAULT = "m3"
    M4_DEFAULT = "m4"


class ADOS2Domain(str, Enum):
    """Dominios del ADOS-2 (para el algoritmo)."""
    SA = "SA"  # Social Affect
    RRB = "RRB"  # Restricted and Repetitive Behaviors
    NONE = "NONE" # Ítems fuera del algoritmo principal


class ADOS2ItemCode(int, Enum):
    """Códigos de puntuación individuales."""
    NORMAL = 0
    SLIGHT = 1
    DEFINITE = 2
    SEVERE = 3          # → se convierte a 2
    NOT_APPLICABLE = 7  # → se convierte a 0
    NOT_OBSERVED = 8    # → se convierte a 0
    NOT_SCORED = 9      # → se convierte a 0


@dataclass(frozen=True)
class ADOS2Item:
    code: str
    name: str
    domain: ADOS2Domain
    module: ADOS2Module
    description: str
    is_algorithm_item: bool


@dataclass
class ADOS2ItemScore:
    """Puntuación registrada para un ítem del ADOS-2."""
    item_code: str
    raw_code: int
    domain: ADOS2Domain
    notes: str = ""
