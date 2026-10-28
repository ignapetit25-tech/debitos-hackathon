# Arquitectura

```
PDF ficticio -> extract.py -> money.py -> CasoStore ----+
   (pypdf / tesseract spa)   (centavos int)             |
                                                       v
contratos.py <-- synthetic.py <-- agent.py --> provider.py
   (ABCs)        (simulador)    (orquesta)     (meta | simulated)
                     |              |
                     v              v
               approvals.py    drafts.py
               (humano obliga) (plantillas)
                     |
              adapter_real.py (JSON, OFF, no verificado)
```

- `contracts.py`: Caso/Renglon/Propuesta/Decision/Historial + ABCs
  (obtener_caso, consultar_arancel, evaluar_reglas, guardar_propuesta,
  obtener_estado_casos). Dinero siempre int centavos.
- `provider.py`: interfaz + `MetaProvider` (paquete openai contra
  api.meta.ai, Responses text.format / Chat response_format, clave
  explícita) + `SimulatedProvider` etiquetado.
- `agent.py`: arma el expediente, pide hallazgos al modelo, los valida
  y persiste; la explicación cita lo verificado (ver README).
- `expediente.py`: conciliación determinista factura/liquidación/convenio,
  verificación de citas normalizada, mapeo a 4 tipos de hallazgo.
- `demo_app.py` + `static/`: API JSON + UI en 3 áreas (shell.html,
  app.css, app.js separados). Sin innerHTML: todo contenido documental
  se renderiza como texto. Documentos = dato delimitado, nunca instrucción.
  Disparador clínico -> `derivar_humano` sin recomendar acción económica.
- `drafts.py`: plantillas deterministas; el modelo no redacta borradores.
- Fronteras: puntaje de reglas (int) y confianza de extracción (float)
  son campos distintos; propuestas y decisiones son registros separados.
