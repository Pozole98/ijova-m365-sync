"""
Generador de Informes Ejecutivos de Supervisión Académica y Tareas en PDF Institucional.
Diseñado para la Dirección del Instituto de Desarrollo Integral Lic. José Vasconcelos (IJOVA).
Formato apaisado (Landscape Letter), semáforo docente con código de color y bitácora de tareas.
"""
import os
from typing import Dict, Any, List
from datetime import datetime

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Image as RLImage
from reportlab.pdfgen import canvas


class NumberedCanvas(canvas.Canvas):
    """Canvas de dos pasadas para calcular e imprimir dinámicamente 'Página X de Y'."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_footer(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_footer(self, page_count: int):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        # Línea divisoria superior del pie de página (Margen izquierdo 36 pt a 756 pt)
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(36, 26, 756, 26)

        left_text = "INSTITUTO DE DESARROLLO INTEGRAL LIC. JOSÉ VASCONCELOS (IJOVA) • DIRECCIÓN GENERAL Y ACADÉMICA"
        self.drawString(36, 16, left_text)

        page_str = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(756, 16, page_str)
        self.restoreState()


def export_assignments_report_pdf(assignments_data: Dict[str, Any], output_path: str) -> str:
    """
    Genera un informe institucional formal en PDF (Landscape Letter)
    con cuadro de KPIs, semáforo docente y bitácora completa de actividades.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    # Documento horizontal con márgenes de 0.5 pulgada (36 pt)
    # Ancho total: 792 pt, Alto: 612 pt. Ancho disponible: 720 pt.
    doc = SimpleDocTemplate(
        output_path,
        pagesize=landscape(letter),
        leftMargin=36,
        rightMargin=36,
        topMargin=32,
        bottomMargin=36
    )

    # Estilos de tipografía
    base_styles = getSampleStyleSheet()

    # Colores de identidad institucional
    C_NAVY = colors.HexColor("#1B365D")
    C_NAVY_LIGHT = colors.HexColor("#2B6CB0")
    C_TEXT = colors.HexColor("#0F172A")
    C_MUTED = colors.HexColor("#475569")
    C_BORDER = colors.HexColor("#CBD5E1")
    C_ZEBRA = colors.HexColor("#F8FAFC")
    C_WHITE = colors.HexColor("#FFFFFF")

    # Colores para semáforo
    C_GREEN_BG = colors.HexColor("#E6F4EA")
    C_GREEN_TXT = colors.HexColor("#137333")
    C_AMBER_BG = colors.HexColor("#FEF7E0")
    C_AMBER_TXT = colors.HexColor("#B06000")
    C_RED_BG = colors.HexColor("#FCE8E6")
    C_RED_TXT = colors.HexColor("#C5221F")

    style_inst_title = ParagraphStyle(
        "InstTitle",
        parent=base_styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14,
        textColor=C_NAVY
    )

    style_report_title = ParagraphStyle(
        "ReportTitle",
        parent=base_styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        textColor=C_NAVY_LIGHT
    )

    style_report_meta = ParagraphStyle(
        "ReportMeta",
        parent=base_styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=C_MUTED
    )

    style_section_heading = ParagraphStyle(
        "SectionHeading",
        parent=base_styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=12,
        textColor=C_NAVY,
        spaceBefore=8,
        spaceAfter=4
    )

    style_section_sub = ParagraphStyle(
        "SectionSub",
        parent=base_styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9,
        textColor=C_MUTED,
        spaceAfter=5
    )

    style_th = ParagraphStyle(
        "TH",
        parent=base_styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9,
        textColor=C_WHITE,
        alignment=1
    )

    style_td = ParagraphStyle(
        "TD",
        parent=base_styles["Normal"],
        fontName="Helvetica",
        fontSize=7.2,
        leading=8.5,
        textColor=C_TEXT
    )

    style_td_center = ParagraphStyle(
        "TDCenter",
        parent=base_styles["Normal"],
        fontName="Helvetica",
        fontSize=7.2,
        leading=8.5,
        textColor=C_TEXT,
        alignment=1
    )

    style_td_bold_center = ParagraphStyle(
        "TDBoldCenter",
        parent=base_styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.2,
        leading=8.5,
        textColor=C_TEXT,
        alignment=1
    )

    style_kpi_num = ParagraphStyle(
        "KPINum",
        parent=base_styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=15,
        textColor=C_NAVY,
        alignment=1
    )

    style_kpi_lbl = ParagraphStyle(
        "KPILbl",
        parent=base_styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=8.5,
        textColor=C_MUTED,
        alignment=1
    )

    story = []

    # Extraer métricas consolidadas
    summary = assignments_data.get("summary", {})
    teachers = assignments_data.get("teachers_compliance") or assignments_data.get("docentes", [])
    flat_assignments = assignments_data.get("flat_assignments", [])

    if not flat_assignments:
        for c in assignments_data.get("classes", []):
            c_name = c.get("name") or c.get("displayName") or ""
            c_cycle = c.get("academic_cycle") or c.get("cycle") or ""
            c_prof = c.get("teacher_name") or c.get("teacher_upn") or ""
            for a in c.get("assignments", []):
                flat_assignments.append({
                    "materia": c_name,
                    "ciclo": c_cycle,
                    "profesor": c_prof,
                    "titulo": a.get("title", ""),
                    "fecha_asignacion": a.get("assigned_date", ""),
                    "fecha_entrega": a.get("due_date", ""),
                    "estado": a.get("status", ""),
                    "puntos": a.get("points") or a.get("max_points", 0),
                    "alumnos_asignados": a.get("submissions_count") or a.get("total_assigned", 0),
                    "entregadas": a.get("turned_in_count") or a.get("submitted_count", 0),
                    "pendientes": a.get("pending_count") or a.get("working_count", 0),
                    "tasa_entrega": a.get("turn_in_rate", 0.0)
                })

    cycle_str = str(summary.get("cycle_evaluated") or summary.get("cycle") or "2026-2027")
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M hrs")

    # =========================================================================
    # 1. ENCABEZADO INSTITUCIONAL CON LOGOTIPO
    # =========================================================================
    logo_path = os.path.join(os.path.dirname(__file__), "..", "assets", "logo_ijova.png")
    logo_cell = ""
    if os.path.exists(logo_path):
        try:
            logo_cell = RLImage(logo_path, width=44, height=44)
        except Exception:
            logo_cell = ""

    header_text_flow = [
        Paragraph("INSTITUTO DE DESARROLLO INTEGRAL LIC. JOSÉ VASCONCELOS", style_inst_title),
        Spacer(1, 2),
        Paragraph(f"INFORME OFICIAL DE SUPERVISIÓN ACADÉMICA Y TAREAS EN MICROSOFT TEAMS • CICLO {cycle_str}", style_report_title),
        Spacer(1, 2),
        Paragraph(f"Fecha de emisión: <b>{now_str}</b> • Sistema: <b>Microsoft Teams Education Graph API</b> • Confidencialidad: <b>Uso Interno de Dirección</b>", style_report_meta),
    ]

    header_table_data = [[logo_cell, header_text_flow]]
    header_table = Table(header_table_data, colWidths=[52, 668])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "CENTER"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 8))

    # =========================================================================
    # 2. CUADRO RESUMEN EJECUTIVO (KPIS)
    # =========================================================================
    total_classes = summary.get("total_classes_audited") or summary.get("total_classes", 0)
    classes_with_t = summary.get("classes_with_assignments", 0)
    total_tasks = summary.get("total_assignments_published") or summary.get("total_assignments", 0)
    total_subs = summary.get("total_students_assigned") or summary.get("total_submissions", 0)
    total_turned = summary.get("total_students_submitted") or summary.get("total_turned_in", 0)
    turn_rate = summary.get("overall_turn_in_pct") or summary.get("overall_turn_in_rate", 0.0)

    doc_activos = summary.get("teachers_active_count") or summary.get("docentes_activos", 0)
    doc_moderados = summary.get("teachers_moderate_count") or summary.get("docentes_moderados", 0)
    doc_inactivos = summary.get("teachers_inactive_count") or summary.get("docentes_inactivos", 0)

    adop_pct = round((classes_with_t / total_classes * 100), 1) if total_classes > 0 else 0.0

    kpi_data = [
        [
            [Paragraph(str(total_classes), style_kpi_num), Paragraph("Clases Auditadas", style_kpi_lbl)],
            [Paragraph(f"{classes_with_t} ({adop_pct}%)", style_kpi_num), Paragraph("Clases con Tareas", style_kpi_lbl)],
            [Paragraph(str(total_tasks), style_kpi_num), Paragraph("Tareas Publicadas", style_kpi_lbl)],
            [Paragraph(f"{total_turned} / {total_subs}", style_kpi_num), Paragraph(f"Entregas ({turn_rate}%)", style_kpi_lbl)],
            [Paragraph(str(doc_activos), style_kpi_num), Paragraph("Docentes Activos (>=4)", style_kpi_lbl)],
            [Paragraph(str(doc_moderados), style_kpi_num), Paragraph("Moderados (1-3)", style_kpi_lbl)],
            [Paragraph(str(doc_inactivos), style_kpi_num), Paragraph("Sin Tareas (0)", style_kpi_lbl)],
        ]
    ]

    kpi_col_w = 720 / 7
    kpi_table = Table(kpi_data, colWidths=[kpi_col_w] * 7)
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_ZEBRA),
        ("BOX", (0, 0), (-1, -1), 0.75, C_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, C_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 8))

    # =========================================================================
    # 3. SECCIÓN 1: SEMÁFORO DE CUMPLIMIENTO DOCENTE
    # =========================================================================
    story.append(Paragraph("1. SEMÁFORO DE CUMPLIMIENTO DOCENTE (ACTIVIDAD EN TEAMS)", style_section_heading))
    story.append(Paragraph("Criterio: <b>Activo</b> (&ge; 4 tareas publicadas) • <b>Moderado</b> (1 a 3 tareas) • <b>Inactivo</b> (0 tareas registradas en el ciclo escolar evaluado)", style_section_sub))

    docentes_headers = [
        Paragraph("Docente Titular", style_th),
        Paragraph("Correo Institucional", style_th),
        Paragraph("Materias", style_th),
        Paragraph("Tareas", style_th),
        Paragraph("Prom./Mat.", style_th),
        Paragraph("Estatus Semáforo", style_th),
        Paragraph("Materias Asignadas", style_th),
    ]

    docentes_rows = [docentes_headers]
    docentes_styles = [
        ("BACKGROUND", (0, 0), (-1, 0), C_NAVY),
        ("BOX", (0, 0), (-1, -1), 0.5, C_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, C_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]

    for idx, t in enumerate(teachers, start=1):
        st_code = t.get("status", "")
        st_label = t.get("status_label") or t.get("status_tag") or st_code

        # Determinar estilo de píldora
        if st_code == "ACTIVO" or "Activo" in st_label or "Frecuente" in st_label:
            st_style = ParagraphStyle("StA", parent=style_td_bold_center, textColor=C_GREEN_TXT)
            bg_color = C_GREEN_BG
        elif st_code == "MODERADO" or "Moderado" in st_label or "Básica" in st_label:
            st_style = ParagraphStyle("StM", parent=style_td_bold_center, textColor=C_AMBER_TXT)
            bg_color = C_AMBER_BG
        else:
            st_style = ParagraphStyle("StI", parent=style_td_bold_center, textColor=C_RED_TXT)
            bg_color = C_RED_BG

        row_cells = [
            Paragraph(t.get("name", "N/D"), style_td),
            Paragraph(t.get("upn", "N/D"), style_td),
            Paragraph(str(t.get("classes_count") or t.get("total_classes", 0)), style_td_center),
            Paragraph(str(t.get("total_assignments", 0)), style_td_center),
            Paragraph(str(t.get("avg_per_class", 0)), style_td_center),
            Paragraph(st_label, st_style),
            Paragraph(t.get("classes_list") or ", ".join(t.get("classes", [])), style_td),
        ]
        docentes_rows.append(row_cells)

        # Cebra y fondo de semáforo en columna 5 (Estatus)
        row_bg = C_ZEBRA if idx % 2 == 0 else C_WHITE
        docentes_styles.append(("BACKGROUND", (0, idx), (4, idx), row_bg))
        docentes_styles.append(("BACKGROUND", (5, idx), (5, idx), bg_color))
        docentes_styles.append(("BACKGROUND", (6, idx), (6, idx), row_bg))

    # Anchos para 720 pt totales: [140, 130, 45, 45, 50, 110, 200]
    t_docentes = Table(docentes_rows, colWidths=[140, 130, 45, 45, 50, 110, 200], repeatRows=1)
    t_docentes.setStyle(TableStyle(docentes_styles))
    story.append(t_docentes)

    # =========================================================================
    # 4. SALTO DE PÁGINA PARA LA BITÁCORA DETALLADA
    # =========================================================================
    story.append(PageBreak())

    # =========================================================================
    # 5. SECCIÓN 2: BITÁCORA DETALLADA DE ACTIVIDADES ACADÉMICAS
    # =========================================================================
    story.append(Paragraph("2. BITÁCORA DETALLADA DE TAREAS Y ENTREGAS ESTUDIANTILES", style_section_heading))
    story.append(Paragraph("Registro pormenorizado de actividades escolares publicadas en Teams, fechas límite, ponderación y nivel de entrega", style_section_sub))

    tasks_headers = [
        Paragraph("Materia / Clase Teams", style_th),
        Paragraph("Profesor Titular", style_th),
        Paragraph("Título de la Tarea", style_th),
        Paragraph("Fecha Límite", style_th),
        Paragraph("Estado", style_th),
        Paragraph("Pts", style_th),
        Paragraph("Entregas", style_th),
        Paragraph("% Cumpl.", style_th),
    ]

    tasks_rows = [tasks_headers]
    tasks_styles = [
        ("BACKGROUND", (0, 0), (-1, 0), C_NAVY),
        ("BOX", (0, 0), (-1, -1), 0.5, C_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, C_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 3.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3.5),
    ]

    if not flat_assignments:
        empty_row = [Paragraph("No se encontraron tareas registradas en este ciclo.", style_td)] + [Paragraph("", style_td)] * 7
        tasks_rows.append(empty_row)
        tasks_styles.append(("SPAN", (0, 1), (-1, 1)))
        tasks_styles.append(("ALIGN", (0, 1), (-1, 1), "CENTER"))
    else:
        for idx, a in enumerate(flat_assignments, start=1):
            raw_due = a.get("fecha_entrega") or a.get("due_date") or ""
            due_formatted = "Sin fecha"
            if raw_due:
                try:
                    dt = datetime.fromisoformat(raw_due.replace("Z", "+00:00"))
                    due_formatted = dt.strftime("%d/%m/%Y %H:%M")
                except Exception:
                    due_formatted = str(raw_due)[:16]

            pts_val = a.get("puntos") if a.get("puntos") is not None else a.get("max_points")
            pts_str = f"{pts_val} pts" if pts_val else "N/A"

            alumnos_n = a.get("alumnos_asignados") or a.get("total_assigned", 0)
            entregadas_n = a.get("entregadas") if a.get("entregadas") is not None else a.get("turned_in_count", 0)
            tasa_cumpl = a.get("tasa_entrega") if a.get("tasa_entrega") is not None else a.get("turn_in_rate", 0.0)

            st_task = str(a.get("estado") or a.get("status") or "").lower()
            if st_task in ["assigned", "published"]:
                st_task_label = "Asignada"
                st_task_style = ParagraphStyle("StTaskPub", parent=style_td_bold_center, textColor=C_GREEN_TXT)
            elif st_task == "completed":
                st_task_label = "Completada"
                st_task_style = ParagraphStyle("StTaskComp", parent=style_td_bold_center, textColor=C_NAVY_LIGHT)
            else:
                st_task_label = "Borrador"
                st_task_style = ParagraphStyle("StTaskDraft", parent=style_td_center, textColor=C_MUTED)

            tasa_style = style_td_bold_center if tasa_cumpl >= 70 else (ParagraphStyle("TasaMed", parent=style_td_bold_center, textColor=C_AMBER_TXT) if tasa_cumpl >= 40 else ParagraphStyle("TasaLow", parent=style_td_bold_center, textColor=C_RED_TXT))

            row_cells = [
                Paragraph(a.get("materia", "Sin Materia"), style_td),
                Paragraph(a.get("profesor", "Sin Profesor"), style_td),
                Paragraph(a.get("titulo", "Sin Título"), style_td),
                Paragraph(due_formatted, style_td_center),
                Paragraph(st_task_label, st_task_style),
                Paragraph(pts_str, style_td_center),
                Paragraph(f"{entregadas_n} / {alumnos_n}", style_td_center),
                Paragraph(f"{tasa_cumpl}%", tasa_style),
            ]
            tasks_rows.append(row_cells)

            row_bg = C_ZEBRA if idx % 2 == 0 else C_WHITE
            tasks_styles.append(("BACKGROUND", (0, idx), (-1, idx), row_bg))

    # Anchos para 720 pt totales: [130, 110, 165, 85, 60, 40, 65, 65]
    t_tasks = Table(tasks_rows, colWidths=[130, 110, 165, 85, 60, 40, 65, 65], repeatRows=1)
    t_tasks.setStyle(TableStyle(tasks_styles))
    story.append(t_tasks)

    # Generar documento con NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)

    return output_path
