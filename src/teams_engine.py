"""
Motor de Auditoría, Creación y Administración de Equipos y Clases en Microsoft Teams (Microsoft 365).
"""
import os
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from src.graph_client import GraphClient, GraphClientError
from src.validator import is_valid_matricula_format


def detect_team_cycle(name: str, created_at: Optional[str] = None) -> str:
    """
    Detecta el ciclo escolar del equipo bajo la regla oficial de IJOVA:
    - Si el equipo fue creado a partir del primero de agosto de 2026 (>= 2026-08-01), es del ciclo 2026-2027 ('2026-2027').
    - Si fue creado antes (< 2026-08-01), es del ciclo 2025-2026 ('2025-2026').
    """
    if created_at:
        try:
            # ISO timestamp e.g. 2026-09-14T19:14:08Z
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            cutoff = datetime(2026, 8, 1, 0, 0, 0, tzinfo=dt.tzinfo)
            if dt >= cutoff:
                return "2026-2027"
            else:
                return "2025-2026"
        except Exception:
            pass

    clean_name = (name or "").upper()
    if any(k in clean_name for k in ["26-27", "26 - 27", "2026-2027", "2026 - 2027", "26/27"]):
        return "2026-2027"
    if any(k in clean_name for k in ["25-26", "25 - 26", "2025-2026", "2025 - 2026", "25/26"]):
        return "2025-2026"

    return "2026-2027"


def detect_team_type(name: str, creation_options: Optional[List[str]] = None, specialization: Optional[str] = None) -> str:
    """
    Determina si el equipo es una Clase Educativa, un Equipo Docente/Staff o General.
    """
    if specialization == "educationClass" or "classAssignments" in (creation_options or []):
        return "CLASE"

    n = (name or "").lower()
    class_keywords = [
        "secundaria", "preparatoria", "prepa", "primaria", "preescolar",
        "semestre", "grado", "español", "matemáticas", "biología", "historia",
        "geografía", "química", "física", "filosofía", "lengua", "artes",
        "inglés", "tecnología", "computación", "ciencias", "humanidades", "1sec", "2sec", "3sec"
    ]
    if any(k in n for k in class_keywords):
        return "CLASE"

    docente_keywords = ["docente", "profesor", "maestro", "academia", "coordinación", "staff", "dirección", "personal"]
    if any(k in n for k in docente_keywords):
        return "DOCENTES"

    return "GENERAL"


def detect_creator_type(owners: Optional[List[Dict[str, Any]]]) -> str:
    """
    Clasifica si el equipo fue creado o es propiedad de un Docente/Staff, un Alumno o si es Huérfano.
    """
    if not owners:
        return "HUERFANO"

    has_student = any(
        is_valid_matricula_format((o.get("userPrincipalName") or o.get("upn") or "").split("@")[0])
        for o in owners
    )
    if has_student:
        return "ALUMNO"

    return "MAESTRO_STAFF"


