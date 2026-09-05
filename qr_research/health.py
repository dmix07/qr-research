"""Print source health and exit non-zero if anything is not ok. Runs last in every workflow."""
import sys
from qr_research.connectors.base import db

rows = db().execute("SELECT source_id, health, last_success, last_volume, expected_min, expected_max, note FROM source_health").fetchall()
bad = 0
for r in rows:
    print(f"{r[0]:12} {r[1]:20} last={r[2]} vol={r[3]} band=[{r[4]},{r[5]}] {r[6] or ''}")
    bad += r[1] != "ok"
sys.exit(1 if bad else 0)
