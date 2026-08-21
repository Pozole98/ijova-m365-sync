"""
Generador de snapshots de auditoría para Microsoft Entra ID.
Captura el estado exacto de los usuarios existentes antes de cualquier comparación o simulación.
"""
import os
import csv
import json
from datetime import datetime, timezone
from typing import List, Optional
from src.models import EntraUser, DomainStatus, AuditSnapshot


def purge_old_snapshots(output_dir: str = "backups", retention_days: int = 30) -> List[str]:
    """
    Política de retención y purga automática de datos de menores:
    Elimina snapshots con antigüedad superior a retention_days días.
    """
    if retention_days <= 0 or not os.path.exists(output_dir):
        return []

    purged = []
    now_ts = datetime.now(timezone.utc).timestamp()
    retention_seconds = retention_days * 86400

    for fname in os.listdir(output_dir):
        if fname.startswith("entra_users_snapshot_") and (fname.endswith(".json") or fname.endswith(".csv")):
            fpath = os.path.join(output_dir, fname)
            try:
                mtime = os.path.getmtime(fpath)
                if (now_ts - mtime) > retention_seconds:
                    os.remove(fpath)
                    purged.append(fpath)
            except Exception as e:
                print(f"⚠️ No se pudo purgar snapshot antiguo {fpath}: {e}")

    if purged:
        print(f"🧹 Purga automática completada: {len(purged)} archivos de snapshot antiguos (> {retention_days} días) eliminados.")
    return purged


def create_audit_snapshot(
    users: List[EntraUser],
    domain_status: Optional[DomainStatus] = None,
    tenant_id: Optional[str] = None,
    output_dir: str = "backups",
    retention_days: int = 30
) -> str:
    """
    Guarda un snapshot estructurado (JSON y CSV) con la lista exacta de usuarios existentes en el tenant.
    Aplica permisos restrictivos (0700) y ejecuta purga de retención de datos.
    No incluye información sensible ni contraseñas.
    """
    os.makedirs(output_dir, exist_ok=True)
    try:
        os.chmod(output_dir, 0o700)
    except Exception:
        pass

    # Ejecutar purga de retención previa
    purge_old_snapshots(output_dir=output_dir, retention_days=retention_days)

    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
    
    # 1. Save JSON Snapshot
    snapshot_data = AuditSnapshot(
        timestamp=timestamp_str,
        tenant_id=tenant_id,
        total_users=len(users),
        domain_status=domain_status,
        users=users
    )

    json_path = os.path.join(output_dir, f"entra_users_snapshot_{timestamp_str}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(snapshot_data.model_dump(), f, indent=2, ensure_ascii=False)
    try:
        os.chmod(json_path, 0o600)
    except Exception:
        pass

    # 2. Save CSV Snapshot for easy viewing
    csv_path = os.path.join(output_dir, f"entra_users_snapshot_{timestamp_str}.csv")
    fieldnames = [
        "id", "user_principal_name", "display_name", "given_name",
        "surname", "account_enabled", "mail", "mail_nickname", "user_type"
    ]
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for u in users:
            writer.writerow({
                "id": u.id,
                "user_principal_name": u.user_principal_name,
                "display_name": u.display_name or "",
                "given_name": u.given_name or "",
                "surname": u.surname or "",
                "account_enabled": u.account_enabled if u.account_enabled is not None else "",
                "mail": u.mail or "",
                "mail_nickname": u.mail_nickname or "",
                "user_type": u.user_type or ""
            })
    try:
        os.chmod(csv_path, 0o600)
    except Exception:
        pass

    print(f"📁 Snapshot de auditoría guardado exitosamente:\n   - JSON: {json_path}\n   - CSV:  {csv_path}")
    return json_path
