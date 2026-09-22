"""
Menú interactivo por terminal para el sistema de gestión de alumnos de Microsoft 365 / Entra ID.
Permite a cualquier operador administrativo acceder a todas las funciones guiadas paso a paso.
"""
import os
import sys
from typing import Optional
from src.config import load_config, AppConfig
from src.graph_client import GraphClient, GraphClientError


def clear_screen():
    """Limpia la terminal para una experiencia visual limpia."""
    os.system('clear' if os.name != 'nt' else 'cls')


def pause():
    """Pausa la ejecución para que el usuario pueda leer los resultados."""
    input("\n👉 Presiona \033[1mENTER\033[0m para volver al Menú Principal...")


def print_banner(config: AppConfig):
    """Muestra el encabezado institucional oficial."""
    print("\033[1;34m" + "╔" + "═" * 84 + "╗")
    print(f"║ {'INSTITUTO DE DESARROLLO INTEGRAL LIC. JOSÉ VASCONCELOS (IJOVA)':^84} ║")
    print(f"║ {'SISTEMA DE GESTIÓN Y SINCRONIZACIÓN MICROSOFT 365':^84} ║")
    print("╠" + "═" * 84 + "╣")
    print(f"║ Dominio: \033[1;32m{config.domain:<22}\033[1;34m Archivo Base: \033[1m{config.excel_path:<40}\033[1;34m ║")
    print("╚" + "═" * 84 + "╝\033[0m\n")


def menu_validate(config: AppConfig):
    clear_screen()
    print("=" * 80)
    print("🔍 [1] VALIDACIÓN LOCAL DEL ARCHIVO EXCEL (OFFLINE)")
    print("=" * 80)
    print("📌 ¿Qué hace esta función?")
    print("   • Lee la hoja 'Listado Global Matriculado' de tu archivo Excel.")
    print("   • Valida que no haya matrículas duplicadas ni nombres inválidos.")
    print("   • Genera la copia normalizada en 'data/normalized/alumnos_normalizados.csv'.")
    print("   • NO requiere internet ni modifica ningún usuario en la nube.")
    print("-" * 80)
    
    confirm = input("¿Deseas iniciar la validación local? (s/n): ").strip().lower()
    if confirm in ["s", "si", "y", "yes", ""]:
        from src.excel_parser import parse_excel_students
        from src.validator import validate_students
        from src.normalizer import normalize_students, export_normalized_data
        from src.report_generator import generate_reports

        students = parse_excel_students(config.excel_path, config.sheet_name)
        students = validate_students(students, expected_domain=config.domain)
        students = normalize_students(students, domain=config.domain)
        norm_file = export_normalized_data(students, output_dir=f"{config.data_dir}/normalized")
        generate_reports(students, discrepancies=[], output_dir=config.reports_dir, is_dry_run=False)
    pause()


def menu_dry_run(config: AppConfig):
    clear_screen()
    print("=" * 80)
    print("🌐 [2] SIMULACIÓN DRY-RUN EN LA NUBE (CERO ESCRITURA)")
    print("=" * 80)
    print("📌 ¿Qué hace esta función?")
    print("   • Conecta a Microsoft Entra ID y descarga todos los usuarios existentes.")
    print("   • Compara la lista del Excel contra Microsoft 365 por correo/UPN.")
    print("   • Te indica exactamente cuántos alumnos ya tienen cuenta y cuántos son nuevos.")
    print("   • Respalda un snapshot de seguridad en 'backups/'.")
    print("   • GARANTÍA: NO crea, no modifica y no borra nada en Microsoft 365.")
    print("-" * 80)

    confirm = input("¿Deseas iniciar la simulación Dry-Run? (s/n): ").strip().lower()
    if confirm in ["s", "si", "y", "yes", ""]:
        from src.excel_parser import parse_excel_students
        from src.validator import validate_students
        from src.normalizer import normalize_students, export_normalized_data
        from src.auditor import create_audit_snapshot
        from src.sync_engine import run_sync_comparison
        from src.report_generator import generate_reports

        students = parse_excel_students(config.excel_path, config.sheet_name)
        students = validate_students(students, expected_domain=config.domain)
        students = normalize_students(students, domain=config.domain)
        export_normalized_data(students, output_dir=f"{config.data_dir}/normalized")

        graph = GraphClient(config.tenant_id, config.client_id, config.graph_scopes)
        graph.authenticate_device_code()
        domain_status = graph.verify_domain(config.domain)
        entra_users = graph.get_all_users()

        create_audit_snapshot(entra_users, domain_status, config.tenant_id, config.backups_dir)
        students, disc = run_sync_comparison(students, entra_users)
        generate_reports(students, disc, domain_status, graph.admin_upn, config.reports_dir, is_dry_run=True)
    pause()


