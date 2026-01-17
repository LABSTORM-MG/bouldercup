# BoulderCup Deployment Guide

This guide covers deploying BoulderCup to your Ubuntu VM using GitHub Actions for automatic deployment from the `deploy` branch.

## Overview

**Deployment Flow:**
1. Push code to `deploy` branch on GitHub
2. GitHub Actions triggers
3. SSH into VM and runs `deploy.sh`
4. Application is updated and restarted automatically

**VM Details:**
- Admin SSH: `ssh -p 2222 labstorm-ssh@labstorm.net`
- Deploy user: `bouldercup-deploy` (created during setup)
- Web: `https://bouldercup.labstorm.net`
- Application directory: `/opt/bouldercup`

---

## Security Model

This deployment uses a **dedicated deployment user** with minimal privileges:

**Why a separate user?**
1. **Least Privilege**: The GitHub Actions SSH key (stored in GitHub Secrets) could be compromised through various means:
   - Compromised GitHub account
   - Malicious pull requests
   - Supply chain attacks

2. **Blast Radius Containment**: If the deploy key is compromised, the attacker can only:
   - Deploy code to `/opt/bouldercup`
   - Restart the `bouldercup` service
   - Write to `/var/log/bouldercup`

   They **cannot**:
   - Access your admin account
   - Read other users' files
   - Modify system configuration
   - Access other services on the VM

3. **Audit Trail**: Separate users create clear audit trails distinguishing automated deployments from manual admin actions.

**User Separation:**
- `labstorm-ssh`: Your admin account for manual SSH access
- `bouldercup-deploy`: Automated deployment account (GitHub Actions only)

---

## Initial VM Setup

### 1. Create Dedicated Deployment User

SSH into your VM as admin:
```bash
ssh -p 2222 labstorm-ssh@labstorm.net
```

Create a dedicated user for deployments (principle of least privilege):
```bash
# Create user without password (SSH key only)
sudo useradd -m -s /bin/bash bouldercup-deploy

# Create SSH directory
sudo mkdir -p /home/bouldercup-deploy/.ssh
sudo chmod 700 /home/bouldercup-deploy/.ssh
```

### 2. Prepare Directories

Create required directories with proper ownership:
```bash
sudo mkdir -p /opt/bouldercup
sudo mkdir -p /var/log/bouldercup
sudo chown -R bouldercup-deploy:bouldercup-deploy /opt/bouldercup
sudo chown -R bouldercup-deploy:bouldercup-deploy /var/log/bouldercup
```

### 3. Install Dependencies

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git nginx
```

### 4. Clone the Repository

Switch to the deployment user and clone the repository:
```bash
sudo -u bouldercup-deploy -i
cd /opt/bouldercup
git clone https://github.com/YOUR_USERNAME/bouldercup.git .
git checkout deploy
```

### 5. Create Python Virtual Environment

Still as `bouldercup-deploy` user:
```bash
cd /opt/bouldercup
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 6. Configure Environment Variables

Generate a Django secret key:
```bash
python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

Create the `.env` file:
```bash
cp .env.production.example .env
nano .env
```

Update `.env` with your values:
```
DJANGO_SECRET_KEY=<paste-generated-secret-key>
DJANGO_ALLOWED_HOSTS=bouldercup.labstorm.net
```

### 7. Initialize Database

Still as `bouldercup-deploy` user:
```bash
cd /opt/bouldercup
source .venv/bin/activate
export DJANGO_SETTINGS_MODULE=web_project.settings.prod
python3 manage.py migrate
python3 manage.py collectstatic --noinput
```

Create a superuser for admin access:
```bash
python3 manage.py createsuperuser
```

Exit back to admin user:
```bash
exit  # Return to labstorm-ssh user
```

### 8. Set Up systemd Service

As admin user (`labstorm-ssh`), copy the service file:
```bash
sudo cp /opt/bouldercup/bouldercup.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable bouldercup
sudo systemctl start bouldercup
sudo systemctl status bouldercup
```

### 9. Configure Nginx

Your VM already has a reverse proxy, but you need to configure the local nginx to serve the app:

```bash
sudo cp /opt/bouldercup/nginx.conf.example /etc/nginx/sites-available/bouldercup
sudo ln -s /etc/nginx/sites-available/bouldercup /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 10. Make Deployment Script Executable

```bash
sudo chmod +x /opt/bouldercup/deploy.sh
```

### 11. Configure Sudoers for Restricted Deploy User

The deploy user needs minimal permissions to restart the service. Create a sudoers file:

```bash
sudo visudo -f /etc/sudoers.d/bouldercup-deploy
```

Add these restricted permissions:
```
# Allow bouldercup-deploy to restart and check service status only
bouldercup-deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart bouldercup, /bin/systemctl status bouldercup
```

Set proper permissions:
```bash
sudo chmod 0440 /etc/sudoers.d/bouldercup-deploy
```

---

## GitHub Setup

### 1. Generate SSH Deploy Key

On your VM, **as admin user** (`labstorm-ssh`), create an SSH key for the deploy user:
```bash
sudo -u bouldercup-deploy ssh-keygen -t ed25519 -C "github-deploy-bouldercup" -f /home/bouldercup-deploy/.ssh/id_ed25519 -N ""
```

Display the **private key** to copy:
```bash
sudo cat /home/bouldercup-deploy/.ssh/id_ed25519
```

Copy the **entire output** (including `-----BEGIN` and `-----END` lines).

