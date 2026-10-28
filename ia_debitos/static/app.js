"use strict";
const $ = id => document.getElementById(id);
const S = {casos: [], caso: null, exp: null, props: [], prop: null, hallM: [],
  hist: [], busy: false, selH: -1, prov: null, proc: null, conv: [], seg: null};
const fmt$ = c => "$" + (c / 100).toLocaleString("es-AR", {minimumFractionDigits: 2});

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined && text !== null) e.textContent = text;
  return e;
}
function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }
function status(n, kind, msg) {
  clear(n);
  n.appendChild(el("div", "status " + kind, msg));
}
async function call(m, u, b) {
  const r = await fetch(u, {method: m, headers: {"Content-Type": "application/json"},
    body: b ? JSON.stringify(b) : undefined});
  let j = {};
  try { j = await r.json(); } catch (e) { /* cuerpo no JSON */ }
  if (!r.ok) throw new Error((j && j.error) || ("HTTP " + r.status));
  return j;
}
function parseAR(s) {
  s = String(s === undefined || s === null ? "" : s).replace(/\$/g, "").replace(/\s/g, "");
  if (!s) return 0;
  let neg = false;
  if (s[0] === "-") { neg = true; s = s.slice(1); }
  let n;
  if (s.indexOf(".") >= 0 && s.indexOf(",") >= 0)
    n = parseFloat(s.replace(/\./g, "").replace(",", "."));
  else if (s.indexOf(",") >= 0) n = parseFloat(s.replace(",", "."));
  else n = parseFloat(s);
  if (!isFinite(n) || n < 0) return null;
  return Math.round(n * 100) * (neg ? -1 : 1);
}
function badge(ok, warn, txtOk, txtWarn) {
  return el("span", "badge " + (ok ? "ok" : (warn ? "warn" : "bad")),
    (ok ? "✓ " : (warn ? "⚠ " : "✕ ")) + (ok ? txtOk : txtWarn));
}

/* ---------- bandeja ---------- */
function renderBandeja() {
  const ul = $("casos");
  clear(ul);
  if (!S.casos.length) { status($("ban-status"), "empty", "Sin casos."); return; }
  status($("ban-status"), "", "");
  S.casos.forEach((c, i) => {
    const li = el("li", null, null);
    li.setAttribute("role", "option");
    li.tabIndex = 0;
    li.setAttribute("aria-selected", S.caso && S.caso.id === c.id ? "true" : "false");
    const t1 = el("div", "t1", null);
    t1.appendChild(el("span", null, c.id));
    t1.appendChild(badge(c.estado === "propuesto", c.estado === "nuevo", c.estado, c.estado));
    li.appendChild(t1);
    li.appendChild(el("div", "t2", c.financiador + " · " + c.factura));
    li.appendChild(el("div", "imp", fmt$(c.total_debito_cents)));
    li.addEventListener("click", () => selectCaso(c.id));
    li.addEventListener("keydown", ev => {
      if (ev.key === "Enter") selectCaso(c.id);
      if (ev.key === "ArrowDown" && ul.children[i + 1]) ul.children[i + 1].focus();
      if (ev.key === "ArrowUp" && ul.children[i - 1]) ul.children[i - 1].focus();
    });
    ul.appendChild(li);
  });
}

async function selectCaso(id) {
  if (S.busy) return;
  S.caso = null; S.exp = null; S.props = []; S.prop = null; S.hallM = []; S.hist = [];
  S.selH = -1; S.nom = ""; S.nota = ""; S.borrador = null;
  S.proc = null; S.conv = []; S.seg = null;
  renderBandeja();
  status($("exp-body"), "loading", "Cargando expediente…");
  status($("evi-body"), "loading", "Cargando evidencia…");
  try {
    const [cj, ej, pj, hj, pr] = await Promise.all([
      call("GET", "/api/caso?caso_id=" + encodeURIComponent(id)),
      call("GET", "/api/expediente?caso_id=" + encodeURIComponent(id)),
      call("GET", "/api/propuestas?caso_id=" + encodeURIComponent(id)),
      call("GET", "/api/historial?caso_id=" + encodeURIComponent(id)),
      call("GET", "/api/proceso?caso_id=" + encodeURIComponent(id))]);
    S.caso = cj.caso; S.exp = ej.expediente; S.props = pj.propuestas; S.hist = hj.historial;
    S.proc = pr;
    try {
      const cv = await call("GET", "/api/convenios?financiador=" + encodeURIComponent(S.caso.financiador));
      S.conv = cv.convenios;
    } catch (e) { S.conv = []; }
    if (S.props.length) await selectProp(S.props[S.props.length - 1].id, true);
    renderBandeja(); renderExp(); renderEvi();
    if (window.innerWidth <= 1000) setView("expediente");
  } catch (e) {
    status($("exp-body"), "error", "No se pudo cargar: " + e.message);
    status($("evi-body"), "empty", "—");
  }
}

