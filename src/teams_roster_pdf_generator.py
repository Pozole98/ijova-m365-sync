"""
Generador de Informes Ejecutivos de Auditoria y Sincronizacion de Roster en Teams en PDF Institucional.
Disenado para la Direccion General y Control Escolar del Instituto Jose Vasconcelos (IJOVA).
Formato apaisado (Landscape Letter), semaforo de alineacion de nomina, KPIs y detalle de regularizacion.
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
    """Canvas de dos pasadas para calcular e imprimir dinamicamente 'Pagina X de Y'."""

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
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(36, 26, 756, 26)

        left_text = "INSTITUTO DE DESARROLLO INTEGRAL LIC. JOSE VASCONCELOS (IJOVA) • CONTROL ESCOLAR Y DIRECCION"
        self.drawString(36, 16, left_text)

        page_str = f"Pagina {self._pageNumber} de {page_count}"
        self.drawRightString(756, 16, page_str)
        self.restoreState()


def export_roster_report_pdf(roster_data: Dict[str, Any], output_path: str) -> str:
    """
    Genera un informe institucional formal en PDF (Landscape Letter)
    con cuadro de KPIs de matricula, semaforo por clase y desglose de regularizacion.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=landscape(letter),
        leftMargin=36,
        rightMargin=36,
        topMargin=32,
        bottomMargin=36
    )

    base_styles = getSampleStyleSheet()

    C_NAVY = colors.HexColor("#1B365D")
    C_NAVY_LIGHT = colors.HexColor("#2B6CB0")
    C_TEXT = colors.HexColor("#0F172A")
    C_MUTED = colors.HexColor("#475569")
    C_BORDER = colors.HexColor("#CBD5E1")
    C_ZEBRA = colors.HexColor("#F8FAFC")
    C_WHITE = colors.HexColor("#FFFFFF")

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
        fontSize=15,
        leading=18,
        textColor=C_TEXT
    )
    style_meta = ParagraphStyle(
        "MetaText",
        parent=base_styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=C_MUTED,
        alignment=2
    )
    style_section = ParagraphStyle(
        "SectionHeading",
        parent=base_styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=13,
        textColor=C_NAVY,
        spaceAfter=6
    )
    style_th = ParagraphStyle(
        "TableHeader",
        parent=base_styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9,
        textColor=C_WHITE,
        alignment=1
    )
    style_td = ParagraphStyle(
        "TableCell",
        parent=base_styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.5,
        textColor=C_TEXT
    )
    style_td_center = ParagraphStyle(
        "TableCellCenter",
        parent=style_td,
        alignment=1
    )

    story = []

    # 1. ENCABEZADO INSTITUCIONAL
    logo_path = "ijovanotext.jpeg"
    logo_elem = ""
    if os.path.exists(logo_path):
        try:
            logo_elem = RLImage(logo_path, width=0.65 * inch, height=0.65 * inch)
        except Exception:
            logo_elem = ""

    header_text = [
        Paragraph("INSTITUTO DE DESARROLLO INTEGRAL LIC. JOSE VASCONCELOS", style_inst_title),
        Paragraph("AUDITORIA INSTITUCIONAL DE ROSTER Y MATRICULA EN MICROSOFT TEAMS", style_report_title)
    ]

    timestamp_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    cycle_name = roster_data.get("cycle", "2026-2027")
    meta_text = [
        Paragraph(f"<b>Ciclo Escolar:</b> {cycle_name}<br/><b>Emision:</b> {timestamp_str}<br/><b>Ambiente:</b> Microsoft 365 Education", style_meta)
    ]

    if logo_elem:
        header_table = Table(
            [[logo_elem, header_text, meta_text]],
            colWidths=[55, 490, 175]
        )
        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
    else:
        header_table = Table(
            [[header_text, meta_text]],
            colWidths=[545, 175]
        )
        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))

    story.append(header_table)
    story.append(Spacer(1, 8))

    # 2. CUADRO DE METRICAS EJECUTIVAS (KPIs)
    total_classes = roster_data.get("total_classes", 0)
    synced_classes = roster_data.get("synced_classes", 0)
    discrepant_classes = roster_data.get("discrepant_classes", 0)
    total_missing = roster_data.get("total_missing", 0)
    total_unexpected = roster_data.get("total_unexpected", 0)
    global_sync_rate = roster_data.get("global_sync_rate", 100.0)

    kpi_boxes = [
        [
            Paragraph("<font size='7' color='#475569'>CLASES AUDITADAS</font><br/><font size='14' color='#1B365D'><b>{}</b></font>".format(total_classes), base_styles["Normal"]),
            Paragraph("<font size='7' color='#137333'>100% SINCRONIZADAS</font><br/><font size='14' color='#137333'><b>{}</b></font>".format(synced_classes), base_styles["Normal"]),
            Paragraph("<font size='7' color='#C5221F'>CON DISCREPANCIAS</font><br/><font size='14' color='#C5221F'><b>{}</b></font>".format(discrepant_classes), base_styles["Normal"]),
            Paragraph("<font size='7' color='#B06000'>ALUMNOS FALTANTES</font><br/><font size='14' color='#B06000'><b>{}</b></font>".format(total_missing), base_styles["Normal"]),
            Paragraph("<font size='7' color='#64748B'>BAJAS / NO PERTENECEN</font><br/><font size='14' color='#475569'><b>{}</b></font>".format(total_unexpected), base_styles["Normal"]),
            Paragraph("<font size='7' color='#1B365D'>ALINEACION GLOBAL</font><br/><font size='14' color='#1B365D'><b>{:.1f}%</b></font>".format(global_sync_rate), base_styles["Normal"]),
        ]
    ]

    t_kpis = Table(kpi_boxes, colWidths=[120, 120, 120, 120, 120, 120])
    t_kpis.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BORDER", (0, 0), (-1, -1), 0.5, C_BORDER),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t_kpis)
    story.append(Spacer(1, 12))

    # 3. TABLA CONSOLIDADA DE ESTADO POR CLASE
    story.append(Paragraph("1. RESUMEN DE COBERTURA DE ROSTER POR EQUIPO DE TEAMS", style_section))

    classes_list = roster_data.get("classes", [])
    t1_headers = [
        Paragraph("<b>Clase / Materia</b>", style_th),
        Paragraph("<b>Nivel y Grado</b>", style_th),
        Paragraph("<b>Docente Titular</b>", style_th),
        Paragraph("<b>Oficial</b>", style_th),
        Paragraph("<b>En Teams</b>", style_th),
        Paragraph("<b>Sincronizados</b>", style_th),
        Paragraph("<b>Faltantes</b>", style_th),
        Paragraph("<b>Bajas</b>", style_th),
        Paragraph("<b>Alineacion</b>", style_th),
        Paragraph("<b>Estado</b>", style_th),
    ]

    t1_data = [t1_headers]
    for c in classes_list:
        pct = c.get("sync_percentage", 0.0)
        c_name = c.get("team_name") or c.get("displayName") or "Sin nombre"
        c_grade = f"{c.get('grado', '')} {c.get('nivel', '')}".strip() or "General"
        teacher = c.get("teacher_name", "Sin asignar")
        oficial = c.get("official_count", 0)
        in_team = c.get("team_count", 0)
        synced = c.get("synced_count", 0)
        missing = c.get("missing_count", 0)
        unexpected = c.get("unexpected_count", 0)

        estado = "OPTIMO" if missing == 0 and unexpected == 0 else "DESALINEADO"

        row = [
            Paragraph(c_name[:34], style_td),
            Paragraph(c_grade[:20], style_td),
            Paragraph(teacher[:22], style_td),
            Paragraph(str(oficial), style_td_center),
            Paragraph(str(in_team), style_td_center),
            Paragraph(str(synced), style_td_center),
            Paragraph(f"<font color='#B06000'><b>{missing}</b></font>" if missing > 0 else "0", style_td_center),
            Paragraph(f"<font color='#C5221F'><b>{unexpected}</b></font>" if unexpected > 0 else "0", style_td_center),
            Paragraph(f"<b>{pct:.1f}%</b>", style_td_center),
            Paragraph(f"<b>{estado}</b>", style_td_center),
        ]
        t1_data.append(row)

    if len(t1_data) == 1:
        t1_data.append([
            Paragraph("No se detectaron clases para el ciclo seleccionado.", style_td),
            Paragraph("-", style_td_center), Paragraph("-", style_td_center),
            Paragraph("-", style_td_center), Paragraph("-", style_td_center),
            Paragraph("-", style_td_center), Paragraph("-", style_td_center),
            Paragraph("-", style_td_center), Paragraph("-", style_td_center),
            Paragraph("-", style_td_center),
        ])

    col_w1 = [170, 95, 110, 45, 45, 55, 45, 45, 55, 55]
    t1_table = Table(t1_data, colWidths=col_w1, repeatRows=1)
    t1_style = [
        ("BACKGROUND", (0, 0), (-1, 0), C_NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, C_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]

    for idx, c in enumerate(classes_list, start=1):
        bg = C_WHITE if idx % 2 != 0 else C_ZEBRA
        t1_style.append(("BACKGROUND", (0, idx), (-1, idx), bg))
        missing = c.get("missing_count", 0)
        unexpected = c.get("unexpected_count", 0)
        if missing == 0 and unexpected == 0:
            t1_style.append(("BACKGROUND", (9, idx), (9, idx), C_GREEN_BG))
            t1_style.append(("TEXTCOLOR", (9, idx), (9, idx), C_GREEN_TXT))
        else:
            t1_style.append(("BACKGROUND", (9, idx), (9, idx), C_RED_BG))
            t1_style.append(("TEXTCOLOR", (9, idx), (9, idx), C_RED_TXT))

    t1_table.setStyle(TableStyle(t1_style))
    story.append(t1_table)
    story.append(Spacer(1, 14))

    # 4. TABLA DE DETALLE NOMINAL DE DISCREPANCIAS
    flat_discrepancies = roster_data.get("discrepancies", [])
    if flat_discrepancies:
        story.append(KeepTogether([
            Paragraph("2. REGISTRO NOMINAL DE ALUMNOS CON DISCREPANCIA (ACCIONES DE REGULARIZACION)", style_section),
            Spacer(1, 4)
        ]))

        t2_headers = [
            Paragraph("<b>Clase / Materia</b>", style_th),
            Paragraph("<b>Matricula</b>", style_th),
            Paragraph("<b>Nombre Oficial del Alumno</b>", style_th),
            Paragraph("<b>UPN / Correo Institucional</b>", style_th),
            Paragraph("<b>Tipo de Discrepancia</b>", style_th),
            Paragraph("<b>Accion Requerida</b>", style_th),
        ]

        t2_data = [t2_headers]
        for d in flat_discrepancies:
            d_type = d.get("tipo", "FALTANTE EN TEAMS")
            action = "Inscribir a la clase en Teams" if "FALTANTE" in d_type.upper() else "Desvincular de la clase"
            is_missing = "FALTANTE" in d_type.upper()

            row = [
                Paragraph(d.get("clase", "")[:32], style_td),
                Paragraph(f"<b>{d.get('matricula', '')}</b>", style_td_center),
                Paragraph(d.get("nombre", "")[:32], style_td),
                Paragraph(d.get("upn", "")[:34], style_td),
                Paragraph(f"<font color='{'#B06000' if is_missing else '#C5221F'}'><b>{d_type}</b></font>", style_td_center),
                Paragraph(action, style_td),
            ]
            t2_data.append(row)

        col_w2 = [170, 60, 160, 150, 90, 90]
        t2_table = Table(t2_data, colWidths=col_w2, repeatRows=1)
        t2_style = [
            ("BACKGROUND", (0, 0), (-1, 0), C_NAVY_LIGHT),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, C_BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]

        for idx, d in enumerate(flat_discrepancies, start=1):
            bg = C_WHITE if idx % 2 != 0 else C_ZEBRA
            t2_style.append(("BACKGROUND", (0, idx), (-1, idx), bg))
            if "FALTANTE" in d.get("tipo", "").upper():
                t2_style.append(("BACKGROUND", (4, idx), (4, idx), C_AMBER_BG))
            else:
                t2_style.append(("BACKGROUND", (4, idx), (4, idx), C_RED_BG))

        t2_table.setStyle(TableStyle(t2_style))
        story.append(t2_table)

    # Construir documento mediante NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)
    return output_path
