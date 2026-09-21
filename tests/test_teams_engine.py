"""
Pruebas unitarias para el motor de auditoría y gestión de Microsoft Teams (teams_engine).
Verifica detección de ciclo escolar, tipificación de equipos, clasificación de creadores/dueños,
filtrado de alumnos por grado y exportación del libro Excel de 4 hojas.
"""
import os
import shutil
import tempfile
import unittest
import openpyxl

from src.teams_engine import (
    detect_team_cycle,
    detect_team_type,
    detect_creator_type,
    get_students_for_grade,
    export_teams_audit_excel,
)


class TestTeamsEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_detect_team_cycle(self):
        """Verifica la detección heurística del ciclo escolar por nombre y fecha."""
        # 1. Por coincidencia en el nombre
        self.assertEqual(detect_team_cycle("Matemáticas (3er Semestre) - 26-27"), "2026-2027")
        self.assertEqual(detect_team_cycle("Historia 2026-2027"), "2026-2027")
        self.assertEqual(detect_team_cycle("Biología 25-26"), "2025-2026")
        self.assertEqual(detect_team_cycle("Física Ciclo 2025-2026"), "2025-2026")

        # 2. Por fecha de creación cuando el nombre no tiene etiqueta
        self.assertEqual(detect_team_cycle("Química General", created_at="2026-08-15T10:00:00Z"), "2026-2027")
        self.assertEqual(detect_team_cycle("Taller de Lectura", created_at="2025-10-01T12:00:00Z"), "2025-2026")
        self.assertEqual(detect_team_cycle("Clase Antigua", created_at="2024-05-10T12:00:00Z"), "2025-2026")

    def test_detect_team_type(self):
        """Verifica la tipificación entre CLASE, DOCENTES y GENERAL."""
        # Por especialización educationClass
        self.assertEqual(detect_team_type("Química I", specialization="educationClass"), "CLASE")

        # Por palabras clave de clase
        self.assertEqual(detect_team_type("Lengua y Comunicación (3er Semestre Preparatoria)"), "CLASE")
        self.assertEqual(detect_team_type("Matemáticas 1° Secundaria"), "CLASE")

        # Por docentes / staff
        self.assertEqual(detect_team_type("Consejo Técnico de Docentes"), "DOCENTES")
        self.assertEqual(detect_team_type("Staff Directivo IJOVA"), "DOCENTES")

        # General / Otro
        self.assertEqual(detect_team_type("Torneo de Ajedrez 2026"), "GENERAL")

    def test_detect_creator_type(self):
        """Verifica la identificación del origen o creador del equipo."""
        # Dueño alumno con matrícula numérica (campo upn o userPrincipalName)
        student_owners = [{"name": "Alumno Uno", "upn": "250012@ijova.com"}]
        self.assertEqual(detect_creator_type(student_owners), "ALUMNO")

        # Dueño maestro / staff institucional
        staff_owners = [{"name": "Profesor Perez", "userPrincipalName": "pperez@ijova.com"}]
        self.assertEqual(detect_creator_type(staff_owners), "MAESTRO_STAFF")

        # Equipo huérfano sin propietarios
        self.assertEqual(detect_creator_type([]), "HUERFANO")
        self.assertEqual(detect_creator_type(None), "HUERFANO")

    def test_get_students_for_grade(self):
        """Verifica el filtrado de alumnos de la base escolar según nivel y grado."""
        school_db = {
            "250001": {"display_name": "ALUMNO A", "nivel": "Preparatoria", "grado": "3er Semestre"},
            "250002": {"display_name": "ALUMNO B", "nivel": "Preparatoria", "grado": "3er Semestre"},
            "250003": {"display_name": "ALUMNO C", "nivel": "Preparatoria", "grado": "1er Semestre"},
            "250004": {"display_name": "ALUMNO D", "nivel": "Secundaria", "grado": "1° Secundaria"},
        }

        prep_3 = get_students_for_grade(school_db, "Preparatoria", "3er Semestre")
        self.assertEqual(len(prep_3), 2)
        self.assertEqual(prep_3[0]["matricula"], "250001")
        self.assertEqual(prep_3[1]["matricula"], "250002")

        sec_1 = get_students_for_grade(school_db, "Secundaria", "1° Secundaria")
        self.assertEqual(len(sec_1), 1)
        self.assertEqual(sec_1[0]["matricula"], "250004")

        empty = get_students_for_grade(school_db, "Primaria", "6° Primaria")
        self.assertEqual(len(empty), 0)

    def test_export_teams_audit_excel(self):
        """Verifica la generación del libro Excel de auditoría con sus 4 hojas oficiales."""
        mock_audit_data = {
            "summary": {
                "total_teams": 3,
                "cycle_2026_2027": 1,
                "past_cycles": 1,
                "class_teams": 2,
                "staff_teams": 1,
                "orphan_teams": 1,
                "student_owned_teams": 1,
                "empty_teams": 1,
            },
            "teams": [
                {
                    "id": "team-001",
                    "name": "Matemáticas III (3er Semestre) - 26-27",
                    "description": "Clase oficial",
                    "created_date_str": "2026-08-20 10:00",
                    "academic_cycle": "2026-2027",
                    "cycle": "2026-2027",
                    "team_type": "CLASE",
                    "creator_type": "MAESTRO_STAFF",
                    "is_archived": False,
                    "owners": [{"name": "Docente Perez", "upn": "docente@ijova.com"}],
                    "members_count": 28,
                    "students_count": 27,
                    "mail": "mat3@ijova.com",
                    "flags": []
                },
                {
                    "id": "team-002",
                    "name": "Historia Universal 25-26",
                    "description": "Ciclo pasado",
                    "created_date_str": "2025-09-01 10:00",
                    "academic_cycle": "2025-2026",
                    "cycle": "2025-2026",
                    "team_type": "CLASE",
                    "creator_type": "MAESTRO_STAFF",
                    "is_archived": True,
                    "owners": [{"name": "Docente Gomez", "upn": "gomez@ijova.com"}],
                    "members_count": 30,
                    "students_count": 29,
                    "mail": "hist@ijova.com",
                    "flags": ["CICLO_ANTERIOR"]
                },
                {
                    "id": "team-003",
                    "name": "Equipo Huérfano y Vacío",
                    "description": "Anomalía",
                    "created_date_str": "2026-09-01 10:00",
                    "academic_cycle": "2026-2027",
                    "cycle": "2026-2027",
                    "team_type": "GENERAL",
                    "creator_type": "HUERFANO",
                    "is_archived": False,
                    "owners": [],
                    "members_count": 0,
                    "students_count": 0,
                    "mail": "huerfano@ijova.com",
                    "flags": ["SIN_PROFESOR", "VACIO"]
                }
            ]
        }

        output_file = os.path.join(self.temp_dir, "test_teams_audit.xlsx")
        export_teams_audit_excel(mock_audit_data, output_file)

        self.assertTrue(os.path.exists(output_file))
        wb = openpyxl.load_workbook(output_file)

        expected_sheets = [
            "Clases Activas 26-27",
            "Ciclos Anteriores",
            "Anomalías y Huérfanos",
            "Resumen Ejecutivo Teams"
        ]
        for sheet_name in expected_sheets:
            self.assertIn(sheet_name, wb.sheetnames)

        # Verificar contenido de Clases Activas
        ws_active = wb["Clases Activas 26-27"]
        self.assertGreater(ws_active.max_row, 1)

        # Verificar contenido de Anomalías
        ws_anomalies = wb["Anomalías y Huérfanos"]
        self.assertGreater(ws_anomalies.max_row, 1)


if __name__ == "__main__":
    unittest.main()
