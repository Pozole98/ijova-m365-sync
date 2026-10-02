#!/usr/bin/env bash
# ==============================================================================
# Script de Instalacion y Habilitacion de Servicio Systemd (Modo Usuario)
# Proyecto: IJOVA M365 Sync - Servicio Web en Puerto 5055
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SERVICE_NAME="ijova-sync.service"
USER_SYSTEMD_DIR="${HOME}/.config/systemd/user"
VENV_PYTHON="${PROJECT_ROOT}/.venv/bin/python"

echo "------------------------------------------------------------------------------"
echo "Instalacion de Servicio Automatico: ${SERVICE_NAME}"
echo "Directorio del proyecto: ${PROJECT_ROOT}"
echo "------------------------------------------------------------------------------"

# 1. Validar entorno virtual
if [ ! -f "${VENV_PYTHON}" ]; then
    echo "Error: No se encontro el interprete virtual en ${VENV_PYTHON}."
    echo "Por favor genera el entorno virtual antes de continuar."
    exit 1
fi

# 2. Crear directorio de systemd de usuario si no existe
mkdir -p "${USER_SYSTEMD_DIR}"

# 3. Generar archivo de servicio ajustado con rutas absolutas
SERVICE_DEST="${USER_SYSTEMD_DIR}/${SERVICE_NAME}"
cat <<EOF > "${SERVICE_DEST}"
[Unit]
Description=IJOVA M365 Sync - Servicio de Gestion, Auditoria y Sincronizacion Escolar
Documentation=https://github.com/Pozole98/ijova-m365-sync
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${PROJECT_ROOT}
ExecStart="${VENV_PYTHON}" main.py gui --port 5055 --no-browser
Restart=always
RestartSec=5s
Environment=PYTHONUNBUFFERED=1
StandardOutput=journal
StandardError=journal

NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=default.target
EOF

echo "Archivo de servicio instalado en: ${SERVICE_DEST}"

# 4. Recargar systemd de usuario
systemctl --user daemon-reload

# 5. Habilitar inicio automatico con el sistema / sesion
systemctl --user enable "${SERVICE_NAME}"
echo "Servicio habilitado para inicio automatico."

# 6. Iniciar o reiniciar el servicio
systemctl --user restart "${SERVICE_NAME}"
echo "Servicio iniciado correctamente."

# 7. Habilitar linger para persistencia tras cierre de sesion grafica (si esta disponible)
if command -v loginctl >/dev/null 2>&1; then
    loginctl enable-linger "${USER}" 2>/dev/null || true
fi

# 8. Verificacion de disponibilidad HTTP en puerto 5055
echo "Verificando respuesta del servidor en http://127.0.0.1:5055..."
STATUS_CODE="000"
for i in {1..10}; do
    sleep 1
    STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5055/ || true)
    if [ "${STATUS_CODE}" = "200" ]; then
        echo "Verificacion completada: Servidor respondiendo con codigo HTTP 200 OK tras ${i}s."
        break
    fi
done

if [ "${STATUS_CODE}" != "200" ]; then
    echo "Aviso: Codigo de respuesta HTTP: ${STATUS_CODE}. Verifique el estado con: systemctl --user status ${SERVICE_NAME}"
fi

echo "------------------------------------------------------------------------------"
echo "Comandos utiles de administracion:"
echo "  - Estado:    systemctl --user status ${SERVICE_NAME}"
echo "  - Detener:   systemctl --user stop ${SERVICE_NAME}"
echo "  - Reiniciar: systemctl --user restart ${SERVICE_NAME}"
echo "  - Registros: journalctl --user -u ${SERVICE_NAME} -f"
echo "------------------------------------------------------------------------------"
