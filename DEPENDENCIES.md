# Dependencies and terms

Python (requirements.txt): `openai` (HTTP client toward api.meta.ai),
`pypdf` (PDF reading), `reportlab` (fixture generation), `pillow`
(images for scanned PDFs). Check installed licenses with
`pip show <package>` before distributing.

System: `tesseract-ocr` + `spa` data, `poppler-utils`
(pdftotext/pdftoppm). Not included; the README explains install.

Provider: Meta Model API, https://dev.meta.ai/docs/overview
(model muse-spark-1.3). Use subject to its terms and billing.
Operator's MODEL_API_KEY credential; never logged or committed.
