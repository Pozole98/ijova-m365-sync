"""
Módulo de configuración y validación de parámetros del sistema.
"""
import os
import json
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    tenant_id: str = Field(default="", description="ID del Tenant de Microsoft Entra")
    client_id: str = Field(default="", description="ID de Aplicación (Client ID) de App Registration")
    domain: str = Field(default="ijova.com", description="Dominio oficial para cuentas M365")
    excel_path: str = Field(default="Listado de Alumnos Inscritos.xlsx", description="Ruta al archivo Excel")
    sheet_name: str = Field(default="Listado Global Matriculado", description="Nombre de la hoja a procesar")
    auth_method: str = Field(default="device_code", description="Método de autenticación: device_code o interactive")
    graph_scopes: List[str] = Field(
        default_factory=lambda: [
            "User.Read.All",
            "Domain.Read.All",
            "LicenseAssignment.Read.All"
        ],
        description="Scopes de Microsoft Graph (Mínimo Privilegio - Solo Lectura en Fase 1)"
    )
    reports_dir: str = Field(default="reports", description="Directorio para reportes CSV y resúmenes")
    backups_dir: str = Field(default="backups", description="Directorio para snapshots de auditoría (permisos 0700)")
    retention_days: int = Field(default=30, description="Días de retención para snapshots de auditoría antes de purga automática")
    data_dir: str = Field(default="data", description="Directorio para datos intermedios normalizados")
    secrets_dir: str = Field(default="secrets", description="Directorio protegido para secretos locales")


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """
    Carga la configuración desde un archivo JSON (o variables de entorno).
    Si el archivo no existe, utiliza los valores predeterminados y variables de entorno.
    """
    default_file = Path(config_path or "config.json")
    config_dict = {}

    if default_file.exists():
        with open(default_file, "r", encoding="utf-8") as f:
            config_dict = json.load(f)
    else:
        # Check environment variables
        if "M365_TENANT_ID" in os.environ:
            config_dict["tenant_id"] = os.environ["M365_TENANT_ID"]
        if "M365_CLIENT_ID" in os.environ:
            config_dict["client_id"] = os.environ["M365_CLIENT_ID"]
        if "M365_DOMAIN" in os.environ:
            config_dict["domain"] = os.environ["M365_DOMAIN"]
        if "M365_RETENTION_DAYS" in os.environ:
            try:
                config_dict["retention_days"] = int(os.environ["M365_RETENTION_DAYS"])
            except ValueError:
                pass

    config = AppConfig(**config_dict)

    # Ensure directories exist
    os.makedirs(config.reports_dir, exist_ok=True)
    os.makedirs(config.backups_dir, exist_ok=True)
    os.makedirs(os.path.join(config.data_dir, "normalized"), exist_ok=True)
    os.makedirs(config.secrets_dir, exist_ok=True)

    # Secure directory permissions (0700 - solo lectura/escritura por el propietario para protección de datos de menores)
    for protected_dir in [config.secrets_dir, config.backups_dir]:
        try:
            os.chmod(protected_dir, 0o700)
        except Exception:
            pass

    return config
