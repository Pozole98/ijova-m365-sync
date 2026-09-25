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
import re
from typing import Optional, Dict, Any, List
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, abort

from src.config import load_config, AppConfig
from src.graph_client import GraphClient, GraphClientError
from src.reset_engine import verify_student_for_reset, execute_password_reset
from src.excel_parser import parse_excel_students
from src.validator import is_valid_matricula_format
from src.delete_engine import execute_student_deletion, is_student_matricula
from src.restore_engine import execute_student_restoration

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

    # =========================================================================
    # ESCUDO DE SEGURIDAD (LOOPBACK ENFORCEMENT, ANTI-CSRF, ANTI-DNS-REBINDING)
    # =========================================================================
    @app.before_request
    def security_shield():
        # 1. Filtro estricto de IP: Solo la máquina local (loopback) puede conectar
        client_ip = request.remote_addr
        if client_ip and client_ip not in ("127.0.0.1", "::1", "localhost", "testclient"):
            app.logger.warning(f"🛡️ Intento de acceso bloqueado desde IP no local: {client_ip}")
            abort(403)

        # 2. Mitigación de DNS Rebinding: El Host debe ser 127.0.0.1 o localhost
        host_hdr = (request.host or "").split(":")[0].lower()
        if host_hdr and host_hdr not in ("127.0.0.1", "localhost", "testclient"):
            app.logger.warning(f"🛡️ Host no autorizado bloqueado (Posible DNS Rebinding): {request.host}")
            abort(400)

        # 3. Mitigación de Cross-Site Request Forgery (CSRF) desde pestañas del navegador
        sec_fetch_site = request.headers.get("Sec-Fetch-Site")
        if sec_fetch_site in ("cross-site",):
            app.logger.warning(f"🛡️ Petición cross-site bloqueada (Sec-Fetch-Site: {sec_fetch_site})")
            abort(403)

        # Verificación de Origin en peticiones de escritura o AJAX
        origin = request.headers.get("Origin")
        if origin:
            parsed_origin = origin.split("://")[-1].split(":")[0].lower()
            if parsed_origin not in ("127.0.0.1", "localhost", "testclient"):
                app.logger.warning(f"🛡️ Petición cross-origin bloqueada con Origin no autorizado: {origin}")
                abort(403)

    @app.after_request
    def set_security_headers(response):
        """Inyecta cabeceras de seguridad HTTP en todas las respuestas."""
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' https://fonts.googleapis.com 'unsafe-inline'; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: blob:; "
            "connect-src 'self';"
        )
        return response

    # Cliente Graph singleton perezoso (lazy)
    _graph_lock = threading.Lock()
    _graph_instance: Optional[GraphClient] = None

    def get_graph() -> GraphClient:
        nonlocal _graph_instance
        with _graph_lock:
            if _graph_instance is None:
                full_scopes = list(dict.fromkeys(
                    config.graph_scopes + [
                        "User.ReadWrite.All",
                        "Domain.Read.All",
                        "LicenseAssignment.Read.All",
                        "Group.ReadWrite.All",
                        "TeamSettings.ReadWrite.All",
                        "TeamMember.ReadWrite.All",
                        "Team.ReadBasic.All"
                    ]
                ))
                client = GraphClient(config.tenant_id, config.client_id, full_scopes, client_secret=config.client_secret)
                client.authenticate_device_code()
                _graph_instance = client
            else:
                try:
                    _graph_instance.ensure_valid_token()
                except Exception:
                    pass
            return _graph_instance

    # Caché en memoria de alumnos del Excel escolar para búsqueda rápida
    _students_cache: Optional[List[Dict[str, Any]]] = None

    def get_cached_students() -> List[Dict[str, Any]]:
        nonlocal _students_cache
        if _students_cache is None:
            items = []
            try:
                from export_students_m365 import build_school_db
                school_db = build_school_db()
                for mat, d in sorted(school_db.items()):
                    estatus = (d.get("estatus") or "").strip()
                    if "egresado" in estatus.lower() or "baja" in estatus.lower():
                        continue
                    disp = d.get("display_name") or f"{d.get('paterno', '')} {d.get('materno', '')} {d.get('nombres', '')}".strip()
                    items.append({
                        "matricula": mat,
                        "nombre": disp,
                        "nivel": d.get("nivel") or "Estudiante",
                        "grado": d.get("grado") or "Activo",
                        "upn": f"{mat}@{config.domain}"
                    })
            except Exception as e:
                app.logger.warning(f"No se pudo cargar el listado de build_school_db: {e}")
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
                    except Exception as e2:
                        app.logger.warning(f"Tampoco se pudo cargar del Excel base: {e2}")
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
        if not is_valid_matricula_format(matricula):
            abort(404)
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

            resp_dict = {
                "success": True,
                "matricula": result["matricula"],
                "upn": result["upn"],
                "display_name": result["display_name"],
                "nombre_oficial": result.get("nombre_oficial", result["display_name"]),
                "password": result["password"],
                "new_password": result["password"],
                "force_change": force_change,
                "pdf_filename": pdf_filename,
                "pdf_url": pdf_url,
                "nivel": result.get("nivel", "Estudiante"),
                "grado_semestre": result.get("grado_semestre", "Activo")
            }
            # Enviar también el objeto anidado 'data' para compatibilidad total con el frontend
            resp_dict["data"] = dict(resp_dict)
            return jsonify(resp_dict)
        except ValueError as ve:
            return jsonify({"success": False, "error": str(ve)}), 400
        except GraphClientError as ge:
            return jsonify({"success": False, "error": str(ge)}), 400
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/pdf/<filename>")
    def api_download_pdf(filename: str):
        """Sirve el documento PDF de la ficha de acceso para previsualización e impresión."""
        clean_filename = os.path.basename(filename).strip()

        # Validación estricta: Solo archivos .pdf con caracteres alfanuméricos seguros
        if not clean_filename.lower().endswith(".pdf") or not re.match(r'^[a-zA-Z0-9_\-]+\.pdf$', clean_filename):
            abort(404)

        # Resolver rutas absolutas y verificar que el archivo resida en secrets_dir o reports_dir
        secrets_dir_abs = os.path.abspath(config.secrets_dir)
        reports_dir_abs = os.path.abspath(config.reports_dir)

        secrets_file = os.path.abspath(os.path.join(secrets_dir_abs, clean_filename))
        reports_file = os.path.abspath(os.path.join(reports_dir_abs, clean_filename))

        target_file = None
        if secrets_file.startswith(secrets_dir_abs) and os.path.exists(secrets_file):
            target_file = secrets_file
        elif reports_file.startswith(reports_dir_abs) and os.path.exists(reports_file):
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

    # =========================================================================
    # ENDPOINTS DE BAJAS Y PAPELERA DE RECICLAJE
    # =========================================================================
    @app.route("/api/student/delete", methods=["POST"])
    def api_student_delete():
        """Da de baja una cuenta de alumno enviándola a la Papelera de Entra ID."""
        data = request.get_json() or {}
        matricula = data.get("matricula", "").strip()
        confirmation = data.get("confirmation", "").strip()

        if not matricula:
            return jsonify({"success": False, "error": "Falta la matrícula del alumno."}), 400

        # Salvaguarda: verificación de doble factor tecleando la matrícula
        if confirmation != matricula:
            return jsonify({
                "success": False,
                "error": f"Confirmación de seguridad requerida: Debes ingresar exactamente la matrícula '{matricula}' para confirmar la baja."
            }), 400

        is_valid, msg = is_student_matricula(matricula)
        if not is_valid:
            return jsonify({"success": False, "error": msg}), 400

        try:
            graph = get_graph()
            res = execute_student_deletion(
                identifiers=[matricula],
                graph=graph,
                excel_path=config.excel_path,
                sheet_name=config.sheet_name,
                reports_dir=config.reports_dir,
                backups_dir=config.backups_dir,
                auto_confirm=True
            )
            deleted_count = res.get("deleted_count", 0)
            if deleted_count > 0:
                return jsonify({
                    "success": True,
                    "matricula": matricula,
                    "message": f"El alumno {matricula} fue dado de baja y su cuenta enviada a la Papelera de Reciclaje (30 días de retención recuperable)."
                })
            else:
                errors = res.get("errors", [])
                err_msg = errors[0].get("error") if errors else "No se pudo eliminar el usuario."
                return jsonify({"success": False, "error": err_msg}), 400
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/recycle-bin")
    def api_recycle_bin():
        """Lista las cuentas de alumnos que se encuentran en la Papelera de Reciclaje (< 30 días)."""
        try:
            graph = get_graph()
            deleted = graph.get_deleted_users()
            student_users = []
            from src.validator import is_valid_matricula_format
            for u in deleted:
                upn = (u.get("userPrincipalName") or "").strip().lower()
                prefix = upn.split("@")[0] if "@" in upn else ""
                nick = (u.get("mailNickname") or "").strip()
                mat = prefix if is_valid_matricula_format(prefix) else (nick if is_valid_matricula_format(nick) else None)
                if mat:
                    student_users.append({
                        "id": u.get("id"),
                        "matricula": mat,
                        "upn": upn,
                        "display_name": u.get("displayName", "Alumno"),
                        "deleted_datetime": u.get("deletedDateTime", "Recientemente")
                    })
            return jsonify({"success": True, "users": student_users})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/recycle-bin/restore", methods=["POST"])
    def api_recycle_bin_restore():
        """Restaura una cuenta de alumno desde la Papelera de Reciclaje reactivando su buzón y OneDrive."""
        data = request.get_json() or {}
        matricula = data.get("matricula", "").strip()
        if not matricula:
            return jsonify({"success": False, "error": "Falta la matrícula a restaurar."}), 400

        try:
            graph = get_graph()
            result = execute_student_restoration(
                identifier=matricula,
                graph=graph,
                domain=config.domain,
                excel_path=config.excel_path,
                sheet_name=config.sheet_name
            )
            if result:
                return jsonify({
                    "success": True,
                    "matricula": matricula,
                    "display_name": result.get("display_name"),
                    "message": f"Cuenta de {result.get('display_name')} ({matricula}) restaurada con éxito desde la Papelera de Reciclaje."
                })
            else:
                return jsonify({"success": False, "error": "No se encontró el alumno en la papelera o ya fue purgado."}), 400
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    # =========================================================================
    # ENDPOINTS DE AUDITORÍA Y GALERÍA DE FOTOS
    # =========================================================================
    @app.route("/api/photos/stats")
    def api_photos_stats():
        """Estadísticas ejecutivas del estado de fotografías de perfil de alumnos."""
        photos_dir = os.path.join(config.reports_dir, "fotos_perfil")
        has_dir = os.path.exists(photos_dir)
        photo_files = os.listdir(photos_dir) if has_dir else []
        photo_count = len([f for f in photo_files if f.lower().endswith(('.jpg', '.jpeg', '.png'))])

        students = get_cached_students()
        total_students = len(students)
        with_photo = photo_count
        without_photo = max(0, total_students - with_photo)
        pct = round((with_photo / total_students * 100), 1) if total_students > 0 else 0

        return jsonify({
            "success": True,
            "total_students": total_students,
            "with_photo": with_photo,
            "without_photo": without_photo,
            "compliance_pct": pct,
            "has_directory": has_dir
        })

    @app.route("/api/photos/gallery")
    def api_photos_gallery():
        """Retorna la lista de alumnos para la galería con filtrado dinámico."""
        filter_type = request.args.get("filter", "all")  # all, with, without
        level_filter = request.args.get("level", "all").lower()

        students = get_cached_students()
        photos_dir = os.path.join(config.reports_dir, "fotos_perfil")
        existing_photos = set(os.listdir(photos_dir)) if os.path.exists(photos_dir) else set()

        cards = []
        for s in students:
            mat = s["matricula"]
            has_photo = any(f.startswith(f"{mat}_") for f in existing_photos)

            if filter_type == "with" and not has_photo:
                continue
            if filter_type == "without" and has_photo:
                continue
            if level_filter != "all" and level_filter not in s["nivel"].lower():
                continue

            cards.append({
                "matricula": mat,
                "nombre": s["nombre"],
                "nivel": s["nivel"],
                "grado": s["grado"],
                "upn": s["upn"],
                "has_photo": has_photo,
                "photo_url": f"/api/student/{mat}/photo" if has_photo else None
            })

        return jsonify({"success": True, "students": cards[:80]})

    _scan_state = {"running": False, "msg": "Inactivo"}

    @app.route("/api/photos/scan", methods=["POST"])
    def api_photos_scan():
        """Inicia el escaneo y descarga masiva de fotografías en segundo plano."""
        nonlocal _scan_state
        if _scan_state["running"]:
            return jsonify({"success": False, "error": "Ya hay una auditoría de fotos en ejecución."}), 400

        def _run_scan():
            nonlocal _scan_state
            _scan_state["running"] = True
            _scan_state["msg"] = "Descargando fotos de Microsoft 365..."
            try:
                graph = get_graph()
                from src.photo_auditor import audit_profile_photos
                audit_profile_photos(graph=graph, config=config, max_workers=8)
                _scan_state["msg"] = "Auditoría completada exitosamente."
            except Exception as e:
                _scan_state["msg"] = f"Error: {e}"
            finally:
                _scan_state["running"] = False

        threading.Thread(target=_run_scan, daemon=True).start()
        return jsonify({"success": True, "message": "Auditoría de fotos iniciada en segundo plano."})

    @app.route("/api/photos/scan/status")
    def api_photos_scan_status():
        return jsonify(_scan_state)

    # =========================================================================
    # ENDPOINTS REST: MÓDULO DE EQUIPOS Y CLASES DE MICROSOFT TEAMS
    # =========================================================================
    _teams_cache: Optional[Dict[str, Any]] = None

    @app.route("/api/teams")
    def api_teams_list():
        """Retorna la lista completa auditada de equipos con métricas consolidadas."""
        nonlocal _teams_cache
        force_refresh = request.args.get("refresh", "false").lower() == "true"
        if _teams_cache is not None and not force_refresh:
            return jsonify({"success": True, "data": _teams_cache})

        try:
            from src.teams_engine import audit_all_teams
            graph = get_graph()
            _teams_cache = audit_all_teams(graph)
            return jsonify({"success": True, "data": _teams_cache})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/teams/teachers")
    def api_teams_teachers():
        """Retorna la lista de docentes para el selector de titular."""
        try:
            graph = get_graph()
            raw_teachers = graph.get_all_teachers()
            teachers = []
            for t in raw_teachers:
                d_name = t.get("display_name") or t.get("displayName") or t.get("name") or ""
                upn = t.get("user_principal_name") or t.get("userPrincipalName") or t.get("mail") or ""
                teachers.append({
                    "id": t.get("id"),
                    "display_name": d_name,
                    "displayName": d_name,
                    "name": d_name,
                    "user_principal_name": upn,
                    "userPrincipalName": upn,
                    "mail": t.get("mail") or upn
                })
            return jsonify({"success": True, "teachers": teachers})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/teams/students-by-grade")
    def api_teams_students_by_grade():
        """Devuelve los alumnos a matricular según el nivel y grado seleccionados."""
        nivel = request.args.get("nivel", "")
        grado = request.args.get("grado", "")
        if not nivel or not grado:
            return jsonify({"success": False, "error": "Parámetros nivel y grado requeridos"}), 400

        try:
            from export_students_m365 import build_school_db
            from src.teams_engine import get_students_for_grade
            school_db = build_school_db()
            matched = get_students_for_grade(school_db, nivel, grado)
            return jsonify({
                "success": True,
                "nivel": nivel,
                "grado": grado,
                "count": len(matched),
                "students": matched
            })
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/teams/create", methods=["POST"])
    def api_teams_create_class():
        """Crea una nueva clase educativa en Teams con matriculación automática de alumnos."""
        nonlocal _teams_cache
        data = request.get_json() or {}
        subject = data.get("subject_name", "").strip()
        nivel = data.get("nivel", "").strip()
        grado = data.get("grado", "").strip()
        teacher_id = data.get("teacher_id", "").strip()
        desc = data.get("description", "").strip()

        if not subject or not nivel or not grado or not teacher_id:
            return jsonify({"success": False, "error": "Materia, nivel, grado y profesor son obligatorios."}), 400

        try:
            from export_students_m365 import build_school_db
            from src.teams_engine import create_class_assisted
            graph = get_graph()
            school_db = build_school_db()
            res = create_class_assisted(
                graph=graph,
                subject_name=subject,
                nivel=nivel,
                grado=grado,
                teacher_user_id=teacher_id,
                school_db=school_db,
                custom_description=desc or None
            )
            # Invalidate teams cache to reflect newly created team on next audit
            _teams_cache = None
            return jsonify({"success": True, "result": res})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/teams/<team_id>/rename", methods=["PATCH"])
    def api_teams_rename(team_id: str):
        """Renombra un equipo existente en Teams."""
        nonlocal _teams_cache
        data = request.get_json() or {}
        new_name = data.get("new_name", "").strip()
        new_desc = data.get("new_description")
        if not new_name:
            return jsonify({"success": False, "error": "El nuevo nombre es obligatorio."}), 400

        try:
            graph = get_graph()
            graph.update_team_info(team_id, new_name, new_desc)
            # Update cache locally if present
            if _teams_cache and "teams" in _teams_cache:
                for t in _teams_cache["teams"]:
                    if t["id"] == team_id:
                        t["name"] = new_name
                        if new_desc is not None:
                            t["description"] = new_desc
            return jsonify({"success": True, "message": f"Equipo renombrado a '{new_name}' exitosamente."})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/teams/<team_id>/archive", methods=["POST"])
    def api_teams_archive(team_id: str):
        """Pone un equipo en modo solo lectura (archivado)."""
        nonlocal _teams_cache
        try:
            graph = get_graph()
            graph.archive_team(team_id)
            if _teams_cache and "teams" in _teams_cache:
                for t in _teams_cache["teams"]:
                    if t["id"] == team_id:
                        t["is_archived"] = True
            return jsonify({"success": True, "message": "Equipo archivado exitosamente."})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/teams/<team_id>/unarchive", methods=["POST"])
    def api_teams_unarchive(team_id: str):
        """Desarchiva un equipo en Teams."""
        nonlocal _teams_cache
        try:
            graph = get_graph()
            graph.unarchive_team(team_id)
            if _teams_cache and "teams" in _teams_cache:
                for t in _teams_cache["teams"]:
                    if t["id"] == team_id:
                        t["is_archived"] = False
            return jsonify({"success": True, "message": "Equipo desarchivado exitosamente."})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/teams/<team_id>/members")
    def api_teams_members(team_id: str):
        """Obtiene la lista detallada de docentes y alumnos de un equipo."""
        try:
            from src.teams_engine import get_team_members_detailed
            graph = get_graph()
            details = get_team_members_detailed(graph, team_id)
            return jsonify({"success": True, "data": details})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/teams/export-excel")
    def api_teams_export_excel():
        """Genera y descarga el archivo Excel oficial de auditoría de Teams."""
        try:
            from src.teams_engine import audit_all_teams, export_teams_audit_excel
            graph = get_graph()
            audit_data = audit_all_teams(graph)
            os.makedirs(config.reports_dir, exist_ok=True)
            out_file = os.path.abspath(os.path.join(config.reports_dir, f"Auditoria_Teams_Clases_IJOVA_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"))
            export_teams_audit_excel(audit_data, out_file)
            return send_file(
                out_file,
                as_attachment=True,
                download_name=os.path.basename(out_file),
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/teams/<team_id>/assignments")
    def api_team_assignments(team_id: str):
        """Retorna las tareas escolares y estadísticas de entrega de una clase en Teams."""
        try:
            from src.teams_engine import audit_class_assignments
            graph = get_graph()
            data = audit_class_assignments(graph, team_id, include_submissions=True)
            return jsonify({"success": True, "data": data})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/teams/assignments/export")
    def api_teams_assignments_export():
        """Genera y descarga el libro Excel oficial de auditoría de tareas para dirección."""
        try:
            from src.teams_engine import audit_all_assignments, export_assignments_report_excel
            cycle = request.args.get("cycle", "2026-2027")
            graph = get_graph()
            data = audit_all_assignments(graph, cycle_filter=cycle, include_submissions=True)
            os.makedirs(config.reports_dir, exist_ok=True)
            out_file = os.path.abspath(os.path.join(
                config.reports_dir,
                f"Reporte_Cumplimiento_Tareas_Teams_IJOVA_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            ))
            export_assignments_report_excel(data, out_file)
            return send_file(
                out_file,
                as_attachment=True,
                download_name=os.path.basename(out_file),
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/teams/assignments/export-pdf")
    def api_teams_assignments_export_pdf():
        """Genera y descarga el informe institucional oficial en PDF de auditoría de tareas para dirección."""
        try:
            from src.teams_engine import audit_all_assignments, export_assignments_report_pdf
            cycle = request.args.get("cycle", "2026-2027")
            graph = get_graph()
            data = audit_all_assignments(graph, cycle_filter=cycle, include_submissions=True)
            os.makedirs(config.reports_dir, exist_ok=True)
            out_file = os.path.abspath(os.path.join(
                config.reports_dir,
                f"Informe_Oficial_Tareas_Teams_IJOVA_{cycle}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            ))
            export_assignments_report_pdf(data, out_file)
            return send_file(
                out_file,
                as_attachment=True,
                download_name=os.path.basename(out_file),
                mimetype="application/pdf"
            )
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/licenses/status", methods=["GET"])
    def api_licenses_status():
        """Retorna el estado de salud predictivo de las licencias M365."""
        try:
            from src.status_engine import get_licenses_health_summary
            graph = get_graph()
            summary = get_licenses_health_summary(graph)
            return jsonify(summary)
        except Exception as e:
            return jsonify({
                "status": "error",
                "error": str(e),
                "level": "warning",
                "badge_color": "warning",
                "student_available": 0,
                "message": "Error al consultar licencias."
            }), 500

    @app.route("/api/students/search", methods=["GET"])
    def api_students_search():
        """Búsqueda rápida unificada para el Omnibar (Ctrl+K) por matrícula, nombre o correo."""
        q = request.args.get("q", "").strip()
        if not q or len(q) < 2:
            return jsonify({"success": True, "results": [], "count": 0})

        try:
            from export_students_m365 import build_school_db
            school_db = build_school_db()
            graph = get_graph()
            all_users = graph.get_all_users()
            upn_map = {u.user_principal_name.lower(): u for u in all_users}

            results = []
            q_lower = q.lower()
            q_clean = q.replace(".", "").strip()

            for mat, s in school_db.items():
                s_name = s.get("display_name", "")
                s_mat = str(mat)
                s_upn = s.get("upn") or f"{s_mat}@{config.domain}"

                if q_clean in s_mat or q_lower in s_name.lower() or q_lower in s_upn.lower():
                    entra_user = upn_map.get(s_upn.lower())
                    account_enabled = entra_user.account_enabled if entra_user else None
                    u_id = entra_user.id if entra_user else None

                    photo_path = os.path.join(config.data_dir, "fotos_perfil", f"{s_mat}.jpg")
                    photo_url = f"/api/photos/thumbnail/{s_mat}" if os.path.exists(photo_path) else None

                    results.append({
                        "matricula": s_mat,
                        "display_name": s_name,
                        "name": s_name,
                        "upn": s_upn,
                        "user_id": u_id,
                        "nivel": s.get("nivel", "General"),
                        "grado": s.get("grado", "General"),
                        "account_enabled": account_enabled,
                        "in_entra": entra_user is not None,
                        "photo_url": photo_url
                    })

                if len(results) >= 15:
                    break

            return jsonify({"success": True, "results": results, "count": len(results)})
        except Exception as e:
            return jsonify({"success": False, "error": str(e), "results": []}), 500

    @app.route("/api/teams/<team_id>/roster/audit", methods=["GET"])
    def api_teams_roster_audit(team_id: str):
        """Audita el roster de una clase educativa contra la base de datos escolar."""
        nivel = request.args.get("nivel")
        grado = request.args.get("grado")
        try:
            from export_students_m365 import build_school_db
            from src.teams_engine import audit_class_roster
            graph = get_graph()
            school_db = build_school_db()
            audit_res = audit_class_roster(
                graph=graph,
                team_id=team_id,
                nivel=nivel,
                grado=grado,
                school_db=school_db
            )
            return jsonify({"success": True, "roster": audit_res})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/teams/<team_id>/roster/sync", methods=["POST"])
    def api_teams_roster_sync(team_id: str):
        """Ejecuta la sincronización/regularización de miembros de una clase en Teams."""
        data = request.get_json() or {}
        action = data.get("action", "custom")
        if action == "add":
            add_missing = True
            remove_unexpected = False
        elif action == "remove":
            add_missing = False
            remove_unexpected = True
        elif action == "both":
            add_missing = True
            remove_unexpected = True
        else:
            add_missing = data.get("add_missing", True)
            remove_unexpected = data.get("remove_unexpected", False)

        missing_user_ids = data.get("missing_user_ids")
        remove_user_ids = data.get("remove_user_ids")
        nivel = data.get("nivel")
        grado = data.get("grado")
        audit_info = data.get("audit_info")

        try:
            from export_students_m365 import build_school_db
            from src.teams_engine import audit_class_roster, sync_class_roster
            graph = get_graph()
            school_db = build_school_db()

            if not audit_info:
                audit_info = audit_class_roster(graph, team_id, nivel, grado, school_db)

            res = sync_class_roster(
                graph=graph,
                team_id=team_id,
                add_missing=add_missing,
                remove_unexpected=remove_unexpected,
                missing_user_ids=missing_user_ids,
                remove_user_ids=remove_user_ids,
                audit_info=audit_info
            )
            nonlocal _teams_cache
            _teams_cache = None
            return jsonify({"success": True, "result": res})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/teams/roster/export-excel", methods=["GET"])
    def api_teams_roster_export_excel():
        """Genera y descarga el libro Excel de auditoría de roster de clases."""
        cycle = request.args.get("cycle", "2026-2027")
        try:
            from src.teams_engine import audit_all_rosters, export_roster_audit_excel
            graph = get_graph()
            roster_data = audit_all_rosters(graph, cycle_filter=cycle)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"Auditoria_Roster_Teams_{ts}.xlsx"
            out_path = os.path.join(config.reports_dir, filename)
            export_roster_audit_excel(roster_data, out_path)
            return send_file(out_path, as_attachment=True, download_name=filename)
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/teams/roster/export-pdf", methods=["GET"])
    def api_teams_roster_export_pdf():
        """Genera y descarga el informe oficial en PDF para dirección de auditoría de roster."""
        cycle = request.args.get("cycle", "2026-2027")
        try:
            from src.teams_engine import audit_all_rosters, export_roster_report_pdf
            graph = get_graph()
            roster_data = audit_all_rosters(graph, cycle_filter=cycle)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"Informe_Roster_Teams_{ts}.pdf"
            out_path = os.path.join(config.reports_dir, filename)
            export_roster_report_pdf(roster_data, out_path)
            return send_file(out_path, as_attachment=True, download_name=filename)
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    return app


def start_gui(config_path: str = "config.json", host: str = "127.0.0.1", port: int = 5055, open_browser: bool = True):
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
