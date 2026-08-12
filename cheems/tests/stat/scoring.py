"""Algoritmo de puntuación y cálculo de riesgo para el Test STAT."""

from typing import Dict, List, Tuple

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
        # Por defecto, el resultado respeta el criterio clínico final del terapeuta,
        # pero se pueden ajustar banderas de concordancia con MediaPipe.
        passed = therapist_passed

        # Ejemplo de refinamiento automatizado por MediaPipe si las métricas están presentes:
        if "hand_gesture_score" in metrics and item_code in ("MI-1", "MI-2", "MI-3", "MI-4"):
            # Si MediaPipe detecta alta precisión en el gesto imitativo (>= 0.65), apoya la aprobación
            if metrics["hand_gesture_score"] >= 0.65:
                passed = True
        elif "gaze_alignment_score" in metrics and item_code in ("DA-3", "DA-4"):
            # Si MediaPipe detecta alineación de mirada/rostro adecuada (>= 0.60)
            if metrics["gaze_alignment_score"] >= 0.60:
                passed = True

        score_value = 0 if passed else 1
        return ItemScore(
            item_code=item_code,
            score=score_value,
            therapist_passed=therapist_passed,
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

            for item in items:
                score_obj = item_scores.get(item.code)
                if score_obj is None or score_obj.score == 1:
                    failed_count += 1
                else:
                    passed_count += 1

            # Aplicar reglas específicas de corte de dominio STAT
            if domain_code in (STATDomainCode.PLAY, STATDomainCode.REQUESTING):
                # Dominios de 2 ítems: falla si ambos son fallados (failed_count >= 2)
                domain_failed = failed_count >= 2
                cutoff_desc = "Fallo si se fallan los 2 ítems del dominio."
            else:
                # Dominios de 4 ítems: falla si se fallan 2 o más ítems (failed_count >= 2)
                domain_failed = failed_count >= 2
                cutoff_desc = "Fallo si se fallan 2 o más ítems de los 4 del dominio."

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
