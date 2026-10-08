"""
Modulo de persistencia y gestion de base de datos MariaDB para IJOVA M365 Sync.
Proporciona operaciones CRUD transaccionales para alumnos, tutores y bitacora,
garantizando alta disponibilidad y compatibilidad con el ecosistema escolar.
"""
import os
import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

import pymysql
import pymysql.cursors

from src.config import load_config, DatabaseConfig
from src.audit_logger import log_audit_event

logger = logging.getLogger("ijova_db")


class DatabaseConnectionError(Exception):
    """Excepcion cuando no se puede conectar al servidor MariaDB."""
    pass


def get_db_config() -> DatabaseConfig:
    config = load_config()
    return config.db


def get_connection(database: Optional[str] = None):
    """
    Obtiene una conexion activa a MariaDB utilizando PyMySQL.
    """
    db_cfg = get_db_config()
    target_db = database if database is not None else db_cfg.database
    try:
        conn = pymysql.connect(
            host=db_cfg.host,
            port=db_cfg.port,
            user=db_cfg.user,
            password=db_cfg.password,
            database=target_db,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
            connect_timeout=5
        )
        return conn
    except pymysql.MySQLError as e:
        raise DatabaseConnectionError(f"No se pudo conectar a MariaDB ({db_cfg.host}:{db_cfg.port}): {e}")


