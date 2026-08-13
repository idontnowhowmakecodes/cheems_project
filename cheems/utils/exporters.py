import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional

from cheems.security.crypto import MedicalDataCryptor


def anonymize_session_data(session_data: Dict[str, Any]) -> Dict[str, Any]:
    """Crea una copia anonimizada de los datos de la sesión (PII ofuscado)."""
    data = deepcopy(session_data)
    patient = data.get("patient", {})
    if patient:
        raw_id = str(patient.get("patient_id", "UNKNOWN"))
        anon_id = MedicalDataCryptor.pseudonymize_id(raw_id)
        patient["full_name"] = f"Paciente Protegido ({anon_id})"
        patient["patient_id"] = anon_id
        patient["notes"] = "[INFORMACIÓN PRIVADA OFUSCADA POR PROTOCOLO]"
        data["patient"] = patient
    return data


def export_stat_to_json(session_data: Dict[str, Any], output_path: Path, anonymize: bool = False) -> Path:
    """Guarda el informe estructurado del Test STAT en formato JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = anonymize_session_data(session_data) if anonymize else session_data
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)
    return output_path


def export_stat_to_html(session_data: Dict[str, Any], output_path: Path) -> Path:
    """Genera un reporte clínico formateado en HTML listo para abrir en cualquier navegador o imprimir."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    patient = session_data.get("patient", {})
    overall_risk = session_data.get("overall_risk", "N/A")
    explanation = session_data.get("explanation", "")
    domain_results = session_data.get("domain_results", {})
    item_scores = session_data.get("item_scores", {})
    notes = session_data.get("specialist_validation_notes", "")

    is_high_risk = "Alto" in overall_risk
    is_incomplete = "Incompleta" in overall_risk
    risk_color = "#f0ad4e" if is_incomplete else ("#d9534f" if is_high_risk else "#28a745")

    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Informe STAT - CHEEMS - {patient.get('full_name', 'Paciente')}</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 30px; background-color: #f8f9fa; color: #333; }}
        .card {{ background: #fff; border-radius: 8px; padding: 25px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 900px; margin: 0 auto; }}
        h1 {{ color: #1a252f; border-bottom: 2px solid #007bff; padding-bottom: 10px; font-size: 24px; }}
        h2 {{ color: #2c3e50; font-size: 18px; margin-top: 25px; }}
        .risk-banner {{ background-color: {risk_color}; color: white; padding: 15px; border-radius: 6px; font-size: 18px; font-weight: bold; margin: 15px 0; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        th, td {{ border: 1px solid #dee2e6; padding: 10px; text-align: left; font-size: 14px; }}
        th {{ background-color: #e9ecef; font-weight: 600; }}
        .badge-pass {{ color: #28a745; font-weight: bold; }}
        .badge-fail {{ color: #dc3545; font-weight: bold; }}
        .footer {{ margin-top: 30px; font-size: 12px; color: #6c757d; border-top: 1px solid #e9ecef; padding-top: 10px; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>Sistema CHEEMS — Informe de Evaluación del Test STAT</h1>
        
        <h2>1. Información del Paciente</h2>
        <table>
            <tr><td><strong>Nombre Completo:</strong> {patient.get('full_name', 'N/A')}</td><td><strong>ID Paciente:</strong> {patient.get('patient_id', 'N/A')}</td></tr>
            <tr><td><strong>Edad:</strong> {patient.get('age_months', 0)} meses ({patient.get('age_years', 0)} años)</td><td><strong>Sexo:</strong> {patient.get('sex', 'N/A')}</td></tr>
            <tr><td><strong>Especialista Evaluador:</strong> {patient.get('evaluator', 'N/A')}</td><td><strong>Fecha:</strong> {(session_data.get('started_at') or '')[:10]}</td></tr>
        </table>

        <h2>2. Clasificación Algorítmica de Riesgo</h2>
        <div class="risk-banner">
            DIAGNÓSTICO PRELIMINAR: {overall_risk.upper()}<br>
            <span style="font-size: 14px; font-weight: normal;">{explanation}</span>
        </div>

        <h2>3. Resultados por Dominios del STAT (4 Dominios)</h2>
        <table>
            <thead>
                <tr><th>Dominio</th><th>Ítems Fallados / Total</th><th>Estado</th><th>Criterio de Corte</th></tr>
            </thead>
            <tbody>
"""
    for code, dom in domain_results.items():
        status_class = "badge-fail" if dom.get("domain_failed") else "badge-pass"
        html_content += f"""
                <tr>
                    <td>{dom.get('domain_name', code)}</td>
                    <td>{dom.get('items_failed', 0)} / {dom.get('items_total', 0)}</td>
                    <td class="{status_class}">{dom.get('status', 'N/A')}</td>
                    <td>{dom.get('cutoff_rule', '')}</td>
                </tr>
"""
    html_content += """
            </tbody>
        </table>

        <h2>4. Desglose Detallado de Ítems (Concordancia Clínica vs IA)</h2>
        <table>
            <thead>
                <tr><th>Código</th><th>Resultado Clínico</th><th>Sugerencia IA</th><th>Notas de Evaluación</th></tr>
            </thead>
            <tbody>
"""
    for code, item in item_scores.items():
        res_str = item.get("result_str", "N/A")
        status_class = "badge-pass" if res_str == "PASS" else "badge-fail"
        
        raw_notes = item.get("notes", "")
        ai_verdict = "N/A"
        if "[IA Sugirió: PASS]" in raw_notes:
            ai_verdict = "PASS"
            raw_notes = raw_notes.replace("[IA Sugirió: PASS]", "").strip()
        elif "[IA Sugirió: FAIL]" in raw_notes:
            ai_verdict = "FAIL"
            raw_notes = raw_notes.replace("[IA Sugirió: FAIL]", "").strip()

        obs = raw_notes if raw_notes else "Evaluación completada."
        
        ai_class = "badge-pass" if ai_verdict == "PASS" else ("badge-fail" if ai_verdict == "FAIL" else "")

        html_content += f"""
                <tr>
                    <td><strong>{code}</strong></td>
                    <td class="{status_class}">{res_str}</td>
                    <td class="{ai_class}">{ai_verdict}</td>
                    <td>{obs}</td>
                </tr>
"""
    
    notes_html = f"<p><strong>Observaciones de Validación:</strong> {notes}</p>" if notes else ""

    html_content += f"""
            </tbody>
        </table>
        {notes_html}

        <h2>5. Recomendaciones Clínicas</h2>
        <ul>
            <li>{"La evaluación no pudo ser completada. Se sugiere agendar una nueva sesión." if is_incomplete else ("Se recomienda derivación urgente a evaluación neuropediátrica/multidisciplinaria completa." if is_high_risk else "Seguimiento periódico del desarrollo infantil a los 6 meses.")}</li>
            <li>Este documento es una herramienta de soporte y debe ser validado con la evaluación clínica directa del especialista.</li>
        </ul>

        <div class="footer">
            Generado automáticamente por el Sistema CHEEMS (Clasificador Holístico de Evaluación Emocional, Motriz y Social).
        </div>
    </div>
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as file:
        file.write(html_content)
    return output_path


def export_stat_to_pdf(session_data: Dict[str, Any], output_path: Path) -> Path:
    """Genera un archivo PDF profesional del informe de evaluación STAT mediante ReportLab."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36,
        )
        story = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Heading1"],
            fontSize=20,
            leading=24,
            textColor=colors.HexColor("#1A252F"),
            alignment=1,  # Center
            spaceAfter=15,
        )
        h2_style = ParagraphStyle(
            "DocH2",
            parent=styles["Heading2"],
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#2C3E50"),
            spaceBefore=12,
            spaceAfter=6,
        )
        body_style = ParagraphStyle(
            "DocBody",
            parent=styles["BodyText"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#333333"),
        )

        patient = session_data.get("patient", {})
        overall_risk = session_data.get("overall_risk", "N/A")
        explanation = session_data.get("explanation", "")
        domain_results = session_data.get("domain_results", {})
        item_scores = session_data.get("item_scores", {})

        is_high_risk = "Alto" in overall_risk
        is_incomplete = "Incompleta" in overall_risk

        # 1. Encabezado
        story.append(Paragraph("Sistema CHEEMS — Informe de Evaluación STAT", title_style))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#007BFF"), spaceAfter=15))

        # 2. Información Paciente
        p_info_data = [
            [
                Paragraph(f"<b>Paciente:</b> {patient.get('full_name', 'N/A')}", body_style),
                Paragraph(f"<b>ID:</b> {patient.get('patient_id', 'N/A')}", body_style),
            ],
            [
                Paragraph(f"<b>Edad:</b> {patient.get('age_months', 0)} meses ({patient.get('age_years', 0)} años)", body_style),
                Paragraph(f"<b>Sexo:</b> {patient.get('sex', 'N/A')}", body_style),
            ],
            [
                Paragraph(f"<b>Especialista:</b> {patient.get('evaluator', 'N/A')}", body_style),
                Paragraph(f"<b>Fecha:</b> {(session_data.get('started_at') or '')[:10]}", body_style),
            ],
        ]
        t_patient = Table(p_info_data, colWidths=[270, 270])
        t_patient.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8F9FA")),
            ("PADDING", (0, 0), (-1, -1), 6),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#DEE2E6")),
        ]))
        story.append(t_patient)
        story.append(Spacer(1, 10))

        # 3. Banner de Riesgo
        banner_bg = colors.HexColor("#f0ad4e") if is_incomplete else (colors.HexColor("#DC3545") if is_high_risk else colors.HexColor("#28A745"))
        risk_text = f"<font color='white'><b>DIAGNÓSTICO PRELIMINAR: {overall_risk.upper()}</b><br/>{explanation}</font>"
        risk_style = ParagraphStyle("RiskText", parent=body_style, fontSize=11, leading=15, alignment=1)
        t_risk = Table([[Paragraph(risk_text, risk_style)]], colWidths=[540])
        t_risk.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), banner_bg),
            ("PADDING", (0, 0), (-1, -1), 10),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        story.append(t_risk)
        story.append(Spacer(1, 10))

        # 4. Dominios del STAT
        story.append(Paragraph("Resumen por Dominios del STAT", h2_style))
        dom_headers = ["Dominio", "Fallados / Total", "Estado", "Regla de Corte"]
        dom_table_data = [[Paragraph(f"<b>{h}</b>", body_style) for h in dom_headers]]

        for code, dom in domain_results.items():
            status_txt = f"<font color='red'><b>{dom.get('status')}</b></font>" if dom.get("domain_failed") else f"<font color='green'><b>{dom.get('status')}</b></font>"
            dom_table_data.append([
                Paragraph(dom.get("domain_name", code), body_style),
                Paragraph(f"{dom.get('items_failed')} / {dom.get('items_total')}", body_style),
                Paragraph(status_txt, body_style),
                Paragraph(dom.get("cutoff_rule", ""), body_style),
            ])

        t_dom = Table(dom_table_data, colWidths=[130, 90, 120, 200])
        t_dom.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E9ECEF")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DEE2E6")),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t_dom)
        story.append(Spacer(1, 10))

        # 5. Desglose 12 Ítems
        story.append(Paragraph("Desglose Detallado de Ítems (Concordancia Clínica vs IA)", h2_style))
        item_headers = ["Código", "Resultado Clínico", "Sugerencia IA", "Notas de Evaluación"]
        item_table_data = [[Paragraph(f"<b>{h}</b>", body_style) for h in item_headers]]

        for code, item in item_scores.items():
            res_str = item.get("result_str", "N/A")
            res_txt = f"<font color='green'><b>{res_str}</b></font>" if res_str == "PASS" else f"<font color='red'><b>{res_str}</b></font>"
            
            raw_notes = item.get("notes", "")
            ai_verdict = "N/A"
            if "[IA Sugirió: PASS]" in raw_notes:
                ai_verdict = "<font color='green'><b>PASS</b></font>"
                raw_notes = raw_notes.replace("[IA Sugirió: PASS]", "").strip()
            elif "[IA Sugirió: FAIL]" in raw_notes:
                ai_verdict = "<font color='red'><b>FAIL</b></font>"
                raw_notes = raw_notes.replace("[IA Sugirió: FAIL]", "").strip()
                
            obs = raw_notes if raw_notes else "Completado."

            item_table_data.append([
                Paragraph(f"<b>{code}</b>", body_style),
                Paragraph(res_txt, body_style),
                Paragraph(ai_verdict, body_style),
                Paragraph(obs, body_style),
            ])

        t_items = Table(item_table_data, colWidths=[70, 80, 80, 310])
        t_items.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E9ECEF")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DEE2E6")),
            ("PADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t_items)
        story.append(Spacer(1, 15))

        # 6. Recomendaciones
        story.append(Paragraph("Recomendaciones Clínicas", h2_style))
        rec_text = "La evaluación no pudo ser completada. Se sugiere agendar una nueva sesión." if is_incomplete else ("Derivación para evaluación neuropsicológica/multidisciplinaria completa." if is_high_risk else "Seguimiento estándar del desarrollo a los 6 meses.")
        story.append(Paragraph(f"• {rec_text}", body_style))
        story.append(Paragraph("• Informe de soporte generado por Sistema CHEEMS.", body_style))

        doc.build(story)
    except Exception as err:
        print(f"[!] Exportador PDF: Fallback a HTML ({err})")
        return export_stat_to_html(session_data, output_path.with_suffix(".html"))

    return output_path


def export_ados2_to_json(session_data: Dict[str, Any], output_path: Path, anonymize: bool = False) -> Path:
    """Guarda el informe estructurado del Test ADOS-2 en formato JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = anonymize_session_data(session_data) if anonymize else session_data
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)
    return output_path