def menu_apply(config: AppConfig):
    clear_screen()
    print("=" * 80)
    print("🚀 [3] APROVISIONAMIENTO MASIVO DE ALUMNOS NUEVOS")
    print("=" * 80)
    print("📌 ¿Qué hace esta función?")
    print("   • Detecta automáticamente a los alumnos que NO tienen cuenta en Microsoft 365.")
    print("   • Crea sus cuentas con la convención estándar (Nombre + Paterno).")
    print("   • Asigna automáticamente la licencia Office 365 A1 for Students.")
    print("   • Genera contraseñas temporales seguras en 'secrets/' (0600).")
    print("   • Protege al 100% las cuentas existentes (no toca a ningún usuario existente).")
    print("-" * 80)

    confirm = input("¿Estás seguro de crear los alumnos nuevos en Microsoft 365? (Escribe 'SI' para confirmar): ").strip().upper()
    if confirm == "SI":
        from src.excel_parser import parse_excel_students
        from src.validator import validate_students
        from src.normalizer import normalize_students, export_normalized_data
        from src.auditor import create_audit_snapshot
        from src.sync_engine import run_sync_comparison
        from src.provisioner import execute_provisioning
        from src.report_generator import generate_reports
        from src.models import ClassificationEnum

        students = parse_excel_students(config.excel_path, config.sheet_name)
        students = validate_students(students, expected_domain=config.domain)
        students = normalize_students(students, domain=config.domain)
        export_normalized_data(students, output_dir=f"{config.data_dir}/normalized")

        write_scopes = ["User.ReadWrite.All", "Domain.Read.All", "LicenseAssignment.Read.All"]
        graph = GraphClient(config.tenant_id, config.client_id, write_scopes)
        graph.authenticate_device_code()
        domain_status = graph.verify_domain(config.domain)
        entra_users = graph.get_all_users()

        create_audit_snapshot(entra_users, domain_status, config.tenant_id, config.backups_dir)
        students, disc = run_sync_comparison(students, entra_users)
        new_students = [s for s in students if s.classification == ClassificationEnum.NUEVO]

        if not new_students:
            print("\n✅ Todos los alumnos ya tienen cuenta en Microsoft 365. No hay nada pendiente por crear.")
        else:
            execute_provisioning(new_students, graph, config.secrets_dir, config.reports_dir)
            final_users = graph.get_all_users()
            final_students, final_disc = run_sync_comparison(students, final_users)
            generate_reports(final_students, final_disc, domain_status, graph.admin_upn, config.reports_dir, is_dry_run=False)
    else:
        print("⛔ Operación cancelada por el usuario.")
    pause()


def menu_enroll(config: AppConfig):
    clear_screen()
    print("=" * 80)
    print("🎓 [4] ALTA RÁPIDA DE ALUMNO NUEVO (EXTEMPORÁNEO)")
    print("=" * 80)
    print("📌 ¿Qué hace esta función?")
    print("   • Asistente paso a paso para inscribir a un alumno a mitad de ciclo escolar.")
    print("   • Te pide: Matrícula, Nombre, Apellidos, Nivel y Grado.")
    print("   • Crea la cuenta en Microsoft 365 y asigna su licencia Office 365 A1.")
    print("   • Añade el registro a tu archivo Excel 'Listado de Alumnos Inscritos.xlsx'.")
    print("   • Genera su Ficha de Acceso en PDF y en pantalla con código QR.")
    print("-" * 80)

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
    pause()