/* ---------- expediente ---------- */
function renderExp() {
  const n = $("exp-body");
  clear(n);
  if (!S.caso || !S.exp) { status(n, "empty", "Elegí un caso de la bandeja."); return; }
  const c = S.caso, e = S.exp;
  n.appendChild(el("p", "muted", c.id + " · " + c.financiador + " · factura " +
    c.factura + " · prestación " + (c.fecha_prestacion || "no informada")));
  if (S.proc) {
    const pr = el("p", null, null);
    pr.appendChild(badge(S.proc.prioridad !== "P3", S.proc.prioridad === "P3",
      "prioridad " + S.proc.prioridad, "prioridad " + S.proc.prioridad));
    pr.appendChild(el("span", null, " "));
    pr.appendChild(el("span", "muted", S.proc.sla.vence ?
      ("SLA responde antes del " + S.proc.sla.vence + " (" + S.proc.sla.dias + " días hábiles desde " + S.proc.sla.desde + ")") :
      "SLA pendiente de derivación (5 días hábiles)"));
    n.appendChild(pr);
    n.appendChild(el("h3", null, "Checklist pre-derivación"));
    const tc = el("table", null, null);
    S.proc.checklist.forEach(it => {
      const tr = el("tr", null, null);
      tr.appendChild(el("td", null, it.item));
      tr.appendChild(el("td", null, it.valor));
      const td = el("td", null, null);
      td.appendChild(badge(it.estado === "ok", it.estado === "aviso", it.estado, it.estado));
      tr.appendChild(td);
      tc.appendChild(tr);
    });
    n.appendChild(tc);
    n.appendChild(el("h3", null, "Convenios de " + c.financiador));
    if (!S.conv.length) n.appendChild(el("p", "muted", "Sin convenios cargados."));
    S.conv.forEach(cv => {
      const vig = c.fecha_prestacion && cv.desde <= c.fecha_prestacion && c.fecha_prestacion <= cv.hasta;
      const d = el("p", null, null);
      d.appendChild(badge(vig, !vig, cv.id + " " + cv.version, cv.id + " " + cv.version));
      d.appendChild(el("span", "muted", " " + cv.desde + " .. " + cv.hasta + " · " +
        Object.keys(cv.aranceles).length + " aranceles"));
      n.appendChild(d);
    });
  }
  const tb = el("table", null, null);
  const hr = el("tr", null, null);
  ["#", "práctica", "facturado", "liquidado", "diferencia", "valor convenido", "fuente"]
    .forEach((h, i) => hr.appendChild(el("th", i >= 2 && i <= 5 ? "num" : null, h)));
  tb.appendChild(hr);
  e.renglones.forEach(r => {
    const tr = el("tr", null, null);
    tr.appendChild(el("td", null, "R" + r.nro + " " + r.practica));
    tr.appendChild(el("td", null, r.motivo));
    [r.facturado_cents, r.liquidado_cents, r.debito_cents].forEach(v =>
      tr.appendChild(el("td", "num", fmt$(v))));
    tr.appendChild(el("td", "num", r.ref_cents === null || r.ref_cents === undefined ? "—" : fmt$(r.ref_cents)));
    tr.appendChild(el("td", null, r.fuente_ref));
    tb.appendChild(tr);
  });
  n.appendChild(tb);
  n.appendChild(badge(e.sumas_ok, false, "sumas OK", "SUMAS INCONSISTENTES"));
  const h3 = el("h3", null, "Hallazgos deterministas");
  n.appendChild(h3);
  if (!e.hallazgos.length) n.appendChild(el("p", "muted", "Sin hallazgos."));
  e.hallazgos.forEach(h => {
    const d = el("div", "card", null);
    d.appendChild(badge(h.tipo === "diferencia_respaldada", h.tipo !== "clinico_humano",
      h.tipo, h.tipo));
    d.appendChild(el("p", null, (h.renglon_nro ? "R" + h.renglon_nro + " · " : "") + h.interpretacion));
    if (h.limitaciones) d.appendChild(el("p", "muted", "Límite: " + h.limitaciones));
    d.appendChild(el("p", "muted", (h.verificado ? "✓ cita verificada" : "✕ cita no verificada") +
      " · " + h.documento + " p." + h.pagina));
    n.appendChild(d);
  });
  if (e.faltantes.length) {
    n.appendChild(el("h3", null, "Información faltante"));
    const ul = el("ul", null, null);
    e.faltantes.forEach(f => ul.appendChild(el("li", null, f)));
    n.appendChild(ul);
  }
  const nx = el("div", "card next", null);
  nx.appendChild(el("strong", null, "Siguiente paso propuesto: "));
  nx.appendChild(el("span", null, e.siguiente_paso + " (" + e.sector + " / " + e.accion + ")"));
  n.appendChild(nx);
  renderPropCard(n);
}

