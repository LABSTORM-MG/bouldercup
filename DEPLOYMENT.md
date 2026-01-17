# BoulderCup Deployment Guide

Complete guide for deploying BoulderCup to your Ubuntu VM using GitHub Actions for automatic deployment.

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Part A: VM Setup (One-Time)](#part-a-vm-setup-one-time)
4. [Part B: GitHub Setup (One-Time)](#part-b-github-setup-one-time)
5. [Part C: First Deployment](#part-c-first-deployment)
6. [Part D: Regular Deployments](#part-d-regular-deployments)
7. [Monitoring & Troubleshooting](#monitoring--troubleshooting)
8. [Security Model](#security-model)

---

## Overview

**Deployment Flow:**
```
Local Machine → Push to deploy branch → GitHub Actions → SSH to VM → Run deploy.sh → Restart service
```

**VM Details:**
- Admin SSH: `ssh -p 2222 labstorm-ssh@labstorm.net`
- Deploy user: `bouldercup-deploy` (automated deployments only)
- Web: `https://bouldercup.labstorm.net`
- Application directory: `/opt/bouldercup`

---

## Prerequisites

Before starting, ensure you have:
- [ ] Ubuntu VM accessible via SSH
- [ ] External reverse proxy already configured for HTTPS
- [ ] GitHub repository for the project
- [ ] Admin access to both VM and GitHub repository

---

## Part A: VM Setup (One-Time)

Complete these steps once to prepare your VM for automated deployments.

### A1. Create Dedicated Deployment User

SSH into your VM as admin:
```bash
ssh -p 2222 labstorm-ssh@labstorm.net
```

Create a dedicated user for deployments (principle of least privilege):
```bash
# Create user without password (SSH key only)
sudo useradd -m -s /bin/bash bouldercup-deploy

# Create SSH directory with proper ownership
sudo mkdir -p /home/bouldercup-deploy/.ssh
sudo chown -R bouldercup-deploy:bouldercup-deploy /home/bouldercup-deploy/.ssh
sudo chmod 700 /home/bouldercup-deploy/.ssh
```

### A2. Prepare Directories

Create required directories with proper ownership:
```bash
sudo mkdir -p /opt/bouldercup
sudo mkdir -p /var/log/bouldercup
sudo chown -R bouldercup-deploy:bouldercup-deploy /opt/bouldercup
sudo chown -R bouldercup-deploy:bouldercup-deploy /var/log/bouldercup
```

### A3. Install Dependencies

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git nginx
```

### A4. Generate SSH Key for GitHub Actions

Generate an SSH key that GitHub Actions will use to connect:
```bash
sudo -u bouldercup-deploy ssh-keygen -t ed25519 -C "github-deploy-bouldercup" -f /home/bouldercup-deploy/.ssh/id_ed25519 -N ""
```

Display the **private key** (needed for GitHub Secrets):
```bash
sudo cat /home/bouldercup-deploy/.ssh/id_ed25519
```

**Copy the entire output** (including `-----BEGIN` and `-----END` lines) - you'll need this for GitHub Secrets in Part B.

Authorize the public key:
```bash
sudo cat /home/bouldercup-deploy/.ssh/id_ed25519.pub | sudo tee -a /home/bouldercup-deploy/.ssh/authorized_keys
sudo chmod 600 /home/bouldercup-deploy/.ssh/authorized_keys
sudo chown bouldercup-deploy:bouldercup-deploy /home/bouldercup-deploy/.ssh/authorized_keys
```

Test the SSH key locally:
```bash
sudo -u bouldercup-deploy ssh -p 2222 -o StrictHostKeyChecking=no bouldercup-deploy@localhost "echo 'SSH key test successful'"
```

### A5. Clone Repository

Switch to deployment user and clone:
```bash
sudo -u bouldercup-deploy -i
cd /opt/bouldercup
git clone https://github.com/YOUR_USERNAME/bouldercup.git .
git checkout master  # We'll create deploy branch later
```

### A6. Setup Python Environment

Still as `bouldercup-deploy` user:
```bash
cd /opt/bouldercup
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### A7. Configure Environment Variables

Generate a Django secret key:
```bash
python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

Create the `.env` file:
```bash
cat > .env << 'EOF'
# Django Secret Key - Generate with command above
DJANGO_SECRET_KEY=your-secret-key-here

# Allowed hosts (comma-separated, include internal IP and domain)
DJANGO_ALLOWED_HOSTS=bouldercup.labstorm.net,192.168.178.53

# Database (optional - defaults to SQLite)
# DATABASE_URL=postgresql://user:password@localhost/bouldercup

# Redis (optional - for production caching)
# REDIS_URL=redis://127.0.0.1:6379/1

# Email settings (optional - for notifications)
# EMAIL_HOST=smtp.example.com
# EMAIL_PORT=587
# EMAIL_USE_TLS=True
# EMAIL_HOST_USER=your-email@example.com
# EMAIL_HOST_PASSWORD=your-password
EOF
```

Edit the file to add your generated secret key:
```bash
nano .env
```

Replace `your-secret-key-here` with the generated key, then save and exit (Ctrl+X, Y, Enter).

### A8. Initialize Database

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

### A9. Setup systemd Service

As admin user (`labstorm-ssh`), create the systemd service file:
```bash
sudo tee /etc/systemd/system/bouldercup.service > /dev/null << 'EOF'
[Unit]
Description=BoulderCup Django Application
After=network.target

[Service]
Type=notify
User=bouldercup-deploy
Group=bouldercup-deploy
WorkingDirectory=/opt/bouldercup
Environment="DJANGO_SETTINGS_MODULE=web_project.settings.prod"
ExecStart=/opt/bouldercup/.venv/bin/gunicorn \
    --workers 3 \
    --bind unix:/opt/bouldercup/bouldercup.sock \
    --timeout 60 \
    --access-logfile /var/log/bouldercup/access.log \
    --error-logfile /var/log/bouldercup/error.log \
    web_project.wsgi:application

# Restart policy
Restart=on-failure
RestartSec=5s

# Security
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable bouldercup
sudo systemctl start bouldercup
sudo systemctl status bouldercup
```

You should see "active (running)".

### A10. Configure Nginx

Create the nginx configuration:
```bash
sudo tee /etc/nginx/sites-available/bouldercup > /dev/null << 'EOF'
# BoulderCup Nginx Configuration
upstream bouldercup {
    server unix:/opt/bouldercup/bouldercup.sock fail_timeout=0;
}

server {
    listen 80;
    server_name bouldercup.labstorm.net;

    client_max_body_size 10M;

    # Static files
    location /static/ {
        alias /opt/bouldercup/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media files
    location /media/ {
        alias /opt/bouldercup/media/;
        expires 7d;
    }

    # Main application
    location / {
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Host $http_host;
        proxy_redirect off;
        proxy_pass http://bouldercup;
    }
}
EOF
```

Enable the site and remove the default:
```bash
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -s /etc/nginx/sites-available/bouldercup /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### A11. Make Deployment Script Executable

```bash
sudo chmod +x /opt/bouldercup/deploy.sh
```

### A12. Configure Sudoers for Deploy User

The deploy user needs minimal permissions to restart the service:

```bash
sudo visudo -f /etc/sudoers.d/bouldercup-deploy
```

Add these lines:
```
# Allow bouldercup-deploy to restart and check service status only
bouldercup-deploy ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart bouldercup, /usr/bin/systemctl status bouldercup*
```

**Important notes:**
- Use `/usr/bin/systemctl` (not `/bin/systemctl`) - this is the correct path on Ubuntu 24.04
- The `*` after `bouldercup` allows systemctl flags like `--no-pager`

Save and exit (Ctrl+X, Y, Enter).

Set proper permissions:
```bash
sudo chmod 0440 /etc/sudoers.d/bouldercup-deploy
```

### A13. Test Manual Deployment

Test that the deployment script works:
```bash
sudo -u bouldercup-deploy -i
cd /opt/bouldercup
./deploy.sh
exit
```

If successful, your application should now be accessible at `https://bouldercup.labstorm.net`

**✅ VM Setup Complete!** Now proceed to Part B for GitHub setup.

---

## Part B: GitHub Setup (One-Time)

Configure GitHub repository and GitHub Actions for automated deployments.

### B1. Add SSH Private Key to GitHub Secrets

1. Go to your GitHub repository: `https://github.com/YOUR_USERNAME/bouldercup`
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Configure the secret:
   - **Name:** `DEPLOY_SSH_PRIVATE_KEY`
   - **Value:** Paste the private key from step A4 (the output of `sudo cat /home/bouldercup-deploy/.ssh/id_ed25519`)
5. Click **Add secret**

### B2. Verify GitHub Actions Workflow File

The workflow file should already exist in your repository at `.github/workflows/deploy.yml`. Verify it's present:

```bash
# On your local machine (in the bouldercup repo)
cat .github/workflows/deploy.yml
```

You should see a workflow that:
- Triggers on push to `deploy` branch
- Uses `appleboy/ssh-action` to connect to your VM
- Runs `./deploy.sh` on the VM

### B3. Create and Push Deploy Branch

On your local machine:
```bash
# Make sure you're up to date
git checkout master
git pull origin master

# Create deploy branch from master
git checkout -b deploy

# Push deploy branch to GitHub
git push origin deploy
```

**⚠️ Important:** This first push will **trigger a deployment** immediately! Make sure VM setup (Part A) is complete.

### B4. Verify GitHub Actions Ran

1. Go to your GitHub repository
2. Click on the **Actions** tab
3. You should see a workflow run for "Deploy to Production"
4. Click on it to see the logs

If successful, you'll see:
- SSH connection established
- Code pulled from git
- Dependencies installed
- Migrations run
- Static files collected
- Service restarted

**✅ GitHub Setup Complete!** Your automated deployment pipeline is now active.

---

## Part C: First Deployment

Your first deployment should have run automatically when you pushed the `deploy` branch in step B3.

### C1. Check Deployment Status

**On GitHub:**
1. Go to **Actions** tab in your repository
2. Check the latest workflow run
3. Review the logs for any errors

**On your VM:**
```bash
ssh -p 2222 labstorm-ssh@labstorm.net

# Check service status
sudo systemctl status bouldercup

# Check recent logs
sudo journalctl -u bouldercup -n 50

# Check Django logs
tail -f /var/log/bouldercup/django.log

# Check Gunicorn logs
tail -f /var/log/bouldercup/error.log
```

### C2. Test the Application

Visit `https://bouldercup.labstorm.net` and verify:
- [ ] Application loads
- [ ] Login works
- [ ] Static files load correctly (CSS, JS)
- [ ] Admin panel accessible at `/admin`

If everything works, your deployment pipeline is ready!

---

## Part D: Regular Deployments

Now that setup is complete, deploying updates is simple.

### D1. Regular Deployment Workflow

On your local machine:

```bash
# 1. Make changes on master branch
git checkout master
# ... make your changes ...
git add .
git commit -m "Your changes"
git push origin master

# 2. Merge to deploy branch
git checkout deploy
git merge master

# 3. Push to trigger deployment
git push origin deploy
```

### D2. Watch Deployment Progress

GitHub Actions will automatically:
1. Connect to your VM via SSH
2. Pull the latest code from `deploy` branch
3. Install/update dependencies
4. Run database migrations
5. Collect static files
6. Restart the service

Monitor progress:
- **GitHub:** Actions tab shows real-time logs
- **VM:** `sudo journalctl -u bouldercup -f` shows service restart

### D3. Manual Deployment (If Needed)

If you need to deploy manually without GitHub Actions:

```bash
ssh -p 2222 labstorm-ssh@labstorm.net
sudo -u bouldercup-deploy -i
cd /opt/bouldercup
./deploy.sh
exit
```

---

## Monitoring & Troubleshooting

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

# Recent service logs (last 100 lines)
sudo journalctl -u bouldercup -n 100
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

#### 503 Service Unavailable

Check if gunicorn is running:
```bash
sudo systemctl status bouldercup
```

Check socket file exists:
```bash
ls -l /opt/bouldercup/bouldercup.sock
```

Check nginx error logs:
```bash
sudo tail /var/log/nginx/error.log
```

#### Static Files Not Loading

Collect static files manually:
```bash
sudo -u bouldercup-deploy -i
cd /opt/bouldercup
source .venv/bin/activate
export DJANGO_SETTINGS_MODULE=web_project.settings.prod
python3 manage.py collectstatic --noinput
exit
sudo systemctl restart bouldercup
```

#### Database Migration Issues

Run migrations manually:
```bash
sudo -u bouldercup-deploy -i
cd /opt/bouldercup
source .venv/bin/activate
export DJANGO_SETTINGS_MODULE=web_project.settings.prod
python3 manage.py migrate
exit
sudo systemctl restart bouldercup
```

#### GitHub Actions Deployment Fails

**SSH Connection Error:**
- Verify `DEPLOY_SSH_PRIVATE_KEY` secret is set correctly in GitHub
- Check that the public key is in `/home/bouldercup-deploy/.ssh/authorized_keys`
- Test SSH manually: `ssh -p 2222 bouldercup-deploy@labstorm.net`

**Permission Denied:**
- Verify deploy user owns `/opt/bouldercup`: `ls -la /opt/`
- Check sudoers file: `sudo cat /etc/sudoers.d/bouldercup-deploy`

**Git Pull Fails:**
- SSH into VM as deploy user: `sudo -u bouldercup-deploy -i`
- Try pulling manually: `cd /opt/bouldercup && git pull origin deploy`
- Check git configuration: `git config --list`

---

## Security Model

### Why a Dedicated Deployment User?

This deployment uses a **dedicated deployment user** with minimal privileges.

**Risk:** The GitHub Actions SSH key (stored in GitHub Secrets) could be compromised through:
- Compromised GitHub account
- Malicious pull requests (if repo becomes public)
- Supply chain attacks on GitHub Actions

**Mitigation:** If the deploy key is compromised, the attacker can **only**:
- Deploy code to `/opt/bouldercup`
- Restart the `bouldercup` service
- Write to `/var/log/bouldercup`

The attacker **cannot**:
- Access your admin account (`labstorm-ssh`)
- Read other users' files
- Modify system configuration
- Access other services on the VM
- Execute arbitrary commands with sudo (only specific systemctl commands)

### User Separation

- **`labstorm-ssh`**: Your personal admin account for manual SSH access and system administration
- **`bouldercup-deploy`**: Automated deployment account used exclusively by GitHub Actions

### Security Checklist

#### Application Security
- [x] `DEBUG = False` in production settings
- [x] `SECRET_KEY` loaded from environment variable (not hardcoded)
- [x] HTTPS enabled (handled by your reverse proxy)
- [x] Secure cookie flags enabled (`SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`)
- [x] `.env` file not committed to git (in `.gitignore`)
- [x] Log files have proper permissions

#### Deployment Security (Principle of Least Privilege)
- [x] Dedicated deploy user (`bouldercup-deploy`) - not your personal SSH account
- [x] Deploy user has **no password** - SSH key authentication only
- [x] Deploy user can **only** restart bouldercup service (via sudoers)
- [x] Deploy user owns **only** `/opt/bouldercup` and `/var/log/bouldercup`
- [x] GitHub Actions SSH key stored in secrets (scoped to deploy user only)
- [x] If deploy key is compromised, attacker gets **minimal** access

---

## Backup Strategy

### Database Backup (Optional Manual Setup)

Create a backup script at `/opt/bouldercup/backup.sh`:
```bash
#!/bin/bash
BACKUP_DIR="/opt/bouldercup/backups"
mkdir -p $BACKUP_DIR
cp /opt/bouldercup/db.sqlite3 "$BACKUP_DIR/db.sqlite3.$(date +%Y%m%d_%H%M%S).bak"
# Keep only last 7 days
find $BACKUP_DIR -name "*.bak" -mtime +7 -delete
```

Make executable:
```bash
sudo chmod +x /opt/bouldercup/backup.sh
sudo chown bouldercup-deploy:bouldercup-deploy /opt/bouldercup/backup.sh
```

Add to deploy user's crontab:
```bash
sudo -u bouldercup-deploy crontab -e
# Add: 0 2 * * * /opt/bouldercup/backup.sh
```

---

## Updating Deployment Configuration

If you need to modify the deployment process:

**For code and deployment script changes:**
1. Update files locally (e.g., `deploy.sh`, Django code)
2. Commit and push to `master` branch
3. Merge `master` into `deploy` branch and push (triggers deployment)

**For infrastructure changes (systemd, nginx):**
- These configs are created directly on the VM during initial setup
- To modify: SSH to VM, edit `/etc/systemd/system/bouldercup.service` or `/etc/nginx/sites-available/bouldercup`
- After changes, reload and restart:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart bouldercup
   sudo systemctl restart nginx
   ```

---

## Production URL

**Application:** https://bouldercup.labstorm.net
**Admin Panel:** https://bouldercup.labstorm.net/admin

---

## Summary

**One-Time Setup:**
1. Complete Part A (VM Setup)
2. Complete Part B (GitHub Setup)
3. Verify Part C (First Deployment)

**Regular Workflow:**
1. Develop on `master` branch
2. Merge to `deploy` branch
3. Push to trigger automatic deployment
4. Monitor via GitHub Actions and VM logs

**Need Help?**
- Check logs: `sudo journalctl -u bouldercup -f`
- Restart service: `sudo systemctl restart bouldercup`
- Manual deploy: SSH to VM, run `./deploy.sh` as `bouldercup-deploy`
