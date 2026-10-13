from qr_research.screen.weekly_pick import WEEKLY_CAP, pick, rank


def _c(cid, ctype="event", source="usaspending", result="surface"):
    return {"candidate_id": cid, "candidate_type": ctype, "source": source, "screen_result": result, "headline": cid}


def test_drafts_first_then_one_event_per_source_rarer_sources_first():
    cands = [_c(f"usas{i}") for i in range(600)] + [
        _c("formd1", source="sec_form_d"), _c("formd2", source="sec_form_d"),
        _c("draft-hold", "observation_draft", "fdic", "hold"),
        _c("draft-surface", "observation_draft", "gateway"),
        _c("accum", "accumulation", "irs_990+usaspending"),
    ]
    ids = [c["candidate_id"] for c in rank(cands, set())]
    assert ids == ["draft-surface", "accum", "draft-hold", "formd1", "usas0"]


def test_cap_skips_delivered_and_screen_kills():
    cands = [_c(f"d{i}", "observation_draft", "fdic") for i in range(10)]
    killer = lambda c: {**c, "screen_result": "kill"} if c["candidate_id"] == "d1" else c
    out = pick(cands, already={"d0"}, screen=killer)
    assert [c["candidate_id"] for c in out] == ["d2", "d3", "d4", "d5", "d6"]
    assert len(out) == WEEKLY_CAP


def test_generator_kills_never_reach_the_screener():
    seen = []
    pick([_c("k", result="kill"), _c("ok")], set(), screen=lambda c: seen.append(c["candidate_id"]) or c)
    assert seen == ["ok"]
