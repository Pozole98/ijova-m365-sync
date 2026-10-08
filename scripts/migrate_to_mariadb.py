#!/usr/bin/env python3
"""
Script de migracion inicial de Excel a MariaDB para IJOVA M365 Sync.
"""
import os
import sys

# Asegurar ruta del proyecto en sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.db import check_db_health, seed_mariadb_from_current_excel


def main():
    print("================================================================================")
    print("MIGRACION DE DATOS ESCOLARES A MARIADB — INSTITUTO JOSE VASCONCELOS (IJOVA)")
    print("================================================================================")
    
    print("\n1. Verificando conexion a MariaDB...")
    health = check_db_health()
    if not health.get("connected"):
        print("\nERROR: No se pudo conectar a MariaDB:")
        print(f"   Detalle: {health.get('error')}")
        print("\nInstrucciones para inicializar MariaDB:")
        print("   Ejecuta en tu terminal:")
        print("   sudo mariadb < scripts/setup_database.sql")
        print("\nLuego vuelve a ejecutar este script:")
        print("   .venv/bin/python scripts/migrate_to_mariadb.py")
        sys.exit(1)

    print(f"OK: Conectado exitosamente a MariaDB ({health.get('host')}, Base de Datos: {health.get('database')}).")

    print("\n2. Ejecutando migracion de alumnos y tutores...")
    try:
        res = seed_mariadb_from_current_excel(force=True)
        print(f"Resultado: {res.get('message')}")
        print(f"   Alumnos procesados: {res.get('students_inserted', 0)}")
        print(f"   Tutores procesados: {res.get('tutors_inserted', 0)}")
    except Exception as e:
        print(f"ERROR durante la siembra de datos: {e}")
        sys.exit(1)

    print("\n3. Verificando estado final...")
    final_health = check_db_health()
    print(f"   Total de alumnos en MariaDB:   {final_health.get('total_alumnos')}")
    print(f"   Alumnos activos (Ciclo 26-27): {final_health.get('alumnos_activos')}")
    print(f"   Alumnos egresados / historial: {final_health.get('alumnos_egresados')}")
    print(f"   Alumnos en baja:               {final_health.get('alumnos_bajas')}")

    print("\nMigracion completada con exito.")


if __name__ == "__main__":
    main()
