#!/bin/bash

#
# setup_backup_cron.sh
#
# Sets up automated database backups via cron for BoulderCup.
# Run this script once when setting up the production server.
#
# Usage:
#   ./setup_backup_cron.sh
#   ./setup_backup_cron.sh --remove  (to remove the cron job)
#

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
VENV_PATH="$PROJECT_DIR/.venv"
PYTHON_CMD="$VENV_PATH/bin/python3"
MANAGE_PY="$PROJECT_DIR/manage.py"
LOG_DIR="$PROJECT_DIR/logs"

# Backup interval (default: every 3 minutes)
BACKUP_INTERVAL="${BACKUP_INTERVAL:-3}"

# Cron job identifier
CRON_MARKER="# BoulderCup automated database backup"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "================================================"
echo "BoulderCup Automated Backup Setup"
echo "================================================"
echo

# Check if --remove flag is provided
if [[ "$1" == "--remove" ]]; then
    echo "Removing BoulderCup backup cron job..."

    # Remove the cron job
    (crontab -l 2>/dev/null | grep -v "$CRON_MARKER" | grep -v "backup_database") | crontab -

    echo -e "${GREEN}✓${NC} Cron job removed successfully"
    echo
    echo "You can verify with: crontab -l"
    exit 0
fi

# Verify project directory exists
if [[ ! -d "$PROJECT_DIR" ]]; then
    echo -e "${RED}✗${NC} Project directory not found: $PROJECT_DIR"
    exit 1
fi

# Verify virtual environment exists
if [[ ! -f "$PYTHON_CMD" ]]; then
    echo -e "${RED}✗${NC} Virtual environment not found at: $VENV_PATH"
    echo "Please create the virtual environment first:"
    echo "  python3 -m venv .venv"
    echo "  source .venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Verify manage.py exists
if [[ ! -f "$MANAGE_PY" ]]; then
    echo -e "${RED}✗${NC} manage.py not found at: $MANAGE_PY"
    exit 1
fi

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Test the backup command
echo "Testing backup command..."
if ! "$PYTHON_CMD" "$MANAGE_PY" backup_database 2>&1 | grep -q "Backup created"; then
    echo -e "${RED}✗${NC} Backup command failed. Please check your Django installation."
    exit 1
fi
echo -e "${GREEN}✓${NC} Backup command works"
echo

# Build cron command
CRON_COMMAND="*/$BACKUP_INTERVAL * * * * cd $PROJECT_DIR && $PYTHON_CMD $MANAGE_PY backup_database >> $LOG_DIR/backup.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "backup_database"; then
    echo -e "${YELLOW}⚠${NC}  A backup cron job already exists."
    echo
    crontab -l 2>/dev/null | grep "backup_database"
    echo
    read -p "Do you want to replace it? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Setup cancelled."
        exit 0
    fi

    # Remove existing cron job
    (crontab -l 2>/dev/null | grep -v "$CRON_MARKER" | grep -v "backup_database") | crontab -
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_MARKER"; echo "$CRON_COMMAND") | crontab -

echo
echo -e "${GREEN}✓${NC} Cron job installed successfully!"
echo
echo "Configuration:"
echo "  • Backup interval: Every $BACKUP_INTERVAL minutes"
echo "  • Backup directory: $PROJECT_DIR/backups/"
echo "  • Log file: $LOG_DIR/backup.log"
echo "  • Backup retention: 3 most recent backups (configured in settings)"
echo
echo "The backup command will run:"
echo "  $CRON_COMMAND"
echo
echo "Verify the cron job:"
echo "  crontab -l"
echo
echo "Monitor backup logs:"
echo "  tail -f $LOG_DIR/backup.log"
echo
echo "View recent backups:"
echo "  ls -lh $PROJECT_DIR/backups/"
echo
echo "To remove the cron job later:"
echo "  ./setup_backup_cron.sh --remove"
echo
echo -e "${GREEN}Setup complete!${NC}"
