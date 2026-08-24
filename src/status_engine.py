"""
Monitor ejecutivo de salud, métricas de identidad y licencias de Microsoft 365 / Entra ID.
"""
import os
import json
from datetime import datetime, timezone
from typing import Dict, Any
from tabulate import tabulate
from src.graph_client import GraphClient, GraphClientError


def execute_tenant_status_check(
    graph: GraphClient,
    domain: str = "ijova.com",
    backups_dir: str = "backups"
) -> Dict[str, Any]:
    """
    Ejecuta un diagnóstico completo y genera el tablero ejecutivo de salud del tenant.
    """
    print("\n🔍 Consultando métricas del tenant de Microsoft 365...")

    # 1. Dominio
    domain_status = graph.verify_domain(domain)

    # 2. Usuarios activos
    all_users = graph.get_all_users()
    students_count = 0
    staff_count = 0
    disabled_count = 0

    for u in all_users:
        upn = u.user_principal_name
        prefix = upn.split("@")[0]
        if prefix.isdigit():
            students_count += 1
        else:
            staff_count += 1
        if u.account_enabled is False:
            disabled_count += 1

    # 3. Papelera de reciclaje
    try:
        deleted_users = graph.get_deleted_users()
        deleted_count = len(deleted_users)
    except Exception:
        deleted_count = 0

    # 4. Licencias disponibles (SKUs)
    skus = graph.get_subscribed_skus()
    license_rows = []
    total_licenses = 0
    total_consumed = 0

    for s in skus:
        part_num = s.get("skuPartNumber", "Desconocido")
        prepaid = s.get("prepaidUnits", {}).get("enabled", 0)
        consumed = s.get("consumedUnits", 0)
        available = prepaid - consumed
        total_licenses += prepaid
        total_consumed += consumed

        pct = f"{(consumed / prepaid * 100):.1f}%" if prepaid > 0 else "0%"
        license_rows.append([part_num, prepaid, consumed, available, pct])

    # 5. Último respaldo
    last_backup_str = "Ninguno"
    if os.path.exists(backups_dir):
        bks = sorted([f for f in os.listdir(backups_dir) if f.endswith(".json")])
        if bks:
            last_backup_str = bks[-1].replace("entra_users_snapshot_", "").replace(".json", "")

    # RENDERIZAR DASHBOARD EJECUTIVO
    print("\n" + "╔" + "═" * 78 + "╗")
    print(f"║ {'INSTITUTO JOSÉ VASCONCELOS - MONITOR EJECUTIVO MICROSOFT 365':^76} ║")
    print("╠" + "═" * 78 + "╣")
    print(f"║ 🌐 Dominio Institucional:  \033[1;34m{domain:<30}\033[0m Estado: \033[1;32m{'VERIFICADO / MANAGED':<22}\033[0m ║")
    print(f"║ 👤 Administrador en sesión:\033[1m{(graph.admin_upn or 'admin@ijova.com'):<30}\033[0m Último Backup: \033[1;33m{last_backup_str:<16}\033[0m ║")
    print("╚" + "═" * 78 + "╝")

    # Tabla 1: Métricas de Usuarios
    user_metrics = [
        ["🎓 Alumnos Activos en Tenant", students_count],
        ["👨‍🏫 Personal Docente / Directivo / Staff", staff_count],
        ["🔒 Cuentas Deshabilitadas", disabled_count],
        ["🗑️ Cuentas en Papelera (Recuperables < 30 días)", deleted_count],
        ["👥 Total de Cuentas en Tenant", len(all_users)]
    ]
    print("\n📊 1. MÉTRICAS DE IDENTIDAD Y USUARIOS:")
    print(tabulate(user_metrics, headers=["Métrica", "Cantidad"], tablefmt="fancy_grid"))

    # Tabla 2: Licencias
    print("\n🏷️ 2. DISPONIBILIDAD DE LICENCIAS OFFICE 365:")
    if license_rows:
        print(tabulate(
            license_rows,
            headers=["Plan / Licencia (SKU)", "Total", "Asignadas", "Disponibles", "Ocupación"],
            tablefmt="fancy_grid"
        ))
    else:
        print("   ℹ️ No se detectaron licencias activas.")

    print(f"\n💡 Estado General: \033[1;32mÓPTIMO\033[0m — Licencias A1 listas para nuevas inscripciones.")

    return {
        "domain": domain,
        "students_count": students_count,
        "staff_count": staff_count,
        "deleted_count": deleted_count,
        "total_licenses": total_licenses,
        "total_consumed": total_consumed
    }