def check_db_health() -> Dict[str, Any]:
    """
    Verifica el estado de conexion a MariaDB y el conteo de tablas y registros.
    """
    db_cfg = get_db_config()
    status = {
        "connected": False,
        "engine": "MariaDB",
        "host": f"{db_cfg.host}:{db_cfg.port}",
        "database": db_cfg.database,
        "user": db_cfg.user,
        "total_alumnos": 0,
        "alumnos_activos": 0,
        "alumnos_bajas": 0,
        "alumnos_egresados": 0,
        "tables_ready": False,
        "error": None
    }
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SHOW TABLES LIKE 'alumnos';")
            if cur.fetchone():
                status["tables_ready"] = True
                cur.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN estatus = 'Activo' THEN 1 ELSE 0 END) as activos,
                        SUM(CASE WHEN estatus = 'Baja' THEN 1 ELSE 0 END) as bajas,
                        SUM(CASE WHEN estatus = 'Egresado / Ciclo Anterior' THEN 1 ELSE 0 END) as egresados
                    FROM alumnos;
                """)
                row = cur.fetchone() or {}
                status["total_alumnos"] = row.get("total") or 0
                status["alumnos_activos"] = row.get("activos") or 0
                status["alumnos_bajas"] = row.get("bajas") or 0
                status["alumnos_egresados"] = row.get("egresados") or 0
        conn.close()
        status["connected"] = True
    except Exception as e:
        status["error"] = str(e)
    return status


def init_db_schema() -> bool:
    """
    Crea las tablas necesarias en MariaDB si aun no existen.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS alumnos (
                matricula VARCHAR(64) PRIMARY KEY,
                nombre_oficial VARCHAR(150) NOT NULL,
                paterno VARCHAR(80),
                materno VARCHAR(80),
                nombres VARCHAR(100),
                curp VARCHAR(25),
                nivel VARCHAR(30) NOT NULL,
                grado VARCHAR(30) NOT NULL,
                seccion VARCHAR(10) DEFAULT 'A',
                sexo VARCHAR(10),
                upn VARCHAR(100) NOT NULL UNIQUE,
                estatus VARCHAR(40) DEFAULT 'Activo',
                ciclo VARCHAR(20) DEFAULT '2026-2027',
                m365_user_id VARCHAR(64),
                tiene_foto BOOLEAN DEFAULT FALSE,
                fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
                fecha_actualizacion DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_nivel_grado (nivel, grado),
                INDEX idx_estatus (estatus),
                INDEX idx_ciclo (ciclo)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS tutores (
                id INT AUTO_INCREMENT PRIMARY KEY,
                matricula_alumno VARCHAR(64) NOT NULL,
                nombre VARCHAR(150),
                telefono VARCHAR(30),
                correo VARCHAR(100),
                parentesco VARCHAR(50) DEFAULT 'Tutor',
                es_principal BOOLEAN DEFAULT TRUE,
                fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (matricula_alumno) REFERENCES alumnos(matricula) ON DELETE CASCADE,
                INDEX idx_tutor_alumno (matricula_alumno)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS bitacora_auditoria (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                fecha_utc DATETIME NOT NULL,
                accion VARCHAR(50) NOT NULL,
                matricula_o_target VARCHAR(100),
                admin_upn VARCHAR(100) NOT NULL,
                resultado VARCHAR(20) NOT NULL,
                detalles TEXT,
                INDEX idx_fecha (fecha_utc),
                INDEX idx_accion (accion)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """)
        return True
    finally:
        conn.close()


def get_all_students(
    search: Optional[str] = None,
    nivel: Optional[str] = None,
    grado: Optional[str] = None,
    estatus: Optional[str] = None,
    limit: int = 500,
    offset: int = 0
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Retorna la lista de alumnos con sus tutores y el total filtrado.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            where_clauses = []
            params = []

            if estatus:
                where_clauses.append("a.estatus = %s")
                params.append(estatus)

            if nivel:
                where_clauses.append("a.nivel = %s")
                params.append(nivel)

            if grado:
                where_clauses.append("a.grado LIKE %s")
                params.append(f"%{grado}%")

            if search:
                s = f"%{search.strip()}%"
                where_clauses.append("(a.matricula LIKE %s OR a.nombre_oficial LIKE %s OR a.upn LIKE %s OR a.curp LIKE %s OR t.nombre LIKE %s)")
                params.extend([s, s, s, s, s])

            where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

            # Conteo total
            count_sql = f"""
                SELECT COUNT(DISTINCT a.matricula) as total
                FROM alumnos a
                LEFT JOIN tutores t ON a.matricula = t.matricula_alumno AND t.es_principal = TRUE
                {where_sql}
            """
            cur.execute(count_sql, params)
            total = cur.fetchone()["total"]

            # Datos paginados
            data_sql = f"""
                SELECT 
                    a.matricula,
                    a.nombre_oficial,
                    a.paterno,
                    a.materno,
                    a.nombres,
                    a.curp,
                    a.nivel,
                    a.grado,
                    a.seccion,
                    a.sexo,
                    a.upn,
                    a.estatus,
                    a.ciclo,
                    a.m365_user_id,
                    a.tiene_foto,
                    a.fecha_creacion,
                    a.fecha_actualizacion,
                    t.nombre AS tutor_nombre,
                    t.telefono AS tutor_telefono,
                    t.correo AS tutor_correo,
                    t.parentesco AS tutor_parentesco
                FROM alumnos a
                LEFT JOIN tutores t ON a.matricula = t.matricula_alumno AND t.es_principal = TRUE
                {where_sql}
                ORDER BY a.nivel ASC, a.grado ASC, a.nombre_oficial ASC
                LIMIT %s OFFSET %s
            """
            cur.execute(data_sql, params + [limit, offset])
            rows = cur.fetchall()
            return rows, total
    finally:
        conn.close()


def get_student_by_matricula(matricula: str) -> Optional[Dict[str, Any]]:
    """
    Obtiene un alumno por matricula con todos sus datos y contacto de tutor.
    """
    clean_mat = matricula.strip()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    a.matricula,
                    a.nombre_oficial,
                    a.paterno,
                    a.materno,
                    a.nombres,
                    a.curp,
                    a.nivel,
                    a.grado,
                    a.seccion,
                    a.sexo,
                    a.upn,
                    a.estatus,
                    a.ciclo,
                    a.m365_user_id,
                    a.tiene_foto,
                    a.fecha_creacion,
                    a.fecha_actualizacion,
                    t.nombre AS tutor_nombre,
                    t.telefono AS tutor_telefono,
                    t.correo AS tutor_correo,
                    t.parentesco AS tutor_parentesco
                FROM alumnos a
                LEFT JOIN tutores t ON a.matricula = t.matricula_alumno AND t.es_principal = TRUE
                WHERE a.matricula = %s
            """, (clean_mat,))
            return cur.fetchone()
    finally:
        conn.close()


def create_student(student_data: Dict[str, Any], tutor_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Registra un nuevo alumno y su tutor en MariaDB.
    """
    mat = str(student_data.get("matricula", "")).strip()
    if not mat:
        raise ValueError("La matricula del alumno es requerida.")

    paterno = (student_data.get("paterno") or "").strip().upper()
    materno = (student_data.get("materno") or "").strip().upper()
    nombres = (student_data.get("nombres") or "").strip().upper()

    nombre_oficial = student_data.get("nombre_oficial")
    if not nombre_oficial:
        nombre_oficial = f"{paterno} {materno} {nombres}".strip()
    else:
        nombre_oficial = nombre_oficial.strip().upper()

    cfg = load_config()
    domain = cfg.domain
    upn = student_data.get("upn") or f"{mat}@{domain}".lower()

    nivel = (student_data.get("nivel") or "Secundaria").strip()
    grado = (student_data.get("grado") or "1°").strip()
    seccion = (student_data.get("seccion") or "A").strip()
    curp = (student_data.get("curp") or "").strip().upper()
    sexo = (student_data.get("sexo") or "").strip().upper()
    estatus = (student_data.get("estatus") or "Activo").strip()
    ciclo = (student_data.get("ciclo") or "2026-2027").strip()
    m365_id = student_data.get("m365_user_id")

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Verificar si ya existe
            cur.execute("SELECT matricula FROM alumnos WHERE matricula = %s OR upn = %s", (mat, upn))
            if cur.fetchone():
                raise ValueError(f"Ya existe un alumno con la matricula '{mat}' o UPN '{upn}'.")

            cur.execute("""
                INSERT INTO alumnos (
                    matricula, nombre_oficial, paterno, materno, nombres,
                    curp, nivel, grado, seccion, sexo, upn, estatus, ciclo, m365_user_id
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """, (
                mat, nombre_oficial, paterno, materno, nombres,
                curp, nivel, grado, seccion, sexo, upn, estatus, ciclo, m365_id
            ))

            if tutor_data:
                t_nom = (tutor_data.get("nombre") or "").strip().upper()
                t_tel = (tutor_data.get("telefono") or "").strip()
                t_cor = (tutor_data.get("correo") or "").strip().lower()
                t_par = (tutor_data.get("parentesco") or "Tutor").strip()
                if t_nom or t_tel or t_cor:
                    cur.execute("""
                        INSERT INTO tutores (
                            matricula_alumno, nombre, telefono, correo, parentesco, es_principal
                        ) VALUES (%s, %s, %s, %s, %s, TRUE)
                    """, (mat, t_nom, t_tel, t_cor, t_par))

        log_audit_event(
            action="CREATE_STUDENT_DB",
            target=mat,
            admin="admin@ijova.com",
            status="SUCCESS",
            details=f"Alumno {nombre_oficial} registrado en MariaDB ({nivel} {grado})"
        )
        return get_student_by_matricula(mat) or {}
    finally:
        conn.close()


def update_student(
    matricula: str,
    student_data: Dict[str, Any],
    tutor_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Actualiza los datos de un alumno existente y su tutor.
    """
    clean_mat = matricula.strip()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT matricula FROM alumnos WHERE matricula = %s", (clean_mat,))
            if not cur.fetchone():
                raise ValueError(f"No se encontro el alumno con matricula '{clean_mat}'.")

            update_fields = []
            params = []

            for field in ["paterno", "materno", "nombres", "nombre_oficial", "curp", "nivel", "grado", "seccion", "sexo", "estatus", "ciclo", "m365_user_id"]:
                if field in student_data:
                    val = student_data[field]
                    if isinstance(val, str):
                        val = val.strip()
                        if field in ["paterno", "materno", "nombres", "nombre_oficial", "curp"]:
                            val = val.upper()
                    update_fields.append(f"{field} = %s")
                    params.append(val)

            if update_fields:
                params.append(clean_mat)
                sql = f"UPDATE alumnos SET {', '.join(update_fields)} WHERE matricula = %s"
                cur.execute(sql, params)

            if tutor_data is not None:
                t_nom = (tutor_data.get("nombre") or "").strip().upper()
                t_tel = (tutor_data.get("telefono") or "").strip()
                t_cor = (tutor_data.get("correo") or "").strip().lower()
                t_par = (tutor_data.get("parentesco") or "Tutor").strip()

                cur.execute("SELECT id FROM tutores WHERE matricula_alumno = %s AND es_principal = TRUE", (clean_mat,))
                existing_tutor = cur.fetchone()
                if existing_tutor:
                    cur.execute("""
                        UPDATE tutores SET
                            nombre = %s, telefono = %s, correo = %s, parentesco = %s
                        WHERE id = %s
                    """, (t_nom, t_tel, t_cor, t_par, existing_tutor["id"]))
                elif t_nom or t_tel or t_cor:
                    cur.execute("""
                        INSERT INTO tutores (
                            matricula_alumno, nombre, telefono, correo, parentesco, es_principal
                        ) VALUES (%s, %s, %s, %s, %s, TRUE)
                    """, (clean_mat, t_nom, t_tel, t_cor, t_par))

        log_audit_event(
            action="UPDATE_STUDENT_DB",
            target=clean_mat,
            admin="admin@ijova.com",
            status="SUCCESS",
            details=f"Datos del alumno {clean_mat} actualizados en MariaDB"
        )
        return get_student_by_matricula(clean_mat) or {}
    finally:
        conn.close()


def set_student_status(matricula: str, new_status: str) -> bool:
    """
    Modifica el estatus de un alumno (Activo, Baja, Egresado).
    """
    clean_mat = matricula.strip()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE alumnos SET estatus = %s WHERE matricula = %s", (new_status, clean_mat))
        log_audit_event(
            action="CHANGE_STUDENT_STATUS_DB",
            target=clean_mat,
            admin="admin@ijova.com",
            status="SUCCESS",
            details=f"Estatus de {clean_mat} cambiado a {new_status}"
        )
        return True
    finally:
        conn.close()


def delete_student_permanently(matricula: str) -> bool:
    """
    Elimina permanentemente un alumno y su tutor de MariaDB.
    """
    clean_mat = matricula.strip()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM alumnos WHERE matricula = %s", (clean_mat,))
        log_audit_event(
            action="DELETE_STUDENT_PERMANENT_DB",
            target=clean_mat,
            admin="admin@ijova.com",
            status="SUCCESS",
            details=f"Registro de {clean_mat} purgado de MariaDB"
        )
        return True
    finally:
        conn.close()


def get_school_db_from_mariadb(only_active: bool = False) -> Dict[str, Dict[str, Any]]:
    """
    Retorna la estructura compatible con build_school_db() de export_students_m365.py.
    Permite sustituir transparentemente la lectura de hojas de cálculo de Excel.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            sql = """
                SELECT 
                    a.matricula,
                    a.nombre_oficial,
                    a.paterno,
                    a.materno,
                    a.nombres,
                    a.curp,
                    a.nivel,
                    a.grado,
                    a.seccion,
                    a.sexo,
                    a.upn,
                    a.estatus,
                    a.ciclo,
                    a.tiene_foto,
                    t.nombre AS tutor_nombre,
                    t.telefono AS tutor_telefono,
                    t.correo AS tutor_correo
                FROM alumnos a
                LEFT JOIN tutores t ON a.matricula = t.matricula_alumno AND t.es_principal = TRUE
            """
            if only_active:
                sql += " WHERE a.estatus = 'Activo'"
            cur.execute(sql)
            rows = cur.fetchall()

            result = {}
            for r in rows:
                mat = str(r["matricula"]).strip()
                result[mat] = {
                    "matricula": mat,
                    "paterno": r.get("paterno") or "",
                    "materno": r.get("materno") or "",
                    "nombres": r.get("nombres") or "",
                    "display_name": r.get("nombre_oficial") or "",
                    "nombre_oficial": r.get("nombre_oficial") or "",
                    "curp": r.get("curp") or "",
                    "nivel": r.get("nivel") or "Secundaria",
                    "grado": r.get("grado") or "1°",
                    "grado_semestre": r.get("grado") or "1°",
                    "seccion": r.get("seccion") or "A",
                    "sexo": r.get("sexo") or "",
                    "upn": r.get("upn") or f"{mat}@ijova.com",
                    "estatus": r.get("estatus") or "Activo",
                    "ciclo": r.get("ciclo") or "2026-2027",
                    "tiene_foto": bool(r.get("tiene_foto")),
                    "tutor_nombre": r.get("tutor_nombre") or "",
                    "padre_o_tutor": r.get("tutor_nombre") or "",
                    "tutor_telefono": r.get("tutor_telefono") or "",
                    "telefono_contacto": r.get("tutor_telefono") or "",
                    "tutor_correo": r.get("tutor_correo") or "",
                    "correo_contacto": r.get("tutor_correo") or "",
                    "alias": ""
                }
            return result
    finally:
        conn.close()


def seed_mariadb_from_current_excel(force: bool = False) -> Dict[str, Any]:
    """
    Migra y siembra la base de datos MariaDB tomando los datos consolidados actuales.
    Inserta alumnos y tutores de forma idempotente.
    """
    init_db_schema()

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as count FROM alumnos")
            existing_count = cur.fetchone()["count"]
            if existing_count > 0 and not force:
                return {
                    "already_seeded": True,
                    "count": existing_count,
                    "message": f"MariaDB ya contiene {existing_count} alumnos. No se requirio resiembra."
                }

        from export_students_m365 import build_school_db
        school_db = build_school_db()

        inserted_students = 0
        inserted_tutors = 0
        cfg = load_config()

        with conn.cursor() as cur:
            for mat, s in school_db.items():
                nom_oficial = s.get("display_name") or s.get("nombre_oficial") or f"{s.get('paterno', '')} {s.get('materno', '')} {s.get('nombres', '')}".strip()
                paterno = s.get("paterno") or ""
                materno = s.get("materno") or ""
                nombres = s.get("nombres") or ""
                nivel = s.get("nivel") or "Secundaria"
                grado = s.get("grado") or s.get("grado_semestre") or "1°"
                curp = s.get("curp") or ""
                seccion = s.get("seccion") or "A"
                sexo = s.get("sexo") or ""
                upn = f"{mat}@{cfg.domain}".lower()
                estatus = s.get("estatus") or "Activo"
                ciclo = s.get("ciclo") or "2026-2027"
                tiene_foto = bool(s.get("tiene_foto"))

                cur.execute("""
                    INSERT INTO alumnos (
                        matricula, nombre_oficial, paterno, materno, nombres,
                        curp, nivel, grado, seccion, sexo, upn, estatus, ciclo, tiene_foto
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON DUPLICATE KEY UPDATE
                        nombre_oficial = VALUES(nombre_oficial),
                        nivel = VALUES(nivel),
                        grado = VALUES(grado),
                        estatus = VALUES(estatus),
                        tiene_foto = VALUES(tiene_foto)
                """, (
                    mat, nom_oficial, paterno, materno, nombres,
                    curp, nivel, grado, seccion, sexo, upn, estatus, ciclo, tiene_foto
                ))
                inserted_students += 1

                t_nom = s.get("tutor_nombre") or s.get("padre_o_tutor") or ""
                t_tel = s.get("tutor_telefono") or s.get("telefono_contacto") or ""
                t_cor = s.get("tutor_correo") or s.get("correo_contacto") or ""

                if t_nom or t_tel or t_cor:
                    cur.execute("""
                        INSERT INTO tutores (
                            matricula_alumno, nombre, telefono, correo, parentesco, es_principal
                        ) VALUES (%s, %s, %s, %s, 'Tutor', TRUE)
                        ON DUPLICATE KEY UPDATE
                            nombre = VALUES(nombre),
                            telefono = VALUES(telefono),
                            correo = VALUES(correo)
                    """, (mat, t_nom, t_tel, t_cor))
                    inserted_tutors += 1

        log_audit_event(
            action="MIGRATE_EXCEL_TO_MARIADB",
            target="all",
            admin="system",
            status="SUCCESS",
            details=f"Migracion completada: {inserted_students} alumnos y {inserted_tutors} tutores sembrados en MariaDB"
        )

        return {
            "already_seeded": False,
            "students_inserted": inserted_students,
            "tutors_inserted": inserted_tutors,
            "message": f"Migracion exitosa a MariaDB: {inserted_students} alumnos importados."
        }
    finally:
        conn.close()
