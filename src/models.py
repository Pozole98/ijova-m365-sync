"""
Modelos de datos fuertemente tipados para el flujo de validación, auditoría y sincronización.
"""
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ClassificationEnum(str, Enum):
    EXISTENTE = "EXISTENTE"
    NUEVO = "NUEVO"
    CONFLICTO = "CONFLICTO"
    INVALIDO = "INVALIDO"


class IssueSeverity(str, Enum):
    ERROR = "ERROR"        # Bloquea o descalifica el registro (conflicto o inválido)
    WARNING = "WARNING"    # Requiere normalización técnica sin bloquear si es corregible
    INFO = "INFO"          # Información de auditoría


class ValidationIssue(BaseModel):
    row_index: int
    matricula: str
    code: str
    severity: IssueSeverity
    message: str
    field: str
    original_value: str
    suggested_value: Optional[str] = None


class StudentRecord(BaseModel):
    row_index: int
    matricula: str
    apellido_paterno: str
    apellido_materno: str
    nombres: str
    nivel: str
    grado_semestre: str
    estatus: str
    upn_raw: str
    nombre1_raw: str
    nombre_limpio_raw: str
    apellido_limpio_raw: str
    alias_raw: str
    display_name_raw: str

    # Normalized fields (computed safely)
    given_name: str = ""
    surname: str = ""
    display_name: str = ""
    upn_normalized: str = ""
    mail_nickname: str = ""
    alias_normalized: str = ""

    # Classification & audit
    classification: ClassificationEnum = ClassificationEnum.NUEVO
    issues: List[ValidationIssue] = Field(default_factory=list)
    entra_id_match: Optional[str] = None
    discrepancies: List[str] = Field(default_factory=list)


class EntraUser(BaseModel):
    id: str
    user_principal_name: str
    display_name: Optional[str] = None
    given_name: Optional[str] = None
    surname: Optional[str] = None
    account_enabled: Optional[bool] = None
    mail: Optional[str] = None
    mail_nickname: Optional[str] = None
    user_type: Optional[str] = None
    assigned_licenses: List[Dict[str, Any]] = Field(default_factory=list)


class DomainStatus(BaseModel):
    domain_name: str
    is_verified: bool
    is_default: bool
    authentication_type: str  # "Managed" or "Federated"
    is_blocked: bool = False
    block_reason: Optional[str] = None


class AuditSnapshot(BaseModel):
    timestamp: str
    tenant_id: Optional[str] = None
    total_users: int
    domain_status: Optional[DomainStatus] = None
    users: List[EntraUser] = Field(default_factory=list)
