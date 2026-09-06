from qr_research.screen import rubric


def test_llm_stage_failure_falls_back_to_dry_mode_not_crash(monkeypatch):
    """Regression test: a live run crashed mid-batch when the Anthropic account ran out of
    credits (a 400 from api.anthropic.com), taking down every candidate file screened after
    it. A single failed call must fall back to the generator's tags for that candidate, not
    kill the whole batch."""
    monkeypatch.setenv("SCREENER_API_KEY", "test-key")
    monkeypatch.setenv("SCREENER_PROVIDER", "anthropic")

    class FakeResp:
        status_code = 400
        text = '{"error": "credit balance too low"}'
        def raise_for_status(self):
            raise __import__("requests").exceptions.HTTPError("400 Client Error")

    monkeypatch.setattr(rubric.requests, "post", lambda *a, **k: FakeResp())
    c = {"candidate_id": "x1", "headline": "test", "counties": ["St. Joseph IN"], "candidate_type": "event",
         "feed": "scanner", "evidence_urls": ["https://example.com"], "screen_result": "surface"}
    out = rubric.screen(c)
    assert out == c  # dry mode: unchanged passthrough, no exception raised
