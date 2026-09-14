"""
Servidor y API REST de la Interfaz Gráfica Web Local (ijovausers).
Proporciona el panel interactivo para verificación, reseteo de contraseñas,
impresión de fichas con código QR y consulta de estado del tenant.
"""
import os
import io
import csv
import json
import logging
import threading
import webbrowser
from typing import Optional, Dict, Any, List
from flask import Flask, render_template, request, jsonify, send_file, abort

from src.config import load_config, AppConfig
from src.graph_client import GraphClient, GraphClientError
from src.reset_engine import verify_student_for_reset, execute_password_reset
from src.excel_parser import parse_excel_students

# Desactivar logs ruidosos de werkzeug en consola para mantener la salida limpia
logging.getLogger("werkzeug").setLevel(logging.WARNING)


def create_app(config_path: str = "config.json") -> Flask:
    """Fábrica de la aplicación web Flask para el panel de administración."""
    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    
    app = Flask(
        __name__,
        template_folder=template_dir,
        static_folder=static_dir,
        static_url_path="/static"
    )
    app.config["CONFIG_PATH"] = config_path

    # Cargar configuración base
    config: AppConfig = load_config(config_path)
    app.config["APP_CONFIG"] = config

    # Cliente Graph singleton perezoso (lazy)
    _graph_lock = threading.Lock()
    _graph_instance: Optional[GraphClient] = None

    def get_graph() -> GraphClient:
        nonlocal _graph_instance
        with _graph_lock:
            if _graph_instance is None:
                write_scopes = ["User.ReadWrite.All", "Domain.Read.All", "LicenseAssignment.Read.All"]
                client = GraphClient(config.tenant_id, config.client_id, write_scopes)
                client.authenticate_device_code()
                _graph_instance = client
            return _graph_instance

    # Caché en memoria de alumnos del Excel escolar para búsqueda rápida
    _students_cache: Optional[List[Dict[str, Any]]] = None

    def get_cached_students() -> List[Dict[str, Any]]:
        nonlocal _students_cache
        if _students_cache is None:
            items = []
            if os.path.exists(config.excel_path):
                try:
                    records = parse_excel_students(config.excel_path, config.sheet_name)
                    for r in records:
                        nombre_completo = f"{r.apellido_paterno} {r.apellido_materno} {r.nombres}".strip()
                        items.append({
                            "matricula": r.matricula.strip(),
                            "nombre": nombre_completo,
                            "nivel": r.nivel or "Estudiante",
                            "grado": r.grado_semestre or "Activo",
                            "upn": f"{r.matricula.strip()}@{config.domain}"
                        })
                except Exception as e:
                    app.logger.warning(f"No se pudo cargar el listado del Excel: {e}")
            _students_cache = items
        return _students_cache

    @app.route("/")
    def index():
        """Página principal del panel interactivo."""
        return render_template(
            "index.html",
            domain=config.domain,
            excel_path=os.path.basename(config.excel_path),
            tenant_id=config.tenant_id[:8] + "..." if config.tenant_id else "No configurado"
        )

    @app.route("/logo")
    def get_logo():
        """Sirve el logotipo institucional oficial."""
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        logo_png = os.path.join(project_root, "assets", "logo_ijova.png")
        if os.path.exists(logo_png):
            return send_file(logo_png, mimetype="image/png")
        logo_jpg = os.path.join(project_root, "ijovanotext.jpeg")
        if os.path.exists(logo_jpg):
            return send_file(logo_jpg, mimetype="image/jpeg")
        abort(404)

    @app.route("/api/search")
    def api_search():
        """Buscador predictivo por matrícula o nombre completo."""
        q = request.args.get("q", "").strip().lower()
        if not q:
            return jsonify({"results": []})

        students = get_cached_students()
        matches = []
        for s in students:
            if q in s["matricula"].lower() or q in s["nombre"].lower():
                matches.append(s)
                if len(matches) >= 15:
                    break

        return jsonify({"results": matches})

    @app.route("/api/student/<matricula>")
    def api_student(matricula: str):
        """Verifica en tiempo real si el alumno está registrado en Microsoft 365."""
        matricula = matricula.strip()
        if not matricula:
            return jsonify({"success": False, "error": "Matrícula no proporcionada"}), 400

        try:
            graph = get_graph()
            info = verify_student_for_reset(
                identifier=matricula,
                graph=graph,
                domain=config.domain,
                excel_path=config.excel_path,
                sheet_name=config.sheet_name
            )
            return jsonify({"success": True, "data": info})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/student/<matricula>/photo")
    def api_student_photo(matricula: str):
        """Descarga y sirve la fotografía de perfil del alumno desde Microsoft Entra ID."""
        matricula = matricula.strip()
        try:
            graph = get_graph()
            upn = f"{matricula}@{config.domain}"
            photo_bytes = graph.get_user_photo(upn)
            if photo_bytes:
                return send_file(
                    io.BytesIO(photo_bytes),
                    mimetype="image/jpeg",
                    as_attachment=False,
                    download_name=f"{matricula}.jpg"
                )
            abort(404)
        except Exception:
            abort(404)

    @app.route("/api/reset-password", methods=["POST"])
    def api_reset_password():
        """
        Ejecuta el reseteo seguro de contraseña tras confirmación explícita del operador.
        Genera la ficha PDF con código QR y registra el evento en la bitácora protegida.
        """
        data = request.get_json() or {}
        matricula = data.get("matricula", "").strip()
        confirmed = data.get("confirmed", False)
        custom_password = data.get("custom_password")
        force_change = data.get("force_change", True)

        if not matricula:
            return jsonify({"success": False, "error": "Falta la matrícula del alumno."}), 400

        # Salvaguarda de confirmación obligatoria
        if not confirmed:
            return jsonify({
                "success": False,
                "error": "Confirmación de seguridad requerida: Debe confirmar que verificó la identidad del alumno."
            }), 400

        try:
            graph = get_graph()
            # 1. Verificar registro del alumno
            verified = verify_student_for_reset(
                identifier=matricula,
                graph=graph,
                domain=config.domain,
                excel_path=config.excel_path,
                sheet_name=config.sheet_name
            )
            if not verified.get("registered"):
                return jsonify({
                    "success": False,
                    "error": verified.get("error") or "El alumno no está registrado en Microsoft 365."
                }), 400

            # 2. Ejecutar reseteo
            result = execute_password_reset(
                identifier=matricula,
                graph=graph,
                domain=config.domain,
                secrets_dir=config.secrets_dir,
                reports_dir=config.reports_dir,
                custom_password=custom_password if custom_password else None,
                force_change=force_change,
                auto_confirm=True,
                excel_path=config.excel_path,
                sheet_name=config.sheet_name,
                verified_student=verified
            )

            if not result:
                return jsonify({"success": False, "error": "No se pudo restablecer la contraseña."}), 500

            pdf_filename = None
            pdf_url = None
            if result.get("pdf_path") and os.path.exists(result["pdf_path"]):
                pdf_filename = os.path.basename(result["pdf_path"])
                pdf_url = f"/api/pdf/{pdf_filename}"

            return jsonify({
                "success": True,
                "matricula": result["matricula"],
                "upn": result["upn"],
                "display_name": result["display_name"],
                "nombre_oficial": result.get("nombre_oficial", result["display_name"]),
                "password": result["password"],
                "pdf_filename": pdf_filename,
                "pdf_url": pdf_url,
                "nivel": result.get("nivel", "Estudiante"),
                "grado_semestre": result.get("grado_semestre", "Activo")
            })
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/pdf/<filename>")
    def api_download_pdf(filename: str):
        """Sirve el documento PDF de la ficha de acceso para previsualización e impresión."""
        # Sanitizar nombre de archivo para evitar path traversal
        clean_filename = os.path.basename(filename)
        secrets_file = os.path.join(config.secrets_dir, clean_filename)
        reports_file = os.path.join(config.reports_dir, clean_filename)

        target_file = None
        if os.path.exists(secrets_file):
            target_file = secrets_file
        elif os.path.exists(reports_file):
            target_file = reports_file

        if not target_file:
            abort(404)

        download = request.args.get("download", "0") == "1"
        return send_file(
            target_file,
            mimetype="application/pdf",
            as_attachment=download,
            download_name=clean_filename
        )

    @app.route("/api/history")
    def api_history():
        """Retorna los reseteos recientes guardados en la bitácora protegida de secrets/."""
        log_file = os.path.join(config.secrets_dir, "historial_reseteos_contrasenas.csv")
        if not os.path.exists(log_file):
            return jsonify({"history": []})

        history_rows = []
        try:
            with open(log_file, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    mat = row.get("matricula", "")
                    # Buscar si existe PDF correspondiente
                    pdf_filename = None
                    if os.path.exists(config.secrets_dir):
                        for fname in os.listdir(config.secrets_dir):
                            if fname.startswith(f"ficha_acceso_reset_{mat}_") and fname.endswith(".pdf"):
                                pdf_filename = fname
                                break
                    history_rows.append({
                        "matricula": mat,
                        "upn": row.get("upn", ""),
                        "display_name": row.get("display_name", "Alumno"),
                        "timestamp_utc": row.get("timestamp_utc", ""),
                        "reset_by": row.get("reset_by", "admin"),
                        "pdf_filename": pdf_filename,
                        "pdf_url": f"/api/pdf/{pdf_filename}" if pdf_filename else None
                    })
        except Exception as e:
            app.logger.error(f"Error al leer historial: {e}")

        # Retornar los más recientes primero
        history_rows.reverse()
        return jsonify({"history": history_rows[:30]})

    @app.route("/api/status")
    def api_status():
        """Retorna el estado de conexión del tenant y dominio institucional."""
        try:
            graph = get_graph()
            dom = graph.verify_domain(config.domain)
            return jsonify({
                "success": True,
                "domain": config.domain,
                "is_verified": dom.is_verified,
                "is_default": dom.is_default,
                "admin_upn": graph.admin_upn or "Conectado",
                "auth_type": dom.authentication_type
            })
        except Exception as e:
            return jsonify({
                "success": False,
                "domain": config.domain,
                "error": str(e)
            })

    return app


def start_gui(config_path: str = "config.json", host: str = "127.0.0.1", port: int = 5000, open_browser: bool = True):
    """Inicia el servidor local de la interfaz gráfica y abre el navegador automáticamente."""
    app = create_app(config_path)
    url = f"http://{host}:{port}"

    print("\n" + "=" * 76)
    print("🌐 PANEL DE CONTROL WEB — INSTITUTO JOSÉ VASCONCELOS")
    print("=" * 76)
    print(f"🚀 Servidor ejecutándose en: \033[1;32m{url}\033[0m")
    print("📌 Presiona \033[1mCtrl + C\033[0m en esta terminal para detener el servidor.")
    print("=" * 76 + "\n")

    if open_browser:
        def _open():
            import time
            time.sleep(1.2)
            try:
                webbrowser.open(url)
            except Exception:
                pass
        threading.Thread(target=_open, daemon=True).start()

    app.run(host=host, port=port, debug=False, threaded=True)