def menu_reset(config: AppConfig):
    clear_screen()
    print("=" * 80)
    print("🔑 [5] RESTABLECER CONTRASEÑAS DE ALUMNOS (INDIVIDUAL O MASIVO)")
    print("=" * 80)
    print("📌 ¿Qué hace esta función?")
    print("   • Permite cambiar la contraseña de un alumno o de TODOS los alumnos para inicio de semestre.")
    print("   • Genera contraseñas temporales seguras de 12 caracteres y exige cambio en el primer inicio.")
    print("   • Exporta automáticamente el archivo protegido de credenciales en 'secrets/' (0600).")
    print("   • Genera de inmediato los PDFs con código QR listos para imprimir y entregar.")
    print("-" * 80)

    print("👉 Selecciona la modalidad de reseteo:")
    print("   \033[1;36m[1]\033[0m Restablecer a UN solo alumno (por matrícula individual)")
    print("   \033[1;32m[2]\033[0m Restablecer a TODOS los alumnos activos en Microsoft 365 (\033[1mInicio de Semestre\033[0m)")
    print("   \033[1;33m[3]\033[0m Restablecer a alumnos desde un archivo Excel o archivo de texto")
    opt = input("\n👉 Opción (1-3): ").strip()

    from src.reset_engine import (
        execute_password_reset,
        execute_bulk_password_reset,
        verify_student_for_reset,
        print_student_verification_card
    )
    from src.excel_parser import parse_excel_students, extract_matriculas_from_excel

    write_scopes = ["User.ReadWrite.All", "Domain.Read.All", "LicenseAssignment.Read.All"]
    graph = GraphClient(config.tenant_id, config.client_id, write_scopes)
    graph.authenticate_device_code()

    if opt == "1":
        matricula = input("\n👉 Ingresa la Matrícula del alumno (ej. 250081): ").strip()
        if not matricula:
            print("⛔ No se ingresó ninguna matrícula.")
        else:
            print(f"\n🔍 Verificando registro del alumno {matricula} en Microsoft 365...")
            student_info = verify_student_for_reset(
                identifier=matricula,
                graph=graph,
                domain=config.domain,
                excel_path=config.excel_path,
                sheet_name=config.sheet_name
            )
            if not student_info.get("registered"):
                print(f"\n❌ ALUMNO NO REGISTRADO:")
                print(f"   {student_info.get('error')}")
                print("   ⚠️  Verifica que la matrícula sea correcta o si el alumno aún no ha sido dado de alta.")
            else:
                print_student_verification_card(student_info)
                confirm = input("\n👉 ¿Confirmas que este es el alumno al que deseas cambiarle la contraseña? (s/n, ENTER=s): ").strip().lower()
                if confirm not in ["s", "si", "y", "yes", ""]:
                    print("⛔ Operación cancelada por el usuario. No se realizó ningún cambio.")
                else:
                    custom_pw = input("👉 Contraseña específica (o presiona ENTER para generar una aleatoria segura): ").strip()
                    force_in = input("👉 ¿Exigir cambio de contraseña en el próximo inicio de sesión? (s/n, ENTER=s): ").strip().lower()
                    force_change = force_in not in ["n", "no"]

                    execute_password_reset(
                        identifier=matricula,
                        graph=graph,
                        domain=config.domain,
                        secrets_dir=config.secrets_dir,
                        reports_dir=config.reports_dir,
                        custom_password=custom_pw if custom_pw else None,
                        force_change=force_change,
                        auto_confirm=True,
                        excel_path=config.excel_path,
                        sheet_name=config.sheet_name,
                        verified_student=student_info
                    )
    elif opt == "2":
        print("\n🔍 Consultando alumnos activos en Microsoft 365...")
        all_users = graph.get_all_users()
        students_data = []

        excel_map = {}
        try:
            ex_students = parse_excel_students(config.excel_path, config.sheet_name)
            for es in ex_students:
                excel_map[es.matricula] = es
        except Exception:
            pass

        from src.validator import is_valid_matricula_format
        for u in all_users:
            prefix = u.user_principal_name.split("@")[0]
            if is_valid_matricula_format(prefix):
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
        else:
            execute_bulk_password_reset(
                students_data=students_data,
                graph=graph,
                domain=config.domain,
                secrets_dir=config.secrets_dir,
                reports_dir=config.reports_dir,
                auto_confirm=False
            )
    elif opt == "3":
        file_path = input("\n👉 Ruta al archivo Excel o .txt con las matrículas: ").strip()
        if file_path and os.path.exists(file_path):
            if file_path.endswith(".xlsx"):
                mats = extract_matriculas_from_excel(file_path)
            else:
                with open(file_path, "r", encoding="utf-8") as f:
                    mats = [line.strip() for line in f if line.strip() and not line.startswith("#")]

            print(f"📑 {len(mats)} matrículas encontradas en el archivo.")
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
            if students_data:
                execute_bulk_password_reset(
                    students_data=students_data,
                    graph=graph,
                    domain=config.domain,
                    secrets_dir=config.secrets_dir,
                    reports_dir=config.reports_dir,
                    auto_confirm=False
                )
            else:
                print("ℹ️ No se encontraron cuentas activas en Entra ID para esas matrículas.")
        else:
            print("❌ Archivo no encontrado.")
    else:
        print("⛔ Opción no válida.")
    pause()


