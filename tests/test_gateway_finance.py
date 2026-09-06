import pytest
from qr_research.connectors import gateway_finance
from qr_research.connectors.base import DB_PATH


@pytest.fixture
def isolated_db(monkeypatch, tmp_path):
    from qr_research.connectors import base
    monkeypatch.setattr(base, "DB_PATH", tmp_path / "t.sqlite")
    monkeypatch.setattr(base, "DATA_DIR", tmp_path)
    monkeypatch.setattr(base, "RAW_DIR", tmp_path / "raw")


def test_health_fails_loudly_on_broken_endpoint(monkeypatch, isolated_db):
    """Deliberate: point the connector at a dead host; health must be 'error', not silently 'ok'."""
    monkeypatch.setattr(gateway_finance, "URL", "https://gateway.ifionline.org.invalid/public/download.aspx")
    res = gateway_finance.GatewayFinanceConnector().run()
    assert res["health"] == "error" and res["records"] == 0


def test_tif_regex_matches_known_fund_names():
    m = gateway_finance.TIF_RE
    assert m.search("Northeast Corridor TIF")
    assert m.search("ECONOMIC DEVELOPMENT IN TIF AREA")
    assert m.search("REDEVELOPMENT DISTRICT")
    assert not m.search("GENERAL FUND")


@pytest.mark.skipif(not DB_PATH.exists(), reason="run `make fetch` first")
def test_scanner_drafts_all_have_evidence():
    import json
    for c in json.load(open("examples/gateway_finance_candidates.json")):
        assert c["evidence_urls"], c["candidate_id"]
        assert c["feed"] == "scanner" and c["candidate_type"] == "event"
        assert c["axis_a"] and c["axis_b"] and c["function"]
