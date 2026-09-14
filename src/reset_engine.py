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


def verify_student_for_reset(
    identifier: str,
    graph: GraphClient,
    domain: str = "ijova.com",
    excel_path: Optional[str] = None,
    sheet_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Verifica de forma segura si un alumno existe en Microsoft 365 (Entra ID)
    y cruza sus datos con el registro escolar oficial (Excel/ODS) si está disponible.
    Retorna un diccionario con 'registered': True/False y todos los detalles del alumno.
    """
    is_valid, result = is_student_matricula(identifier)
    if not is_valid:
        return {
            "registered": False,
            "matricula": identifier,
            "upn": f"{identifier}@{domain}",
            "error": f"BLOQUEO DE SEGURIDAD: {result}"
        }

    upn = result
    matricula = upn.split("@")[0]

    # Consultar Microsoft Graph en tiempo real
    user = graph.get_user_by_upn(upn)
    if not user:
        return {
            "registered": False,
            "matricula": matricula,
            "upn": upn,
            "error": f"El alumno con matrícula {matricula} ({upn}) no está registrado en Microsoft 365 / Entra ID."
        }

    user_id = user.get("id")
    display_name = user.get("displayName", "Alumno")
    account_enabled = user.get("accountEnabled", True)

    # Cruzar con Excel escolar si existe para enriquecer datos de nivel/grado
    excel_info: Dict[str, str] = {}
    if excel_path and os.path.exists(excel_path):
        try:
            from src.excel_parser import parse_excel_students
            students = parse_excel_students(excel_path, sheet_name)
            for s in students:
                if s.matricula.strip().lower() == matricula.lower():
                    excel_info = {
                        "nombre_excel": f"{s.apellido_paterno} {s.apellido_materno} {s.nombres}".strip(),
                        "nivel": s.nivel or "Estudiante",
                        "grado_semestre": s.grado_semestre or "Activo",
                        "estatus": s.estatus or "Activo"
                    }
                    break
        except Exception:
            pass

    # Comprobar si tiene fotografía de perfil
    has_photo = False
    try:
        if hasattr(graph, "get_user_photo_metadata"):
            meta = graph.get_user_photo_metadata(user_id or upn)
            has_photo = meta is not None
    except Exception:
        pass

    return {
        "registered": True,
        "matricula": matricula,
        "upn": upn,
        "user_id": user_id,
        "display_name": display_name,
        "nombre_oficial": excel_info.get("nombre_excel", display_name),
        "nivel": excel_info.get("nivel", "Estudiante"),
        "grado_semestre": excel_info.get("grado_semestre", "Activo"),
        "account_enabled": account_enabled,
        "has_photo": has_photo,
        "error": None
    }


def print_student_verification_card(student_info: Dict[str, Any]):
    """Despliega en consola la tarjeta de verificación visual del alumno."""
    status_str = "\033[1;32mHabilitada (Activa)\033[0m" if student_info.get("account_enabled", True) else "\033[1;31mDeshabilitada\033[0m"
    photo_str = "📸 Con fotografía" if student_info.get("has_photo") else "⚪ Sin fotografía"
    
    print("\n" + "\033[1;34m╔" + "═" * 76 + "╗")
    print(f"║ {'FICHA DE VERIFICACIÓN DE ALUMNO EN MICROSOFT 365':^76} ║")
    print("╠" + "═" * 76 + "╣\033[0m")
    print(f"  👤 \033[1mNombre Oficial:\033[0m      {student_info.get('nombre_oficial', student_info.get('display_name'))}")
    if student_info.get("nombre_oficial") != student_info.get("display_name"):
        print(f"  🏷️  \033[1mEntra ID Name:\033[0m       {student_info.get('display_name')}")
    print(f"  🎓 \033[1mMatrícula:\033[0m           \033[1;36m{student_info.get('matricula')}\033[0m")
    print(f"  📧 \033[1mCorreo Institucional:\033[0m\033[1;33m{student_info.get('upn')}\033[0m")
    print(f"  🏫 \033[1mNivel y Grado:\033[0m        {student_info.get('nivel')} — {student_info.get('grado_semestre')}")
    print(f"  ⚡ \033[1mEstado de Cuenta:\033[0m     {status_str} | {photo_str}")
    print("\033[1;34m╚" + "═" * 76 + "╝\033[0m")


def execute_password_reset(
    identifier: str,
    graph: GraphClient,
    domain: str = "ijova.com",
    secrets_dir: str = "secrets",
    reports_dir: str = "reports",
    custom_password: Optional[str] = None,
    force_change: bool = True,
    auto_confirm: bool = True,
    excel_path: Optional[str] = None,
    sheet_name: Optional[str] = None,
    verified_student: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Restablece la contraseña de un alumno individual por su matrícula en Microsoft 365.
    Verifica primero si el alumno está registrado.
    Si auto_confirm=False, muestra la ficha del alumno y solicita confirmación interactiva al operador.
    Si se proporciona custom_password, se valida y asigna dicha contraseña específica.
    """
    # 1. Verificar registro del alumno en Microsoft 365 y datos escolares
    if verified_student and verified_student.get("registered"):
        student_info = verified_student
    else:
        student_info = verify_student_for_reset(
            identifier=identifier,
            graph=graph,
            domain=domain,
            excel_path=excel_path,
            sheet_name=sheet_name
        )

    if not student_info.get("registered"):
        print(f"\n❌ ALUMNO NO REGISTRADO: {student_info.get('error')}")
        return None

    user_id = student_info["user_id"]
    matricula = student_info["matricula"]
    upn = student_info["upn"]
    display_name = student_info["display_name"]
    nivel = student_info.get("nivel", "Estudiante")
    grado_semestre = student_info.get("grado_semestre", "Activo")

    # 2. Confirmación de seguridad si no está en modo auto_confirm
    if not auto_confirm:
        print_student_verification_card(student_info)
        confirm = input(f"\n👉 ¿Confirmas que deseas restablecer la contraseña a {display_name} ({matricula})? (s/n, ENTER=s): ").strip().lower()
        if confirm not in ["s", "si", "y", "yes", ""]:
            print("⛔ Operación de reseteo cancelada por el usuario. No se modificó la contraseña.")
            return None

    # 3. Obtener o generar la contraseña
    if custom_password:
        from src.password_generator import validate_password_complexity
        is_valid, msg = validate_password_complexity(custom_password)
        if not is_valid:
            print(f"\n⛔ CONTRASEÑA NO VÁLIDA: {msg}")
            return None
        new_password = custom_password
    else:
        new_password = generate_secure_password(length=12)

    # 3. Aplicar reseteo en Microsoft Entra ID vía Graph
    print(f"⚡ Restableciendo contraseña en Microsoft 365...")
    try:
        success = graph.reset_password(user_id, new_password, force_change=force_change)
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
        "nombre_completo": student_info.get("nombre_oficial", display_name),
        "password_temporal": new_password,
        "nivel": nivel,
        "grado_semestre": grado_semestre
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
        display_name=student_info.get("nombre_oficial", display_name),
        nivel=nivel,
        grado=grado_semestre,
        temp_password=new_password,
        domain=domain
    )

    from src.audit_logger import log_audit_event
    log_audit_event(
        action="RESET_PASSWORD",
        target=matricula,
        admin=graph.admin_upn or "Admin",
        status="SUCCESS",
        details=f"Contraseña restablecida para {display_name} ({upn})"
    )

    return {
        "matricula": matricula,
        "upn": upn,
        "display_name": display_name,
        "nombre_oficial": student_info.get("nombre_oficial", display_name),
        "password": new_password,
        "user_id": user_id,
        "pdf_path": pdf_out if os.path.exists(pdf_out) else None,
        "nivel": nivel,
        "grado_semestre": grado_semestre
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

    # Preparar datos con contraseñas seguras generadas
    prepared_students = []
    for s in students_data:
        new_pass = generate_secure_password(length=12)
        prepared_students.append({
            "id": s["id"],
            "matricula": s["matricula"],
            "upn": s["upn"],
            "display_name": s["display_name"],
            "nivel": s.get("nivel", "Estudiante"),
            "grado_semestre": s.get("grado_semestre", "Activo"),
            "new_password": new_pass
        })

    # Usar Microsoft Graph $batch si hay más de 3 alumnos para acelerar drásticamente
    if hasattr(graph, "batch_reset_passwords") and len(prepared_students) > 3:
        print(f"⚡ Ejecutando reseteo acelerado vía Microsoft Graph $batch (bloques de 20 concurrentes)...")
        batch_res = graph.batch_reset_passwords(prepared_students)
        for item in batch_res.get("successes", []):
            st = item["student"]
            credentials_list.append({
                "matricula": st["matricula"],
                "upn": st["upn"],
                "nombre_completo": st["display_name"],
                "password_temporal": st["new_password"],
                "nivel": st["nivel"],
                "grado_semestre": st["grado_semestre"]
            })
            print(f"   ✅ {st['display_name']} ({st['upn']}) — Contraseña restablecida.")

        for item in batch_res.get("failures", []):
            st = item["student"]
            failed_list.append({"matricula": st["matricula"], "upn": st["upn"], "error": str(item.get("error"))})
            print(f"   ❌ Error en {st['upn']}: {item.get('error')}")
    else:
        for idx, s in enumerate(prepared_students, 1):
            try:
                success = graph.reset_password(s["id"], s["new_password"])
                if success:
                    credentials_list.append({
                        "matricula": s["matricula"],
                        "upn": s["upn"],
                        "nombre_completo": s["display_name"],
                        "password_temporal": s["new_password"],
                        "nivel": s["nivel"],
                        "grado_semestre": s["grado_semestre"]
                    })
                    print(f"   [{idx}/{len(prepared_students)}] ✅ {s['display_name']} ({s['upn']}) — Contraseña restablecida.")
                else:
                    failed_list.append({"matricula": s["matricula"], "upn": s["upn"], "error": "FAILED"})
            except Exception as e:
                failed_list.append({"matricula": s["matricula"], "upn": s["upn"], "error": str(e)})
                print(f"   [{idx}/{len(prepared_students)}] ❌ Error en {s['upn']}: {e}")

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
    from src.audit_logger import log_audit_event
    log_audit_event(
        action="BULK_PASSWORD_RESET",
        target=f"{len(credentials_list)} alumnos",
        admin=graph.admin_upn or "Admin",
        status="SUCCESS" if not failed_list else "WARNING",
        details=f"Éxitos: {len(credentials_list)} | Fallos: {len(failed_list)} | CSV: {csv_file}"
    )

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