def menu_export_pdf(config: AppConfig):
    clear_screen()
    print("=" * 80)
    print("📄 [6] GENERADOR DE FICHAS DE ACCESO EN PDF (CON CÓDIGO QR)")
    print("=" * 80)
    print("📌 ¿Qué hace esta función?")
    print("   • Toma el archivo de contraseñas de los alumnos y genera un PDF de alta calidad.")
    print("   • Incluye los datos del alumno, código QR directo al portal y guía paso a paso.")
    print("   • Opciones de formato:")
    print("     [1] 4 Tarjetas por hoja (Recortables - ideal para repartir en clase).")
    print("     [2] 1 Ficha por hoja (Formato completo para expedientes o tutores).")
    print("-" * 80)

    print("👉 Selecciona el formato de impresión:")
    print("   [1] 4 Tarjetas recortables por hoja (Ahorro de papel)")
    print("   [2] 1 Ficha por hoja (Formato expediente formal)")
    opt = input("   Opción (1 o 2, por defecto 1): ").strip()
    mode = "full" if opt == "2" else "cards"

    from src.pdf_generator import generate_pdf_from_credentials_csv

    # Buscar archivo CSV más reciente
    csv_file = None
    if os.path.exists(config.secrets_dir):
        cred_files = sorted([
            os.path.join(config.secrets_dir, f)
            for f in os.listdir(config.secrets_dir)
            if f.startswith("credenciales_alumnos_") and f.endswith(".csv")
        ])
        if cred_files:
            csv_file = cred_files[-1]

    if not csv_file:
        print("❌ No se encontró ningún archivo de credenciales en 'secrets/'.")
    else:
        timestamp_str = os.path.splitext(os.path.basename(csv_file))[0]
        output_pdf = os.path.join("reports", f"fichas_acceso_{timestamp_str}_{mode}.pdf")
        print(f"\nGenerando PDF desde: {csv_file}...")
        gen_path = generate_pdf_from_credentials_csv(csv_file, output_pdf, layout_mode=mode)
        print(f"\n🎉 ¡PDF generado con éxito!")
        print(f"📍 Archivo listo para imprimir: \033[1;32m{gen_path}\033[0m")
    pause()


def menu_delete(config: AppConfig):
    clear_screen()
    print("=" * 80)
    print("❌ [7] BAJA Y ELIMINACIÓN SEGURA DE ALUMNOS")
    print("=" * 80)
    print("📌 ¿Qué hace esta función?")
    print("   • Elimina alumnos que se hayan graduado o retirado de la institución.")
    print("   • Libera automáticamente sus licencias Office 365 A1 para reutilizarlas.")
    print("   • Envía las cuentas a la Papelera de Reciclaje (recuperables por 30 días con 'restore').")
    print("   • SALVAGUARDA: Bloquea terminantemente cuentas de docentes o administradores.")
    print("-" * 80)

    print("👉 Selecciona el método de baja:")
    print("   [1] Por Matrícula Individual")
    print("   [2] Por Lote desde Archivo Excel (Ej. graduados o no reinscritos)")
    print("   [3] Por Lista desde Archivo de Texto (.txt)")
    opt = input("   Opción (1-3): ").strip()

    identifiers = []
    if opt == "1":
        mat = input("\n👉 Ingresa la Matrícula del alumno a dar de baja: ").strip()
        if mat:
            identifiers.append(mat)
    elif opt == "2":
        excel_path = input("\n👉 Ruta al archivo Excel con las matrículas: ").strip()
        if excel_path and os.path.exists(excel_path):
            from src.excel_parser import extract_matriculas_from_excel
            identifiers = extract_matriculas_from_excel(excel_path)
            print(f"📑 {len(identifiers)} matrículas extraídas desde el Excel.")
        else:
            print("❌ Archivo no encontrado.")
            pause()
            return
    elif opt == "3":
        txt_path = input("\n👉 Ruta al archivo .txt con matrículas (una por línea): ").strip()
        if txt_path and os.path.exists(txt_path):
            with open(txt_path, "r", encoding="utf-8") as f:
                identifiers = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            print(f"📑 {len(identifiers)} matrículas leídas desde el archivo.")
        else:
            print("❌ Archivo no encontrado.")
            pause()
            return

    if identifiers:
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
            backups_dir=config.backups_dir
        )
    else:
        print("⛔ No se especificó ninguna matrícula.")
    pause()


def menu_restore(config: AppConfig):
    clear_screen()
    print("=" * 80)
    print("🔄 [8] RESTAURAR ALUMNO DESDE LA PAPELERA DE RECICLAJE")
    print("=" * 80)
    print("📌 ¿Qué hace esta función?")
    print("   • Recupera una cuenta de alumno eliminada en los últimos 30 días.")
    print("   • Reactiva todos sus correos de Outlook, archivos de OneDrive y tareas de Teams.")
    print("   • Reasigna su licencia Office 365 A1 automáticamente.")
    print("-" * 80)

    matricula = input("👉 Ingresa la Matrícula del alumno a restaurar: ").strip()
    if matricula:
        from src.restore_engine import execute_student_restoration
        write_scopes = ["User.ReadWrite.All", "Domain.Read.All", "LicenseAssignment.Read.All"]
        graph = GraphClient(config.tenant_id, config.client_id, write_scopes)
        graph.authenticate_device_code()

        execute_student_restoration(
            identifier=matricula,
            graph=graph,
            domain=config.domain,
            excel_path=config.excel_path,
            sheet_name=config.sheet_name
        )
    else:
        print("⛔ No se ingresó ninguna matrícula.")
    pause()