function renderPropCard(n) {
  const d = el("div", "card decision", null);
  d.appendChild(el("h3", null, "Propuesta y revisión humana"));
  const row = el("div", "row", null);
  const sel = el("select", null, null);
  sel.id = "v-sel";
  sel.setAttribute("aria-label", "Versión de propuesta");
  if (!S.props.length) sel.appendChild(el("option", null, "sin propuestas (pedí una)"));
  S.props.forEach(p => {
    const o = el("option", null, p.id + " · " + p.sector + " / " + p.accion +
      (p.degradado ? " · DEGRADADO" : ""));
    o.value = p.id;
    sel.appendChild(o);
  });
  if (S.prop) sel.value = S.prop;
  sel.addEventListener("change", () => selectProp(sel.value, false));
  row.appendChild(sel);
  const bp = el("button", null, "Pedir propuesta");
  bp.id = "b-prop";
  bp.disabled = S.busy;
  bp.addEventListener("click", pedir);
  row.appendChild(bp);
  d.appendChild(row);
  d.appendChild(el("p", "muted", "Aprobar = aceptar la propuesta de derivación. No acepta el débito ni autoriza comunicaciones: la demo no envía mensajes ni modifica sistemas externos."));
  const rn = el("input", null, null);
  rn.id = "r-nom"; rn.placeholder = "Tu nombre (revisor)";
  rn.value = S.nom || "";
  rn.addEventListener("input", () => { S.nom = rn.value; });
  rn.setAttribute("aria-label", "Revisor");
  d.appendChild(rn);
  const rt = document.createElement("textarea");
  rt.id = "r-nota"; rt.rows = 2;
  rt.placeholder = "Fundamento (queda registrado)";
  rt.value = S.nota || "";
  rt.addEventListener("input", () => { S.nota = rt.value; });
  rt.setAttribute("aria-label", "Fundamento");
  d.appendChild(rt);
  const r2 = el("div", "row", null);
  const ba = el("button", "ok", "Aprobar");
  const br = el("button", "no", "Rechazar");
  ba.disabled = br.disabled = S.busy || !S.prop;
  ba.addEventListener("click", () => decidir("aprobada"));
  br.addEventListener("click", () => decidir("rechazada"));
  r2.appendChild(ba); r2.appendChild(br);
  d.appendChild(r2);
  d.appendChild(el("p", "muted", S.prop ? ("Revisás exactamente: " + S.prop) : "Sin propuesta seleccionada."));
  const out = el("div", null, null);
  out.id = "rev-out";
  out.setAttribute("aria-live", "polite");
  d.appendChild(out);
  const bb = el("button", "sec", "Ver borrador");
  bb.addEventListener("click", verBorrador);
  d.appendChild(bb);
  const bp2 = el("pre", "doc", S.borrador || "—");
  bp2.id = "borr";
  d.appendChild(bp2);
  n.appendChild(d);
  const sg = el("div", "card", null);
  sg.appendChild(el("h3", null, "Devolución del sector (seguimiento)"));
  if (S.seg) {
    sg.appendChild(el("p", null, S.seg.decision + " · recuperable " + fmt$(S.seg.recuperable_cents) +
      " · aceptado " + fmt$(S.seg.aceptado_cents)));
    sg.appendChild(el("p", "muted", "Responsable: " + S.seg.responsable + " · " + S.seg.fecha +
      (S.seg.nota ? " · " + S.seg.nota : "")));
  } else {
    sg.appendChild(el("p", "muted", S.prop ? "Sin respuesta registrada." : "Elegí una propuesta."));
  }
  if (S.prop) {
    const sel = el("select", null, null);
    sel.id = "sg-dec";
    sel.setAttribute("aria-label", "Decisión del sector");
    ["pendiente", "recuperado", "parcial", "aceptado"].forEach(v =>
      sel.appendChild(el("option", null, v)));
    if (S.seg) sel.value = S.seg.decision;
    sg.appendChild(sel);
    const r1 = el("div", "row", null);
    const ri = el("input", null, null);
    ri.id = "sg-rec"; ri.placeholder = "Recuperable $ (ej. 12.500,50)";
    ri.setAttribute("aria-label", "Monto recuperable");
    ri.value = S.seg ? (S.seg.recuperable_cents / 100).toString() : "";
    const ai = el("input", null, null);
    ai.id = "sg-ace"; ai.placeholder = "Aceptado $ (ej. 0)";
    ai.setAttribute("aria-label", "Monto aceptado");
    ai.value = S.seg ? (S.seg.aceptado_cents / 100).toString() : "";
    r1.appendChild(ri); r1.appendChild(ai);
    sg.appendChild(r1);
    const r2 = el("div", "row", null);
    const rs = el("input", null, null);
    rs.id = "sg-resp"; rs.placeholder = "Responsable del sector";
    rs.setAttribute("aria-label", "Responsable");
    rs.value = S.seg ? S.seg.responsable : "";
    const fe = el("input", null, null);
    fe.id = "sg-fecha"; fe.type = "date";
    fe.setAttribute("aria-label", "Fecha de respuesta");
    fe.value = S.seg ? S.seg.fecha : "";
    r2.appendChild(rs); r2.appendChild(fe);
    sg.appendChild(r2);
    const nt = document.createElement("textarea");
    nt.id = "sg-nota"; nt.rows = 2;
    nt.placeholder = "Nota (opcional)";
    nt.setAttribute("aria-label", "Nota de seguimiento");
    nt.value = S.seg ? (S.seg.nota || "") : "";
    sg.appendChild(nt);
    const bs = el("button", "sec", "Guardar devolución");
    bs.disabled = S.busy;
    bs.addEventListener("click", guardarSeg);
    sg.appendChild(bs);
    const so = el("div", null, null);
    so.id = "seg-out";
    so.setAttribute("aria-live", "polite");
    sg.appendChild(so);
  }
  n.appendChild(sg);
}

