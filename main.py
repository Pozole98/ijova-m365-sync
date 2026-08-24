#!/usr/bin/env python3
"""
CLI Principal de Aprovisionamiento y Sincronización Segura hacia Microsoft 365 / Microsoft Entra ID.

Fase 1: Validación Local, Auditoría de Tenant y Simulación DRY-RUN (Cero Escritura).
"""
import os
import sys
import argparse
from src.config import load_config
from src.excel_parser import parse_excel_students
from src.validator import validate_students
from src.normalizer import normalize_students, export_normalized_data
from src.graph_client import GraphClient, GraphClientError
from src.auditor import create_audit_snapshot
from src.sync_engine import run_sync_comparison
from src.report_generator import generate_reports
from src.models import ClassificationEnum


def cmd_validate(args):
    """
    Comando 'validate': Ejecuta la validación y normalización local offline.
    No requiere conexión a Microsoft Graph.
    """
    config = load_config(args.config)
    print(f"📖 Leyendo archivo Excel: {config.excel_path} (Hoja: {config.sheet_name})...")
    
    students = parse_excel_students(config.excel_path, config.sheet_name)
    print(f"✅ {len(students)} registros extraídos correctamente.")

    print("🔍 Ejecutando motor de validación de reglas de integridad...")
    students = validate_students(students, expected_domain=config.domain)

    print("⚙️ Normalizando atributos técnicos (conservando nombres humanos)...")
    students = normalize_students(students, domain=config.domain)

    norm_file = export_normalized_data(students, output_dir=f"{config.data_dir}/normalized")
    print(f"💾 Copia normalizada exportada a: {norm_file}")

    # Report results (without Graph cross-check, valid items are marked as NUEVO/pending)
    generate_reports(students, discrepancies=[], output_dir=config.reports_dir, is_dry_run=False)


def cmd_dry_run(args):
    """
    Comando 'dry-run': Flujo integrado de validación, auditoría de Entra ID y simulación.
    CERO ESCRITURA: No crea, modifica, elimina ni altera usuarios o licencias.
    """
    config = load_config(args.config)

    if not config.tenant_id or not config.client_id:
        print("\n❌ ERROR DE CONFIGURACIÓN:")
        print("   Para ejecutar el 'dry-run' se requiere 'tenant_id' y 'client_id'.")
        print("   Puedes configurarlos en 'config.json' o mediante las variables de entorno:")
        print("   export M365_TENANT_ID='tu-tenant-id'")
        print("   export M365_CLIENT_ID='tu-client-id'")
        print("\n   Si deseas ejecutar la validación local sin credenciales de Graph, usa:")
        print("   python3 main.py validate\n")
        sys.exit(1)

    # 1. Leer y validar Excel local
    print(f"📖 [Paso 1/6] Leyendo archivo Excel: {config.excel_path}...")
    students = parse_excel_students(config.excel_path, config.sheet_name)
    students = validate_students(students, expected_domain=config.domain)
    students = normalize_students(students, domain=config.domain)
    export_normalized_data(students, output_dir=f"{config.data_dir}/normalized")

    # 2. Autenticación Microsoft Graph
    print(f"\n🔐 [Paso 2/6] Iniciando conexión con Microsoft Graph (Mínimo Privilegio)...")
    graph = GraphClient(
        tenant_id=config.tenant_id,
        client_id=config.client_id,
        scopes=config.graph_scopes
    )
    try:
        graph.authenticate_device_code()
    except GraphClientError as e:
        print(f"\n❌ Error fatal de autenticación: {e}")
        sys.exit(1)

    # 3. Verificación de Dominio
    print(f"\n🌐 [Paso 3/6] Verificando estado del dominio institucional '{config.domain}'...")
    try:
        domain_status = graph.verify_domain(config.domain)
        if domain_status.is_blocked:
            print(f"\n❌ BLOQUEO CRÍTICO: {domain_status.block_reason}")
            print("   El proceso se detiene de forma segura. Resuelva la verificación del dominio antes de continuar.")
            sys.exit(1)
        else:
            print(f"✅ Dominio '{config.domain}' verificado y activo (Tipo: {domain_status.authentication_type}).")
    except GraphClientError as e:
        print(f"\n❌ Error al verificar dominios: {e}")
        sys.exit(1)

    # 4. Descarga de usuarios existentes de Entra ID
    print(f"\n📥 [Paso 4/6] Descargando usuarios existentes del tenant de Microsoft 365 con paginación...")
    try:
        entra_users = graph.get_all_users()
    except GraphClientError as e:
        print(f"\n❌ Error fatal en la consulta de usuarios: {e}")
        print("   SALVAGUARDA ACTIVA: El proceso se aborta inmediatamente para evitar clasificaciones erróneas.")
        sys.exit(1)

    # 5. Generación de Snapshot de Auditoría Atómico (con purga de retención para protección de datos de menores)
    print(f"\n📸 [Paso 5/6] Generando snapshot atómico de auditoría en '{config.backups_dir}'...")
    create_audit_snapshot(
        users=entra_users,
        domain_status=domain_status,
        tenant_id=config.tenant_id,
        output_dir=config.backups_dir,
        retention_days=config.retention_days
    )

    # 6. Sincronización Lógica y Clasificación
    print(f"\n⚡ [Paso 6/6] Comparando alumnos de Excel contra Entra ID por UPN...")
    students, discrepancies = run_sync_comparison(students, entra_users)

    # Generar reportes finales y CSVs con rastro de auditoría
    generate_reports(
        students=students,
        discrepancies=discrepancies,
        domain_status=domain_status,
        admin_upn=graph.admin_upn,
        output_dir=config.reports_dir,
        is_dry_run=True
    )
    print("\n🏁 Simulación DRY-RUN completada con éxito. CERO cambios realizados en Microsoft 365.")


