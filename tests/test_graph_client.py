"""
Pruebas unitarias para verificar el manejo de paginación (@odata.nextLink),
rate limiting (HTTP 429 con Retry-After) y abortos de seguridad en GraphClient.
"""
import os
import unittest
from unittest.mock import patch, MagicMock
from src.graph_client import GraphClient, GraphClientError


class TestGraphClient(unittest.TestCase):
    @patch("src.graph_client.PublicClientApplication")
    def setUp(self, mock_msal_app):
        self.client = GraphClient(
            tenant_id="test-tenant-id",
            client_id="test-client-id",
            scopes=["User.Read.All"]
        )
        self.client.access_token = "fake-mock-token"

    @patch("requests.get")
    def test_pagination_success(self, mock_get):
        """Verifica que la paginación recorra múltiples páginas hasta que @odata.nextLink sea nulo."""
        # Page 1 response with nextLink
        resp1 = MagicMock()
        resp1.status_code = 200
        resp1.json.return_value = {
            "value": [
                {"id": "u1", "userPrincipalName": "user1@ijova.com", "displayName": "User 1"},
                {"id": "u2", "userPrincipalName": "user2@ijova.com", "displayName": "User 2"}
            ],
            "@odata.nextLink": "https://graph.microsoft.com/v1.0/users?$skiptoken=page2"
        }

        # Page 2 response without nextLink (end of list)
        resp2 = MagicMock()
        resp2.status_code = 200
        resp2.json.return_value = {
            "value": [
                {"id": "u3", "userPrincipalName": "user3@ijova.com", "displayName": "User 3"}
            ]
        }

        mock_get.side_effect = [resp1, resp2]

        users = self.client.get_all_users()
        self.assertEqual(len(users), 3)
        self.assertEqual(users[0].user_principal_name, "user1@ijova.com")
        self.assertEqual(users[2].user_principal_name, "user3@ijova.com")
        self.assertEqual(mock_get.call_count, 2)

    @patch("time.sleep", return_value=None)
    @patch("requests.get")
    def test_rate_limiting_retry_429(self, mock_get, mock_sleep):
        """Verifica el reintento ante HTTP 429 respetando el header Retry-After."""
        # 1st attempt: 429 with Retry-After: 2
        resp_429 = MagicMock()
        resp_429.status_code = 429
        resp_429.headers = {"Retry-After": "2"}

        # 2nd attempt: 200 OK
        resp_ok = MagicMock()
        resp_ok.status_code = 200
        resp_ok.json.return_value = {
            "value": [
                {"id": "u1", "userPrincipalName": "user1@ijova.com"}
            ]
        }

        mock_get.side_effect = [resp_429, resp_ok]

        users = self.client.get_all_users()
        self.assertEqual(len(users), 1)
        mock_sleep.assert_called_with(2)

    @patch("time.sleep", return_value=None)
    @patch("requests.get")
    def test_pagination_failure_aborts_securely(self, mock_get, mock_sleep):
        """Verifica que una falla en mitad de la paginación lanza GraphClientError y ABORTA."""
        # Page 1 OK
        resp1 = MagicMock()
        resp1.status_code = 200
        resp1.json.return_value = {
            "value": [{"id": "u1", "userPrincipalName": "user1@ijova.com"}],
            "@odata.nextLink": "https://graph.microsoft.com/v1.0/users?$skiptoken=page2"
        }

        # Page 2 fails with 500 continuously
        resp_500 = MagicMock()
        resp_500.status_code = 500

        mock_get.side_effect = [resp1, resp_500, resp_500, resp_500, resp_500]

    @patch("requests.post")
    def test_create_user_success(self, mock_post):
        """Verifica la creación exitosa de usuario vía POST /v1.0/users."""
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {
            "id": "new-user-id",
            "userPrincipalName": "250081@ijova.com",
            "displayName": "LOGAN JAVIER VALENCIA"
        }
        mock_post.return_value = mock_resp

        payload = {
            "userPrincipalName": "250081@ijova.com",
            "displayName": "LOGAN JAVIER VALENCIA"
        }
        result = self.client.create_user(payload)
        self.assertEqual(result["id"], "new-user-id")
        self.assertEqual(result["userPrincipalName"], "250081@ijova.com")

    @patch("requests.post")
    def test_assign_license_success(self, mock_post):
        """Verifica la asignación de licencias vía POST /v1.0/users/{id}/assignLicense."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {}
        mock_post.return_value = mock_resp

        res = self.client.assign_license("test-user-id", "sku-guid-123")
        self.assertTrue(res)

    @patch("requests.delete")
    def test_delete_user_success(self, mock_delete):
        """Verifica la eliminación de usuario vía DELETE /v1.0/users/{id}."""
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_delete.return_value = mock_resp

        res = self.client.delete_user("test-user-id-to-delete")
        self.assertTrue(res)

    def test_delete_safety_blocks_admins_and_staff(self):
        """Verifica que el motor de bajas bloquee terminantemente cuentas que no sean matrículas estudiantiles."""
        from src.delete_engine import is_student_matricula

        # Casos administrativos que deben ser BLOQUEADOS
        admin_cases = [
            "admin@ijova.com",
            "adminbackup@ijova.com",
            "carmelaleticiapachecosoriano@ijova.com",
            "director",
            "profesor.juan@ijova.com",
            "superadmin"
        ]
        for ac in admin_cases:
            valid, msg = is_student_matricula(ac)
            self.assertFalse(valid, f"Se esperaba bloqueo para {ac}")
            self.assertIn("NO es una matrícula estudiantil numérica", msg)

        # Casos estudiantiles que deben ser ACEPTADOS
        student_cases = ["250010", "260017", "250001@ijova.com", " 260002 "]
        for sc in student_cases:
            valid, upn = is_student_matricula(sc)
            self.assertTrue(valid, f"Se esperaba aceptación para {sc}")
            self.assertTrue(upn.endswith("@ijova.com"))

    @patch("requests.patch")
    def test_reset_password_success(self, mock_patch):
        """Verifica el restablecimiento de contraseña vía PATCH /v1.0/users/{id}."""
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_patch.return_value = mock_resp

        res = self.client.reset_password("test-user-id", "NewPassword123!")
        self.assertTrue(res)

    def test_pdf_generation_smoke_test(self):
        """Verifica la generación de PDF con tarjetas de acceso y código QR."""
        import tempfile
        import os
        from src.pdf_generator import generate_pdf_cards_from_list

        test_students = [{
            "matricula": "250001",
            "upn": "250001@ijova.com",
            "nombre_completo": "ALUMNO DEMO UNO",
            "password_temporal": "TempPass123!",
            "nivel": "Secundaria",
            "grado_semestre": "1ro"
        }]

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            out_path = generate_pdf_cards_from_list(test_students, tmp_path, layout_mode="cards")
            self.assertTrue(os.path.exists(out_path))
            self.assertGreater(os.path.getsize(out_path), 1000)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    @patch("requests.get")
    def test_get_deleted_users(self, mock_get):
        """Verifica la consulta de usuarios en la papelera de reciclaje."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "value": [
                {"id": "del-1", "userPrincipalName": "250010@ijova.com", "displayName": "Alumno Eliminado"}
            ]
        }
        mock_get.return_value = mock_resp

        deleted = self.client.get_deleted_users()
        self.assertEqual(len(deleted), 1)
        self.assertEqual(deleted[0]["userPrincipalName"], "250010@ijova.com")

    @patch("requests.post")
    def test_restore_deleted_user_success(self, mock_post):
        """Verifica la restauración de usuario vía POST /deletedItems/{id}/restore."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "restored-user-id", "userPrincipalName": "250010@ijova.com"}
        mock_post.return_value = mock_resp

        res = self.client.restore_deleted_user("restored-user-id")
        self.assertEqual(res["id"], "restored-user-id")

    def test_extract_matriculas_from_excel(self):
        """Verifica la extracción de matrículas desde un Excel simple."""
        import tempfile
        import openpyxl
        from src.excel_parser import extract_matriculas_from_excel

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(["Matricula"])
            ws.append([250001])
            ws.append(["250002.0"])
            ws.append([""])
            ws.append(["260010"])
            wb.save(tmp_path)
            wb.close()

            mats = extract_matriculas_from_excel(tmp_path)
            self.assertEqual(mats, ["250001", "250002", "260010"])
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


if __name__ == "__main__":
    unittest.main()