async function selectProp(pid, silent) {
  S.prop = pid || null;
  S.hallM = [];
  S.borrador = null;
  S.seg = null;
  if (!pid) { if (!silent) { renderExp(); renderEvi(); } return; }
  try {
    const j = await call("GET", "/api/hallazgos?propuesta_id=" + encodeURIComponent(pid));
    S.hallM = j.hallazgos;
    const g = await call("GET", "/api/seguimiento?propuesta_id=" + encodeURIComponent(pid));
    S.seg = g.seguimiento;
  } catch (e) { S.hallM = []; S.seg = null; }
  if (!silent) { renderExp(); renderEvi(); }
}

async function guardarSeg() {
  if (S.busy || !S.prop) return;
  const rec = parseAR($("sg-rec").value);
  const ace = parseAR($("sg-ace").value);
  const resp = $("sg-resp").value.trim();
  if (rec === null || ace === null) { $("seg-out").textContent = "✕ Importes inválidos (ej. 12.500,50)."; return; }
  if (!resp) { $("seg-out").textContent = "Escribí el responsable del sector."; return; }
  S.busy = true;
  try {
    const j = await call("POST", "/api/seguimiento", {propuesta_id: S.prop,
      decision: $("sg-dec").value, recuperable_cents: rec, aceptado_cents: ace,
      responsable: resp, fecha: $("sg-fecha").value, nota: $("sg-nota").value.trim()});
    S.seg = j.seguimiento;
    const hj = await call("GET", "/api/historial?caso_id=" + encodeURIComponent(S.caso.id));
    S.hist = hj.historial;
    S.busy = false;
    renderExp(); renderEvi();
    $("seg-out").textContent = "✓ Devolución registrada.";
  } catch (e) {
    S.busy = false;
    $("seg-out").textContent = "✕ Error: " + e.message;
  }
}