def cmd_backup(args):
    """
    Comando 'backup': Extrae y guarda un snapshot de usuarios existentes de Entra ID.
    """
    config = load_config(args.config)
    if not config.tenant_id or not config.client_id:
        print("❌ Se requiere 'tenant_id' y 'client_id' en config.json para ejecutar el backup.")
        sys.exit(1)

    graph = GraphClient(config.tenant_id, config.client_id, config.graph_scopes)
    graph.authenticate_device_code()
    users = graph.get_all_users()
    domain_status = graph.verify_domain(config.domain)
    create_audit_snapshot(
        users,
        domain_status=domain_status,
        tenant_id=config.tenant_id,
        output_dir=config.backups_dir,
        retention_days=config.retention_days
    )


def cmd_apply(args):
    """
    Comando 'apply': Ejecuta el aprovisionamiento real y seguro de los alumnos clasificados como NUEVO.
    - CERO afectación sobre cuentas existentes.
    - Re-verificación anti-drift.
    - Asignación de licencias Office 365 A1.
    - Almacenamiento seguro de contraseñas temporales en secrets/ (0600).
    """
    config = load_config(args.config)

    if not config.tenant_id or not config.client_id:
        print("❌ Se requiere 'tenant_id' y 'client_id' en config.json para ejecutar el aprovisionamiento.")
        sys.exit(1)

    print("\n" + "=" * 80)
    print("⚠️ ADVERTENCIA DE APROVISIONAMIENTO EN VIVO - MICROSOFT 365")
    print("=" * 80)
    print("Este comando creará las cuentas de alumnos nuevos en Microsoft Entra ID y asignará licencias A1.")
    print("Las cuentas existentes serán detectadas y conservadas 100% intactas.")
    print("=" * 80)

    if not args.yes:
        confirm = input("\n¿Deseas proceder con la creación de los alumnos nuevos? (Escribe 'SI' para confirmar): ")
        if confirm.strip().upper() != "SI":
            print("⛔ Operación cancelada por el usuario. No se realizaron cambios.")
            sys.exit(0)

    # 1. Leer y validar Excel local
    print(f"\n📖 [Paso 1/7] Leyendo archivo Excel: {config.excel_path}...")
    students = parse_excel_students(config.excel_path, config.sheet_name)
    students = validate_students(students, expected_domain=config.domain)
    students = normalize_students(students, domain=config.domain)
    export_normalized_data(students, output_dir=f"{config.data_dir}/normalized")

    # 2. Autenticación con scopes de escritura
    write_scopes = ["User.ReadWrite.All", "Domain.Read.All", "LicenseAssignment.Read.All"]
    print(f"\n🔐 [Paso 2/7] Conectando a Microsoft Graph con permisos de aprovisionamiento...")
    graph = GraphClient(
        tenant_id=config.tenant_id,
        client_id=config.client_id,
        scopes=write_scopes
    )
    try:
        graph.authenticate_device_code()
    except GraphClientError as e:
        print(f"\n❌ Error fatal de autenticación: {e}")
        sys.exit(1)

    # 3. Verificación de Dominio
    print(f"\n🌐 [Paso 3/7] Verificando dominio institucional '{config.domain}'...")
    domain_status = graph.verify_domain(config.domain)
    if domain_status.is_blocked:
        print(f"\n❌ BLOQUEO: {domain_status.block_reason}")
        sys.exit(1)

    # 4. Descarga de usuarios actuales y Snapshot preventivo
    print(f"\n📥 [Paso 4/7] Descargando estado actual del tenant para snapshot previo...")
    entra_users = graph.get_all_users()
    create_audit_snapshot(
        users=entra_users,
        domain_status=domain_status,
        tenant_id=config.tenant_id,
        output_dir=config.backups_dir,
        retention_days=config.retention_days
    )

    # 5. Clasificación y filtrado exclusivo de NUEVOS
    print(f"\n⚡ [Paso 5/7] Identificando alumnos candidatos a creación...")
    students, discrepancies = run_sync_comparison(students, entra_users)
    new_students = [s for s in students if s.classification == ClassificationEnum.NUEVO]

    print(f"📊 Estado actual:")
    print(f"   - Alumnos existentes en tenant: {len([s for s in students if s.classification == ClassificationEnum.EXISTENTE])} (Intactos)")
    print(f"   - Alumnos nuevos a crear:      {len(new_students)}")
    print(f"   - Alumnos en conflicto:         {len([s for s in students if s.classification == ClassificationEnum.CONFLICTO])} (Bloqueados)")

    if not new_students:
        print("\n✅ No hay alumnos nuevos pendientes de creación. El tenant ya está al día.")
        sys.exit(0)

    # 6. Ejecutar aprovisionamiento
    from src.provisioner import execute_provisioning
    print(f"\n🚀 [Paso 6/7] Creando {len(new_students)} cuentas de alumnos nuevos...")
    prov_result = execute_provisioning(
        new_students=new_students,
        graph=graph,
        secrets_dir=config.secrets_dir,
        reports_dir=config.reports_dir
    )

    # 7. Re-sincronización y reporte final post-creación
    print(f"\n🔄 [Paso 7/7] Re-verificando estado final del tenant con Graph...")
    final_users = graph.get_all_users()
    final_students, final_disc = run_sync_comparison(students, final_users)

    generate_reports(
        students=final_students,
        discrepancies=final_disc,
        domain_status=domain_status,
        admin_upn=graph.admin_upn,
        output_dir=config.reports_dir,
        is_dry_run=False
    )
    print("\n🎉 APROVISIONAMIENTO FASE 2 COMPLETADO CON ÉXITO.")


