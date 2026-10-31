# Demo script (3 minutes, live)

[0:00] Opening: the back-office system already existed. This is an
independent AI layer built during the hackathon, with a fully
fictitious demo and data. Origin: I run the debit department of an
Argentine outpatient clinic.
[0:25] Case `EXP-900`: inbox → casefile with 3 documents
(invoice, settlement, agreement). Table: billed, settled,
difference and agreed value current at service time. Differences
are arithmetic checks only; they never decide merit.
[0:50] Deterministic checks + missing items + next step. Request
proposal: route to the Agreements team with the literal payer
reason and the checks the team must run. Model findings carry
code-checked citations (verified vs flagged unverified).
[1:20] Evidence: click a finding → excerpt, document, page,
interpretation and limitations. Model details in a dropdown.
Draft: referral template, a proposal, not a sending.
[1:50] Review: approving the routing does NOT accept the debit, does
NOT resolve anything economic, and does NOT authorize messages;
the demo sends nothing and touches no external systems.
[2:10] History: date/time with zone, model call (provider,
ID, latency, usage), proposal and reasoned decision.
[2:30] Second case (clinical or ambiguous): routes to people
("Medical Audit" is a human destination team), without forcing
conclusions. The AI classifies and routes; it never judges
clinical merit.
[2:40] Task circuit (EXP-2501, fictitious): per-line tasks to
Billing and Medical Audit, one line with Agreements + Billing, a
returned insufficient answer, debitos verifications, individual
per-line resolution, linked rebilling invoice (not money),
recovery with labeled fictitious evidence.
[2:55] Closing: idea declared eligible by Adam Blumenfeld (Cerebral
Valley) on 10/27/2026 for administrative management with fictitious
data and human approval. Real vs simulated vs pending in
TEST_REPORT.md. Future implementation is a possibility, not a deployment.