def menu_status(config: AppConfig):
    clear_screen()
    print("=" * 80)
    print("📊 [9] MONITOR EJECUTIVO DE SALUD DEL TENANT Y LICENCIAS A1")
    print("=" * 80)
    print("📌 ¿Qué hace esta función?")
    print("   • Muestra un tablero en tiempo real con las licencias A1 disponibles.")
    print("   • Muestra el conteo de alumnos activos, docentes y cuentas en papelera.")
    print("   • Verifica el estado del dominio oficial ijova.com.")
    print("-" * 80)

    from src.status_engine import execute_tenant_status_check
    read_scopes = ["User.Read.All", "Domain.Read.All", "LicenseAssignment.Read.All"]
    graph = GraphClient(config.tenant_id, config.client_id, read_scopes)
    graph.authenticate_device_code()

    execute_tenant_status_check(
        graph=graph,
        domain=config.domain,
        backups_dir=config.backups_dir
    )
    pause()


def menu_backup(config: AppConfig):
    clear_screen()
    print("=" * 80)
    print("📸 [10] GENERAR SNAPSHOT DE AUDITORÍA (RESPALDO DEL TENANT)")
    print("=" * 80)
    print("📌 ¿Qué hace esta función?")
    print("   • Extrae una copia íntegra con timestamp de todos los usuarios de Entra ID.")
    print("   • La guarda en 'backups/' en formatos JSON y CSV protegidos (0700).")
    print("   • Aplica purga automática de respaldos con más de 30 días.")
    print("-" * 80)

    from src.auditor import create_audit_snapshot
    read_scopes = ["User.Read.All", "Domain.Read.All", "LicenseAssignment.Read.All"]
    graph = GraphClient(config.tenant_id, config.client_id, read_scopes)
    graph.authenticate_device_code()
    domain_status = graph.verify_domain(config.domain)
    entra_users = graph.get_all_users()

    snap_file = create_audit_snapshot(
        users=entra_users,
        domain_status=domain_status,
        tenant_id=config.tenant_id,
        output_dir=config.backups_dir
    )
    print(f"\n✅ Snapshot guardado en: {snap_file}")
    pause()


def menu_logout(config: AppConfig):
    clear_screen()
    print("=" * 80)
    print("🔒 [11] CERRAR SESIÓN DE ADMINISTRADOR")
    print("=" * 80)
    print("📌 Esta acción eliminará el archivo de sesión guardado en 'secrets/token_cache.bin'.")
    print("   La próxima vez que realices una operación en la nube, el sistema solicitará")
    print("   nuevamente la autenticación en el navegador.")
    print("-" * 80)
    confirm = input("¿Deseas cerrar la sesión administrativa? (s/n): ").strip().lower()
    if confirm in ["s", "si", "y", "yes"]:
        cache_file = os.path.join(config.secrets_dir, "token_cache.bin")
        if os.path.exists(cache_file):
            try:
                os.remove(cache_file)
                print("✅ Sesión cerrada y archivo de caché eliminado correctamente.")
            except Exception as e:
                print(f"❌ Error al eliminar caché de sesión: {e}")
        else:
            print("ℹ️ No hay ninguna sesión activa guardada en caché.")

        try:
            from src.audit_logger import log_audit_event
            log_audit_event(
                action="LOGOUT",
                target="Session",
                admin="Admin",
                status="SUCCESS",
                details="Caché de tokens eliminado"
            )
        except Exception:
            pass
    pause()


