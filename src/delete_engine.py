"""
Motor de baja y eliminación masiva segura de alumnos en Microsoft 365 / Entra ID.
Implementa salvaguardas estrictas contra eliminación de personal/administradores,
previsualización enriquecida en tiempo real y registro en bitácora de auditoría.
"""
import os
import csv
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from tabulate import tabulate

from src.graph_client import GraphClient, GraphClientError
from src.excel_parser import update_student_status_in_excel
from src.auditor import create_audit_snapshot


def is_student_matricula(identifier: str) -> Tuple[bool, str]:
    """
    Valida que el identificador corresponda estrictamente a una matrícula de alumno.
    Bloquea cualquier cuenta de administrador, docente o personal escolar.
    """
    clean_id = identifier.strip().lower()
    if clean_id.endswith("@ijova.com"):
        prefix = clean_id.split("@")[0]
    else:
        prefix = clean_id

    # 1. Debe ser numérico (bloqueo anti-admin / docentes / cuentas de personal)
    if not prefix.isdigit():
        return False, f"El identificador '{identifier}' NO es una matrícula estudiantil numérica. Por seguridad se bloquea la eliminación de cuentas de personal/administradores."

    # 2. Debe cumplir con el formato institucional de 6 dígitos (ej. 25xxxx, 26xxxx)
    from src.validator import is_valid_matricula_format
    if not is_valid_matricula_format(prefix):
        return False, f"El identificador '{identifier}' NO cumple con el formato de matrícula escolar (debe constar exactamente de 6 dígitos numéricos, ej. 25xxxx o 26xxxx). Por seguridad se bloquea la operación."

    upn = f"{prefix}@ijova.com"
    return True, upn