async function pedir() {
  if (S.busy || !S.caso) return;
  S.busy = true;
  renderExp();
  try {
    const j = await call("POST", "/api/proponer", {caso_id: S.caso.id});
    const pj = await call("GET", "/api/propuestas?caso_id=" + encodeURIComponent(S.caso.id));
    S.props = pj.propuestas;
    const hj = await call("GET", "/api/historial?caso_id=" + encodeURIComponent(S.caso.id));
    S.hist = hj.historial;
    S.busy = false;
    await selectProp(j.propuesta.id, true);
    renderExp(); renderEvi();
  } catch (e) {
    S.busy = false;
    renderExp();
    $("rev-out").textContent = "✕ Error al pedir propuesta: " + e.message;
  }
}

async function verBorrador() {
  if (!S.prop) return;
  try {
    const j = await call("GET", "/api/borrador?propuesta_id=" + encodeURIComponent(S.prop));
    S.borrador = j.titulo + "\n\n" + j.cuerpo;
  } catch (e) { S.borrador = "✕ " + e.message; }
  renderExp();
}

async function decidir(v) {
  if (S.busy || !S.prop) return;
  const nom = ($("r-nom").value || "").trim();
  const nota = ($("r-nota").value || "").trim();
  if (!nom) { $("rev-out").textContent = "Escribí tu nombre como revisor."; return; }
  S.nom = $("r-nom").value; S.nota = $("r-nota").value;
  S.busy = true;
  renderExp();
  try {
    const j = await call("POST", "/api/revisar", {propuesta_id: S.prop, revisor: nom,
      veredicto: v, nota: nota});
    const hj = await call("GET", "/api/historial?caso_id=" + encodeURIComponent(S.caso.id));
    S.hist = hj.historial;
    S.busy = false;
    renderExp(); renderEvi();
    $("rev-out").textContent = "✓ " + j.decision.veredicto.toUpperCase() + " por " +
      j.decision.revisor + " — " + S.prop + " registrado en historial.";
  } catch (e) {
    S.busy = false;
    renderExp();
    $("rev-out").textContent = "✕ Error al registrar: " + e.message;
  }
}

