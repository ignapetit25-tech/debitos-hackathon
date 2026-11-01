# Architecture

```
Fictitious PDF -> extract.py -> money.py -> CaseStore ----+
   (pypdf / tesseract spa)   (int cents)                 |
                                                         v
contracts.py <-- synthetic.py <-- agent.py --> provider.py
   (ABCs)        (simulator)    (orchestrates)  (meta | simulated)
                     |              |
                     v              v
               approvals.py    drafts.py
               (human required) (templates)
                     |
              real_adapter.py (JSON, OFF, unverified)
```

- `contracts.py`: Case/LineItem/Proposal/Decision/History + ABCs
  (get_case, get_rate, evaluate_rules, save_proposal,
  list_cases). Money always int cents.
- `provider.py`: interface + `MetaProvider` (openai package against
  api.meta.ai, Responses text.format / Chat response_format, explicit
  key) + tagged `SimulatedProvider`.
- `agent.py`: builds the casefile, asks the model for findings, validates
  and persists them; the explanation cites the verified (see README).
- `casefile.py`: deterministic invoice/settlement/agreement reconciliation,
  normalized citation checks, mapping to 4 finding kinds.
- `demo_app.py` + `static/`: JSON API + 3-area UI (shell.html,
  app.css, app.js separated). No innerHTML: all document content
  renders as text. Documents = delimited data, never instruction.
  Clinical trigger -> `route_human` with no economic recommendation.
- `drafts.py`: deterministic templates; the model writes no drafts.
- `process.py`: priority, business-day SLA, checklist.
- `tasks.py`: per-line task circuit (answer with backing,
  debitos verify/return, per-line resolution, rebilling,
  recognition events with issuer, dispute balance, accepted-debit
  closure, accounting docs, reconciliation, shared audits,
  alerts).
  `approvals.followup` and `tasks.record_recovery` are legacy,
  kept only for old records and unit tests.
- Boundaries: rule score (int) and extraction confidence (float)
  are distinct fields; proposals and decisions are separate records.
