"""
Paquete GUI de Gestión de Alumnos de Microsoft 365 para el Instituto José Vasconcelos.
Proporciona el servidor web local y la interfaz de usuario interactiva.
"""
from src.gui.app import create_app, start_gui

__all__ = ["create_app", "start_gui"]
