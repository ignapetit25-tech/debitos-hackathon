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

from ia_debitos import approvals, drafts, proceso
from ia_debitos.agent import Agente
from ia_debitos.provider import ProviderError, build_provider
from ia_debitos.synthetic import SyntheticStore

PUERTO = int(os.environ.get("IA_DEMO_PORT", "8931"))
STATIC = Path(__file__).resolve().parent / "static"
HTML = (STATIC / "shell.html").read_text(encoding="utf-8")


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


def _hal_json(h) -> dict:
    return {"id": h.id, "caso_id": h.caso_id, "renglon_nro": h.renglon_nro,
            "tipo": h.tipo, "documento": h.documento, "pagina": h.pagina,
            "fragmento": h.fragmento, "interpretacion": h.interpretacion,
            "limitaciones": h.limitaciones, "verificado": h.verificado}


def _exp_json(inv: dict) -> dict:
    return {"renglones": inv["renglones"],
            "hallazgos": [_hal_json(h) for h in inv["hallazgos"]],
            "faltantes": inv["faltantes"],
            "regla": {"sector": inv["regla"].sector, "puntos": inv["regla"].puntos,
                      "frases": list(inv["regla"].frases)},
            "sector": inv["sector"], "accion": inv["accion"],
            "siguiente_paso": inv["siguiente_paso"],
            "sumas_ok": inv["sumas_ok"], "dif_cents": inv["dif_cents"]}


def _caso_json(caso, docs: list | None = None) -> dict:
    pdf = _pdf_caso(caso.id)
    return {"id": caso.id, "financiador": caso.financiador, "pdf": pdf.name if pdf else None,
            "fecha_prestacion": caso.fecha_prestacion,
            "documentos": [{"rol": d["rol"], "archivo": d["archivo"]} for d in (docs or [])],
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
            if url.path.startswith("/static/"):
                nombre = url.path[len("/static/"):]
                tipos = {"app.css": "text/css", "app.js": "text/javascript"}
                if nombre not in tipos:
                    _json(self, 404, {"error": "estático inexistente"})
                    return
                raw = (STATIC / nombre).read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", tipos[nombre] + "; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            elif url.path == "/":
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
                _json(self, 200, {"caso": _caso_json(self.store.obtener_caso(cid),
                                                    self.store.documentos(cid))})
            elif url.path == "/api/expediente":
                cid = parse_qs(url.query).get("caso_id", [""])[0]
                _json(self, 200, {"expediente": _exp_json(self.agente.expediente(cid))})
            elif url.path == "/api/propuestas":
                cid = parse_qs(url.query).get("caso_id", [""])[0]
                out = []
                for pid in self.store.propuestas_caso(cid):
                    prop = self.store.propuesta(pid)
                    out.append({"id": pid, "sector": prop["sector"],
                                "accion": prop["accion"],
                                "degradado": "DEGRADADO" in (prop["explicacion"] or "")})
                _json(self, 200, {"propuestas": out})
            elif url.path == "/api/convenios":
                fin = parse_qs(url.query).get("financiador", [""])[0]
                _json(self, 200, {"convenios": self.store.convenios_financiador(fin)})
            elif url.path == "/api/proceso":
                cid = parse_qs(url.query).get("caso_id", [""])[0]
                caso = self.store.obtener_caso(cid)
                inv = self.agente.expediente(cid)
                revs = [h for h in self.store.historial(cid) if h[1] == "revision" and h[5]]
                desde = revs[0][5][:10] if revs else None
                revisor = revs[-1][4].rsplit(" por ", 1)[-1] if revs else ""
                chk = proceso.checklist(caso, inv)
                if revisor:
                    for it in chk:
                        if it["item"] == "Responsable":
                            it["valor"] = revisor
                            it["estado"] = "ok"
                _json(self, 200, {
                    "prioridad": proceso.prioridad(caso.total_debito_cents),
                    "checklist": chk, "revisor": revisor,
                    "sla": {"desde": desde, "dias": proceso.SLA_DIAS,
                            "vence": proceso.sumar_habiles(desde) if desde else None}})
            elif url.path == "/api/seguimiento":
                pid = parse_qs(url.query).get("propuesta_id", [""])[0]
                _json(self, 200, {"seguimiento": self.store.seguimiento(pid)})
            elif url.path == "/api/hallazgos":
                pid = parse_qs(url.query).get("propuesta_id", [""])[0]
                if not self.store.propuesta(pid):
                    _json(self, 404, {"error": "propuesta inexistente"})
                    return
                _json(self, 200, {"hallazgos": self.store.hallazgos_propuesta(pid)})
            elif url.path == "/api/pdf":
                cid = parse_qs(url.query).get("caso_id", [""])[0]
                rol = parse_qs(url.query).get("rol", [""])[0]
                try:
                    self.store.obtener_caso(cid)
                except KeyError:
                    _json(self, 404, {"error": "caso inexistente"})
                    return
                pdf = None
                if rol in ("factura", "liquidacion", "convenio"):
                    for d in self.store.documentos(cid):
                        if d["rol"] == rol:
                            cand = GENERADOS / Path(d["archivo"]).name
                            pdf = cand if cand.is_file() else None
                else:
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
            elif self.path == "/api/seguimiento":
                seg = approvals.seguimiento(
                    self.store, body["propuesta_id"], body.get("decision", ""),
                    body.get("recuperable_cents"), body.get("aceptado_cents"),
                    body.get("responsable", ""), body.get("fecha", ""),
                    body.get("nota", ""))
                _json(self, 200, {"seguimiento": seg})
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
