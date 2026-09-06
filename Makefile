.PHONY: fetch candidates screen deliver reproduce health test all
fetch:       ; python3 -m qr_research.run
candidates:  ; python3 -m qr_research.lens.fdic_drafts && python3 -m qr_research.lens.gateway_drafts && python3 -m qr_research.lens.gateway_finance_drafts
screen:      ; for f in examples/*_candidates.json; do python3 -m qr_research.screen.rubric $$f; done
deliver:     ; for f in examples/*_candidates.json; do python3 -m qr_research.deliver.airtable $$f; done
reproduce:   ; python3 -m qr_research.lens.reproduce
health:      ; python3 -m qr_research.health
test:        ; python3 -m pytest -q tests
all: fetch candidates screen deliver health
