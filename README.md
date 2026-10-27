# Capa IA de débitos (hackatón)

Capa de IA independiente sobre un sistema preexistente de gestión de
débitos de financiadores de salud. Demo autónoma con datos 100%
ficticios.

Idea declarada elegible por Adam Blumenfeld (Cerebral Valley) en el hilo del proyecto, 27/10/2026: https://discord.com/channels/1557169028080869426/1564401698259337216/1564670797908410389 — Alcance: gestión administrativa de débitos, sin juicio clínico, datos ficticios, aprobación humana. Valoró el conocimiento directo del problema y la posibilidad real de implementación. No resolvió por separado código preexistente ni modelos aceptados (se siguen las FAQs oficiales). No es certificación de seguridad/cumplimiento ni aprobación de ampliaciones futuras.

## Origen

El proyecto nace de la experiencia de su creador como responsable del sector Débitos de un policlínico argentino, donde gestiona diariamente deducciones de obras sociales, prepagas y ART. Busca reducir el trabajo manual de lectura, conciliación, derivación y seguimiento, manteniendo las decisiones finales en personas.

## Qué hace

PDF ficticio → extracción (texto u OCR español) → validación de sumas
→ consulta de reglas y aranceles → propuesta de derivación con
explicación → revisión humana obligatoria → historial antes/después.

Límites duros (en contratos, no en carteles): la IA no evalúa medicina,
no recibe historias clínicas, no envía correos, no acepta/rechaza
débitos. "Auditoría Médica" es un sector humano de destino.

## Qué hace cada etapa (implementación real)

- Extracción (`extract.py`): texto vía pypdf u OCR español vía
  tesseract; confianza por documento. Determinista, sin modelo.
- Cálculos (`money.py`, `validar`): sumas en centavos enteros.
  Determinista, sin modelo.
- Reglas (`rules.py` + aranceles): puntaje y sector por frases.
  Determinista, sin modelo.
- Aporte de Meta (`provider.py` + `agent.py`): redacta la explicación
  de la propuesta SOLO con datos dados (no inventa importes, puntajes
  ni sectores). Es lo único que hace el modelo.
- Borradores (`drafts.py`): plantillas deterministas con datos del
  caso. Propuestas, no envíos.

## Tres decisiones distintas

Aprobar una propuesta (aceptar la derivación sugerida) NO es aceptar
un débito (darle conformidad económica) NI autorizar una comunicación
(enviar algo a alguien). La demo solo registra la primera: no envía
mensajes ni modifica sistemas externos.

## Instalación

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
# Sistema: tesseract-ocr + datos spa + poppler-utils (pdftotext/pdftoppm)
# Si spa no está en el sistema:
#   curl -o ~/.local/share/tessdata/spa.traineddata <tessdata spa>
#   export TESSDATA_PREFIX=~/.local/share/tessdata
cp .env.example .env   # completar MODEL_API_KEY para Meta real
```

## Ejecución

```bash
.venv/bin/python -B tools/reset_demo.py          # regenera base + PDFs
IA_PROVIDER=simulated .venv/bin/python -B -m ia_debitos.demo_app
# abrir http://127.0.0.1:8931/
```

Con clave Meta: `MODEL_API_KEY=... .venv/bin/python -B -m ia_debitos.demo_app`.
Todo se reproduce sin acceso al sistema original: este repo no lo importa, no lo llama y no conoce sus rutas (ver PRIOR_WORK.md).
Sin clave y sin `IA_PROVIDER=simulated`, la demo se niega a arrancar
(error explícito, jamás fallback silencioso).

## Pruebas y evaluación

```bash
.venv/bin/python -B -m unittest discover -s tests
TESSDATA_PREFIX=~/.local/share/tessdata .venv/bin/python -B evals/eval_sintetica.py
```

## Limitaciones honestas

- Integración Meta: sonda mínima y test de aceptación OK con
  `muse-spark-1.3` (Responses), datos ficticios, clave en `.env` local
  fuera de Git. Recorrido demo operado por un agente OK; falta la
  revisión personal del usuario (casos pendientes en la demo).
  Ejecuciones `simulated` siguen sin demostrar funcionamiento con Meta.
- Adaptador real (JSON): implementado, desactivado por defecto, NO verificado.
- Ejecuciones `simulated` no demuestran funcionamiento con Meta.
- OCR probado solo sobre fixtures generados con ruido controlado.

## Estado de licencia y publicación

- Licencia MIT: BORRADOR pendiente de aprobación (ver LICENSE-DRAFT-MIT.md).
- Sin remoto configurado, sin publicar, sin cambios de visibilidad.
- Elegibilidad: Idea declarada elegible por Adam Blumenfeld (Cerebral Valley) en el hilo del proyecto, 27/10/2026: https://discord.com/channels/1557169028080869426/1564401698259337216/1564670797908410389 — Alcance: gestión administrativa de débitos, sin juicio clínico, datos ficticios, aprobación humana. Valoró el conocimiento directo del problema y la posibilidad real de implementación. No resolvió por separado código preexistente ni modelos aceptados (se siguen las FAQs oficiales). No es certificación de seguridad/cumplimiento ni aprobación de ampliaciones futuras.
