import json
import os

from qr_research.scanner import accumulate


def _write(tmp_path, monkeypatch, name, cands):
    monkeypatch.chdir(tmp_path)
    os.makedirs("examples", exist_ok=True)
    json.dump(cands, open(f"examples/{name}", "w"))


def test_two_sources_within_window_accumulate(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, "a_candidates.json", [{
        "feed": "scanner", "candidate_type": "event", "candidate_id": "scan-a-1", "source": "usaspending",
        "entity_name": "Widget Manufacturing LLC", "entity_county_fips": "18141", "event_date": "2025-01-01",
        "counties": ["St. Joseph IN"], "headline": "Widget Manufacturing LLC got a grant", "evidence_urls": ["https://example.com/a"],
    }])
    _write(tmp_path, monkeypatch, "b_candidates.json", [{
        "feed": "scanner", "candidate_type": "event", "candidate_id": "scan-b-1", "source": "bankruptcy",
        "entity_name": "WIDGET MANUFACTURING, LLC", "entity_county_fips": "18141", "event_date": "2025-06-01",
        "counties": ["St. Joseph IN"], "headline": "Widget Manufacturing LLC filed Chapter 11", "evidence_urls": ["https://example.com/b"],
    }])
    out = accumulate.find_accumulations()
    assert len(out) == 1
    assert out[0]["candidate_type"] == "accumulation"
    assert set(out[0]["related_candidates"]) == {"scan-a-1", "scan-b-1"}


def test_same_source_twice_does_not_accumulate(tmp_path, monkeypatch):
    """Hard requirement: >=2 *sources*, not just >=2 events."""
    _write(tmp_path, monkeypatch, "a_candidates.json", [
        {"feed": "scanner", "candidate_type": "event", "candidate_id": "scan-a-1", "source": "usaspending",
         "entity_name": "Widget LLC", "entity_county_fips": "18141", "event_date": "2025-01-01",
         "counties": ["St. Joseph IN"], "headline": "x", "evidence_urls": ["https://example.com/a"]},
        {"feed": "scanner", "candidate_type": "event", "candidate_id": "scan-a-2", "source": "usaspending",
         "entity_name": "Widget LLC", "entity_county_fips": "18141", "event_date": "2025-02-01",
         "counties": ["St. Joseph IN"], "headline": "y", "evidence_urls": ["https://example.com/a2"]},
    ])
    assert accumulate.find_accumulations() == []


def test_outside_window_does_not_accumulate(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, "a_candidates.json", [{
        "feed": "scanner", "candidate_type": "event", "candidate_id": "scan-a-1", "source": "usaspending",
        "entity_name": "Widget LLC", "entity_county_fips": "18141", "event_date": "2020-01-01",
        "counties": ["St. Joseph IN"], "headline": "x", "evidence_urls": ["https://example.com/a"],
    }])
    _write(tmp_path, monkeypatch, "b_candidates.json", [{
        "feed": "scanner", "candidate_type": "event", "candidate_id": "scan-b-1", "source": "bankruptcy",
        "entity_name": "Widget LLC", "entity_county_fips": "18141", "event_date": "2026-01-01",
        "counties": ["St. Joseph IN"], "headline": "y", "evidence_urls": ["https://example.com/b"],
    }])
    assert accumulate.find_accumulations() == []
