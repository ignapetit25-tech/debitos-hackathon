"""Demo autónoma mínima (stdlib http.server). Datos 100% ficticios.

Puertos/rutas: 127.0.0.1:8931. Proveedor según IA_PROVIDER (meta por
defecto, simulated explícito). Sin clave Meta, la explicación del modelo
se degrada con mensaje claro; reglas/cálculos siguen deterministas.
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
<title>IA Débitos — Demo ficticia</title>
<style>body{font-family:sans-serif;max-width:900px;margin:2em auto;padding:0 1em}
pre{background:#f4f4f4;padding:1em;white-space:pre-wrap}
.banner{background:#fff3cd;border:1px solid #c90;padding:.5em 1em}</style></head>
<body>
<h1>Capa IA de débitos — DEMO (datos ficticios)</h1>
<p class="banner" id="prov">proveedor: …</p>
<h2>1. Casos</h2><button onclick="api('GET','/api/casos')">listar</button>
<h2>2. Proponer <input id="caso" value="DEMO-F123" size="14">
<button onclick="api('POST','/api/proponer',{caso_id:val('caso')})">proponer</button></h2>
<h2>3. Revisar (humano) <input id="prop" size="14" placeholder="P-…">
<input id="rev" value="Operador Demo" size="14">
<button onclick="api('POST','/api/revisar',{propuesta_id:val('prop'),revisor:val('rev'),veredicto:'aprobada'})">aprobar</button>
<button onclick="api('POST','/api/revisar',{propuesta_id:val('prop'),revisor:val('rev'),veredicto:'rechazada'})">rechazar</button></h2>
<h2>4. Historial <button onclick="api('GET','/api/historial?caso_id='+val('caso'))">ver</button></h2>
<h2>5. Borrador <button onclick="api('GET','/api/borrador?propuesta_id='+val('prop'))">ver</button></h2>
<pre id="out">…</pre>
<script>
const val=id=>document.getElementById(id).value;
async function api(m,u,b){
 const r=await fetch(u,{method:m,headers:{'Content-Type':'application/json'},body:b?JSON.stringify(b):undefined});
 document.getElementById('out').textContent=JSON.stringify(await r.json(),null,2);
}
fetch('/api/proveedor').then(r=>r.json()).then(j=>{document.getElementById('prov').textContent='proveedor: '+j.proveedor+(j.simulado?' — SIMULADO, no demuestra Meta':''));});
</script></body></html>"""


def _prop_json(prop) -> dict:
    return {"id": prop.id, "caso_id": prop.caso_id, "sector": prop.sector,
            "regla": {"sector": prop.regla.sector, "puntos": prop.regla.puntos,
                      "frases": list(prop.regla.frases)},
            "accion": prop.accion, "explicacion": prop.explicacion,
            "referencias": list(prop.referencias),
            "abstencion_clinica": prop.abstencion_clinica,
            "extraccion_confianza": prop.extraccion_confianza}


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
