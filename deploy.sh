#!/bin/bash
set -e

echo "=== BoulderCup Deployment Started ==="

# Pull latest changes
echo "Pulling latest changes from deploy branch..."
git pull origin deploy

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Set Django settings for production
export DJANGO_SETTINGS_MODULE=web_project.settings.prod

# Install/update dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Run migrations
echo "Running database migrations..."
python3 manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python3 manage.py collectstatic --noinput

# Restart the service
echo "Restarting BoulderCup service..."
sudo systemctl restart bouldercup

# Check service status
echo "Checking service status..."
sudo systemctl status bouldercup --no-pager

echo "=== Deployment Complete ==="