### 2. Add SSH Key to GitHub Secrets

1. Go to your GitHub repository
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `DEPLOY_SSH_PRIVATE_KEY`
5. Value: Paste the private key from above
6. Click **Add secret**

### 3. Authorize the Public Key on VM

Add the public key to the deploy user's authorized_keys:
```bash
sudo cat /home/bouldercup-deploy/.ssh/id_ed25519.pub | sudo tee -a /home/bouldercup-deploy/.ssh/authorized_keys
sudo chmod 600 /home/bouldercup-deploy/.ssh/authorized_keys
sudo chown bouldercup-deploy:bouldercup-deploy /home/bouldercup-deploy/.ssh/authorized_keys
```

### 4. Test SSH Connection

From your local machine (save the private key temporarily to test):
```bash
# Save private key to a file locally first, then:
chmod 600 /tmp/deploy_key
ssh -p 2222 -i /tmp/deploy_key bouldercup-deploy@labstorm.net "echo 'Connection successful'"
rm /tmp/deploy_key  # Clean up after testing
```

Or test directly on the VM:
```bash
sudo -u bouldercup-deploy ssh -p 2222 -o StrictHostKeyChecking=no bouldercup-deploy@localhost "echo 'Local connection successful'"
```

---

## Deployment Workflow

### Automatic Deployment

Simply push to the `deploy` branch:
```bash
git checkout deploy
git merge master  # or your main development branch
git push origin deploy
```

GitHub Actions will automatically:
1. Connect to your VM via SSH
2. Pull the latest code
3. Install dependencies
4. Run migrations
5. Collect static files
6. Restart the service

### Manual Deployment

If needed, you can deploy manually as the deploy user:
```bash
ssh -p 2222 labstorm-ssh@labstorm.net
sudo -u bouldercup-deploy -i
cd /opt/bouldercup
./deploy.sh
```

---

## Monitoring and Troubleshooting

### Check Service Status
```bash
sudo systemctl status bouldercup
```

### View Logs
```bash
# Django application logs
tail -f /var/log/bouldercup/django.log

# Gunicorn access logs
tail -f /var/log/bouldercup/access.log

# Gunicorn error logs
tail -f /var/log/bouldercup/error.log

# Systemd service logs
sudo journalctl -u bouldercup -f
```

### Restart Service
```bash
sudo systemctl restart bouldercup
```

### Check Nginx
```bash
sudo nginx -t
sudo systemctl status nginx
tail -f /var/log/nginx/error.log
```

### Common Issues

**503 Service Unavailable:**
- Check if gunicorn is running: `sudo systemctl status bouldercup`
- Check socket file exists: `ls -l /opt/bouldercup/bouldercup.sock`
- Check nginx error logs: `sudo tail /var/log/nginx/error.log`

**Static files not loading:**
```bash
cd /opt/bouldercup
source .venv/bin/activate
export DJANGO_SETTINGS_MODULE=web_project.settings.prod
python3 manage.py collectstatic --noinput
```

**Database migrations needed:**
```bash
cd /opt/bouldercup
source .venv/bin/activate
export DJANGO_SETTINGS_MODULE=web_project.settings.prod
python3 manage.py migrate
sudo systemctl restart bouldercup
```

---

## Security Checklist

### Application Security
- [x] `DEBUG = False` in production settings
- [x] `SECRET_KEY` loaded from environment variable
- [x] HTTPS enabled (handled by your reverse proxy)
- [x] Secure cookie flags enabled
- [x] `.env` file not committed to git (in `.gitignore`)
- [x] Log files with proper permissions

### Deployment Security (Principle of Least Privilege)
- [x] **Dedicated deploy user** (`bouldercup-deploy`) - not your personal SSH account
- [x] Deploy user has **no password** - SSH key authentication only
- [x] Deploy user can **only** restart bouldercup service (via sudoers)
- [x] Deploy user owns **only** `/opt/bouldercup` and `/var/log/bouldercup`
- [x] GitHub Actions SSH key stored in secrets (scoped to deploy user only)
- [x] If deploy key is compromised, attacker gets **minimal** access

**Security Benefits:**
- Compromised GitHub Actions key ≠ full system access
- Deploy user cannot access other services or data
- Clear audit trail (deploy vs admin actions)
- Follows principle of least privilege

---

## Backup Strategy

### Database Backup

Create a backup script at `/opt/bouldercup/backup.sh`:
```bash
#!/bin/bash
BACKUP_DIR="/opt/bouldercup/backups"
mkdir -p $BACKUP_DIR
cp /opt/bouldercup/db.sqlite3 "$BACKUP_DIR/db.sqlite3.$(date +%Y%m%d_%H%M%S).bak"
# Keep only last 7 days
find $BACKUP_DIR -name "*.bak" -mtime +7 -delete
```

Add to crontab:
```bash
crontab -e
# Add: 0 2 * * * /opt/bouldercup/backup.sh
```

---

## Updating the Deployment

To modify the deployment process:

1. Update files locally (`deploy.sh`, `bouldercup.service`, etc.)
2. Commit and push to `deploy` branch
3. SSH to VM and manually update if needed:
   ```bash
   sudo cp /opt/bouldercup/bouldercup.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl restart bouldercup
   ```

---

## Production URL

Your application will be accessible at: **https://bouldercup.labstorm.net**

Admin panel: **https://bouldercup.labstorm.net/admin**
