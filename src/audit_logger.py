"""
Módulo centralizado de auditoría y trazabilidad de operaciones críticas en Microsoft 365.
Registra marcas de tiempo UTC, identidades administrativas y resultados en logs/ijova_audit.log.
"""
import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone
from typing import Optional

LOGS_DIR = "logs"
AUDIT_LOG_FILE = os.path.join(LOGS_DIR, "ijova_audit.log")

# Configurar logger singleton
_logger: Optional[logging.Logger] = None


def get_audit_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    os.makedirs(LOGS_DIR, exist_ok=True)
    try:
        os.chmod(LOGS_DIR, 0o700)
    except Exception:
        pass

    logger = logging.getLogger("ijova_audit")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    # Evitar handlers duplicados si se recarga el módulo
    if not logger.handlers:
        handler = RotatingFileHandler(
            AUDIT_LOG_FILE,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=5,
            encoding="utf-8"
        )
        formatter = logging.Formatter(
            fmt="%(asctime)s UTC [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        # Formatear en UTC
        formatter.converter = lambda *args: datetime.now(timezone.utc).timetuple()
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        try:
            if os.path.exists(AUDIT_LOG_FILE):
                os.chmod(AUDIT_LOG_FILE, 0o600)
        except Exception:
            pass

    _logger = logger
    return _logger


def log_audit_event(
    action: str,
    target: str,
    admin: str = "Desconocido",
    status: str = "SUCCESS",
    details: str = ""
):
    """
    Registra un evento de auditoría formal para cumplimiento institucional.
    
    :param action: Código de acción (ej. ENROLL, DELETE, RESET_PASSWORD, RESTORE, BULK_RESET)
    :param target: Identificador afectado (ej. Matrícula, UPN o total de alumnos)
    :param admin: Correo del administrador de Entra ID que ejecutó la acción
    :param status: Resultado (SUCCESS, FAILED, BLOCKED, WARNING)
    :param details: Contexto adicional o motivo de bloqueo
    """
    logger = get_audit_logger()
    clean_admin = admin or "Desconocido"
    msg = f"[ACTION: {action}] [TARGET: {target}] [ADMIN: {clean_admin}] [STATUS: {status}]"
    if details:
        msg += f" - {details}"

    if status in ["FAILED", "ERROR"]:
        logger.error(msg)
    elif status in ["BLOCKED", "WARNING"]:
        logger.warning(msg)
    else:
        logger.info(msg)
