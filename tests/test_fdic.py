import os, sqlite3
import pytest
from qr_research.connectors import fdic
from qr_research.connectors.base import DB_PATH, record_health


@pytest.fixture
def isolated_db(monkeypatch, tmp_path):
    from qr_research.connectors import base
    monkeypatch.setattr(base, "DB_PATH", tmp_path / "t.sqlite")
    monkeypatch.setattr(base, "DATA_DIR", tmp_path)
    monkeypatch.setattr(base, "RAW_DIR", tmp_path / "raw")


def test_health_fails_loudly_on_broken_endpoint(monkeypatch, isolated_db):
    """Deliberate: point the connector at a dead host; health must be 'error', not silently 'ok'."""
    monkeypatch.setattr(fdic, "BASE", "https://api.fdic.gov.invalid/banks")
    monkeypatch.setattr(fdic, "_get", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("dns")))
    res = fdic.FDICConnector().run()
    assert res["health"] == "error" and res["records"] == 0


def test_volume_band_flags_silence(isolated_db):
    assert record_health("unit_test_src", 0, (100, 200), "abc", ok=True) == "volume_out_of_band"


@pytest.mark.skipif(not DB_PATH.exists(), reason="run `make fetch` first")
def test_reproduces_published_001_002():
    from qr_research.lens.reproduce import hq_institutions_by_year, deposits_by_control, region_share_of_us
    c = sqlite3.connect(DB_PATH)
    hq = hq_institutions_by_year(c)
    assert max(hq.values()) == 47 and hq[2025] == 4
    assert round(deposits_by_control(c, 2025)["share_elsewhere_by_inst_hq"], 2) == 0.59
    sh = region_share_of_us(c)
    assert 480 < 1 / sh[1994] < 520 and 1200 < 1 / sh[2025] < 1350


def test_lens_drafts_all_have_recipes_and_evidence():
    import json
    for c in json.load(open("examples/fdic_candidates.json")):
        assert c["evidence_urls"], c["candidate_id"]
        if c["feed"] == "lens":
            assert c["recipe_ids"] and c["method"] and c["stock_or_flow"], c["candidate_id"]


@pytest.mark.skipif(not DB_PATH.exists(), reason="run `make fetch` first")
def test_reproduces_published_006():
    import re
    c = sqlite3.connect(DB_PATH)
    if not c.execute("select count(*) from gateway_parcels").fetchone()[0]:
        pytest.skip("gateway not fetched")
    num = lambda a: (re.match(r"\s*(\d+)", a or "") or [None, None])[1]
    rows = c.execute("select prop_address,prop_zip5,owner_address,owner_zip5 from gateway_parcels where property_class between '510' and '515'").fetchall()
    home = sum(1 for pa, pz, oa, oz in rows if oz == pz and pz and num(oa) and num(oa) == num(pa)) / len(rows)
    assert 0.78 <= home <= 0.85
