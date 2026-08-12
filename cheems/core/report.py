"""Generador de Reportes Clínicos para la Evaluación STAT en CHEEMS."""

from typing import Any, Dict


class STATReportGenerator:
    """Genera un reporte clínico detallado y formateado del Test STAT."""

    @staticmethod
    def generate_markdown_report(evaluation_summary: Dict[str, Any]) -> str:
        """Crea un informe formateado en Markdown a partir del resumen de la sesión."""
        patient = evaluation_summary.get("patient", {})
        overall_risk = evaluation_summary.get("overall_risk", "No evaluado")
        failed_count = evaluation_summary.get("failed_domains_count", 0)
        explanation = evaluation_summary.get("explanation", "")
        domain_results = evaluation_summary.get("domain_results", {})
        item_scores = evaluation_summary.get("item_scores", {})

        is_high_risk = "Alto" in overall_risk
        is_incomplete = "Incompleta" in overall_risk

        if is_incomplete:
            alert_box = (
                f"> [!CAUTION]\n"
                f"> **DIAGNÓSTICO PRELIMINAR**: **{overall_risk.upper()}**\n"
                f"> {explanation}\n"
            )
        elif is_high_risk:
            alert_box = (
                f"> [!WARNING]\n"
                f"> **DIAGNÓSTICO PRELIMINAR**: **{overall_risk.upper()}**\n"
                f"> {explanation}\n"
            )
        else:
            alert_box = (
                f"> [!NOTE]\n"
                f"> **DIAGNÓSTICO PRELIMINAR**: **{overall_risk.upper()}**\n"
                f"> {explanation}\n"
            )

        lines = [
            "# Informe de Evaluación STAT — Sistema CHEEMS",
            "",
            "## 1. Datos del Paciente y Evaluación",
            f"- **Nombre Completo**: {patient.get('full_name', 'N/A')}",
            f"- **ID Paciente**: {patient.get('patient_id', 'N/A')}",
            f"- **Edad**: {patient.get('age_months', 0)} meses ({patient.get('age_years', 0)} años)",
            f"- **Sexo**: {patient.get('sex', 'N/A')}",
            f"- **Especialista Evaluador**: {patient.get('evaluator', 'N/A')}",
            f"- **Fecha de Evaluación**: {evaluation_summary.get('started_at', '')[:10]}",
            "",
            "## 2. Clasificación Global de Riesgo",
            alert_box,
            "",
            "## 3. Resumen por Dominios del STAT",
            "| Dominio | Ítems Fallados / Total | Estado | Regla de Corte |",
            "| --- | --- | --- | --- |",
        ]

        for code, domain in domain_results.items():
            name = domain.get("domain_name", code)
            failed = domain.get("items_failed", 0)
            total = domain.get("items_total", 0)
            status = domain.get("status", "N/A")
            rule = domain.get("cutoff_rule", "")
            lines.append(f"| {name} | {failed} / {total} | **{status}** | {rule} |")

        lines.extend([
            "",
            "## 4. Desglose Detallado de Ítems (12 Ítems)",
            "| Código | Resultado | Criterio Especialista | Notas / Métricas |",
            "| --- | --- | --- | --- |",
        ])

        for code, item_data in item_scores.items():
            result_str = item_data.get("result_str", "N/A")
            therapist_obs = "PASS" if item_data.get("therapist_passed") else "FAIL"
            notes = item_data.get("notes", "") or "Sin observaciones ad-hoc."
            lines.append(f"| {code} | **{result_str}** | {therapist_obs} | {notes} |")

        lines.extend([
            "",
            "## 5. Recomendaciones Clínicas",
            "- " + (
                "La evaluación no pudo ser completada. Se sugiere agendar una nueva sesión." if is_incomplete else
                "Se recomienda derivar al menor a una evaluación diagnóstica multidisciplinaria de neurodesarrollo de nivel secundario/terciario (p. ej., ADOS-2 completo, neuropsicología)."
                if is_high_risk
                else "El menor no cumple los criterios de corte de alto riesgo en el STAT. Se sugiere seguimiento estándar del desarrollo infantil a los 6 meses."
            ),
            "- Este informe es una herramienta complementaria para el especialista in-situ y no reemplaza el criterio médico directo.",
        ])

        return "\n".join(lines)


class ADOS2ReportGenerator:
    """Genera un reporte clínico detallado y formateado del Test ADOS-2."""

    @staticmethod
    def generate_markdown_report(evaluation_summary: Dict[str, Any]) -> str:
        patient = evaluation_summary.get("patient", {})
        classification = evaluation_summary.get("classification", "No evaluado")
        totals = evaluation_summary.get("totals", {})
        css_score = evaluation_summary.get("css_score", -1)
        item_scores = evaluation_summary.get("item_scores", {})
        module = evaluation_summary.get("module", "")
        
        is_spectrum = "Espectro" in classification or "Autismo" in classification or "Preocupación" in classification

        if classification == "Incompleta":
            alert_box = f"> [!CAUTION]\n> **RESULTADO**: **{classification.upper()}**\n> La evaluación no pudo ser completada.\n"
        elif is_spectrum:
            alert_box = f"> [!WARNING]\n> **CLASIFICACIÓN**: **{classification.upper()}**\n"
        else:
            alert_box = f"> [!NOTE]\n> **CLASIFICACIÓN**: **{classification.upper()}**\n"

        css_str = f"{css_score} / 10" if css_score > 0 else "N/A (No aplicable a este módulo/edad)"

        lines = [
            "# Informe de Evaluación ADOS-2 — Sistema CHEEMS",
            "",
            "## 1. Datos del Paciente y Evaluación",
            f"- **Nombre Completo**: {patient.get('full_name', 'N/A')}",
            f"- **ID Paciente**: {patient.get('patient_id', 'N/A')}",
            f"- **Edad**: {patient.get('age_months', 0)} meses",
            f"- **Módulo Administrado**: {module}",
            f"- **Fecha de Evaluación**: {evaluation_summary.get('started_at', '')[:10]}",
            "",
            "## 2. Clasificación y Puntajes Algorítmicos",
            alert_box,
            "",
            f"- **Total Afecto Social (SA)**: {totals.get('sa', 0)}",
            f"- **Total Comportamientos Restringidos y Repetitivos (RRB)**: {totals.get('rrb', 0)}",
            f"- **Puntuación Total (SA + RRB)**: {totals.get('overall', 0)}",
            f"- **Puntuación de Severidad Calibrada (CSS)**: {css_str}",
            "",
            "## 3. Desglose Detallado de Ítems",
            "| Código | Puntuación Original | Puntuación Convertida | Dominio |",
            "| --- | --- | --- | --- |",
        ]

        for code, data in item_scores.items():
            lines.append(f"| {code} | {data.get('raw_code')} | {data.get('converted_code')} | {data.get('domain')} |")

        lines.extend([
            "",
            "## 4. Recomendaciones Clínicas",
            "- " + ("La evaluación no pudo ser completada. Se sugiere agendar una nueva sesión." if classification == "Incompleta" else "Validar resultados con historia clínica y otras herramientas diagnósticas.")
        ])

        return "\n".join(lines)
