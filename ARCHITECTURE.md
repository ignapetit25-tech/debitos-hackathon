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
- `agent.py`: pipeline determinista; el modelo solo redacta explicación
  con datos dados (ver "Qué hace cada etapa" en README). Documentos = dato delimitado, nunca instrucción.
  Disparador clínico -> `derivar_humano` sin recomendar acción económica.
- `drafts.py`: plantillas deterministas; el modelo no redacta borradores.
- Fronteras: puntaje de reglas (int) y confianza de extracción (float)
  son campos distintos; propuestas y decisiones son registros separados.
