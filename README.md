# Debit AI layer (hackathon)

Independent AI layer over a pre-existing debit-management system for
health payers. Standalone demo with 100% fictitious data.

Idea declared eligible by Adam Blumenfeld (Cerebral Valley) in the project thread, 10/27/2026: https://discord.com/channels/1557169028080869426/1564401698259337216/1564670797908410389 — Scope: administrative debit management, no clinical judgment, fictitious data, human approval. He valued the direct knowledge of the problem and the real chance of implementation. He did not rule separately on pre-existing code or accepted models (the official FAQs apply). Not a security/compliance certification nor an approval of future extensions.

## Origin

I run the debit department of an Argentine outpatient clinic, where I
deal every day with deductions from obras sociales, prepagas, and ART.
I designed this project to cut the manual work of reading, reconciling,
routing, and following up, while keeping final decisions with people.

Glossary (Argentine domain terms kept in Spanish on purpose):
- obra social: union-run health fund.
- prepaga: private health insurer.
- ART: workers' compensation insurer.

## What it does

Fictitious casefile (invoice + settlement + agreement) → deterministic
extraction and reconciliation → verifiable findings → Meta input
with code-checked citations → proposal → draft → mandatory human
review → auditable history. UI in 3 areas: inbox,
casefile, evidence.

Hard limits (in contracts, not on posters): the AI does not assess
medicine, receives no clinical records, sends no emails, does not
accept/reject debits. "Medical Audit" is a human destination team.

## What each stage does (real implementation)

- Extraction (`extract.py`): text via pypdf or Spanish OCR via
  tesseract; per-document confidence. Deterministic, no model.
- Math (`money.py`, `validate`): sums in whole cents.
  Deterministic, no model.
- Rules (`rules.py` + rates): score and team by phrases.
  Deterministic, no model.
- Agreements (`synthetic.py` manager): per-payer versions with
  validity and rate tables (fictitious); the applicable value is
  picked by service date and overlaps raise a warning.
- Process (`process.py`): P1/P2/P3 priority by amount, 5-business-day
  SLA from review, pre-routing checklist and team reply
  (decision, recoverable/accepted, owner, date).
- Meta input (`provider.py` + `agent.py`): returns structured
  findings (document, page, excerpt, interpretation,
  limitations). The code drops invalid kinds and checks each
  citation against the document; the unverifiable is tagged
  CITATION UNVERIFIED. The model does no math, picks no team, and
  invents no numeric confidence.
- Drafts (`drafts.py`): deterministic templates with case data.
  Proposals, not sendings.

## Three distinct decisions

Approving a proposal (accepting the suggested routing) is NOT
accepting a debit (agreeing to its economics) NOR authorizing a
message (sending something to someone). The demo only records the
first: it sends no messages and changes no external systems.

## Install

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
# System: tesseract-ocr + spa data + poppler-utils (pdftotext/pdftoppm)
# If spa is missing from the system:
#   curl -o ~/.local/share/tessdata/spa.traineddata <tessdata spa>
#   export TESSDATA_PREFIX=~/.local/share/tessdata
cp .env.example .env   # fill in MODEL_API_KEY for real Meta
```

## Run

```bash
.venv/bin/python -B tools/reset_demo.py          # rebuilds base + PDFs
IA_PROVIDER=simulated .venv/bin/python -B -m debit_ai.demo_app
# open http://127.0.0.1:8931/
```

With a Meta key: `MODEL_API_KEY=... .venv/bin/python -B -m debit_ai.demo_app`.
Everything reproduces without access to the original system: this repo
neither imports, calls, nor knows its paths (see PRIOR_WORK.md).
Without a key and without `IA_PROVIDER=simulated`, the demo refuses
to start (explicit error, never silent fallback).

## Tests and evaluation

```bash
.venv/bin/python -B -m unittest discover -s tests
TESSDATA_PREFIX=~/.local/share/tessdata .venv/bin/python -B evals/eval_synthetic.py
```

## Honest limitations

- Meta integration: minimal probe and acceptance test OK with
  `muse-spark-1.3` (Responses), fictitious data, key in local `.env`
  outside Git. Agent-operated demo walkthrough OK; the user's
  personal review is missing (cases pending in the demo).
  `simulated` runs still prove nothing about Meta.
- Real adapter (JSON): implemented, off by default, UNVERIFIED.
- `simulated` runs prove nothing about Meta.
- OCR tested only on fixtures built with controlled noise.

## Baseten (hackathon)

`baseten` provider (OpenAI-compatible, Chat Completions only):
base `https://inference.baseten.co/v1`, exact model
`meta-models/muse-spark-open-1026`. Explicit timeout
(`BASETEN_TIMEOUT`, default 60s), no retries. The Pi Meta
provider (`muse-spark-1.3`) was not modified.

Enter the key (the operator does it, never in chat):
1. Open `debitos-hackathon/.env` with an editor (Git-ignored).
2. Add the line `BASETEN_API_KEY=...` with the hackathon key.
3. Save; check presence only with
   `grep -c '^BASETEN_API_KEY=.' .env` (prints 1, not the value).

First real test (only with authorization, spends credits):
`.venv/bin/python -B tools/check_baseten.py` — exactly 1 call,
bounded output, 60s timeout, no retries; shows metadata and
reported usage, never the key. Then the full flow:
`BASETEN_LIVE=1 .venv/bin/python -B -m unittest tests.test_baseten_live`.

Isolation: no live test runs just because a key exists.
Meta requires `META_LIVE=1` and Baseten `BASETEN_LIVE=1`, both
off by default; without the flag, the suite skips with no network.

Status: probe + flow verified with authorized real calls;
demo running on Baseten (`IA_PROVIDER=baseten`). Meta (`muse-spark-1.3`)
stays as validated backup. Each "request proposal" in the demo spends
hackathon credits.

## License and publication status

- MIT license in force (see LICENSE; prior record in LICENSE-DRAFT-MIT.md).
- No remote configured, not published, no visibility changes.
- Eligibility: Idea declared eligible by Adam Blumenfeld (Cerebral Valley) in the project thread, 10/27/2026: https://discord.com/channels/1557169028080869426/1564401698259337216/1564670797908410389 — Scope: administrative debit management, no clinical judgment, fictitious data, human approval. He valued the direct knowledge of the problem and the real chance of implementation. He did not rule separately on pre-existing code or accepted models (the official FAQs apply). Not a security/compliance certification nor an approval of future extensions.
