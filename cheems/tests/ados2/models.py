"""Modelos base de datos para el Test ADOS-2 (Módulos Toddler, 1, 2, 3)."""

from dataclasses import dataclass
from enum import Enum


class ADOS2Module(str, Enum):
    """Módulos disponibles en ADOS-2 según edad y nivel de lenguaje."""

    TODDLER = "Toddler (12-30 meses)"
    MODULE_1 = "Módulo 1 (Pocas/Sin Palabras)"
    MODULE_2 = "Módulo 2 (Lenguaje en Frases)"
    MODULE_3 = "Módulo 3 (Lenguaje Fluido)"


class ADOS2Domain(str, Enum):
    """Dominios del ADOS-2."""

    SOCIAL_AFFECT = "Afecto Social (SA)"
    RESTRICTED_REPETITIVE = "Comportamientos Restringidos y Repetitivos (RBR)"


@dataclass
class ADOS2Item:
    """Representa un ítem individual de ADOS-2."""

    code: str
    name: str
    domain: ADOS2Domain
    module: ADOS2Module
    description: str
