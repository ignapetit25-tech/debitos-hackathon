# Informe de pruebas

## Métricas deterministas (sin modelo)

Ejecutadas (entorno local):
- Suite unitaria: 19 tests OK (dinero, reglas, aprobaciones, historial,
  aislamiento, errores de proveedor, inyección).
- Evaluación sintética sobre 7 casos controlados: extracción 7/7,
  derivación 7/7, abstención 7/7 (incluye 1 PDF escaneado con OCR
  spa, confianza 0.92). "Abstención 7/7" significa: derivó a humano
  en los casos clínicos y produjo propuesta administrativa en los
  demás, sin falsos en ningún sentido. Es una comprobación sobre
  esos ejemplos, NO demuestra precisión general ni cobertura clínica.
- Demo web: flujo proponer->revisar->historial->borrador OK;
  caso clínico deriva a humanos.

## Evidencia Meta (separada de lo determinista y del simulador)

- Sonda mínima `tools/check_meta.py`: OK con `muse-spark-1.3` vía
  protocolo Responses, datos ficticios. Evidencia: proveedor, modelo
  devuelto, ID de respuesta, estado, latencia y consumo informado.
- Aceptación `tests/test_meta_live.py`: OK. Llamada real → texto del
  modelo usado en la propuesta → evento `llamada_modelo` auditable →
  aprobación registrada en historial. Suite total: 20/20.
- Corrección requerida por Meta: `EXPLICACION_SCHEMA` necesitó
  `"additionalProperties": False` (modo estricto). El
  `AuthenticationError` anterior solo confirmaba conectividad y rechazo
  de credenciales; NO validaba el esquema. El esquema quedó validado
  por la llamada exitosa posterior.
- LÍMITE: la aprobación del test es automatizada (`revisor-hito`);
  NO representa una revisión humana real. Falta un recorrido con Meta
  donde una persona revise y apruebe en la demo.
- Clave del proyecto en `.env` local (permisos 600, ignorado por Git);
  jamás impresa ni commiteada. No se repitieron llamadas para
  reconfirmar lo ya evidenciado.

Pendientes:
- Adaptador real JSON (implementado, desactivado, no verificado).
- OCR sobre documentos fuera de los fixtures controlados.