def cmd_enroll(args):
    """
    Comando 'enroll': Asistente de alta interactiva rápida para alumnos extemporáneos.
    Crea la cuenta en Microsoft 365, asigna licencia A1, guarda en Excel y genera Ficha de Bienvenida.
    """
    config = load_config(args.config)
    if not config.tenant_id or not config.client_id:
        print("❌ Se requiere 'tenant_id' y 'client_id' en config.json para registrar alumnos.")
        sys.exit(1)

    from src.enroll_engine import execute_interactive_enrollment
    write_scopes = ["User.ReadWrite.All", "Domain.Read.All", "LicenseAssignment.Read.All"]
    graph = GraphClient(config.tenant_id, config.client_id, write_scopes)
    graph.authenticate_device_code()

    execute_interactive_enrollment(
        graph=graph,
        excel_path=config.excel_path,
        sheet_name=config.sheet_name,
        secrets_dir=config.secrets_dir,
        domain=config.domain
    )


def cmd_delete(args):
    """
    Comando 'delete': Baja y eliminación segura de alumnos en Microsoft 365 a partir de su matrícula.
    Bloquea eliminación de cuentas de administradores o personal, envía a papelera (30 días) y actualiza Excel.
    """
    config = load_config(args.config)
    if not config.tenant_id or not config.client_id:
        print("❌ Se requiere 'tenant_id' y 'client_id' en config.json para dar de baja alumnos.")
        sys.exit(1)

    identifiers: list[str] = []

    # 1. Matrículas pasadas como argumentos posicionales
    if args.matriculas:
        identifiers.extend(args.matriculas)

    # 2. Matrículas leídas desde archivo de texto
    if args.file:
        if not os.path.exists(args.file):
            print(f"❌ El archivo '{args.file}' no existe.")
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if line_str and not line_str.startswith("#"):
                    identifiers.append(line_str)

    # 3. Matrículas leídas desde archivo Excel
    if args.excel:
        if not os.path.exists(args.excel):
            print(f"❌ El archivo Excel '{args.excel}' no existe.")
            sys.exit(1)
        from src.excel_parser import extract_matriculas_from_excel
        excel_mats = extract_matriculas_from_excel(args.excel, args.sheet)
        print(f"📑 {len(excel_mats)} matrículas extraídas desde '{args.excel}'.")
        identifiers.extend(excel_mats)

    # 4. Si no se especificó nada, solicitar interactivamente
    if not identifiers:
        mat_in = input("👉 Ingresa la Matrícula del alumno a dar de baja (ej. 250010): ").strip()
        if mat_in:
            identifiers.append(mat_in)
        else:
            print("⛔ No se ingresó ninguna matrícula. Operación cancelada.")
            sys.exit(0)

    from src.delete_engine import execute_student_deletion
    write_scopes = ["User.ReadWrite.All", "Domain.Read.All", "LicenseAssignment.Read.All"]
    graph = GraphClient(config.tenant_id, config.client_id, write_scopes)
    graph.authenticate_device_code()

    execute_student_deletion(
        identifiers=identifiers,
        graph=graph,
        excel_path=config.excel_path,
        sheet_name=config.sheet_name,
        reports_dir=config.reports_dir,
        backups_dir=config.backups_dir,
        auto_confirm=args.yes
    )


