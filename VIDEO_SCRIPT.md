# Guion del video

Aclaración inicial (textual):

> El sistema administrativo ya existía. Durante este hackatón
> construimos esta capa independiente de IA y su demo con datos
> completamente ficticios.

## Quién y por qué (0:10)

> El proyecto nace de la experiencia de su creador como responsable
> del sector Débitos de un policlínico argentino, donde gestiona
> diariamente deducciones de obras sociales, prepagas y ART. Busca
> reducir el trabajo manual de lectura, conciliación, derivación y
> seguimiento, manteniendo las decisiones finales en personas.

## Recorrido (0:40–2:30)

1. Expediente `EXP-900` → 3 documentos de origen (factura,
   liquidación, convenio con vigencia).
2. Extracción: 2 renglones, origen texto, confianza 1.0, sin dudosos.
3. Conciliación: $16.500 + $42.000 = $58.500, dif 0 (centavos
   enteros); valores convenidos vigentes a la prestación.
4. Propuesta: Convenios/reclamar respaldada por hallazgos.
5. Aporte de Baseten (muse-spark-open): hallazgos con citas comprobadas por código
   (qué se verificó y qué quedó marcado no verificado).
6. Borrador de reclamo: plantilla con datos verificables.
7. Revisión personal en la interfaz: aprobar la propuesta no acepta
   el débito ni autoriza comunicaciones.
8. Historial: fecha/hora con zona, llamada al modelo, revisor,
   fundamento y transición antes/después.
9. Caso clínico: derivación a personas sin recomendar aceptar ni
   reclamar; caso ambiguo: revisión humana obligatoria.

## Cierre (2:30–3:00)

- Idea declarada elegible por Adam Blumenfeld (Cerebral Valley),
  27/10/2026: gestión administrativa de débitos, sin juicio clínico,
  datos ficticios, aprobación humana. Enlace y alcance exacto en
  README y TEST_REPORT.md. No es certificación de seguridad o
  cumplimiento ni aprobación de ampliaciones futuras.
- La posibilidad de implementación futura es parte del valor del
  proyecto. La capa IA NO está desplegada en el policlínico ni sus
  beneficios fueron medidos en producción.
- Separación: métricas deterministas, llamadas reales al proveedor y
  revisión humana van por separado (TEST_REPORT.md).
