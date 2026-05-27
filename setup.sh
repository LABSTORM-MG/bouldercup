#!/bin/bash
# BoulderCup one-time setup script.
# Run this from the project root after cloning the repository.
# Clone with: git clone https://github.com/LABSTORM-MG/bouldercup.git
set -e

# ── Colours ──────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'
step()  { echo -e "\n${BOLD}${GREEN}[$1/6]${NC} $2"; }
info()  { echo "       $1"; }
error() { echo -e "\n${RED}Error:${NC} $1\n"; exit 1; }

# ── Sanity check ─────────────────────────────────────────────────
[ -f "manage.py" ] || error "Run this script from the BoulderCup project root (where manage.py lives)."

APP_DIR=$(pwd)
APP_USER=$(whoami)

# ── Collect inputs ────────────────────────────────────────────────
echo ""
echo -e "${BOLD}BoulderCup Setup${NC}"
echo "════════════════"
echo ""

read -p "  Domain or IP  (e.g. bouldercup.example.com): " DOMAIN
[ -z "$DOMAIN" ] && error "Domain is required."

read -p "  Admin username: " ADMIN_USER
[ -z "$ADMIN_USER" ] && error "Admin username is required."

read -p "  Admin email   [admin@example.com]: " ADMIN_EMAIL
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@example.com}

while true; do
    read -s -p "  Admin password: " ADMIN_PASSWORD; echo ""
    [ ${#ADMIN_PASSWORD} -ge 8 ] || { echo "       Password must be at least 8 characters."; continue; }
    read -s -p "  Confirm password: " ADMIN_PASSWORD_CONFIRM; echo ""
    [ "$ADMIN_PASSWORD" = "$ADMIN_PASSWORD_CONFIRM" ] && break
    echo "       Passwords don't match, try again."
done

echo ""
echo -e "  Domain:      ${YELLOW}$DOMAIN${NC}"
echo -e "  Admin user:  ${YELLOW}$ADMIN_USER${NC}"
echo -e "  Admin email: ${YELLOW}$ADMIN_EMAIL${NC}"
echo ""
read -p "  Proceed? [y/N] " CONFIRM
[[ "$CONFIRM" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }

# ── 1 / System dependencies ───────────────────────────────────────
step 1 "Installing system dependencies"
sudo apt-get update -q
sudo apt-get install -y -q \
    python3 python3-pip python3-venv git nginx \
    libcairo2 libpango-1.0-0 libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 libffi-dev shared-mime-info fonts-liberation
info "Done."

# ── 2 / Python environment ────────────────────────────────────────
step 2 "Setting up Python environment"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
info "Done."

# ── 3 / Configuration ─────────────────────────────────────────────
step 3 "Generating configuration (.env)"
# Use Python to write the file — avoids shell escaping issues with the secret key
.venv/bin/python - <<PYEOF
from django.core.management.utils import get_random_secret_key
key = get_random_secret_key()
with open('.env', 'w') as f:
    f.write(f'DJANGO_SECRET_KEY={key}\n')
    f.write(f'DJANGO_ALLOWED_HOSTS=$DOMAIN,127.0.0.1,localhost\n')
print(f'       Secret key generated and saved to .env')
PYEOF

# ── 4 / Database, static files, and admin account ─────────────────
step 4 "Setting up database and admin account"
export DJANGO_SETTINGS_MODULE=web_project.settings.prod
python3 manage.py migrate --noinput
python3 manage.py collectstatic --noinput -v 0

DJANGO_SUPERUSER_PASSWORD="$ADMIN_PASSWORD" \
    python3 manage.py createsuperuser \
        --username "$ADMIN_USER" \
        --email    "$ADMIN_EMAIL" \
        --noinput
info "Admin account '$ADMIN_USER' created."

# ── 5 / systemd service ───────────────────────────────────────────
step 5 "Installing systemd service"
sudo mkdir -p /var/log/bouldercup
sudo chown "$APP_USER:$APP_USER" /var/log/bouldercup

sed "s/YOUR_USER/$APP_USER/g" deploy/bouldercup.service \
    | sudo tee /etc/systemd/system/bouldercup.service > /dev/null

sudo systemctl daemon-reload
sudo systemctl enable bouldercup
sudo systemctl start bouldercup
info "Service enabled and started."

# ── 6 / nginx ─────────────────────────────────────────────────────
step 6 "Configuring nginx"
sed "s/yourdomain.com/$DOMAIN/g" deploy/nginx.conf \
    | sudo tee /etc/nginx/sites-available/bouldercup > /dev/null

sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -s /etc/nginx/sites-available/bouldercup /etc/nginx/sites-enabled/bouldercup
sudo nginx -t -q
sudo systemctl restart nginx
info "nginx configured and restarted."

# ── Done ──────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}✓ Setup complete!${NC}"
echo ""
echo -e "  App:    http://$DOMAIN"
echo -e "  Admin:  http://$DOMAIN/myadmin  (login: ${YELLOW}$ADMIN_USER${NC})"
echo ""
echo "  To deploy updates later, run:  ./deploy.sh"
echo ""
