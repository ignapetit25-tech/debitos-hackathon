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

## Evidencia Meta (separada del simulador)

- Sonda mínima: `tools/check_meta.py` (pendiente de ejecución con clave).
- Aceptación: `tests/test_meta_live.py` — exige llamada Meta exitosa →
  texto usado en propuesta → revisión humana → aprobación registrada.
  Sin clave se omite; con clave y fallo de Meta, FALLA (el modo
  degradado no cumple el hito de integración real).
- Métricas deterministas (extracción/reglas) y del simulador NO se
  mezclan con evidencia Meta: cada corrida declara su proveedor.

Pendientes:
- Solicitud mínima autenticada contra Meta (clave del proyecto
  configurada localmente, fuera del repo; prueba en curso).
- Adaptador real JSON (implementado, desactivado, no verificado).
- OCR sobre documentos fuera de los fixtures controlados.
