"""
Motor de Inferencia IA para CHEEMS — v2 con doble modo (estimado / final).

Modo ESTIMADO: opera sobre la ventana deslizante de los últimos 90 frames.
               El resultado puede fluctuar y se muestra como guía tenue en la UI.

Modo FINAL:    opera sobre las estadísticas completas del ítem (toda la actividad).
               Usa media, desviación estándar y proporciones de tiempo.
               Este es el único veredicto que se almacena y exporta al informe.

Los umbrales clínicos están basados en la literatura del STAT y ADOS-2:
  - STAT (Stone et al., 2004): criterios de corte por dominio (DA, MI, P, RRB)
  - Referencia de atención visual: ≥ 30% del tiempo sostenida para DA-3/DA-4
"""

from __future__ import annotations

from typing import Any, Dict, Optional


# ─────────────────────────── Umbrales Clínicos ───────────────────────────────
# Estos valores representan el umbral mínimo para PASS en cada dimensión.
# Ajustar tras calibración con datos reales de la población objetivo.

_THRESHOLDS = {
    # Atención visual (Face Mesh - Euler)
    "attention_pct_pass":     0.30,   # 30% del tiempo mirando al evaluador → PASS
    "attention_pct_moderate": 0.15,   # 15-30% → FAIL intermitente
    "gaze_mean_pass":         0.45,   # Score medio de alineación → apoyo a PASS

    # Señalamiento intencional (Hands)
    "pointing_peak_pass":     0.55,   # Al menos un momento claro de señalamiento
    "pointing_mean_pass":     0.25,   # Media sostenida

    # Imitación (Hands elevadas / palmas proximales)
    "imitation_clap_pass":    0.60,   # Proximidad de muñecas
    "imitation_elev_pass":    0.50,   # Elevación de manos

    # Movimientos atípicos (Flapping / Rocking)
    "flapping_pct_alarm":     0.20,   # >20% del tiempo → indicador fuerte
    "rocking_pct_alarm":      0.15,
}


