"use strict";
const $ = id => document.getElementById(id);
const S = {cases: [], case: null, file: null, props: [], prop: null, modelH: [],
  hist: [], busy: false, selF: -1, provider: null, proc: null, agree: [], fol: null};
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
  S.proc = null; S.agree = []; S.fol = null; S.approved = false;
  renderInbox();
  status($("file-body"), "loading", "Loading casefile…");
  status($("evidence-body"), "loading", "Loading evidence…");
  try {
    const [cj, ej, pj, hj, pr] = await Promise.all([
      call("GET", "/api/case?case_id=" + encodeURIComponent(id)),
      call("GET", "/api/casefile?case_id=" + encodeURIComponent(id)),
      call("GET", "/api/proposals?case_id=" + encodeURIComponent(id)),
      call("GET", "/api/history?case_id=" + encodeURIComponent(id)),
      call("GET", "/api/process?case_id=" + encodeURIComponent(id))]);
    S.case = cj.case; S.file = ej.casefile; S.props = pj.proposals; S.hist = hj.history;
    S.proc = pr;
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
  const sg = el("div", "card", null);
  sg.appendChild(el("h3", null, "Team reply (follow-up)"));
  if (S.fol) {
    sg.appendChild(el("p", null, S.fol.decision + " · recoverable " + fmtMoney(S.fol.recoverable_cents) +
      " · accepted " + fmtMoney(S.fol.accepted_cents)));
    sg.appendChild(el("p", "muted", "Owner: " + S.fol.owner + " · " + S.fol.date +
      (S.fol.note ? " · " + S.fol.note : "")));
  } else {
    sg.appendChild(el("p", "muted", S.prop ? "No reply recorded." : "Pick a proposal."));
  }
  if (S.prop) {
    const sel = el("select", null, null);
    sel.id = "fo-dec";
    sel.setAttribute("aria-label", "Team decision");
    ["pending", "recovered", "partial", "accepted"].forEach(v =>
      sel.appendChild(el("option", null, v)));
    if (S.fol) sel.value = S.fol.decision;
    sg.appendChild(sel);
    const r1 = el("div", "row", null);
    const ri = el("input", null, null);
    ri.id = "fo-rec"; ri.placeholder = "Recoverable $ (e.g. 12,500.50)";
    ri.setAttribute("aria-label", "Recoverable amount");
    ri.value = S.fol ? (S.fol.recoverable_cents / 100).toString() : "";
    const ai = el("input", null, null);
    ai.id = "fo-acc"; ai.placeholder = "Accepted $ (e.g. 0)";
    ai.setAttribute("aria-label", "Accepted amount");
    ai.value = S.fol ? (S.fol.accepted_cents / 100).toString() : "";
    r1.appendChild(ri); r1.appendChild(ai);
    sg.appendChild(r1);
    const r2 = el("div", "row", null);
    const rs = el("input", null, null);
    rs.id = "fo-owner"; rs.placeholder = "Team owner";
    rs.setAttribute("aria-label", "Owner");
    rs.value = S.fol ? S.fol.owner : "";
    const fe = el("input", null, null);
    fe.id = "fo-date"; fe.type = "date";
    fe.setAttribute("aria-label", "Reply date");
    fe.value = S.fol ? S.fol.date : "";
    r2.appendChild(rs); r2.appendChild(fe);
    sg.appendChild(r2);
    const nt = document.createElement("textarea");
    nt.id = "fo-note"; nt.rows = 2;
    nt.placeholder = "Note (optional)";
    nt.setAttribute("aria-label", "Follow-up note");
    nt.value = S.fol ? (S.fol.note || "") : "";
    sg.appendChild(nt);
    if (!S.approved)
      sg.appendChild(el("p", "muted", "Needs an approved review first."));
    const bs = el("button", "sec", "Save reply");
    bs.disabled = S.busy || !S.approved;
    bs.addEventListener("click", saveFollowup);
    sg.appendChild(bs);
    const so = el("div", null, null);
    so.id = "fo-out";
    so.setAttribute("aria-live", "polite");
    sg.appendChild(so);
  }
  n.appendChild(sg);
}

async function selectProp(pid, silent) {
  S.prop = pid || null;
  S.modelH = [];
  S.draft = null;
  S.fol = null;
  S.approved = false;
  S.reviewMsg = "";
  if (!pid) { if (!silent) { renderFile(); renderEvidence(); } return; }
  try {
    const j = await call("GET", "/api/findings?proposal_id=" + encodeURIComponent(pid));
    S.modelH = j.findings;
    const g = await call("GET", "/api/followup?proposal_id=" + encodeURIComponent(pid));
    S.fol = g.followup;
    S.approved = !!g.approved;
  } catch (e) { S.modelH = []; S.fol = null; }
  if (!silent) { renderFile(); renderEvidence(); }
}

async function saveFollowup() {
  if (S.busy || !S.prop || !S.approved) return;
  const rec = parseMoney($("fo-rec").value);
  const ace = parseMoney($("fo-acc").value);
  const resp = $("fo-owner").value.trim();
  if (rec === null || ace === null) { $("fo-out").textContent = "✕ Invalid amounts: use 12,500.50 format (explicit 0, no negatives)."; return; }
  if (!resp) { $("fo-out").textContent = "Type the team owner."; return; }
  S.busy = true;
  try {
    const j = await call("POST", "/api/followup", {proposal_id: S.prop,
      decision: $("fo-dec").value, recoverable_cents: rec, accepted_cents: ace,
      owner: resp, date: $("fo-date").value, note: $("fo-note").value.trim()});
    S.fol = j.followup;
    const hj = await call("GET", "/api/history?case_id=" + encodeURIComponent(S.case.id));
    S.hist = hj.history;
    S.busy = false;
    renderFile(); renderEvidence();
    $("fo-out").textContent = "✓ Reply recorded.";
  } catch (e) {
    S.busy = false;
    $("fo-out").textContent = "✕ Error: " + e.message;
  }
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
    const g = await call("GET", "/api/followup?proposal_id=" + encodeURIComponent(S.prop));
    S.fol = g.followup;
    S.approved = !!g.approved;
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
  const ICON = {proposal: "✓", review: "✔", followup: "↩", model_call: "◈", gate: "⛔"};
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
