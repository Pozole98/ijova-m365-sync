"""
Pruebas unitarias para el modulo de base de datos MariaDB y endpoints de gestion de alumnos.
"""
import unittest
from unittest.mock import patch, MagicMock
from src.config import load_config
from src.db import check_db_health
from src.gui.app import create_app


class TestMariaDBIntegration(unittest.TestCase):

    def test_db_config_loading(self):
        cfg = load_config()
        self.assertIsNotNone(cfg.db)
        self.assertEqual(cfg.db.host, "localhost")
        self.assertEqual(cfg.db.port, 3306)
        self.assertEqual(cfg.db.user, "ijova_user")
        self.assertEqual(cfg.db.database, "ijova_identity")

    def test_check_db_health_structure(self):
        health = check_db_health()
        self.assertIn("connected", health)
        self.assertIn("engine", health)
        self.assertIn("host", health)
        self.assertIn("database", health)
        self.assertIn("total_alumnos", health)
        self.assertIn("alumnos_activos", health)

    def test_api_db_status_endpoint(self):
        app = create_app()
        client = app.test_client()
        resp = client.get("/api/db/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertIn("engine", data)

    def test_api_db_students_list_endpoint(self):
        app = create_app()
        client = app.test_client()
        resp = client.get("/api/db/students?limit=10&page=1")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertIn("students", data["data"])
        self.assertIn("total", data["data"])

    def test_api_db_student_validation(self):
        app = create_app()
        client = app.test_client()
        # Enviar sin matricula debe retornar 400
        resp = client.post("/api/db/students", json={})
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data["success"])

    def test_enroll_student_programmatic_invalid_mat(self):
        from src.enroll_engine import enroll_student_programmatic
        with self.assertRaises(ValueError):
            enroll_student_programmatic(
                graph=None,
                student_data={"matricula": "invalida"},
                provision_m365=False
            )


if __name__ == "__main__":
    unittest.main()
