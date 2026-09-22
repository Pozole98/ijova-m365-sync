"""
Motor de Auditoría, Creación y Administración de Equipos y Clases en Microsoft Teams (Microsoft 365).
"""
import os
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
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
        d_name = o.get("displayName") or o.get("userPrincipalName") or ""
        u_upn = o.get("userPrincipalName") or o.get("mail") or ""
        teachers.append({
            "id": o.get("id"),
            "name": d_name,
            "display_name": d_name,
            "displayName": d_name,
            "upn": u_upn,
            "user_principal_name": u_upn,
            "userPrincipalName": u_upn,
            "mail": o.get("mail") or u_upn,
            "is_owner": True
        })

    students = []
    other_members = []
    for m in members_raw:
        m_upn = m.get("userPrincipalName", "")
        prefix = m_upn.split("@")[0]
        st_name = m.get("displayName") or m_upn
        rec = {
            "id": m.get("id"),
            "name": st_name,
            "display_name": st_name,
            "displayName": st_name,
            "upn": m_upn,
            "user_principal_name": m_upn,
            "userPrincipalName": m_upn,
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
        estatus = (d.get("estatus") or "").strip().lower()
        if "baja" in estatus or "inactivo" in estatus or "egresado" in estatus:
            continue

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
    clean_grado = grado.strip()
    clean_nivel = nivel.strip()
    clean_subj = subject_name.strip()

    if clean_nivel.lower() in clean_grado.lower():
        grade_label = clean_grado
    else:
        grade_label = f"{clean_grado} {clean_nivel}".strip()

    # Si el usuario ya ingresó el formato completo con el ciclo 26-27, respetarlo sin duplicar
    if cycle_tag in clean_subj:
        display_name = clean_subj
    else:
        display_name = f"{clean_subj} ({grade_label}) - {cycle_tag}".strip()
    
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
    res["team_name"] = display_name
    if "students_enrolled_count" not in res:
        res["students_enrolled_count"] = len(enrolled_students)
    return res


def audit_class_assignments(
    graph: GraphClient,
    class_id: str,
    include_submissions: bool = True
) -> Dict[str, Any]:
    """
    Audita las tareas de una clase específica, recuperando detalles, fechas y métricas de entrega.
    """
    raw_assignments = graph.get_class_assignments(class_id)
    assignments = []

    for a in raw_assignments:
        aid = a.get("id", "")
        title = (a.get("displayName") or "Sin título").strip()
        instructions_obj = a.get("instructions")
        desc = ""
        if isinstance(instructions_obj, dict):
            desc = instructions_obj.get("content", "")
        elif isinstance(instructions_obj, str):
            desc = instructions_obj

        assigned_dt = a.get("assignedDateTime")
        due_dt = a.get("dueDateTime")
        status = a.get("status", "desconocido")
        allow_late = a.get("allowLateSubmissions", False)

        grading = a.get("grading", {})
        max_points = grading.get("maxPoints", 0) if isinstance(grading, dict) else 0

        total_assigned = 0
        submitted_count = 0
        working_count = 0
        returned_count = 0
        turn_in_rate = 0.0

        if include_submissions and aid:
            try:
                subs = graph.get_assignment_submissions(class_id, aid)
                total_assigned = len(subs)
                for s in subs:
                    st = s.get("status", "")
                    if st in ["submitted", "turnedIn", "resubmitted"]:
                        submitted_count += 1
                    elif st in ["returned"]:
                        returned_count += 1
                    else:
                        working_count += 1

                effective_turned = submitted_count + returned_count
                if total_assigned > 0:
                    turn_in_rate = round((effective_turned / total_assigned) * 100, 1)
            except Exception:
                pass

        effective_turned = submitted_count + returned_count
        assignments.append({
            "id": aid,
            "title": title,
            "instructions": desc,
            "assigned_date": assigned_dt,
            "due_date": due_dt,
            "status": status,
            "allow_late": allow_late,
            "max_points": max_points,
            "points": max_points,
            "total_assigned": total_assigned,
            "submissions_count": total_assigned,
            "submitted_count": submitted_count,
            "returned_count": returned_count,
            "turned_in_count": effective_turned,
            "working_count": working_count,
            "pending_count": working_count,
            "turn_in_rate": turn_in_rate
        })

    total_assigned_subs = sum(a.get("total_assigned", 0) for a in assignments)
    total_turned_in = sum(a.get("turned_in_count", 0) for a in assignments)
    overall_rate = round((total_turned_in / total_assigned_subs) * 100, 1) if total_assigned_subs > 0 else 0.0

    return {
        "class_id": class_id,
        "total_assignments": len(assignments),
        "assigned_count": sum(1 for a in assignments if a.get("status") == "assigned"),
        "draft_count": sum(1 for a in assignments if a.get("status") == "draft"),
        "total_submissions": total_assigned_subs,
        "total_turned_in": total_turned_in,
        "turn_in_rate": overall_rate,
        "assignments": assignments
    }


def audit_all_assignments(
    graph: GraphClient,
    cycle_filter: Optional[str] = "2026-2027",
    include_submissions: bool = True,
    teams_data: Optional[Dict[str, Any]] = None,
    target_cycle: Optional[str] = None
) -> Dict[str, Any]:
    """
    Realiza una auditoría concurrente de tareas en todas las clases del ciclo seleccionado.
    Genera métricas consolidadas, semáforo docente y bitácora detallada.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    actual_cycle = target_cycle if target_cycle is not None else cycle_filter

    if teams_data is None:
        teams_data = audit_all_teams(graph)
    all_teams = teams_data.get("teams", [])

    candidate_classes = []
    for t in all_teams:
        t_type = t.get("team_type") or t.get("tipo")
        t_cycle = t.get("academic_cycle") or t.get("cycle") or t.get("ciclo")
        if t_type == "CLASE":
            if not actual_cycle or actual_cycle == "TODOS" or t_cycle == actual_cycle:
                candidate_classes.append(t)

    results_by_id = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_team = {
            executor.submit(audit_class_assignments, graph, t["id"], include_submissions): t
            for t in candidate_classes
        }
        for future in as_completed(future_to_team):
            team = future_to_team[future]
            try:
                res = future.result()
                results_by_id[team["id"]] = res
            except Exception as e:
                results_by_id[team["id"]] = {
                    "class_id": team["id"],
                    "total_assignments": 0,
                    "assigned_count": 0,
                    "draft_count": 0,
                    "assignments": [],
                    "error": str(e)
                }

    classes_with_tasks = 0
    classes_without_tasks = 0
    total_assignments_count = 0
    total_students_assigned = 0
    total_students_submitted = 0

    teachers_dict = {}
    flat_assignments = []

    for t in candidate_classes:
        cid = t["id"]
        audit_res = results_by_id.get(cid, {})
        assignments = audit_res.get("assignments", [])
        num_tasks = len(assignments)

        t["total_assignments"] = num_tasks
        t["assignments_data"] = audit_res

        if num_tasks > 0:
            classes_with_tasks += 1
        else:
            classes_without_tasks += 1

        total_assignments_count += num_tasks

        t_name = t.get("name") or t.get("nombre") or t.get("displayName") or "Clase"
        t_cycle = t.get("cycle") or t.get("ciclo") or "2026-2027"

        owners = t.get("owners", [])
        teacher_names = [o.get("displayName") or o.get("name") or o.get("userPrincipalName", "") for o in owners]
        teacher_display = ", ".join(teacher_names) if teacher_names else "Sin Profesor Asignado"

        for o in owners:
            t_upn = (o.get("userPrincipalName") or o.get("upn") or "").lower()
            t_doc_name = o.get("displayName") or o.get("name") or t_upn
            if t_upn and not is_valid_matricula_format(t_upn.split("@")[0]):
                if t_upn not in teachers_dict:
                    teachers_dict[t_upn] = {
                        "name": t_doc_name,
                        "upn": t_upn,
                        "classes": [],
                        "total_assignments": 0,
                        "total_students_assigned": 0,
                        "total_students_submitted": 0
                    }
                teachers_dict[t_upn]["classes"].append(t_name)
                teachers_dict[t_upn]["total_assignments"] += num_tasks

        for a in assignments:
            total_students_assigned += a["total_assigned"]
            total_students_submitted += (a["submitted_count"] + a["returned_count"])
            flat_assignments.append({
                "materia": t_name,
                "ciclo": t_cycle,
                "nivel": t.get("nivel", "General"),
                "profesor": teacher_display,
                "titulo": a["title"],
                "fecha_asignacion": a["assigned_date"],
                "fecha_entrega": a["due_date"],
                "estado": a["status"],
                "puntos": a["max_points"],
                "alumnos_asignados": a["total_assigned"],
                "entregadas": a["submitted_count"] + a["returned_count"],
                "pendientes": a["working_count"],
                "tasa_entrega": a["turn_in_rate"]
            })

    teachers_compliance = []
    for t_upn, td in teachers_dict.items():
        n_classes = len(td["classes"])
        n_tasks = td["total_assignments"]
        avg_tasks = round(n_tasks / n_classes, 1) if n_classes > 0 else 0

        if n_tasks >= 4:
            status = "ACTIVO"
            status_label = "Uso Frecuente"
        elif n_tasks >= 1:
            status = "MODERADO"
            status_label = "Actividad Básica"
        else:
            status = "INACTIVO"
            status_label = "Sin Tareas Registradas"

        teachers_compliance.append({
            "name": td["name"],
            "upn": td["upn"],
            "classes_count": n_classes,
            "total_classes": n_classes,
            "classes_list": ", ".join(td["classes"]),
            "total_assignments": n_tasks,
            "avg_per_class": avg_tasks,
            "status": status,
            "status_label": status_label,
            "status_tag": f"{status.capitalize()} ({status_label})",
            "total_submissions": td.get("total_students_assigned", 0),
            "total_turned_in": td.get("total_students_submitted", 0),
            "turn_in_rate": round((td.get("total_students_submitted", 0) / td.get("total_students_assigned", 1)) * 100, 1) if td.get("total_students_assigned", 0) > 0 else 0.0
        })

    teachers_compliance.sort(key=lambda x: (x["total_assignments"], x["classes_count"]), reverse=True)

    overall_turn_in_pct = 0.0
    if total_students_assigned > 0:
        overall_turn_in_pct = round((total_students_submitted / total_students_assigned) * 100, 1)

    summary = {
        "cycle": actual_cycle or "Todos",
        "cycle_evaluated": actual_cycle or "Todos",
        "total_classes": len(candidate_classes),
        "total_classes_audited": len(candidate_classes),
        "classes_with_assignments": classes_with_tasks,
        "classes_without_assignments": classes_without_tasks,
        "total_assignments": total_assignments_count,
        "total_assignments_published": total_assignments_count,
        "total_submissions": total_students_assigned,
        "total_students_assigned": total_students_assigned,
        "total_turned_in": total_students_submitted,
        "total_students_submitted": total_students_submitted,
        "overall_turn_in_rate": overall_turn_in_pct,
        "overall_turn_in_pct": overall_turn_in_pct,
        "docentes_activos": sum(1 for t in teachers_compliance if t["status"] == "ACTIVO"),
        "teachers_active_count": sum(1 for t in teachers_compliance if t["status"] == "ACTIVO"),
        "docentes_moderados": sum(1 for t in teachers_compliance if t["status"] == "MODERADO"),
        "teachers_moderate_count": sum(1 for t in teachers_compliance if t["status"] == "MODERADO"),
        "docentes_inactivos": sum(1 for t in teachers_compliance if t["status"] == "INACTIVO"),
        "teachers_inactive_count": sum(1 for t in teachers_compliance if t["status"] == "INACTIVO")
    }

    return {
        "summary": summary,
        "classes": candidate_classes,
        "teachers_compliance": teachers_compliance,
        "docentes": teachers_compliance,
        "flat_assignments": flat_assignments
    }


def export_assignments_report_excel(assignments_data: Dict[str, Any], output_path: str) -> str:
    """
    Genera un informe en Excel (.xlsx) con 3 hojas estructuradas para dirección y administración escolar:
    - Hoja 1: Resumen Ejecutivo y Adopción
    - Hoja 2: Semáforo de Cumplimiento Docente
    - Hoja 3: Bitácora Detallada de Tareas
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
        left=Side(style="thin", color="D2D6DC"),
        right=Side(style="thin", color="D2D6DC"),
        top=Side(style="thin", color="D2D6DC"),
        bottom=Side(style="thin", color="D2D6DC")
    )
    zebra_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    white_fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")

    green_fill = PatternFill(start_color="E6F4EA", end_color="E6F4EA", fill_type="solid")
    green_font = Font(name="Segoe UI", size=10, bold=True, color="137333")
    amber_fill = PatternFill(start_color="FEF7E0", end_color="FEF7E0", fill_type="solid")
    amber_font = Font(name="Segoe UI", size=10, bold=True, color="B06000")
    red_fill = PatternFill(start_color="FCE8E6", end_color="FCE8E6", fill_type="solid")
    red_font = Font(name="Segoe UI", size=10, bold=True, color="C5221F")

    summary = assignments_data.get("summary", {})
    teachers_compliance = assignments_data.get("teachers_compliance") or assignments_data.get("docentes", [])
    flat_assignments = assignments_data.get("flat_assignments", [])

    if not flat_assignments:
        for c in assignments_data.get("classes", []):
            c_name = c.get("name") or c.get("displayName") or ""
            c_cycle = c.get("academic_cycle") or c.get("cycle") or ""
            c_nivel = c.get("nivel", "General")
            c_prof = c.get("teacher_name") or c.get("teacher_upn") or ""
            for a in c.get("assignments", []):
                flat_assignments.append({
                    "materia": c_name,
                    "ciclo": c_cycle,
                    "nivel": c_nivel,
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

    # ==========================================
    # HOJA 1: RESUMEN EJECUTIVO Y ADOPCIÓN
    # ==========================================
    ws1 = wb.active
    ws1.title = "Resumen Ejecutivo Tareas"
    ws1.sheet_properties.tabColor = navy_primary

    ws1.merge_cells("A1:E1")
    t1 = ws1["A1"]
    t1.value = "INSTITUTO DE DESARROLLO INTEGRAL LIC. JOSÉ VASCONCELOS (IJOVA)"
    t1.font = Font(name="Segoe UI", size=14, bold=True, color="FFFFFF")
    t1.fill = header_fill
    t1.alignment = Alignment(horizontal="center", vertical="center")
    ws1.row_dimensions[1].height = 32

    ws1.merge_cells("A2:E2")
    t2 = ws1["A2"]
    t2.value = f"INFORME OFICIAL DE AUDITORÍA DE TAREAS ESCOLARES EN MICROSOFT TEAMS (CICLO {summary.get('cycle_evaluated', '2026-2027')})"
    t2.font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    t2.fill = sub_header_fill
    t2.alignment = Alignment(horizontal="center", vertical="center")
    ws1.row_dimensions[2].height = 24

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    meta = [
        ("Fecha de Auditoría:", now_str),
        ("Ciclo Escolar Evaluado:", str(summary.get("cycle_evaluated", "2026-2027"))),
        ("Plataforma Evaluada:", "Microsoft Teams Education (Assignments & Submissions)"),
        ("Tipo de Autenticación:", "Microsoft Graph Education API (Application Client Secret)")
    ]
    for idx, (label, val) in enumerate(meta, start=4):
        ws1.cell(row=idx, column=1, value=label).font = data_font_bold
        ws1.cell(row=idx, column=2, value=val).font = data_font
        ws1.row_dimensions[idx].height = 20

    start_m = 9
    ws1.cell(row=start_m, column=1, value="MÉTRICAS GLOBALES DE CUMPLIMIENTO ACADÉMICO").font = Font(name="Segoe UI", size=11, bold=True, color=navy_primary)
    m_headers = ["Indicador Institucional", "Total", "Porcentaje", "Estado Operativo"]
    for c_idx, h in enumerate(m_headers, start=1):
        c = ws1.cell(row=start_m + 1, column=c_idx, value=h)
        c.fill = header_fill
        c.font = header_font
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = thin_border
    ws1.row_dimensions[start_m + 1].height = 25

    total_classes = summary.get("total_classes_audited", 0)
    classes_with_t = summary.get("classes_with_assignments", 0)
    classes_no_t = summary.get("classes_without_assignments", 0)
    pct_adop = f"{(classes_with_t / total_classes * 100):.1f}%" if total_classes > 0 else "0.0%"

    metrics_rows = [
        ("Total de Clases / Materias Auditadas", total_classes, "100.0%", "Clases Activas en Tenant"),
        ("Materias con Tareas Registradas", classes_with_t, pct_adop, "Uso Activo de Teams"),
        ("Materias sin Tareas Registradas", classes_no_t, f"{(classes_no_t / total_classes * 100):.1f}%" if total_classes > 0 else "0.0%", "Sin Actividad en Plataforma"),
        ("Total de Tareas Publicadas en el Ciclo", summary.get("total_assignments_published", 0), "-", "Actividades Escolares"),
        ("Entregas de Alumnos Recibidas", summary.get("total_students_submitted", 0), f"{summary.get('overall_turn_in_pct', 0)}%", "Cumplimiento Estudiantil"),
        ("Docentes con Uso Frecuente (>= 4 tareas)", summary.get("teachers_active_count", 0), "-", "Nivel Alto"),
        ("Docentes con Actividad Básica (1 a 3 tareas)", summary.get("teachers_moderate_count", 0), "-", "Nivel Moderado"),
        ("Docentes sin Tareas Registradas", summary.get("teachers_inactive_count", 0), "-", "Atención Requerida")
    ]

    for idx, (label, val, pct, note) in enumerate(metrics_rows, start=start_m + 2):
        ws1.row_dimensions[idx].height = 20
        c1 = ws1.cell(row=idx, column=1, value=label)
        c2 = ws1.cell(row=idx, column=2, value=val)
        c3 = ws1.cell(row=idx, column=3, value=pct)
        c4 = ws1.cell(row=idx, column=4, value=note)
        row_fill = zebra_fill if idx % 2 == 0 else white_fill
        for c in [c1, c2, c3, c4]:
            c.border = thin_border
            c.font = data_font
            c.fill = row_fill
        c2.alignment = Alignment(horizontal="center")
        c3.alignment = Alignment(horizontal="center")

    ws1.column_dimensions["A"].width = 44
    ws1.column_dimensions["B"].width = 18
    ws1.column_dimensions["C"].width = 16
    ws1.column_dimensions["D"].width = 30
    ws1.column_dimensions["E"].width = 15

    # ==========================================
    # HOJA 2: SEMÁFORO DE CUMPLIMIENTO DOCENTE
    # ==========================================
    ws2 = wb.create_sheet(title="Semaforo Cumplimiento Docente")
    ws2.sheet_properties.tabColor = "2E7D32"

    h2 = ["Docente Titular", "Correo Institucional", "Materias Asignadas", "Tareas Publicadas", "Promedio / Materia", "Estatus de Cumplimiento", "Materias"]
    ws2.append(h2)
    for col_num in range(1, len(h2) + 1):
        c = ws2.cell(row=1, column=col_num)
        c.fill = header_fill
        c.font = header_font
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = thin_border
    ws2.row_dimensions[1].height = 28

    for idx, t in enumerate(teachers_compliance, start=2):
        ws2.row_dimensions[idx].height = 20
        status_val = t.get("status_label") or t.get("status_tag") or t.get("status", "")
        row_data = [
            t.get("name", ""),
            t.get("upn", ""),
            t.get("classes_count") or t.get("total_classes", 0),
            t.get("total_assignments", 0),
            t.get("avg_per_class", 0),
            status_val,
            t.get("classes_list") or ", ".join(t.get("classes", []))
        ]
        ws2.append(row_data)
        row_fill = zebra_fill if idx % 2 == 0 else white_fill
        for col_num in range(1, len(row_data) + 1):
            cell = ws2.cell(row=idx, column=col_num)
            cell.border = thin_border
            cell.font = data_font
            cell.fill = row_fill
            if col_num in [3, 4, 5, 6]:
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

            if col_num == 6:
                st_code = t.get("status", "")
                if st_code == "ACTIVO" or "Activo" in status_val or "Frecuente" in status_val:
                    cell.fill = green_fill
                    cell.font = green_font
                elif st_code == "MODERADO" or "Moderado" in status_val or "Básica" in status_val:
                    cell.fill = amber_fill
                    cell.font = amber_font
                else:
                    cell.fill = red_fill
                    cell.font = red_font

    ws2.freeze_panes = "A2"
    ws2.auto_filter.ref = f"A1:{get_column_letter(len(h2))}{len(teachers_compliance) + 1}"
    for col in ws2.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws2.column_dimensions[col_letter].width = min(max(max_len + 4, 14), 50)

    # ==========================================
    # HOJA 3: BITÁCORA DETALLADA DE TAREAS
    # ==========================================
    ws3 = wb.create_sheet(title="Bitacora Detallada de Tareas")
    ws3.sheet_properties.tabColor = "0288D1"

    h3 = [
        "Materia / Clase Teams",
        "Ciclo",
        "Nivel",
        "Profesor(es) Titular(es)",
        "Título de la Tarea",
        "Fecha de Asignación",
        "Fecha Límite de Entrega",
        "Estado",
        "Puntos Máx.",
        "Alumnos Asignados",
        "Entregadas",
        "Pendientes",
        "% Cumplimiento"
    ]
    ws3.append(h3)
    for col_num in range(1, len(h3) + 1):
        c = ws3.cell(row=1, column=col_num)
        c.fill = header_fill
        c.font = header_font
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = thin_border
    ws3.row_dimensions[1].height = 28

    for idx, a in enumerate(flat_assignments, start=2):
        ws3.row_dimensions[idx].height = 20
        # Formatear fechas ISO para Excel
        def fmt_dt(dt_str):
            if not dt_str:
                return ""
            try:
                return dt_str.replace("T", " ").replace("Z", "")[:19]
            except Exception:
                return str(dt_str)

        row_data = [
            a["materia"],
            a["ciclo"],
            a["nivel"],
            a["profesor"],
            a["titulo"],
            fmt_dt(a["fecha_asignacion"]),
            fmt_dt(a["fecha_entrega"]),
            a["estado"].capitalize() if a["estado"] else "",
            a["puntos"],
            a["alumnos_asignados"],
            a["entregadas"],
            a["pendientes"],
            f"{a['tasa_entrega']}%"
        ]
        ws3.append(row_data)
        row_fill = zebra_fill if idx % 2 == 0 else white_fill
        for col_num, val in enumerate(row_data, start=1):
            cell = ws3.cell(row=idx, column=col_num)
            cell.border = thin_border
            cell.font = data_font
            cell.fill = row_fill
            if col_num in [2, 3, 6, 7, 8, 9, 10, 11, 12, 13]:
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

            if col_num == 13:
                if a["tasa_entrega"] >= 70:
                    cell.fill = green_fill
                    cell.font = green_font
                elif a["tasa_entrega"] >= 40:
                    cell.fill = amber_fill
                    cell.font = amber_font
                elif a["alumnos_asignados"] > 0:
                    cell.fill = red_fill
                    cell.font = red_font

    ws3.freeze_panes = "A2"
    ws3.auto_filter.ref = f"A1:{get_column_letter(len(h3))}{len(flat_assignments) + 1}"
    for col in ws3.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws3.column_dimensions[col_letter].width = min(max(max_len + 4, 14), 45)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    wb.save(output_path)
    return output_path


# Re-exportar generador institucional de informe de tareas en PDF
from src.teams_pdf_generator import export_assignments_report_pdf
# Re-exportar generador institucional de informe de roster en PDF
from src.teams_roster_pdf_generator import export_roster_report_pdf


def detect_grade_and_nivel_from_text(name: str, desc: str = "") -> Tuple[Optional[str], Optional[str]]:
    """
    Infiere el nivel educativo y grado escolar a partir del nombre o descripcion de la clase.
    """
    text = f"{name or ''} {desc or ''}".lower()

    # Semestres de Preparatoria
    sem_patterns = [
        (r"1\s*(?:er|°|ro)?\s*semestre", "1er Semestre", "Preparatoria"),
        (r"2\s*(?:do|°)?\s*semestre", "2do Semestre", "Preparatoria"),
        (r"3\s*(?:er|°|ro)?\s*semestre", "3er Semestre", "Preparatoria"),
        (r"4\s*(?:to|°)?\s*semestre", "4to Semestre", "Preparatoria"),
        (r"5\s*(?:to|°)?\s*semestre", "5to Semestre", "Preparatoria"),
        (r"6\s*(?:to|°)?\s*semestre", "6to Semestre", "Preparatoria"),
    ]
    for pattern, grado, nivel in sem_patterns:
        if re.search(pattern, text):
            return nivel, grado

    # Grados de Secundaria
    sec_patterns = [
        (r"1\s*(?:er|°|ero|ro)?\s*(?:de\s*)?secundaria", "1° Secundaria", "Secundaria"),
        (r"2\s*(?:do|°)?\s*(?:de\s*)?secundaria", "2° Secundaria", "Secundaria"),
        (r"3\s*(?:er|°|ero|ro)?\s*(?:de\s*)?secundaria", "3° Secundaria", "Secundaria"),
    ]
    for pattern, grado, nivel in sec_patterns:
        if re.search(pattern, text):
            return nivel, grado

    # Grados de Primaria
    prim_patterns = [
        (r"1\s*(?:er|°|ero|ro)?\s*(?:de\s*)?primaria", "1° Primaria", "Primaria"),
        (r"2\s*(?:do|°)?\s*(?:de\s*)?primaria", "2° Primaria", "Primaria"),
        (r"3\s*(?:er|°|ero|ro)?\s*(?:de\s*)?primaria", "3° Primaria", "Primaria"),
        (r"4\s*(?:to|°)?\s*(?:de\s*)?primaria", "4° Primaria", "Primaria"),
        (r"5\s*(?:to|°)?\s*(?:de\s*)?primaria", "5° Primaria", "Primaria"),
        (r"6\s*(?:to|°)?\s*(?:de\s*)?primaria", "6° Primaria", "Primaria"),
    ]
    for pattern, grado, nivel in prim_patterns:
        if re.search(pattern, text):
            return nivel, grado

    # Grados de Preescolar
    pre_patterns = [
        (r"1\s*(?:er|°|ero|ro)?\s*(?:de\s*)?preescolar", "1° Preescolar", "Preescolar"),
        (r"2\s*(?:do|°)?\s*(?:de\s*)?preescolar", "2° Preescolar", "Preescolar"),
        (r"3\s*(?:er|°|ero|ro)?\s*(?:de\s*)?preescolar", "3° Preescolar", "Preescolar"),
    ]
    for pattern, grado, nivel in pre_patterns:
        if re.search(pattern, text):
            return nivel, grado

    # Solo nivel si no se especifica grado
    if "preparatoria" in text or "prepa" in text:
        return "Preparatoria", None
    if "secundaria" in text:
        return "Secundaria", None
    if "primaria" in text:
        return "Primaria", None
    if "preescolar" in text or "kinder" in text:
        return "Preescolar", None

    return None, None


def audit_class_roster(
    graph: GraphClient,
    team_id: str,
    nivel: Optional[str] = None,
    grado: Optional[str] = None,
    school_db: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Audita los miembros de una clase educativa en Teams comparandolos contra la base de datos oficial del grado.
    Identifica:
      - Alumnos sincronizados (presentes en ambos)
      - Alumnos faltantes (matriculados oficialmente pero ausentes en el equipo)
      - Alumnos inesperados / bajas (en el equipo pero que no corresponden a la nomina oficial del grado)
    """
    if school_db is None:
        from export_students_m365 import build_school_db
        school_db = build_school_db()

    # Obtener detalle del equipo
    team_detail = get_team_members_detailed(graph, team_id)
    team_students = team_detail.get("students", [])
    team_teachers = team_detail.get("teachers", [])

    # Obtener nombre del equipo
    team_name = ""
    team_desc = ""
    try:
        raw_teams = graph.get_all_teams()
        for rt in raw_teams:
            if rt.get("id") == team_id:
                team_name = rt.get("displayName", "")
                team_desc = rt.get("description", "")
                break
    except Exception:
        pass

    # Inferir nivel y grado si no fueron proporcionados
    if not nivel or not grado:
        inf_nivel, inf_grado = detect_grade_and_nivel_from_text(team_name, team_desc)
        nivel = nivel or inf_nivel or "Desconocido"
        grado = grado or inf_grado or "Desconocido"

    # Obtener alumnos oficiales del grado
    official_students = get_students_for_grade(school_db, nivel, grado) if (nivel != "Desconocido" and grado != "Desconocido") else []

    official_by_mat = {s["matricula"]: s for s in official_students}
    team_by_mat = {s["matricula"]: s for s in team_students if s.get("matricula")}

    # Resolver user_ids de Entra ID para alumnos faltantes
    all_users = graph.get_all_users()
    upn_to_id = {u.user_principal_name.lower(): u.id for u in all_users}

    synced_students = []
    missing_students = []
    unexpected_students = []

    for mat, off_s in official_by_mat.items():
        if mat in team_by_mat:
            synced_students.append({
                "matricula": mat,
                "name": off_s.get("display_name", ""),
                "upn": off_s.get("upn", ""),
                "user_id": team_by_mat[mat].get("id") or upn_to_id.get(off_s.get("upn", "").lower()),
                "status": "SINCRONIZADO"
            })
        else:
            u_id = upn_to_id.get(off_s.get("upn", "").lower(), "")
            missing_students.append({
                "matricula": mat,
                "name": off_s.get("display_name", ""),
                "upn": off_s.get("upn", ""),
                "user_id": u_id,
                "status": "FALTANTE EN TEAMS"
            })

    for mat, tm_s in team_by_mat.items():
        if mat not in official_by_mat:
            unexpected_students.append({
                "matricula": mat,
                "name": tm_s.get("name") or tm_s.get("display_name", ""),
                "upn": tm_s.get("upn", ""),
                "user_id": tm_s.get("id", ""),
                "status": "BAJA / NO PERTENECE"
            })

    total_official = len(official_students)
    synced_count = len(synced_students)
    sync_pct = round((synced_count / total_official * 100), 1) if total_official > 0 else (100.0 if not team_students else 0.0)
    teacher_display = team_teachers[0]["display_name"] if team_teachers else "Sin asignar"

    return {
        "team_id": team_id,
        "team_name": team_name,
        "displayName": team_name,
        "nivel": nivel,
        "grado": grado,
        "teacher_name": teacher_display,
        "teachers": team_teachers,
        "official_count": total_official,
        "team_count": len(team_students),
        "synced_count": synced_count,
        "missing_count": len(missing_students),
        "unexpected_count": len(unexpected_students),
        "sync_percentage": sync_pct,
        "is_synced": (len(missing_students) == 0 and len(unexpected_students) == 0),
        "synced_students": synced_students,
        "missing_students": missing_students,
        "unexpected_students": unexpected_students,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def sync_class_roster(
    graph: GraphClient,
    team_id: str,
    add_missing: bool = True,
    remove_unexpected: bool = False,
    missing_user_ids: Optional[List[str]] = None,
    remove_user_ids: Optional[List[str]] = None,
    audit_info: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Ejecuta la regularizacion de la nomina de una clase:
    - Agrega los alumnos faltantes
    - Opcionalmente remueve a los alumnos inesperados / bajas
    """
    added_count = 0
    removed_count = 0
    errors = []

    to_add = list(missing_user_ids or [])
    if not to_add and audit_info and add_missing:
        to_add = [s["user_id"] for s in audit_info.get("missing_students", []) if s.get("user_id")]

    if to_add and add_missing:
        add_url = f"https://graph.microsoft.com/v1.0/teams/{team_id}/members/add"
        headers = {
            "Authorization": f"Bearer {graph.access_token}",
            "Content-Type": "application/json"
        }
        members_values = [
            {
                "@odata.type": "#microsoft.graph.aadUserConversationMember",
                "roles": [],
                "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{u_id}')"
            }
            for u_id in to_add
        ]
        try:
            import requests
            resp = requests.post(add_url, headers=headers, json={"values": members_values}, timeout=30)
            if resp.status_code in [200, 202, 207]:
                added_count = len(to_add)
            else:
                for u_id in to_add:
                    try:
                        if graph.add_team_member(team_id, u_id, is_owner=False):
                            added_count += 1
                    except Exception as ex:
                        errors.append(f"Error al agregar {u_id}: {str(ex)}")
        except Exception:
            for u_id in to_add:
                try:
                    if graph.add_team_member(team_id, u_id, is_owner=False):
                        added_count += 1
                except Exception as ex:
                    errors.append(f"Error al agregar {u_id}: {str(ex)}")

    to_remove = list(remove_user_ids or [])
    if not to_remove and audit_info and remove_unexpected:
        to_remove = [s["user_id"] for s in audit_info.get("unexpected_students", []) if s.get("user_id")]

    if to_remove and remove_unexpected:
        for u_id in to_remove:
            try:
                if graph.remove_team_member(team_id, u_id):
                    removed_count += 1
            except Exception as ex:
                errors.append(f"Error al remover {u_id}: {str(ex)}")

    return {
        "status": "success" if not errors else "partial",
        "team_id": team_id,
        "added_count": added_count,
        "removed_count": removed_count,
        "errors": errors,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def audit_all_rosters(
    graph: GraphClient,
    school_db: Optional[Dict[str, Any]] = None,
    cycle_filter: str = "2026-2027"
) -> Dict[str, Any]:
    """
    Audita los rosters de todas las clases del ciclo indicado y genera el balance institucional.
    """
    if school_db is None:
        from export_students_m365 import build_school_db
        school_db = build_school_db()

    inv = audit_teams_inventory(graph)
    teams = inv.get("teams", [])

    classes_to_audit = [
        t for t in teams
        if t.get("team_type") == "CLASE" and (not cycle_filter or t.get("cycle") == cycle_filter)
    ]

    audited_classes = []
    total_missing = 0
    total_unexpected = 0
    synced_classes = 0
    all_discrepancies = []

    for c in classes_to_audit:
        t_id = c["id"]
        audit_res = audit_class_roster(
            graph=graph,
            team_id=t_id,
            nivel=c.get("nivel"),
            grado=c.get("grado"),
            school_db=school_db
        )
        # Si el nombre no venia en audit_res, tomar el de inventario
        if not audit_res.get("team_name"):
            audit_res["team_name"] = c.get("name", "")
            audit_res["displayName"] = c.get("name", "")

        total_missing += audit_res["missing_count"]
        total_unexpected += audit_res["unexpected_count"]
        if audit_res["is_synced"]:
            synced_classes += 1

        for ms in audit_res["missing_students"]:
            all_discrepancies.append({
                "clase": audit_res["team_name"],
                "team_id": t_id,
                "matricula": ms["matricula"],
                "nombre": ms["name"],
                "upn": ms["upn"],
                "tipo": "FALTANTE EN TEAMS",
                "nivel": audit_res["nivel"],
                "grado": audit_res["grado"]
            })

        for un in audit_res["unexpected_students"]:
            all_discrepancies.append({
                "clase": audit_res["team_name"],
                "team_id": t_id,
                "matricula": un["matricula"],
                "nombre": un["name"],
                "upn": un["upn"],
                "tipo": "BAJA / NO PERTENECE",
                "nivel": audit_res["nivel"],
                "grado": audit_res["grado"]
            })

        audited_classes.append(audit_res)

    total_classes = len(classes_to_audit)
    discrepant = total_classes - synced_classes
    total_official_slots = sum(c["official_count"] for c in audited_classes)
    total_synced_slots = sum(c["synced_count"] for c in audited_classes)
    global_rate = round((total_synced_slots / total_official_slots * 100), 1) if total_official_slots > 0 else 100.0

    return {
        "cycle": cycle_filter,
        "total_classes": total_classes,
        "synced_classes": synced_classes,
        "discrepant_classes": discrepant,
        "total_missing": total_missing,
        "total_unexpected": total_unexpected,
        "global_sync_rate": global_rate,
        "classes": audited_classes,
        "discrepancies": all_discrepancies,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def export_roster_audit_excel(roster_data: Dict[str, Any], output_path: str) -> str:
    """
    Genera un libro oficial en Excel con 3 hojas de trabajo:
    1. Resumen Ejecutivo (KPIs de matricula y cobertura)
    2. Estado por Clase (Semaforo de cobertura)
    3. Detalle Discrepancias (Registro nominal)
    """
    wb = openpyxl.Workbook()
    ws_kpi = wb.active
    ws_kpi.title = "Resumen Ejecutivo"

    # Paleta institucional
    navy_fill = PatternFill(start_color="1B365D", end_color="1B365D", fill_type="solid")
    navy_light_fill = PatternFill(start_color="2B6CB0", end_color="2B6CB0", fill_type="solid")
    kpi_bg = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    zebra_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    white_fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
    green_fill = PatternFill(start_color="E6F4EA", end_color="E6F4EA", fill_type="solid")
    amber_fill = PatternFill(start_color="FEF7E0", end_color="FEF7E0", fill_type="solid")
    red_fill = PatternFill(start_color="FCE8E6", end_color="FCE8E6", fill_type="solid")

    white_title = Font(name="Segoe UI", size=14, bold=True, color="FFFFFF")
    white_bold = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    kpi_label_font = Font(name="Segoe UI", size=9, color="475569")
    kpi_val_font = Font(name="Segoe UI", size=16, bold=True, color="1B365D")
    data_font = Font(name="Segoe UI", size=9)
    green_font = Font(name="Segoe UI", size=9, bold=True, color="137333")
    amber_font = Font(name="Segoe UI", size=9, bold=True, color="B06000")
    red_font = Font(name="Segoe UI", size=9, bold=True, color="C5221F")

    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1")
    )

    # HOJA 1: RESUMEN EJECUTIVO
    ws_kpi.merge_cells("A1:G1")
    t_cell = ws_kpi["A1"]
    t_cell.value = "INSTITUTO DE DESARROLLO INTEGRAL LIC. JOSE VASCONCELOS"
    t_cell.font = white_title
    t_cell.fill = navy_fill
    t_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws_kpi.row_dimensions[1].height = 36

    ws_kpi.merge_cells("A2:G2")
    st_cell = ws_kpi["A2"]
    st_cell.value = f"INFORME EJECUTIVO DE AUDITORIA Y SINCRONIZACION DE ROSTER EN TEAMS • CICLO {roster_data.get('cycle', '2026-2027')}"
    st_cell.font = white_bold
    st_cell.fill = navy_light_fill
    st_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws_kpi.row_dimensions[2].height = 24

    ws_kpi["A4"] = f"Fecha de Emisión: {roster_data.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}"
    ws_kpi["A4"].font = Font(name="Segoe UI", size=9, italic=True, color="64748B")

    kpis = [
        ("Total Clases Auditadas", roster_data.get("total_classes", 0)),
        ("Clases 100% Sincronizadas", roster_data.get("synced_classes", 0)),
        ("Clases con Discrepancia", roster_data.get("discrepant_classes", 0)),
        ("Alumnos Faltantes en Equipos", roster_data.get("total_missing", 0)),
        ("Bajas / No Pertenecen", roster_data.get("total_unexpected", 0)),
        ("Tasa Global de Alineación", f"{roster_data.get('global_sync_rate', 100.0):.1f}%"),
    ]

    for idx, (label, val) in enumerate(kpis, start=6):
        ws_kpi.cell(row=idx, column=1, value=label).font = Font(name="Segoe UI", size=10, bold=True, color="1B365D")
        ws_kpi.cell(row=idx, column=1).fill = kpi_bg
        ws_kpi.cell(row=idx, column=1).border = thin_border
        
        v_cell = ws_kpi.cell(row=idx, column=2, value=val)
        v_cell.font = Font(name="Segoe UI", size=10, bold=True)
        v_cell.alignment = Alignment(horizontal="center")
        v_cell.fill = white_fill
        v_cell.border = thin_border

    ws_kpi.column_dimensions["A"].width = 32
    ws_kpi.column_dimensions["B"].width = 20

    # HOJA 2: ESTADO POR CLASE
    ws_cl = wb.create_sheet(title="Estado por Clase")
    h2 = ["Equipo / Clase", "Nivel", "Grado", "Docente Titular", "Nómina Oficial", "En Teams", "Sincronizados", "Faltantes", "Bajas", "% Sincronización", "Semáforo"]
    ws_cl.append(h2)
    ws_cl.row_dimensions[1].height = 26
    for col_num in range(1, len(h2) + 1):
        c = ws_cl.cell(row=1, column=col_num)
        c.fill = navy_fill
        c.font = white_bold
        c.alignment = Alignment(horizontal="center", vertical="center")

    classes_list = roster_data.get("classes", [])
    for idx, cl in enumerate(classes_list, start=2):
        missing = cl.get("missing_count", 0)
        unexpected = cl.get("unexpected_count", 0)
        semaforo = "ÓPTIMO" if missing == 0 and unexpected == 0 else "DESALINEADO"
        row_data = [
            cl.get("team_name", ""),
            cl.get("nivel", ""),
            cl.get("grado", ""),
            cl.get("teacher_name", ""),
            cl.get("official_count", 0),
            cl.get("team_count", 0),
            cl.get("synced_count", 0),
            missing,
            unexpected,
            f"{cl.get('sync_percentage', 0.0):.1f}%",
            semaforo
        ]
        ws_cl.append(row_data)
        r_fill = zebra_fill if idx % 2 == 0 else white_fill
        for c_idx in range(1, len(row_data) + 1):
            cell = ws_cl.cell(row=idx, column=c_idx)
            cell.font = data_font
            cell.fill = r_fill
            cell.border = thin_border
            if c_idx in [5, 6, 7, 8, 9, 10, 11]:
                cell.alignment = Alignment(horizontal="center", vertical="center")
            if c_idx == 11:
                if semaforo == "ÓPTIMO":
                    cell.fill = green_fill
                    cell.font = green_font
                else:
                    cell.fill = red_fill
                    cell.font = red_font

    ws_cl.freeze_panes = "A2"
    for col in ws_cl.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws_cl.column_dimensions[col_letter].width = min(max(max_len + 4, 12), 40)

    # HOJA 3: DETALLE DISCREPANCIAS
    ws_disc = wb.create_sheet(title="Detalle Discrepancias")
    h3 = ["Clase / Materia", "Nivel", "Grado", "Matrícula", "Nombre del Alumno", "UPN Institucional", "Tipo de Discrepancia", "Acción Recomendada"]
    ws_disc.append(h3)
    ws_disc.row_dimensions[1].height = 26
    for col_num in range(1, len(h3) + 1):
        c = ws_disc.cell(row=1, column=col_num)
        c.fill = navy_light_fill
        c.font = white_bold
        c.alignment = Alignment(horizontal="center", vertical="center")

    discrepancies = roster_data.get("discrepancies", [])
    for idx, d in enumerate(discrepancies, start=2):
        d_type = d.get("tipo", "FALTANTE EN TEAMS")
        action = "Inscribir al equipo en Teams" if "FALTANTE" in d_type else "Desvincular del equipo"
        row_data = [
            d.get("clase", ""),
            d.get("nivel", ""),
            d.get("grado", ""),
            d.get("matricula", ""),
            d.get("nombre", ""),
            d.get("upn", ""),
            d_type,
            action
        ]
        ws_disc.append(row_data)
        r_fill = zebra_fill if idx % 2 == 0 else white_fill
        for c_idx in range(1, len(row_data) + 1):
            cell = ws_disc.cell(row=idx, column=c_idx)
            cell.font = data_font
            cell.fill = r_fill
            cell.border = thin_border
            if c_idx in [4, 7]:
                cell.alignment = Alignment(horizontal="center", vertical="center")
            if c_idx == 7:
                if "FALTANTE" in d_type:
                    cell.fill = amber_fill
                    cell.font = amber_font
                else:
                    cell.fill = red_fill
                    cell.font = red_font

    ws_disc.freeze_panes = "A2"
    for col in ws_disc.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws_disc.column_dimensions[col_letter].width = min(max(max_len + 4, 12), 40)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    wb.save(output_path)
    return output_path




