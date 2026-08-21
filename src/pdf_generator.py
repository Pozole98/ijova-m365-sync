"""
Generador de Fichas y Tarjetas de Acceso a Microsoft 365 en formato PDF para alumnos.
Diseño institucional de alta calidad, con código QR y guía paso a paso para el primer inicio de sesión.
"""
import os
import io
import csv
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import qrcode
from PIL import Image

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, KeepTogether, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas


def generate_qr_buffer(data_url: str = "https://portal.office.com") -> io.BytesIO:
    """Genera una imagen de código QR de alta resolución en un buffer de memoria."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=1,
    )
    qr.add_data(data_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1A365D", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def create_student_card_flowable(student: Dict[str, Any], qr_buf: io.BytesIO, card_width: float = 3.5 * inch, card_height: float = 4.8 * inch) -> Table:
    """
    Crea una tarjeta individual estilizada de acceso a Microsoft 365.
    """
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'CardTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=10,
        textColor=colors.HexColor('#1A365D'),
        alignment=1  # Centered
    )
    sub_title_style = ParagraphStyle(
        'CardSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7,
        leading=8.5,
        textColor=colors.HexColor('#0D9488'),
        alignment=1
    )
    label_style = ParagraphStyle(
        'CardLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=6.5,
        leading=7.5,
        textColor=colors.HexColor('#64748B')
    )
    val_name_style = ParagraphStyle(
        'CardValName',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=9.5,
        textColor=colors.HexColor('#0F172A')
    )
    val_upn_style = ParagraphStyle(
        'CardValUPN',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=9.5,
        textColor=colors.HexColor('#1D4ED8')
    )
    val_pwd_style = ParagraphStyle(
        'CardValPwd',
        parent=styles['Normal'],
        fontName='Courier-Bold',
        fontSize=8.5,
        leading=10,
        textColor=colors.HexColor('#047857')
    )
    step_style = ParagraphStyle(
        'CardStep',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=5.8,
        leading=7,
        textColor=colors.HexColor('#334155')
    )

    qr_img = RLImage(qr_buf, width=0.85 * inch, height=0.85 * inch)

    # Content building
    display_name = student.get("nombre_completo") or student.get("display_name", "")
    matricula = student.get("matricula", "")
    upn = student.get("upn", "")
    pwd = student.get("password_temporal") or student.get("password", "")
    nivel = student.get("nivel", "")
    grado = student.get("grado_semestre") or student.get("grado", "")

    header_text = "<b>INSTITUTO JOSÉ VASCONCELOS</b>"
    sub_text = f"FICHA DE ACCESO MICROSOFT 365 • {nivel} ({grado})".upper()

    instr_html = (
        "<b>Primer Inicio de Sesión:</b><br/>"
        "1. Escanea el QR o entra a: <b>portal.office.com</b><br/>"
        "2. Escribe tu correo institucional y contraseña temporal.<br/>"
        "3. Crea tu contraseña personal definitiva.<br/>"
        "4. ¡Listo! Acceso a Teams, Outlook, Word y OneDrive."
    )

    card_data = [
        [Paragraph(header_text, title_style), ""],
        [Paragraph(sub_text, sub_title_style), ""],
        [
            Paragraph(f"{matricula} - {display_name}", val_name_style),
            ""
        ],
        [
            Paragraph(f"<b>CORREO:</b> <font color='#1D4ED8'>{upn}</font>", val_upn_style),
            ""
        ],
        [
            Paragraph(f"<b>CONTRASEÑA TEMPORAL:</b><br/><font color='#047857'>{pwd}</font>", val_pwd_style),
            ""
        ],
        [
            Paragraph(instr_html, step_style),
            qr_img
        ]
    ]

    card_table = Table(
        card_data,
        colWidths=[card_width - 1.1 * inch, 1.0 * inch],
        rowHeights=[14, 12, 18, 16, 22, 58]
    )

    card_table.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('SPAN', (0, 1), (1, 1)),
        ('SPAN', (0, 2), (1, 2)),
        ('SPAN', (0, 3), (1, 3)),
        ('SPAN', (0, 4), (1, 4)),
        ('ALIGN', (0, 0), (1, 1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('VALIGN', (1, 5), (1, 5), 'MIDDLE'),
        ('ALIGN', (1, 5), (1, 5), 'CENTER'),
        ('BACKGROUND', (0, 0), (-1, 1), colors.HexColor('#F1F5F9')),
        ('BACKGROUND', (0, 4), (-1, 4), colors.HexColor('#ECFDF5')),
        ('BOX', (0, 0), (-1, -1), 1.2, colors.HexColor('#1A365D')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))

    return card_table


def generate_pdf_cards_from_list(
    students: List[Dict[str, Any]],
    output_pdf_path: str,
    layout_mode: str = "cards"
) -> str:
    """
    Genera el archivo PDF con las fichas de los alumnos.
    - layout_mode='cards': Cuadrícula de 4 tarjetas por hoja (recortables).
    - layout_mode='full': 1 ficha por hoja (formato expediente).
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_pdf_path)), exist_ok=True)
    doc = SimpleDocTemplate(
        output_pdf_path,
        pagesize=letter,
        leftMargin=0.4 * inch,
        rightMargin=0.4 * inch,
        topMargin=0.4 * inch,
        bottomMargin=0.4 * inch
    )

    qr_buf = generate_qr_buffer("https://portal.office.com")
    story = []

    if layout_mode == "cards":
        # Grid of 2x2 cards per page (4 cards per sheet)
        col_w = 3.65 * inch
        row_h = 4.85 * inch

        # Chunk students into groups of 4
        for chunk_idx in range(0, len(students), 4):
            chunk = students[chunk_idx:chunk_idx + 4]
            grid_cells = []

            for s in chunk:
                card = create_student_card_flowable(s, qr_buf, card_width=col_w - 0.1 * inch)
                grid_cells.append(card)

            # Fill up to 4 if last page has fewer
            while len(grid_cells) < 4:
                grid_cells.append(Paragraph("", getSampleStyleSheet()['Normal']))

            page_grid_data = [
                [grid_cells[0], grid_cells[1]],
                [grid_cells[2], grid_cells[3]]
            ]

            grid_table = Table(
                page_grid_data,
                colWidths=[col_w, col_w],
                rowHeights=[row_h, row_h]
            )
            grid_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))

            story.append(grid_table)
            if chunk_idx + 4 < len(students):
                story.append(PageBreak())

    else:
        # Full-page individual format (1 student per page)
        styles = getSampleStyleSheet()
        for idx, s in enumerate(students):
            display_name = s.get("nombre_completo") or s.get("display_name", "")
            matricula = s.get("matricula", "")
            upn = s.get("upn", "")
            pwd = s.get("password_temporal") or s.get("password", "")
            nivel = s.get("nivel", "")
            grado = s.get("grado_semestre") or s.get("grado", "")

            # Single full page content
            full_card = create_student_card_flowable(s, qr_buf, card_width=6.8 * inch, card_height=3.5 * inch)
            story.append(Spacer(1, 0.5 * inch))
            story.append(full_card)
            story.append(Spacer(1, 0.5 * inch))

            notes = Paragraph(
                "<b>Nota Importante para Padres de Familia y Alumnos:</b><br/>"
                "• Esta cuenta es de uso estrictamente educativo y da acceso a la plataforma oficial de clases de la institución.<br/>"
                "• Al ingresar por primera vez, el sistema solicitará el cambio de contraseña temporal a una propia.<br/>"
                "• Por seguridad, conserve este documento en un lugar seguro.",
                styles['Normal']
            )
            story.append(notes)

            if idx < len(students) - 1:
                story.append(PageBreak())

    doc.build(story)
    return output_pdf_path


def generate_pdf_from_credentials_csv(
    csv_file_path: str,
    output_pdf_path: Optional[str] = None,
    layout_mode: str = "cards"
) -> str:
    """
    Lee un archivo CSV de credenciales (de secrets/) y genera el PDF de tarjetas de acceso.
    """
    if not os.path.exists(csv_file_path):
        raise FileNotFoundError(f"No se encontró el archivo de credenciales: {csv_file_path}")

    students: List[Dict[str, Any]] = []
    with open(csv_file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            students.append(row)

    if not output_pdf_path:
        base_name = os.path.splitext(os.path.basename(csv_file_path))[0]
        output_pdf_path = os.path.join("reports", f"{base_name}.pdf")

    return generate_pdf_cards_from_list(students, output_pdf_path, layout_mode=layout_mode)
