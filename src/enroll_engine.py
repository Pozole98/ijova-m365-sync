"""
Motor de alta interactiva de alumnos extemporáneos hacia Microsoft 365 / Entra ID.
Crea la cuenta, asigna licencia A1, actualiza el archivo Excel y genera la Ficha de Bienvenida.
"""
import os
import csv
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from src.graph_client import GraphClient, GraphClientError
from src.password_generator import generate_secure_password
from src.excel_parser import append_student_to_excel


def print_welcome_card(
    matricula: str,
    upn: str,
    display_name: str,
    nivel: str,
    grado: str,
    temp_password: str,
    domain: str = "ijova.com"
):
    """
    Imprime una Ficha de Bienvenida con formato limpio y profesional para entregar al alumno/tutor.
    """
    print("\n" + "╔" + "═" * 72 + "╗")
    print(f"║ {'INSTITUTO DE DESARROLLO INTEGRAL LIC. JOSÉ VASCONCELOS (IJOVA)':^70} ║")
    print(f"║ {'FICHA DE ACCESO A MICROSOFT 365':^70} ║")
    print("╠" + "═" * 72 + "╣")
    print(f"║ Alumno:        {display_name:<55} ║")
    print(f"║ Matrícula:     {matricula:<55} ║")
    print(f"║ Nivel Escolar: {nivel} ({grado}){' ' * (52 - len(nivel) - len(grado))} ║")
    print("╟" + "─" * 72 + "╢")
    print(f"║ 📧 Correo / Usuario:   \033[1;34m{upn:<48}\033[0m ║")
    print(f"║ 🔑 Contraseña Temporal:\033[1;32m{temp_password:<48}\033[0m ║")
    print("╟" + "─" * 72 + "╢")
    print("║ 🌐 Portal de Acceso:   https://portal.office.com                             ║")
    print("║ ℹ️  Instrucciones:                                                           ║")
    print("║   1. Ingresa a portal.office.com con tu correo y contraseña.                 ║")
    print("║   2. El sistema te solicitará cambiar tu contraseña en el primer             ║")
    print("║      inicio de sesión por una personal y segura.                             ║")
    print("║   3. Incluye acceso a Teams, Word, Excel, PowerPoint y OneDrive.             ║")
    print("╚" + "═" * 72 + "╝\n")


