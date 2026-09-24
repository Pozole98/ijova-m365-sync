"""
Pruebas unitarias para la verificación de alumnos antes de restablecer contraseñas
y para los endpoints de la Interfaz Gráfica Web Local (GUI).
"""
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.graph_client import GraphClient
from src.reset_engine import verify_student_for_reset, execute_password_reset
from src.gui.app import create_app


class TestResetVerificationAndGUI(unittest.TestCase):

    @patch("src.graph_client.PublicClientApplication")
    def setUp(self, mock_msal_app):
        self.client = GraphClient(
            tenant_id="mock-tenant-id",
            client_id="mock-client-id",
            scopes=["User.Read.All"]
        )
        self.client.access_token = "mock-token"
        self.client.admin_upn = "admin@ijova.com"

    @patch.object(GraphClient, "get_user_photo_metadata", return_value=None)
    @patch.object(GraphClient, "get_user_by_upn")
    def test_verify_student_registered(self, mock_get_user, mock_photo):
        """Verifica que un alumno registrado en Microsoft 365 sea identificado correctamente."""
        mock_get_user.return_value = {
            "id": "user-123",
            "displayName": "ALUMNO REGISTRADO PRUEBA",
            "userPrincipalName": "250081@ijova.com",
            "accountEnabled": True
        }

        info = verify_student_for_reset(
            identifier="250081",
            graph=self.client,
            domain="ijova.com"
        )

        self.assertTrue(info["registered"])
        self.assertEqual(info["matricula"], "250081")
        self.assertEqual(info["upn"], "250081@ijova.com")
        self.assertEqual(info["display_name"], "ALUMNO REGISTRADO PRUEBA")
        self.assertTrue(info["account_enabled"])
        self.assertIsNone(info["error"])

    @patch.object(GraphClient, "get_user_photo_metadata", return_value=None)
    @patch.object(GraphClient, "get_user_by_upn")
    def test_verify_student_not_registered(self, mock_get_user, mock_photo):
        """Verifica que un alumno no existente en Microsoft 365 retorne registered=False."""
        mock_get_user.return_value = None

        info = verify_student_for_reset(
            identifier="259999",
            graph=self.client,
            domain="ijova.com"
        )

        self.assertFalse(info["registered"])
        self.assertIn("no está registrado", info["error"])

    def test_verify_student_invalid_matricula(self):
        """Verifica que un identificador no estudiantil sea bloqueado por seguridad."""
        info = verify_student_for_reset(
            identifier="admin_director",
            graph=self.client,
            domain="ijova.com"
        )

        self.assertFalse(info["registered"])
        self.assertIn("BLOQUEO DE SEGURIDAD", info["error"])

    @patch("builtins.input", return_value="n")
    @patch.object(GraphClient, "get_user_photo_metadata", return_value=None)
    @patch.object(GraphClient, "reset_password")
    @patch.object(GraphClient, "get_user_by_upn")
    def test_execute_password_reset_cancelled_by_user(self, mock_get_user, mock_reset, mock_photo, mock_input):
        """Verifica que si el operador NO confirma la identidad del alumno, no se cambie nada."""
        mock_get_user.return_value = {
            "id": "user-123",
            "displayName": "ALUMNO A CANCELAR",
            "userPrincipalName": "250081@ijova.com",
            "accountEnabled": True
        }

        with tempfile.TemporaryDirectory() as tmp_sec, tempfile.TemporaryDirectory() as tmp_rep:
            res = execute_password_reset(
                identifier="250081",
                graph=self.client,
                domain="ijova.com",
                secrets_dir=tmp_sec,
                reports_dir=tmp_rep,
                auto_confirm=False  # Requiere confirmación interactiva
            )

            # Debe retornar None y no llamar a reset_password en Graph
            self.assertIsNone(res)
            mock_reset.assert_not_called()

    @patch.object(GraphClient, "verify_domain")
    def test_gui_index_and_status_endpoints(self, mock_verify_domain):
        """Verifica que la app web de Flask responda en la ruta principal y API de status."""
        from src.models import DomainStatus
        mock_verify_domain.return_value = DomainStatus(
            domain_name="ijova.com",
            is_verified=True,
            is_default=True,
            authentication_type="Managed"
        )

        app = create_app()
        client = app.test_client()

        # Probar página de inicio
        resp = client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"IJOVA", resp.data)
        self.assertIn(b"Restablecimiento Seguro de Contrase", resp.data)

        # Probar endpoint de búsqueda
        resp_search = client.get("/api/search?q=250")
        self.assertEqual(resp_search.status_code, 200)
        json_data = resp_search.get_json()
        self.assertIn("results", json_data)

    def test_gui_reset_password_requires_confirmation(self):
        """Verifica que la API /api/reset-password rechace peticiones sin confirmación explícita."""
        app = create_app()
        client = app.test_client()

        payload = {
            "matricula": "250081",
            "confirmed": False  # Sin confirmación
        }
        resp = client.post("/api/reset-password", json=payload)
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data["success"])
        self.assertIn("Confirmación de seguridad requerida", data["error"])

    def test_gui_student_delete_requires_exact_matricula(self):
        """Verifica que /api/student/delete exija teclear exactamente la matrícula del alumno."""
        app = create_app()
        client = app.test_client()

        # Confirmación que no coincide
        payload_mismatch = {
            "matricula": "250081",
            "confirmation": "123456"
        }
        resp = client.post("/api/student/delete", json=payload_mismatch)
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data["success"])
        self.assertIn("Debes ingresar exactamente la matrícula", data["error"])

    def test_gui_recycle_bin_restore_validation(self):
        """Verifica que /api/recycle-bin/restore valide los parámetros de entrada."""
        app = create_app()
        client = app.test_client()

        # Sin matrícula
        resp = client.post("/api/recycle-bin/restore", json={})
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data["success"])
        self.assertIn("Falta la matrícula", data["error"])

    def test_gui_photos_stats_and_gallery(self):
        """Verifica que los endpoints de fotos entreguen estadísticas y estructura de galería."""
        app = create_app()
        client = app.test_client()

        resp_stats = client.get("/api/photos/stats")
        self.assertEqual(resp_stats.status_code, 200)
        stats_data = resp_stats.get_json()
        self.assertTrue(stats_data["success"])
        self.assertIn("total_students", stats_data)
        self.assertIn("compliance_pct", stats_data)

        resp_gallery = client.get("/api/photos/gallery?filter=all")
        self.assertEqual(resp_gallery.status_code, 200)
        gallery_data = resp_gallery.get_json()
        self.assertTrue(gallery_data["success"])
        self.assertIn("students", gallery_data)

    def test_gui_security_ip_whitelist(self):
        """Verifica que conexiones desde IPs externas no-loopback sean bloqueadas con 403 Forbidden."""
        app = create_app()
        client = app.test_client()

        # Conexión externa simulada (LAN IP)
        resp_ext = client.get("/", environ_base={"REMOTE_ADDR": "192.168.1.50"})
        self.assertEqual(resp_ext.status_code, 403)

        # Conexión local autorizada (127.0.0.1)
        resp_local = client.get("/", environ_base={"REMOTE_ADDR": "127.0.0.1"})
        self.assertEqual(resp_local.status_code, 200)

    def test_gui_security_dns_rebinding_protection(self):
        """Verifica que peticiones con encabezados Host no autorizados (DNS Rebinding) sean rechazadas con 400."""
        app = create_app()
        client = app.test_client()

        # Host malicioso
        resp_evil = client.get("/", headers={"Host": "attacker-dns-rebind.com:5000"})
        self.assertEqual(resp_evil.status_code, 400)

        # Host legítimo
        resp_good = client.get("/", headers={"Host": "127.0.0.1:5000"})
        self.assertEqual(resp_good.status_code, 200)

    def test_gui_security_cross_origin_and_csrf_protection(self):
        """Verifica que peticiones cross-site (Sec-Fetch-Site o Origin externo) sean bloqueadas con 403."""
        app = create_app()
        client = app.test_client()

        # Petición cross-site de navegador
        resp_cross_site = client.get("/", headers={"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(resp_cross_site.status_code, 403)

        # Petición con Origin externo malicioso
        resp_evil_origin = client.post(
            "/api/reset-password",
            headers={"Origin": "https://malicious-website.com"},
            json={"matricula": "250081"}
        )
        self.assertEqual(resp_evil_origin.status_code, 403)

    def test_gui_security_pdf_download_protection(self):
        """Verifica que /api/pdf/<filename> bloquee estrictamente archivos no-PDF y path traversal."""
        app = create_app()
        client = app.test_client()

        # Intento de leer token_cache.bin
        resp_token = client.get("/api/pdf/token_cache.bin")
        self.assertEqual(resp_token.status_code, 404)

        # Intento de leer CSV de historial o contraseñas
        resp_csv = client.get("/api/pdf/historial_reseteos_contrasenas.csv")
        self.assertEqual(resp_csv.status_code, 404)

        # Intento de path traversal hacia /etc/passwd
        resp_traversal = client.get("/api/pdf/..%2F..%2Fetc%2Fpasswd")
        self.assertEqual(resp_traversal.status_code, 404)

    def test_gui_security_headers_present(self):
        """Verifica que las cabeceras HTTP de seguridad (CSP, X-Frame-Options, nosniff) se inyecten."""
        app = create_app()
        client = app.test_client()

        resp = client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(resp.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertIn("default-src 'self'", resp.headers.get("Content-Security-Policy", ""))

    def test_gui_cli_catalog_rendered(self):
        """Verifica que la pestaña de Comandos CLI se renderice en el HTML con sus comandos clave."""
        app = create_app()
        client = app.test_client()

        resp = client.get("/")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn("Terminal & Guía CLI", html)
        self.assertIn("python3 main.py apply", html)
        self.assertIn("python3 main.py dry-run", html)
        self.assertIn("python3 main.py reset --all", html)
        self.assertIn("Bajas de Alumnos", html)
        self.assertIn("Papelera & Restauración", html)

    @patch("src.gui.app.execute_password_reset")
    @patch("src.gui.app.verify_student_for_reset")
    def test_gui_reset_password_with_custom_password(self, mock_verify, mock_execute):
        """Verifica que /api/reset-password procese contraseñas específicas y retorne la estructura con data."""
        mock_verify.return_value = {
            "registered": True,
            "matricula": "250081",
            "upn": "250081@ijova.com",
            "display_name": "ALUMNO PRUEBA"
        }
        mock_execute.return_value = {
            "matricula": "250081",
            "upn": "250081@ijova.com",
            "display_name": "ALUMNO PRUEBA",
            "nombre_oficial": "ALUMNO PRUEBA",
            "password": "MiClaveEspecifica2026!",
            "pdf_path": None,
            "nivel": "Secundaria",
            "grado_semestre": "1° Secundaria"
        }

        app = create_app()
        client = app.test_client()

        payload = {
            "matricula": "250081",
            "confirmed": True,
            "password_mode": "custom",
            "custom_password": "MiClaveEspecifica2026!",
            "force_change": False
        }
        resp = client.post("/api/reset-password", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertIn("data", data)
        self.assertEqual(data["data"]["password"], "MiClaveEspecifica2026!")
        self.assertEqual(data["data"]["new_password"], "MiClaveEspecifica2026!")
        self.assertFalse(data["force_change"])

    @patch("src.gui.app.execute_password_reset")
    @patch("src.gui.app.verify_student_for_reset")
    def test_gui_reset_password_handles_validation_error(self, mock_verify, mock_execute):
        """Verifica que /api/reset-password propague los errores de complejidad o directivas al frontend."""
        mock_verify.return_value = {"registered": True, "matricula": "250081"}
        mock_execute.side_effect = ValueError("Contraseña no válida: La contraseña debe tener al menos 8 caracteres.")

        app = create_app()
        client = app.test_client()

        payload = {
            "matricula": "250081",
            "confirmed": True,
            "password_mode": "custom",
            "custom_password": "123",
            "force_change": False
        }
        resp = client.post("/api/reset-password", json=payload)
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data["success"])
        self.assertIn("Contraseña no válida", data["error"])


if __name__ == "__main__":
    unittest.main()
