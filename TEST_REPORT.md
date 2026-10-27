# Informe de pruebas

Ejecutadas (entorno local, 2026-10-26):
- Suite nueva: 19 tests OK (dinero, reglas, aprobaciones, historial,
  aislamiento, errores de proveedor, inyección).
- Evaluación sintética sobre 7 casos controlados: extracción 7/7,
  derivación 7/7, abstención 7/7 (incluye 1 PDF escaneado con OCR
  spa, confianza 0.92). "Abstención 7/7" significa: derivó a humano
  en los casos clínicos y produjo propuesta administrativa en los
  demás, sin falsos en ningún sentido. Es una comprobación sobre
  esos ejemplos, NO demuestra precisión general ni cobertura clínica.
- Demo web: flujo proponer->revisar->historial->borrador OK;
  caso clínico deriva a humanos.

Pendientes:
- Solicitud mínima autenticada contra Meta (clave del proyecto
  configurada localmente, fuera del repo; prueba en curso).
- Adaptador real JSON (implementado, desactivado, no verificado).
- OCR sobre documentos fuera de los fixtures controlados.
