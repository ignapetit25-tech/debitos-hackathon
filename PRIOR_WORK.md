# Trabajo previo vs trabajo nuevo

Preexistente (repo privado `pmc-tools-web`, main `0ac2c4c`, revisión
externa): aplicación web de débitos, motor de reglas propio, SQLite
productiva, derivación, historial, evaluaciones, borradores. ~9.600 líneas.

Nuevo en este repositorio (hackatón), escrito desde cero:
- Contratos de integración, núcleo IA, reglas sintéticas mínimas.
- Cliente Meta Muse Spark + proveedor simulado explícito.
- Extracción PDF/OCR, agente, aprobaciones, borradores, demo web.
- Generador de fixtures ficticios, reinicio seguro, evaluación, tests.
- Toda la documentación de este repo.

Separación verificable: ningún `.py` de aquí importa `pmc_validator` ni
`sistema` (test_isolation); sin submódulos; sin historial copiado;
datos demo generados, jamás reales. Conceptos de dominio reutilizados
(derivación por puntaje/umbral, trazabilidad) sin copiar código.

Reproducción sin el sistema original: clonar SOLO este repo, crear
venv, `pip install -r requirements.txt`, `tools/reset_demo.py` y
levantar la demo. Ningún paso lee, importa o llama al sistema
preexistente; los PDFs y la base se generan aquí.