def cmd_restore(args):
    """
    Comando 'restore': Restaura un alumno desde la papelera de reciclaje de Microsoft Entra ID.
    """
    config = load_config(args.config)
    if not config.tenant_id or not config.client_id:
        print("❌ Se requiere 'tenant_id' y 'client_id' en config.json para restaurar alumnos.")
        sys.exit(1)

    from src.restore_engine import execute_student_restoration
    write_scopes = ["User.ReadWrite.All", "Domain.Read.All", "LicenseAssignment.Read.All"]
    graph = GraphClient(config.tenant_id, config.client_id, write_scopes)
    graph.authenticate_device_code()

    execute_student_restoration(
        identifier=args.matricula,
        graph=graph,
        domain=config.domain,
        excel_path=config.excel_path,
        sheet_name=config.sheet_name
    )


def cmd_status(args):
    """
    Comando 'status': Muestra el tablero ejecutivo de salud del tenant, licencias y usuarios.
    """
    config = load_config(args.config)
    if not config.tenant_id or not config.client_id:
        print("❌ Se requiere 'tenant_id' y 'client_id' en config.json para consultar el estado.")
        sys.exit(1)

    from src.status_engine import execute_tenant_status_check
    read_scopes = ["User.Read.All", "Domain.Read.All", "LicenseAssignment.Read.All"]
    graph = GraphClient(config.tenant_id, config.client_id, read_scopes)
    graph.authenticate_device_code()

    execute_tenant_status_check(
        graph=graph,
        domain=config.domain,
        backups_dir=config.backups_dir
    )