def menu_photos(config: AppConfig):
    clear_screen()
    print("=" * 80)
    print("🖼️ [12] AUDITORÍA DE FOTOS DE PERFIL (DESCARGA + GALERÍA WEB INTERACTIVA)")
    print("=" * 80)
    print("📌 ¿Qué hace esta función?")
    print("   • Descarga las fotos de perfil de todos los alumnos de Microsoft 365.")
    print("   • Guarda las imágenes en 'reports/fotos_perfil/' identificadas por matrícula.")
    print("   • Genera una Galería Web Visual interactiva ('reports/galeria_fotos_alumnos.html')")
    print("     para que puedas revisar de inmediato si las fotos son apropiadas o no.")
    print("   • Te permite marcar fotos inapropiadas y exportar la lista a CSV.")
    print("   • Genera un informe detallado en Excel ('reports/auditoria_fotos_perfil.xlsx').")
    print("-" * 80)

    confirm = input("¿Deseas iniciar la auditoría y descarga de fotos? (s/n): ").strip().lower()
    if confirm in ["s", "si", "y", "yes", ""]:
        graph = GraphClient(config.tenant_id, config.client_id, config.graph_scopes)
        graph.authenticate_device_code()

        from src.photo_auditor import audit_profile_photos
        records, stats, gallery_path, excel_path = audit_profile_photos(
            graph=graph,
            config=config,
            max_workers=8
        )

        print("\n" + "=" * 80)
        print("🎉 AUDITORÍA DE FOTOS COMPLETADA CON ÉXITO")
        print("=" * 80)
        print(f"👉 Para revisar visualmente las fotos de los alumnos, abre en tu navegador:")
        print(f"   \033[1;36m{gallery_path}\033[0m")
        print(f"👉 Para consultar el reporte de auditoría en Excel:")
        print(f"   \033[1;32m{excel_path}\033[0m\n")
    pause()


