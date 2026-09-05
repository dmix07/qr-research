# Deploy — one Claude Code session

1. Dustin: create the smallest Ubuntu 24.04 VM at any provider (~$5–10/mo), note its IP, put the SSH key on it.
2. Claude Code, from Dustin's laptop:
       ssh ubuntu@<ip> 'REPO_URL=<github url> bash -s' < deploy/install.sh
   then fill `/opt/qr-research/.env` over ssh (values from Dustin's .env), and `sudo systemctl start qr-research.service` for a first run.
3. Verify: `journalctl -u qr-research -n 50` ends with every source `ok`.

What runs: every Monday 06:15 local, the timer pulls the latest code, runs all connectors, generates candidates, screens, delivers to Airtable, checks health. On any failure `alert_on_failure.sh` emails/webhooks Dustin. On success it says nothing.

Data lives at `/opt/qr-research/data` — raw snapshots are never deleted. Back up: `deploy/backup_to_drive.md` (Google Drive mirror via rclone, optional).
