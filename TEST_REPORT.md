# Test report

## Data-loss incident (2026-10-30) — read before the evidence below

On 10/30 the agent ran `tools/prepare_demo.py` without a scratch
destination; the script silently rebuilt the default path and
deleted the live `demo_data/demo.db` (it used `unlink()` with no
backup). No copy existed (git-ignored, no open handle to recover
from, no matching /tmp copy among 1157 scanned). This report now
distinguishes three evidence classes — do not mix them:

1. HISTORICAL (records lost, written account preserved). The Meta
   and Baseten runs below happened as described, with the IDs,
   latencies and token counts quoted — but their original DB rows
   (`model_call` events, proposals, the `deler` personal review)
   are GONE and were NOT reconstructed. Treat quoted IDs/dates as
   a written record, not as queryable originals. No agent will
   ever re-create the personal review; only the owner can.
2. PRESERVED (files intact). Fixture PDFs, `demo_data/generated`,
   shots `docs/shots/01-06`, scripts, docs, and the offline suite.
3. NEW (from 10/31 on). Any run recorded after the fix below, on
   the current reseeded DB, with real dates and verifiable rows.

Fix (all in-repo, tested): `prepare_demo.py` now REQUIRES an
explicit destination (`--db` or `IA_DEMO_DB`), fails without
touching anything when the target exists, and rebuilds only via
`--replace --backup-to <new-path>` with a verified backup first;
replacing the active server DB additionally needs
`--confirm-active-db`. `tools/backup_db.py` takes backups with the
sqlite3 backup API + `integrity_check` + a restore test on a
separate path (a file alone is never reported VALID). Protection
suite `tests/test_protection.py` (9 tests): no-destination CLI
failure with the live DB byte-identical, existing-target refusal
with records intact, active-DB refusal, fresh prepare on a
separate path, and a backup→restore roundtrip with proposals,
reviews and history identical. Post-incident baseline backup:
`demo_data/backups/demo-20261031-postincident.db` (VALID,
fixtures only, history 0 — the honest empty state).

## Deterministic metrics (no model)

Run (local environment):
- Offline suite: 121 tests OK, 2 live skipped (gated by
  `META_LIVE=1` / `BASETEN_LIVE=1`, off by default).
  Stages 1-4 added: strict money-input vectors (Node, 25/25),
  post-model gate, neutral routing (no merit conclusions),
  review persistence, one-command setup, per-page citations,
  per-action drafts, numeric versions.
  Post-incident: 9 protection tests (explicit destination,
  fail-if-exists, active-DB guard, verified backup roundtrip).
  Circuit: 29 tests (task lifecycle, answer/verify/return guards,
  per-line resolution, rebilling link, partial recognition with
  issuer, dispute balance, duplicate refusal, reconciliation,
  accepted-debit closure, accounting docs with authorization-gap
  alerts, shared-audit link and conclusion with guards, no
  amount-derived status) + 9 provider-limit tests
  (input truncation before any call, output token caps passed to
  Meta responses/chat and Baseten chat, coverage transparency in
  model_call and proposal, stubbed clients, 0 network).
  The legacy reply endpoint/UI (`pending/recovered/accepted/
  partial`) and the generic single-recovery endpoint were REMOVED
  as validated definitions; their library functions stay only
  for old records and unit tests.
  Package `debit_ai`, English API/UI; Spanish kept only in
  fictitious domain text.
- Baseten: implemented (`BasetenProvider`, minimal probe and
  acceptance test with fictitious data). Keyless probe fails
  explicit (exit 1, 0 calls).
- REAL Baseten (authorized, 2 total calls): minimal probe OK
  (953 tokens) + `BASE-1` flow OK — call → proposal with
  `Model (baseten):` → review → recorded approval
  (418/2988 in/out = 3,406 tokens, ID chatcmpl-458d…). Baseten
  total: 4,359 tokens. Daily dev stays on Meta; Baseten
  stands validated as the hackathon path.
- Demo switched to Baseten (restart with `IA_PROVIDER=baseten`, 0
  new calls): Meta histories and proposals kept
  (`P-EXP-900-1` intact).
