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

## Problem and real user

The debit department receives invoice deductions from many payers, each
with its own literal reason. Invoices × payers × reasons used to mean
chaos: little information for management, an inefficient team, and no
traceability. The goal is to automate breakdown, routing, pending-item
organization and follow-up so verification work can be distributed
across teams with traceable replies — instead of one experienced
person resolving everything alone.

## Concrete demo result

Open case `EXP-900`: the jury can check what the system received (3
linked PDFs), what it extracted (2 lines, sums in whole cents), what
the code verified (rate validity, document reconciliation, citation
checks), what Meta contributed (structured findings, each citation
checked on its page), what stayed uncertain (flagged, never used as
evidence), and what a person reviewed and decided (recorded approval
with rationale and before/after).

![Case inbox](docs/shots/01-inbox.png)

## What it does

Fictitious casefile (invoice + settlement + agreement) → deterministic
extraction and reconciliation → verifiable findings → Meta input
with code-checked citations → routing proposal → draft → mandatory
human review → auditable history. UI in 3 areas: inbox,
casefile, evidence.

Hard limits (in contracts, not on posters): the AI classifies and
routes; it does not assess medicine, receives no clinical records,
sends no emails, and never decides whether a debit should be
accepted, claimed, or paid. Arithmetic differences are checks, not
payer reasons. "Medical Audit" is a human destination team.

## What each stage does (real implementation)

- Extraction (`extract.py`): text via pypdf or Spanish OCR via
  tesseract; per-document confidence. Deterministic, no model.
- Math (`money.py`): sums in whole cents; US display in the UI,
  Argentine format only inside document-domain parsing.
  Deterministic, no model.
- Rules (`rules.py` + rates): classification and team from the
  literal reason; clinical triggers route to people.
  Deterministic, no model.
- Agreements (`synthetic.py` manager): per-payer versions with
  validity and rate tables (fictitious); the applicable value is
  picked by service date and overlaps raise a warning.
- Casefile (`casefile.py`): invoice/settlement/agreement checks,
  amount facts, pending items; routing proposal
  (`route_team` / `route_human` / `request_extension`).
  No merit conclusions. Deterministic, no model.
- Meta input (`provider.py` + `agent.py`): structured findings
  (line, kind, document, page, excerpt, interpretation,
  limitations). Strict validation (integers, existing lines);
  each citation is checked on its indicated page. Unverifiable
  findings are tagged CITATION UNVERIFIED and never used as
  evidence. A post-model gate in code can only stop or reroute a
  routing proposal, never make one. The model does no math and
  invents no confidence.
- Drafts (`drafts.py`): one deterministic template per action
  (referral, clinical routing, information request).
  Proposals, not sendings.
- Process (`process.py`): P1/P2/P3 priority by amount, 5-business-day
  SLA from review, pre-routing checklist.
- Team reply (under redefinition): the current reply form records a
  team response with owner and date; its decision/amount fields are
  being reworked into per-task replies with backing references,
  per the owner's debit circuit (see TEST_REPORT.md).

## Three distinct decisions

Approving a proposal (accepting the suggested routing) is NOT
accepting a debit (agreeing to its economics) NOR authorizing a
message (sending something to someone). The demo only records the
first: it sends no messages and changes no external systems.

## Install

```bash
python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt
# System: tesseract-ocr + spa data + poppler-utils (pdftotext/pdftoppm)
# If spa is missing from the system:
#   curl -o ~/.local/share/tessdata/spa.traineddata <tessdata spa>
#   export TESSDATA_PREFIX=~/.local/share/tessdata
cp .env.example .env   # fill in MODEL_API_KEY for real Meta
```

## Run

```bash
.venv/bin/python -B tools/prepare_demo.py --db demo_data/demo.db
# 8 cases + main case + docs. The destination is REQUIRED and must
# not exist (for scratch work use --db /tmp/you/demo.db). Rebuilding
# an existing DB needs --replace --backup-to <new-path>, plus
# --confirm-active-db for the DB the server uses.
IA_PROVIDER=simulated .venv/bin/python -B -m debit_ai.demo_app
# open http://127.0.0.1:8931/ (main case EXP-900 opens by itself)
```

Back up before anything risky (verified, never blind copy):

```bash
.venv/bin/python -B tools/backup_db.py --db demo_data/demo.db \
    --to demo_data/backups/demo-<date>.db
# VALID only with integrity_check + restore test on a separate path
```

The demo reads the repo `.env` itself (explicit environment always
wins; values are never printed). With a Meta key, omit
`IA_PROVIDER=simulated`. Everything reproduces without access to the
original system: this repo neither imports, calls, nor knows its
paths (see PRIOR_WORK.md). Without a key and without
`IA_PROVIDER=simulated`, the demo refuses to start (explicit error,
never silent fallback).

## Tests and evaluation

```bash
.venv/bin/python -B -m unittest discover -s tests   # 71 OK, 2 live skipped
node tests/test_parse_money.cjs                     # 25/25 input vectors
TESSDATA_PREFIX=~/.local/share/tessdata .venv/bin/python -B evals/eval_synthetic.py
```

UI flows (review, reply, drafts, versions) are also probed in jsdom
and Chromium with zero JS/console errors (see TEST_REPORT.md).

## Honest limitations

- Meta integration: minimal probe and acceptance test OK with
  `muse-spark-1.3` (Responses), fictitious data, key in local `.env`
  outside Git. Baseten path validated with authorized calls
  (details below); spend frozen since. `simulated` runs still
  prove nothing about any provider.
- The user's personal review exists (`deler` approved
  `P-DEMO-F123-4` on 10/27/2026); agent-operated walkthroughs are
  recorded as `muse-demo`, never as a person.
- Real adapter (JSON): implemented, off by default, UNVERIFIED.
- OCR tested only on fixtures built with controlled noise.
- Team-reply economics are under redefinition (per-task replies,
  resolution, rebilling link, recovery evidence); see TEST_REPORT.md.
- Not deployed at the clinic; no production results measured.

## Baseten (hackathon)

`baseten` provider (OpenAI-compatible, Chat Completions only):
base `https://inference.baseten.co/v1`, exact model
`meta-models/muse-spark-open-1026`. Explicit timeout
(`BASETEN_TIMEOUT`, default 60s), no retries.

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

Status: probe + flow verified with authorized real calls
(Meta: 10 findings, 8 verified / 2 unverified; Baseten
`P-EXP-900-2`: 7 findings, 7/7 verified); spend frozen at
13,053 Baseten tokens in 3 calls. Demo runs on Baseten
(`IA_PROVIDER=baseten`); Meta stays as validated backup. Each
"request proposal" in the demo spends hackathon credits.

## License and publication status

- MIT license in force (see LICENSE; prior record in LICENSE-DRAFT-MIT.md).
- Public repo: https://github.com/ignapetit25-tech/debitos-hackathon.
- Eligibility: Idea declared eligible by Adam Blumenfeld (Cerebral Valley) in the project thread, 10/27/2026: https://discord.com/channels/1557169028080869426/1564401698259337216/1564670797908410389 — Scope: administrative debit management, no clinical judgment, fictitious data, human approval. He valued the direct knowledge of the problem and the real chance of implementation. He did not rule separately on pre-existing code or accepted models (the official FAQs apply). Not a security/compliance certification nor an approval of future extensions.