def cmd_export_pdf(args):
    """
    Comando 'export-pdf': Genera documentos PDF imprimibles con fichas de acceso y códigos QR.
    """
    config = load_config(args.config)
    from src.pdf_generator import generate_pdf_from_credentials_csv

    csv_file = args.file
    if not csv_file:
        # Buscar el archivo de credenciales más reciente en secrets/
        if os.path.exists(config.secrets_dir):
            cred_files = sorted([
                os.path.join(config.secrets_dir, f)
                for f in os.listdir(config.secrets_dir)
                if f.startswith("credenciales_alumnos_") and f.endswith(".csv")
            ])
            if cred_files:
                csv_file = cred_files[-1]

    if not csv_file or not os.path.exists(csv_file):
        print(f"❌ No se encontró ningún archivo de credenciales para generar el PDF.")
        print(f"   Especifica la ruta con --file ruta/al/archivo.csv")
        sys.exit(1)

    output_pdf = args.output
    if not output_pdf:
        timestamp_str = os.path.splitext(os.path.basename(csv_file))[0]
        output_pdf = os.path.join("reports", f"fichas_acceso_{timestamp_str}_{args.mode}.pdf")

    print(f"📄 Leyendo credenciales desde: \033[1m{csv_file}\033[0m")
    print(f"⚙️ Modo de maquetación:        \033[1m{'4 Tarjetas por hoja (Recortables)' if args.mode == 'cards' else '1 Ficha por hoja (Expediente)'}\033[0m")
    
    generated_path = generate_pdf_from_credentials_csv(
        csv_file_path=csv_file,
        output_pdf_path=output_pdf,
        layout_mode=args.mode
    )

    print(f"\n🎉 ¡PDF generado exitosamente!")
    print(f"📍 Archivo listo para imprimir: \033[1;32m{generated_path}\033[0m")


