"use strict";
const $ = id => document.getElementById(id);
const S = {cases: [], case: null, file: null, props: [], prop: null, modelH: [],
  hist: [], busy: false, selF: -1, provider: null, proc: null, agree: [], circuit: null};
const fmtMoney = c => "$" + (c / 100).toLocaleString("en-US", {minimumFractionDigits: 2});

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined && text !== null) e.textContent = text;
  return e;
}
function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }
function scrollWrap(tb) {
  const d = el("div", "scroll-x", null);
  d.appendChild(tb);
  return d;
}
function status(n, kind, msg) {
  clear(n);
  n.appendChild(el("div", "status " + kind, msg));
}
async function call(m, u, b) {
  const r = await fetch(u, {method: m, headers: {"Content-Type": "application/json"},
    body: b ? JSON.stringify(b) : undefined});
  let j = {};
  try { j = await r.json(); } catch (e) { /* non-JSON body */ }
  if (!r.ok) throw new Error((j && j.error) || ("HTTP " + r.status));
  return j;
}
function parseMoney(s) {
  // Strict US format ONLY (matches fmtMoney display): optional $, digits
  // with optional thousands commas, optional .cents (1-2 digits).
  // Anything else (trailing text, bad grouping, AR-style decimals,
  // empties, negatives) is invalid: never guess silently.
  if (s === undefined || s === null) return null;
  s = String(s).replace(/\$/g, "").replace(/\s/g, "");
  if (!s) return null;
  if (!/^(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?$/.test(s)) return null;
  const n = parseFloat(s.replace(/,/g, ""));
  if (!isFinite(n)) return null;
  return Math.round(n * 100);
}
function badge(ok, warn, txtOk, txtWarn) {
  return el("span", "badge " + (ok ? "ok" : (warn ? "warn" : "bad")),
    (ok ? "✓ " : (warn ? "⚠ " : "✕ ")) + (ok ? txtOk : txtWarn));
}

/* ---------- inbox ---------- */
function renderInbox() {
  const ul = $("cases");
  clear(ul);
  if (!S.cases.length) { status($("inbox-status"), "empty", "No cases."); return; }
  status($("inbox-status"), "", "");
  S.cases.forEach((c, i) => {
    const li = el("li", null, null);
    li.setAttribute("role", "option");
    li.tabIndex = 0;
    li.setAttribute("aria-selected", S.case && S.case.id === c.id ? "true" : "false");
    const t1 = el("div", "t1", null);
    t1.appendChild(el("span", null, c.id));
    t1.appendChild(badge(c.status === "proposed", c.status === "new", c.status, c.status));
    li.appendChild(t1);
    li.appendChild(el("div", "t2", c.payer + " · " + c.invoice));
    li.appendChild(el("div", "amt", fmtMoney(c.total_debit_cents)));
    li.addEventListener("click", () => selectCase(c.id));
    li.addEventListener("keydown", ev => {
      if (ev.key === "Enter") selectCase(c.id);
      if (ev.key === "ArrowDown" && ul.children[i + 1]) ul.children[i + 1].focus();
      if (ev.key === "ArrowUp" && ul.children[i - 1]) ul.children[i - 1].focus();
    });
    ul.appendChild(li);
  });
}

async function selectCase(id) {
  if (S.busy) return;
  S.case = null; S.file = null; S.props = []; S.prop = null; S.modelH = []; S.hist = [];
  S.selF = -1; S.name = ""; S.note = ""; S.draft = null; S.reviewMsg = "";
  S.proc = null; S.agree = []; S.circuit = null;
  renderInbox();
  status($("file-body"), "loading", "Loading casefile…");
  status($("evidence-body"), "loading", "Loading evidence…");
  try {
    const [cj, ej, pj, hj, pr, cc] = await Promise.all([
      call("GET", "/api/case?case_id=" + encodeURIComponent(id)),
      call("GET", "/api/casefile?case_id=" + encodeURIComponent(id)),
      call("GET", "/api/proposals?case_id=" + encodeURIComponent(id)),
      call("GET", "/api/history?case_id=" + encodeURIComponent(id)),
      call("GET", "/api/process?case_id=" + encodeURIComponent(id)),
      call("GET", "/api/circuit?case_id=" + encodeURIComponent(id))]);
    S.case = cj.case; S.file = ej.casefile; S.props = pj.proposals; S.hist = hj.history;
    S.proc = pr; S.circuit = cc;
    try {
      const cv = await call("GET", "/api/agreements?payer=" + encodeURIComponent(S.case.payer));
      S.agree = cv.agreements;
    } catch (e) { S.agree = []; }
    if (S.props.length) await selectProp(S.props[S.props.length - 1].id, true);
    renderInbox(); renderFile(); renderEvidence();
    if (window.innerWidth <= 1000) setView("casefile");
  } catch (e) {
    status($("file-body"), "error", "Could not load: " + e.message);
    status($("evidence-body"), "empty", "—");
  }
}

/* ---------- casefile ---------- */
function renderFile() {
  const n = $("file-body");
  clear(n);
  if (!S.case || !S.file) { status(n, "empty", "Pick a case from the inbox."); return; }
  const c = S.case, e = S.file;
  n.appendChild(el("p", "muted", c.id + " · " + c.payer + " · invoice " +
    c.invoice + " · service " + (c.service_date || "not reported")));
  const sum = el("p", "summary", null);
  sum.appendChild(el("strong", null, fmtMoney(c.total_debit_cents) + " debited · "));
  sum.appendChild(el("span", null, c.status + " · next: " + e.next_step));
  n.appendChild(sum);
  if (S.proc) {
    const pr = el("p", null, null);
    pr.appendChild(badge(S.proc.priority !== "P3", S.proc.priority === "P3",
      "priority " + S.proc.priority, "priority " + S.proc.priority));
    pr.appendChild(el("span", null, " "));
    pr.appendChild(el("span", "muted", S.proc.sla.due ?
      ("SLA replies before " + S.proc.sla.due + " (" + S.proc.sla.days + " business days from " + S.proc.sla.since + ")") :
      "SLA pending routing (5 business days)"));
    n.appendChild(pr);
    n.appendChild(el("h3", null, "Pre-routing checklist"));
    const tc = el("table", null, null);
    S.proc.checklist.forEach(it => {
      const tr = el("tr", null, null);
      tr.appendChild(el("td", null, it.item));
      tr.appendChild(el("td", null, it.value));
      const td = el("td", null, null);
      td.appendChild(badge(it.state === "ok", it.state === "warn", it.state, it.state));
      tr.appendChild(td);
      tc.appendChild(tr);
    });
    n.appendChild(scrollWrap(tc));
    n.appendChild(el("h3", null, c.payer + " agreements"));
    if (!S.agree.length) n.appendChild(el("p", "muted", "No agreements loaded."));
    S.agree.forEach(cv => {
      const vig = c.service_date && cv["from"] <= c.service_date && c.service_date <= cv.to;
      const d = el("p", null, null);
      d.appendChild(badge(vig, !vig, cv.id + " " + cv.version, cv.id + " " + cv.version));
      d.appendChild(el("span", "muted", " " + cv["from"] + " .. " + cv.to + " · " +
        Object.keys(cv.rates).length + " rates"));
      n.appendChild(d);
    });
  }
  const tb = el("table", null, null);
  const hr = el("tr", null, null);
  ["line", "billed", "settled", "difference", "agreed value", "source"]
    .forEach((h, i) => hr.appendChild(el("th", i >= 1 ? "num" : null, h)));
  tb.appendChild(hr);
  e.lines.forEach(r => {
    const tr = el("tr", null, null);
    const lc = el("td", null, null);
    lc.appendChild(el("strong", null, "L" + r.line_no + " " + r.procedure));
    lc.appendChild(el("div", "muted", r.reason));
    tr.appendChild(lc);
    [r.billed_cents, r.settled_cents, r.debit_cents].forEach(v =>
      tr.appendChild(el("td", "num", fmtMoney(v))));
    tr.appendChild(el("td", "num", r.ref_cents === null || r.ref_cents === undefined ? "—" : fmtMoney(r.ref_cents)));
    tr.appendChild(el("td", null, r.ref_source));
    tb.appendChild(tr);
  });
  const tr = el("tr", null, null);
  const lab = el("td", null, null);
  lab.appendChild(el("strong", null, "TOTAL"));
  tr.appendChild(lab);
  const sumK = k => e.lines.reduce((a, r) => a + r[k], 0);
  [sumK("billed_cents"), sumK("settled_cents"), sumK("debit_cents")].forEach(v =>
    tr.appendChild(el("td", "num", fmtMoney(v))));
  tr.appendChild(el("td", "num", e.total_ref_cents === null || e.total_ref_cents === undefined ? "—" : fmtMoney(e.total_ref_cents)));
  tr.appendChild(el("td", null, ""));
  tb.appendChild(tr);
  n.appendChild(scrollWrap(tb));
  n.appendChild(badge(e.sums_ok, false, "sums OK", "INCONSISTENT SUMS"));
  const h3 = el("h3", null, "Checks performed (deterministic code)");
  n.appendChild(h3);
  if (!e.findings.length) n.appendChild(el("p", "muted", "No findings."));
  e.findings.forEach(h => {
    const d = el("div", "card", null);
    d.appendChild(badge(h.kind === "backed_difference", h.kind !== "clinical_human",
      h.kind, h.kind));
    d.appendChild(el("p", null, (h.line_no ? "L" + h.line_no + " · " : "") + h.interpretation));
    if (h.limitations) d.appendChild(el("p", "muted", "Limit: " + h.limitations));
    d.appendChild(el("p", "muted", (h.verified ? "✓ citation verified" : "✕ citation unverified") +
      " · " + h.document + " p." + h.page));
    if ((S.case.documents || []).some(x => x.role === h.document)) {
      const ob = el("button", "sec", "Open " + h.document + " PDF");
      ob.addEventListener("click", () => window.open("/api/pdf?case_id=" +
        encodeURIComponent(S.case.id) + "&role=" + encodeURIComponent(h.document), "_blank"));
      d.appendChild(ob);
    }
    n.appendChild(d);
  });
  if (e.missing.length) {
    n.appendChild(el("h3", null, "Pending items"));
    const ul = el("ul", null, null);
    e.missing.forEach(f => ul.appendChild(el("li", null, f)));
    n.appendChild(ul);
  }
  const nx = el("div", "card next", null);
  nx.appendChild(el("strong", null, "Proposed next step: "));
  nx.appendChild(el("span", null, e.next_step + " (" + e.team + " / " + e.action + ")"));
  n.appendChild(nx);
  renderProposal(n);
}

function renderProposal(n) {
  const d = el("div", "card decision", null);
  d.appendChild(el("h3", null, "Proposal and human review"));
  const row = el("div", "row", null);
  const sel = el("select", null, null);
  sel.id = "ver-sel";
  sel.setAttribute("aria-label", "Proposal version");
  if (!S.props.length) sel.appendChild(el("option", null, "no proposals (request one)"));
  const decided = {};
  S.hist.filter(h => h[1] === "review").forEach(h => {
    const m = /^proposal (\S+) (approved|rejected) by /.exec(h[4] || "");
    if (m) decided[m[1]] = m[2];
  });
  S.props.forEach(p => {
    const o = el("option", null, p.id + " · " + p.team + " / " + p.action +
      (p.degraded ? " · DEGRADED" : "") +
      (decided[p.id] ? " · ✓ " + decided[p.id] : " · undecided"));
    o.value = p.id;
    sel.appendChild(o);
  });
  if (S.prop) sel.value = S.prop;
  sel.addEventListener("change", () => selectProp(sel.value, false));
  row.appendChild(sel);
  const bp = el("button", null, "Request proposal");
  bp.id = "b-propose";
  bp.disabled = S.busy;
  bp.addEventListener("click", requestProposal);
  row.appendChild(bp);
  d.appendChild(row);
  const out = el("div", null, S.reviewMsg || "");
  out.id = "review-out";
  out.setAttribute("aria-live", "polite");
  d.appendChild(out);
  const ya = S.hist.filter(h => h[1] === "review" && (h[4] || "").indexOf(S.prop) >= 0).pop();
  if (ya) {
    d.appendChild(el("p", null, "✔ Already decided: " + ya[4] + " · " + (ya[5] || "")));
    d.appendChild(el("p", "muted", ya[2] || ""));
    n.appendChild(d);
  } else {
  d.appendChild(el("p", "muted", "Approve = accept the routing proposal. It does not accept the debit or authorize messages: the demo sends nothing and changes no external systems."));
  const rn = el("input", null, null);
  rn.id = "r-name"; rn.placeholder = "Your name (reviewer)";
  rn.value = S.name || "";
  rn.addEventListener("input", () => { S.name = rn.value; });
  rn.setAttribute("aria-label", "Reviewer");
  d.appendChild(rn);
  const rt = document.createElement("textarea");
  rt.id = "r-note"; rt.rows = 2;
  rt.placeholder = "Rationale (kept on record)";
  rt.value = S.note || "";
  rt.addEventListener("input", () => { S.note = rt.value; });
  rt.setAttribute("aria-label", "Rationale");
  d.appendChild(rt);
  const r2 = el("div", "row", null);
  const ba = el("button", "ok", "Approve");
  const br = el("button", "no", "Reject");
  ba.disabled = br.disabled = S.busy || !S.prop;
  ba.addEventListener("click", () => decide("approved"));
  br.addEventListener("click", () => decide("rejected"));
  r2.appendChild(ba); r2.appendChild(br);
  d.appendChild(r2);
  d.appendChild(el("p", "muted", S.prop ? ("You review exactly: " + S.prop) : "No proposal selected."));
  }
  const bb = el("button", "sec", "View draft");
  bb.addEventListener("click", viewDraft);
  d.appendChild(bb);
  if (S.draft) {
    const bp2 = el("pre", "doc", S.draft);
    bp2.id = "draft-out";
    d.appendChild(bp2);
  }
  n.appendChild(d);
  renderCircuit(n);
}

async function selectProp(pid, silent) {
  S.prop = pid || null;
  S.modelH = [];
  S.draft = null;
  S.reviewMsg = "";
  if (!pid) { if (!silent) { renderFile(); renderEvidence(); } return; }
  try {
    const j = await call("GET", "/api/findings?proposal_id=" + encodeURIComponent(pid));
    S.modelH = j.findings;
  } catch (e) { S.modelH = []; }
  if (!silent) { renderFile(); renderEvidence(); }
}

async function requestProposal() {
  if (S.busy || !S.case) return;
  S.busy = true;
  renderFile();
  try {
    const j = await call("POST", "/api/propose", {case_id: S.case.id});
    const pj = await call("GET", "/api/proposals?case_id=" + encodeURIComponent(S.case.id));
    S.props = pj.proposals;
    const hj = await call("GET", "/api/history?case_id=" + encodeURIComponent(S.case.id));
    S.hist = hj.history;
    S.busy = false;
    await selectProp(j.proposal.id, true);
    renderFile(); renderEvidence();
  } catch (e) {
    S.busy = false;
    renderFile();
    $("review-out").textContent = "✕ Error requesting proposal: " + e.message;
  }
}

async function viewDraft() {
  if (!S.prop || S.busy) return;
  try {
    const j = await call("GET", "/api/draft?proposal_id=" + encodeURIComponent(S.prop));
    S.draft = j.title + "\n\n" + j.body;
  } catch (e) { S.draft = "✕ " + e.message; }
  renderFile();
}

async function decide(v) {
  if (S.busy || !S.prop) return;
  const nameEl = $("r-name"), noteEl = $("r-note");
  if (!nameEl || !noteEl) return;  // form not rendered (already decided)
  const nom = (nameEl.value || "").trim();
  const nota = (noteEl.value || "").trim();
  if (!nom) { S.reviewMsg = "Type your name as reviewer."; renderFile(); return; }
  S.name = nameEl.value; S.note = noteEl.value;
  S.busy = true;
  renderFile();  // disables buttons: no accidental double submit
  try {
    const j = await call("POST", "/api/review", {proposal_id: S.prop, reviewer: nom,
      verdict: v, note: nota});
    const hj = await call("GET", "/api/history?case_id=" + encodeURIComponent(S.case.id));
    S.hist = hj.history;
    S.busy = false;
    S.reviewMsg = "✓ " + j.decision.verdict.toUpperCase() + " by " +
      j.decision.reviewer + " — " + S.prop + " recorded in history.";
    renderFile(); renderEvidence();
  } catch (e) {
    S.busy = false;
    S.reviewMsg = "✕ Error recording: " + e.message;
    renderFile();
  }
}

/* ---------- circuit: tasks, resolution, rebilling, recovery ---------- */
const TEAMS = ["Agreements", "Billing", "Medical Audit", "Pharmacy"];
function tid(s) { return String(s).replace(/[^A-Za-z0-9_-]/g, "_"); }

async function refreshCircuit() {
  const j = await call("GET", "/api/circuit?case_id=" + encodeURIComponent(S.case.id));
  S.circuit = j;
  const hj = await call("GET", "/api/history?case_id=" + encodeURIComponent(S.case.id));
  S.hist = hj.history;
}
function circuitMsg(msg) {
  const o = $("circuit-out");
  if (o) o.textContent = msg;
}
async function circuitPost(url, body, okMsg) {
  if (S.busy) return;
  S.busy = true;
  try {
    await call("POST", url, body);
    await refreshCircuit();
    S.busy = false;
    renderFile(); renderEvidence();
    circuitMsg(okMsg);
  } catch (e) {
    S.busy = false;
    circuitMsg("Error: " + e.message);
  }
}
function stateBadge(st) {
  return badge(st === "verified", st !== "returned", st, st);
}

function renderCircuit(n) {
  const sg = el("div", "card", null);
  sg.appendChild(el("h3", null, "Line tasks & resolution"));
  const C = S.circuit;
  if (!C) { sg.appendChild(el("p", "muted", "Loading.")); n.appendChild(sg); return; }
  if (!C.tasks.length) sg.appendChild(el("p", "muted", "No tasks yet. Create one per line + sector below."));
  C.tasks.forEach(t => {
    const d = el("div", "card", null);
    const h = el("p", null, null);
    h.appendChild(el("strong", null, t.id + " / L" + t.line_no + " / " + t.team + " "));
    h.appendChild(stateBadge(t.state));
    d.appendChild(h);
    d.appendChild(el("p", "muted", "Motive: " + t.motive));
    if (t.assignee) d.appendChild(el("p", "muted", "Assignee: " + t.assignee));
    if (t.state === "assigned" || t.state === "returned") {
      if (t.state === "returned" && t.return_note)
        d.appendChild(el("p", null, "Debitos asked: " + t.return_note));
      if (t.response) d.appendChild(el("p", "muted", "Prior answer: " + t.response));
      const k = tid(t.id);
      const r1 = el("div", "row", null);
      const rname = el("input", null, null);
      rname.id = "an-" + k + "-responder"; rname.placeholder = "Responder (sector)";
      rname.setAttribute("aria-label", "Responder");
      const bref = el("input", null, null);
      bref.id = "an-" + k + "-backing"; bref.placeholder = "Backing: document or precise reference (required)";
      bref.setAttribute("aria-label", "Backing reference");
      r1.appendChild(rname); r1.appendChild(bref);
      d.appendChild(r1);
      const resp = document.createElement("textarea");
      resp.id = "an-" + k + "-response"; resp.rows = 2;
      resp.placeholder = "Sector response";
      resp.setAttribute("aria-label", "Response");
      d.appendChild(resp);
      const b = el("button", "sec", "Send answer");
      b.setAttribute("data-task", t.id);
      b.setAttribute("data-act", "answer");
      b.disabled = S.busy;
      b.addEventListener("click", () => circuitPost("/api/task/answer", {
        task_id: t.id, responder: $("an-" + k + "-responder").value,
        response: $("an-" + k + "-response").value,
        backing_ref: $("an-" + k + "-backing").value}, "Answer recorded: pending debitos verification."));
      d.appendChild(b);
    } else if (t.state === "pending_verification") {
      d.appendChild(el("p", null, "Answer by " + t.responder + ": " + t.response));
      d.appendChild(el("p", null, "Backing: " + t.backing_ref));
      const k = tid(t.id);
      const rev = el("input", null, null);
      rev.id = "vf-" + k + "-reviewer"; rev.placeholder = "Debitos reviewer";
      rev.setAttribute("aria-label", "Debitos reviewer");
      d.appendChild(rev);
      const note = el("input", null, null);
      note.id = "vf-" + k + "-note"; note.placeholder = "Note (accept) or what is missing (return)";
      note.setAttribute("aria-label", "Verification note");
      d.appendChild(note);
      const r2 = el("div", "row", null);
      const ba = el("button", "ok", "Verify");
      ba.setAttribute("data-task", t.id); ba.setAttribute("data-act", "verify");
      ba.disabled = S.busy;
      ba.addEventListener("click", () => circuitPost("/api/task/verify", {
        task_id: t.id, reviewer: $("vf-" + k + "-reviewer").value,
        note: $("vf-" + k + "-note").value}, "Task verified."));
      const br = el("button", "no", "Return to sector");
      br.setAttribute("data-task", t.id); br.setAttribute("data-act", "return");
      br.disabled = S.busy;
      br.addEventListener("click", () => circuitPost("/api/task/return", {
        task_id: t.id, reviewer: $("vf-" + k + "-reviewer").value,
        missing: $("vf-" + k + "-note").value}, "Task returned to sector."));
      r2.appendChild(ba); r2.appendChild(br);
      d.appendChild(r2);
    } else {
      d.appendChild(el("p", null, "Verified. Answer by " + t.responder + ": " + t.response));
      d.appendChild(el("p", "muted", "Backing: " + t.backing_ref));
    }
    sg.appendChild(d);
  });
  sg.appendChild(el("h3", null, "New task"));
  const c1 = el("div", "row", null);
  const ln = el("input", null, null);
  ln.id = "ct-line"; ln.placeholder = "Line #"; ln.setAttribute("aria-label", "Line number");
  const tm = el("select", null, null);
  tm.id = "ct-team"; tm.setAttribute("aria-label", "Team");
  TEAMS.forEach(v => tm.appendChild(el("option", null, v)));
  const as = el("input", null, null);
  as.id = "ct-assignee"; as.placeholder = "Assignee (optional)"; as.setAttribute("aria-label", "Assignee");
  c1.appendChild(ln); c1.appendChild(tm); c1.appendChild(as);
  sg.appendChild(c1);
  const mo = el("input", null, null);
  mo.id = "ct-motive"; mo.placeholder = "Literal motive this task answers (required)";
  mo.setAttribute("aria-label", "Motive");
  sg.appendChild(mo);
  const bc = el("button", "sec", "Create task");
  bc.id = "b-task-new"; bc.disabled = S.busy;
  bc.addEventListener("click", () => {
    const n = parseInt($("ct-line").value, 10);
    if (!n) { circuitMsg("Type the line number."); return; }
    circuitPost("/api/task", {case_id: S.case.id, line_no: n,
      team: $("ct-team").value, motive: $("ct-motive").value,
      assignee: $("ct-assignee").value}, "Task created.");
  });
  sg.appendChild(bc);
  sg.appendChild(el("h3", null, "Per-line resolutions"));
  if (!C.resolutions.length) sg.appendChild(el("p", "muted", "No resolutions."));
  C.resolutions.forEach(r => {
    sg.appendChild(el("p", null, "L" + r.line_no + " resolved by " + r.decided_by + ": " + r.decision));
    if (r.note) sg.appendChild(el("p", "muted", r.note));
  });
  const s1 = el("div", "row", null);
  const sl = el("input", null, null);
  sl.id = "rs-line"; sl.placeholder = "Line #"; sl.setAttribute("aria-label", "Resolution line");
  const sd = el("input", null, null);
  sd.id = "rs-by"; sd.placeholder = "Decided by"; sd.setAttribute("aria-label", "Decided by");
  s1.appendChild(sl); s1.appendChild(sd);
  sg.appendChild(s1);
  const sz = el("input", null, null);
  sz.id = "rs-decision"; sz.placeholder = "Administrative decision (required)";
  sz.setAttribute("aria-label", "Decision");
  sg.appendChild(sz);
  const bs = el("button", "sec", "Resolve line");
  bs.id = "b-resolve"; bs.disabled = S.busy;
  bs.addEventListener("click", () => {
    const n = parseInt($("rs-line").value, 10);
    if (!n) { circuitMsg("Type the line number."); return; }
    circuitPost("/api/resolution", {case_id: S.case.id, line_no: n,
      decided_by: $("rs-by").value, decision: $("rs-decision").value},
      "Line resolved (individual; no mass close).");
  });
  sg.appendChild(bs);
  sg.appendChild(el("h3", null, "Rebilling invoices (not recovered money)"));
  if (!C.rebillings.length) sg.appendChild(el("p", "muted", "No rebillings."));
  C.rebillings.forEach(r => {
    sg.appendChild(el("p", null, r.number + " / " + fmtMoney(r.amount_cents) +
      " / " + r.payer + " / from " + r.resolution_id));
  });
  const b1 = el("div", "row", null);
  const bl = el("input", null, null);
  bl.id = "rb-line"; bl.placeholder = "Line #"; bl.setAttribute("aria-label", "Rebilling line");
  const bn = el("input", null, null);
  bn.id = "rb-number"; bn.placeholder = "New invoice number"; bn.setAttribute("aria-label", "Invoice number");
  const ba2 = el("input", null, null);
  ba2.id = "rb-amount"; ba2.placeholder = "Amount $ (e.g. 12,500.50)";
  ba2.setAttribute("aria-label", "Rebilling amount");
  b1.appendChild(bl); b1.appendChild(bn); b1.appendChild(ba2);
  sg.appendChild(b1);
  const b2 = el("div", "row", null);
  const bp = el("input", null, null);
  bp.id = "rb-payer"; bp.placeholder = "Payer"; bp.setAttribute("aria-label", "Payer");
  const bd = el("input", null, null);
  bd.id = "rb-date"; bd.type = "date"; bd.setAttribute("aria-label", "Rebilling date");
  b2.appendChild(bp); b2.appendChild(bd);
  sg.appendChild(b2);
  const bb = el("button", "sec", "Record rebilling");
  bb.id = "b-rebill"; bb.disabled = S.busy;
  bb.addEventListener("click", () => {
    const n = parseInt($("rb-line").value, 10);
    const amt = parseMoney($("rb-amount").value);
    if (!n) { circuitMsg("Type the line number."); return; }
    if (amt === null) { circuitMsg("Invalid amount: use 12,500.50 format."); return; }
    circuitPost("/api/rebilling", {case_id: S.case.id, line_no: n,
      number: $("rb-number").value, amount_cents: amt,
      payer: $("rb-payer").value, date: $("rb-date").value},
      "Rebilling recorded (not recovered money).");
  });
  sg.appendChild(bb);
  if ((C.alerts || []).length) {
    sg.appendChild(el("h3", null, "Needs attention"));
    C.alerts.forEach(a => sg.appendChild(el("p", null, "! " + a)));
  }
  sg.appendChild(el("h3", null, "Recognition events (per rebilling)"));
  const recs = C.recognitions || [];
  if (!recs.length) sg.appendChild(el("p", "muted", "No recognitions recorded."));
  recs.forEach(r => {
    sg.appendChild(el("p", null, r.id + " / " + r.kind + " / " + fmtMoney(r.amount_cents) +
      " / " + r.reference + " (confirmed by " + r.confirmed_by +
      "; recorded by " + r.recorded_by + ")" +
      (r.duplicate_of ? " [duplicate of " + r.duplicate_of + "]" : "")));
  });
  (C.rebillings || []).forEach(b => {
    const st = (C.rebilling_status || {})[b.id];
    if (st) {
      sg.appendChild(el("p", null, b.id + ": recognized " + fmtMoney(st.recognized_cents) +
        " of " + fmtMoney(b.amount_cents) +
        (st.disputed_cents > 0 ? " / BALANCE IN DISPUTE " + fmtMoney(st.disputed_cents) : "")));
    }
  });
  if (C.rebillings.length) {
    const v1 = el("div", "row", null);
    const vs = el("select", null, null);
    vs.id = "rc-rebilling"; vs.setAttribute("aria-label", "Rebilling");
    C.rebillings.forEach(r => vs.appendChild(el("option", null, r.id)));
    const vm = el("select", null, null);
    vm.id = "rc-kind"; vm.setAttribute("aria-label", "Kind");
    ["financier_credit_note", "provider_credit_note", "treasury_confirmation", "rebilling_paid"].forEach(v => vm.appendChild(el("option", null, v)));
    v1.appendChild(vs); v1.appendChild(vm);
    sg.appendChild(v1);
    const v2 = el("div", "row", null);
    const va = el("input", null, null);
    va.id = "rc-amount"; va.placeholder = "Amount $ (required)";
    va.setAttribute("aria-label", "Amount");
    const vr = el("input", null, null);
    vr.id = "rc-reference"; vr.placeholder = "Evidence reference (required)";
    vr.setAttribute("aria-label", "Reference");
    v2.appendChild(va); v2.appendChild(vr);
    sg.appendChild(v2);
    const v3 = el("div", "row", null);
    const vc = el("input", null, null);
    vc.id = "rc-confirmed"; vc.placeholder = "Issuer / confirming sector";
    vc.setAttribute("aria-label", "Confirmed by");
    const vd = el("input", null, null);
    vd.id = "rc-recorded"; vd.placeholder = "Recording owner";
    vd.setAttribute("aria-label", "Recorded by");
    const ve = el("input", null, null);
    ve.id = "rc-date"; ve.type = "date"; ve.setAttribute("aria-label", "Date");
    v3.appendChild(vc); v3.appendChild(vd); v3.appendChild(ve);
    sg.appendChild(v3);
    const bv = el("button", "sec", "Record recognition");
    bv.id = "b-recognize"; bv.disabled = S.busy;
    bv.addEventListener("click", () => {
      const amt = parseMoney($("rc-amount").value);
      if (amt === null) { circuitMsg("Invalid amount: use 12,500.50 format."); return; }
      circuitPost("/api/recognition", {rebilling_id: $("rc-rebilling").value,
        kind: $("rc-kind").value, amount_cents: amt,
        reference: $("rc-reference").value, confirmed_by: $("rc-confirmed").value,
        recorded_by: $("rc-recorded").value, date: $("rc-date").value},
        "Recognition recorded.");
    });
    sg.appendChild(bv);
    if (recs.length > 1) {
      const x1 = el("div", "row", null);
      const xe = el("select", null, null);
      xe.id = "rx-event"; xe.setAttribute("aria-label", "Event");
      recs.forEach(r => xe.appendChild(el("option", null, r.id)));
      const xd = el("select", null, null);
      xd.id = "rx-dupof"; xd.setAttribute("aria-label", "Duplicate of");
      recs.forEach(r => xd.appendChild(el("option", null, r.id)));
      const xb = el("input", null, null);
      xb.id = "rx-by"; xb.placeholder = "Reconciled by"; xb.setAttribute("aria-label", "Reconciled by");
      x1.appendChild(xe); x1.appendChild(xd); x1.appendChild(xb);
      sg.appendChild(x1);
      const bx = el("button", "sec", "Mark as duplicate");
      bx.id = "b-reconcile"; bx.disabled = S.busy;
      bx.addEventListener("click", () => circuitPost("/api/reconcile", {
        event_id: $("rx-event").value, duplicate_of: $("rx-dupof").value,
        reconciled_by: $("rx-by").value}, "Recognition reconciled."));
      sg.appendChild(bx);
    }
  } else {
    sg.appendChild(el("p", "muted", "Record a rebilling first."));
  }
  sg.appendChild(el("h3", null, "Accepted debits (terminal closure)"));
  const accs = C.accepted || [];
  if (!accs.length) sg.appendChild(el("p", "muted", "No accepted debits."));
  accs.forEach(a => {
    sg.appendChild(el("p", null, "L" + a.line_no + " accepted by " + a.accepted_by + ": " + a.origin));
    if (a.corrective) sg.appendChild(el("p", "muted", "Corrective: " + a.corrective));
  });
  const a1 = el("div", "row", null);
  const al = el("input", null, null);
  al.id = "ac-line"; al.placeholder = "Line #"; al.setAttribute("aria-label", "Line");
  const ab = el("input", null, null);
  ab.id = "ac-by"; ab.placeholder = "Accepted by"; ab.setAttribute("aria-label", "Accepted by");
  a1.appendChild(al); a1.appendChild(ab);
  sg.appendChild(a1);
  const ao = el("input", null, null);
  ao.id = "ac-origin"; ao.placeholder = "Analyzed origin (required)";
  ao.setAttribute("aria-label", "Origin");
  sg.appendChild(ao);
  const aw = el("input", null, null);
  aw.id = "ac-corrective"; aw.placeholder = "Corrective action (optional)";
  aw.setAttribute("aria-label", "Corrective");
  sg.appendChild(aw);
  const ba3 = el("button", "sec", "Accept debit");
  ba3.id = "b-accept"; ba3.disabled = S.busy;
  ba3.addEventListener("click", () => {
    const n = parseInt($("ac-line").value, 10);
    if (!n) { circuitMsg("Type the line number."); return; }
    circuitPost("/api/accept-debit", {case_id: S.case.id, line_no: n,
      accepted_by: $("ac-by").value, origin: $("ac-origin").value,
      corrective: $("ac-corrective").value}, "Debit accepted (terminal closure).");
  });
  sg.appendChild(ba3);
  sg.appendChild(el("h3", null, "Accounting documents (not an authorization)"));
  const docs = C.accounting_docs || [];
  if (!docs.length) sg.appendChild(el("p", "muted", "No accounting documents."));
  docs.forEach(x => {
    sg.appendChild(el("p", null, x.id + " / " + x.kind + " / " + x.number +
      ((x.amount_cents !== null && x.amount_cents !== undefined) ? " / " + fmtMoney(x.amount_cents) : "") +
      ((x.line_no !== null && x.line_no !== undefined) ? " / L" + x.line_no : " / case") +
      " (recorded by " + x.recorded_by + ")"));
  });
  const g1 = el("div", "row", null);
  const gl = el("input", null, null);
  gl.id = "ad-line"; gl.placeholder = "Line # (optional)"; gl.setAttribute("aria-label", "Line");
  const gn = el("input", null, null);
  gn.id = "ad-number"; gn.placeholder = "Document number (required)";
  gn.setAttribute("aria-label", "Number");
  const gm = el("input", null, null);
  gm.id = "ad-amount"; gm.placeholder = "Observed $ (optional)";
  gm.setAttribute("aria-label", "Amount");
  g1.appendChild(gl); g1.appendChild(gn); g1.appendChild(gm);
  sg.appendChild(g1);
  const g2 = el("div", "row", null);
  const gd = el("input", null, null);
  gd.id = "ad-date"; gd.type = "date"; gd.setAttribute("aria-label", "Date");
  const gb = el("input", null, null);
  gb.id = "ad-by"; gb.placeholder = "Recorded by"; gb.setAttribute("aria-label", "Recorded by");
  g2.appendChild(gd); g2.appendChild(gb);
  sg.appendChild(g2);
  const bdoc = el("button", "sec", "Record accounting doc");
  bdoc.id = "b-accdoc"; bdoc.disabled = S.busy;
  bdoc.addEventListener("click", () => {
    const raw = $("ad-line").value.trim();
    const n = raw ? parseInt(raw, 10) : null;
    if (raw && !n) { circuitMsg("Invalid line number."); return; }
    const mraw = $("ad-amount").value.trim();
    const amt = mraw ? parseMoney(mraw) : null;
    if (mraw && amt === null) { circuitMsg("Invalid amount: use 12,500.50 format."); return; }
    const body = {case_id: S.case.id, line_no: n, kind: "provider_credit_note",
      number: $("ad-number").value, recorded_by: $("ad-by").value,
      date: $("ad-date").value};
    if (amt !== null) body.amount_cents = amt;
    circuitPost("/api/accounting-doc", body, "Accounting doc recorded (not an authorization).");
  });
  sg.appendChild(bdoc);
  sg.appendChild(el("h3", null, "Shared audits (by email)"));
  const aus = C.shared_audits || [];
  if (!aus.length) sg.appendChild(el("p", "muted", "No shared audits."));
  aus.forEach(a => {
    sg.appendChild(el("p", null, a.id + ": dispute on " + a.origin_rebilling_id +
      " followed to " + a.new_case_id + " (" + a.new_motive + "); requested by " +
      a.requested_by + " with " + a.company_auditor + " + " + a.payer_side + " by email"));
  });
  if (C.rebillings.length) {
    const u1 = el("div", "row", null);
    const us = el("select", null, null);
    us.id = "sa-rebilling"; us.setAttribute("aria-label", "Origin rebilling");
    C.rebillings.forEach(r => us.appendChild(el("option", null, r.id)));
    const uc = el("input", null, null);
    uc.id = "sa-case"; uc.placeholder = "New debit case id";
    uc.setAttribute("aria-label", "New case");
    const um = el("input", null, null);
    um.id = "sa-motive"; um.placeholder = "New motive (required)";
    um.setAttribute("aria-label", "New motive");
    u1.appendChild(us); u1.appendChild(uc); u1.appendChild(um);
    sg.appendChild(u1);
    const u2 = el("div", "row", null);
    const ub = el("input", null, null);
    ub.id = "sa-by"; ub.placeholder = "Requested by"; ub.setAttribute("aria-label", "Requested by");
    const ua = el("input", null, null);
    ua.id = "sa-auditor"; ua.placeholder = "Company auditor"; ua.setAttribute("aria-label", "Auditor");
    const up = el("input", null, null);
    up.id = "sa-payer"; up.placeholder = "Payer side"; up.setAttribute("aria-label", "Payer side");
    u2.appendChild(ub); u2.appendChild(ua); u2.appendChild(up);
    sg.appendChild(u2);
    const bu = el("button", "sec", "Request shared audit");
    bu.id = "b-audit"; bu.disabled = S.busy;
    bu.addEventListener("click", () => circuitPost("/api/shared-audit", {
      origin_rebilling_id: $("sa-rebilling").value, new_case_id: $("sa-case").value,
      new_motive: $("sa-motive").value, requested_by: $("sa-by").value,
      company_auditor: $("sa-auditor").value, payer_side: $("sa-payer").value,
      channel: "email"}, "Shared audit requested (by email)."));
    sg.appendChild(bu);
  }
  const so = el("div", null, null);
  so.id = "circuit-out";
  so.setAttribute("aria-live", "polite");
  sg.appendChild(so);
  n.appendChild(sg);
}

/* ---------- evidence ---------- */
function renderEvidence() {
  const n = $("evidence-body");
  clear(n);
  if (!S.case) { status(n, "empty", "Pick a case."); return; }
  n.appendChild(el("h3", null, "Documents"));
  const docs = S.case.documents || [];
  if (!docs.length && !S.case.pdf) n.appendChild(el("p", "muted", "No linked documents."));
  docs.forEach(d => {
    const b = el("button", "sec", d.role + " (PDF)");
    b.addEventListener("click", () => window.open("/api/pdf?case_id=" +
      encodeURIComponent(S.case.id) + "&role=" + encodeURIComponent(d.role), "_blank"));
    n.appendChild(b);
    n.appendChild(el("span", null, " "));
  });
  if (S.case.pdf && !docs.length) {
    const b = el("button", "sec", "document (PDF)");
    b.addEventListener("click", () => window.open("/api/pdf?case_id=" +
      encodeURIComponent(S.case.id), "_blank"));
    n.appendChild(b);
  }
  n.appendChild(el("h3", null, "Model findings" + (S.prop ? " · " + S.prop : "")));
  if (!S.prop) n.appendChild(el("p", "muted", "No proposal selected."));
  else if (!S.modelH.length) n.appendChild(el("p", "muted", "No model findings."));
  S.modelH.forEach((h, i) => {
    const b = el("button", "finding", null);
    b.setAttribute("aria-current", S.selF === i ? "true" : "false");
    b.appendChild(badge(h.verified, false, "citation OK", "CITATION UNVERIFIED"));
    b.appendChild(el("span", null, " [" + h.kind + "] " +
      (h.line_no ? "L" + h.line_no + " · " : "") + h.interpretation.slice(0, 90)));
    b.addEventListener("click", () => { S.selF = i; renderEvidence(); });
    n.appendChild(b);
  });
  if (S.selF >= 0 && S.modelH[S.selF]) {
    const h = S.modelH[S.selF];
    const d = el("div", "card", null);
    d.appendChild(el("blockquote", null, h.excerpt));
    d.appendChild(el("p", "muted", h.document + " · page " + h.page +
      (h.verified ? " · ✓ reference exists and citation matches" :
        " · ✕ missing reference or citation mismatch")));
    d.appendChild(el("p", null, h.interpretation));
    if (h.limitations) d.appendChild(el("p", "muted", "Limitations: " + h.limitations));
    d.appendChild(el("p", "muted", "Verified validates the citation, not the interpretation."));
    if ((S.case.documents || []).some(x => x.role === h.document)) {
      const ob = el("button", "sec", "Open " + h.document + " PDF (p." + h.page + ")");
      ob.addEventListener("click", () => window.open("/api/pdf?case_id=" +
        encodeURIComponent(S.case.id) + "&role=" + encodeURIComponent(h.document), "_blank"));
      d.appendChild(ob);
    }
    n.appendChild(d);
  }
  const det = el("details", "meta", null);
  det.appendChild(el("summary", null, "Technical details (" + (S.provider || "?") + ")"));
  const calls = S.hist.filter(h => h[1] === "model_call");
  const last = calls.filter(h => (h[2] || "").includes("proposal=" + S.prop)).pop()
    || calls.pop();  // legacy events carry no proposal id
  det.appendChild(el("p", null, "Configured provider: " + (S.provider || "?")));
  det.appendChild(el("p", null, last ? ("Last call: " + last[2] + " → " + last[4]) :
    "No model calls on this case."));
  det.appendChild(el("p", "muted", "Success and degraded mode are reported per proposal, not globally."));
  n.appendChild(det);
  n.appendChild(el("h3", null, "History"));
  if (!S.hist.length) { n.appendChild(el("p", "muted", "No events.")); return; }
  const evtLast = S.hist[S.hist.length - 1];
  n.appendChild(el("p", "muted", S.hist.length + " events · last: " +
    evtLast[1] + " " + (evtLast[5] || "")));
  const ICON = {proposal: "✓", review: "✔", model_call: "◈", gate: "⛔", task: "→", task_verify: "✔", task_return: "↩", resolution: "●", rebilling: "▸", recovery: "◆", recognition: "◆", reconcile: "=", accepted: "■", accounting_doc: "▤", shared_audit: "✉"};
  S.hist.filter(h => ICON[h[1]]).forEach(h => {
    const d = el("p", null, null);
    d.appendChild(el("strong", null, ICON[h[1]] + " " + h[1] + " "));
    d.appendChild(el("span", "muted", (h[5] || "") + " · "));
    d.appendChild(el("span", null, (h[4] || h[2] || "").slice(0, 110)));
    n.appendChild(d);
  });
  const det2 = el("details", "meta", null);
  det2.appendChild(el("summary", null, "Full technical log (" + S.hist.length + ")"));
  const tb = el("table", null, null);
  const hr = el("tr", null, null);
  ["#", "date/time", "kind", "detail", "before", "after"].forEach(h =>
    hr.appendChild(el("th", null, h)));
  tb.appendChild(hr);
  S.hist.forEach(h => {
    const tr = el("tr", null, null);
    [h[0], h[5] || "—", h[1], h[2], h[3] || "", h[4] || ""].forEach(v =>
      tr.appendChild(el("td", null, String(v))));
    tb.appendChild(tr);
  });
  det2.appendChild(scrollWrap(tb));
  n.appendChild(det2);
}

/* ---------- init ---------- */
function setView(v) {
  document.body.setAttribute("data-view", v);
  ["inbox", "casefile", "evidence"].forEach(k =>
    $("tab-" + k).disabled = (k === v));
}
async function init() {
  document.body.setAttribute("data-view", "inbox");
  ["inbox", "casefile", "evidence"].forEach(k =>
    $("tab-" + k).addEventListener("click", () => setView(k)));
  try {
    const p = await call("GET", "/api/provider");
    S.provider = p.provider;
    const e = $("provider");
    e.textContent = "Configured provider: " + p.provider +
      (p.simulated ? " — SIMULATED (proves nothing about the provider)" : " — real " + p.provider);
    e.className = "banner " + (p.simulated ? "sim" : "meta");
    const c = await call("GET", "/api/cases");
    S.cases = c.cases;
    renderInbox();
    const main = S.cases.find(x => x.id === "EXP-900");
    if (main) selectCase(main.id);
    else {
      status($("file-body"), "empty", "Pick a case from the inbox.");
      status($("evidence-body"), "empty", "Pick a case from the inbox.");
    }
  } catch (e) {
    $("provider").textContent = "✕ Connection error: " + e.message;
    status($("inbox-status"), "error", "Could not load.");
  }
}
init();
