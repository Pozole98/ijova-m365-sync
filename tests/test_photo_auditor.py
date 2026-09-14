"""
Pruebas unitarias para el módulo de auditoría de fotografías de perfil (photo_auditor).
Verifica descarga simulada, generación de HTML interactivo, exportación a Excel/CSV
y manejo de alumnos con y sin foto de perfil.
"""
import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.config import AppConfig
from src.graph_client import GraphClient
from src.models import EntraUser
from src.photo_auditor import (
    PhotoAuditRecord,
    download_single_photo,
    generate_html_gallery,
    generate_excel_audit_report,
    generate_csv_audit_report,
    audit_profile_photos
)


class TestPhotoAuditor(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.mock_graph = MagicMock(spec=GraphClient)
        self.mock_graph.admin_upn = "admin@ijova.com"
        self.mock_graph.tenant_id = "test-tenant"
        self.mock_graph.client_id = "test-client"

        self.mock_config = AppConfig(
            tenant_id="test-tenant",
            client_id="test-client",
            domain="ijova.com",
            excel_path="non_existent.xlsx",
            sheet_name="Hoja1",
            auth_method="device_code",
            graph_scopes=["User.Read.All"],
            reports_dir=self.temp_dir,
            backups_dir=os.path.join(self.temp_dir, "backups"),
            data_dir=os.path.join(self.temp_dir, "data"),
            secrets_dir=os.path.join(self.temp_dir, "secrets")
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_download_single_photo_with_image(self):
        """Verifica el procesamiento de un alumno que SÍ tiene fotografía en Entra ID."""
        fake_image_bytes = b"\xFF\xD8\xFF\xE0\x00\x10JFIF" # Minimal JPEG header
        self.mock_graph.get_user_photo.return_value = fake_image_bytes

        user = EntraUser(
            id="user-123",
            user_principal_name="250001@ijova.com",
            display_name="SCARLETT LUCERO ABREGO",
            mail_nickname="250001"
        )
        student_info = {"nivel": "Secundaria", "grado": "1° A"}
        photos_dir = os.path.join(self.temp_dir, "fotos_perfil")
        os.makedirs(photos_dir, exist_ok=True)

        rec = download_single_photo(self.mock_graph, user, student_info, photos_dir)

        self.assertTrue(rec.has_photo)
        self.assertEqual(rec.matricula, "250001")
        self.assertEqual(rec.nivel, "Secundaria")
        self.assertIsNotNone(rec.photo_filename)
        self.assertIn("250001", rec.photo_filename)
        self.assertGreater(rec.photo_size_bytes, 0)
        self.assertIsNotNone(rec.photo_base64)

        # Check file was saved
        saved_file = os.path.join(photos_dir, rec.photo_filename)
        self.assertTrue(os.path.exists(saved_file))

    def test_download_single_photo_without_image(self):
        """Verifica el procesamiento de un alumno que NO tiene fotografía (Graph retorna None / 404)."""
        self.mock_graph.get_user_photo.return_value = None

        user = EntraUser(
            id="user-456",
            user_principal_name="250002@ijova.com",
            display_name="DOMINIK ROMAN ARCINIEGA",
            mail_nickname="250002"
        )
        student_info = {"nivel": "Preparatoria", "grado": "3° Semestre"}
        photos_dir = os.path.join(self.temp_dir, "fotos_perfil")
        os.makedirs(photos_dir, exist_ok=True)

        rec = download_single_photo(self.mock_graph, user, student_info, photos_dir)

        self.assertFalse(rec.has_photo)
        self.assertEqual(rec.matricula, "250002")
        self.assertEqual(rec.photo_size_bytes, 0)
        self.assertIsNone(rec.photo_filename)
        self.assertIsNone(rec.photo_base64)

    def test_generate_html_gallery(self):
        """Verifica la generación del archivo HTML de la galería interactiva con métricas y tarjetas."""
        records = [
            PhotoAuditRecord(
                matricula="250001",
                upn="250001@ijova.com",
                display_name="SCARLETT LUCERO",
                nivel="Secundaria",
                grado_semestre="1°",
                has_photo=True,
                photo_filename="250001_SCARLETT.jpg",
                photo_size_bytes=2048,
                photo_base64="ZmFrZV9pbWFnZQ=="
            ),
            PhotoAuditRecord(
                matricula="250002",
                upn="250002@ijova.com",
                display_name="DOMINIK ROMAN",
                nivel="Preparatoria",
                grado_semestre="3°",
                has_photo=False
            )
        ]
        stats = {
            "total_audited": 2,
            "with_photo": 1,
            "without_photo": 1,
            "coverage_pct": 50.0,
            "timestamp": "2026-09-10 12:00:00"
        }
        gallery_file = os.path.join(self.temp_dir, "galeria.html")
        generate_html_gallery(records, gallery_file, stats, self.mock_config)

        self.assertTrue(os.path.exists(gallery_file))
        with open(gallery_file, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("Auditoría y Galería de Fotos de Perfil", content)
            self.assertIn("SCARLETT LUCERO", content)
            self.assertIn("DOMINIK ROMAN", content)
            self.assertIn("ijova.com", content)

    def test_generate_excel_and_csv_reports(self):
        """Verifica la generación de los reportes en Excel (.xlsx) y CSV."""
        records = [
            PhotoAuditRecord(
                matricula="250001",
                upn="250001@ijova.com",
                display_name="ALUMNO UNO",
                nivel="Primaria",
                grado_semestre="6°",
                has_photo=True,
                photo_filename="250001_ALUMNO.jpg",
                photo_size_bytes=4096
            ),
            PhotoAuditRecord(
                matricula="250002",
                upn="250002@ijova.com",
                display_name="ALUMNO DOS",
                nivel="Primaria",
                grado_semestre="6°",
                has_photo=False
            )
        ]
        stats = {
            "total_audited": 2,
            "with_photo": 1,
            "without_photo": 1,
            "coverage_pct": 50.0,
            "timestamp": "2026-09-10 12:00:00"
        }

        excel_path = os.path.join(self.temp_dir, "auditoria.xlsx")
        csv_path = os.path.join(self.temp_dir, "auditoria.csv")

        generate_excel_audit_report(records, excel_path, stats)
        generate_csv_audit_report(records, csv_path)

        self.assertTrue(os.path.exists(excel_path))
        self.assertTrue(os.path.exists(csv_path))
        self.assertGreater(os.path.getsize(excel_path), 0)
        self.assertGreater(os.path.getsize(csv_path), 0)

    @patch("src.photo_auditor.build_student_lookup", return_value={})
    def test_audit_profile_photos_flow(self, mock_lookup):
        """Verifica el flujo completo de auditoría con ThreadPoolExecutor."""
        mock_users = [
            EntraUser(
                id="u1",
                user_principal_name="250001@ijova.com",
                display_name="ALUMNO CON FOTO",
                mail_nickname="250001"
            ),
            EntraUser(
                id="u2",
                user_principal_name="250002@ijova.com",
                display_name="ALUMNO SIN FOTO",
                mail_nickname="250002"
            )
        ]
        self.mock_graph.get_all_users.return_value = mock_users
        self.mock_graph.get_user_photo.side_effect = lambda uid: b"mock-jpeg-data" if uid == "u1" else None

        records, stats, gal_path, xls_path = audit_profile_photos(
            graph=self.mock_graph,
            config=self.mock_config,
            max_workers=2,
            output_dir=self.temp_dir
        )

        self.assertEqual(stats["total_audited"], 2)
        self.assertEqual(stats["with_photo"], 1)
        self.assertEqual(stats["without_photo"], 1)
        self.assertEqual(stats["coverage_pct"], 50.0)
        self.assertTrue(os.path.exists(gal_path))
        self.assertTrue(os.path.exists(xls_path))


if __name__ == "__main__":
    unittest.main()