- `P-EXP-900-2` on Baseten (1 authorized call): Agreements/claim,
  sums OK, 7 findings persisted with 7/7 verified citations
  (752/7942 in/out = 8,694 tokens, ID chatcmpl-4ccd…). Baseten
  total: 13,053 tokens in 3 calls. Spend frozen from here:
  the rest (reviews, screenshots, video, docs, UI) uses existing
  artifacts with 0 calls.
- Live isolation: `META_LIVE=1` / `BASETEN_LIVE=1` required
  besides the key (default skipped). Verified offline: 2 tests
  skipped in 0.1s; with flag but no key, still skipped.
- `.env` loading verified with a temp marker (file
  restored byte-identical, 0 secrets printed); the probe reports
  loading even on failure.
- Prior unit suite: 35 tests OK (money, rules, approvals, history
  + timestamps, isolation, provider errors, injection,
  casefile + findings, process + manager + follow-up). The live
  test was not repeated in this phase (budget); its last run
  was green.
- Agreement manager (fictitious, 0 inferences): 4 versions across 3
  payers; June-2026 overlap resolved to v2026 with warning;
  idempotent seeding; rates now come from the manager.
- Process: threshold priority, weekend-skipping SLA,
  checklist (lines, sums, copays, agreement, owner).
  Task circuit (confirmed): tasks per line + sector; answer with
  backing → debitos verify/return; per-line resolution; rebilling
  (not money); recognition events with explicit issuer; balance
  in dispute ("saldo en disputa", owner-confirmed); accepted-debit
  terminal closure with origin analysis (text fields suffice);
  separate
  accounting docs with alerts. Multi-invoice credit notes were
  ruled OUT by the owner (modeling error, not implemented).
  Fictitious demo case EXP-2501 (`tools/demo_circuit.py`, all
  actors auto-test-*): 3 lines, 4 tasks, 1 return, 2 resolutions,
  1 rebilling with partial recognition ($10,000 of $30,000,
  $20,000 disputed), 1 accepted debit, 1 shared audit (dispute
  returns as EXP-2502, concluded: rebill $12,000). Shot
  `docs/shots/05-process.png`.
- Synthetic evaluation over 7 controlled cases: extraction 7/7,
  routing 7/7, abstention 7/7 (includes 1 scanned PDF with
  spa OCR, confidence 0.92). "Abstention 7/7" means: routed to a human
  on clinical cases and produced an admin proposal on the
  rest, with no misses either way. It is a check on
  those examples, does NOT prove general accuracy or clinical coverage.
- Web demo: propose->review->history->draft flow OK;
  clinical case routes to humans.

## Meta evidence (separate from deterministic and simulator)

- Minimal probe `tools/check_meta.py`: OK with `muse-spark-1.3` via
  the Responses protocol, fictitious data. Evidence: provider, returned
  model, response ID, status, latency and reported usage.
- Acceptance `tests/test_meta_live.py`: OK. Real call → model
  text used in the proposal → auditable `model_call` event →
  approval recorded in history.
- Casefile `EXP-900` (invoice + settlement + agreement, service
  2026-08-10): 1 Meta call → 10 findings persisted, 8 with
  verified citation and 2 tagged CITATION UNVERIFIED; usage 615/13057
  in/out (13,672 of a 20,000-token F2 budget). Backed
  Agreements/claim proposal, pending review.
- 6-failure matrix (simulated provider, 0 inferences): missing
  agreement → request_extension; wrong validity → request_extension;
  inconsistent sums → inconsistency + request_extension; missing
  reference → explicit CITATION UNVERIFIED; case switch mid-request
  → busy guard + disabled buttons (inspection);
  fallen provider → DEGRADED with the deterministic casefile intact.
- UI verified in real engines (jsdom probes + Chromium screenshots
  against a scratch server, simulated provider, 0 paid calls):
  circuit probe 28/28 in Chromium (Playwright; the /tmp jsdom
  harness was lost to a tmp cleanup, probes re-implemented):
  create → answer guards → verify → resolve → rebill →
  partial recognition with dispute → duplicate refusal →
  ambiguity alert → reconcile → accepted debit with closure
  guards → shared-audit request with duplicate guard →
  audit conclusion with terms guards → accounting-doc alert,
  prebuilt circuit case;
  0 console errors; 0 innerHTML uses. Review UI code unchanged
  since its 9/9; review backend re-verified via API (propose →
  approve → single review event).
