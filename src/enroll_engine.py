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
    print("\n" + "╔" + "═" * 68 + "╗")
    print(f"║ {'INSTITUTO JOSÉ VASCONCELOS - FICHA DE ACCESO A MICROSOFT 365':^66} ║")
    print("╠" + "═" * 68 + "╣")
    print(f"║ Alumno:        {display_name:<51} ║")
    print(f"║ Matrícula:     {matricula:<51} ║")
    print(f"║ Nivel Escolar: {nivel} ({grado}){' ' * (48 - len(nivel) - len(grado))} ║")
    print("╟" + "─" * 68 + "╢")
    print(f"║ 📧 Correo / Usuario:   \033[1;34m{upn:<44}\033[0m ║")
    print(f"║ 🔑 Contraseña Temporal:\033[1;32m{temp_password:<44}\033[0m ║")
    print("╟" + "─" * 68 + "╢")
    print("║ 🌐 Portal de Acceso:   https://portal.office.com                   ║")
    print("║ ℹ️  Instrucciones:                                                 ║")
    print("║   1. Ingresa a portal.office.com con tu correo y contraseña.       ║")
    print("║   2. El sistema te solicitará cambiar tu contraseña en el primer   ║")
    print("║      inicio de sesión por una personal y segura.                   ║")
    print("║   3. Incluye acceso a Teams, Word, Excel, PowerPoint y OneDrive.   ║")
    print("╚" + "═" * 68 + "╝\n")


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
        if not mat_input.isdigit():
            print("❌ La matrícula debe ser un número entero. Intenta nuevamente.")
            continue

        upn = f"{mat_input}@{domain.lower()}"
        print(f"   🔍 Verificando disponibilidad de {upn} en Microsoft Entra ID...")
        existing = graph.get_user_by_upn(upn)
        if existing:
            print(f"❌ La matrícula {mat_input} YA EXISTE en Microsoft 365 ({existing.get('displayName')}).")
            continue
        
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

    return {
        "matricula": mat_input,
        "upn": upn,
        "display_name": display_name,
        "password": temp_password,
        "user_id": user_id
    }
