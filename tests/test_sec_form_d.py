import pytest
from qr_research.connectors import sec_form_d
from qr_research.connectors.base import DB_PATH


@pytest.fixture
def isolated_db(monkeypatch, tmp_path):
    from qr_research.connectors import base
    monkeypatch.setattr(base, "DB_PATH", tmp_path / "t.sqlite")
    monkeypatch.setattr(base, "DATA_DIR", tmp_path)
    monkeypatch.setattr(base, "RAW_DIR", tmp_path / "raw")


def test_health_fails_loudly_on_broken_endpoint(monkeypatch, isolated_db):
    """Deliberate: point full-text search at a dead host; health must be 'error', not silently 'ok'."""
    monkeypatch.setattr(sec_form_d, "EFTS", "https://efts.sec.gov.invalid/LATEST/search-index")
    monkeypatch.setattr(sec_form_d, "MI_ZIPS", {"49022"})  # keep it to one query so the test is fast
    res = sec_form_d.SECFormDConnector().run()
    assert res["health"] == "error" and res["records"] == 0


def test_related_person_address_does_not_count_as_issuer(monkeypatch):
    """Deliberate regression test for the Southfield/Harbert false positive found during
    development: a hit whose issuer address is outside the region must be dropped even
    though full-text search matched the document (a related person's address, in that case)."""
    monkeypatch.setattr(sec_form_d, "_issuer_address", lambda cik, acc: {"city": "SOUTHFIELD", "state": "MI", "zip5": "48076"})
    monkeypatch.setattr(sec_form_d, "_search", lambda term, s, e: [{"_source": {"adsh": "0001-24-000001", "ciks": ["1"], "display_names": ["X"], "file_date": "2024-01-01", "items": []}}])
    monkeypatch.setattr(sec_form_d, "_region_in_lists", lambda: (set(), {"49115": "26021"}))
    res = sec_form_d.SECFormDConnector().fetch()
    assert res == []
