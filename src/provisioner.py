"""
Motor de aprovisionamiento masivo y seguro de alumnos hacia Microsoft 365 / Entra ID (Fase 2).
Garantiza re-verificación anti-drift, asignación de licencias A1 y exportación de contraseñas temporales en secrets/ (0600).
"""
import os
import csv
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from src.models import StudentRecord, ClassificationEnum
from src.graph_client import GraphClient, GraphClientError
from src.password_generator import generate_secure_password


def execute_provisioning(
    new_students: List[StudentRecord],
    graph: GraphClient,
    secrets_dir: str = "secrets",
    reports_dir: str = "reports"
) -> Dict[str, Any]:
    """
    Ejecuta la creación segura de alumnos clasificados como NUEVO.
    - Cero modificación sobre existentes.
    - Anti-drift por cada usuario.
    - Asignación de licencia Office 365 A1 for Students.
    - Generación y almacenamiento protegido de contraseñas temporales.
    """
    os.makedirs(secrets_dir, exist_ok=True)
    os.makedirs(reports_dir, exist_ok=True)
    try:
        os.chmod(secrets_dir, 0o700)
    except Exception:
        pass

    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
    
    # 1. Identificar SKU de Licencia A1 para Estudiantes
    print("\n🔍 Consultando licencias disponibles en Microsoft 365...")
    student_sku = graph.find_student_sku()
    sku_id = None
    if student_sku:
        sku_id = student_sku["skuId"]
        print(f"✅ SKU de Licencia detectado: \033[1;32m{student_sku['skuPartNumber']}\033[0m (Unidades disponibles: {student_sku['available']})")
    else:
        print("⚠️ No se detectó un SKU de estudiantes con unidades disponibles. Las cuentas se crearán sin licencia directa.")

    print(f"\n🚀 Iniciando aprovisionamiento seguro de \033[1;34m{len(new_students)}\033[0m alumnos nuevos...\n")

    created_records: List[Dict[str, Any]] = []
    skipped_records: List[Dict[str, Any]] = []
    failed_records: List[Dict[str, Any]] = []
    credentials_list: List[Dict[str, Any]] = []

    for idx, s in enumerate(new_students, 1):
        upn = s.upn_normalized
        print(f"[{idx}/{len(new_students)}] Procesando: \033[1m{s.display_name}\033[0m ({upn})...")

        # Salvaguarda 1: Anti-drift en tiempo real
        existing_user = graph.get_user_by_upn(upn)
        if existing_user:
            print(f"   ℹ️ OMITIDO: El usuario {upn} ya existe en Entra ID (ID: {existing_user.get('id')}).")
            skipped_records.append({
                "matricula": s.matricula,
                "upn": upn,
                "display_name": s.display_name,
                "status": "OMITIDO_YA_EXISTE",
                "id": existing_user.get("id")
            })
            continue

        # Salvaguarda 2: Contraseña temporal segura e individual
        temp_password = generate_secure_password(length=12)

        # Construir payload conforme al estándar de Entra ID
        payload = {
            "accountEnabled": True,
            "displayName": s.display_name,
            "givenName": s.given_name,
            "surname": s.surname,
            "mailNickname": s.mail_nickname,
            "userPrincipalName": upn,
            "usageLocation": "MX",
            "passwordProfile": {
                "forceChangePasswordNextSignIn": True,
                "password": temp_password
            }
        }

        try:
            # Crear usuario en Microsoft Entra ID
            created_user = graph.create_user(payload)
            user_id = created_user.get("id")
            print(f"   ✅ Cuenta creada con éxito (ID: {user_id}).")

            # Asignar licencia Office 365 A1
            license_assigned = False
            if sku_id and user_id:
                # Small pause to allow directory replication
                time.sleep(0.5)
                license_assigned = graph.assign_license(user_id, sku_id)
                if license_assigned:
                    print("   🏷️ Licencia Office 365 A1 asignada correctamente.")
                else:
                    print("   ⚠️ No se pudo asignar la licencia automáticamente.")

            # Guardar en lista de credenciales protegidas
            credentials_list.append({
                "matricula": s.matricula,
                "upn": upn,
                "nombre_completo": s.display_name,
                "nivel": s.nivel,
                "grado_semestre": s.grado_semestre,
                "password_temporal": temp_password,
                "licencia_asignada": "SÍ" if license_assigned else "NO",
                "fecha_creacion_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            })

            created_records.append({
                "matricula": s.matricula,
                "upn": upn,
                "display_name": s.display_name,
                "status": "CREADO_EXITOSAMENTE",
                "id": user_id,
                "licencia_a1": "ASIGNADA" if license_assigned else "PENDIENTE"
            })

        except Exception as e:
            print(f"   ❌ ERROR al crear usuario {upn}: {e}")
            failed_records.append({
                "matricula": s.matricula,
                "upn": upn,
                "display_name": s.display_name,
                "error": str(e)
            })

    # 3. Exportar Credenciales a Archivo Protegido (0600)
    creds_file = os.path.join(secrets_dir, f"credenciales_alumnos_{timestamp_str}.csv")
    creds_fieldnames = [
        "matricula", "upn", "nombre_completo", "nivel", "grado_semestre",
        "password_temporal", "licencia_asignada", "fecha_creacion_utc"
    ]
    with open(creds_file, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=creds_fieldnames)
        writer.writeheader()
        for c in credentials_list:
            writer.writerow(c)
    try:
        os.chmod(creds_file, 0o600)
    except Exception:
        pass

    # 4. Exportar Reporte de Creación a reports/
    report_file = os.path.join(reports_dir, f"creacion_alumnos_{timestamp_str}.csv")
    with open(report_file, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["matricula", "upn", "display_name", "status", "id", "licencia_a1"])
        writer.writeheader()
        for r in created_records + skipped_records:
            writer.writerow(r)

    print("\n" + "=" * 80)
    print("🏁 RESUMEN DEL APROVISIONAMIENTO EN MICROSOFT 365:")
    print("=" * 80)
    print(f"✅ Cuentas creadas exitosamente: {len(created_records)}")
    print(f"ℹ️ Cuentas omitidas (ya existían): {len(skipped_records)}")
    print(f"❌ Cuentas con error: {len(failed_records)}")
    print(f"🔐 Archivo protegido de contraseñas iniciales (0600): {creds_file}")
    print(f"📊 Reporte de auditoría de creación: {report_file}")

    return {
        "created_count": len(created_records),
        "skipped_count": len(skipped_records),
        "failed_count": len(failed_records),
        "credentials_file": creds_file,
        "report_file": report_file
    }