/* ---------- evidencia ---------- */
function renderEvi() {
  const n = $("evi-body");
  clear(n);
  if (!S.caso) { status(n, "empty", "Elegí un caso."); return; }
  n.appendChild(el("h3", null, "Documentos"));
  const docs = S.caso.documentos || [];
  if (!docs.length && !S.caso.pdf) n.appendChild(el("p", "muted", "Sin documentos vinculados."));
  docs.forEach(d => {
    const b = el("button", "sec", d.rol + " (PDF)");
    b.addEventListener("click", () => window.open("/api/pdf?caso_id=" +
      encodeURIComponent(S.caso.id) + "&rol=" + encodeURIComponent(d.rol), "_blank"));
    n.appendChild(b);
    n.appendChild(el("span", null, " "));
  });
  if (S.caso.pdf && !docs.length) {
    const b = el("button", "sec", "documento (PDF)");
    b.addEventListener("click", () => window.open("/api/pdf?caso_id=" +
      encodeURIComponent(S.caso.id), "_blank"));
    n.appendChild(b);
  }
  n.appendChild(el("h3", null, "Hallazgos del modelo" + (S.prop ? " · " + S.prop : "")));
  if (!S.prop) n.appendChild(el("p", "muted", "Sin propuesta seleccionada."));
  else if (!S.hallM.length) n.appendChild(el("p", "muted", "Sin hallazgos del modelo."));
  S.hallM.forEach((h, i) => {
    const b = el("button", "hall", null);
    b.setAttribute("aria-current", S.selH === i ? "true" : "false");
    b.appendChild(badge(h.verificado, false, "cita OK", "CITA NO VERIFICADA"));
    b.appendChild(el("span", null, " [" + h.tipo + "] " +
      (h.renglon_nro ? "R" + h.renglon_nro + " · " : "") + h.interpretacion.slice(0, 90)));
    b.addEventListener("click", () => { S.selH = i; renderEvi(); });
    n.appendChild(b);
  });
  if (S.selH >= 0 && S.hallM[S.selH]) {
    const h = S.hallM[S.selH];
    const d = el("div", "card", null);
    d.appendChild(el("blockquote", null, h.fragmento));
    d.appendChild(el("p", "muted", h.documento + " · página " + h.pagina +
      (h.verificado ? " · ✓ referencia existe y cita coincide" :
        " · ✕ referencia inexistente o cita no coincide")));
    d.appendChild(el("p", null, h.interpretacion));
    if (h.limitaciones) d.appendChild(el("p", "muted", "Limitaciones: " + h.limitaciones));
    d.appendChild(el("p", "muted", "Verificado valida la cita, no la interpretación."));
    n.appendChild(d);
  }
  const det = el("details", "meta", null);
  det.appendChild(el("summary", null, "Detalles técnicos de Meta"));
  const last = S.hist.filter(h => h[1] === "llamada_modelo").pop();
  det.appendChild(el("p", null, "Proveedor configurado: " + (S.prov || "?")));
  det.appendChild(el("p", null, last ? ("Última llamada: " + last[2] + " → " + last[4]) :
    "Sin llamadas al modelo en este caso."));
  det.appendChild(el("p", "muted", "Ejecución exitosa y modo degradado se informan por propuesta, no globalmente."));
  n.appendChild(det);
  n.appendChild(el("h3", null, "Historial"));
  if (!S.hist.length) { n.appendChild(el("p", "muted", "Sin eventos.")); return; }
  const tb = el("table", null, null);
  const hr = el("tr", null, null);
  ["#", "fecha/hora", "tipo", "detalle", "antes", "después"].forEach(h =>
    hr.appendChild(el("th", null, h)));
  tb.appendChild(hr);
  S.hist.forEach(h => {
    const tr = el("tr", null, null);
    [h[0], h[5] || "—", h[1], h[2], h[3] || "", h[4] || ""].forEach(v =>
      tr.appendChild(el("td", null, String(v))));
    tb.appendChild(tr);
  });
  n.appendChild(tb);
}

/* ---------- init ---------- */
function setView(v) {
  document.body.setAttribute("data-view", v);
  ["bandeja", "expediente", "evidencia"].forEach(k =>
    $("tab-" + k).disabled = (k === v));
}
async function init() {
  document.body.setAttribute("data-view", "bandeja");
  ["bandeja", "expediente", "evidencia"].forEach(k =>
    $("tab-" + k).addEventListener("click", () => setView(k)));
  try {
    const p = await call("GET", "/api/proveedor");
    S.prov = p.proveedor;
    const e = $("prov");
    e.textContent = "Proveedor configurado: " + p.proveedor +
      (p.simulado ? " — SIMULADO (no demuestra Meta)" : " — Meta real");
    e.className = "banner " + (p.simulado ? "sim" : "meta");
    const c = await call("GET", "/api/casos");
    S.casos = c.casos;
    renderBandeja();
    status($("exp-body"), "empty", "Elegí un caso de la bandeja.");
    status($("evi-body"), "empty", "Elegí un caso de la bandeja.");
  } catch (e) {
    $("prov").textContent = "✕ Error de conexión: " + e.message;
    status($("ban-status"), "error", "No se pudo cargar.");
  }
}
init();
