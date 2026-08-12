"""Gestión de Sesión de Evaluación para el Test STAT en CHEEMS."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from cheems.core.patient import Patient
from cheems.tests.stat.models import ALL_STAT_ITEMS, ItemScore, STATDomainResult, STATRiskLevel
from cheems.tests.stat.scoring import STATScorer
from cheems.tracking.stat_tracker import STATMediaPipeTracker


class STATSession:
    """Orquestador de la Sesión de Evaluación STAT.
    
    Gestiona la secuencia de los 12 ítems del STAT, recopila marcas de teclado (F7, F8, F9)
    y métricas espaciales del tracker MediaPipe, y computa el diagnóstico final de riesgo.
    """

    def __init__(
        self,
        patient: Patient,
        camera_source: str = "0",
        model_path: Optional[Path] = None,
        db_path: Optional[Path] = None,
    ) -> None:
        self.session_id = str(uuid4())
        self.patient = patient
        self.camera_source = camera_source
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.ended_at: Optional[str] = None

        self.scorer = STATScorer()
        self.tracker = STATMediaPipeTracker(model_path)
        self.db_path = db_path

        self.item_scores: Dict[str, ItemScore] = {}
        self.current_item_index = 0
        self.is_completed = False

    @property
    def current_item(self):
        """Devuelve el ítem actual en evaluación dentro de los 12 ítems del STAT."""
        if self.current_item_index < len(ALL_STAT_ITEMS):
            return ALL_STAT_ITEMS[self.current_item_index]
        return None

    def record_item_result(
        self,
        item_code: str,
        therapist_passed: bool,
        metrics: Optional[Dict[str, float]] = None,
        notes: str = "",
    ) -> ItemScore:
        """Registra la puntuación de un ítem individual y avanza al siguiente."""
        score_obj = self.scorer.evaluate_item(
            item_code=item_code,
            therapist_passed=therapist_passed,
            metrics=metrics,
            notes=notes,
        )
        self.item_scores[item_code] = score_obj
        return score_obj

    def advance_item(self) -> bool:
        """Avanza al siguiente ítem del STAT. Retorna True si la sesión terminó."""
        self.current_item_index += 1
        if self.current_item_index >= len(ALL_STAT_ITEMS):
            self.is_completed = True
            self.ended_at = datetime.now(timezone.utc).isoformat()
            return True
        return False

    def evaluate_session(self) -> Dict[str, Any]:
        """Calcula los resultados por dominio y el nivel global de riesgo del STAT."""
        domain_results = self.scorer.calculate_domain_results(self.item_scores)
        risk_level, failed_domains_count, explanation = self.scorer.compute_overall_risk(domain_results)

        return {
            "session_id": self.session_id,
            "patient": self.patient.to_dict(),
            "started_at": self.started_at,
            "ended_at": self.ended_at or datetime.now(timezone.utc).isoformat(),
            "is_completed": self.is_completed,
            "items_evaluated": len(self.item_scores),
            "items_total": len(ALL_STAT_ITEMS),
            "item_scores": {
                code: {
                    "score": item.score,
                    "result_str": "PASS" if item.score == 0 else "FAIL",
                    "therapist_passed": item.therapist_passed,
                    "metrics": item.raw_metrics,
                    "notes": item.notes,
                }
                for code, item in self.item_scores.items()
            },
            "domain_results": {
                domain_code.value: {
                    "domain_name": res.domain_name,
                    "items_total": res.items_total,
                    "items_failed": res.items_failed,
                    "items_passed": res.items_passed,
                    "domain_failed": res.domain_failed,
                    "status": "FAIL (Fallado)" if res.domain_failed else "PASS (Aprobado)",
                    "cutoff_rule": res.cutoff_description,
                }
                for domain_code, res in domain_results.items()
            },
            "failed_domains_count": failed_domains_count,
            "overall_risk": risk_level.value,
            "explanation": explanation,
        }

    def close(self) -> None:
        """Libera los recursos asociados al tracker."""
        self.tracker.close()
