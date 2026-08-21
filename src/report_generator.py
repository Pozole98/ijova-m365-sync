"""
Generador exhaustivo de reportes en consola, Markdown y archivos CSV segmentados.
Exporta existentes.csv, nuevos.csv, conflictos.csv, invalidos.csv y discrepancias.csv.
"""
import os
import csv
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from tabulate import tabulate
from src.models import StudentRecord, ClassificationEnum, DomainStatus


def generate_reports(
    students: List[StudentRecord],
    discrepancies: List[Dict[str, str]],
    domain_status: Optional[DomainStatus] = None,
    admin_upn: Optional[str] = None,
    output_dir: str = "reports",
    is_dry_run: bool = True
) -> Dict[str, str]:
    """
    Genera y guarda los reportes estructurados, archivos CSV segmentados y el resumen de auditoría Markdown.
    Incluye rastro de auditoría: Timestamp UTC y Admin UPN.
    """
    os.makedirs(output_dir, exist_ok=True)
    generated_files: Dict[str, str] = {}
    timestamp_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Separate students by classification
    existentes = [s for s in students if s.classification == ClassificationEnum.EXISTENTE]
    nuevos = [s for s in students if s.classification == ClassificationEnum.NUEVO]
    conflictos = [s for s in students if s.classification == ClassificationEnum.CONFLICTO]
    invalidos = [s for s in students if s.classification == ClassificationEnum.INVALIDO]

    # Metrics
    total_registros = len(students)
    matriculas_unicas = len(set(s.matricula for s in students if s.matricula))
    
    # Personas potencialmente únicas
    import unicodedata
    def norm_name(s: StudentRecord) -> str:
        t = unicodedata.normalize('NFKD', f"{s.nombres} {s.apellido_paterno} {s.apellido_materno}").encode('ASCII', 'ignore').decode('utf-8')
        return " ".join(t.upper().split())
    personas_unicas = len(set(norm_name(s) for s in students))

    # Helper function to write CSV
    def write_student_csv(filename: str, records: List[StudentRecord], extra_cols: bool = False):
        filepath = os.path.join(output_dir, filename)
        fieldnames = [
            "row_index", "matricula", "nombres", "apellido_paterno", "apellido_materno",
            "display_name", "nivel", "grado_semestre", "estatus",
            "upn_normalized", "alias_normalized", "mail_nickname", "classification"
        ]
        if extra_cols:
            fieldnames.extend(["motivo_bloqueo_o_error", "entra_id_match"])

        with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for s in records:
                row_dict = {
                    "row_index": s.row_index,
                    "matricula": s.matricula,
                    "nombres": s.nombres,
                    "apellido_paterno": s.apellido_paterno,
                    "apellido_materno": s.apellido_materno,
                    "display_name": s.display_name,
                    "nivel": s.nivel,
                    "grado_semestre": s.grado_semestre,
                    "estatus": s.estatus,
                    "upn_normalized": s.upn_normalized,
                    "alias_normalized": s.alias_normalized,
                    "mail_nickname": s.mail_nickname,
                    "classification": s.classification.value
                }
                if extra_cols:
                    issues_str = " | ".join([f"[{i.code}] {i.message}" for i in s.issues])
                    row_dict["motivo_bloqueo_o_error"] = issues_str
                    row_dict["entra_id_match"] = s.entra_id_match or ""
                writer.writerow(row_dict)

        generated_files[filename] = filepath

    # 1. Export CSVs
    write_student_csv("existentes.csv", existentes, extra_cols=True)
    write_student_csv("nuevos.csv", nuevos, extra_cols=True)
    write_student_csv("conflictos.csv", conflictos, extra_cols=True)
    write_student_csv("invalidos.csv", invalidos, extra_cols=True)

    # 2. Export Discrepancias CSV
    disc_path = os.path.join(output_dir, "discrepancias.csv")
    with open(disc_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["matricula", "upn", "campo", "valor_entra", "valor_excel"])
        writer.writeheader()
        for d in discrepancies:
            writer.writerow(d)
    generated_files["discrepancias.csv"] = disc_path

    # 3. Export Markdown Summary for Audit Evidence
    md_summary_path = os.path.join(output_dir, "dry_run_audit_summary.md")
    with open(md_summary_path, "w", encoding="utf-8") as f:
        f.write("# Rastro de Auditoría y Resumen de Simulación (Dry-Run)\n\n")
        f.write(f"- **Fecha y Hora de Ejecución:** `{timestamp_utc}`\n")
        f.write(f"- **Administrador Responsable (UPN):** `{admin_upn or 'No autenticado / Validación local'}`\n")
        f.write(f"- **Modo de Operación:** `{'DRY-RUN (Simulación 100% solo lectura)' if is_dry_run else 'VALIDACIÓN LOCAL'}`\n")
        f.write(f"- **Dominio Validado:** `{domain_status.domain_name if domain_status else 'N/A'}` (Verificado: `{domain_status.is_verified if domain_status else 'N/A'}`)\n\n")
        f.write("## 📊 Métricas de Sincronización\n\n")
        f.write(f"| Métrica | Cantidad |\n| :--- | :---: |\n")
        f.write(f"| Registros Administrativos Totales | **{total_registros}** |\n")
        f.write(f"| Matrículas Únicas en Hoja | **{matriculas_unicas}** |\n")
        f.write(f"| Personas Potencialmente Únicas | **{personas_unicas}** |\n")
        f.write(f"| Cuentas EXISTENTES en Entra ID (Intactas) | **{len(existentes)}** |\n")
        f.write(f"| Cuentas NUEVAS (Candidatas a creación) | **{len(nuevos)}** |\n")
        f.write(f"| CONFLICTOS (Bloqueados para creación) | **{len(conflictos)}** |\n")
        f.write(f"| INVÁLIDOS (Errores estructurales) | **{len(invalidos)}** |\n")
        f.write(f"| Discrepancias Detectadas | **{len(discrepancies)}** |\n\n")

        if conflictos:
            f.write("## ⚠️ Registros Bloqueados por Conflicto\n\n")
            f.write("| Fila | Matrícula | Nombre | UPN | Motivo de Conflicto |\n| :---: | :---: | :--- | :--- | :--- |\n")
            for c in conflictos:
                issues_msg = " ; ".join([f"[{i.code}] {i.message}" for i in c.issues if i.severity == "ERROR"])
                f.write(f"| {c.row_index} | {c.matricula} | {c.display_name} | {c.upn_normalized} | {issues_msg} |\n")
    generated_files["dry_run_audit_summary.md"] = md_summary_path

    # 4. Print Console Summary Table
    print("\n" + "=" * 80)
    mode_title = "SIMULACIÓN DRY RUN - MICROSOFT ENTRA ID" if is_dry_run else "VALIDACIÓN LOCAL DE EXCEL"
    print(f"📊 REPORTE DE RESULTADOS: {mode_title}")
    print("=" * 80)
    print(f"🕒 Timestamp de Ejecución: {timestamp_utc}")
    print(f"👤 Administrador Autenticado: {admin_upn or 'Validación Local / Sin Autenticación'}")
    print("-" * 80)

    summary_table = [
        ["Registros Administrativos Totales", total_registros],
        ["Matrículas Únicas en Hoja", matriculas_unicas],
        ["Personas Potencialmente Únicas", personas_unicas],
        ["----------------------------------------", "------"],
        ["Cuentas EXISTENTES en Entra ID (Omitidas sin cambios)", len(existentes)],
        ["Cuentas NUEVAS (Candidatas a creación futura)", len(nuevos)],
        ["CONFLICTOS (Bloqueados - Requieren decisión)", len(conflictos)],
        ["INVÁLIDOS (Errores de formato en hoja)", len(invalidos)],
        ["----------------------------------------", "------"],
        ["Discrepancias Hoja vs Entra ID", len(discrepancies)]
    ]
    print(tabulate(summary_table, headers=["Métrica", "Cantidad"], tablefmt="fancy_grid"))

    if domain_status:
        print("\n🌐 Estado del Dominio Institucional:")
        print(f"   - Dominio: {domain_status.domain_name}")
        print(f"   - Verificado: {'✅ SÍ' if domain_status.is_verified else '❌ NO (BLOQUEO)'}")
        print(f"   - Tipo de Autenticación: {domain_status.authentication_type}")
        if domain_status.is_blocked:
            print(f"   - \033[1;31mALERTA:\033[0m {domain_status.block_reason}")

    if conflictos:
        print("\n⚠️ REGISTROS EN CONFLICTO (BLOQUEADOS PARA CREACIÓN):")
        conflict_rows = []
        for c in conflictos:
            issues_msg = " ; ".join([f"[{i.code}] {i.message}" for i in c.issues if i.severity == "ERROR"])
            conflict_rows.append([c.row_index, c.matricula, c.display_name, c.upn_normalized, issues_msg])
        print(tabulate(conflict_rows, headers=["Fila", "Matrícula", "Nombre", "UPN", "Motivo de Conflicto"], tablefmt="grid"))

    print("\n📁 Archivos de reporte generados en:", os.path.abspath(output_dir))
    for name, path in generated_files.items():
        print(f"   • {name}: {path}")

    return generated_files
