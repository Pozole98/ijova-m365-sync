"""
Motor de reseteo rápido y masivo de contraseñas para alumnos en Microsoft 365 / Entra ID.
Soporta reseteo individual en 2 segundos o reseteo masivo para inicio de semestre con generación
automática de credenciales protegidas y fichas PDF con código QR listas para imprimir.
"""
import os
import csv
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from tabulate import tabulate

from src.graph_client import GraphClient, GraphClientError
from src.password_generator import generate_secure_password
from src.enroll_engine import print_welcome_card
from src.delete_engine import is_student_matricula
from src.pdf_generator import generate_pdf_cards_from_list, generate_pdf_from_credentials_csv


def execute_password_reset(
    identifier: str,
    graph: GraphClient,
    domain: str = "ijova.com",
    secrets_dir: str = "secrets",
    reports_dir: str = "reports"
) -> Optional[Dict[str, Any]]:
    """
    Restablece la contraseña de un alumno individual por su matrícula en Microsoft 365.
    """
    # 1. Validar salvaguarda anti-admin (solo matrículas estudiantiles)
    is_valid, result = is_student_matricula(identifier)
    if not is_valid:
        print(f"\n⛔ BLOQUEO DE SEGURIDAD: {result}")
        return None

    upn = result
    matricula = upn.split("@")[0]

    print(f"\n🔍 Buscando alumno con matrícula \033[1;34m{matricula}\033[0m ({upn})...")
    user = graph.get_user_by_upn(upn)
    if not user:
        print(f"❌ El alumno {upn} no existe en Microsoft Entra ID.")
        return None

    user_id = user.get("id")
    display_name = user.get("displayName", "Alumno")

    print(f"   👤 Alumno: \033[1m{display_name}\033[0m (ID: {user_id})")

    # 2. Generar nueva contraseña temporal segura
    new_password = generate_secure_password(length=12)

    # 3. Aplicar reseteo en Microsoft Entra ID vía Graph
    print(f"⚡ Restableciendo contraseña en Microsoft 365...")
    try:
        success = graph.reset_password(user_id, new_password)
        if not success:
            print(f"❌ No se pudo restablecer la contraseña en Graph.")
            return None
        print(f"✅ Contraseña restablecida con éxito en la nube.")
    except Exception as e:
        print(f"❌ Error al comunicarse con Microsoft Graph: {e}")
        return None

    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
    
    # 4. Guardar en bitácora protegida de reseteos en secrets/
    os.makedirs(secrets_dir, exist_ok=True)
    os.makedirs(reports_dir, exist_ok=True)
    reset_log_file = os.path.join(secrets_dir, "historial_reseteos_contrasenas.csv")
    file_exists = os.path.exists(reset_log_file)
    with open(reset_log_file, "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["matricula", "upn", "display_name", "nueva_password", "reset_by", "timestamp_utc"])
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "matricula": matricula,
            "upn": upn,
            "display_name": display_name,
            "nueva_password": new_password,
            "reset_by": graph.admin_upn or "admin",
            "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        })
    try:
        os.chmod(reset_log_file, 0o600)
    except Exception:
        pass

    # 5. Generar Ficha Individual en PDF lista para imprimir
    pdf_out = os.path.join(secrets_dir, f"ficha_acceso_reset_{matricula}_{timestamp_str}.pdf")
    student_dict = {
        "matricula": matricula,
        "upn": upn,
        "nombre_completo": display_name,
        "password_temporal": new_password,
        "nivel": "Estudiante",
        "grado_semestre": "Activo"
    }
    try:
        generate_pdf_cards_from_list([student_dict], pdf_out, layout_mode="cards")
        print(f"📄 Ficha PDF generada lista para imprimir: \033[1;32m{pdf_out}\033[0m")
    except Exception as e:
        print(f"⚠️ No se pudo generar el PDF individual: {e}")

    # 6. Imprimir Ficha en consola
    print_welcome_card(
        matricula=matricula,
        upn=upn,
        display_name=display_name,
        nivel="Estudiante",
        grado="Activo",
        temp_password=new_password,
        domain=domain
    )

    return {
        "matricula": matricula,
        "upn": upn,
        "display_name": display_name,
        "password": new_password,
        "pdf_path": pdf_out
    }


def execute_bulk_password_reset(
    students_data: List[Dict[str, Any]],
    graph: GraphClient,
    domain: str = "ijova.com",
    secrets_dir: str = "secrets",
    reports_dir: str = "reports",
    auto_confirm: bool = False
) -> Dict[str, Any]:
    """
    Restablece masivamente las contraseñas de una lista de alumnos (ej. Inicio de Semestre).
    Genera el archivo de credenciales protegido (0600) y los dos formatos de PDF (tarjetas y expediente).
    """
    if not students_data:
        print("\n⚠️ No se proporcionaron alumnos para restablecer contraseñas.")
        return {"reset_count": 0}

    os.makedirs(secrets_dir, exist_ok=True)
    os.makedirs(reports_dir, exist_ok=True)
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")

    print("\n" + "=" * 80)
    print(f"📋 RESUMEN DE ALUMNOS PARA RESETEO MASIVO DE CONTRASEÑAS (Total: {len(students_data)})")
    print("=" * 80)

    table_data = []
    for idx, s in enumerate(students_data[:20], 1):
        table_data.append([idx, s["matricula"], s["display_name"], s["upn"], s.get("nivel", "Estudiante")])

    print(tabulate(
        table_data,
        headers=["#", "Matrícula", "Nombre Completo", "Correo Institucional", "Nivel"],
        tablefmt="fancy_grid"
    ))
    if len(students_data) > 20:
        print(f"   ... y {len(students_data) - 20} alumnos más en la lista.")

    # 1. Confirmación de Seguridad
    if not auto_confirm:
        print("\n⚠️ Esta acción generará NUEVAS contraseñas temporales para todos estos alumnos.")
        confirm = input(f"¿Confirmas el reseteo masivo de {len(students_data)} alumnos? (Escribe 'RESETEAR' para confirmar): ").strip().upper()
        if confirm != "RESETEAR":
            print("⛔ Operación de reseteo masivo cancelada por el usuario. No se modificó ninguna contraseña.")
            return {"reset_count": 0, "cancelled": True}

    print(f"\n🚀 Iniciando reseteo masivo en Microsoft Entra ID vía Graph API...")

    credentials_list: List[Dict[str, Any]] = []
    failed_list: List[Dict[str, Any]] = []

    for idx, s in enumerate(students_data, 1):
        mat = s["matricula"]
        upn = s["upn"]
        user_id = s["id"]
        dname = s["display_name"]
        nivel = s.get("nivel", "Estudiante")
        grado = s.get("grado_semestre", "Activo")

        new_pass = generate_secure_password(length=12)

        try:
            success = graph.reset_password(user_id, new_pass)
            if success:
                credentials_list.append({
                    "matricula": mat,
                    "upn": upn,
                    "nombre_completo": dname,
                    "password_temporal": new_pass,
                    "nivel": nivel,
                    "grado_semestre": grado
                })
                print(f"   [{idx}/{len(students_data)}] ✅ {dname} ({upn}) — Contraseña restablecida.")
            else:
                failed_list.append({"matricula": mat, "upn": upn, "error": "FAILED"})
        except Exception as e:
            failed_list.append({"matricula": mat, "upn": upn, "error": str(e)})
            print(f"   [{idx}/{len(students_data)}] ❌ Error en {upn}: {e}")

    # 2. Guardar archivo CSV de credenciales con permisos Unix 0600
    csv_file = os.path.join(secrets_dir, f"credenciales_alumnos_reset_{timestamp_str}.csv")
    with open(csv_file, "w", encoding="utf-8-sig", newline="") as f:
        fieldnames = ["matricula", "upn", "nombre_completo", "password_temporal", "nivel", "grado_semestre"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for c in credentials_list:
            writer.writerow(c)
    try:
        os.chmod(csv_file, 0o600)
    except Exception:
        pass

    print(f"\n🔐 Archivo de credenciales resguardado en: \033[1;32m{csv_file}\033[0m (Permisos 0600)")

    # 3. Generar Documentos PDF imprimibles (Tarjetas 4 por hoja y Ficha completa)
    pdf_cards = os.path.join(reports_dir, f"fichas_alumnos_reset_{timestamp_str}_cards.pdf")
    pdf_full = os.path.join(reports_dir, f"fichas_alumnos_reset_{timestamp_str}_expediente.pdf")

    try:
        generate_pdf_from_credentials_csv(csv_file, pdf_cards, layout_mode="cards")
        generate_pdf_from_credentials_csv(csv_file, pdf_full, layout_mode="full")
        print(f"🖨️ PDF Recortable (4 por hoja) listo para repartir: \033[1;32m{pdf_cards}\033[0m")
        print(f"📁 PDF Expediente (1 por hoja) generado en:        \033[1;32m{pdf_full}\033[0m")
    except Exception as e:
        print(f"⚠️ Error al generar los PDFs: {e}")

    print("\n" + "=" * 80)
    print("🏁 RESUMEN DE RESETEO MASIVO:")
    print("=" * 80)
    print(f"✅ Contraseñas restablecidas con éxito: {len(credentials_list)}")
    print(f"❌ Fallos en reseteo:                   {len(failed_list)}")
    print("ℹ️ Todos los alumnos deberán definir su contraseña personal en su primer acceso.")

    return {
        "reset_count": len(credentials_list),
        "failed_count": len(failed_list),
        "csv_path": csv_file,
        "pdf_cards": pdf_cards,
        "pdf_full": pdf_full
    }


def execute_modular_grade_password_reset(
    graph: GraphClient,
    excel_path: str = "Listado_Global_Matriculado_M365.ods",
    sheet_name: str = "Listado Global Matriculado",
    target_levels: Optional[List[str]] = None,
    output_base_dir: str = "reports/fichas_entregas_2026",
    secrets_dir: str = "secrets",
    auto_confirm: bool = False
) -> Dict[str, Any]:
    """
    Restablece contraseñas de los niveles seleccionados (ej. Secundaria y Preparatoria)
    y genera carpetas independientes por nivel y grado con sus respectivos PDFs recortables
    (6 tarjetas por hoja) y archivos CSV de credenciales.
    """
    from collections import defaultdict
    from src.excel_parser import parse_excel_students
    from src.pdf_generator import generate_pdf_cards_from_list

    if target_levels is None:
        target_levels = ["Secundaria", "Preparatoria"]

    students = parse_excel_students(excel_path, sheet_name)
    target_students = [s for s in students if s.nivel in target_levels]

    if not target_students:
        print(f"⚠️ No se encontraron alumnos para los niveles: {target_levels} en {excel_path}")
        return {"reset_count": 0}

    # Consultar Microsoft Graph para obtener los IDs reales de Entra ID
    print(f"\n🔍 Consultando identidades en Microsoft Entra ID para {len(target_students)} alumnos...")
    all_users = graph.get_all_users()
    entra_map = {u.user_principal_name.lower(): u for u in all_users}

    students_to_reset = []
    missing = []

    for s in target_students:
        domain = "ijova.com"
        upn = f"{s.matricula}@{domain}".lower()
        u = entra_map.get(upn)
        if u:
            students_to_reset.append({
                "matricula": s.matricula,
                "upn": upn,
                "id": u.id,
                "display_name": u.display_name or f"{s.nombres} {s.apellido_paterno}",
                "nivel": s.nivel,
                "grado_semestre": s.grado_semestre
            })
        else:
            missing.append(s)

    print(f"✅ {len(students_to_reset)} alumnos listos para reseteo en Microsoft Entra ID.")
    if missing:
        print(f"ℹ️ {len(missing)} alumnos no encontrados en Entra ID (omitidos del reseteo).")

    if not auto_confirm:
        print("\n" + "=" * 80)
        print("📋 RESUMEN POR SALÓN Y GRADO A RESETEAR:")
        print("=" * 80)
        by_lvl_grd_preview = defaultdict(int)
        for s in students_to_reset:
            by_lvl_grd_preview[(s["nivel"], s["grado_semestre"])] += 1
        for (lvl, grd), count in sorted(by_lvl_grd_preview.items()):
            print(f"   • {lvl} -> {grd}: {count} alumnos")
        print(f"\nTotal general: {len(students_to_reset)} alumnos.")
        confirm = input("\n¿Deseas proceder con el reseteo de contraseñas en Microsoft 365 y generación de PDFs? (s/n): ").strip().lower()
        if confirm not in ["s", "si", "y", "yes"]:
            print("⛔ Operación cancelada por el usuario.")
            return {"reset_count": 0, "cancelled": True}

    # Ejecutar reseteo
    print(f"\n🚀 Restableciendo contraseñas de {len(students_to_reset)} alumnos en Microsoft 365...")
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
    reset_success = []
    failed_list = []

    for idx, s in enumerate(students_to_reset, 1):
        new_pass = generate_secure_password(length=12)
        try:
            success = graph.reset_password(s["id"], new_pass)
            if success:
                rec = {
                    "matricula": s["matricula"],
                    "upn": s["upn"],
                    "nombre_completo": s["display_name"],
                    "password_temporal": new_pass,
                    "nivel": s["nivel"],
                    "grado_semestre": s["grado_semestre"]
                }
                reset_success.append(rec)
                print(f"   [{idx}/{len(students_to_reset)}] ✅ {s['display_name']} ({s['upn']}) — Contraseña restablecida.")
            else:
                failed_list.append({"matricula": s["matricula"], "error": "FAILED"})
        except Exception as e:
            failed_list.append({"matricula": s["matricula"], "error": str(e)})
            print(f"   [{idx}/{len(students_to_reset)}] ❌ Error en {s['upn']}: {e}")

    # Guardar Respaldo Global en secrets/ (0600)
    os.makedirs(secrets_dir, exist_ok=True)
    master_csv = os.path.join(secrets_dir, f"credenciales_alumnos_reset_secundaria_preparatoria_{timestamp_str}.csv")
    with open(master_csv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["matricula", "upn", "nombre_completo", "password_temporal", "nivel", "grado_semestre"])
        writer.writeheader()
        for r in reset_success:
            writer.writerow(r)
    try:
        os.chmod(master_csv, 0o600)
    except Exception:
        pass

    # Generar estructura modular en reports/fichas_entregas_2026/
    by_group = defaultdict(list)
    for r in reset_success:
        lvl_slug = r["nivel"].lower().replace(" ", "_") if r["nivel"] else "general"
        grd_slug = r["grado_semestre"].lower().replace(" ", "_") if r["grado_semestre"] else "general"
        by_group[(lvl_slug, grd_slug, r["nivel"], r["grado_semestre"])].append(r)

    generated_folders = []

    for (lvl_slug, grd_slug, lvl_display, grd_display), group_students in by_group.items():
        group_dir = os.path.join(output_base_dir, lvl_slug, grd_slug)
        os.makedirs(group_dir, exist_ok=True)

        pdf_filename = f"Fichas_Recortables_{lvl_display}_{grd_display}.pdf".replace(" ", "_")
        csv_filename = f"Credenciales_{lvl_display}_{grd_display}.csv".replace(" ", "_")

        pdf_path = os.path.join(group_dir, pdf_filename)
        csv_path = os.path.join(group_dir, csv_filename)

        # 1. Guardar CSV del salón
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["matricula", "upn", "nombre_completo", "password_temporal", "nivel", "grado_semestre"])
            writer.writeheader()
            for gs in group_students:
                writer.writerow(gs)

        # 2. Generar PDF con 6 tarjetas por hoja
        generate_pdf_cards_from_list(group_students, pdf_path, layout_mode="cards")

        generated_folders.append({
            "nivel": lvl_display,
            "grado": grd_display,
            "count": len(group_students),
            "pdf": pdf_path,
            "csv": csv_path,
            "dir": group_dir
        })

    print("\n" + "=" * 80)
    print("🏁 RESUMEN FINAL DE RESETEO Y ENTREGABLES MODULARES:")
    print("=" * 80)
    print(f"✅ Total de cuentas restablecidas: {len(reset_success)}")
    print(f"❌ Fallos:                         {len(failed_list)}")
    print(f"🔐 Respaldo Global Cifrado:       \033[1;32m{master_csv}\033[0m (Permisos 0600)")
    print(f"\n📁 CARPETAS Y FICHAS PDF GENERADAS POR SALÓN ({output_base_dir}):")
    for g in generated_folders:
        print(f"   • \033[1m{g['nivel']} {g['grado']}\033[0m ({g['count']} alumnos):")
        print(f"     📄 PDF listo para imprimir: \033[1;32m{g['pdf']}\033[0m")
        print(f"     📊 Lista de contraseñas:   {g['csv']}")

    return {
        "reset_count": len(reset_success),
        "failed_count": len(failed_list),
        "master_csv": master_csv,
        "groups": generated_folders
    }