def cmd_reset(args):
    """
    Comando 'reset': Restablece contraseñas de alumnos (individual, masivo --all, o lote desde Excel).
    """
    config = load_config(args.config)
    if not config.tenant_id or not config.client_id:
        print("❌ Se requiere 'tenant_id' y 'client_id' en config.json para restablecer contraseñas.")
        sys.exit(1)

    from src.reset_engine import execute_password_reset, execute_bulk_password_reset
    from src.excel_parser import parse_excel_students, extract_matriculas_from_excel

    write_scopes = ["User.ReadWrite.All", "Domain.Read.All", "LicenseAssignment.Read.All"]
    graph = GraphClient(config.tenant_id, config.client_id, write_scopes)
    graph.authenticate_device_code()

    # 1. Modo --all: Restablecer a todos los alumnos activos en Microsoft 365
    if getattr(args, "all", False):
        print("\n🔍 Recuperando todos los alumnos activos en Microsoft 365...")
        all_users = graph.get_all_users()
        students_data = []

        # Intentar cargar metadata de nivel/grado desde Excel para enriquecer fichas
        excel_map = {}
        try:
            ex_students = parse_excel_students(config.excel_path, config.sheet_name)
            for es in ex_students:
                excel_map[es.matricula] = es
        except Exception:
            pass

        for u in all_users:
            prefix = u.user_principal_name.split("@")[0]
            if prefix.isdigit():
                es_info = excel_map.get(prefix)
                students_data.append({
                    "matricula": prefix,
                    "upn": u.user_principal_name,
                    "display_name": u.display_name,
                    "id": u.id,
                    "nivel": es_info.nivel if es_info else "Estudiante",
                    "grado_semestre": es_info.grado_semestre if es_info else "Activo"
                })

        if not students_data:
            print("ℹ️ No se encontraron alumnos activos en Microsoft 365.")
            sys.exit(0)

        execute_bulk_password_reset(
            students_data=students_data,
            graph=graph,
            domain=config.domain,
            secrets_dir=config.secrets_dir,
            reports_dir=config.reports_dir,
            auto_confirm=args.yes
        )
        return

    # 2. Modo --excel: Restablecer alumnos leídos desde un Excel
    if getattr(args, "excel", None):
        if not os.path.exists(args.excel):
            print(f"❌ El archivo Excel '{args.excel}' no existe.")
            sys.exit(1)
        mats = extract_matriculas_from_excel(args.excel, args.sheet)
        print(f"📑 {len(mats)} matrículas extraídas desde '{args.excel}'.")
        students_data = []
        for m in mats:
            u = graph.get_user_by_upn(f"{m}@{config.domain}")
            if u:
                students_data.append({
                    "matricula": m,
                    "upn": f"{m}@{config.domain}",
                    "display_name": u.get("displayName", "Alumno"),
                    "id": u.get("id"),
                    "nivel": "Estudiante",
                    "grado_semestre": "Activo"
                })
        execute_bulk_password_reset(
            students_data=students_data,
            graph=graph,
            domain=config.domain,
            secrets_dir=config.secrets_dir,
            reports_dir=config.reports_dir,
            auto_confirm=args.yes
        )
        return

    # 3. Matrículas pasadas como argumentos
    mats = getattr(args, "matriculas", [])
    if mats:
        if len(mats) == 1:
            execute_password_reset(
                identifier=mats[0],
                graph=graph,
                domain=config.domain,
                secrets_dir=config.secrets_dir,
                reports_dir=config.reports_dir
            )
        else:
            students_data = []
            for m in mats:
                u = graph.get_user_by_upn(f"{m}@{config.domain}")
                if u:
                    students_data.append({
                        "matricula": m,
                        "upn": f"{m}@{config.domain}",
                        "display_name": u.get("displayName", "Alumno"),
                        "id": u.get("id"),
                        "nivel": "Estudiante",
                        "grado_semestre": "Activo"
                    })
            execute_bulk_password_reset(
                students_data=students_data,
                graph=graph,
                domain=config.domain,
                secrets_dir=config.secrets_dir,
                reports_dir=config.reports_dir,
                auto_confirm=args.yes
            )
        return

    # 4. Solicitud interactiva individual si no se pasó ningún parámetro
    mat_in = input("👉 Ingresa la Matrícula del alumno a restablecer (ej. 250081): ").strip()
    if mat_in:
        execute_password_reset(
            identifier=mat_in,
            graph=graph,
            domain=config.domain,
            secrets_dir=config.secrets_dir,
            reports_dir=config.reports_dir
        )
    else:
        print("⛔ No se ingresó ninguna matrícula.")


