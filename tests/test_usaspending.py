import pytest
from qr_research.connectors import usaspending
from qr_research.connectors.base import DB_PATH


@pytest.fixture
def isolated_db(monkeypatch, tmp_path):
    from qr_research.connectors import base
    monkeypatch.setattr(base, "DB_PATH", tmp_path / "t.sqlite")
    monkeypatch.setattr(base, "DATA_DIR", tmp_path)
    monkeypatch.setattr(base, "RAW_DIR", tmp_path / "raw")


def test_health_fails_loudly_on_broken_endpoint(monkeypatch, isolated_db):
    """Deliberate: point the search endpoint at a dead host; health must be 'error', not silently 'ok'."""
    monkeypatch.setattr(usaspending, "SEARCH", "https://api.usaspending.gov.invalid/api/v2/search/spending_by_award/")
    res = usaspending.USASpendingConnector().run()
    assert res["health"] == "error" and res["records"] == 0


def test_awards_predating_backfill_window_are_dropped(monkeypatch):
    """Regression test: time_period filters on activity, not the award's own start date
    (confirmed live — a 2004 grant surfaced under a 2024-2026 filter). An award whose own
    Start Date predates the window must not count as 'new'."""
    def fake_get(fips, group, codes, start, end):
        return [
            {"Award ID": "OLD1", "Start Date": "2010-01-01", "_group": group, "_county_fips": fips},
            {"Award ID": "NEW1", "Start Date": "2026-01-01", "_group": group, "_county_fips": fips},
        ]
    monkeypatch.setattr(usaspending, "_get", fake_get)
    recs = usaspending.USASpendingConnector().fetch()
    ids = [r.payload["Award ID"] for r in recs]
    assert "OLD1" not in ids and "NEW1" in ids


@pytest.mark.skipif(not DB_PATH.exists(), reason="run `make fetch` first")
def test_scanner_drafts_all_have_evidence():
    import json
    for c in json.load(open("examples/usaspending_candidates.json")):
        assert c["evidence_urls"], c["candidate_id"]
        assert c["feed"] == "scanner" and c["candidate_type"] == "event"
