"""
Módulo de normalización técnica no destructiva para Microsoft Entra ID.
Preserva intactos los nombres humanos y genera atributos técnicos compatibles (mailNickname, alias, UPN).
"""
import os
import csv
import json
import unicodedata
import re
from typing import List
from collections import Counter
from src.models import StudentRecord, ClassificationEnum, ValidationIssue, IssueSeverity


def strip_accents(text: str) -> str:
    """Convierte caracteres acentuados y eñes a su equivalente ASCII base."""
    # Special handle ñ/Ñ -> n/N before general decomposition
    text = text.replace('ñ', 'n').replace('Ñ', 'N')
    text = text.replace('ü', 'u').replace('Ü', 'U')
    nfkd = unicodedata.normalize('NFKD', text)
    return "".join([c for c in nfkd if not unicodedata.combining(c)])


def sanitize_technical_string(text: str) -> str:
    """
    Convierte una cadena en formato seguro para mailNickname/alias:
    - Sin acentos ni caracteres no ASCII
    - Sin espacios internos (se remueven o unen)
    - En minúsculas
    - Solo caracteres alfanuméricos y puntos
    """
    clean = strip_accents(text).lower().strip()
    # Replace spaces with empty or single dot
    clean = re.sub(r'\s+', '', clean)
    # Remove any character that is not a-z, 0-9 or dot
    clean = re.sub(r'[^a-z0-9\.]', '', clean)
    return clean


def normalize_students(students: List[StudentRecord], domain: str = "ijova.com") -> List[StudentRecord]:
    """
    Normaliza atributos técnicos y humanos para Entra ID respetando la convención estándar del tenant:
    - given_name = Nombre(s)
    - surname = Apellido Paterno
    - display_name = Nombre(s) + Apellido Paterno
    - mail_nickname = Matrícula (numérico estándar del tenant)
    - upn_normalized = Matrícula@domain
    """
    for s in students:
        # 1. Atributos Humanos Estandarizados según el tenant
        s.given_name = " ".join(s.nombres.split())
        s.surname = " ".join(s.apellido_paterno.split())
        s.display_name = f"{s.given_name} {s.surname}".strip()

        # 2. UPN Normalizado: [Matricula]@domain
        if s.matricula:
            mat_clean = s.matricula.strip()
            s.upn_normalized = f"{mat_clean}@{domain.lower()}"
        else:
            s.upn_normalized = s.upn_raw.strip().lower()

        # 3. MailNickname estándar (Matrícula numérica, idéntico a las 75 cuentas existentes)
        s.mail_nickname = s.matricula.strip()

        # 4. Alias secundario saneado (primer_nombre.apellido_paterno@domain)
        primer_nombre = s.given_name.split()[0] if s.given_name else ""
        pat_sanitized = sanitize_technical_string(s.apellido_paterno)
        nom1_sanitized = sanitize_technical_string(primer_nombre)

        if nom1_sanitized and pat_sanitized:
            safe_alias = f"{nom1_sanitized}.{pat_sanitized}"
        elif nom1_sanitized:
            safe_alias = nom1_sanitized
        else:
            safe_alias = s.matricula.strip()

        s.alias_normalized = f"{safe_alias}@{domain.lower()}"

    # 4. Verificar si la normalización técnica introdujo nuevas colisiones de alias
    alias_counts = Counter([s.alias_normalized for s in students if s.alias_normalized])
    for s in students:
        if s.alias_normalized and alias_counts[s.alias_normalized] > 1:
            # Check if this student is not already marked as conflict
            if s.classification != ClassificationEnum.CONFLICTO:
                s.issues.append(ValidationIssue(
                    row_index=s.row_index,
                    matricula=s.matricula,
                    code="COLISION_ALIAS_NORMALIZADO",
                    severity=IssueSeverity.ERROR,
                    message=f"El alias normalizado '{s.alias_normalized}' colisiona con otro alumno. Se bloquea para evitar sobrescrituras.",
                    field="alias_normalized",
                    original_value=s.alias_raw,
                    suggested_value=s.alias_normalized
                ))
                s.classification = ClassificationEnum.CONFLICTO

    return students


def export_normalized_data(students: List[StudentRecord], output_dir: str = "data/normalized") -> str:
    """
    Exporta una copia independiente de los datos normalizados en formato CSV.
    El archivo Excel original NUNCA se toca.
    """
    os.makedirs(output_dir, exist_ok=True)
    out_file = os.path.join(output_dir, "alumnos_normalizados.csv")

    fieldnames = [
        "row_index", "matricula", "given_name", "surname", "display_name",
        "nivel", "grado_semestre", "estatus",
        "upn_original", "upn_normalized",
        "alias_original", "alias_normalized", "mail_nickname",
        "classification", "num_issues"
    ]

    with open(out_file, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for s in students:
            writer.writerow({
                "row_index": s.row_index,
                "matricula": s.matricula,
                "given_name": s.given_name,
                "surname": s.surname,
                "display_name": s.display_name,
                "nivel": s.nivel,
                "grado_semestre": s.grado_semestre,
                "estatus": s.estatus,
                "upn_original": s.upn_raw,
                "upn_normalized": s.upn_normalized,
                "alias_original": s.alias_raw,
                "alias_normalized": s.alias_normalized,
                "mail_nickname": s.mail_nickname,
                "classification": s.classification.value,
                "num_issues": len(s.issues)
            })

    return out_file