def main():
    parser = argparse.ArgumentParser(
        description="Sistema de Aprovisionamiento, Gestión y Sincronización Segura de Alumnos hacia Microsoft 365 / Entra ID"
    )
    parser.add_argument(
        "-c", "--config",
        default="config.json",
        help="Ruta al archivo de configuración JSON (por defecto: config.json)"
    )

    subparsers = parser.add_subparsers(dest="command", help="Comandos disponibles")

    # validate command
    p_validate = subparsers.add_parser("validate", help="Valida el archivo Excel y genera datos normalizados de forma offline")

    # dry-run command
    p_dryrun = subparsers.add_parser("dry-run", help="Ejecuta la simulación completa contra Entra ID sin escrituras")

    # backup command
    p_backup = subparsers.add_parser("backup", help="Genera un snapshot de auditoría de los usuarios actuales en Entra ID")

    # apply command
    p_apply = subparsers.add_parser("apply", help="Crea los alumnos nuevos y asigna licencias A1 en Microsoft 365")
    p_apply.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Confirma automáticamente la creación sin solicitar confirmación interactiva"
    )

    # enroll command
    p_enroll = subparsers.add_parser("enroll", help="Asistente interactivo de alta rápida para alumnos nuevos extemporáneos")

    # delete command
    p_delete = subparsers.add_parser("delete", help="Elimina alumnos de Microsoft 365 a partir de su matrícula (individual, archivo o Excel)")
    p_delete.add_argument(
        "matriculas",
        nargs="*",
        help="Una o más matrículas a eliminar (ej. 250010 250062)"
    )
    p_delete.add_argument(
        "-f", "--file",
        help="Ruta a un archivo de texto con lista de matrículas a dar de baja (una por línea)"
    )
    p_delete.add_argument(
        "--excel",
        help="Ruta a un archivo Excel con listado o columna de matrículas a dar de baja"
    )
    p_delete.add_argument(
        "--sheet",
        help="Nombre de la hoja de Excel (opcional)"
    )
    p_delete.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Confirma automáticamente las eliminaciones sin solicitar confirmación interactiva"
    )

    # restore command
    p_restore = subparsers.add_parser("restore", help="Restaura un alumno desde la papelera de reciclaje de Entra ID (< 30 días)")
    p_restore.add_argument(
        "matricula",
        help="Matrícula del alumno a restaurar (ej. 250010)"
    )

    # status command
    p_status = subparsers.add_parser("status", help="Muestra el tablero ejecutivo de salud del tenant, licencias A1 y usuarios")
    p_health = subparsers.add_parser("health", help="Alias de 'status'")

    # export-pdf command
    p_pdf = subparsers.add_parser("export-pdf", help="Genera documento PDF imprimible con tarjetas de acceso y códigos QR")
    p_pdf.add_argument(
        "-f", "--file",
        help="Ruta al archivo CSV de credenciales (por defecto: el más reciente en secrets/)"
    )
    p_pdf.add_argument(
        "-o", "--output",
        help="Ruta de salida para el archivo PDF generado"
    )
    p_pdf.add_argument(
        "-m", "--mode",
        choices=["cards", "full"],
        default="cards",
        help="Modo de maquetación: 'cards' (4 tarjetas recortables por hoja) o 'full' (1 ficha por hoja)"
    )

    # reset command
    p_reset = subparsers.add_parser("reset", help="Restablece contraseñas de alumnos (individual, masivo --all, o lote desde Excel)")
    p_reset.add_argument(
        "matriculas",
        nargs="*",
        help="Una o más matrículas de alumnos a restablecer (ej. 250081 250082)"
    )
    p_reset.add_argument(
        "--all",
        action="store_true",
        help="Restablece la contraseña de TODOS los alumnos activos en Microsoft 365 (Inicio de Semestre)"
    )
    p_reset.add_argument(
        "--excel",
        help="Ruta a un archivo Excel con listado o columna de alumnos a restablecer"
    )
    p_reset.add_argument(
        "--sheet",
        help="Nombre de la hoja de Excel (opcional)"
    )
    p_reset.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Confirma automáticamente el reseteo sin solicitar confirmación interactiva"
    )

    # menu command
    p_menu = subparsers.add_parser("menu", help="Inicia el Menú Interactivo en Terminal con todas las funciones explicadas")

    args = parser.parse_args()

    # Si no se pasó ningún comando o se solicitó 'menu', abrir el menú interactivo guiado
    if not args.command or args.command == "menu":
        from src.menu import run_interactive_menu
        run_interactive_menu(args.config)
        sys.exit(0)

    if args.command == "validate":
        cmd_validate(args)
    elif args.command == "dry-run":
        cmd_dry_run(args)
    elif args.command == "backup":
        cmd_backup(args)
    elif args.command == "apply":
        cmd_apply(args)
    elif args.command == "enroll":
        cmd_enroll(args)
    elif args.command == "delete":
        cmd_delete(args)
    elif args.command == "restore":
        cmd_restore(args)
    elif args.command in ["status", "health"]:
        cmd_status(args)
    elif args.command == "export-pdf":
        cmd_export_pdf(args)
    elif args.command == "reset":
        cmd_reset(args)


if __name__ == "__main__":
    main()