- Shots `docs/shots/01-inbox.png` … `06-polish.png` (Chromium,
  English UI, simulated provider, 0 console errors, 0 inferences):
  01 inbox (10 cases) with states and amounts; 02 `EXP-900`
  casefile (summary, totals, neutral checks, open-document
  buttons); 03 evidence with a selected finding; 04 undecided
  review form; 05 `EXP-2501` circuit (verified tasks, resolutions,
  rebilling, partial recognition with $20,000 dispute, accepted
  debit, accounting section); 06 final state.
- Legacy taxonomy note: proposals recorded before the domain
  correction carry action `claim`; drafts and UI render them with
  the current referral template. Old records are kept verbatim.
- Meta-required fix: `EXPLANATION_SCHEMA` needed
  `"additionalProperties": False` (strict mode). The
  earlier `AuthenticationError` only proved connectivity and credential
  rejection; it did NOT validate the schema. The schema was validated
  by the later successful call.
- LIMIT: the test's approval is automated (`auto-test-live`);
  it does NOT stand for a real human review. All test reviewers
  are named `auto-test*` and run on temp DBs, never the live one.
- Meta demo walkthrough (`DEMO-F123`, fictitious data): extraction
  2/2 with no flags, sums OK (dif 0), Agreements/claim proposal with
  `muse-spark-1.3` text, draft checked figure by figure,
  recorded approval. History: `model_call` provider=meta
  status=ok latency 5400ms usage 155/1229 in/out + approved `review`
  with rationale. Review operated by Muse under the user's explicit
  instruction, recorded as `muse-demo` (not as a person): the
  propose→review→approve loop with Meta was tested end to
  end (automated test, NOT a human review).
- Eligibility: Idea declared eligible by Adam Blumenfeld (Cerebral Valley) in the project thread, 10/27/2026: https://discord.com/channels/1557169028080869426/1564401698259337216/1564670797908410389 — Scope: administrative debit management, no clinical judgment, fictitious data, human approval. He valued the direct knowledge of the problem and the real chance of implementation. He did not rule separately on pre-existing code or accepted models (the official FAQs apply). Not a security/compliance certification nor an approval of future extensions.
- History with ISO date and time per event; the migration keeps
  prior events with empty `created_at`. Cases `DEMO-META-2` /
  `P-DEMO-META-2-1` and `DEMO-META-3` / `P-DEMO-META-3-1` prepared with
  Meta (proposal and draft visible, 0 reviews), awaiting the
  user's personal decision from the UI. `DEMO-META-3` was
  seeded by real extraction of its generated PDF (`tools/add_case_pdf.py`).
- The demo serves the source PDF (`/api/pdf`, only cases with a
  generated PDF) and states at review time: approving the proposal
  neither accepts the debit nor authorizes messages; nothing sends
  messages or touches external systems.
- The user's PERSONAL review (`deler`, 10/27/2026 3:53 PM -03:00):
  approved `P-DEMO-F123-4` (Agreements/claim) on `DEMO-F123`.
  Chain verified: served source PDF → sums OK (dif 0) →
  4-pt rules → Meta `model_call` ok (muse-spark-1.3, real ID,
  6890ms, 155/1656 tokens) → proposal → review with reviewer,
  proposal, before/after and date/time (no written rationale).
  It is a personal review, distinct from the agent-operated test
  (`muse-demo`). `DEMO-META-2` and `DEMO-META-3` still pending
  (0 reviews).
- Project key in local `.env` (600 perms, Git-ignored);
  never printed or committed. No calls repeated to
  reconfirm what was already evidenced.

Pending:
- Real JSON adapter (implemented, disabled, unverified).
- OCR on documents outside the controlled fixtures.
- Circuit exceptions still open: joint multi-line resolutions
  (single-line only, unconfirmed).
  Settled: "saldo en disputa" (confirmed); multiple documented
  events per rebilling ALLOWED (partial recognition);
  multi-invoice notes ruled out (owner: modeling error);
  accepted-debit text fields suffice; shared-audit conclusion
  (rebill amount within disputed, or accept; terms only).
