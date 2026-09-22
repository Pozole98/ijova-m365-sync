#!/usr/bin/env python3
"""
Script para extraer y generar un reporte Excel profesional y exhaustivo
con todos los alumnos de Microsoft 365 (Microsoft Entra ID) cruzados con sus datos escolares.
"""
import os
import sys
import re
import csv
import glob
import unicodedata
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from src.config import load_config
from src.graph_client import GraphClient
from src.validator import is_valid_matricula_format
import requests


def norm(s):
    if not s:
        return ''
    return ''.join(c for c in unicodedata.normalize('NFD', str(s).upper()) if unicodedata.category(c) != 'Mn').strip()


def split_mexican_name(full_name):
    if not full_name:
        return "", "", ""
    parts = full_name.strip().split()
    if len(parts) == 1:
        return parts[0], "", ""
    elif len(parts) == 2:
        return parts[0], parts[1], ""
    elif len(parts) == 3:
        return parts[0], parts[1], parts[2]
    elif len(parts) == 4:
        return f"{parts[0]} {parts[1]}", parts[2], parts[3]
    else:
        return " ".join(parts[:-2]), parts[-2], parts[-1]


def build_school_db():
    school_db = {}

    # 1. Listado de Alumnos Inscritos.xlsx - Listado Global Matriculado
    try:
        wb = openpyxl.load_workbook('Listado de Alumnos Inscritos.xlsx', data_only=True)
        if 'Listado Global Matriculado' in wb.sheetnames:
            ws = wb['Listado Global Matriculado']
            headers = [c for c in next(ws.iter_rows(values_only=True))]
            for r in ws.iter_rows(min_row=2, values_only=True):
                if not any(r):
                    continue
                d = dict(zip(headers, r))
                mat = str(d.get('Matricula') or '').strip()
                if mat:
                    school_db[mat] = {
                        'matricula': mat,
                        'paterno': str(d.get('Apellido Paterno') or '').strip().upper(),
                        'materno': str(d.get('Apellido Materno') or '').strip().upper(),
                        'nombres': str(d.get('Nombre(s)') or '').strip().upper(),
                        'nivel': str(d.get('Nivel') or '').strip(),
                        'grado': str(d.get('Grado/Semestre') or '').strip(),
                        'estatus': str(d.get('Estatus') or '').strip(),
                        'alias': str(d.get('Alias de Correo') or '').strip().lower(),
                        'display_name': str(d.get('Nombre para Mostrar') or '').strip().upper(),
                        'curp': '',
                        'seccion': '',
                        'sexo': '',
                        'tutor_nombre': '',
                        'tutor_correo': '',
                        'tutor_telefono': '',
                        'tiene_foto': False
                    }
    except Exception as e:
        print(f"⚠️ Aviso al leer Listado de Alumnos Inscritos.xlsx: {e}")

    # 2. Grade sheets in Listado de Alumnos Inscritos.xlsx
    try:
        wb = openpyxl.load_workbook('Listado de Alumnos Inscritos.xlsx', data_only=True)
        name_to_info = {}
        for sname in wb.sheetnames:
            if sname in ['Listado Global Matriculado', 'Registrados', 'Faltantes']:
                continue
            sws = wb[sname]
            sh = [c for c in next(sws.iter_rows(values_only=True))]
            for r in sws.iter_rows(min_row=2, values_only=True):
                if not any(r):
                    continue
                rd = dict(zip(sh, r))
                name = rd.get('NOMBRE DEL ALUMNO')
                curp = rd.get('CURP')
                sexo = rd.get('SEXO')
                if name:
                    name_to_info[norm(name)] = (str(curp or '').strip(), str(sexo or '').strip())

        for mat, d in school_db.items():
            fn1 = norm(f"{d['paterno']} {d['materno']} {d['nombres']}")
            fn2 = norm(f"{d['paterno']} {d['nombres']}")
            if fn1 in name_to_info:
                c, s = name_to_info[fn1]
                if c: d['curp'] = c
                if s: d['sexo'] = s
            elif fn2 in name_to_info:
                c, s = name_to_info[fn2]
                if c: d['curp'] = c
                if s: d['sexo'] = s
    except Exception as e:
        print(f"⚠️ Aviso al leer hojas de grado: {e}")

    # 3. Cometa export (students_report_2026-09-07_gfW21IW.xlsx)
    try:
        wb_c = openpyxl.load_workbook('students_report_2026-09-07_gfW21IW.xlsx', data_only=True)
        ws_c = wb_c['Estudiantes']
        c_headers = [c for c in next(ws_c.iter_rows(values_only=True))]
        for r in ws_c.iter_rows(min_row=2, values_only=True):
            if not any(r):
                continue
            cd = dict(zip(c_headers, r))
            mat = str(cd.get('Matricula') or '').strip()
            if mat:
                if mat not in school_db:
                    school_db[mat] = {'matricula': mat, 'tiene_foto': False}
                rec = school_db[mat]
                if cd.get('CURP'): rec['curp'] = str(cd.get('CURP')).strip()
                if cd.get('Nivel actual'): rec['nivel'] = str(cd.get('Nivel actual')).strip()
                if cd.get('Sección actual'): rec['seccion'] = str(cd.get('Sección actual')).strip()
                if cd.get('Sexo'): rec['sexo'] = str(cd.get('Sexo')).strip()
                if cd.get('Tutor 1 - Nombre'): rec['tutor_nombre'] = str(cd.get('Tutor 1 - Nombre')).strip()
                if cd.get('Correo 1'): rec['tutor_correo'] = str(cd.get('Correo 1')).strip()
                if cd.get('Teléfono 1'): rec['tutor_telefono'] = str(cd.get('Teléfono 1')).strip()
                if cd.get('Nombre') and not rec.get('nombres'): rec['nombres'] = str(cd.get('Nombre')).strip().upper()
                if cd.get('Apellido') and not rec.get('paterno'): rec['paterno'] = str(cd.get('Apellido')).strip().upper()
    except Exception as e:
        print(f"⚠️ Aviso al leer students_report_2026-09-07_gfW21IW.xlsx: {e}")

    # 4. librosluca/pagoslibrosprimariaypreescolar.xlsx
    try:
        wb_p = openpyxl.load_workbook('librosluca/pagoslibrosprimariaypreescolar.xlsx', data_only=True)
        ws_p = wb_p['Estudiantes']
        p_headers = [c for c in next(ws_p.iter_rows(values_only=True))]
        for r in ws_p.iter_rows(min_row=2, values_only=True):
            if not any(r):
                continue
            pd = dict(zip(p_headers, r))
            mat = str(pd.get('Matricula') or '').strip()
            if mat:
                if mat not in school_db:
                    school_db[mat] = {'matricula': mat, 'tiene_foto': False}
                rec = school_db[mat]
                if pd.get('CURP') and not rec.get('curp'): rec['curp'] = str(pd.get('CURP')).strip()
                if pd.get('Nivel actual') and not rec.get('nivel'): rec['nivel'] = str(pd.get('Nivel actual')).strip()
                if pd.get('Sección actual') and not rec.get('seccion'): rec['seccion'] = str(pd.get('Sección actual')).strip()
                if pd.get('Sexo') and not rec.get('sexo'): rec['sexo'] = str(pd.get('Sexo')).strip()
                if pd.get('Tutor 1 - Nombre') and not rec.get('tutor_nombre'): rec['tutor_nombre'] = str(pd.get('Tutor 1 - Nombre')).strip()
                if pd.get('Correo 1') and not rec.get('tutor_correo'): rec['tutor_correo'] = str(pd.get('Correo 1')).strip()
                if pd.get('Teléfono 1') and not rec.get('tutor_telefono'): rec['tutor_telefono'] = str(pd.get('Teléfono 1')).strip()
    except Exception:
        pass

    # 5. auditoria_fotos_perfil.csv
    try:
        with open('reports/auditoria_fotos_perfil.csv', mode='r', encoding='utf-8') as f:
            r = csv.DictReader(f)
            for row in r:
                mat = str(row.get('matricula') or '').strip()
                if mat:
                    if mat not in school_db:
                        school_db[mat] = {'matricula': mat}
                    rec = school_db[mat]
                    if row.get('nivel') and not rec.get('nivel'):
                        rec['nivel'] = str(row.get('nivel')).strip()
                    if row.get('grado_semestre') and not rec.get('grado'):
                        rec['grado'] = str(row.get('grado_semestre')).strip()
                    rec['tiene_foto'] = (row.get('tiene_foto') == 'SI')
    except Exception:
        pass

    # 6. CSV files in secrets/
    for f in sorted(glob.glob('secrets/credenciales_alumnos_*.csv')):
        try:
            with open(f, 'r', encoding='utf-8') as cf:
                reader = csv.DictReader(cf)
                for row in reader:
                    mat = str(row.get('matricula') or '').strip()
                    if mat:
                        if mat not in school_db:
                            school_db[mat] = {'matricula': mat, 'tiene_foto': False}
                        rec = school_db[mat]
                        if row.get('nivel') and not rec.get('nivel'):
                            rec['nivel'] = str(row.get('nivel')).strip()
                        if row.get('grado_semestre') and not rec.get('grado'):
                            rec['grado'] = str(row.get('grado_semestre')).strip()
        except Exception:
            pass

    # 7. librosluca/Luca-Estudiantes-*.xlsx
    for fn in glob.glob('librosluca/Luca-Estudiantes-*.xlsx'):
        try:
            wbl = openpyxl.load_workbook(fn, data_only=True)
            for sname in wbl.sheetnames:
                wsl = wbl[sname]
                for r in wsl.iter_rows(values_only=True):
                    for c in r:
                        if c and '@ijova.com' in str(c):
                            mat = str(c).split('@')[0]
                            if mat in school_db and not school_db[mat].get('seccion'):
                                g_num = re.search(r'\d', str(r[4])) if len(r) > 4 else None
                                g_str = g_num.group(0) if g_num else ''
                                grp_letter = str(r[5]).strip() if len(r) > 5 and r[5] else 'A'
                                school_db[mat]['seccion'] = f"{g_str} {grp_letter}".strip() if g_str else grp_letter
        except Exception:
            pass

    # 8. librosluca/students_report_2026-09-07_ILDhyDg.xlsx
    try:
        wb_ild = openpyxl.load_workbook('librosluca/students_report_2026-09-07_ILDhyDg.xlsx', data_only=True)
        ws_ild = wb_ild['Estudiantes']
        hi = [c for c in next(ws_ild.iter_rows(values_only=True))]
        for r in ws_ild.iter_rows(min_row=2, values_only=True):
            if not any(r): continue
            mat = str(r[hi.index('Matricula')] or '').strip()
            sec = str(r[hi.index('Sección actual')] or '').strip()
            if mat and sec and mat in school_db and not school_db[mat].get('seccion'):
                school_db[mat]['seccion'] = sec
    except Exception:
        pass

    # 9. COLEGIATURAS 26-27 (Fuente de verdad oficial del ciclo escolar 2026-2027)
    try:
        col_files = glob.glob("COLEGIATURAS 26-27*.xlsx")
        if col_files:
            col_path = sorted(col_files)[-1]
            wb_col = openpyxl.load_workbook(col_path, data_only=True)
            sheets_config = [
                ("PREESCOLAR", 2, 4, 9, "Preescolar"),
                ("PRIMARIA", 2, 3, 8, "Primaria"),
                ("SECUNDARIA", 2, 3, 9, "Secundaria"),
                ("PREPARATORIA", 3, 4, 8, "Preparatoria")
            ]

            manual_corrections = {
                "ROBLES CRUZ VICTOR AZIEL": "260032",
                "VARCENAS LOPEZ DE NAVA LUIS MANUEL": "260033",
                "BARRIENTOS ALONSO SAID JARED": "PENDING_BAJA",
                "JUAREZ RAMOS MELANIE": "250052",
                "VAZQUEZ HERNANDEZ VALENTINA": "260016",
                "LOPEZ DE NAVA TENORIO RUTH MARISOL": "250101",
                "VARCENAS LOPEZ DE NAVA ARLETH AMAYA": "250082",
                "CAHUICH ORTIZ JOHAN ALEXANDER": "260028",
                "CAHUICH ORTIZ DORIAN ALEXANDER": "250016",
                "MARTINEZ CUEVAS ALEJANDRO": "260024",
                "MARTINEZ CUEVAS ALIX LARISA": "250063",
                "MEDINA GARCIA JONATHAN": "260029",
                "BARRANCO URBINA THIAGO LEONARDO": "260027",
                "CAMACHO NAVA MARCO ANTONIO": "260031",
                "MARURI PIÑA BETBIRAI": "260030",
                "CERON ENRIQUEZ JEIMI ZOE": "260021",
                "CERON ENRIQUEZ ALISSON YOALI": "260025",
                "DOMINGO PEREZ PAULINA ALEXANDRA": "260020",
                "BUSTOS BUENO MELISSA JULIETTE": "260022",
                "RAMIREZ HERNANDEZ ANDREA": "260019",
                "DIAZ PINEDA LUIS ENRIQUE": "260004",
                "CRUZ NESTOR JULIAN ELEAZAR": "260005",
                "JIMENEZ HERNANDEZ IKER LEOPOLDO": "260006",
                "SALAS PEREZ DANIELA SAMARA": "260003",
                "REYES LUCIO ELIAS ISBAQ": "260009",
                "REYES LUCIO ENRIQUE OWEN": "260010",
                "CASTRO RAMIREZ OMAR": "260011",
                "GUERRERO MEDINA GAEL": "260012",
                "PASTEN JIMENEZ MARIA SOFIA": "260013",
                "CERVANTES GARCIA ANTONIO ADAIR": "260014",
                "SOTO CARRANZA MARIA SOFIA": "260015",
                "MARTINEZ VALENTINEZ VALENTINA GUADALUPE": "260017",
                "HERNANDEZ NESTOR IVAN YERAY": "260018",
                "PEREZ HERNANDEZ LUIS ANGEL": "260023",
                "ESTRADA MONTECINOS MAURICIO": "260026",
                "LAMADRID ALVAREZ XIMENA OSIRIS": "260007",
                "GOMEZ TRUJILLO OSVALDO": "260008",
                "JUAN ESPINDOLA CAMILA": "260001",
                "LEON ROJAS DAFNE ANAHI": "260002"
            }

            name_to_mat = {}
            for mat, d in school_db.items():
                fn1 = norm(f"{d.get('paterno', '')} {d.get('materno', '')} {d.get('nombres', '')}")
                fn2 = norm(f"{d.get('paterno', '')} {d.get('nombres', '')}")
                fn3 = norm(d.get("display_name", ""))
                for f in [fn1, fn2, fn3]:
                    if f and f not in name_to_mat:
                        name_to_mat[f] = mat

            active_2627_mats = set()

            for sheet_name, col_g, col_n, start_r, nivel in sheets_config:
                if sheet_name not in wb_col.sheetnames:
                    continue
                ws = wb_col[sheet_name]
                cur_g = None
                for r in range(start_r, ws.max_row + 1):
                    g = ws.cell(row=r, column=col_g).value
                    n = ws.cell(row=r, column=col_n).value
                    if g is not None and str(g).strip():
                        cur_g = str(g).strip()
                    if n and str(n).strip():
                        val = str(n).strip()
                        if any(k in val.upper() for k in ["TOTAL", "SUBTOTAL", "NOMBRE", "ALUMNO", "COLEGIATURA", "BAJAS", "PROMEDIO"]):
                            continue
                        notes = [str(ws.cell(row=r, column=c).value or "").strip() for c in range(1, 15)]
                        is_baja = any("BAJA" in x.upper() for x in notes)

                        if nivel == "Preparatoria":
                            sem_map = {"1": "1er Semestre", "2": "3er Semestre", "3": "5to Semestre"}
                            grado_str = sem_map.get(str(cur_g), f"{cur_g}° Semestre")
                        elif nivel == "Secundaria":
                            grado_str = f"{cur_g}° Secundaria"
                        elif nivel == "Primaria":
                            grado_str = f"{cur_g}° Primaria"
                        elif nivel == "Preescolar":
                            grado_str = f"{cur_g}° Preescolar"
                        else:
                            grado_str = str(cur_g)

                        n_norm = norm(val)
                        target_mat = manual_corrections.get(val) or name_to_mat.get(n_norm)
                        if not target_mat:
                            v_toks = set(n_norm.split())
                            for fn, m in name_to_mat.items():
                                fn_toks = set(fn.split())
                                if len(v_toks.intersection(fn_toks)) >= 3:
                                    target_mat = m
                                    break

                        if target_mat and not target_mat.endswith("_PENDING") and target_mat != "PENDING_BAJA":
                            active_2627_mats.add(target_mat)
                            if target_mat not in school_db:
                                school_db[target_mat] = {"matricula": target_mat}
                            rec = school_db[target_mat]
                            rec["nivel"] = nivel
                            rec["grado"] = grado_str
                            rec["estatus"] = "Baja" if is_baja else "Activo"
                            rec["ciclo"] = "2026-2027"
                            rec["display_name"] = rec.get("display_name") or val

            # Alumnos de la base anterior no presentes en Colegiaturas 26-27 se marcan como inactivos/egresados
            for mat, d in school_db.items():
                if mat not in active_2627_mats:
                    d["estatus"] = "Egresado / Ciclo Anterior"
                    d["ciclo"] = "2025-2026"
    except Exception as e:
        print(f"Aviso al procesar Colegiaturas 26-27: {e}")

    return school_db


