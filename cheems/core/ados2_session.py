"""Gestión de Sesión de Evaluación para el Test ADOS-2 en CHEEMS."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from cheems.core.patient import Patient
from cheems.tests.ados2.models import ADOS2ItemScore, ADOS2Module, ADOS2SubAlgorithm, ADOS2Domain
from cheems.tests.ados2.items import ALL_ADOS2_ITEMS
from cheems.tests.ados2.scoring import ADOS2Scorer
from cheems.tests.ados2.css import calculate_css


class ADOS2Session:
    """Orquestador de la Sesión de Evaluación ADOS-2."""

    def __init__(
        self,
        patient: Patient,
        module: ADOS2Module,
        sub_algorithm: ADOS2SubAlgorithm,
        camera_source: str = "0",
    ) -> None:
        self.session_id = str(uuid4())
        self.patient = patient
        self.module = module
        self.sub_algorithm = sub_algorithm
        self.camera_source = camera_source
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.ended_at: Optional[str] = None

        # Filtramos solo los ítems del módulo seleccionado
        self.module_items = [i for i in ALL_ADOS2_ITEMS if i.module == module]
        
        self.item_scores: Dict[str, ADOS2ItemScore] = {}
        self.current_item_index = 0
        self.is_completed = False

    @property
    def current_item(self):
        """Devuelve el ítem actual en evaluación."""
        if self.current_item_index < len(self.module_items):
            return self.module_items[self.current_item_index]
        return None

    def record_item_result(
        self,
        item_code: str,
        raw_code: int,
        notes: str = "",
    ) -> ADOS2ItemScore:
        """Registra la puntuación (0-3, 7, 8) de un ítem individual."""
        item = next((i for i in self.module_items if i.code == item_code), None)
        if not item:
            raise ValueError(f"Ítem {item_code} no pertenece al {self.module.value}")

        score_obj = ADOS2ItemScore(
            item_code=item_code,
            raw_code=raw_code,
            domain=item.domain,
            notes=notes,
        )
        self.item_scores[item_code] = score_obj
        return score_obj

    def advance_item(self) -> bool:
        """Avanza al siguiente ítem. Retorna True si la sesión terminó."""
        self.current_item_index += 1
        if self.current_item_index >= len(self.module_items):
            self.is_completed = True
            self.ended_at = datetime.now(timezone.utc).isoformat()
            return True
        return False

    def evaluate_session(self) -> Dict[str, Any]:
        """Calcula el algoritmo ADOS-2: Totales, Clasificación y CSS."""
        scores_list = list(self.item_scores.values())
        
        sa_total, rrb_total = ADOS2Scorer.calculate_domain_totals(scores_list)
        overall_total = sa_total + rrb_total
        
        classification = "Incompleta"
        css_score = -1
        
        if self.is_completed:
            classification = ADOS2Scorer.classify(self.sub_algorithm, overall_total)
            css_score = calculate_css(self.sub_algorithm, overall_total, self.patient.age_months)

        return {
            "session_id": self.session_id,
            "patient": self.patient.to_dict(),
            "module": self.module.value,
            "sub_algorithm": self.sub_algorithm.value,
            "started_at": self.started_at,
            "ended_at": self.ended_at or datetime.now(timezone.utc).isoformat(),
            "is_completed": self.is_completed,
            "items_evaluated": len(self.item_scores),
            "items_total": len(self.module_items),
            "item_scores": {
                code: {
                    "raw_code": item.raw_code,
                    "converted_code": ADOS2Scorer.convert_code(item.raw_code),
                    "domain": item.domain.value,
                    "notes": item.notes,
                }
                for code, item in self.item_scores.items()
            },
            "totals": {
                "sa": sa_total,
                "rrb": rrb_total,
                "overall": overall_total,
            },
            "classification": classification,
            "css_score": css_score,
        }

    def close(self) -> None:
        """Limpieza de recursos si es necesario."""
        pass