class AISuggestionEngine:
    """
    Motor de inferencia de sugerencias PASS/FAIL basado en biometría.

    No mantiene estado propio de frames — ese es el trabajo del MetricsAccumulator.
    Solo aplica las reglas clínicas sobre los datos que recibe.
    """

    # ─────────────────────────── Modo Estimado ───────────────────────────
    def evaluate_realtime(
        self,
        item_code: str,
        avg_metrics: Dict[str, float],
        frame_count: int = 0,
    ) -> Dict[str, Any]:
        """
        Evalúa el promedio de la ventana deslizante para la UI en vivo.

        Returns:
            dict con suggested_verdict (None si insuficiente), confidence,
            reasoning (etiquetado como estimado), y is_estimate=True.
        """
        MIN_FRAMES_FOR_ESTIMATE = 30

        if frame_count < MIN_FRAMES_FOR_ESTIMATE or not avg_metrics:
            return {
                "suggested_verdict": None,
                "confidence": 0.0,
                "reasoning": "Capturando datos...",
                "is_estimate": True,
                "metrics_summary": {},
            }

        result = self._apply_item_rules(
            item_code=item_code,
            gaze_score=avg_metrics.get("gaze_alignment_score", 0.0),
            attention_pct=avg_metrics.get("attention_on", 0.0),
            pointing_peak=avg_metrics.get("pointing_score", 0.0),
            clapping=avg_metrics.get("clapping_proximity", 0.0),
            elevated=avg_metrics.get("hands_elevated_score", 0.0),
            flapping_pct=avg_metrics.get("flapping_detected", 0.0),
            rocking_pct=avg_metrics.get("rocking_detected", 0.0),
            is_final=False,
        )
        result["is_estimate"] = True
        return result

    # ─────────────────────────── Modo Final ──────────────────────────────
    def evaluate_final(
        self,
        item_code: str,
        stats: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Veredicto definitivo basado en las estadísticas completas del ítem.

        Args:
            stats: Salida de MetricsAccumulator.get_final_stats()

        Returns:
            dict con suggested_verdict, confidence, reasoning detallado,
            metrics_summary con lenguaje natural, y is_estimate=False.
        """
        if not stats or stats.get("frame_count", 0) == 0:
            return {
                "suggested_verdict": None,
                "confidence": 0.0,
                "reasoning": "No se registraron datos suficientes para evaluar.",
                "is_estimate": False,
                "metrics_summary": {},
            }

        result = self._apply_item_rules(
            item_code=item_code,
            gaze_score=stats.get("gaze_alignment_score_mean", 0.0),
            attention_pct=stats.get("attention_duration_pct", 0.0),
            pointing_peak=stats.get("pointing_peak", 0.0),
            clapping=stats.get("clapping_proximity_max", 0.0),
            elevated=stats.get("hands_elevated_score_max", 0.0),
            flapping_pct=stats.get("flapping_duration_pct", 0.0),
            rocking_pct=stats.get("rocking_duration_pct", 0.0),
            is_final=True,
            raw_stats=stats,
        )
        result["is_estimate"] = False
        return result

    # ─────────────────────────── Lógica por Ítem ─────────────────────────
    def _apply_item_rules(
        self,
        item_code: str,
        gaze_score: float,
        attention_pct: float,
        pointing_peak: float,
        clapping: float,
        elevated: float,
        flapping_pct: float,
        rocking_pct: float,
        is_final: bool,
        raw_stats: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Aplica las reglas específicas de cada ítem del STAT."""
        
        prefix = ""
        t = _THRESHOLDS

        # ── Movimientos Atípicos: siempre como contexto negativo ──────────
        atypical_note = ""
        if flapping_pct > t["flapping_pct_alarm"]:
            freq = raw_stats.get("flapping_freq_mean_hz", 0.0) if raw_stats else 0.0
            pct_str = f"{flapping_pct * 100:.0f}%"
            freq_str = f"{freq:.1f} Hz" if freq > 0 else "frecuencia no determinada"
            atypical_note = f" Se detectó aleteo de manos el {pct_str} del tiempo ({freq_str})."
        if rocking_pct > t["rocking_pct_alarm"]:
            pct_str = f"{rocking_pct * 100:.0f}%"
            atypical_note += f" Balanceo de tronco presente el {pct_str} del tiempo."

        # ── Dominio: Atención Dirigida y Respuesta Social (DA, R) ─────────
        if item_code in {"DA-1", "DA-2", "DA-3", "DA-4", "R-1", "R-2"}:
            return self._rule_attention(
                item_code, attention_pct, gaze_score, pointing_peak,
                atypical_note, prefix, is_final, raw_stats
            )

        # ── Dominio: Imitación Motora (MI) ────────────────────────────────
        elif item_code in {"MI-1", "MI-2", "MI-3", "MI-4"}:
            return self._rule_imitation(
                item_code, clapping, elevated, atypical_note, prefix, is_final
            )

        # ── Dominio: Juego Funcional y Simbólico (P) ─────────────────────
        elif item_code in {"P-1", "P-2"}:
            return self._rule_play(
                item_code, gaze_score, flapping_pct, atypical_note, prefix, is_final, raw_stats
            )

        # ── Dominio: Conductas Repetitivas (RRB / M) ─────────────────────
        elif item_code.startswith("M") or item_code in {"RRB-1"}:
            return self._rule_repetitive(
                item_code, flapping_pct, rocking_pct, atypical_note, prefix, is_final, raw_stats
            )

        # ── Fallback general ──────────────────────────────────────────────
        return self._rule_general(
            gaze_score, attention_pct, atypical_note, prefix
        )

    # ─────────────────────────── Reglas Específicas ──────────────────────

    def _rule_attention(
        self, item_code, attention_pct, gaze_score, pointing_peak,
        atypical_note, prefix, is_final, raw_stats
    ) -> Dict[str, Any]:
        t = _THRESHOLDS
        attn_str = f"{attention_pct * 100:.0f}%"
        gaze_qual = "adecuada" if gaze_score > 0.6 else ("moderada" if gaze_score > 0.35 else "baja")
        point_str = f"{pointing_peak * 100:.0f}%" if pointing_peak > 0.1 else "no detectado"

        if attention_pct >= t["attention_pct_pass"] or pointing_peak >= t["pointing_peak_pass"]:
            verdict = True
            confidence = max(attention_pct / t["attention_pct_pass"], pointing_peak / t["pointing_peak_pass"])
            confidence = min(1.0, round(confidence * 0.85, 3))
            reason = (
                f"{prefix}Sugerencia: PASS — La orientación visual hacia el evaluador fue {gaze_qual}, "
                f"sostenida el {attn_str} del tiempo observado."
            )
            if pointing_peak > t["pointing_peak_pass"]:
                reason += f" Se detectó señalamiento intencional ({point_str} de intensidad)."
        elif attention_pct >= t["attention_pct_moderate"]:
            verdict = False
            confidence = round(0.60, 3)
            reason = (
                f"{prefix}Sugerencia: FAIL — La atención fue intermitente ({attn_str} del tiempo). "
                f"No alcanzó el umbral mínimo sostenido para este dominio."
            )
        else:
            verdict = False
            confidence = round(min(1.0, 1.0 - attention_pct / t["attention_pct_pass"]), 3)
            reason = (
                f"{prefix}Sugerencia: FAIL — La fijación visual fue mínima o ausente "
                f"({attn_str} del tiempo, calidad {gaze_qual})."
            )

        reason += atypical_note

        dur = raw_stats.get("duration_seconds", 0.0) if raw_stats else 0.0
        frames = raw_stats.get("frame_count", 0) if raw_stats else 0
        summary: Dict[str, str] = {
            "Atención visual sostenida": f"{attn_str} del tiempo",
            "Calidad de alineación ocular": gaze_qual,
            "Señalamiento detectado": point_str,
        }
        if is_final and dur > 0:
            summary["Duración analizada"] = f"{dur:.0f} segundos ({frames} frames)"
        if atypical_note:
            summary["Movimientos atípicos"] = atypical_note.strip()

        return {
            "suggested_verdict": verdict,
            "confidence": confidence,
            "reasoning": reason,
            "metrics_summary": summary,
        }

    def _rule_imitation(
        self, item_code, clapping, elevated, atypical_note, prefix, is_final
    ) -> Dict[str, Any]:
        t = _THRESHOLDS
        score = max(clapping, elevated)
        score_pct = f"{score * 100:.0f}%"
        qual = "clara" if score > 0.6 else ("parcial" if score > 0.35 else "ausente o mínima")

        if score >= t["imitation_clap_pass"]:
            verdict, conf = True, round(score * 0.9, 3)
            reason = (
                f"{prefix}Sugerencia: PASS — Se detectó imitación motora {qual}. "
                f"Proximidad de manos o elevación: {score_pct}."
            )
        else:
            verdict, conf = False, round(1.0 - score, 3)
            reason = (
                f"{prefix}Sugerencia: FAIL — La imitación motora fue {qual} "
                f"(marcador espacial: {score_pct})."
            )
        reason += atypical_note
        return {
            "suggested_verdict": verdict,
            "confidence": conf,
            "reasoning": reason,
            "metrics_summary": {
                "Imitación motora detectada": qual,
                "Marcador de movimiento": score_pct,
            },
        }

    def _rule_play(
        self, item_code, gaze_score, flapping_pct, atypical_note, prefix, is_final, raw_stats
    ) -> Dict[str, Any]:
        t = _THRESHOLDS
        # El juego funcional se infiere indirectamente: atención + ausencia de estereotipias
        flap_str = f"{flapping_pct * 100:.0f}%"

        if flapping_pct > t["flapping_pct_alarm"]:
            verdict, conf = False, round(flapping_pct, 3)
            reason = (
                f"{prefix}Sugerencia: FAIL — Se detectaron movimientos estereotipados "
                f"el {flap_str} del tiempo, que interrumpen el juego funcional."
            )
        elif gaze_score > 0.45:
            verdict, conf = True, round(gaze_score * 0.85, 3)
            reason = (
                f"{prefix}Sugerencia: PASS — La actividad mostró atención y participación "
                f"sin patrones repetitivos dominantes."
            )
        else:
            verdict, conf = False, round(1.0 - gaze_score, 3)
            reason = (
                f"{prefix}Sugerencia: FAIL — Participación y atención al juego insuficientes."
            )
        return {
            "suggested_verdict": verdict,
            "confidence": conf,
            "reasoning": reason,
            "metrics_summary": {
                "Movimientos atípicos": flap_str + " del tiempo",
                "Nivel de atención al juego": f"{gaze_score * 100:.0f}%",
            },
        }

    def _rule_repetitive(
        self, item_code, flapping_pct, rocking_pct, atypical_note, prefix, is_final, raw_stats
    ) -> Dict[str, Any]:
        """
        En el dominio RRB del STAT, la presencia de estereotipias motoras
        indica FAIL (conducta presente = problema detectado).
        """
        t = _THRESHOLDS
        flap_str = f"{flapping_pct * 100:.0f}%"
        rock_str = f"{rocking_pct * 100:.0f}%"
        freq_mean = raw_stats.get("flapping_freq_mean_hz", 0.0) if raw_stats else 0.0

        atypical_present = (
            flapping_pct > t["flapping_pct_alarm"] or
            rocking_pct > t["rocking_pct_alarm"]
        )

        if atypical_present:
            verdict, conf = False, round(max(flapping_pct, rocking_pct), 3)
            parts = []
            if flapping_pct > t["flapping_pct_alarm"]:
                parts.append(
                    f"aleteo de manos el {flap_str} del tiempo"
                    + (f" ({freq_mean:.1f} Hz promedio)" if freq_mean > 0 else "")
                )
            if rocking_pct > t["rocking_pct_alarm"]:
                parts.append(f"balanceo de tronco el {rock_str} del tiempo")
            reason = (
                f"{prefix}Sugerencia: FAIL — Se detectaron conductas repetitivas: "
                + " y ".join(parts) + "."
            )
        else:
            verdict, conf = True, 0.70
            reason = (
                f"{prefix}Sugerencia: PASS — No se observaron conductas motoras "
                f"repetitivas en el rango esperado."
            )

        return {
            "suggested_verdict": verdict,
            "confidence": conf,
            "reasoning": reason,
            "metrics_summary": {
                "Aleteo de manos": flap_str + " del tiempo",
                "Balanceo de tronco": rock_str + " del tiempo",
            },
        }

    def _rule_general(
        self, gaze_score, attention_pct, atypical_note, prefix
    ) -> Dict[str, Any]:
        attn_str = f"{attention_pct * 100:.0f}%"
        if gaze_score > 0.50 or attention_pct > 0.30:
            verdict, conf = True, round(max(gaze_score, attention_pct), 3)
            reason = f"{prefix}Sugerencia: PASS — Participación y atención generales adecuadas ({attn_str} del tiempo)."
        else:
            verdict, conf = False, round(1.0 - max(gaze_score, attention_pct), 3)
            reason = f"{prefix}Sugerencia: FAIL — Participación y atención generales bajas ({attn_str} del tiempo)."
        reason += atypical_note
        return {
            "suggested_verdict": verdict,
            "confidence": conf,
            "reasoning": reason,
            "metrics_summary": {"Atención general": attn_str + " del tiempo"},
        }
