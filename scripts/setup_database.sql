-- Script de inicialización de Base de Datos MariaDB para IJOVA M365 Sync
-- Ejecutar con: sudo mariadb < scripts/setup_database.sql

CREATE DATABASE IF NOT EXISTS ijova_identity
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'ijova_user'@'localhost' IDENTIFIED BY 'Ijova_Secure_2026!';
GRANT ALL PRIVILEGES ON ijova_identity.* TO 'ijova_user'@'localhost';
FLUSH PRIVILEGES;

USE ijova_identity;

-- 1. Tabla de Alumnos (Padrón Oficial)
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

-- 2. Tabla de Tutores y Contacto
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

-- 3. Tabla de Bitácora y Auditoría de Operaciones
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
