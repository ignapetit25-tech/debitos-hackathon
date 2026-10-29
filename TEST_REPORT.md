# Test report

## Deterministic metrics (no model)

Run (local environment):
- API-free suite: 42 tests OK (37 prior + 5 Baseten offline:
  explicit no-key, default model/base, timeout 60 and
  max_retries 0, net error with no faked success, chat-only;
  2 live skipped). Full code translated to English
  (`feat/english-rewrite`): package `debit_ai`, English API/UI,
  Spanish kept only in fictitious domain text.
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
  checklist (lines, sums, copays, agreement, owner),
  validated reply (decision, whole amounts, owner, date)
  with a `followup` event. Shot `docs/shots/05-process.png`.
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
- UI verified in a real JS engine (jsdom against the server): Meta
  banner, 10 inbox cases, casefile, 10 findings, 3 documents,
  history; 0 JS errors; 0 innerHTML uses.
- Shots `docs/shots/01-inbox.png` … `04-review.png`
  (Playwright against the local page, 0 JS errors, 0 inferences):
  inbox with states and amounts, reconciled `EXP-900` casefile,
  evidence with citation-OK / CITATION UNVERIFIED findings and a
  pending review form (undecided). NOTE: shots predate the English
  UI rewrite (Spanish UI shown). Pending cosmetic detail:
  column widths in narrow tables.
- Meta-required fix: `EXPLANATION_SCHEMA` needed
  `"additionalProperties": False` (strict mode). The
  earlier `AuthenticationError` only proved connectivity and credential
  rejection; it did NOT validate the schema. The schema was validated
  by the later successful call.
- LIMIT: the test's approval is automated (`reviewer-milestone`);
  it does NOT stand for a real human review.
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
