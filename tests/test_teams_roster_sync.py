"""
Pruebas unitarias para la Fase 1: Auditoria y Sincronizacion de Roster en Teams,
Monitor de Licencias y Generacion de Informes Oficiales en PDF y Excel.
"""
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.status_engine import get_licenses_health_summary
from src.teams_engine import (
    detect_grade_and_nivel_from_text,
    audit_class_roster,
    sync_class_roster,
    audit_all_rosters,
    export_roster_audit_excel,
    export_roster_report_pdf
)


class TestTeamsRosterSyncAndPhase1(unittest.TestCase):

    def test_detect_grade_and_nivel_from_text(self):
        """Valida la inferencia automatica de nivel y grado desde nombres de clases."""
        cases = [
            ("Comunicados (1° Secundaria) - 26-27", "Secundaria", "1° Secundaria"),
            ("Matemáticas (3er Semestre) - 26-27", "Preparatoria", "3er Semestre"),
            ("Español (5° Primaria) - 26-27", "Primaria", "5° Primaria"),
            ("Educación Física (2° Preescolar) - 26-27", "Preescolar", "2° Preescolar"),
            ("Taller de Lectura 2do de Secundaria", "Secundaria", "2° Secundaria"),
            ("Inglés 4to Semestre Preparatoria", "Preparatoria", "4to Semestre"),
            ("Materia General Sin Grado", None, None)
        ]
        for text, exp_nivel, exp_grado in cases:
            nivel, grado = detect_grade_and_nivel_from_text(text)
            self.assertEqual(nivel, exp_nivel, f"Fallo nivel en '{text}'")
            self.assertEqual(grado, exp_grado, f"Fallo grado en '{text}'")

    def test_get_licenses_health_summary(self):
        """Valida el calculo predictivo de inventario de licencias M365."""
        graph_mock = MagicMock()

        # Caso 1: Optimo (>= 15)
        graph_mock.get_subscribed_skus.return_value = [
            {
                "skuPartNumber": "STANDARDWOFFPACK_STUDENT",
                "prepaidUnits": {"enabled": 100},
                "consumedUnits": 80
            }
        ]
        res_opt = get_licenses_health_summary(graph_mock)
        self.assertEqual(res_opt["level"], "normal")
        self.assertEqual(res_opt["badge_color"], "success")
        self.assertEqual(res_opt["student_available"], 20)

        # Caso 2: Advertencia (5 - 14)
        graph_mock.get_subscribed_skus.return_value = [
            {
                "skuPartNumber": "STANDARDWOFFPACK_STUDENT",
                "prepaidUnits": {"enabled": 100},
                "consumedUnits": 92
            }
        ]
        res_warn = get_licenses_health_summary(graph_mock)
        self.assertEqual(res_warn["level"], "warning")
        self.assertEqual(res_warn["badge_color"], "warning")
        self.assertEqual(res_warn["student_available"], 8)

        # Caso 3: Critico (< 5)
        graph_mock.get_subscribed_skus.return_value = [
            {
                "skuPartNumber": "STANDARDWOFFPACK_STUDENT",
                "prepaidUnits": {"enabled": 100},
                "consumedUnits": 98
            }
        ]
        res_crit = get_licenses_health_summary(graph_mock)
        self.assertEqual(res_crit["level"], "critical")
        self.assertEqual(res_crit["badge_color"], "danger")
        self.assertEqual(res_crit["student_available"], 2)

    def test_audit_class_roster(self):
        """Valida la deteccion de alumnos sincronizados, faltantes e inesperados."""
        graph_mock = MagicMock()
        graph_mock.get_team_owners.return_value = [
            {"id": "docente-1", "displayName": "Profesor Demo", "userPrincipalName": "profe@ijova.com"}
        ]
        # Alumnos en el equipo de Teams: 250001 (valido), 250099 (baja/ajeno al grado)
        graph_mock.get_team_members.return_value = [
            {"id": "docente-1", "userPrincipalName": "profe@ijova.com", "displayName": "Profesor Demo"},
            {"id": "s-1", "userPrincipalName": "250001@ijova.com", "displayName": "ALUMNO UNO"},
            {"id": "s-99", "userPrincipalName": "250099@ijova.com", "displayName": "ALUMNO BAJA"}
        ]
        graph_mock.get_all_teams.return_value = [
            {"id": "team-123", "displayName": "Biología (1° Secundaria) - 26-27"}
        ]

        # Usuarios en Entra ID
        user_mock_1 = MagicMock(id="s-1", user_principal_name="250001@ijova.com")
        user_mock_2 = MagicMock(id="s-2", user_principal_name="250002@ijova.com")
        user_mock_99 = MagicMock(id="s-99", user_principal_name="250099@ijova.com")
        graph_mock.get_all_users.return_value = [user_mock_1, user_mock_2, user_mock_99]

        # Base escolar oficial: 250001 y 250002 pertenecen a 1° Secundaria
        school_db = {
            "250001": {"display_name": "ALUMNO UNO", "upn": "250001@ijova.com", "nivel": "Secundaria", "grado": "1° Secundaria"},
            "250002": {"display_name": "ALUMNO DOS", "upn": "250002@ijova.com", "nivel": "Secundaria", "grado": "1° Secundaria"}
        }

        audit = audit_class_roster(
            graph=graph_mock,
            team_id="team-123",
            nivel="Secundaria",
            grado="1° Secundaria",
            school_db=school_db
        )

        self.assertEqual(audit["official_count"], 2)
        self.assertEqual(audit["team_count"], 2)  # 250001 y 250099
        self.assertEqual(audit["synced_count"], 1)  # 250001
        self.assertEqual(audit["missing_count"], 1)  # 250002 falta en Teams
        self.assertEqual(audit["unexpected_count"], 1)  # 250099 no pertenece
        self.assertFalse(audit["is_synced"])

        self.assertEqual(audit["missing_students"][0]["matricula"], "250002")
        self.assertEqual(audit["unexpected_students"][0]["matricula"], "250099")

    def test_sync_class_roster(self):
        """Valida la ejecucion de la sincronizacion de miembros."""
        graph_mock = MagicMock()
        graph_mock.access_token = "fake-token"
        graph_mock.add_team_member.return_value = True
        graph_mock.remove_team_member.return_value = True

        audit_info = {
            "missing_students": [{"user_id": "u-2", "matricula": "250002"}],
            "unexpected_students": [{"user_id": "u-99", "matricula": "250099"}]
        }

        # Sincronizar agregando faltantes
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            res = sync_class_roster(
                graph=graph_mock,
                team_id="team-123",
                add_missing=True,
                remove_unexpected=True,
                audit_info=audit_info
            )
            self.assertEqual(res["status"], "success")
            self.assertEqual(res["added_count"], 1)
            self.assertEqual(res["removed_count"], 1)

    def test_export_roster_excel_and_pdf(self):
        """Valida que la generacion de reportes oficiales Excel y PDF se ejecute sin excepciones."""
        mock_roster_data = {
            "cycle": "2026-2027",
            "total_classes": 1,
            "synced_classes": 0,
            "discrepant_classes": 1,
            "total_missing": 1,
            "total_unexpected": 1,
            "global_sync_rate": 50.0,
            "timestamp": "2026-09-22 13:30:00",
            "classes": [
                {
                    "team_name": "Biología (1° Secundaria) - 26-27",
                    "nivel": "Secundaria",
                    "grado": "1° Secundaria",
                    "teacher_name": "Profesor Demo",
                    "official_count": 2,
                    "team_count": 2,
                    "synced_count": 1,
                    "missing_count": 1,
                    "unexpected_count": 1,
                    "sync_percentage": 50.0
                }
            ],
            "discrepancies": [
                {
                    "clase": "Biología (1° Secundaria) - 26-27",
                    "matricula": "250002",
                    "nombre": "ALUMNO DOS",
                    "upn": "250002@ijova.com",
                    "tipo": "FALTANTE EN TEAMS",
                    "nivel": "Secundaria",
                    "grado": "1° Secundaria"
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            excel_path = os.path.join(tmpdir, "test_roster_audit.xlsx")
            export_roster_audit_excel(mock_roster_data, excel_path)
            self.assertTrue(os.path.exists(excel_path))
            self.assertGreater(os.path.getsize(excel_path), 2000)

            pdf_path = os.path.join(tmpdir, "test_roster_audit.pdf")
            export_roster_report_pdf(mock_roster_data, pdf_path)
            self.assertTrue(os.path.exists(pdf_path))
            self.assertGreater(os.path.getsize(pdf_path), 2000)

    @patch("src.graph_client.PublicClientApplication")
    def test_graph_client_401_auto_token_refresh(self, mock_msal):
        """Valida que un error HTTP 401 active la renovación automática del token y reintente con éxito."""
        from src.graph_client import GraphClient

        client = GraphClient(tenant_id="test-tenant", client_id="test-client", scopes=["User.Read.All"], cache_path=None)
        client.access_token = "expired-token-123"

        # Simular que ensure_valid_token renueva el token
        client.ensure_valid_token = MagicMock(return_value="fresh-token-456")

        mock_resp_401 = MagicMock()
        mock_resp_401.status_code = 401

        mock_resp_200 = MagicMock()
        mock_resp_200.status_code = 200
        mock_resp_200.json.return_value = {"value": [{"id": "teacher-1", "displayName": "Docente Test"}]}

        with patch("requests.get", side_effect=[mock_resp_401, mock_resp_200]) as mock_get:
            res = client._request_with_retry("https://graph.microsoft.com/v1.0/groups/team-123/owners")
            self.assertEqual(res, {"value": [{"id": "teacher-1", "displayName": "Docente Test"}]})
            self.assertEqual(mock_get.call_count, 2)
            client.ensure_valid_token.assert_called_with(force_refresh=True)


if __name__ == "__main__":
    unittest.main()
