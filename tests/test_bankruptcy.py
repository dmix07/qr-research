import pytest
from qr_research.connectors import bankruptcy
from qr_research.connectors.base import DB_PATH


@pytest.fixture
def isolated_db(monkeypatch, tmp_path):
    from qr_research.connectors import base
    monkeypatch.setattr(base, "DB_PATH", tmp_path / "t.sqlite")
    monkeypatch.setattr(base, "DATA_DIR", tmp_path)
    monkeypatch.setattr(base, "RAW_DIR", tmp_path / "raw")


def test_health_fails_loudly_on_broken_endpoint(monkeypatch, isolated_db):
    """Deliberate: point the search endpoint at a dead host; health must be 'error', not silently 'ok'."""
    monkeypatch.setattr(bankruptcy, "SEARCH", "https://www.courtlistener.com.invalid/api/rest/v4/search/")
    monkeypatch.setattr(bankruptcy, "MI_ZIP_COUNTY", {"49022": ("26021",)})  # one query, fast test
    monkeypatch.setattr(bankruptcy, "_region_in_lists", lambda: (set(), {}))
    res = bankruptcy.BankruptcyConnector().run()
    assert res["health"] == "error" and res["records"] == 0


def test_individuals_and_chapter_13_are_excluded(monkeypatch, isolated_db):
    """Hard rule: never individuals. Chapter 13 is individual-only regardless of name."""
    hits = [
        {"docket_id": 1, "caseName": "Jane Smith", "chapter": "13", "dateFiled": "2025-01-01", "docketNumber": "1", "docket_absolute_url": "/x/"},
        {"docket_id": 2, "caseName": "Jane Smith", "chapter": "7", "dateFiled": "2025-01-01", "docketNumber": "2", "docket_absolute_url": "/x/"},
        {"docket_id": 3, "caseName": "Smith Trucking LLC", "chapter": "11", "dateFiled": "2025-01-01", "docketNumber": "3", "docket_absolute_url": "/x/"},
    ]
    monkeypatch.setattr(bankruptcy, "_search", lambda court, term, a, b: hits)
    monkeypatch.setattr(bankruptcy, "_region_in_lists", lambda: ({"SOUTH BEND"}, {}))
    monkeypatch.setattr(bankruptcy, "MI_ZIP_COUNTY", {})
    recs = bankruptcy.BankruptcyConnector().fetch()
    names = [r.payload["case_name"] for r in recs]
    assert names == ["Smith Trucking LLC"]


@pytest.mark.skipif(not DB_PATH.exists(), reason="run `make fetch` first")
def test_scanner_drafts_all_have_evidence():
    import json
    for c in json.load(open("examples/bankruptcy_candidates.json")):
        assert c["evidence_urls"], c["candidate_id"]
        assert c["feed"] == "scanner" and c["candidate_type"] == "event"
