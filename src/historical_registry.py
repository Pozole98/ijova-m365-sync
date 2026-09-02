"""
Gestor del Registro Histórico Permanente de Bajas y Regla de Bloqueo Anti-Reasignación de Matrículas.
Garantiza que una matrícula estudiantil sea intransferible de por vida y que las identidades
de alumnos dados de baja permanezcan archivadas para futuras reinscripciones o trámites.
"""
import os
import json
import csv
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple


DEFAULT_HISTORY_JSON = "data/historico_bajas_alumnos.json"
DEFAULT_HISTORY_CSV = "data/historico_bajas_alumnos.csv"


def get_historical_bajas(history_path: str = DEFAULT_HISTORY_JSON) -> List[Dict[str, Any]]:
    """Carga la lista completa de alumnos en el histórico de bajas."""
    if not os.path.exists(history_path) or os.path.getsize(history_path) == 0:
        return []
    try:
        with open(history_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        return []


def save_historical_bajas(records: List[Dict[str, Any]], history_json: str = DEFAULT_HISTORY_JSON, history_csv: str = DEFAULT_HISTORY_CSV) -> None:
    """Guarda el historial de bajas en formato JSON y CSV sincronizados."""
    os.makedirs(os.path.dirname(history_json) or "data", exist_ok=True)

    # 1. Guardar JSON
    with open(history_json, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    # 2. Guardar CSV
    if records:
        fieldnames = [
            "matricula", "upn", "nombre_completo", "apellido_paterno", "apellido_materno", "nombres",
            "nivel", "ultimo_grado", "motivo_baja", "entra_id", "fecha_baja_utc", "baja_por", "estatus"
        ]
        with open(history_csv, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for r in records:
                writer.writerow(r)


def record_student_baja(
    matricula: str,
    upn: str,
    nombre_completo: str,
    apellido_paterno: str = "",
    apellido_materno: str = "",
    nombres: str = "",
    nivel: str = "",
    ultimo_grado: str = "",
    motivo_baja: str = "",
    entra_id: str = "",
    baja_por: str = "admin",
    history_path: str = DEFAULT_HISTORY_JSON
) -> None:
    """Registra o actualiza a un alumno en el expediente histórico permanente de bajas."""
    records = get_historical_bajas(history_path)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Verificar si ya existe en el histórico para actualizarlo
    clean_mat = matricula.strip()
    existing_idx = None
    for idx, r in enumerate(records):
        if r.get("matricula", "").strip() == clean_mat:
            existing_idx = idx
            break

    new_record = {
        "matricula": clean_mat,
        "upn": upn.strip(),
        "nombre_completo": nombre_completo.strip().upper(),
        "apellido_paterno": apellido_paterno.strip().upper(),
        "apellido_materno": apellido_materno.strip().upper(),
        "nombres": nombres.strip().upper(),
        "nivel": nivel.strip(),
        "ultimo_grado": ultimo_grado.strip(),
        "motivo_baja": motivo_baja.strip() or "No reinscrito para el ciclo escolar",
        "entra_id": entra_id.strip(),
        "fecha_baja_utc": now_str,
        "baja_por": baja_por.strip(),
        "estatus": "Baja"
    }

    if existing_idx is not None:
        records[existing_idx] = new_record
    else:
        records.append(new_record)

    save_historical_bajas(records, history_path)


def mark_student_reactivated(matricula: str, history_path: str = DEFAULT_HISTORY_JSON) -> bool:
    """Marca a un alumno en el histórico como 'Reactivado / Reinscrito'."""
    records = get_historical_bajas(history_path)
    clean_mat = matricula.strip()
    found = False

    for r in records:
        if r.get("matricula", "").strip() == clean_mat:
            r["estatus"] = "Reactivado"
            r["fecha_reactivacion_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            found = True
            break

    if found:
        save_historical_bajas(records, history_path)
    return found


def check_matricula_transfer_conflict(
    matricula: str,
    incoming_full_name: str,
    history_path: str = DEFAULT_HISTORY_JSON
) -> Tuple[bool, Optional[str]]:
    """
    Regla de Bloqueo Anti-Reasignación de Matrículas:
    Comprueba si una matrícula ya fue asignada históricamente a OTRA persona.
    - Si la matrícula perteneció a otra persona: Retorna (True, "Mensaje de Bloqueo").
    - Si es la misma persona (mismo nombre) o la matrícula es libre: Retorna (False, None).
    """
    clean_mat = matricula.strip()
    if not clean_mat:
        return False, None

    records = get_historical_bajas(history_path)
    historical_owner = None

    for r in records:
        if r.get("matricula", "").strip() == clean_mat:
            historical_owner = r
            break

    if not historical_owner:
        return False, None

    # Comparar nombres para saber si es la misma persona reinscribiéndose o alguien diferente
    hist_name = (historical_owner.get("nombre_completo") or "").strip().upper()
    incoming_name = incoming_full_name.strip().upper()

    # Si los nombres son prácticamente idénticos (misma persona), se permite
    # Normalizar quitando espacios para comparación relajada
    h_clean = "".join(hist_name.split())
    i_clean = "".join(incoming_name.split())

    if h_clean and i_clean and (h_clean == i_clean or h_clean in i_clean or i_clean in h_clean):
        # Es la misma persona regresando
        return False, None

    # ¡ES OTRA PERSONA! Bloqueo estricto
    baja_date = historical_owner.get("fecha_baja_utc", "Fecha no registrada")
    motivo = historical_owner.get("motivo_baja", "Baja")
    msg = (
        f"La matrícula '{clean_mat}' ya perteneció históricamente a '{hist_name}' "
        f"(Estatus: {motivo}, Registrada el {baja_date}). "
        f"Las matrículas escolares son intransferibles de por vida y no pueden ser reasignadas a una persona diferente ('{incoming_name}'). "
        f"Por favor asigna una nueva matrícula correlativa libre (ej. 260xxx) al alumno nuevo."
    )
    return True, msg
