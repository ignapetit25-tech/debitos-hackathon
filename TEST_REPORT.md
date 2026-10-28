# Informe de pruebas

## Métricas deterministas (sin modelo)

Ejecutadas (entorno local):
- Suite sin API: 40 tests OK (35 previos + 5 Baseten sin red:
  sin-clave explícita, modelo/base por defecto, timeout 60 y
  max_retries 0, error de red sin éxito simulado, solo-chat).
- Baseten: implementado (`BasetenProvider`, sonda mínima y test de
  aceptación con datos ficticios). Sonda sin clave falla explícito
  (exit 1, 0 llamadas). Prueba real pendiente de autorización;
  0 llamadas a Baseten hasta ahora.
- Suite unitaria previa: 35 tests OK (dinero, reglas, aprobaciones, historial
  + timestamps, aislamiento, errores de proveedor, inyección,
  expediente + hallazgos, proceso + gestor + seguimiento). El test
  live no se repitió en esta fase (presupuesto); su última corrida
  fue verde.
- Gestor de convenios (ficticios, 0 inferencias): 4 versiones en 3
  financiadores; solape junio-2026 resuelto a v2026 con aviso;
  siembra idempotente; aranceles ahora salen del gestor.
- Proceso: prioridad por umbrales, SLA que salta fines de semana,
  checklist (renglones, sumas, coseguros, convenio, responsable),
  devolución validada (decisión, montos enteros, responsable, fecha)
  con evento `seguimiento`. Captura `docs/shots/05-proceso.png`.
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
  aprobación registrada en historial.
- Expediente `EXP-900` (factura + liquidación + convenio, prestación
  2026-08-10): 1 llamada Meta → 10 hallazgos persistidos, 8 con cita
  verificada y 2 marcados CITA NO VERIFICADA; consumo 615/13057
  in/out (13.672 de 20.000 tokens de presupuesto F2). Propuesta
  Convenios/reclamar respaldada, pendiente de revisión.
- Matriz de 6 fallos (proveedor simulado, 0 inferencias): convenio
  ausente → pedir_extension; vigencia incorrecta → pedir_extension;
  sumas inconsistentes → inconsistencia + pedir_extension; referencia
  inexistente → CITA NO VERIFICADA explícita; cambio de caso durante
  solicitud → guard busy + botones deshabilitados (inspección);
  proveedor caído → DEGRADADO con expediente determinista intacto.
- UI verificada en motor JS real (jsdom contra el servidor): banner
  Meta, 10 casos en bandeja, expediente, 10 hallazgos, 3 documentos,
  historial; 0 errores JS; 0 usos de innerHTML.
- Capturas `docs/shots/01-bandeja.png` … `04-revision.png`
  (Playwright contra la página local, 0 errores JS, 0 inferencias):
  bandeja con estados e importes, expediente conciliado de `EXP-900`,
  evidencia con hallazgos cita OK / CITA NO VERIFICADA y formulario
  de revisión pendiente (sin decidir). Detalle cosmético pendiente:
  anchos de columna en tablas angostas.
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
  a punta (prueba automatizada, NO revisión humana).
- Elegibilidad: Idea declarada elegible por Adam Blumenfeld (Cerebral Valley) en el hilo del proyecto, 27/10/2026: https://discord.com/channels/1557169028080869426/1564401698259337216/1564670797908410389 — Alcance: gestión administrativa de débitos, sin juicio clínico, datos ficticios, aprobación humana. Valoró el conocimiento directo del problema y la posibilidad real de implementación. No resolvió por separado código preexistente ni modelos aceptados (se siguen las FAQs oficiales). No es certificación de seguridad/cumplimiento ni aprobación de ampliaciones futuras.
- Historial con fecha y hora ISO por evento; la migración conserva
  eventos previos con `creado` vacío. Casos `DEMO-META-2` /
  `P-DEMO-META-2-1` y `DEMO-META-3` / `P-DEMO-META-3-1` preparados con
  Meta (propuesta y borrador visibles, 0 revisiones), pendientes de
  decisión personal del usuario desde la interfaz. `DEMO-META-3` se
  sembró por extracción real de su PDF generado (`tools/add_caso_pdf.py`).
- La demo sirve el PDF de origen (`/api/pdf`, solo casos con PDF
  generado) y aclara en la revisión: aprobar la propuesta no acepta
  el débito ni autoriza comunicaciones; nada envía mensajes ni toca
  sistemas externos.
- Revisión PERSONAL del usuario (`deler`, 27/10/2026 15:53 -03:00):
  aprobada `P-DEMO-F123-4` (Convenios/reclamar) sobre `DEMO-F123`.
  Cadena verificada: PDF de origen servido → sumas OK (dif 0) →
  reglas 4 pts → `llamada_modelo` Meta ok (muse-spark-1.3, ID real,
  6890ms, 155/1656 tokens) → propuesta → revisión con revisor,
  propuesta, antes/después y fecha/hora (sin fundamento escrito).
  Es revisión personal, distinta de la prueba operada por el agente
  (`muse-demo`). `DEMO-META-2` y `DEMO-META-3` siguen pendientes
  (0 revisiones).
- Clave del proyecto en `.env` local (permisos 600, ignorado por Git);
  jamás impresa ni commiteada. No se repitieron llamadas para
  reconfirmar lo ya evidenciado.

Pendientes:
- Adaptador real JSON (implementado, desactivado, no verificado).
- OCR sobre documentos fuera de los fixtures controlados.