def execute_interactive_enrollment(
    graph: GraphClient,
    excel_path: str = "Listado de Alumnos Inscritos.xlsx",
    sheet_name: str = "Listado Global Matriculado",
    secrets_dir: str = "secrets",
    domain: str = "ijova.com"
) -> Optional[Dict[str, Any]]:
    """
    Guía al operador para registrar un nuevo alumno paso a paso.
    """
    print("\n" + "=" * 70)
    print("🎓 REGISTRO Y ALTA RÁPIDA DE ALUMNO NUEVO (MICROSOFT 365)")
    print("=" * 70)

    # 1. Solicitar Matrícula
    while True:
        mat_input = input("\n👉 Ingresa la Matrícula del alumno (ej. 260017): ").strip()
        from src.validator import is_valid_matricula_format
        if not is_valid_matricula_format(mat_input):
            print("❌ Formato de matrícula inválido. Debe constar exactamente de 6 dígitos numéricos iniciando con el año (ej. 25xxxx o 26xxxx). Intenta nuevamente.")
            continue

        upn = f"{mat_input}@{domain.lower()}"
        print(f"   🔍 Verificando disponibilidad de {upn} en Microsoft Entra ID...")
        existing = graph.get_user_by_upn(upn)
        if existing:
            print(f"❌ La matrícula {mat_input} YA EXISTE en Microsoft 365 ({existing.get('displayName')}).")
            continue

        # Verificar si la matrícula existe en la Papelera de Reciclaje (< 30 días de baja)
        try:
            deleted_users = graph.get_deleted_users()
        except Exception:
            deleted_users = []

        del_user = None
        for du in deleted_users:
            d_upn = (du.get("userPrincipalName") or "").strip().lower()
            d_nick = (du.get("mailNickname") or "").strip().lower()
            if d_upn == upn.lower() or d_nick == mat_input.lower():
                del_user = du
                break

        if del_user:
            del_name = del_user.get("displayName", "Alumno")
            del_date = del_user.get("deletedDateTime", "Recientemente")
            print(f"\n⚠️ ATENCIÓN: La matrícula {mat_input} se encuentra en la Papelera de Reciclaje de Microsoft Entra ID.")
            print(f"   👤 Alumno registrado: \033[1m{del_name}\033[0m (Eliminado el {del_date})")
            print("   💡 Esta cuenta puede ser RESTAURADA conservando intacto su buzón, OneDrive y tareas.")
            resp = input("   👉 ¿Deseas restaurar esta cuenta en lugar de registrar una nueva? (s/n): ").strip().lower()
            if resp in ["s", "si", "y", "yes"]:
                from src.restore_engine import execute_student_restoration
                from src.audit_logger import log_audit_event
                log_audit_event(
                    action="ENROLL_RESTORE_REDIRECT",
                    target=mat_input,
                    admin=graph.admin_upn or "Admin",
                    status="SUCCESS",
                    details=f"Redirigido a restauración de cuenta en papelera: {del_name}"
                )
                return execute_student_restoration(mat_input, graph, domain, excel_path, sheet_name, auto_confirm=True)
            else:
                print("   ℹ️ Continuando con el proceso de alta...")

        print(f"   ✅ Matrícula {mat_input} disponible.")
        break

    # 2. Solicitar Nombres y Apellidos
    while True:
        nombres = input("👉 Nombre(s) del alumno: ").strip().upper()
        if nombres:
            break
        print("❌ El nombre no puede estar vacío.")

    while True:
        paterno = input("👉 Apellido Paterno: ").strip().upper()
        if paterno:
            break
    materno = input("👉 Apellido Materno (opcional, presiona Enter si no tiene): ").strip().upper()
    full_name = f"{nombres} {paterno} {materno}".strip()

    # --- Validación de Matrícula Intransferible (Histórico de Bajas) ---
    from src.historical_registry import check_matricula_transfer_conflict
    is_conflict, conflict_msg = check_matricula_transfer_conflict(mat_input, full_name)
    if is_conflict:
        print("\n" + "=" * 70)
        print("⛔ BLOQUEO DE SEGURIDAD (MATRÍCULA INTRANSFERIBLE)")
        print("=" * 70)
        print(conflict_msg)
        print("=" * 70)
        print("⛔ Registro cancelado por conflicto de identidad histórica.")
        from src.audit_logger import log_audit_event
        log_audit_event(
            action="ENROLL",
            target=mat_input,
            admin=graph.admin_upn or "Admin",
            status="BLOCKED",
            details=f"Conflicto de matrícula intransferible con {full_name}: {conflict_msg}"
        )
        return None

    # 3. Nivel Escolar
    print("\n👉 Selecciona el Nivel Escolar:")
    print("   [1] Preescolar")
    print("   [2] Primaria")
    print("   [3] Secundaria")
    print("   [4] Preparatoria")
    nivel_map = {"1": "Preescolar", "2": "Primaria", "3": "Secundaria", "4": "Preparatoria"}
    while True:
        opt = input("   Opción (1-4): ").strip()
        if opt in nivel_map:
            nivel = nivel_map[opt]
            break
        print("❌ Opción inválida. Selecciona 1, 2, 3 o 4.")

    # 4. Grado
    grado = input("👉 Grado o Semestre (ej. 1ro, 2do, 3ro, 4to, 5to, 6to): ").strip()
    if not grado:
        grado = "1ro"

    # Resumen y confirmación previa
    display_name = f"{nombres} {paterno}".strip()
    print("\n" + "-" * 50)
    print("📋 DATOS DEL ALUMNO A REGISTRAR:")
    print(f"   • Alumno:      {display_name}")
    print(f"   • Matrícula:   {mat_input}")
    print(f"   • UPN / Mail:  {upn}")
    print(f"   • Nivel/Grado: {nivel} ({grado})")
    print("-" * 50)

    confirm = input("¿Proceder con la creación en Microsoft 365 y guardado en Excel? (s/n): ")
    if confirm.strip().lower() not in ["s", "si", "y", "yes"]:
        print("⛔ Registro cancelado por el usuario.")
        return None

    # 5. Generar Contraseña Temporal Segura
    temp_password = generate_secure_password(length=12)

    # 6. Crear Usuario en Microsoft Entra ID
    payload = {
        "accountEnabled": True,
        "displayName": display_name,
        "givenName": nombres,
        "surname": paterno,
        "mailNickname": mat_input,
        "userPrincipalName": upn,
        "usageLocation": "MX",
        "passwordProfile": {
            "forceChangePasswordNextSignIn": True,
            "password": temp_password
        }
    }

    print(f"\n🚀 Creando usuario {upn} en Microsoft Entra ID...")
    try:
        created_user = graph.create_user(payload)
        user_id = created_user.get("id")
        print(f"✅ Cuenta creada exitosamente en la nube (ID: {user_id}).")
    except Exception as e:
        print(f"❌ Error al crear usuario en Microsoft Graph: {e}")
        return None

    # 7. Asignar Licencia Office 365 A1
    student_sku = graph.find_student_sku()
    license_assigned = False
    if student_sku and user_id:
        time.sleep(0.5)
        license_assigned = graph.assign_license(user_id, student_sku["skuId"])
        if license_assigned:
            print(f"🏷️ Licencia {student_sku['skuPartNumber']} asignada correctamente.")
        else:
            print("⚠️ No se pudo asignar la licencia automáticamente.")

    # 8. Agregar Fila al Excel
    try:
        row_num = append_student_to_excel(
            excel_path=excel_path,
            sheet_name=sheet_name,
            matricula=mat_input,
            nombres=nombres,
            apellido_paterno=paterno,
            apellido_materno=materno,
            nivel=nivel,
            grado_semestre=grado,
            estatus="Activo"
        )
        print(f"📑 Alumno guardado en el archivo Excel (Fila {row_num}).")
    except Exception as e:
        print(f"⚠️ No se pudo actualizar el Excel automáticamente: {e}")

    # 9. Guardar Credencial en secrets/
    os.makedirs(secrets_dir, exist_ok=True)
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
    creds_file = os.path.join(secrets_dir, f"credencial_alumno_{mat_input}_{timestamp_str}.csv")
    with open(creds_file, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["matricula", "upn", "nombre_completo", "nivel", "grado_semestre", "password_temporal", "fecha_creacion_utc"])
        writer.writeheader()
        writer.writerow({
            "matricula": mat_input,
            "upn": upn,
            "nombre_completo": display_name,
            "nivel": nivel,
            "grado_semestre": grado,
            "password_temporal": temp_password,
            "fecha_creacion_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        })
    try:
        os.chmod(creds_file, 0o600)
    except Exception:
        pass

    # 10. Generar Ficha Individual en PDF lista para imprimir
    try:
        from src.pdf_generator import generate_pdf_cards_from_list
        pdf_out = os.path.join(secrets_dir, f"ficha_acceso_{mat_input}_{timestamp_str}.pdf")
        student_dict = {
            "matricula": mat_input,
            "upn": upn,
            "nombre_completo": display_name,
            "password_temporal": temp_password,
            "nivel": nivel,
            "grado_semestre": grado
        }
        generate_pdf_cards_from_list([student_dict], pdf_out, layout_mode="cards")
        print(f"📄 Ficha de Acceso en PDF generada: \033[1;32m{pdf_out}\033[0m")
    except Exception as e:
        print(f"⚠️ No se pudo generar el PDF individual: {e}")

    # 11. Imprimir Ficha de Bienvenida en consola
    print_welcome_card(
        matricula=mat_input,
        upn=upn,
        display_name=display_name,
        nivel=nivel,
        grado=grado,
        temp_password=temp_password,
        domain=domain
    )

    from src.audit_logger import log_audit_event
    log_audit_event(
        action="ENROLL",
        target=mat_input,
        admin=graph.admin_upn or "Admin",
        status="SUCCESS",
        details=f"Alta exitosa: {display_name} ({upn}) | Nivel: {nivel} ({grado}) | Entra ID: {user_id}"
    )

    return {
        "matricula": mat_input,
        "upn": upn,
        "display_name": display_name,
        "password": temp_password,
        "user_id": user_id
    }


def enroll_student_programmatic(
    graph: Optional[GraphClient],
    student_data: Dict[str, Any],
    tutor_data: Optional[Dict[str, Any]] = None,
    provision_m365: bool = True,
    domain: str = "ijova.com",
    reports_dir: str = "reports"
) -> Dict[str, Any]:
    """
    Registra un alumno en la base de datos MariaDB y opcionalmente lo aprovisiona
    en Microsoft Entra ID asignandole licencia Office 365 A1 y generando su ficha PDF.
    """
    from src.validator import is_valid_matricula_format
    from src.historical_registry import check_matricula_transfer_conflict
    from src.audit_logger import log_audit_event
    from src.db import create_student, update_student

    mat = str(student_data.get("matricula", "")).strip()
    if not is_valid_matricula_format(mat):
        raise ValueError(f"Formato de matricula invalido ({mat}). Debe constar exactamente de 6 digitos.")

    paterno = (student_data.get("paterno") or "").strip().upper()
    materno = (student_data.get("materno") or "").strip().upper()
    nombres = (student_data.get("nombres") or "").strip().upper()
    display_name = f"{paterno} {materno} {nombres}".strip() if (paterno or nombres) else (student_data.get("nombre_oficial") or mat)
    nivel = (student_data.get("nivel") or "Secundaria").strip()
    grado = (student_data.get("grado") or "1°").strip()
    upn = f"{mat}@{domain.lower()}"

    # Verificacion de conflicto historico
    is_conflict, conflict_msg = check_matricula_transfer_conflict(mat, display_name)
    if is_conflict:
        log_audit_event(
            action="ENROLL_DB",
            target=mat,
            admin="admin@ijova.com",
            status="BLOCKED",
            details=f"Conflicto historico con {display_name}: {conflict_msg}"
        )
        raise ValueError(f"Bloqueo de seguridad: {conflict_msg}")

    # 1. Guardar en MariaDB
    db_student = create_student(
        student_data={
            "matricula": mat,
            "nombre_oficial": display_name,
            "paterno": paterno,
            "materno": materno,
            "nombres": nombres,
            "nivel": nivel,
            "grado": grado,
            "seccion": student_data.get("seccion") or "A",
            "curp": student_data.get("curp") or "",
            "sexo": student_data.get("sexo") or "",
            "estatus": "Activo",
            "upn": upn,
            "ciclo": student_data.get("ciclo") or "2026-2027"
        },
        tutor_data=tutor_data
    )

    result = {
        "success": True,
        "matricula": mat,
        "upn": upn,
        "display_name": display_name,
        "nivel": nivel,
        "grado": grado,
        "database_saved": True,
        "m365_provisioned": False,
        "temp_password": None,
        "pdf_filename": None,
        "license_assigned": False
    }

    # 2. Aprovisionar en Microsoft 365 si se solicito y graph esta disponible
    if provision_m365 and graph:
        try:
            temp_password = generate_secure_password(length=12)
            existing_user = graph.get_user_by_upn(upn)
            user_id = None

            if existing_user:
                user_id = existing_user.get("id")
                # Si existe, habilitar y actualizar credencial
                graph.reset_user_password(user_id, temp_password, force_change_next_sign_in=True)
            else:
                payload = {
                    "accountEnabled": True,
                    "displayName": display_name,
                    "givenName": nombres or display_name,
                    "surname": paterno,
                    "mailNickname": mat,
                    "userPrincipalName": upn,
                    "usageLocation": "MX",
                    "passwordProfile": {
                        "forceChangePasswordNextSignIn": True,
                        "password": temp_password
                    }
                }
                created = graph.create_user(payload)
                user_id = created.get("id")

            result["m365_provisioned"] = True
            result["user_id"] = user_id
            result["temp_password"] = temp_password

            # Asignar licencia
            student_sku = graph.find_student_sku()
            if student_sku and user_id:
                time.sleep(0.5)
                lic_ok = graph.assign_license(user_id, student_sku["skuId"])
                result["license_assigned"] = lic_ok

            # Actualizar m365_user_id en MariaDB
            update_student(mat, {"m365_user_id": user_id})

            # Generar ficha PDF individual
            from src.pdf_generator import generate_pdf_cards_from_list
            os.makedirs(reports_dir, exist_ok=True)
            timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
            pdf_filename = f"ficha_acceso_{mat}_{timestamp_str}.pdf"
            pdf_path = os.path.join(reports_dir, pdf_filename)
            student_dict = {
                "matricula": mat,
                "upn": upn,
                "nombre_completo": display_name,
                "password_temporal": temp_password,
                "nivel": nivel,
                "grado_semestre": grado
            }
            generate_pdf_cards_from_list([student_dict], pdf_path, layout_mode="cards")
            result["pdf_filename"] = pdf_filename

            log_audit_event(
                action="ENROLL_WEBUI",
                target=mat,
                admin="admin@ijova.com",
                status="SUCCESS",
                details=f"Alta completa: {display_name} en MariaDB y M365 (Licencia: {result['license_assigned']})"
            )
        except Exception as e:
            result["m365_error"] = str(e)
            log_audit_event(
                action="ENROLL_WEBUI",
                target=mat,
                admin="admin@ijova.com",
                status="WARNING",
                details=f"Guardado en MariaDB pero error en M365: {e}"
            )

    return result