def audit_all_teams(graph: GraphClient) -> Dict[str, Any]:
    """
    Ejecuta la auditoría exhaustiva de todos los equipos del tenant.
    Clasifica ciclos, tipos, docentes a cargo, anomalías y métricas globales.
    """
    raw_teams = graph.get_all_teams()
    teams_list: List[Dict[str, Any]] = []

    # Sort raw teams by creation date descending
    def get_dt(t):
        return t.get("createdDateTime") or ""

    raw_teams = sorted(raw_teams, key=get_dt, reverse=True)

    # Counters for dashboard
    c_active_2627 = 0
    c_past_cycles = 0
    c_orphans = 0
    c_empty = 0
    c_student_owned = 0
    c_classes = 0
    c_staff = 0
    c_archived = 0

    from concurrent.futures import ThreadPoolExecutor

    def process_team(t):
        team_id = t["id"]
        name = t.get("displayName", "Sin nombre")
        desc = t.get("description", "")
        mail = t.get("mail", "")
        created_at = t.get("createdDateTime", "")
        creation_opts = t.get("creationOptions", [])

        # Fetch owners and members
        try:
            owners = graph.get_team_owners(team_id)
        except Exception:
            owners = []

        try:
            members = graph.get_team_members(team_id)
        except Exception:
            members = []

        cycle = detect_team_cycle(name, created_at)
        team_type = detect_team_type(name, creation_opts)
        creator_type = detect_creator_type(owners)

        students_in_team = []
        for m in members:
            m_upn = m.get("userPrincipalName", "")
            prefix = m_upn.split("@")[0]
            if is_valid_matricula_format(prefix):
                students_in_team.append({
                    "matricula": prefix,
                    "name": m.get("displayName", prefix),
                    "upn": m_upn
                })

        created_date_str = ""
        if created_at:
            try:
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                created_date_str = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                created_date_str = str(created_at)[:10]

        return {
            "id": team_id,
            "name": name,
            "description": desc,
            "mail": mail,
            "created_datetime": created_at,
            "created_date_str": created_date_str,
            "created_date": created_at,
            "cycle": cycle,
            "academic_cycle": cycle,
            "team_type": team_type,
            "creator_type": creator_type,
            "is_archived": False,
            "owners": [
                {
                    "id": o.get("id"),
                    "name": o.get("displayName") or o.get("userPrincipalName"),
                    "upn": o.get("userPrincipalName")
                }
                for o in owners
            ],
            "members_count": len(members),
            "member_count": len(members),
            "students_count": len(students_in_team),
            "student_count": len(students_in_team),
            "students": students_in_team
        }

    with ThreadPoolExecutor(max_workers=8) as executor:
        processed_teams = list(executor.map(process_team, raw_teams))

    for t_data in processed_teams:
        flags = []
        if not t_data["owners"]:
            flags.append("SIN_PROFESOR")
            c_orphans += 1

        if t_data["members_count"] == 0:
            flags.append("VACIO")
            c_empty += 1

        if t_data["creator_type"] == "ALUMNO":
            flags.append("ALUMNO_PROPIETARIO")
            c_student_owned += 1

        if t_data["cycle"] != "2026-2027" and t_data["cycle"] != "Indeterminado":
            flags.append("CICLO_ANTERIOR")
            c_past_cycles += 1
        elif t_data["cycle"] == "2026-2027":
            c_active_2627 += 1

        if t_data["team_type"] == "CLASE":
            c_classes += 1
        elif t_data["team_type"] == "DOCENTES":
            c_staff += 1

        t_data["flags"] = flags
        teams_list.append(t_data)

    metrics = {
        "total_teams": len(teams_list),
        "active_2627": c_active_2627,
        "cycle_2026_2027": c_active_2627,
        "past_cycles": c_past_cycles,
        "total_classes": c_classes,
        "class_teams": c_classes,
        "staff_teams": c_staff,
        "orphan_teams": c_orphans,
        "empty_teams": c_empty,
        "student_owned": c_student_owned,
        "student_owned_teams": c_student_owned,
        "archived_teams": c_archived
    }

    return {
        "metrics": metrics,
        "summary": metrics,
        "teams": teams_list,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def get_team_members_detailed(graph: GraphClient, team_id: str) -> Dict[str, Any]:
    """
    Retorna el detalle nominal de profesores (propietarios) y alumnos inscritos en un equipo.
    """
    owners_raw = graph.get_team_owners(team_id)
    members_raw = graph.get_team_members(team_id)

    teachers = []
    for o in owners_raw:
        teachers.append({
            "id": o.get("id"),
            "name": o.get("displayName") or o.get("userPrincipalName"),
            "upn": o.get("userPrincipalName"),
            "mail": o.get("mail") or o.get("userPrincipalName"),
            "is_owner": True
        })

    students = []
    other_members = []
    for m in members_raw:
        m_upn = m.get("userPrincipalName", "")
        prefix = m_upn.split("@")[0]
        rec = {
            "id": m.get("id"),
            "name": m.get("displayName") or m_upn,
            "upn": m_upn,
            "mail": m.get("mail") or m_upn,
            "is_owner": any(t["id"] == m.get("id") for t in teachers)
        }
        if is_valid_matricula_format(prefix):
            rec["matricula"] = prefix
            students.append(rec)
        else:
            other_members.append(rec)

    # Sort students by matricula
    students.sort(key=lambda x: x.get("matricula", ""))

    return {
        "team_id": team_id,
        "teachers": teachers,
        "students": students,
        "other_members": other_members,
        "total_students": len(students),
        "total_teachers": len(teachers)
    }


def get_students_for_grade(school_db: Dict[str, Any], nivel: str, grado: str) -> List[Dict[str, Any]]:
    """
    Filtra los alumnos activos del colegio que corresponden exactamente al Nivel y Grado solicitados.
    """
    matched = []
    clean_nivel = nivel.strip().lower()
    clean_grado = grado.strip().lower()
    i_num_match = re.search(r'\d+', clean_grado)
    input_num = i_num_match.group(0) if i_num_match else None

    for mat, d in school_db.items():
        s_nivel = (d.get("nivel") or "").strip().lower()
        s_grado = (d.get("grado") or "").strip().lower()

        nivel_match = (clean_nivel in s_nivel or s_nivel in clean_nivel)

        d_num_match = re.search(r'\d+', s_grado)
        db_num = d_num_match.group(0) if d_num_match else None
        if input_num and db_num:
            grado_match = (input_num == db_num)
        else:
            grado_match = (clean_grado in s_grado or s_grado in clean_grado)

        if nivel_match and grado_match:
            disp = d.get("display_name") or f"{d.get('paterno', '')} {d.get('nombres', '')}".strip()
            matched.append({
                "matricula": mat,
                "display_name": disp,
                "name": disp,
                "upn": f"{mat}@ijova.com",
                "nivel": d.get("nivel"),
                "grado": d.get("grado"),
                "seccion": d.get("seccion", "A")
            })

    matched.sort(key=lambda x: x["matricula"])
    return matched


def export_teams_audit_excel(audit_data: Dict[str, Any], output_path: str) -> str:
    """
    Genera un archivo Excel oficial con la auditoría completa de los equipos de Teams.
    """
    wb = openpyxl.Workbook()

    navy_primary = "1B365D"
    navy_secondary = "2B6CB0"
    header_fill = PatternFill(start_color=navy_primary, end_color=navy_primary, fill_type="solid")
    sub_header_fill = PatternFill(start_color=navy_secondary, end_color=navy_secondary, fill_type="solid")
    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    data_font = Font(name="Segoe UI", size=10)
    data_font_bold = Font(name="Segoe UI", size=10, bold=True)
    
    thin_border = Border(
        left=Side(style='thin', color='D2D6DC'),
        right=Side(style='thin', color='D2D6DC'),
        top=Side(style='thin', color='D2D6DC'),
        bottom=Side(style='thin', color='D2D6DC')
    )
    zebra_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    white_fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")

    green_fill = PatternFill(start_color="E6F4EA", end_color="E6F4EA", fill_type="solid")
    green_font = Font(name="Segoe UI", size=10, bold=True, color="137333")

    amber_fill = PatternFill(start_color="FEF7E0", end_color="FEF7E0", fill_type="solid")
    amber_font = Font(name="Segoe UI", size=10, bold=True, color="B06000")

    red_fill = PatternFill(start_color="FCE8E6", end_color="FCE8E6", fill_type="solid")
    red_font = Font(name="Segoe UI", size=10, bold=True, color="C5221F")

    # ==========================================
    # HOJA 1: Clases Activas 2026-2027
    # ==========================================
    ws1 = wb.active
    ws1.title = "Clases Activas 26-27"
    ws1.sheet_properties.tabColor = navy_primary

    headers1 = [
        "Nombre de la Clase / Materia",
        "Tipo de Equipo",
        "Profesor(es) Titular(es)",
        "Alumnos Matriculados",
        "Total Miembros",
        "Fecha de Creación",
        "Ciclo Escolar",
        "Correo del Equipo",
        "ID de Teams (GUID)"
    ]
    ws1.append(headers1)
    for col_idx in range(1, len(headers1) + 1):
        c = ws1.cell(row=1, column=col_idx)
        c.fill = header_fill
        c.font = header_font
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = thin_border
    ws1.row_dimensions[1].height = 28

    teams_2627 = [t for t in audit_data["teams"] if (t.get("cycle") or t.get("academic_cycle")) == "2026-2027"]
    for row_idx, t in enumerate(teams_2627, start=2):
        profes = ", ".join(o.get("name", o.get("displayName", "")) for o in t.get("owners", [])) if t.get("owners") else "⚠️ Sin profesor asignado"
        row_data = [
            t.get("name", "Sin nombre"),
            t.get("team_type", "GENERAL"),
            profes,
            t.get("students_count", len(t.get("students", []))),
            t.get("members_count", t.get("member_count", 0)),
            t.get("created_date_str") or str(t.get("created_date") or t.get("created_datetime") or "")[:10],
            t.get("cycle") or t.get("academic_cycle", ""),
            t.get("mail", ""),
            t.get("id", "")
        ]
        ws1.append(row_data)
        r_fill = zebra_fill if row_idx % 2 == 0 else white_fill
        ws1.row_dimensions[row_idx].height = 20

        for col_idx, val in enumerate(row_data, start=1):
            cell = ws1.cell(row=row_idx, column=col_idx)
            cell.border = thin_border
            cell.font = data_font
            cell.fill = r_fill
            if col_idx in [2, 4, 5, 6, 7]:
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

            if col_idx == 3 and not t.get("owners"):
                cell.fill = red_fill
                cell.font = red_font

    ws1.freeze_panes = "A2"
    ws1.auto_filter.ref = f"A1:{get_column_letter(len(headers1))}{len(teams_2627) + 1}"
    for col in ws1.columns:
        max_len = max(len(str(c.value or "")) for c in col)
        col_letter = get_column_letter(col[0].column)
        ws1.column_dimensions[col_letter].width = max(max_len + 3, 14)

    # ==========================================
    # HOJA 2: Ciclos Anteriores (Histórico)
    # ==========================================
    ws2 = wb.create_sheet(title="Ciclos Anteriores")
    ws2.sheet_properties.tabColor = "4A5568"
    ws2.append(headers1)
    for col_idx in range(1, len(headers1) + 1):
        c = ws2.cell(row=1, column=col_idx)
        c.fill = PatternFill(start_color="4A5568", end_color="4A5568", fill_type="solid")
        c.font = header_font
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = thin_border
    ws2.row_dimensions[1].height = 28

    teams_past = [t for t in audit_data["teams"] if (t.get("cycle") or t.get("academic_cycle")) != "2026-2027"]
    for row_idx, t in enumerate(teams_past, start=2):
        profes = ", ".join(o.get("name", o.get("displayName", "")) for o in t.get("owners", [])) if t.get("owners") else "⚠️ Sin profesor"
        row_data = [
            t.get("name", "Sin nombre"),
            t.get("team_type", "GENERAL"),
            profes,
            t.get("students_count", len(t.get("students", []))),
            t.get("members_count", t.get("member_count", 0)),
            t.get("created_date_str") or str(t.get("created_date") or t.get("created_datetime") or "")[:10],
            t.get("cycle") or t.get("academic_cycle", ""),
            t.get("mail", ""),
            t.get("id", "")
        ]
        ws2.append(row_data)
        r_fill = zebra_fill if row_idx % 2 == 0 else white_fill
        ws2.row_dimensions[row_idx].height = 20

        for col_idx, val in enumerate(row_data, start=1):
            cell = ws2.cell(row=row_idx, column=col_idx)
            cell.border = thin_border
            cell.font = data_font
            cell.fill = r_fill
            if col_idx in [2, 4, 5, 6, 7]:
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

    ws2.freeze_panes = "A2"
    ws2.auto_filter.ref = f"A1:{get_column_letter(len(headers1))}{len(teams_past) + 1}"
    for col in ws2.columns:
        max_len = max(len(str(c.value or "")) for c in col)
        col_letter = get_column_letter(col[0].column)
        ws2.column_dimensions[col_letter].width = max(max_len + 3, 14)

    # ==========================================
    # HOJA 3: Anomalías y Huérfanos
    # ==========================================
    ws3 = wb.create_sheet(title="Anomalías y Huérfanos")
    ws3.sheet_properties.tabColor = "C5221F"

    headers3 = [
        "Equipo / Materia",
        "Anomalía Detectada",
        "Propietario(s)",
        "Miembros",
        "Ciclo",
        "Acción Recomendada",
        "ID de Teams"
    ]
    ws3.append(headers3)
    for col_idx in range(1, len(headers3) + 1):
        c = ws3.cell(row=1, column=col_idx)
        c.fill = PatternFill(start_color="8C1D40", end_color="8C1D40", fill_type="solid")
        c.font = header_font
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = thin_border
    ws3.row_dimensions[1].height = 28

    anomaly_teams = [
        t for t in audit_data["teams"]
        if t.get("flags")
        or not t.get("owners")
        or (t.get("members_count", t.get("member_count", 0))) == 0
        or t.get("creator_type") in ["ALUMNO", "HUERFANO"]
    ]
    for row_idx, t in enumerate(anomaly_teams, start=2):
        reasons = []
        rec_action = []
        flags = t.get("flags", [])
        m_count = t.get("members_count", t.get("member_count", 0))
        c_type = t.get("creator_type", "")
        cyc = t.get("cycle") or t.get("academic_cycle", "")

        if "SIN_PROFESOR" in flags or not t.get("owners"):
            reasons.append("🔴 Huérfano (Sin maestro)")
            rec_action.append("Asignar docente titular")
        if "VACIO" in flags or m_count == 0:
            reasons.append("🟡 Vacío (0 miembros)")
            rec_action.append("Eliminar o matricular alumnos")
        if "ALUMNO_PROPIETARIO" in flags or c_type == "ALUMNO":
            reasons.append("🟠 Creado por alumno")
            rec_action.append("Revisar pertinencia institucional")
        if ("CICLO_ANTERIOR" in flags or cyc != "2026-2027") and not t.get("is_archived", False):
            reasons.append("🔵 Ciclo pasado activo")
            rec_action.append("Archivar en modo solo lectura")

        profes = ", ".join(o.get("name", o.get("displayName", "")) for o in t.get("owners", [])) if t.get("owners") else "Ninguno"
        row_data = [
            t.get("name", "Sin nombre"),
            " | ".join(reasons) if reasons else "Revisión preventiva",
            profes,
            m_count,
            cyc,
            " / ".join(rec_action) if rec_action else "Conservar",
            t.get("id", "")
        ]
        ws3.append(row_data)
        r_fill = zebra_fill if row_idx % 2 == 0 else white_fill
        ws3.row_dimensions[row_idx].height = 20

        for col_idx, val in enumerate(row_data, start=1):
            cell = ws3.cell(row=row_idx, column=col_idx)
            cell.border = thin_border
            cell.font = data_font
            cell.fill = r_fill
            if col_idx in [4, 5]:
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

            if col_idx == 2:
                if "Huérfano" in val:
                    cell.fill = red_fill
                    cell.font = red_font
                else:
                    cell.fill = amber_fill
                    cell.font = amber_font

    ws3.freeze_panes = "A2"
    ws3.auto_filter.ref = f"A1:{get_column_letter(len(headers3))}{len(anomaly_teams) + 1}"
    for col in ws3.columns:
        max_len = max(len(str(c.value or "")) for c in col)
        col_letter = get_column_letter(col[0].column)
        ws3.column_dimensions[col_letter].width = max(max_len + 3, 14)

    # ==========================================
    # HOJA 4: Resumen Ejecutivo
    # ==========================================
    ws4 = wb.create_sheet(title="Resumen Ejecutivo Teams")
    ws4.sheet_properties.tabColor = "00897B"

    ws4.merge_cells("A1:E1")
    t_cell = ws4["A1"]
    t_cell.value = "INSTITUTO DE DESARROLLO INTEGRAL LIC. JOSÉ VASCONCELOS (IJOVA)"
    t_cell.font = Font(name="Segoe UI", size=14, bold=True, color="FFFFFF")
    t_cell.fill = header_fill
    t_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws4.row_dimensions[1].height = 32

    ws4.merge_cells("A2:E2")
    s_cell = ws4["A2"]
    s_cell.value = "AUDITORÍA GENERAL Y GESTIÓN DE EQUIPOS MICROSOFT TEAMS"
    s_cell.font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    s_cell.fill = sub_header_fill
    s_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws4.row_dimensions[2].height = 24

    m = audit_data.get("metrics") or audit_data.get("summary") or {}
    tot = m.get("total_teams", len(audit_data.get("teams", [])))
    active_2627 = m.get("active_2627", m.get("cycle_2026_2027", 0))
    past_cycles = m.get("past_cycles", 0)
    total_classes = m.get("total_classes", m.get("class_teams", 0))
    orphan_teams = m.get("orphan_teams", 0)
    empty_teams = m.get("empty_teams", 0)
    student_owned = m.get("student_owned", m.get("student_owned_teams", 0))

    summary_rows = [
        ("Métrica Institucional de Teams", "Cantidad", "% del Total", "Estado Operativo"),
        ("📚 Total de Equipos en el Tenant", tot, "100.0%", "Total Histórico en Cloud"),
        ("✨ Clases del Ciclo Actual (2026-2027)", active_2627, f"{(active_2627 / tot * 100):.1f}%" if tot else "0.0%", "En impartición"),
        ("🏛️ Equipos de Ciclos Anteriores (2025-2026)", past_cycles, f"{(past_cycles / tot * 100):.1f}%" if tot else "0.0%", "Candidatos a archivar"),
        ("🎓 Clases Educativas (con Tareas/OneNote)", total_classes, f"{(total_classes / tot * 100):.1f}%" if tot else "0.0%", "Plantilla Education"),
        ("🔴 Equipos Huérfanos (Sin Maestro Titular)", orphan_teams, f"{(orphan_teams / tot * 100):.1f}%" if tot else "0.0%", "Requieren atención"),
        ("🟡 Equipos Vacíos (0 Miembros)", empty_teams, f"{(empty_teams / tot * 100):.1f}%" if tot else "0.0%", "Pruebas o abandonados"),
        ("👤 Equipos Creados / Propiedad de Alumno", student_owned, f"{(student_owned / tot * 100):.1f}%" if tot else "0.0%", "Auditoría de políticas"),
    ]

    for idx, row in enumerate(summary_rows, start=4):
        ws4.row_dimensions[idx].height = 20
        for col_idx, val in enumerate(row, start=1):
            c = ws4.cell(row=idx, column=col_idx, value=val)
            c.border = thin_border
            if idx == 4:
                c.fill = header_fill
                c.font = header_font
                c.alignment = Alignment(horizontal="center", vertical="center")
            else:
                c.font = data_font_bold if "Total" in str(row[0]) else data_font
                c.fill = zebra_fill if idx % 2 == 0 else white_fill
                if col_idx in [2, 3]:
                    c.alignment = Alignment(horizontal="center", vertical="center")
                else:
                    c.alignment = Alignment(horizontal="left", vertical="center")

    ws4.column_dimensions["A"].width = 46
    ws4.column_dimensions["B"].width = 18
    ws4.column_dimensions["C"].width = 18
    ws4.column_dimensions["D"].width = 30
    ws4.column_dimensions["E"].width = 15

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    wb.save(output_path)
    return output_path


def create_class_assisted(
    graph: GraphClient,
    subject_name: str,
    nivel: str,
    grado: str,
    teacher_user_id: str,
    school_db: Dict[str, Any],
    custom_description: Optional[str] = None
) -> Dict[str, Any]:
    """
    Crea una clase educativa completa en Teams:
    1. Genera el nombre institucional estandarizado.
    2. Obtiene la lista de alumnos correspondientes al Nivel y Grado desde la base escolar.
    3. Resuelve los Object IDs de los alumnos en Entra ID.
    4. Invoca la creación mediante Graph API con la plantilla educationClass.
    """
    cycle_tag = "26-27"
    display_name = f"{subject_name.strip()} ({grado} {nivel}) - {cycle_tag}".strip()
    
    students = get_students_for_grade(school_db, nivel, grado)
    if not students:
        raise GraphClientError(f"No se encontraron alumnos activos matriculados en {nivel} - {grado}.")

    all_users = graph.get_all_users()
    upn_to_id = {u.user_principal_name.lower(): u.id for u in all_users}

    student_ids = []
    enrolled_students = []
    for s in students:
        s_upn = s["upn"].lower()
        if s_upn in upn_to_id:
            student_ids.append(upn_to_id[s_upn])
            enrolled_students.append(s)

    desc = custom_description or f"Clase oficial de {subject_name} para {grado} de {nivel} - Ciclo Escolar 2026-2027. Instituto Vasconcelos."

    res = graph.create_education_class_team(
        display_name=display_name,
        description=desc,
        teacher_user_id=teacher_user_id,
        student_user_ids=student_ids
    )
    res["enrolled_students"] = enrolled_students
    res["display_name"] = display_name
    return res

