# BoulderCup — Deployment Guide

How to deploy BoulderCup on a fresh Ubuntu server.
This guide assumes you're already on the server and comfortable with a terminal.

For the automated CI/CD pipeline (GitHub Actions), see [DEV_DEPLOYMENT.md](DEV_DEPLOYMENT.md).

---

## Setup

Clone the repository and run the setup script:

```bash
git clone https://github.com/LABSTORM-MG/bouldercup.git /opt/bouldercup
cd /opt/bouldercup
./setup.sh
```

The script will ask for:

| Prompt | Description |
|--------|-------------|
| **Domain or IP** | Where the app will be served (e.g. `bouldercup.example.com`) |
| **Admin username** | Login name for the `/myadmin` panel |
| **Admin email** | Email address for the admin account |
| **Admin password** | Password for the admin account (min. 8 characters) |

It then takes care of everything automatically: system dependencies, Python environment, database setup, static files, systemd service, and nginx.

When it's done you'll see:

```
✓ Setup complete!

  App:    http://yourdomain.com
  Admin:  http://yourdomain.com/myadmin  (login: youradmin)
```

---

## Deploying an Update

```bash
cd /opt/bouldercup
./deploy.sh
```

Pulls the latest code, installs any new dependencies, runs migrations, collects static files, and restarts the service.

---

## Logs and Troubleshooting

```bash
# Is the app running?
sudo systemctl status bouldercup

# Live logs
sudo journalctl -u bouldercup -f

# Gunicorn error log
tail -f /var/log/bouldercup/error.log
```

| Problem | Solution |
|---------|----------|
| 503 error in browser | `sudo systemctl restart bouldercup` and check logs |
| CSS/JS not loading | `python3 manage.py collectstatic --noinput` then restart |
| App crashes on startup | `python3 manage.py check` to see config errors |
| Nginx shows default page | `sudo nginx -t` and confirm the symlink exists in `/etc/nginx/sites-enabled/` |