def fetch_m365_data():
    config = load_config('config.json')
    client = GraphClient(config.tenant_id, config.client_id, config.graph_scopes)
    accounts = client.app.get_accounts()
    if not accounts:
        raise RuntimeError("No hay cuentas autenticadas en el token cache.")

    res = client.app.acquire_token_silent(config.graph_scopes, account=accounts[0])
    if not res or 'access_token' not in res:
        raise RuntimeError("No se pudo renovar silenciosamente el token de acceso.")

    token = res['access_token']
    admin_username = accounts[0].get('username', 'admin@ijova.com')

    # 1. Fetch all active users
    all_users = []
    url = 'https://graph.microsoft.com/v1.0/users?$select=id,userPrincipalName,displayName,givenName,surname,mail,mailNickname,jobTitle,accountEnabled&$top=999'
    while url:
        r = requests.get(url, headers={'Authorization': 'Bearer ' + token})
        d = r.json()
        all_users.extend(d.get('value', []))
        url = d.get('@odata.nextLink')

    active_students = [
        u for u in all_users
        if is_valid_matricula_format(u.get('userPrincipalName', '').split('@')[0]) or u.get('jobTitle') == 'Alumno'
    ]

    # 2. Fetch deleted users from Entra ID recycle bin
    r_del = requests.get(
        'https://graph.microsoft.com/v1.0/directory/deletedItems/microsoft.graph.user',
        headers={'Authorization': 'Bearer ' + token}
    )
    del_raw = r_del.json().get('value', []) if r_del.status_code == 200 else []

    deleted_students = []
    for u in del_raw:
        upn = u.get('userPrincipalName', '').lower()
        prefix = upn.split('@')[0]
        m = re.search(r'(\d{6})$', prefix)
        if m:
            u['extracted_matricula'] = m.group(1)
            deleted_students.append(u)
        elif u.get('jobTitle') == 'Alumno':
            deleted_students.append(u)

    return active_students, deleted_students, admin_username, config


