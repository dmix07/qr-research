.PHONY: fetch candidates screen deliver reproduce health test all
fetch:       ; python3 -m qr_research.run
candidates:  ; python3 -m qr_research.lens.fdic_drafts && python3 -m qr_research.lens.gateway_drafts && python3 -m qr_research.lens.gateway_finance_drafts && python3 -m qr_research.lens.sec_form_d_drafts && python3 -m qr_research.lens.bankruptcy_drafts && python3 -m qr_research.lens.usaspending_drafts && python3 -m qr_research.lens.irs_990_drafts && python3 -m qr_research.scanner.accumulate
screen:      ; python3 -m qr_research.screen.weekly_pick
deliver:     ; python3 -m qr_research.deliver.airtable examples/weekly_pick.json && python3 -m qr_research.screen.weekly_pick --mark-delivered
reproduce:   ; python3 -m qr_research.lens.reproduce
health:      ; python3 -m qr_research.health
test:        ; python3 -m pytest -q tests
all: fetch candidates screen deliver health
