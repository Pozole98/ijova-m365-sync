"""
Pruebas unitarias para el Auditor de Inactividad y Primer Acceso (Teams y M365).
Verifica:
1. Logica de clasificacion de inactividad (<5d, 5-14d advertencia, >=15d critico, nunca inicio sesion)
2. Cruce con la plantilla oficial del ciclo 2026-2027 y base de tutores
3. Generacion de archivo Excel de auditoria
4. Endpoints de la interfaz web Flask
"""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import openpyxl

from src.teams_engine import (
    audit_students_login_activity,
    export_activity_audit_excel,
)
from src.gui.app import create_app


class TestTeamsActivityAudit(unittest.TestCase):

    def setUp(self):
        self.mock_graph = MagicMock()
        self.mock_db = {
            "250001": {
                "matricula": "250001",
                "nombre_oficial": "ALUMNO RECIENTE",
                "upn": "250001@ijova.com",
                "nivel": "Secundaria",
                "grado_semestre": "3°",
                "estatus": "Activo",
                "padre_o_tutor": "PADRE RECIENTE",
                "telefono_contacto": "5511223344",
                "correo_contacto": "padre1@correo.com",
            },
            "250002": {
                "matricula": "250002",
                "nombre_oficial": "ALUMNO ADVERTENCIA",
                "upn": "250002@ijova.com",
                "nivel": "Secundaria",
                "grado_semestre": "2°",
                "estatus": "Activo",
                "padre_o_tutor": "MADRE ADVERTENCIA",
                "telefono_contacto": "5522334455",
                "correo_contacto": "madre2@correo.com",
            },
            "250003": {
                "matricula": "250003",
                "nombre_oficial": "ALUMNO CRITICO",
                "upn": "250003@ijova.com",
                "nivel": "Primaria",
                "grado_semestre": "5°",
                "estatus": "Activo",
                "padre_o_tutor": "",
                "telefono_contacto": "",
                "correo_contacto": "",
            },
            "250004": {
                "matricula": "250004",
                "nombre_oficial": "ALUMNO NUNCA INICIO",
                "upn": "250004@ijova.com",
                "nivel": "Preparatoria",
                "grado_semestre": "1°",
                "estatus": "Activo",
                "padre_o_tutor": "TUTOR NUNCA",
                "telefono_contacto": "5544556677",
                "correo_contacto": "tutor4@correo.com",
            },
            "240001": {
                "matricula": "240001",
                "nombre_oficial": "ALUMNO BAJA O CICLO ANTERIOR",
                "upn": "240001@ijova.com",
                "nivel": "Secundaria",
                "grado_semestre": "3°",
                "estatus": "Baja",
            }
        }

    def test_audit_students_login_activity_classification(self):
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)

        ts_recent = (now - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        ts_warning = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        ts_critical = (now - timedelta(days=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
        ts_created = (now - timedelta(days=40)).strftime("%Y-%m-%dT10:00:00Z")
        ts_same_as_created = (now - timedelta(days=40)).strftime("%Y-%m-%dT10:00:15Z")

        graph_users = [
            {
                "id": "u1",
                "displayName": "ALUMNO RECIENTE",
                "userPrincipalName": "250001@ijova.com",
                "createdDateTime": ts_created,
                "signInSessionsValidFromDateTime": ts_recent,
                "deviceKeys": [{"deviceId": "d1"}],
                "accountEnabled": True,
            },
            {
                "id": "u2",
                "displayName": "ALUMNO ADVERTENCIA",
                "userPrincipalName": "250002@ijova.com",
                "createdDateTime": ts_created,
                "signInSessionsValidFromDateTime": ts_warning,
                "deviceKeys": [],
                "accountEnabled": True,
            },
            {
                "id": "u3",
                "displayName": "ALUMNO CRITICO",
                "userPrincipalName": "250003@ijova.com",
                "createdDateTime": ts_created,
                "signInSessionsValidFromDateTime": ts_critical,
                "deviceKeys": [{"deviceId": "d3"}],
                "accountEnabled": True,
            },
            {
                "id": "u4",
                "displayName": "ALUMNO NUNCA INICIO",
                "userPrincipalName": "250004@ijova.com",
                "createdDateTime": ts_created,
                "signInSessionsValidFromDateTime": ts_same_as_created,
                "deviceKeys": [],
                "accountEnabled": True,
            },
            {
                "id": "u5",
                "displayName": "ALUMNO EXCLUIDO",
                "userPrincipalName": "240001@ijova.com",
                "createdDateTime": ts_created,
                "signInSessionsValidFromDateTime": ts_recent,
                "deviceKeys": [],
                "accountEnabled": True,
            }
        ]

        self.mock_graph.get_users_with_activity.return_value = graph_users

        res = audit_students_login_activity(self.mock_graph, self.mock_db, days_threshold=5)

        summary = res["summary"]
        students = res["students"]

        # Exactly 4 official active students evaluated (240001 excluded)
        self.assertEqual(summary["total_students"], 4)
        self.assertEqual(summary["active_recent"], 1)
        self.assertEqual(summary["inactive_5d_or_more"], 3)
        self.assertEqual(summary["inactive_15d_or_more"], 2)
        self.assertEqual(summary["never_logged_in"], 1)

        stu_map = {s["matricula"]: s for s in students}

        # Recent
        self.assertEqual(stu_map["250001"]["risk_level"], "ACTIVE")
        self.assertEqual(stu_map["250001"]["days_inactive"], 2)
        self.assertEqual(stu_map["250001"]["devices_count"], 1)
        self.assertEqual(stu_map["250001"]["tutor"]["nombre"], "PADRE RECIENTE")

        # Warning
        self.assertEqual(stu_map["250002"]["risk_level"], "WARNING")
        self.assertEqual(stu_map["250002"]["days_inactive"], 7)
        self.assertEqual(stu_map["250002"]["tutor"]["telefono"], "5522334455")

        # Critical
        self.assertEqual(stu_map["250003"]["risk_level"], "CRITICAL")
        self.assertEqual(stu_map["250003"]["days_inactive"], 20)

        # Never logged in
        self.assertEqual(stu_map["250004"]["risk_level"], "CRITICAL")
        self.assertTrue(stu_map["250004"]["never_logged_in"])

    def test_export_activity_audit_excel(self):
        activity_data = {
            "summary": {
                "total_students": 2,
                "active_recent": 1,
                "inactive_5d_or_more": 1,
                "inactive_15d_or_more": 1,
                "never_logged_in": 1,
                "threshold_days": 5,
            },
            "students": [
                {
                    "matricula": "250001",
                    "displayName": "ALUMNO UNO",
                    "userPrincipalName": "250001@ijova.com",
                    "nivel": "Secundaria",
                    "grado": "3°",
                    "days_inactive": 1,
                    "last_sign_in_formatted": "04/10/2026 12:00",
                    "never_logged_in": False,
                    "risk_level": "ACTIVE",
                    "risk_label": "Al dia (<5d)",
                    "devices_count": 1,
                    "account_enabled": True,
                    "tutor": {
                        "nombre": "TUTOR UNO",
                        "telefono": "5512345678",
                        "correo": "tutor1@mail.com",
                    }
                },
                {
                    "matricula": "250002",
                    "displayName": "ALUMNO DOS",
                    "userPrincipalName": "250002@ijova.com",
                    "nivel": "Secundaria",
                    "grado": "2°",
                    "days_inactive": 999,
                    "last_sign_in_formatted": "-",
                    "never_logged_in": True,
                    "risk_level": "CRITICAL",
                    "risk_label": "Nunca Inicio Sesion",
                    "devices_count": 0,
                    "account_enabled": True,
                    "tutor": {
                        "nombre": "TUTOR DOS",
                        "telefono": "5587654321",
                        "correo": "tutor2@mail.com",
                    }
                }
            ]
        }

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            res_path = export_activity_audit_excel(activity_data, tmp_path)
            self.assertEqual(res_path, tmp_path)
            self.assertTrue(os.path.exists(tmp_path))

            wb = openpyxl.load_workbook(tmp_path)
            self.assertIn("Auditoría de Inactividad", wb.sheetnames)
            ws = wb["Auditoría de Inactividad"]

            # Row 1 is table header
            headers = [cell.value for cell in ws[1]]
            self.assertIn("Matrícula", headers)
            self.assertIn("Nombre del Alumno", headers)
            self.assertIn("Correo Institucional", headers)
            self.assertIn("Días Inactivo", headers)
            self.assertIn("Estado Actividad", headers)
            self.assertIn("Nombre Tutor", headers)
            self.assertIn("Teléfono Tutor", headers)

            # Row 2 and 3 are student data
            self.assertEqual(ws.cell(row=2, column=1).value, "250001")
            self.assertEqual(ws.cell(row=3, column=1).value, "250002")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_gui_activity_endpoints(self):
        app = create_app()
        client = app.test_client()

        # Mock audit_students_login_activity in teams_engine module
        sample_audit_result = {
            "summary": {
                "total_students": 1,
                "active_recent": 1,
                "inactive_5d_or_more": 0,
                "inactive_15d_or_more": 0,
                "never_logged_in": 0,
                "threshold_days": 5,
            },
            "students": [
                {
                    "matricula": "250010",
                    "displayName": "TEST ALUMNO",
                    "userPrincipalName": "250010@ijova.com",
                    "nivel": "Primaria",
                    "grado": "1°",
                    "days_inactive": 1,
                    "last_sign_in_formatted": "05/10/2026 08:00",
                    "never_logged_in": False,
                    "risk_level": "ACTIVE",
                    "risk_label": "Al dia (<5d)",
                    "devices_count": 1,
                    "account_enabled": True,
                    "tutor": {}
                }
            ]
        }

        with patch("src.teams_engine.audit_students_login_activity", return_value=sample_audit_result):
            resp = client.get("/api/teams/activity/audit")
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["data"]["summary"]["total_students"], 1)

        with patch("src.teams_engine.audit_students_login_activity", return_value=sample_audit_result):
            resp_excel = client.get("/api/teams/activity/export-excel")
            self.assertEqual(resp_excel.status_code, 200)
            self.assertIn("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", resp_excel.content_type)


if __name__ == "__main__":
    unittest.main()
