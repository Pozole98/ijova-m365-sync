"""
Motor de validación exhaustiva de integridad, formato y reglas de negocio para alumnos.
"""
import re
import unicodedata
from typing import List, Dict
from collections import Counter
from src.models import StudentRecord, ValidationIssue, IssueSeverity, ClassificationEnum


MATRICULA_REGEX = re.compile(r"^2\d{5}$")


def is_valid_matricula_format(matricula: str) -> bool:
    """
    Verifica que la matrícula cumpla con el estándar institucional del IJOVA:
    Exactamente 6 dígitos numéricos iniciando con el prefijo generacional de la década actual (ej. 25xxxx, 26xxxx).
    """
    if not matricula or not isinstance(matricula, str):
        return False
    return bool(MATRICULA_REGEX.match(matricula.strip()))


def validate_students(students: List[StudentRecord], expected_domain: str = "ijova.com") -> List[StudentRecord]:
    """
    Ejecuta una batería completa de validaciones sobre la lista de alumnos extraída.
    Asigna issues y clasificaciones iniciales (CONFLICTO, INVALIDO o NUEVO pendiente de cruce Entra ID).
    """
    # 1. Check duplicate matriculas in the dataset
    matriculas_list = [s.matricula for s in students if s.matricula]
    mat_counter = Counter(matriculas_list)
    dup_mats = {m for m, count in mat_counter.items() if count > 1}

    # 2. Check duplicate aliases in the dataset
    aliases_list = [s.alias_raw.lower() for s in students if s.alias_raw]
    alias_counter = Counter(aliases_list)
    dup_aliases = {a for a, count in alias_counter.items() if count > 1}

    # 3. Check duplicate full person names (normalized)
    def normalize_str(s: str) -> str:
        s = unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('utf-8')
        return " ".join(s.upper().split())

    full_names_map: Dict[str, List[StudentRecord]] = {}
    for s in students:
        full_n = normalize_str(f"{s.nombres} {s.apellido_paterno} {s.apellido_materno}")
        if full_n not in full_names_map:
            full_names_map[full_n] = []
        full_names_map[full_n].append(s)

    dup_persons = {name: recs for name, recs in full_names_map.items() if len(recs) > 1}

    for s in students:
        s.issues = []

        # --- A. Validación de Matrícula ---
        if not s.matricula:
            s.issues.append(ValidationIssue(
                row_index=s.row_index,
                matricula="",
                code="MATRICULA_VACIA",
                severity=IssueSeverity.ERROR,
                message="El alumno no tiene matrícula asignada en la hoja.",
                field="matricula",
                original_value=""
            ))
            s.classification = ClassificationEnum.INVALIDO

        elif not is_valid_matricula_format(s.matricula):
            s.issues.append(ValidationIssue(
                row_index=s.row_index,
                matricula=s.matricula,
                code="MATRICULA_FORMATO_INVALIDO",
                severity=IssueSeverity.ERROR,
                message=f"El formato de la matrícula '{s.matricula}' es inválido. Debe constar exactamente de 6 dígitos numéricos iniciando con el año (ej. 25xxxx o 26xxxx).",
                field="matricula",
                original_value=s.matricula
            ))
            s.classification = ClassificationEnum.INVALIDO

        elif s.matricula in dup_mats:
            s.issues.append(ValidationIssue(
                row_index=s.row_index,
                matricula=s.matricula,
                code="MATRICULA_DUPLICADA",
                severity=IssueSeverity.ERROR,
                message=f"La matrícula '{s.matricula}' se repite en múltiples filas de la hoja.",
                field="matricula",
                original_value=s.matricula
            ))
            s.classification = ClassificationEnum.CONFLICTO

        else:
            # --- Validación Anti-Reasignación de Matrícula Histórica ---
            from src.historical_registry import check_matricula_transfer_conflict
            student_full_name = f"{s.nombres} {s.apellido_paterno} {s.apellido_materno}".strip()
            is_conflict, conflict_msg = check_matricula_transfer_conflict(s.matricula, student_full_name)
            if is_conflict:
                s.issues.append(ValidationIssue(
                    row_index=s.row_index,
                    matricula=s.matricula,
                    code="MATRICULA_INTRANSFERIBLE_REASIGNADA",
                    severity=IssueSeverity.CRITICAL,
                    message=conflict_msg or "Matrícula histórica ya asignada a otra persona.",
                    field="matricula",
                    original_value=s.matricula
                ))
                s.classification = ClassificationEnum.CONFLICTO

        # --- B. Detección de Conflicto de Doble Matrícula (Misma Persona) ---
        full_n = normalize_str(f"{s.nombres} {s.apellido_paterno} {s.apellido_materno}")
        if full_n in dup_persons and len(dup_persons[full_n]) > 1:
            other_mats = [o.matricula for o in dup_persons[full_n] if o.row_index != s.row_index]
            s.issues.append(ValidationIssue(
                row_index=s.row_index,
                matricula=s.matricula,
                code="PERSONA_DUPLICADA_DOBLE_MATRICULA",
                severity=IssueSeverity.ERROR,
                message=f"El alumno '{s.nombres} {s.apellido_paterno} {s.apellido_materno}' tiene otra matrícula registrada en la hoja ({', '.join(other_mats)}). Requiere confirmación administrativa.",
                field="nombre_completo",
                original_value=f"Fila {s.row_index}, Matrícula {s.matricula}"
            ))
            s.classification = ClassificationEnum.CONFLICTO

        # --- C. Validación de Nombres y Apellidos ---
        if not s.nombres:
            s.issues.append(ValidationIssue(
                row_index=s.row_index,
                matricula=s.matricula,
                code="NOMBRE_VACIO",
                severity=IssueSeverity.ERROR,
                message="El alumno no tiene nombre(s) registrado.",
                field="nombres",
                original_value=""
            ))
            s.classification = ClassificationEnum.INVALIDO

        if not s.apellido_paterno:
            s.issues.append(ValidationIssue(
                row_index=s.row_index,
                matricula=s.matricula,
                code="PATERNO_VACIO",
                severity=IssueSeverity.ERROR,
                message="El alumno no tiene apellido paterno registrado.",
                field="apellido_paterno",
                original_value=""
            ))
            s.classification = ClassificationEnum.INVALIDO

        if not s.apellido_materno:
            # Not an error, just an informational notice (e.g. foreign students)
            s.issues.append(ValidationIssue(
                row_index=s.row_index,
                matricula=s.matricula,
                code="MATERNO_VACIO",
                severity=IssueSeverity.INFO,
                message="El alumno no tiene apellido materno (ej. alumno extranjero).",
                field="apellido_materno",
                original_value=""
            ))

        # --- D. Validación de UPN en la Hoja ---
        upn = s.upn_raw
        if not upn:
            s.issues.append(ValidationIssue(
                row_index=s.row_index,
                matricula=s.matricula,
                code="UPN_VACIO",
                severity=IssueSeverity.ERROR,
                message="El campo UPN está vacío en la hoja.",
                field="upn",
                original_value=""
            ))
            s.classification = ClassificationEnum.INVALIDO
        else:
            if upn != upn.strip():
                s.issues.append(ValidationIssue(
                    row_index=s.row_index,
                    matricula=s.matricula,
                    code="UPN_ESPACIOS_EXTREMOS",
                    severity=IssueSeverity.WARNING,
                    message="El UPN tiene espacios al inicio o al final.",
                    field="upn",
                    original_value=upn,
                    suggested_value=upn.strip()
                ))
            if " " in upn.strip():
                s.issues.append(ValidationIssue(
                    row_index=s.row_index,
                    matricula=s.matricula,
                    code="UPN_ESPACIOS_INTERNOS",
                    severity=IssueSeverity.ERROR,
                    message="El UPN contiene espacios en su interior.",
                    field="upn",
                    original_value=upn
                ))
                s.classification = ClassificationEnum.INVALIDO

            expected_suffix = f"@{expected_domain}".lower()
            if not upn.strip().lower().endswith(expected_suffix):
                s.issues.append(ValidationIssue(
                    row_index=s.row_index,
                    matricula=s.matricula,
                    code="UPN_DOMINIO_INCORRECTO",
                    severity=IssueSeverity.ERROR,
                    message=f"El dominio del UPN no coincide con @{expected_domain}.",
                    field="upn",
                    original_value=upn
                ))
                s.classification = ClassificationEnum.INVALIDO

            # Check special chars / accents in UPN
            if re.search(r'[áéíóúÁÉÍÓÚñÑüÜ]', upn):
                s.issues.append(ValidationIssue(
                    row_index=s.row_index,
                    matricula=s.matricula,
                    code="UPN_CON_ACENTOS",
                    severity=IssueSeverity.ERROR,
                    message="El UPN contiene caracteres acentuados o eñes no permitidos en Microsoft Entra.",
                    field="upn",
                    original_value=upn
                ))
                s.classification = ClassificationEnum.INVALIDO

        # --- E. Validación de Alias de Correo ---
        alias = s.alias_raw
        if alias:
            if " " in alias:
                s.issues.append(ValidationIssue(
                    row_index=s.row_index,
                    matricula=s.matricula,
                    code="ALIAS_ESPACIOS_INTERNOS",
                    severity=IssueSeverity.WARNING,
                    message="El alias contiene espacios debido a apellidos compuestos o espacios en celdas.",
                    field="alias",
                    original_value=alias
                ))
            if re.search(r'[áéíóúÁÉÍÓÚñÑüÜ]', alias):
                s.issues.append(ValidationIssue(
                    row_index=s.row_index,
                    matricula=s.matricula,
                    code="ALIAS_CON_ACENTOS_ENES",
                    severity=IssueSeverity.WARNING,
                    message="El alias contiene letras con acento o eñes no estándar para direcciones SMTP/mailNickname.",
                    field="alias",
                    original_value=alias
                ))
            if alias.lower() in dup_aliases and len(dup_aliases) > 0:
                s.issues.append(ValidationIssue(
                    row_index=s.row_index,
                    matricula=s.matricula,
                    code="ALIAS_DUPLICADO",
                    severity=IssueSeverity.ERROR,
                    message=f"El alias '{alias}' colisiona con otro registro de la hoja.",
                    field="alias",
                    original_value=alias
                ))
                s.classification = ClassificationEnum.CONFLICTO

        # --- F. Estatus de Baja ---
        if s.estatus.strip().lower() == "baja":
            s.issues.append(ValidationIssue(
                row_index=s.row_index,
                matricula=s.matricula,
                code="ESTATUS_BAJA",
                severity=IssueSeverity.INFO,
                message="El alumno está marcado con estatus 'Baja' en el sistema escolar.",
                field="estatus",
                original_value=s.estatus
            ))

    return students