def menu_teams(config: AppConfig):
    """Módulo interactivo de auditoría y gestión de equipos y clases en Teams."""
    clear_screen()
    print("=" * 80)
    print("👥 [T] AUDITORÍA Y ADMINISTRACIÓN DE MICROSOFT TEAMS (CLASES ESCOLARES)")
    print("=" * 80)
    print("📌 Funciones disponibles:")
    print("   [1] 🔍 Auditoría en Tiempo Real de Equipos y Clases (Consola)")
    print("   [2] 📊 Generar y Descargar Libro Excel de Auditoría Oficial (.xlsx)")
    print("   [3] ✏️ Renombrar Equipo o Clase en Microsoft Teams")
    print("   [4] 🎓 Crear Nueva Clase Educativa (Matriculación Automática por Nivel/Grado)")
    print("   [5] 📋 Auditoría de Tareas Escolares y Cumplimiento Docente (Consola y Excel)")
    print("   [0] 🔙 Volver al Menú Principal")
    print("-" * 80)

    sub_choice = input("👉 Selecciona una sub-opción (1-5 o 0): ").strip()
    if sub_choice == "0" or not sub_choice:
        return

    graph = GraphClient(config.tenant_id, config.client_id, config.graph_scopes, client_secret=config.client_secret)
    graph.authenticate_device_code()

    from src.teams_engine import (
        audit_all_teams,
        export_teams_audit_excel,
        create_class_assisted,
    )
    from export_students_m365 import build_school_db
    from datetime import datetime

    if sub_choice == "1":
        print("\n🔍 Auditando los equipos en Microsoft Teams en tiempo real...")
        data = audit_all_teams(graph)
        s = data["summary"]
        print("\n" + "=" * 80)
        print("📊 RESUMEN EJECUTIVO DE TEAMS:")
        print("=" * 80)
        print(f"  • Total de Equipos:               {s['total_teams']}")
        print(f"  • Clases Activas Ciclo 26-27:     {s['cycle_2026_2027']}")
        print(f"  • Clases de Ciclos Anteriores:    {s['past_cycles']}")
        print(f"  • Clases Educativas:              {s['class_teams']}")
        print(f"  • Equipos de Docentes / Staff:    {s['staff_teams']}")
        print(f"  • Equipos Huérfanos (0 Dueños):   {s['orphan_teams']}")
        print(f"  • Creados por Alumnos:            {s['student_owned_teams']}")
        print(f"  • Equipos Vacíos (0 Miembros):    {s['empty_teams']}")
        print("=" * 80)

    elif sub_choice == "2":
        print("\n📊 Generando libro de auditoría de Teams...")
        data = audit_all_teams(graph)
        out_file = os.path.join(
            config.reports_dir,
            f"Auditoria_Teams_Clases_IJOVA_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )
        export_teams_audit_excel(data, out_file)
        print(f"✅ Libro Excel exportado exitosamente:")
        print(f"   \033[1;32m{out_file}\033[0m")

    elif sub_choice == "3":
        team_id = input("👉 Introduce el ID del equipo en Teams: ").strip()
        new_name = input("👉 Introduce el nuevo nombre institucional: ").strip()
        new_desc = input("👉 Nueva descripción (opcional): ").strip()
        if team_id and new_name:
            print(f"\n🔄 Renombrando equipo en Microsoft Teams...")
            graph.update_team_info(team_id, new_name, new_desc or None)
            print(f"✅ Equipo renombrado a '{new_name}' con éxito.")

    elif sub_choice == "4":
        print("\n🎓 ASISTENTE DE CREACIÓN DE CLASES ESCOLARES")
        print("-" * 80)
        subject = input("👉 Nombre de la materia (ej. Lengua y Comunicación): ").strip()
        print("\nNiveles disponibles: Preparatoria, Secundaria, Primaria, Preescolar")
        nivel = input("👉 Nivel educativo: ").strip()
        grado = input("👉 Grado escolar o semestre (ej. 3er Semestre, 1° Secundaria): ").strip()

        print("\n🔍 Consultando catálogo de docentes en Microsoft 365...")
        teachers = graph.get_all_teachers()
        print(f"Docentes disponibles ({len(teachers)} encontrados):")
        for i, t in enumerate(teachers[:15], 1):
            print(f"  [{i}] {t['displayName']} ({t['userPrincipalName']})")
        if len(teachers) > 15:
            print(f"  ... y {len(teachers) - 15} más.")

        teacher_input = input("\n👉 Correo o número del docente responsable: ").strip()
        teacher_id = None
        if teacher_input.isdigit() and 1 <= int(teacher_input) <= len(teachers):
            teacher_id = teachers[int(teacher_input) - 1]["id"]
        elif "@" in teacher_input:
            u = graph.get_user_by_upn(teacher_input)
            if u:
                teacher_id = u["id"]
        else:
            teacher_id = teacher_input

        if not teacher_id:
            print("❌ No se pudo identificar al docente.")
            pause()
            return

        desc = input("👉 Descripción del equipo (opcional): ").strip()

        print("\n🚀 Creando clase y matriculando alumnos automáticamente...")
        school_db = build_school_db()
        res = create_class_assisted(
            graph=graph,
            subject_name=subject,
            nivel=nivel,
            grado=grado,
            teacher_user_id=teacher_id,
            school_db=school_db,
            custom_description=desc or None
        )
        print("=" * 80)
        print("🎉 CLASE CREADA EXITOSAMENTE EN MICROSOFT TEAMS")
        print("=" * 80)
        print(f"  • Nombre Oficial:    {res['team_name']}")
        print(f"  • ID de Equipo:      {res['team_id']}")
        print(f"  • Alumnos Inscritos: {res['students_enrolled_count']}")
        print("=" * 80)

    elif sub_choice == "5":
        cycle_in = input("👉 Ciclo escolar a auditar (Enter para '2026-2027'): ").strip()
        target_cycle = cycle_in or "2026-2027"
        print(f"\n📋 Auditando tareas y actividades escolares para el ciclo {target_cycle}...")
        from src.teams_engine import audit_all_assignments, export_assignments_report_excel
        data = audit_all_assignments(graph, target_cycle=target_cycle)
        s = data["summary"]
        print("\n" + "=" * 80)
        print(f"📊 RESUMEN AUDITORÍA DE TAREAS Y CUMPLIMIENTO DOCENTE (CICLO {target_cycle})")
        print("=" * 80)
        print(f"  • Total Clases Auditadas:          {s['total_classes']}")
        print(f"  • Clases con Tareas Publicadas:    {s['classes_with_assignments']}")
        print(f"  • Clases Inactivas (0 Tareas):     {s['classes_without_assignments']}")
        print(f"  • Tareas Asignadas Totales:        {s['total_assignments']}")
        print(f"  • Entregas Totales Registradas:    {s['total_submissions']}")
        print(f"  • Entregadas en Tiempo y Forma:    {s['total_turned_in']}")
        print(f"  • Tasa Global de Entrega:          {s['overall_turn_in_rate']}%")
        print(f"  • Docentes Activos (>= 4 tareas):  {s['docentes_activos']}")
        print(f"  • Docentes Moderados (1-3 tareas): {s['docentes_moderados']}")
        print(f"  • Docentes Inactivos (0 tareas):   {s['docentes_inactivos']}")
        print("=" * 80)

        out_file = os.path.join(
            config.reports_dir,
            f"Reporte_Tareas_Docentes_{target_cycle}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )
        export_assignments_report_excel(data, out_file)
        print(f"✅ Reporte ejecutivo de 3 hojas guardado en:")
        print(f"   \033[1;32m{out_file}\033[0m")

    pause()


def menu_gui(config: AppConfig):
    """Inicia la interfaz gráfica web local desde el menú."""
    clear_screen()
    print("=" * 80)
    print("🖥️ [G] INTERFAZ GRÁFICA WEB LOCAL (DASHBOARD)")
    print("=" * 80)
    print("📌 ¿Qué hace esta función?")
    print("   • Inicia el servidor web local en http://127.0.0.1:5000.")
    print("   • Abre automáticamente tu navegador predeterminado.")
    print("   • Te permite buscar alumnos interactivamente por nombre o matrícula.")
    print("   • Despliega su fotografía, datos de Entra ID y grupo escolar.")
    print("   • Incluye ventana de confirmación previa obligatoria antes de resetear.")
    print("   • Genera y permite imprimir directamente las fichas con código QR.")
    print("-" * 80)

    confirm = input("¿Deseas iniciar la Interfaz Gráfica en tu navegador? (s/n, ENTER=s): ").strip().lower()
    if confirm in ["s", "si", "y", "yes", ""]:
        from src.gui.app import start_gui
        start_gui(config_path="config.json", host="127.0.0.1", port=5000, open_browser=True)
    pause()


def run_interactive_menu(config_path: str = "config.json"):
    """Bucle principal del menú interactivo por terminal."""
    config = load_config(config_path)

    while True:
        clear_screen()
        print_banner(config)
        print("📂 GESTIÓN DE CICLO ESCOLAR Y SINCRONIZACIÓN:")
        print("  \033[1;36m[1]\033[0m 🔍 Validar Archivo Excel Local (Offline / Sin internet)")
        print("  \033[1;36m[2]\033[0m 🌐 Simulación DRY-RUN contra Microsoft 365 (Sin escrituras)")
        print("  \033[1;36m[3]\033[0m 🚀 Aprovisionamiento Masivo (Crear Alumnos Nuevos con Licencia A1)\n")

        print("👤 OPERACIÓN DIARIA Y ATENCIÓN A ALUMNOS:")
        print("  \033[1;32m[4]\033[0m 🎓 Alta Rápida de Alumno Extemporáneo (Ficha de Bienvenida + Excel)")
        print("  \033[1;32m[5]\033[0m 🔑 Restablecer Contraseña Olvidada de Alumno (Por matrícula con verificación)")
        print("  \033[1;32m[6]\033[0m 📄 Generar Fichas de Acceso en PDF con Código QR (Imprimibles)\n")

        print("👥 EQUIPOS Y CLASES DE MICROSOFT TEAMS:")
        print("  \033[1;34m[T]\033[0m 👥 Auditoría y Gestión de Equipos / Clases Teams (Creación, Renombrado, Excel)\n")

        print("🗑️ BAJAS, REINICIO DE CICLO Y RECUPERACIÓN:")
        print("  \033[1;31m[7]\033[0m ❌ Dar de Baja Alumno(s) (Individual, Lote o Archivo Excel)")
        print("  \033[1;33m[8]\033[0m 🔄 Restaurar Alumno desde la Papelera de Reciclaje (< 30 días)\n")

        print("📊 AUDITORÍA Y ESTADO DEL TENANT:")
        print("  \033[1;35m[9]\033[0m 📈 Monitor Ejecutivo de Salud del Tenant y Licencias A1")
        print("  \033[1;35m[10]\033[0m 📸 Descargar Snapshot de Auditoría (Respaldo en backups/)")
        print("  \033[1;33m[11]\033[0m 🔒 Cerrar Sesión Administrativa (Borrar credenciales guardadas)")
        print("  \033[1;32m[12]\033[0m 🖼️ Auditoría de Fotos de Perfil (Descarga + Galería Web Interactiva)\n")

        print("🖥️ PANEL DE CONTROL VISUAL:")
        print("  \033[1;36m[G]\033[0m 🌐 Iniciar Interfaz Gráfica Web (Buscador, Fotos, Fichas y Módulo Teams)\n")

        print("  \033[1m[0]\033[0m 🚪 Salir del Sistema\n")
        print("=" * 80)

        choice = input("👉 Selecciona una opción (0-12, T o G): ").strip()

        if choice == "1":
            menu_validate(config)
        elif choice == "2":
            menu_dry_run(config)
        elif choice == "3":
            menu_apply(config)
        elif choice == "4":
            menu_enroll(config)
        elif choice == "5":
            menu_reset(config)
        elif choice == "6":
            menu_export_pdf(config)
        elif choice.upper() in ["T", "TEAMS"]:
            menu_teams(config)
        elif choice == "7":
            menu_delete(config)
        elif choice == "8":
            menu_restore(config)
        elif choice == "9":
            menu_status(config)
        elif choice == "10":
            menu_backup(config)
        elif choice == "11":
            menu_logout(config)
        elif choice == "12":
            menu_photos(config)
        elif choice.upper() in ["G", "GUI", "13"]:
            menu_gui(config)
        elif choice in ["0", "q", "exit", "salir"]:
            clear_screen()
            print("\n👋 ¡Hasta luego! Sistema cerrado de forma segura.\n")
            break
        else:
            print("\n❌ Opción no válida. Por favor introduce un número del 0 al 12, 'T' o 'G'.")
            pause()

