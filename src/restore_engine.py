"""
Motor de restauración rápida de alumnos desde la Papelera de Reciclaje de Microsoft Entra ID.
Permite recuperar cuentas eliminadas en los últimos 30 días, preservando OneDrive, buzón y tareas intactos.
"""
import os
from typing import Dict, Any, Optional
from src.graph_client import GraphClient, GraphClientError
from src.delete_engine import is_student_matricula
from src.excel_parser import update_student_status_in_excel


def execute_student_restoration(
    identifier: str,
    graph: GraphClient,
    domain: str = "ijova.com",
    excel_path: str = "Listado de Alumnos Inscritos.xlsx",
    sheet_name: str = "Listado Global Matriculado"
) -> Optional[Dict[str, Any]]:
    """
    Restaura una cuenta de alumno desde la papelera de reciclaje de Entra ID a partir de su matrícula.
    """
    # 1. Validar matrícula estudiantil
    is_valid, result = is_student_matricula(identifier)
    if not is_valid:
        print(f"\n⛔ BLOQUEO DE SEGURIDAD: {result}")
        return None

    upn = result
    matricula = upn.split("@")[0]

    print(f"\n🔍 Buscando matrícula \033[1;34m{matricula}\033[0m en la Papelera de Reciclaje de Microsoft Entra ID...")

    try:
        deleted_users = graph.get_deleted_users()
    except Exception as e:
        print(f"❌ Error al consultar la papelera de reciclaje: {e}")
        return None

    target_user = None
    for u in deleted_users:
        u_upn = (u.get("userPrincipalName") or "").strip().lower()
        u_nick = (u.get("mailNickname") or "").strip().lower()
        if u_upn == upn.lower() or u_nick == matricula.lower():
            target_user = u
            break

    if not target_user:
        print(f"ℹ️ No se encontró ninguna cuenta para {upn} en la Papelera de Reciclaje.")
        print("   Posibles causas:")
        print("   1. La cuenta ya está activa en Microsoft 365.")
        print("   2. Fue eliminada hace más de 30 días y ya fue purgada permanentemente por Microsoft.")
        return None

    user_id = target_user.get("id")
    display_name = target_user.get("displayName", "Alumno")
    deleted_date = target_user.get("deletedDateTime", "Recientemente")

    print(f"   👤 Alumno encontrado en Papelera: \033[1m{display_name}\033[0m")
    print(f"   🆔 Entra Object ID:              {user_id}")
    print(f"   📅 Fecha de eliminación:         {deleted_date}")

    confirm = input(f"\n¿Deseas restaurar a '{display_name}' y reactivar todos sus accesos? (s/n): ")
    if confirm.strip().lower() not in ["s", "si", "y", "yes"]:
        print("⛔ Restauración cancelada por el usuario.")
        return None

    # 2. Restaurar usuario en Entra ID
    print(f"\n🚀 Restaurando cuenta en Microsoft Graph...")
    try:
        restored = graph.restore_deleted_user(user_id)
        print(f"✅ ¡Cuenta de \033[1;32m{display_name}\033[0m restaurada exitosamente!")
    except Exception as e:
        print(f"❌ Error al restaurar usuario: {e}")
        return None

    # 3. Asignar/Verificar Licencia Office 365 A1
    student_sku = graph.find_student_sku()
    if student_sku:
        try:
            graph.assign_license(user_id, student_sku["skuId"])
            print(f"🏷️ Licencia {student_sku['skuPartNumber']} reasignada correctamente.")
        except Exception as e:
            print(f"⚠️ Nota de licencia: {e}")

    # 4. Actualizar estatus en Excel a 'Activo'
    excel_updated = update_student_status_in_excel(excel_path, sheet_name, matricula, "Activo")
    if excel_updated:
        print("📑 Estatus del alumno actualizado a 'Activo' en el Excel.")

    print("\n" + "╔" + "═" * 68 + "╗")
    print(f"║ {'CUENTA RESTAURADA EXITOSAMENTE':^68} ║")
    print("╠" + "═" * 68 + "╣")
    print(f"║ Alumno:        {display_name:<51} ║")
    print(f"║ Matrícula:     {matricula:<51} ║")
    print(f"║ Correo:        {upn:<51} ║")
    print(f"║ Estado:        \033[1;32m{'ACTIVO (Buzón, OneDrive y Teams Recuperados)':<43}\033[0m ║")
    print("╚" + "═" * 68 + "╝\n")

    return {
        "matricula": matricula,
        "upn": upn,
        "display_name": display_name,
        "id": user_id
    }
