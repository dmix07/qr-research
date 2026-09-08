import pytest

from qr_research.connectors import gateway
from qr_research.connectors.base import RawRecord


@pytest.fixture
def isolated_db(monkeypatch, tmp_path):
    from qr_research.connectors import base
    monkeypatch.setattr(base, "DB_PATH", tmp_path / "t.sqlite")
    monkeypatch.setattr(base, "DATA_DIR", tmp_path)
    monkeypatch.setattr(base, "RAW_DIR", tmp_path / "raw")


def test_parse_acreage_decimal_format():
    """Pre-2025 vintages: plain decimal string."""
    assert gateway._parse_acreage("39.5500") == 39.55


def test_parse_acreage_scaled_integer_format():
    """2025 vintage: zero-padded, x10000-scaled integer."""
    assert gateway._parse_acreage("000000428300") == 42.83


def test_parse_acreage_blank_is_zero():
    assert gateway._parse_acreage("            ") == 0.0
    assert gateway._parse_acreage("") == 0.0


def test_parse_acreage_decimal_without_leading_zero():
    """Found live during the 2020-2025 backfill (DECISIONS.md #87): under-an-acre parcels are
    sometimes stored as ".9900" rather than "0.9900"."""
    assert gateway._parse_acreage(".9900") == 0.99


def test_parse_acreage_unrecognized_format_fails_loud():
    """Regression test for DECISIONS.md #78: an acreage value that matches neither known
    format must raise, not silently coerce to 0."""
    with pytest.raises(ValueError):
        gateway._parse_acreage("39.55.00")
    with pytest.raises(ValueError):
        gateway._parse_acreage("N/A")


def _row(overrides: dict) -> dict:
    base = {
        "assessment_year": 2025, "county_fips": "18141", "parcel_number": "P1",
        "township_no": "", "state_district_no": "", "prop_address": "", "prop_city": "",
        "prop_zip": "", "property_class": "400", "owner_name": "Test Owner LLC",
        "owner_address": "", "owner_city": "", "owner_state": "IN", "owner_zip": "",
        "owner_country": "USA", "transfer_date": "", "av_land": "0", "av_improvements": "0",
        "av_total": "0", "acreage_x10000": "000000010000",
    }
    base.update(overrides)
    return base


def test_bad_acreage_fails_the_connector_loudly_not_silently(monkeypatch, isolated_db):
    """A malformed acreage value must surface as health='error' for this source — not get
    coerced to acres=0 while health stays 'ok' (the exact bug found in DECISIONS.md #78)."""
    good = RawRecord("in_gateway_parcels", "parcel:2025:18141:P1", _row({}))
    bad = RawRecord("in_gateway_parcels", "parcel:2025:18141:P2", _row({"parcel_number": "P2", "acreage_x10000": "N/A"}))
    monkeypatch.setattr(gateway.GatewayConnector, "fetch", lambda self, since=None: [good, bad])
    res = gateway.GatewayConnector().run()
    assert res["health"] == "error"
    assert "unrecognized acreage format" in res["note"]
