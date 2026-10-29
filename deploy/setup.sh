#!/usr/bin/env bash
# Instala o actualiza BackToYou en un servidor Ubuntu 24.04 (por ejemplo EC2).
#
# El proyecto debe estar en /home/ubuntu/BackToYou. La primera vez:
#     bash deploy/setup.sh <IP o dominio del servidor>
# Para actualizar, despues de "git pull":
#     bash deploy/setup.sh
#
# Se puede correr las veces que haga falta: nunca toca la base de datos, las
# fotos subidas ni la configuracion que ya exista en /etc/backtoyou.env.
set -euo pipefail

APP_DIR=/home/ubuntu/BackToYou
ENV_FILE=/etc/backtoyou.env

cd "$APP_DIR"

sudo apt-get update -q
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q python3-venv nginx

# Nginx corre como www-data y necesita entrar a la carpeta personal para
# leer staticfiles/ y media_local/.
chmod o+x /home/ubuntu

[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

# La configuracion se crea solo la primera vez, con una clave secreta nueva.
# Despues se cambia a mano: sudo nano /etc/backtoyou.env
if ! sudo test -f "$ENV_FILE"; then
    HOST="${1:?La primera vez hay que pasar la IP o el dominio del servidor}"
    SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
    sudo install -m 600 /dev/null "$ENV_FILE"
    sudo tee "$ENV_FILE" > /dev/null <<EOF
DJANGO_SECRET_KEY=$SECRET
DJANGO_DEBUG=False
# Separados por comas si hay varios: 3.85.10.20,backtoyou.com
DJANGO_ALLOWED_HOSTS=$HOST

# Correo (RF39, RF15). Mientras esten comentados, los correos no salen y
# solo quedan en el registro: journalctl -u backtoyou
#EMAIL_HOST_USER=tu.cuenta@gmail.com
#EMAIL_HOST_PASSWORD=
#DEFAULT_FROM_EMAIL="BackToYou <tu.cuenta@gmail.com>"
EOF
fi

.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py seed_categories
.venv/bin/python manage.py collectstatic --noinput

sudo cp deploy/backtoyou.service /etc/systemd/system/backtoyou.service
if [ ! -f /etc/nginx/sites-available/backtoyou ]; then
    sudo cp deploy/nginx.conf /etc/nginx/sites-available/backtoyou
fi
sudo ln -sf /etc/nginx/sites-available/backtoyou /etc/nginx/sites-enabled/backtoyou
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t

sudo systemctl daemon-reload
sudo systemctl enable backtoyou
sudo systemctl restart backtoyou
sudo systemctl reload nginx

echo "BackToYou quedo corriendo."
