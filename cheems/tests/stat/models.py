"""Modelos de datos para el Test STAT (Screening Tool for Autism in Toddlers)."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class STATDomainCode(str, Enum):
    """Códigos de los 4 Dominios del Test STAT."""

    PLAY = "PLAY"
    REQUESTING = "REQUESTING"
    DIRECTING_ATTENTION = "DIRECTING_ATTENTION"
    MOTOR_IMITATION = "MOTOR_IMITATION"


class STATRiskLevel(str, Enum):
    """Niveles de riesgo para TEA según el algoritmo global de corte del STAT."""

    LOW_RISK = "Riesgo Bajo de TEA"
    HIGH_RISK = "Riesgo Alto de TEA"
    INCOMPLETE = "Evaluación Incompleta"


@dataclass(frozen=True)
class STATItem:
    """Definición de un ítem del Test STAT."""

    code: str
    name: str
    domain: STATDomainCode
    description: str
    pass_criteria: str
    instruction: str


@dataclass
class ItemScore:
    """Puntuación registrada para un ítem del STAT.
    
    Score:
        0 = PASS (Pasa / Conducta observada adecuadamente)
        1 = FAIL (Falla / Ausencia o alteración de conducta)
    """

    item_code: str
    score: int  # 0: Pass, 1: Fail
    therapist_passed: bool
    ai_suggested_pass: Optional[bool] = None
    has_discrepancy: bool = False
    raw_metrics: Dict[str, float] = field(default_factory=dict)
    notes: str = ""

    def __post_init__(self) -> None:
        """Valida que la puntuación sea 0 (Pass) o 1 (Fail)."""
        if self.score not in (0, 1):
            raise ValueError(f"La puntuación del ítem {self.item_code} debe ser 0 (Pass) o 1 (Fail).")


@dataclass
class STATDomainResult:
    """Resumen de puntuación para un dominio del STAT."""

    domain: STATDomainCode
    domain_name: str
    items_total: int
    items_failed: int
    items_passed: int
    domain_failed: Optional[bool]
    cutoff_description: str
    items_unevaluated: int = 0
    is_complete: bool = True


# Registro exhaustivo de los 12 Ítems del Test STAT
ALL_STAT_ITEMS: List[STATItem] = [
    # Dom 1: PLAY (Juego)
    STATItem(
        code="P-1",
        name="Imitación de Juego",
        domain=STATDomainCode.PLAY,
        description="Imitación de acciones de juego funcionales con objetos (p. ej. rodar autito, dar de comer al muñeco).",
        pass_criteria="Imita al menos 1 acción de juego funcional con los objetos dados.",
        instruction="El terapeuta muestra una acción de juego y solicita imitación al menor.",
    ),
    STATItem(
        code="P-2",
        name="Juego Representacional",
        domain=STATDomainCode.PLAY,
        description="Juego simbólico o espontáneo dirigido hacia un objeto/muñeco.",
        pass_criteria="Realiza espontáneamente una conducta de juego de simulación/representación.",
        instruction="Se presentan objetos de juego simbolicó para observar el uso espontáneo.",
    ),
    # Dom 2: REQUESTING (Petición)
    STATItem(
        code="R-1",
        name="Petición con Burbujas",
        domain=STATDomainCode.REQUESTING,
        description="Solicitud de continuación de la actividad de burbujas (gestos, mirada o vocalización).",
        pass_criteria="Hace un contacto visual, gesto o vocalización para pedir más burbujas.",
        instruction="El terapeuta sopla burbujas, cierra el frasco y observa la reacción de petición del menor.",
    ),
    STATItem(
        code="R-2",
        name="Petición con Objeto/Globo",
        domain=STATDomainCode.REQUESTING,
        description="Solicitud de ayuda para inflar un globo o abrir un recipiente con alimento.",
        pass_criteria="Entrega el objeto o hace un gesto/mirada de solicitud de ayuda.",
        instruction="El terapeuta muestra un globo desinflado o frasco sellado y espera solicitud del menor.",
    ),
    # Dom 3: DIRECTING ATTENTION (Dirigir la Atención)
    STATItem(
        code="DA-1",
        name="Mostrar Objeto",
        domain=STATDomainCode.DIRECTING_ATTENTION,
        description="Muestra un objeto al evaluador para compartir interés visual.",
        pass_criteria="Extiende o sostiene un objeto hacia la cara del evaluador para mostrárselo.",
        instruction="Se ofrecen juguetes llamativos para observar si el niño los muestra al evaluador.",
    ),
    STATItem(
        code="DA-2",
        name="Señalar",
        domain=STATDomainCode.DIRECTING_ATTENTION,
        description="Señala con el dedo índice hacia un estímulo distante para compartir interés.",
        pass_criteria="Extiende el brazo y señala un objeto distante con intención comunicativa.",
        instruction="Se activa un estímulo lejano (afiche/luces) para evaluar si el niño señala.",
    ),
    STATItem(
        code="DA-3",
        name="Seguimiento de la Mirada",
        domain=STATDomainCode.DIRECTING_ATTENTION,
        description="Sigue la orientación de la cabeza y mirada del evaluador hacia un punto objetivo.",
        pass_criteria="Gira la cara/mirada hacia el objetivo al cual el evaluador está mirando.",
        instruction="El evaluador mira marcadamente hacia un lado y dice '¡Mira!'.",
    ),
    STATItem(
        code="DA-4",
        name="Atención Conjunta",
        domain=STATDomainCode.DIRECTING_ATTENTION,
        description="Alternancia de mirada entre un objeto de interés y los ojos del evaluador.",
        pass_criteria="Alterna espontáneamente la mirada entre objeto y evaluador al menos 1 vez.",
        instruction="Se activa un juguete mecánico y se observa la alternancia de mirada.",
    ),
    # Dom 4: MOTOR IMITATION (Imitación Motora)
    STATItem(
        code="MI-1",
        name="Aplaudir",
        domain=STATDomainCode.MOTOR_IMITATION,
        description="Imitación del gesto corporal de aplaudir.",
        pass_criteria="Imita aplaudir juntando ambas manos.",
        instruction="El evaluador aplaude y dice '¡Haz esto!'.",
    ),
    STATItem(
        code="MI-2",
        name="Golpear la Mesa",
        domain=STATDomainCode.MOTOR_IMITATION,
        description="Imitación de golpear rítmicamente la mesa con las palmas/manos.",
        pass_criteria="Imita golpear la mesa con una o ambas manos.",
        instruction="El evaluador da golpecitos a la mesa y pide imitación.",
    ),
    STATItem(
        code="MI-3",
        name="Manos en la Cabeza",
        domain=STATDomainCode.MOTOR_IMITATION,
        description="Imitación de colocar ambas manos sobre la cabeza.",
        pass_criteria="Lleva ambas manos arriba sobre la cabeza.",
        instruction="El evaluador se pone las manos en la cabeza y dice '¡Haz esto!'.",
    ),
    STATItem(
        code="MI-4",
        name="Imitación con Objetos",
        domain=STATDomainCode.MOTOR_IMITATION,
        description="Imitación de una acción motora utilizando un objeto simple (p. ej. sonar campanilla).",
        pass_criteria="Imita el movimiento motor especifico usando el objeto.",
        instruction="El evaluador realiza una acción motora con objeto y se lo pasa al niño.",
    ),
]
