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


def create_student_card_flowable(
    student: Dict[str, Any],
    qr_buf: io.BytesIO,
    card_width: float = 3.65 * inch,
    card_height: float = 5.0 * inch,
    logo_path: str = "assets/logo_ijova.png"
) -> Table:
    """
    Crea una tarjeta individual estilizada de acceso a Microsoft 365
    con logo oficial, nombre institucional completo y código QR.
    """
    styles = getSampleStyleSheet()

    # Paleta de colores institucionales: Azul Marino Intermedio (#203A63) y Slate (#475569)
    COLOR_NAVY = colors.HexColor('#203A63')
    COLOR_NAVY_LIGHT = colors.HexColor('#2A4D80')
    COLOR_TEXT_MAIN = colors.HexColor('#0F172A')
    COLOR_BLUE_ACCENT = colors.HexColor('#1D4ED8')
    COLOR_PWD = colors.HexColor('#047857')
    COLOR_BG_HEADER = colors.HexColor('#F8FAFC')
    COLOR_BG_PWD = colors.HexColor('#ECFDF5')
    COLOR_BORDER = colors.HexColor('#94A3B8')

    title_style = ParagraphStyle(
        'CardTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.2,
        leading=8.5,
        textColor=COLOR_NAVY,
        alignment=1  # Center
    )
    sub_title_style = ParagraphStyle(
        'CardSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=6.5,
        leading=7.8,
        textColor=COLOR_NAVY_LIGHT,
        alignment=1
    )
    val_name_style = ParagraphStyle(
        'CardValName',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.8,
        leading=9.2,
        textColor=COLOR_TEXT_MAIN
    )
    val_upn_style = ParagraphStyle(
        'CardValUPN',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=8.8,
        textColor=COLOR_TEXT_MAIN
    )
    val_pwd_style = ParagraphStyle(
        'CardValPwd',
        parent=styles['Normal'],
        fontName='Courier-Bold',
        fontSize=8.5,
        leading=10,
        textColor=COLOR_PWD
    )
    step_style = ParagraphStyle(
        'CardStep',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=5.6,
        leading=6.8,
        textColor=colors.HexColor('#334155')
    )
    qr_caption_style = ParagraphStyle(
        'QRCaption',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=5.2,
        leading=6.2,
        textColor=COLOR_NAVY,
        alignment=1
    )

    qr_img = RLImage(qr_buf, width=0.85 * inch, height=0.85 * inch)

    # Logo oficial
    if os.path.exists(logo_path):
        logo_img = RLImage(logo_path, width=0.46 * inch, height=0.46 * inch)
    else:
        logo_img = Paragraph("<b>IJOVA</b>", title_style)

    display_name = student.get("nombre_completo") or student.get("display_name", "")
    matricula = student.get("matricula", "")
    upn = student.get("upn", "")
    pwd = student.get("password_temporal") or student.get("password", "")
    nivel = student.get("nivel", "")
    grado = student.get("grado_semestre") or student.get("grado", "")

    header_html = "<b>INSTITUTO DE DESARROLLO INTEGRAL<br/>LIC. JOSÉ VASCONCELOS (IJOVA)</b>"
    sub_html = f"FICHA DE ACCESO A MICROSOFT 365 • {nivel} ({grado})".upper()

    instr_html = (
        "<b>Primer Inicio de Sesión:</b><br/>"
        "1. Escanea el QR o ingresa a: <b>portal.office.com</b><br/>"
        "2. Escribe tu correo institucional y contraseña temporal.<br/>"
        "3. Define tu contraseña personal segura.<br/>"
        "4. ¡Listo! Acceso a Teams, Outlook, Word y OneDrive."
    )

    val_pwd_style = ParagraphStyle(
        'CardValPwd',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9.0,
        textColor=COLOR_TEXT_MAIN
    )

    qr_cell = Table([
        [qr_img],
        [Paragraph("portal.office.com", qr_caption_style)]
    ], colWidths=[0.90 * inch], rowHeights=[0.76 * inch, 8])
    qr_cell.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    header_cell = Table([
        [logo_img, Table([
            [Paragraph(header_html, title_style)],
            [Paragraph(sub_html, sub_title_style)]
        ], colWidths=[card_width - 0.70 * inch])]
    ], colWidths=[0.55 * inch, card_width - 0.70 * inch])
    header_cell.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
    ]))

    card_data = [
        [header_cell, ""],
        [
            Paragraph(f"<b>ALUMNO:</b> {display_name} <font color='#64748B'>({matricula})</font>", val_name_style),
            ""
        ],
        [
            Paragraph(f"<b>CORREO:</b> <font color='#1D4ED8'><b>{upn}</b></font>", val_upn_style),
            ""
        ],
        [
            Paragraph(f"<b>CONTRASEÑA TEMPORAL:</b> &nbsp;<font name='Courier-Bold' size='8.5' color='#047857'>{pwd}</font>", val_pwd_style),
            ""
        ],
        [
            Paragraph(instr_html, step_style),
            qr_cell
        ]
    ]

    card_table = Table(
        card_data,
        colWidths=[card_width - 1.0 * inch, 1.0 * inch],
        rowHeights=[38, 18, 17, 20, 70]
    )

    card_table.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('SPAN', (0, 1), (1, 1)),
        ('SPAN', (0, 2), (1, 2)),
        ('SPAN', (0, 3), (1, 3)),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('VALIGN', (1, 4), (1, 4), 'MIDDLE'),
        ('ALIGN', (1, 4), (1, 4), 'CENTER'),
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_BG_HEADER),
        ('BACKGROUND', (0, 3), (-1, 3), COLOR_BG_PWD),
        ('BOX', (0, 0), (-1, -1), 1.2, COLOR_NAVY),
        ('LINEBELOW', (0, 0), (1, 0), 0.8, COLOR_NAVY),
        ('INNERGRID', (0, 1), (-1, 3), 0.4, colors.HexColor('#E2E8F0')),
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
        leftMargin=18,
        rightMargin=18,
        topMargin=18,
        bottomMargin=18
    )

    qr_buf = generate_qr_buffer("https://portal.office.com")
    story = []

    if layout_mode == "cards":
        # Cuadrícula optimizada de 2x3 (6 tarjetas por hoja tamaño carta)
        col_w = 280
        row_h = 245

        # Agrupar alumnos de 6 en 6
        for chunk_idx in range(0, len(students), 6):
            chunk = students[chunk_idx:chunk_idx + 6]
            grid_cells = []

            for s in chunk:
                card = create_student_card_flowable(s, qr_buf, card_width=col_w - 6)
                grid_cells.append(card)

            # Rellenar celdas vacías si la última hoja tiene menos de 6
            while len(grid_cells) < 6:
                grid_cells.append(Paragraph("", getSampleStyleSheet()['Normal']))

            page_grid_data = [
                [grid_cells[0], grid_cells[1]],
                [grid_cells[2], grid_cells[3]],
                [grid_cells[4], grid_cells[5]]
            ]

            grid_table = Table(
                page_grid_data,
                colWidths=[col_w, col_w],
                rowHeights=[row_h, row_h, row_h]
            )
            grid_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]))

            story.append(grid_table)
            if chunk_idx + 6 < len(students):
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
