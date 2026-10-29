# Prior work vs new work

Pre-existing (pre-existing private repo, main `0ac2c4c`, external
review): debit web app, own rules engine, production SQLite,
routing, history, evaluations, drafts. ~9,600 lines.

New in this repo (hackathon), written from scratch:
- Integration contracts, AI core, minimal synthetic rules.
- Meta Muse Spark client + explicit simulated provider.
- PDF/OCR extraction, agent, approvals, drafts, web demo.
- Fictitious fixture generator, safe reset, evaluation, tests.
- All documentation in this repo.

Verifiable separation: no `.py` here imports `pmc_validator` or
`sistema` (test_isolation); no submodules; no copied history;
demo data generated, never real. Domain concepts reused
(score/threshold routing, traceability) without copying code.

Reproduction without the original system: clone ONLY this repo, create
a venv, `pip install -r requirements.txt`, `tools/reset_demo.py` and
start the demo. No step reads, imports, or calls the pre-existing
system; the PDFs and the base are generated here.
