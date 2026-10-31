# Video script

Opening note (verbatim):

> The back-office system already existed. During this hackathon
> I built this independent AI layer and its demo with fully
> fictitious data.

## Who and why (0:10)

> I run the debit department of an Argentine outpatient clinic, where I
> deal daily with deductions from obras sociales, prepagas, and ART. I
> designed this project to cut the manual work of reading, reconciling,
> routing, and following up, while keeping final decisions with people.

## Walkthrough (0:40–2:30)

1. Casefile `EXP-900` → 3 source documents (invoice,
   settlement, agreement with validity).
2. Extraction: 2 lines, text source, confidence 1.0, no flags.
3. Reconciliation: $16,500 + $42,000 = $58,500, dif 0 (whole
   cents); agreed values current at service time. Arithmetic
   only — no claim about what is recoverable.
4. Proposal: route to the Agreements team with the literal
   payer reason and the checks the team must run.
5. Model input (Baseten muse-spark-open): findings with code-checked
   citations (what was verified and what stayed flagged
   unverified).
6. Referral draft: template with checkable data.
7. Personal review in the UI: approving the routing neither accepts
   the debit, nor resolves anything economic, nor authorizes
   messages.
8. History: date/time with zone, model call, reviewer,
   rationale and before/after transition.
9. Clinical case: routing to people with no accept/claim
   recommendation; ambiguous case: mandatory human review.

## Closing (2:30–3:00)

- Idea declared eligible by Adam Blumenfeld (Cerebral Valley),
  10/27/2026: administrative debit management, no clinical judgment,
  fictitious data, human approval. Not a security or
  compliance certification nor an approval of future extensions.
- A future implementation is part of the project's value. The AI layer
  is NOT deployed at the clinic and its benefits were not
  measured in production.
- Separation: deterministic metrics, real provider calls, and
  human review are tracked separately (TEST_REPORT.md).