def generate_excel_report(output_paths):
    print("🔄 Conectando con Microsoft 365 (Microsoft Graph API)...")
    active_students, deleted_students, admin_user, config = fetch_m365_data()
    print(f"✅ Microsoft 365: {len(active_students)} alumnos activos y {len(deleted_students)} alumnos en papelera.")

    print("📚 Cruzando con base de datos escolar e histórico...")
    school_db = build_school_db()

    # Sort active students by Matricula
    def get_mat(u):
        upn = u.get('userPrincipalName', '').split('@')[0]
        try:
            return int(upn)
        except ValueError:
            return 999999

    active_students = sorted(active_students, key=get_mat)
    deleted_students = sorted(deleted_students, key=lambda x: x.get('extracted_matricula', ''))

    # Build openpyxl workbook
    wb = openpyxl.Workbook()

    # Styles
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
    
    active_pill_fill = PatternFill(start_color="E6F4EA", end_color="E6F4EA", fill_type="solid")
    active_pill_font = Font(name="Segoe UI", size=10, bold=True, color="137333")
    
    warning_pill_fill = PatternFill(start_color="FEF7E0", end_color="FEF7E0", fill_type="solid")
    warning_pill_font = Font(name="Segoe UI", size=10, bold=True, color="B06000")

    no_pill_fill = PatternFill(start_color="FCE8E6", end_color="FCE8E6", fill_type="solid")
    no_pill_font = Font(name="Segoe UI", size=10, bold=True, color="C5221F")

    # ==========================================
    # SHEET 1: Alumnos Activos M365
    # ==========================================
    ws1 = wb.active
    ws1.title = "Alumnos Activos M365"
    ws1.sheet_properties.tabColor = navy_primary

    headers1 = [
        "Matrícula",
        "Nombre Completo",
        "Nombres",
        "Apellido Paterno",
        "Apellido Materno",
        "UPN (Cuenta Acceso M365)",
        "Correo Institucional (Alias)",
        "Nivel Escolar",
        "Grado / Semestre",
        "Grupo / Sección",
        "CURP",
        "Sexo",
        "Estado en M365",
        "Rol Institucional",
        "Licencia M365",
        "Tiene Foto de Perfil",
        "Nombre del Tutor",
        "Teléfono Tutor",
        "Correo Tutor",
        "ID Objeto Entra ID"
    ]

    ws1.append(headers1)
    for col_num in range(1, len(headers1) + 1):
        cell = ws1.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=False)
        cell.border = thin_border
    ws1.row_dimensions[1].height = 28
    for idx, u in enumerate(active_students, start=2):
        upn = u.get('userPrincipalName', '')
        mat = upn.split('@')[0]
        school_rec = school_db.get(mat, {})

        display_name = u.get('displayName') or school_rec.get('display_name') or ''
        
        # Check if school_rec identity matches M365 identity
        rec_name = school_rec.get('display_name') or f"{school_rec.get('paterno', '')} {school_rec.get('nombres', '')}"
        name_mismatch = False
        if display_name and rec_name:
            norm_disp = norm(display_name)
            norm_rec = norm(rec_name)
            if not any(part in norm_disp for part in norm_rec.split() if len(part) > 2):
                name_mismatch = True

        if name_mismatch:
            given_name, paterno, materno = split_mexican_name(display_name)
        else:
            given_name = u.get('givenName') or school_rec.get('nombres') or ''
            paterno = school_rec.get('paterno') or ''
            materno = school_rec.get('materno') or ''
            if not given_name or not paterno:
                g, p, m = split_mexican_name(display_name)
                given_name = given_name or g
                paterno = paterno or p
                materno = materno or m

        mail = u.get('mail') or school_rec.get('alias') or upn
        nivel = school_rec.get('nivel') or 'No especificado'
        grado = school_rec.get('grado') or ''
        seccion = school_rec.get('seccion') or ''
        if not seccion:
            m = re.search(r'(\d)', grado)
            if m:
                seccion = f"{m.group(1)} A"
            else:
                seccion = "A"
        curp = school_rec.get('curp') or ''
        sexo = school_rec.get('sexo') or ''
        estado_m365 = "Activo"
        rol = "Alumno"
        licencia = "Office 365 Education A1 (Estudiantes)"
        tiene_foto = "SÍ" if school_rec.get('tiene_foto') else "NO"
        tutor_nombre = school_rec.get('tutor_nombre') or ''
        tutor_tel = school_rec.get('tutor_telefono') or ''
        tutor_mail = school_rec.get('tutor_correo') or ''
        obj_id = u.get('id') or ''

        row_data = [
            mat,
            display_name,
            given_name,
            paterno,
            materno,
            upn,
            mail,
            nivel,
            grado,
            seccion,
            curp,
            sexo,
            estado_m365,
            rol,
            licencia,
            tiene_foto,
            tutor_nombre,
            tutor_tel,
            tutor_mail,
            obj_id
        ]
        ws1.append(row_data)

        # Style row
        row_fill = zebra_fill if idx % 2 == 0 else white_fill
        ws1.row_dimensions[idx].height = 20

        for col_num, val in enumerate(row_data, start=1):
            c = ws1.cell(row=idx, column=col_num)
            c.border = thin_border
            c.font = data_font
            c.fill = row_fill

            # Alignment
            if col_num in [1, 8, 9, 10, 11, 12, 13, 14, 15, 16]:
                c.alignment = Alignment(horizontal="center", vertical="center")
            else:
                c.alignment = Alignment(horizontal="left", vertical="center")

            # Pills
            if col_num == 13:  # Estado
                c.fill = active_pill_fill
                c.font = active_pill_font
            elif col_num == 16:  # Tiene Foto
                if val == "SÍ":
                    c.fill = active_pill_fill
                    c.font = active_pill_font
                else:
                    c.fill = no_pill_fill
                    c.font = no_pill_font

    ws1.freeze_panes = "A2"
    ws1.auto_filter.ref = f"A1:{get_column_letter(len(headers1))}{len(active_students) + 1}"

    # Auto-adjust column widths
    for col in ws1.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws1.column_dimensions[col_letter].width = max(max_len + 4, 12)

    # ==========================================
    # SHEET 2: Alumnos en Papelera (Bajas)
    # ==========================================
    ws2 = wb.create_sheet(title="Alumnos en Papelera (Bajas)")
    ws2.sheet_properties.tabColor = "E65100"

    headers2 = [
        "Matrícula",
        "Nombre Completo",
        "Correo Original Estimado",
        "UPN en Papelera de Reciclaje",
        "Estado en Entra ID",
        "Nivel Escolar",
        "Grado / Semestre",
        "CURP",
        "ID Objeto Entra ID"
    ]

    ws2.append(headers2)
    for col_num in range(1, len(headers2) + 1):
        cell = ws2.cell(row=1, column=col_num)
        cell.fill = PatternFill(start_color="8C1D40", end_color="8C1D40", fill_type="solid")
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border
    ws2.row_dimensions[1].height = 28

    for idx, u in enumerate(deleted_students, start=2):
        mat = u.get('extracted_matricula', '')
        school_rec = school_db.get(mat, {})
        display_name = u.get('displayName') or school_rec.get('display_name') or ''
        del_upn = u.get('userPrincipalName') or ''
        orig_mail = f"{mat}@ijova.com"
        nivel = school_rec.get('nivel') or 'No especificado'
        grado = school_rec.get('grado') or ''
        curp = school_rec.get('curp') or ''
        obj_id = u.get('id') or ''
        estado = "En Papelera (< 30 días de retención)"

        row_data = [
            mat,
            display_name,
            orig_mail,
            del_upn,
            estado,
            nivel,
            grado,
            curp,
            obj_id
        ]
        ws2.append(row_data)

        row_fill = zebra_fill if idx % 2 == 0 else white_fill
        ws2.row_dimensions[idx].height = 20

        for col_num, val in enumerate(row_data, start=1):
            c = ws2.cell(row=idx, column=col_num)
            c.border = thin_border
            c.font = data_font
            c.fill = row_fill

            if col_num in [1, 5, 6, 7, 8]:
                c.alignment = Alignment(horizontal="center", vertical="center")
            else:
                c.alignment = Alignment(horizontal="left", vertical="center")

            if col_num == 5:
                c.fill = warning_pill_fill
                c.font = warning_pill_font

    ws2.freeze_panes = "A2"
    ws2.auto_filter.ref = f"A1:{get_column_letter(len(headers2))}{len(deleted_students) + 1}"

    for col in ws2.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws2.column_dimensions[col_letter].width = max(max_len + 4, 12)

    # ==========================================
    # SHEET 3: Resumen Ejecutivo
    # ==========================================
    ws3 = wb.create_sheet(title="Resumen Ejecutivo")
    ws3.sheet_properties.tabColor = "00897B"

    # Title Banner
    ws3.merge_cells("A1:F1")
    title_cell = ws3["A1"]
    title_cell.value = "INSTITUTO DE DESARROLLO INTEGRAL LIC. JOSÉ VASCONCELOS (IJOVA)"
    title_cell.font = Font(name="Segoe UI", size=14, bold=True, color="FFFFFF")
    title_cell.fill = header_fill
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws3.row_dimensions[1].height = 32

    ws3.merge_cells("A2:F2")
    sub_cell = ws3["A2"]
    sub_cell.value = "REPORTE GENERAL DE CUENTAS ESTUDIANTILES MICROSOFT 365 EDUCATION"
    sub_cell.font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    sub_cell.fill = sub_header_fill
    sub_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws3.row_dimensions[2].height = 24

    # Metadata Block
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    meta_rows = [
        ("Fecha de Extracción Cloud:", now_str),
        ("Tenant ID Microsoft Entra:", config.tenant_id),
        ("Dominio Institucional:", f"{config.domain} (Verificado / Managed)"),
        ("Administrador de Extracción:", admin_user),
        ("Licenciamiento Estudiantil:", "Office 365 Education A1 (STANDARDWOFFPACK_STUDENT)"),
    ]

    for i, (label, val) in enumerate(meta_rows, start=4):
        ws3.cell(row=i, column=1, value=label).font = data_font_bold
        ws3.cell(row=i, column=2, value=val).font = data_font
        ws3.row_dimensions[i].height = 20

    # Table 1: Métricas de Cuentas
    t1_start = 10
    ws3.cell(row=t1_start, column=1, value="MÉTRICAS GLOBALES DE CUENTAS").font = Font(name="Segoe UI", size=11, bold=True, color=navy_primary)
    
    t1_headers = ["Categoría de Cuenta", "Total", "Porcentaje", "Estado Operativo"]
    for c_idx, h in enumerate(t1_headers, start=1):
        c = ws3.cell(row=t1_start + 1, column=c_idx, value=h)
        c.fill = header_fill
        c.font = header_font
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = thin_border

    tot_active = len(active_students)
    tot_del = len(deleted_students)
    grand_total = tot_active + tot_del
    tot_con_foto = sum(1 for s in active_students if school_db.get(s.get('userPrincipalName', '').split('@')[0], {}).get('tiene_foto'))

    t1_data = [
        ("🎓 Alumnos Activos en Tenant", tot_active, f"{(tot_active / grand_total * 100):.1f}%", "Activos / Con Licencia A1"),
        ("🗑️ Alumnos en Papelera (Bajas)", tot_del, f"{(tot_del / grand_total * 100):.1f}%", "Recuperables (< 30 días)"),
        ("TOTAL CUENTAS GESTIONADAS", grand_total, "100.0%", "Total Histórico en Cloud"),
        ("🖼️ Alumnos Activos con Foto Institucional", tot_con_foto, f"{(tot_con_foto / tot_active * 100):.1f}%", "Auditados con Fotografía"),
        ("⏳ Alumnos Activos sin Foto", tot_active - tot_con_foto, f"{((tot_active - tot_con_foto) / tot_active * 100):.1f}%", "Pendientes de Subir Foto")
    ]

    for idx, (cat, cnt, pct, note) in enumerate(t1_data, start=t1_start + 2):
        ws3.row_dimensions[idx].height = 20
        c1 = ws3.cell(row=idx, column=1, value=cat)
        c2 = ws3.cell(row=idx, column=2, value=cnt)
        c3 = ws3.cell(row=idx, column=3, value=pct)
        c4 = ws3.cell(row=idx, column=4, value=note)

        for c in [c1, c2, c3, c4]:
            c.border = thin_border
            c.font = data_font_bold if "TOTAL" in cat else data_font
            c.fill = zebra_fill if idx % 2 == 0 else white_fill

        c2.alignment = Alignment(horizontal="center")
        c3.alignment = Alignment(horizontal="center")

    # Table 2: Desglose por Nivel Escolar (Alumnos Activos)
    t2_start = t1_start + len(t1_data) + 3
    ws3.cell(row=t2_start, column=1, value="DISTRIBUCIÓN DE ALUMNOS ACTIVOS POR NIVEL EDUCATIVO").font = Font(name="Segoe UI", size=11, bold=True, color=navy_primary)

    t2_headers = ["Nivel Educativo", "Cantidad de Alumnos", "Porcentaje de Población"]
    for c_idx, h in enumerate(t2_headers, start=1):
        c = ws3.cell(row=t2_start + 1, column=c_idx, value=h)
        c.fill = header_fill
        c.font = header_font
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = thin_border

    import collections
    nivel_counts = collections.Counter()
    for s in active_students:
        mat = s.get('userPrincipalName', '').split('@')[0]
        niv = school_db.get(mat, {}).get('nivel') or 'Sin Nivel Asignado'
        nivel_counts[niv] += 1

    niveles_orden = ["Primaria", "Secundaria", "Preparatoria", "Preescolar"]
    for n in list(nivel_counts.keys()):
        if n not in niveles_orden:
            niveles_orden.append(n)

    for idx, niv in enumerate(niveles_orden, start=t2_start + 2):
        cnt = nivel_counts.get(niv, 0)
        pct = f"{(cnt / tot_active * 100):.1f}%" if tot_active > 0 else "0%"
        ws3.row_dimensions[idx].height = 20

        c1 = ws3.cell(row=idx, column=1, value=niv)
        c2 = ws3.cell(row=idx, column=2, value=cnt)
        c3 = ws3.cell(row=idx, column=3, value=pct)

        for c in [c1, c2, c3]:
            c.border = thin_border
            c.font = data_font
            c.fill = zebra_fill if idx % 2 == 0 else white_fill

        c2.alignment = Alignment(horizontal="center")
        c3.alignment = Alignment(horizontal="center")

    # Column widths for Sheet 3
    ws3.column_dimensions['A'].width = 44
    ws3.column_dimensions['B'].width = 30
    ws3.column_dimensions['C'].width = 24
    ws3.column_dimensions['D'].width = 32
    ws3.column_dimensions['E'].width = 18
    ws3.column_dimensions['F'].width = 18

    # Save to all target paths
    for p in output_paths:
        os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
        wb.save(p)
        print(f"💾 Reporte Excel guardado exitosamente en: {p}")

    return {
        "active_count": tot_active,
        "deleted_count": tot_del,
        "total_managed": grand_total,
        "nivel_distribution": dict(nivel_counts),
        "con_foto": tot_con_foto,
        "admin_user": admin_user,
        "paths": output_paths
    }


if __name__ == "__main__":
    paths = [
        "Alumnos_M365_IJOVA_Completo_2026-09-18.xlsx",
        "reports/Alumnos_M365_IJOVA_Completo_2026-09-18.xlsx"
    ]
    res = generate_excel_report(paths)
    print("\n🎉 EXPORTACIÓN COMPLETADA SATISFACTORIAMENTE:")
    print(f"   - Alumnos Activos: {res['active_count']}")
    print(f"   - Alumnos en Papelera: {res['deleted_count']}")
    print(f"   - Total Gestionados: {res['total_managed']}")
