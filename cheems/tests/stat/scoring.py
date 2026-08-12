"""Algoritmo de puntuación y cálculo de riesgo para el Test STAT."""

from typing import Dict, List, Tuple, Optional

from cheems.tests.stat.models import (
    ALL_STAT_ITEMS,
    ItemScore,
    STATDomainCode,
    STATDomainResult,
    STATItem,
    STATRiskLevel,
)


class STATScorer:
    """Motor de cálculo de puntajes, cortes de dominios y clasificación de riesgo del STAT."""

    def __init__(self) -> None:
        self._items_by_code: Dict[str, STATItem] = {item.code: item for item in ALL_STAT_ITEMS}

    def get_item(self, code: str) -> STATItem:
        """Devuelve la definición de un ítem según su código."""
        if code not in self._items_by_code:
            raise KeyError(f"Código de ítem STAT no válido: {code}")
        return self._items_by_code[code]

    def _compute_ai_suggestion(self, item_code: str, metrics: Dict[str, float]) -> Optional[bool]:
        """Calcula una sugerencia automatizada de PASS basada en MediaPipe."""
        if not metrics:
            return None
            
        if item_code in ("P-1", "P-2"):
            if metrics.get("play_functional_score", 0.0) >= 0.60 or metrics.get("symbolic_interaction_score", 0.0) >= 0.55:
                return True
        elif item_code == "R-1":
            if metrics.get("gaze_alignment_score", 0.0) >= 0.60:
                return True
        elif item_code == "R-2":
            if metrics.get("help_request_gesture_score", 0.0) >= 0.65:
                return True
        elif item_code == "DA-1":
            if metrics.get("object_show_score", 0.0) >= 0.60:
                return True
        elif item_code == "DA-2":
            if metrics.get("pointing_detected", 0.0) >= 0.70 or metrics.get("pointing_vector_confidence", 0.0) >= 0.70:
                return True
        elif item_code in ("DA-3", "DA-4"):
            if metrics.get("gaze_alignment_score", 0.0) >= 0.60 or metrics.get("gaze_head_turn_angle", 0.0) >= 25.0:
                return True
        elif item_code == "MI-1":
            if metrics.get("clapping_proximity", 0.0) >= 0.75 or metrics.get("hand_gesture_score", 0.0) >= 0.65:
                return True
        elif item_code == "MI-2":
            if metrics.get("hand_gesture_score", 0.0) >= 0.65:
                return True
        elif item_code == "MI-3":
            if metrics.get("hands_elevated_score", 0.0) >= 0.70:
                return True
        elif item_code == "MI-4":
            if metrics.get("hand_gesture_score", 0.0) >= 0.65:
                return True
                
        return None

    def evaluate_item(
        self,
        item_code: str,
        therapist_passed: bool,
        metrics: Dict[str, float] = None,
        notes: str = "",
    ) -> ItemScore:
        """Evalúa un ítem combinando el criterio del especialista y las métricas computadas por MediaPipe.
        
        Score:
            0 = PASS (Conducta aprobada / desarrollo esperado)
            1 = FAIL (Conducta no aprobada / indicador de riesgo)
        """
        metrics = metrics or {}
        ai_suggestion = self._compute_ai_suggestion(item_code, metrics)
        has_discrepancy = (ai_suggestion is not None) and (ai_suggestion != therapist_passed)

        score_value = 0 if therapist_passed else 1
        return ItemScore(
            item_code=item_code,
            score=score_value,
            therapist_passed=therapist_passed,
            ai_suggested_pass=ai_suggestion,
            has_discrepancy=has_discrepancy,
            raw_metrics=metrics,
            notes=notes,
        )

    def calculate_domain_results(
        self, item_scores: Dict[str, ItemScore]
    ) -> Dict[STATDomainCode, STATDomainResult]:
        """Calcula el estado de aprobación/fallo por cada uno de los 4 dominios del STAT.
        
        Criterios de corte por dominio del STAT:
        - PLAY: Fallo si se fallan los 2 ítems (P-1 y P-2).
        - REQUESTING: Fallo si se fallan los 2 ítems (R-1 y R-2).
        - DIRECTING ATTENTION: Fallo si se fallan 2 o más ítems de los 4 (DA-1 a DA-4).
        - MOTOR IMITATION: Fallo si se fallan 2 o más ítems de los 4 (MI-1 a MI-4).
        """
        domain_items: Dict[STATDomainCode, List[STATItem]] = {d: [] for d in STATDomainCode}
        for item in ALL_STAT_ITEMS:
            domain_items[item.domain].append(item)

        results: Dict[STATDomainCode, STATDomainResult] = {}

        for domain_code, items in domain_items.items():
            total = len(items)
            failed_count = 0
            passed_count = 0
            unevaluated_count = 0

            for item in items:
                score_obj = item_scores.get(item.code)
                if score_obj is None:
                    unevaluated_count += 1
                elif score_obj.score == 1:
                    failed_count += 1
                else:
                    passed_count += 1

            is_complete = (unevaluated_count == 0)

            # Aplicar reglas específicas de corte de dominio STAT
            cutoff = 2
            if domain_code in (STATDomainCode.PLAY, STATDomainCode.REQUESTING):
                # Dominios de 2 ítems: falla si ambos son fallados (failed_count >= 2)
                cutoff_desc = "Fallo si se fallan los 2 ítems del dominio."
            else:
                # Dominios de 4 ítems: falla si se fallan 2 o más ítems (failed_count >= 2)
                cutoff_desc = "Fallo si se fallan 2 o más ítems de los 4 del dominio."

            domain_failed = None if not is_complete else (failed_count >= cutoff)

            domain_names = {
                STATDomainCode.PLAY: "Juego",
                STATDomainCode.REQUESTING: "Petición",
                STATDomainCode.DIRECTING_ATTENTION: "Dirigir la Atención",
                STATDomainCode.MOTOR_IMITATION: "Imitación Motora",
            }

            results[domain_code] = STATDomainResult(
                domain=domain_code,
                domain_name=domain_names[domain_code],
                items_total=total,
                items_failed=failed_count,
                items_passed=passed_count,
                domain_failed=domain_failed,
                cutoff_description=cutoff_desc,
                items_unevaluated=unevaluated_count,
                is_complete=is_complete,
            )

        return results

    def compute_overall_risk(
        self, domain_results: Dict[STATDomainCode, STATDomainResult]
    ) -> Tuple[STATRiskLevel, int, str]:
        """Calcula la clasificación global de riesgo para TEA del STAT.
        
        Regla Global del STAT:
        - 2 o más dominios fallados = RIESGO ALTO DE TEA.
        - 0 o 1 dominio fallado = RIESGO BAJO DE TEA.
        """
        incomplete_domains = [d for d, r in domain_results.items() if not r.is_complete]
        if incomplete_domains:
            return STATRiskLevel.INCOMPLETE, 0, (
                "La sesión está INCOMPLETA. No se puede generar una clasificación "
                "de riesgo válida."
            )

        failed_domains_count = sum(1 for res in domain_results.values() if res.domain_failed)

        if failed_domains_count >= 2:
            risk_level = STATRiskLevel.HIGH_RISK
            explanation = (
                f"El menor presenta fallo en {failed_domains_count} de los 4 dominios del STAT "
                f"(umbral de corte: >= 2 dominios), clasificando con RIESGO ALTO de TEA."
            )
        else:
            risk_level = STATRiskLevel.LOW_RISK
            explanation = (
                f"El menor presenta fallo en {failed_domains_count} de los 4 dominios del STAT "
                f"(umbral de corte: >= 2 dominios), clasificando con RIESGO BAJO de TEA."
            )

        return risk_level, failed_domains_count, explanation
