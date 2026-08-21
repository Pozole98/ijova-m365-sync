"""
Motor de baja y eliminación segura de alumnos en Microsoft 365 / Entra ID.
Implementa salvaguardas estrictas contra eliminación de personal/administradores y registro en bitácora.
"""
import os
import csv
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from src.graph_client import GraphClient, GraphClientError
from src.excel_parser import update_student_status_in_excel


def is_student_matricula(identifier: str) -> Tuple_Bool_Str:
    """
    Valida que el identificador corresponda estrictamente a una matrícula de alumno.
    Bloquea cualquier cuenta de administrador, docente o personal escolar.
    """
    clean_id = identifier.strip().lower()
    if clean_id.endswith("@ijova.com"):
        prefix = clean_id.split("@")[0]
    else:
        prefix = clean_id

    # Debe ser numérico
    if not prefix.isdigit():
        return False, f"El identificador '{identifier}' NO es una matrícula estudiantil numérica. Por seguridad se bloquea la eliminación de cuentas de personal/administradores."

    upn = f"{prefix}@ijova.com"
    return True, upn


# Type annotation helper
Tuple_Bool_Str = tuple[bool, str]


def execute_student_deletion(
    identifiers: List[str],
    graph: GraphClient,
    excel_path: str = "Listado de Alumnos Inscritos.xlsx",
    sheet_name: str = "Listado Global Matriculado",
    reports_dir: str = "reports",
    auto_confirm: bool = False
) -> Dict[str, Any]:
    """
    Elimina uno o varios alumnos de Microsoft 365 a partir de su matrícula.
    - Soft-delete en Entra ID (papelera con 30 días de retención).
    - Libera automáticamente la licencia A1.
    - Actualiza el estatus en el Excel a 'Baja'.
    - Registra en reports/bajas_alumnos_*.csv.
    """
    os.makedirs(reports_dir, exist_ok=True)
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
    
    deleted_list: List[Dict[str, Any]] = []
    skipped_list: List[Dict[str, Any]] = []
    failed_list: List[Dict[str, Any]] = []

    print("\n" + "=" * 80)
    print("🗑️ PROCESO DE BAJA / ELIMINACIÓN DE ALUMNOS EN MICROSOFT 365")
    print("=" * 80)

    for ident in identifiers:
        is_valid, result = is_student_matricula(ident)
        if not is_valid:
            print(f"\n⛔ BLOQUEO DE SEGURIDAD: {result}")
            skipped_list.append({"identificador": ident, "motivo": result})
            continue

        upn = result
        matricula = upn.split("@")[0]
        print(f"\n🔍 Buscando alumno con matrícula \033[1;34m{matricula}\033[0m ({upn})...")

        # 1. Consultar usuario en Microsoft Entra ID
        try:
            user = graph.get_user_by_upn(upn)
        except Exception as e:
            print(f"❌ Error al consultar usuario {upn}: {e}")
            failed_list.append({"matricula": matricula, "upn": upn, "error": str(e)})
            continue

        if not user:
            print(f"ℹ️ El usuario {upn} no existe en Microsoft Entra ID (o ya fue eliminado previamente).")
            # Actualizar Excel por consistencia si existe en la hoja
            update_student_status_in_excel(excel_path, sheet_name, matricula, "Baja")
            skipped_list.append({"matricula": matricula, "upn": upn, "motivo": "NO_EXISTE_EN_ENTRA"})
            continue

        user_id = user.get("id")
        display_name = user.get("displayName", "Sin nombre")

        print(f"   👤 Alumno encontrado: \033[1m{display_name}\033[0m")
        print(f"   🆔 Entra Object ID:   {user_id}")
        print(f"   📧 UPN Institucional: {upn}")

        # 2. Confirmación Interactiva
        if not auto_confirm:
            confirm = input(f"   ¿Confirmas eliminar a '{display_name}' de Microsoft 365? (s/n): ")
            if confirm.strip().lower() not in ["s", "si", "y", "yes"]:
                print("   ⛔ Eliminación omitida por el usuario.")
                skipped_list.append({"matricula": matricula, "upn": upn, "motivo": "CANCELADO_POR_USUARIO"})
                continue

        # 3. Ejecutar Eliminación en Microsoft Graph (Soft-Delete)
        try:
            success = graph.delete_user(user_id)
            if success:
                print(f"   ✅ Alumno \033[1;32m{display_name}\033[0m eliminado exitosamente de Microsoft 365 (Licencia A1 liberada).")
                
                # 4. Actualizar estatus en Excel a 'Baja'
                excel_updated = update_student_status_in_excel(excel_path, sheet_name, matricula, "Baja")
                if excel_updated:
                    print("   📑 Estatus del alumno actualizado a 'Baja' en el Excel.")

                deleted_list.append({
                    "matricula": matricula,
                    "upn": upn,
                    "display_name": display_name,
                    "id": user_id,
                    "deleted_by": graph.admin_upn or "admin",
                    "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                })
            else:
                print(f"   ❌ No se pudo eliminar la cuenta {upn}.")
                failed_list.append({"matricula": matricula, "upn": upn, "error": "DELETE_FAILED"})
        except Exception as e:
            print(f"   ❌ Error al eliminar usuario {upn}: {e}")
            failed_list.append({"matricula": matricula, "upn": upn, "error": str(e)})

    # 5. Generar bitácora de bajas en reports/
    if deleted_list:
        bajas_file = os.path.join(reports_dir, f"bajas_alumnos_{timestamp_str}.csv")
        with open(bajas_file, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["matricula", "upn", "display_name", "id", "deleted_by", "timestamp_utc"])
            writer.writeheader()
            for d in deleted_list:
                writer.writerow(d)
        print(f"\n📊 Bitácora de bajas guardada en: {bajas_file}")

    print("\n" + "=" * 80)
    print("🏁 RESUMEN DEL PROCESO DE BAJAS:")
    print("=" * 80)
    print(f"✅ Alumnos eliminados: {len(deleted_list)}")
    print(f"ℹ️ Alumnos omitidos:   {len(skipped_list)}")
    print(f"❌ Errores:            {len(failed_list)}")

    return {
        "deleted_count": len(deleted_list),
        "skipped_count": len(skipped_list),
        "failed_count": len(failed_list)
    }
