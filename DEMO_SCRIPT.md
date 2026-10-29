# Guion demo (3 minutos, en vivo)

[0:00] Apertura: el sistema administrativo ya existía. Esta es una
capa IA independiente construida durante el hackatón, con demo y
datos completamente ficticios. Origen: su creador es responsable
del sector Débitos de un policlínico argentino.
[0:25] Caso `EXP-900`: bandeja → expediente con 3 documentos
(factura, liquidación, convenio). Tabla: facturado, liquidado,
diferencia y valor convenido vigente a la prestación.
[0:50] Hallazgos deterministas + faltantes + siguiente paso. Pedir
propuesta: 10 hallazgos de Baseten (muse-spark-open) con citas comprobadas por código
(8 OK, 2 marcadas no verificadas).
[1:20] Evidencia: clic en un hallazgo → fragmento, documento, página,
interpretación y limitaciones. Detalles Baseten en desplegable.
Borrador: plantilla, propuesta, no envío.
[1:50] Revisión: aprobar la propuesta NO acepta el débito NI autoriza
comunicaciones; la demo no envía mensajes ni toca sistemas externos.
[2:10] Historial: fecha/hora con zona, llamada al modelo (proveedor,
ID, latencia, consumo), propuesta y decisión con fundamento.
[2:30] Segundo caso (clínico o ambiguo): pide aclaración o deriva a
personas, sin forzar conclusiones. "Auditoría Médica" es un sector
humano de destino.
[2:50] Cierre: idea declarada elegible por Adam Blumenfeld (Cerebral
Valley) el 27/10/2026 para gestión administrativa con datos
ficticios y aprobación humana. Real vs simulado vs pendiente en
TEST_REPORT.md. La implementación futura es posibilidad, no despliegue.
