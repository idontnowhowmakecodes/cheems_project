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

        alert_box = (
            f"> [!WARNING]\n"
            f"> **DIAGNÓSTICO PRELIMINAR**: **{overall_risk.upper()}**\n"
            f"> {explanation}\n"
            if is_high_risk
            else
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
                "Se recomienda derivar al menor a una evaluación diagnóstica multidisciplinaria de neurodesarrollo de nivel secundario/terciario (p. ej., ADOS-2 completo, neuropsicología)."
                if is_high_risk
                else "El menor no cumple los criterios de corte de alto riesgo en el STAT. Se sugiere seguimiento estándar del desarrollo infantil a los 6 meses."
            ),
            "- Este informe es una herramienta complementaria para el especialista in-situ y no reemplaza el criterio médico directo.",
        ])

        return "\n".join(lines)
