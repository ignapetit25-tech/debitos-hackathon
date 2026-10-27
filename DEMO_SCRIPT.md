# Guion demo (3 minutos, en vivo)

[0:00] Apertura: el sistema administrativo ya existía. Esta es una
capa IA independiente construida durante el hackatón, con demo y
datos completamente ficticios. Origen: su creador es responsable
del sector Débitos de un policlínico argentino.
[0:25] Caso `DEMO-META-3` (OS ficticia, F-400, $31.000): ver documento
de origen (PDF generado), detalle de renglones e importes.
[0:50] Pedir propuesta: validación de sumas OK, reglas → Convenios
con puntaje y frases, aranceles consultados.
[1:20] Explicación de Meta (`muse-spark-1.3`): redacta con datos
dados; mostrar qué aportó y qué NO (cifras y sector son
deterministas). Borrador: plantilla, propuesta, no envío.
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
