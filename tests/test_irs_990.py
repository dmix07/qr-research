import pytest
from qr_research.connectors import irs_990
from qr_research.connectors.base import DB_PATH


@pytest.fixture
def isolated_db(monkeypatch, tmp_path):
    from qr_research.connectors import base
    monkeypatch.setattr(base, "DB_PATH", tmp_path / "t.sqlite")
    monkeypatch.setattr(base, "DATA_DIR", tmp_path)
    monkeypatch.setattr(base, "RAW_DIR", tmp_path / "raw")


def test_health_fails_loudly_on_broken_endpoint(monkeypatch, isolated_db):
    """Deliberate: point the IRS bulk file at a dead host; health must be 'error', not silently 'ok'."""
    monkeypatch.setattr(irs_990, "EO_BMF", "https://www.irs.gov.invalid/pub/irs-soi/eo_{st}.csv")
    res = irs_990.IRS990Connector().run()
    assert res["health"] == "error" and res["records"] == 0


def test_pct_change_computed_from_two_most_recent_years(monkeypatch, isolated_db):
    monkeypatch.setattr(irs_990, "_stream_state_csv", lambda state, zips: (
        [{"EIN": "010000001", "NAME": "Test Nonprofit", "CITY": "Niles", "ZIP": "49120-0000", "NTEE_CD": "", "_county_fips": "26021"}]
        if state == "MI" else []
    ))
    monkeypatch.setattr(irs_990, "_latest_two_years", lambda ein: (
        {"tax_prd_yr": 2023, "totassetsend": 150000},
        {"tax_prd_yr": 2022, "totassetsend": 100000},
    ))
    recs = irs_990.IRS990Connector().fetch()
    assert len(recs) == 1
    assert round(recs[0].payload["pct_change"], 2) == 0.5


@pytest.mark.skipif(not DB_PATH.exists(), reason="run `make fetch` first")
def test_scanner_drafts_all_have_evidence():
    import json
    for c in json.load(open("examples/irs_990_candidates.json")):
        assert c["evidence_urls"], c["candidate_id"]
        assert c["feed"] == "scanner" and c["candidate_type"] == "event"
