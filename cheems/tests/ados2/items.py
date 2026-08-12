"""Definición de ítems oficiales del ADOS-2 por módulo."""

from typing import List

from cheems.tests.ados2.models import ADOS2Domain, ADOS2Item, ADOS2Module

# Items de ejemplo para el algoritmo de cada módulo.
# En una versión completa de producción se listarían los 20-30 ítems por módulo.

ALL_ADOS2_ITEMS: List[ADOS2Item] = [
    # MÓDULO TODDLER
    ADOS2Item(
        code="T-A1",
        name="Frecuencia del balbuceo",
        domain=ADOS2Domain.SA,
        module=ADOS2Module.TODDLER,
        description="Evalúa la cantidad y calidad del balbuceo.",
        is_algorithm_item=True,
    ),
    ADOS2Item(
        code="T-B1",
        name="Contacto visual inusual",
        domain=ADOS2Domain.SA,
        module=ADOS2Module.TODDLER,
        description="Uso del contacto visual para fines sociales.",
        is_algorithm_item=True,
    ),
    ADOS2Item(
        code="T-D1",
        name="Intereses inusuales",
        domain=ADOS2Domain.RRB,
        module=ADOS2Module.TODDLER,
        description="Intereses sensoriales o restringidos.",
        is_algorithm_item=True,
    ),

    # MÓDULO 1
    ADOS2Item(
        code="M1-A1",
        name="Nivel general de lenguaje",
        domain=ADOS2Domain.SA,
        module=ADOS2Module.MODULE_1,
        description="Nivel de lenguaje expresivo no ecolálico.",
        is_algorithm_item=True,
    ),
    ADOS2Item(
        code="M1-B1",
        name="Contacto visual",
        domain=ADOS2Domain.SA,
        module=ADOS2Module.MODULE_1,
        description="Contacto visual inusual o falta del mismo.",
        is_algorithm_item=True,
    ),
    ADOS2Item(
        code="M1-D1",
        name="Manierismos de manos y dedos",
        domain=ADOS2Domain.RRB,
        module=ADOS2Module.MODULE_1,
        description="Movimientos repetitivos.",
        is_algorithm_item=True,
    ),

    # MÓDULO 2
    ADOS2Item(
        code="M2-A1",
        name="Nivel general de lenguaje",
        domain=ADOS2Domain.SA,
        module=ADOS2Module.MODULE_2,
        description="Lenguaje en frases.",
        is_algorithm_item=True,
    ),
    ADOS2Item(
        code="M2-B1",
        name="Contacto visual",
        domain=ADOS2Domain.SA,
        module=ADOS2Module.MODULE_2,
        description="Contacto visual inusual.",
        is_algorithm_item=True,
    ),
    ADOS2Item(
        code="M2-D1",
        name="Comportamientos repetitivos",
        domain=ADOS2Domain.RRB,
        module=ADOS2Module.MODULE_2,
        description="Intereses sensoriales o restringidos.",
        is_algorithm_item=True,
    ),

    # MÓDULO 3
    ADOS2Item(
        code="M3-A1",
        name="Nivel general de lenguaje",
        domain=ADOS2Domain.SA,
        module=ADOS2Module.MODULE_3,
        description="Lenguaje fluido.",
        is_algorithm_item=True,
    ),
    ADOS2Item(
        code="M3-B1",
        name="Contacto visual",
        domain=ADOS2Domain.SA,
        module=ADOS2Module.MODULE_3,
        description="Contacto visual inusual.",
        is_algorithm_item=True,
    ),
    ADOS2Item(
        code="M3-D1",
        name="Comportamientos repetitivos",
        domain=ADOS2Domain.RRB,
        module=ADOS2Module.MODULE_3,
        description="Intereses restringidos.",
        is_algorithm_item=True,
    ),

    # MÓDULO 4
    ADOS2Item(
        code="M4-A1",
        name="Nivel general de lenguaje",
        domain=ADOS2Domain.SA,
        module=ADOS2Module.MODULE_4,
        description="Lenguaje en adultos.",
        is_algorithm_item=True,
    ),
    ADOS2Item(
        code="M4-B1",
        name="Contacto visual",
        domain=ADOS2Domain.SA,
        module=ADOS2Module.MODULE_4,
        description="Contacto visual inusual.",
        is_algorithm_item=True,
    ),
    ADOS2Item(
        code="M4-D1",
        name="Comportamientos repetitivos",
        domain=ADOS2Domain.RRB,
        module=ADOS2Module.MODULE_4,
        description="Intereses restringidos.",
        is_algorithm_item=True,
    ),
]