def execute_student_deletion(
    identifiers: List[str],
    graph: GraphClient,
    excel_path: str = "Listado de Alumnos Inscritos.xlsx",
    sheet_name: str = "Listado Global Matriculado",
    reports_dir: str = "reports",
    backups_dir: str = "backups",
    auto_confirm: bool = False
) -> Dict[str, Any]:
    """
    Elimina uno o múltiples alumnos de Microsoft 365 a partir de sus matrículas.
    Para lotes (>1 alumno), muestra una tabla de previsualización ejecutiva antes de proceder.
    """
    os.makedirs(reports_dir, exist_ok=True)
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")

    print("\n" + "=" * 80)
    print("🗑️ PROCESO DE BAJA / ELIMINACIÓN DE ALUMNOS EN MICROSOFT 365")
    print("=" * 80)

    # 1. Enriquecer matrículas consultando Microsoft Graph en tiempo real
    print(f"\n🔍 Verificando {len(identifiers)} matrículas en Microsoft Entra ID...")
    
    valid_candidates: List[Dict[str, Any]] = []
    blocked_candidates: List[Dict[str, Any]] = []
    not_found_candidates: List[Dict[str, Any]] = []

    for ident in identifiers:
        is_valid, result = is_student_matricula(ident)
        if not is_valid:
            blocked_candidates.append({"identificador": ident, "motivo": result})
            continue

        upn = result
        matricula = upn.split("@")[0]

        try:
            user = graph.get_user_by_upn(upn)
            if user:
                valid_candidates.append({
                    "matricula": matricula,
                    "upn": upn,
                    "id": user.get("id"),
                    "display_name": user.get("displayName", "Sin nombre"),
                    "account_enabled": user.get("accountEnabled", True)
                })
            else:
                not_found_candidates.append({
                    "matricula": matricula,
                    "upn": upn,
                    "motivo": "No existe en Entra ID o ya fue eliminado"
                })
                # Actualizar Excel por consistencia si existe
                update_student_status_in_excel(excel_path, sheet_name, matricula, "Baja")
        except Exception as e:
            blocked_candidates.append({"identificador": ident, "motivo": str(e)})

    # 2. Mostrar alertas si hubo cuentas bloqueadas o no encontradas
    if blocked_candidates:
        print("\n⛔ CUENTAS BLOQUEADAS POR SEGURIDAD (NO ESTUDIANTILES O INVÁLIDAS):")
        for b in blocked_candidates:
            print(f"   • {b['identificador']}: {b['motivo']}")

    if not_found_candidates:
        print(f"\nℹ️ ALUMNOS NO ENCONTRADOS EN MICROSOFT 365 (Total: {len(not_found_candidates)}):")
        for nf in not_found_candidates[:5]:
            print(f"   • Matrícula {nf['matricula']} ({nf['upn']})")
        if len(not_found_candidates) > 5:
            print(f"   ... y {len(not_found_candidates) - 5} más.")

    if not valid_candidates:
        print("\n⚠️ No se encontraron alumnos activos válidos para eliminar. Operación finalizada.")
        return {"deleted_count": 0, "skipped_count": len(not_found_candidates) + len(blocked_candidates)}

    # 3. Mostrar Tabla de Previsualización Ejecutiva
    print("\n" + "=" * 80)
    print(f"📋 ALUMNOS CONFIRMADOS PARA ELIMINACIÓN (Total: {len(valid_candidates)})")
    print("=" * 80)

    table_data = []
    for idx, c in enumerate(valid_candidates, 1):
        status_text = "Activo" if c["account_enabled"] else "Deshabilitado"
        table_data.append([idx, c["matricula"], c["display_name"], c["upn"], status_text])

    print(tabulate(
        table_data[:20],
        headers=["#", "Matrícula", "Nombre Completo", "Correo Institucional", "Estado"],
        tablefmt="fancy_grid"
    ))
    if len(valid_candidates) > 20:
        print(f"   ... y {len(valid_candidates) - 20} alumnos más en el lote.")

    # 4. Confirmación de Seguridad
    if not auto_confirm:
        if len(valid_candidates) > 1:
            confirm = input(f"\n⚠️ ¿Confirmas eliminar a estos {len(valid_candidates)} alumnos y liberar sus licencias? (Escribe 'ELIMINAR' para confirmar): ")
            if confirm.strip().upper() != "ELIMINAR":
                print("⛔ Operación masiva cancelada por el usuario. No se borró ninguna cuenta.")
                return {"deleted_count": 0, "cancelled": True}
        else:
            confirm = input(f"\n¿Confirmas eliminar a '{valid_candidates[0]['display_name']}' de Microsoft 365? (s/n): ")
            if confirm.strip().lower() not in ["s", "si", "y", "yes"]:
                print("⛔ Eliminación cancelada por el usuario.")
                return {"deleted_count": 0, "cancelled": True}

    # 5. Snapshot Preventivo de Seguridad
    try:
        print(f"\n📸 Generando snapshot de seguridad en '{backups_dir}' antes de eliminar...")
        all_current_users = graph.get_all_users()
        domain_status = graph.verify_domain("ijova.com")
        create_audit_snapshot(
            users=all_current_users,
            domain_status=domain_status,
            tenant_id=graph.tenant_id,
            output_dir=backups_dir
        )
    except Exception as e:
        print(f"⚠️ Advertencia al crear snapshot: {e}")

    # 6. Ejecutar Eliminación Controlada
    print(f"\n🚀 Eliminando {len(valid_candidates)} cuentas de alumnos en Microsoft Graph...")
    deleted_list: List[Dict[str, Any]] = []
    failed_list: List[Dict[str, Any]] = []

    from src.historical_registry import record_student_baja

    for idx, c in enumerate(valid_candidates, 1):
        try:
            success = graph.delete_user(c["id"])
            if success:
                # Actualizar estatus en Excel
                update_student_status_in_excel(excel_path, sheet_name, c["matricula"], "Baja")
                
                # Archivar en Registro Histórico Permanente
                record_student_baja(
                    matricula=c["matricula"],
                    upn=c["upn"],
                    nombre_completo=c["display_name"],
                    entra_id=c["id"],
                    baja_por=graph.admin_upn or "admin"
                )

                deleted_list.append({
                    "matricula": c["matricula"],
                    "upn": c["upn"],
                    "display_name": c["display_name"],
                    "id": c["id"],
                    "deleted_by": graph.admin_upn or "admin",
                    "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                })
                print(f"   [{idx}/{len(valid_candidates)}] ✅ {c['display_name']} ({c['upn']}) eliminado y archivado en Histórico.")
            else:
                failed_list.append({"matricula": c["matricula"], "error": "DELETE_FAILED"})
        except Exception as e:
            failed_list.append({"matricula": c["matricula"], "error": str(e)})
            print(f"   [{idx}/{len(valid_candidates)}] ❌ Error al eliminar {c['upn']}: {e}")

    # 7. Generar Bitácora de Bajas en reports/
    if deleted_list:
        bajas_file = os.path.join(reports_dir, f"bajas_masivas_{timestamp_str}.csv")
        with open(bajas_file, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["matricula", "upn", "display_name", "id", "deleted_by", "timestamp_utc"])
            writer.writeheader()
            for d in deleted_list:
                writer.writerow(d)
        print(f"\n📊 Bitácora oficial de bajas guardada en: \033[1;32m{bajas_file}\033[0m")

    print("\n" + "=" * 80)
    print("🏁 RESUMEN FINAL DE BAJAS MASIVAS:")
    print("=" * 80)
    print(f"✅ Alumnos eliminados con éxito (Licencias A1 liberadas): {len(deleted_list)}")
    print(f"ℹ️ Alumnos no encontrados en Entra ID:                  {len(not_found_candidates)}")
    print(f"⛔ Cuentas bloqueadas por seguridad:                   {len(blocked_candidates)}")
    print(f"❌ Errores en eliminación:                              {len(failed_list)}")
    print("ℹ️ Nota: Las cuentas se encuentran en la Papelera de Reciclaje (recuperables por 30 días con 'restore').")

    return {
        "deleted_count": len(deleted_list),
        "failed_count": len(failed_list),
        "skipped_count": len(not_found_candidates) + len(blocked_candidates)
    }
