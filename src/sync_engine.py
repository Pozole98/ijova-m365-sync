"""
Motor de comparación y sincronización lógica (Sync Engine).
Determina el estado de cada alumno cruzando exclusivamente contra el UPN en Microsoft Entra ID.
"""
from typing import List, Dict, Tuple
from src.models import StudentRecord, EntraUser, ClassificationEnum


def run_sync_comparison(
    students: List[StudentRecord],
    entra_users: List[EntraUser]
) -> Tuple[List[StudentRecord], List[Dict[str, str]]]:
    """
    Cruza los registros de alumnos con el índice de usuarios de Microsoft Entra ID.
    - Matching estricto por userPrincipalName (UPN).
    - Detección de discrepancias para usuarios existentes (sin modificarlos).
    - Clasifica en: EXISTENTE, NUEVO, CONFLICTO, INVALIDO.
    """
    # 1. Crear índice de Entra ID por UPN (clave canónica en minúsculas)
    entra_by_upn: Dict[str, EntraUser] = {
        u.user_principal_name.strip().lower(): u for u in entra_users
    }

    discrepancies_list: List[Dict[str, str]] = []

    for s in students:
        upn_key = s.upn_normalized.strip().lower()
        upn_raw_key = s.upn_raw.strip().lower()

        # Si el alumno tiene conflicto de doble matrícula pero una de ellas ya existe en Entra ID:
        if s.classification == ClassificationEnum.CONFLICTO:
            # Caso 1: Si esta matrícula específica ya existe en Entra ID (ej. 260002), es la cuenta oficial
            if upn_key in entra_by_upn or upn_raw_key in entra_by_upn:
                matched_user = entra_by_upn.get(upn_key) or entra_by_upn.get(upn_raw_key)
                s.classification = ClassificationEnum.EXISTENTE
                s.entra_id_match = matched_user.id
                continue
            else:
                # Caso 2: Es la matrícula obsoleta/duplicada (ej. 250138). Se mantiene en CONFLICTO bloqueada.
                continue

        if s.classification == ClassificationEnum.INVALIDO:
            continue

        # 2. Comprobar existencia en Microsoft Entra ID por UPN
        matched_user = entra_by_upn.get(upn_key) or entra_by_upn.get(upn_raw_key)

        if matched_user:
            s.classification = ClassificationEnum.EXISTENTE
            s.entra_id_match = matched_user.id

            # Detectar discrepancias entre la hoja Excel y el estado real en Entra ID
            # (Únicamente para auditoría en discrepancias.csv, NUNCA para modificar al usuario)
            if matched_user.display_name and s.display_name:
                if matched_user.display_name.strip().upper() != s.display_name.strip().upper():
                    disc = f"DisplayName difiere: Entra='{matched_user.display_name}' vs Excel='{s.display_name}'"
                    s.discrepancies.append(disc)
                    discrepancies_list.append({
                        "matricula": s.matricula,
                        "upn": matched_user.user_principal_name,
                        "campo": "displayName",
                        "valor_entra": matched_user.display_name,
                        "valor_excel": s.display_name
                    })

            if matched_user.account_enabled is False:
                disc = "Cuenta deshabilitada en Entra ID pero presente en Excel escolar"
                s.discrepancies.append(disc)
                discrepancies_list.append({
                    "matricula": s.matricula,
                    "upn": matched_user.user_principal_name,
                    "campo": "accountEnabled",
                    "valor_entra": "False",
                    "valor_excel": "Activo"
                })

        else:
            # El UPN no existe en Entra ID y pasó todas las validaciones
            s.classification = ClassificationEnum.NUEVO

    return students, discrepancies_list
