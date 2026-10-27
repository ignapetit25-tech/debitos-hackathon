# Dependencias y condiciones

Python (requirements.txt): `openai` (cliente HTTP hacia api.meta.ai),
`pypdf` (lectura PDF), `reportlab` (generación de fixtures), `pillow`
(imágenes para PDF escaneados). Verificar licencias instaladas con
`pip show <paquete>` antes de distribuir.

Sistema: `tesseract-ocr` + datos `spa`, `poppler-utils`
(pdftotext/pdftoppm). No incluidos; el README explica instalación.

Proveedor: Meta Model API, https://dev.meta.ai/docs/overview
(modelo muse-spark-1.3). Uso sujeto a sus términos y facturación.
Credencial MODEL_API_KEY del operador; jamás se registra ni se commitea.
