#!/usr/bin/env bash
# One-shot install on a fresh Ubuntu 24.04 VM. Run as a user with sudo. Idempotent.
set -euo pipefail
sudo apt-get update -qq && sudo apt-get install -y -qq python3 python3-venv python3-pip git make
APP=/opt/qr-research
sudo mkdir -p $APP && sudo chown "$USER" $APP
if [ ! -d $APP/.git ]; then git clone "${REPO_URL:?set REPO_URL}" $APP; else git -C $APP pull --ff-only; fi
cd $APP
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt
[ -f .env ] || { cp .env.example .env; echo ">> edit $APP/.env then re-run"; }
sudo cp deploy/qr-research.service deploy/qr-research.timer /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now qr-research.timer
systemctl list-timers qr-research.timer --no-pager
echo "installed. logs: journalctl -u qr-research -n 100"
