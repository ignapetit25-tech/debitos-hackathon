"""Demo autónoma (stdlib http.server). Datos 100% ficticios.

127.0.0.1:8931. Proveedor según IA_PROVIDER (meta por defecto,
simulated explícito). Interfaz completa: casos, propuesta, borrador,
revisión humana e historial con fecha/hora.
"""
from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ia_debitos import approvals, drafts
from ia_debitos.agent import Agente
from ia_debitos.provider import ProviderError, build_provider
from ia_debitos.synthetic import SyntheticStore

PUERTO = int(os.environ.get("IA_DEMO_PORT", "8931"))
HTML = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Demo IA Débitos — datos ficticios</title>
<style>
:root{--bg:#f7f7f8;--card:#fff;--line:#e2e2e6;--acc:#1a56db;--warn:#9a3412;--ok:#166534}
*{box-sizing:border-box}body{font-family:system-ui,sans-serif;background:var(--bg);margin:0;color:#222}
header{background:#111827;color:#fff;padding:1em 1.5em}
header h1{margin:0;font-size:1.2em}header p{margin:.2em 0 0;font-size:.85em;color:#cbd5e1}
main{max-width:1000px;margin:1.5em auto;padding:0 1em 3em;display:grid;gap:1em}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:1em 1.2em}
.card h2{margin:.1em 0 .6em;font-size:1em;text-transform:uppercase;letter-spacing:.04em;color:#555}
.banner{border-radius:10px;padding:.7em 1em;font-size:.9em}
.banner.fict{background:#fef9c3;border:1px solid #eab308}
.banner.meta{background:#dcfce7;border:1px solid #22c55e}
.banner.sim{background:#ffedd5;border:1px solid #fb923c}
button{background:var(--acc);color:#fff;border:0;border-radius:6px;padding:.5em 1em;cursor:pointer;font-size:.9em}
button.sec{background:#4b5563}button.ok{background:var(--ok)}button.no{background:#b91c1c}
button:disabled{opacity:.5;cursor:default}
input,select,textarea{font-size:.9em;padding:.4em;border:1px solid var(--line);border-radius:6px;width:100%}
.row{display:flex;gap:.6em;flex-wrap:wrap;align-items:center}.row>*{flex:1;min-width:140px}
pre{background:#111827;color:#e5e7eb;padding:1em;border-radius:8px;white-space:pre-wrap;font-size:.85em;max-height:320px;overflow:auto}
table{border-collapse:collapse;width:100%;font-size:.82em}
th,td{border:1px solid var(--line);padding:.35em .5em;text-align:left;vertical-align:top}
th{background:#f3f4f6}.clin{color:var(--warn);font-weight:bold}.muted{color:#777;font-size:.85em}
</style></head>
<body>
<header><h1>Demo IA de débitos</h1><p>Propuesta → revisión humana → historial auditable</p></header>
<main>
<div class="banner fict">DATOS 100% FICTICIOS — Demostración. Nada aquí es un débito real.</div>
<div class="banner meta" id="prov">proveedor: …</div>
<div class="card"><h2>1 · Caso</h2>
<div class="row"><select id="sel"></select><button class="sec" id="b-caso">ver detalle</button>
<button class="sec" id="b-pdf">ver documento</button>
<button id="b-prop">2 · pedir propuesta</button></div>
<pre id="caso">Elegí un caso y pedí la propuesta.</pre></div>
<div class="card"><h2>2 · Propuesta</h2><pre id="prop">—</pre>
<div class="row"><button class="sec" id="b-borr">ver borrador</button><button class="sec" id="b-hist">ver historial</button></div></div>
<div class="card"><h2>3 · Borrador</h2><pre id="borr">—</pre></div>
<div class="card"><h2>4 · Revisión humana (tu decisión)</h2>
<div class="row"><input id="r-prop" placeholder="ID propuesta (P-…)" disabled>
<input id="r-nom" placeholder="Tu nombre (revisor)"></div>
<p><textarea id="r-nota" rows="2" placeholder="Fundamento de tu decisión (queda registrado)"></textarea></p>
<p class="muted">Aprobar aquí = aceptar la propuesta de derivación. No acepta el débito ni autoriza comunicaciones: la demo no envía mensajes ni modifica sistemas externos.</p>
<div class="row"><button class="ok" id="b-ap">aprobar</button><button class="no" id="b-re">rechazar</button></div>
<pre id="rev-out">Pendiente de tu decisión.</pre></div>
<div class="card"><h2>5 · Historial</h2><div id="hist" class="muted">—</div></div>
</main>
<script>
const $=id=>document.getElementById(id);
let propId="";
async function call(m,u,b){
 const r=await fetch(u,{method:m,headers:{"Content-Type":"application/json"},body:b?JSON.stringify(b):undefined});
 const j=await r.json();if(!r.ok)throw new Error(j.error||r.status);return j;
}
async function init(){
 const p=await call("GET","/api/proveedor");
 const e=$("prov");e.textContent="proveedor: "+p.proveedor+(p.simulado?" — SIMULADO (no demuestra Meta)":" — Meta real");
 e.className="banner "+(p.simulado?"sim":"meta");
 const c=await call("GET","/api/casos");
 $("sel").innerHTML=c.casos.map(k=>`<option value="${k.id}">${k.id} · ${k.financiador} · ${k.factura} · ${k.estado}</option>`).join("");
}
$("b-caso").onclick=async()=>{
 const j=await call("GET","/api/caso?caso_id="+encodeURIComponent($("sel").value));
 const c=j.caso;
 $("caso").textContent=`${c.id} · ${c.financiador} · factura ${c.factura} · estado ${c.estado}\n`+
  c.renglones.map(r=>`R${r.nro} ${r.practica}: ${r.motivo}\n   fact $${(r.facturado_cents/100).toFixed(2)} liq $${(r.liquidado_cents/100).toFixed(2)} débito $${(r.debito_cents/100).toFixed(2)}`).join("\\n")+
  `\nTotal débito: $${(c.total_debito_cents/100).toFixed(2)}`;
};
$("b-pdf").onclick=async()=>{
 const j=await call("GET","/api/caso?caso_id="+encodeURIComponent($("sel").value));
 if(!j.caso.pdf){$("caso").textContent="Este caso no tiene PDF de origen en la demo.";return;}
 window.open("/api/pdf?caso_id="+encodeURIComponent($("sel").value),"_blank");
};
$("b-prop").onclick=async()=>{
 $("prop").textContent="Consultando…";
 const j=await call("POST","/api/proponer",{caso_id:$("sel").value});
 const p=j.propuesta;propId=p.id;$("r-prop").value=p.id;
 $("prop").textContent=`${p.id} · ${p.sector} / ${p.accion} · sumas ${j.sumas_ok?"OK":"DIFIEREN"}\nRegla: ${p.regla.puntos} pts (${p.regla.frases.join(", ")})\n${p.abstencion_clinica?"DERIVA A HUMANO (clínico o sin criterio) — sin recomendar aceptar/reclamar\\n":""}${p.explicacion}\nRefs: ${p.referencias.join(" · ")}`;
};
$("b-borr").onclick=async()=>{
 if(!propId){$("borr").textContent="Primero pedí una propuesta.";return;}
 const j=await call("GET","/api/borrador?propuesta_id="+encodeURIComponent(propId));
 $("borr").textContent=j.titulo+"\\n\\n"+j.cuerpo;
};
$("b-hist").onclick=async()=>{
 const j=await call("GET","/api/historial?caso_id="+encodeURIComponent($("sel").value));
 const rows=j.historial.map(h=>`<tr><td>${h[0]}</td><td>${h[5]||"—"}</td><td>${h[1]}</td><td>${h[2]}</td><td>${h[3]||""}</td><td>${h[4]||""}</td></tr>`).join("");
 $("hist").innerHTML=`<table><tr><th>#</th><th>fecha/hora</th><th>tipo</th><th>detalle</th><th>antes</th><th>después</th></tr>${rows}</table>`;
};
async function decidir(v){
 if(!propId){$("rev-out").textContent="Primero pedí una propuesta.";return;}
 const nom=$("r-nom").value.trim();
 if(!nom){$("rev-out").textContent="Escribí tu nombre como revisor.";return;}
 const j=await call("POST","/api/revisar",{propuesta_id:propId,revisor:nom,veredicto:v,nota:$("r-nota").value.trim()});
 $("rev-out").textContent=`${j.decision.veredicto.toUpperCase()} por ${j.decision.revisor} — registrado en historial.`;
 $("b-hist").click();
}
$("b-ap").onclick=()=>decidir("aprobada");$("b-re").onclick=()=>decidir("rechazada");
init().catch(e=>{$("prov").textContent="error: "+e.message;});
</script></body></html>"""


def _prop_json(prop) -> dict:
    return {"id": prop.id, "caso_id": prop.caso_id, "sector": prop.sector,
            "regla": {"sector": prop.regla.sector, "puntos": prop.regla.puntos,
                      "frases": list(prop.regla.frases)},
            "accion": prop.accion, "explicacion": prop.explicacion,
            "referencias": list(prop.referencias),
            "abstencion_clinica": prop.abstencion_clinica,
            "extraccion_confianza": prop.extraccion_confianza}


GENERADOS = Path(__file__).resolve().parent.parent / "demo_data" / "generated"


def _pdf_caso(cid: str) -> Path | None:
    if not cid or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-" for c in cid):
        return None
    pdf = GENERADOS / f"{cid}.pdf"
    return pdf if pdf.is_file() else None


def _caso_json(caso) -> dict:
    pdf = _pdf_caso(caso.id)
    return {"id": caso.id, "financiador": caso.financiador, "pdf": pdf.name if pdf else None,
            "factura": caso.factura, "estado": caso.estado,
            "total_debito_cents": caso.total_debito_cents,
            "renglones": [{"nro": r.nro, "practica": r.practica,
                           "motivo": r.motivo,
                           "facturado_cents": r.facturado_cents,
                           "liquidado_cents": r.liquidado_cents,
                           "debito_cents": r.debito_cents}
                          for r in caso.renglones]}


def _json(handler: BaseHTTPRequestHandler, code: int, payload: dict) -> None:
    raw = json.dumps(payload, ensure_ascii=False).encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


class Manejador(BaseHTTPRequestHandler):
    store: SyntheticStore
    agente: Agente

    def log_message(self, *args):
        pass

    def do_GET(self):
        try:
            url = urlparse(self.path)
            if url.path == "/":
                raw = HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            elif url.path == "/api/proveedor":
                _json(self, 200, {"proveedor": self.agente.provider.name,
                                  "simulado": self.agente.provider.name == "simulated"})
            elif url.path == "/api/casos":
                _json(self, 200, {"casos": self.agente.consultar_estados()})
            elif url.path == "/api/caso":
                cid = parse_qs(url.query).get("caso_id", [""])[0]
                _json(self, 200, {"caso": _caso_json(self.store.obtener_caso(cid))})
            elif url.path == "/api/pdf":
                cid = parse_qs(url.query).get("caso_id", [""])[0]
                try:
                    self.store.obtener_caso(cid)
                except KeyError:
                    _json(self, 404, {"error": "caso inexistente"})
                    return
                pdf = _pdf_caso(cid)
                if pdf is None:
                    _json(self, 404, {"error": "caso sin PDF de origen"})
                    return
                raw = pdf.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            elif url.path == "/api/historial":
                cid = parse_qs(url.query).get("caso_id", [""])[0]
                _json(self, 200, {"historial": self.agente.historial(cid)})
            elif url.path == "/api/borrador":
                pid = parse_qs(url.query).get("propuesta_id", [""])[0]
                prop = self.store.propuesta(pid)
                if not prop:
                    _json(self, 404, {"error": "propuesta inexistente"})
                    return
                caso = self.store.obtener_caso(prop["caso_id"])
                _json(self, 200, drafts.borrador_reclamo(caso, prop["sector"],
                                                         prop["explicacion"][:300]))
            else:
                _json(self, 404, {"error": "ruta inexistente"})
        except Exception as exc:
            _json(self, 500, {"error": f"{type(exc).__name__}"})

    def do_POST(self):
        try:
            largo = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(largo) or b"{}")
            if self.path == "/api/proponer":
                caso = self.store.obtener_caso(body["caso_id"])
                ok, dif = self.agente.validar_caso(caso)
                prop = self.agente.proponer(body["caso_id"])
                _json(self, 200, {"sumas_ok": ok, "dif_cents": dif,
                                  "propuesta": _prop_json(prop)})
            elif self.path == "/api/revisar":
                dec = approvals.revisar(
                    self.store, body["propuesta_id"], body.get("revisor", ""),
                    body.get("veredicto", ""), body.get("nota", ""))
                _json(self, 200, {"decision": {"propuesta_id": dec.propuesta_id, "revisor": dec.revisor, "veredicto": dec.veredicto, "nota": dec.nota}})
            else:
                _json(self, 404, {"error": "ruta inexistente"})
        except (KeyError, ValueError) as exc:
            _json(self, 400, {"error": str(exc)[:200]})
        except Exception as exc:
            _json(self, 500, {"error": f"{type(exc).__name__}"})


def main() -> None:
    try:
        provider = build_provider()
    except ProviderError as exc:
        print(f"Proveedor: ERROR ({exc}). Use IA_PROVIDER=simulated sin clave.")
        raise SystemExit(1)
    store = SyntheticStore()
    Manejador.store = store
    Manejador.agente = Agente(store, provider)
    srv = ThreadingHTTPServer(("127.0.0.1", PUERTO), Manejador)
    print(f"Demo IA en http://127.0.0.1:{PUERTO}/ (proveedor={provider.name})")
    srv.serve_forever()


if __name__ == "__main__":
    main()
