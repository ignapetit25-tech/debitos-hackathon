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
  NO representa una revisión humana real.
- Recorrido demo con Meta (`DEMO-F123`, datos ficticios): extracción
  2/2 sin dudosos, sumas OK (dif 0), propuesta Convenios/reclamar con
  texto de `muse-spark-1.3`, borrador verificado cifra por cifra,
  aprobación registrada. Historial: `llamada_modelo` proveedor=meta
  estado=ok latencia 5400ms uso 155/1229 in/out + `revision` aprobada
  con fundamento. Revisión operada por Muse bajo instrucción explícita
  del usuario, registrada como `muse-demo` (no como persona): el
  circuito proponer→revisar→aprobar con Meta quedó probado de punta
  a punta (prueba automatizada, NO revisión humana). La elegibilidad
  ante los organizadores es una validación distinta y sigue pendiente.
- Historial con fecha y hora ISO por evento; la migración conserva
  eventos previos con `creado` vacío. Caso `DEMO-META-2` /
  `P-DEMO-META-2-1` preparado con Meta, propuesta y borrador visibles,
  pendiente de decisión personal del usuario desde la interfaz.
- Clave del proyecto en `.env` local (permisos 600, ignorado por Git);
  jamás impresa ni commiteada. No se repitieron llamadas para
  reconfirmar lo ya evidenciado.

Pendientes:
- Adaptador real JSON (implementado, desactivado, no verificado).
- OCR sobre documentos fuera de los fixtures controlados.
