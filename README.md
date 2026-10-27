# Capa IA de débitos (hackatón)

Capa de IA independiente sobre un sistema preexistente de gestión de
débitos de financiadores de salud. Demo autónoma con datos 100%
ficticios. La elegibilidad específica está pendiente de confirmación
de los organizadores: nada aquí afirma aprobación alguna.

## Qué hace

PDF ficticio → extracción (texto u OCR español) → validación de sumas
→ consulta de reglas y aranceles → propuesta de derivación con
explicación → revisión humana obligatoria → historial antes/después.

Límites duros (en contratos, no en carteles): la IA no evalúa medicina,
no recibe historias clínicas, no envía correos, no acepta/rechaza
débitos. "Auditoría Médica" es un sector humano de destino.

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
  fuera de Git. Falta un recorrido demo con revisión humana real.
  Ejecuciones `simulated` siguen sin demostrar funcionamiento con Meta.
- Adaptador real (JSON): implementado, desactivado por defecto, NO verificado.
- Ejecuciones `simulated` no demuestran funcionamiento con Meta.
- OCR probado solo sobre fixtures generados con ruido controlado.

## Estado de licencia y publicación

- Licencia MIT: BORRADOR pendiente de aprobación (ver LICENSE-DRAFT-MIT.md).
- Sin remoto configurado, sin publicar, sin cambios de visibilidad.
- Elegibilidad del hackatón pendiente de respuesta de los organizadores.
