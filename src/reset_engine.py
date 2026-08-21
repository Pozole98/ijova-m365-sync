"""
Motor de reseteo rápido de contraseñas para alumnos en Microsoft 365 / Entra ID.
Genera una nueva contraseña temporal segura en 2 segundos, fuerza el cambio de contraseña
y genera la ficha de acceso individual en PDF y consola.
"""
import os
import csv
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from src.graph_client import GraphClient, GraphClientError
from src.password_generator import generate_secure_password
from src.enroll_engine import print_welcome_card
from src.delete_engine import is_student_matricula
from src.pdf_generator import generate_pdf_cards_from_list


def execute_password_reset(
    identifier: str,
    graph: GraphClient,
    domain: str = "ijova.com",
    secrets_dir: str = "secrets",
    reports_dir: str = "reports"
) -> Optional[Dict[str, Any]]:
    """
    Restablece la contraseña de un alumno por su matrícula en Microsoft 365.
    """
    # 1. Validar salvaguarda anti-admin (solo matrículas estudiantiles)
    is_valid, result = is_student_matricula(identifier)
    if not is_valid:
        print(f"\n⛔ BLOQUEO DE SEGURIDAD: {result}")
        return None

    upn = result
    matricula = upn.split("@")[0]

    print(f"\n🔍 Buscando alumno con matrícula \033[1;34m{matricula}\033[0m ({upn})...")
    user = graph.get_user_by_upn(upn)
    if not user:
        print(f"❌ El alumno {upn} no existe en Microsoft Entra ID.")
        return None

    user_id = user.get("id")
    display_name = user.get("displayName", "Alumno")

    print(f"   👤 Alumno: \033[1m{display_name}\033[0m (ID: {user_id})")

    # 2. Generar nueva contraseña temporal segura
    new_password = generate_secure_password(length=12)

    # 3. Aplicar reseteo en Microsoft Entra ID vía Graph
    print(f"⚡ Restableciendo contraseña en Microsoft 365...")
    try:
        success = graph.reset_password(user_id, new_password)
        if not success:
            print(f"❌ No se pudo restablecer la contraseña en Graph.")
            return None
        print(f"✅ Contraseña restablecida con éxito en la nube.")
    except Exception as e:
        print(f"❌ Error al comunicarse con Microsoft Graph: {e}")
        return None

    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
    
    # 4. Guardar en bitácora protegida de reseteos en secrets/
    os.makedirs(secrets_dir, exist_ok=True)
    os.makedirs(reports_dir, exist_ok=True)
    reset_log_file = os.path.join(secrets_dir, "historial_reseteos_contrasenas.csv")
    file_exists = os.path.exists(reset_log_file)
    with open(reset_log_file, "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["matricula", "upn", "display_name", "nueva_password", "reset_by", "timestamp_utc"])
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "matricula": matricula,
            "upn": upn,
            "display_name": display_name,
            "nueva_password": new_password,
            "reset_by": graph.admin_upn or "admin",
            "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        })
    try:
        os.chmod(reset_log_file, 0o600)
    except Exception:
        pass

    # 5. Generar Ficha Individual en PDF lista para imprimir
    pdf_out = os.path.join(secrets_dir, f"ficha_acceso_reset_{matricula}_{timestamp_str}.pdf")
    student_dict = {
        "matricula": matricula,
        "upn": upn,
        "nombre_completo": display_name,
        "password_temporal": new_password,
        "nivel": "Estudiante",
        "grado_semestre": "Activo"
    }
    try:
        generate_pdf_cards_from_list([student_dict], pdf_out, layout_mode="cards")
        print(f"📄 Ficha PDF generada lista para imprimir: \033[1;32m{pdf_out}\033[0m")
    except Exception as e:
        print(f"⚠️ No se pudo generar el PDF individual: {e}")

    # 6. Imprimir Ficha en consola
    print_welcome_card(
        matricula=matricula,
        upn=upn,
        display_name=display_name,
        nivel="Estudiante",
        grado="Activo",
        temp_password=new_password,
        domain=domain
    )

    return {
        "matricula": matricula,
        "upn": upn,
        "display_name": display_name,
        "password": new_password,
        "pdf_path": pdf_out
    }
