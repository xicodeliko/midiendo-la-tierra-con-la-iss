#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# instalar_servidor.sh
# Instala el grabador de la ISS como un SERVICIO del sistema (systemd) en Ubuntu.
#
# Un servicio systemd es un programa que:
#   - arranca solo cuando el servidor se enciende,
#   - se reinicia solo si se cae,
#   - guarda sus mensajes en un log que puedes revisar con journalctl.
#
# Uso (dentro de la carpeta del proyecto, SIN sudo):
#   bash instalar_servidor.sh
# -----------------------------------------------------------------------------

# -e: detenerse si un comando falla | -u: error si se usa una variable no definida
# -o pipefail: un error en medio de un "|" también cuenta como error
set -euo pipefail

NOMBRE_SERVICIO="iss-paneles"
CARPETA="$(cd "$(dirname "$0")" && pwd)"   # carpeta donde está este script
USUARIO="$(whoami)"

if [ "$EUID" -eq 0 ]; then
    echo "❌ Córrelo SIN sudo (con tu usuario normal). El script pide sudo cuando lo necesita."
    exit 1
fi

echo "📦 1/4 Instalando Python y venv del sistema..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-venv

echo "🐍 2/4 Creando entorno virtual e instalando librerías..."
python3 -m venv "$CARPETA/.venv"
"$CARPETA/.venv/bin/pip" install -q --upgrade pip
"$CARPETA/.venv/bin/pip" install -q -r "$CARPETA/requirements-servidor.txt"

echo "⚙️  3/4 Creando el servicio $NOMBRE_SERVICIO..."
# "tee" escribe el texto en un archivo que requiere permisos de administrador.
sudo tee "/etc/systemd/system/$NOMBRE_SERVICIO.service" > /dev/null <<EOF
[Unit]
Description=Grabador de telemetría de paneles solares de la ISS
# Esperar a tener internet antes de arrancar
After=network-online.target
Wants=network-online.target

[Service]
User=$USUARIO
WorkingDirectory=$CARPETA
ExecStart=$CARPETA/.venv/bin/python $CARPETA/grabar_paneles.py
# Si el programa se cae por cualquier motivo, reiniciarlo a los 30 segundos
Restart=always
RestartSec=30
# Que los print() aparezcan altiro en el log
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

echo "🚀 4/4 Activando y arrancando el servicio..."
sudo systemctl daemon-reload                      # que systemd lea el archivo nuevo
sudo systemctl enable --now "$NOMBRE_SERVICIO"     # enable = arrancar al encender; --now = y ahora mismo

sleep 15
echo
echo "✅ Listo. Estado actual:"
systemctl status "$NOMBRE_SERVICIO" --no-pager --lines=8 || true
echo
echo "Comandos útiles:"
echo "  Ver el log en vivo:   journalctl -u $NOMBRE_SERVICIO -f"
echo "  Detener:              sudo systemctl stop $NOMBRE_SERVICIO"
echo "  Reiniciar:            sudo systemctl restart $NOMBRE_SERVICIO"
echo "  Ver los datos:        ls -lh $CARPETA/datos/"
