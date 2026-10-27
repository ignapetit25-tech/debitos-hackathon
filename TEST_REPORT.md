# Informe de pruebas

Ejecutadas (entorno local, 2026-10-26):
- Suite nueva: 19 tests OK (dinero, reglas, aprobaciones, historial,
  aislamiento, errores de proveedor, inyección).
- Evaluación sintética: extracción 7/7, derivación 7/7, abstención 7/7
  (incluye 1 PDF escaneado con OCR spa, confianza 0.92).
- Demo web: flujo proponer->revisar->historial->borrador OK;
  caso clínico deriva a humanos.

Pendientes:
- Solicitud mínima autenticada contra Meta (sin MODEL_API_KEY aquí).
- Adaptador real JSON (implementado, desactivado, no verificado).
- OCR sobre documentos fuera de los fixtures controlados.
