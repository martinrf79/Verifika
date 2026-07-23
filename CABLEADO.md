# CABLEADO.md — Mapa de plomería y checklist del sistema

> Panorama del CABLEADO (conectores, contactores, enums, y la conexión entre
> fuentes). Las PARTES del sistema (intérprete, solver, tools) viven en
> `ARQUITECTURA.md`; el ESTADO vivo en `RESUMEN_PARA_NUEVO_CHAT.md`; las REGLAS
> en `CLAUDE.md`. Este doc es la PLOMERÍA: cómo se conectan las partes y qué
> tiene que estar completo para que el sistema no falle por falta de datos.

## Por qué existe

Cada sesión nueva clona el repo desde cero y no ve las anteriores. A esta altura
la mayoría de las fallas **NO son de código: son de falta de datos o de
incompatibilidad de cableado.** Es el mismo fenómeno que cuando el LLM responde
mal porque algo no está en la fuente de verdad. Este documento es el mapa para
no repetir eso, y el checklist para robustecer área por área.

## Las dos fuentes de verdad (y el problema de namespace)

1. **CONTACTOR** — `data/clientes/<tienda>/base_conocimiento.json`. Las
   CATEGORÍAS (el enum) al que el INTÉRPRETE clasifica cada mensaje. Cada una:
   `id`, `grupo`, `pilar`, `descripcion`, `disparadores`, `criterio` (el "desde
   dónde contestar" del modelo, **sin un solo dígito**).
2. **FAQ** — `data/clientes/<tienda>/faq.json`. Las `respuesta_curada` de cara al
   cliente y el DATO DURO (`valores` con placeholders como `{{envio_gratis}}`).

**REGLA DE ORO DEL CABLEADO:** todo tema que un cliente pueda preguntar tiene que
existir en AMBOS namespaces, con la MISMA clave. Si la FAQ tiene un tema que el
contactor no tiene como categoría, el intérprete **no puede rutearlo**: cae en la
categoría más cercana equivocada y el modelo parafrasea desde el bloque
incorrecto. Eso es la alucinación blanda. Fue la causa raíz de envío (embalaje
caía en garantía) y de 5 áreas más (ubicacion, horarios, reservas, usados,
retiro_local). No era el intérprete: era el contactor incompleto.

## El flujo — dónde vive cada conexión

```
mensaje
  → INTERPRETADOR (app/core/interpretador.py)
       clasifica a categorias del ENUM del contactor (+ pedido, destino, intención)
  → HUB_ATADO (app/core/hub_atado.py)  [el orquestador del turno, VIVO en prod]
  → GENERADOR_V2 (app/core/generador_v2.py)
       arma FRAGMENTOS, RINDE cada dato desde la fuente, ESTAMPA el dato duro
  → TOOLS (app/core/tools.py, geo_cp, envio, calc) — el dato duro nace acá
  → VERIFICADORES (verificador_stock, guardia_promesas, verificador_cita)
  → respuesta estampada al cliente
```

- El **dato duro** (precio, stock, total, tarifa de envío) SIEMPRE lo estampa el
  código desde la tool o desde `valores`. NUNCA sale del `criterio` ni de la
  prosa del modelo.
- El **criterio** (base_conocimiento) es guía del modelo, sin dígitos.
- La **prosa** la escribe el MODELO con su criterio. El código NO estampa frases
  fijas de política: se probó (fix de envío del 23-jul) y robotiza. Se revirtió.

## Reparto de responsabilidad (decisión de arquitectura, 23-jul)

- **LLM: DECIDE y HABLA.** Qué decir, tono, cuándo confirmar lead fuerte, cuándo
  cerrar, qué datos tejer. Criterio libre. Es su fuerza; no se toca.
- **Código: VERIFICA el dato duro y ATA por enum.** No decide prosa ni estampa
  frases. Filtro de salida, no generador.
- **Línea de error, explícita:** dato duro = tolerancia cero (lo caza el
  verificador). Matiz de prosa/política ("automático" vs "tabla por localidad") =
  se acepta. Perseguir el matiz es lo que robotiza.

## Checklist de cableado correcto (para agregar o robustecer un área)

Para CADA área (envío, garantía, financiación, postventa, fiscal, etc.):

1. ¿Todo tema de la FAQ tiene **categoría espejo** en el contactor?
2. ¿El `id` de la categoría **== la clave del tema de la FAQ**? (evita colisiones
   de nombre tipo `envio_costo` vs `costo_envio`).
3. ¿El `criterio` **no tiene dígitos**? (el loader lo exige; el dato duro sale de
   `valores`/tools).
4. ¿Los `disparadores` cubren las formas comunes de preguntar?
5. ¿El tema es de PRODUCTO (specs, material, procedencia, contenido de la caja)?
   → va por **FICHA** (`CAMPOS_FICHA` en generador_v2), NO por categoría.
6. ¿Es STOCK / precio / total? → va por **HERRAMIENTA**, NO por categoría.
7. **Confirmación CONDUCTUAL obligatoria:** tirar varios fraseos por el intérprete
   y ver que rutee a la categoría correcta. El match estático NO alcanza.

## Cómo CHEQUEAR — el sistema de fiscalización (dos capas)

- **Capa 1, estático (barato, sobre-reporta, NO es veredicto):**
  `python3 banco_pruebas/fiscalizador.py [tienda]`
  Cruza los dos namespaces y marca temas sin categoría espejo + colisiones de
  nombre. Sobre-reporta a propósito: algunos temas van por ficha o herramienta.
- **Capa 2, conductual (la verdad):**
  `INTERPRETER_PROVIDER=gemini BANCO_PAUSA_S=22 python banco_pruebas/fiscalizador_conductual.py`
  Corre fraseos NATURALES (que NO copian los disparadores) por el intérprete REAL
  y verifica que cada uno rutee a la categoría que puede contestarlo, sin que un
  vecino confundible se lo robe. Es lo ÚNICO que confirma si un hueco es real.
  Ojo cuota: Gemini free throttlea (429); el script reintenta con backoff y marca
  "sin evaluar" lo que no pudo, sin contarlo como fallo.

## Deuda de plomería conocida (snapshot — actualizar al cerrarla)

- **Colisiones de nombre — reconciliadas (23-jul):** `envio_costo` y
  `envio_plazo` del contactor se renombraron a `costo_envio` y `plazo_envio`
  para calzar con la clave FAQ, que es la load-bearing en código. El fix tocó
  solo `base_conocimiento.json` (las categorías no se referencian en código) más
  el lock del enum en `tests/test_contactor_categorias.py`.
- **Falso positivo del pre-scan:** `seguimiento` (contactor) ↔ `seguimiento_pedido`
  (FAQ) NO es colisión: el primero es re-enganche conversacional del cliente que
  quedó en pensarlo, el segundo es rastreo del envío. Conceptos distintos, no se
  fusionan.
- **Categorías espejo agregadas (23-jul):** el contactor pasó de 85 a 93
  categorías. Se renombró `seguimiento_tracking` → `seguimiento_pedido` (calza con
  la clave FAQ, mismo concepto) y se sumaron 7 espejos que no tenían categoría
  rueteable: `precios_iva`, `monedas_aceptadas`, `promociones`, `reposicion_stock`,
  `verificacion_pagos`, `cancelacion_pedido`, `contacto_humano`, más
  `envoltorio_regalo`. Todas con criterio sin dígitos y disparadores desde los
  keywords de la FAQ. **Confirmación conductual (Capa 2) HECHA (23-jul): 18/18.**
  Las 8 espejos rutean a su id con fraseos naturales, ningún vecino confundible
  se las roba (ej. "aceptan usdt" → monedas_aceptadas; "quiero dar de baja lo que
  pedí" → cancelacion_pedido; "rastreo el paquete" → seguimiento_pedido). El set
  vive en `banco_pruebas/fiscalizador_conductual.py`.

- **Auditoría de cableado determinista (23-jul) — LIMPIA.** Se cruzaron todos los
  ejes duros offline: los 93 criterios sin dígitos (todos entran a GUIA_VENTA), las
  50 respuestas_curadas estampan sin fallar (ningún placeholder `{{x}}` sin su
  valor), FAQ sin temas huérfanos (todos con keywords y curada), no_vendidas con
  alternativas que validan contra el catálogo real, y las ataduras de código
  (`faq_tema`/`concepto` en tools) resuelven o degradan sin romper. La Capa 1
  estructural está sólida; el riesgo residual es solo conductual (Capa 2).
- **Cubiertos por categoría-concepto bajo otra clave** (el pre-scan los marca por
  token pero SÍ rutean): `reembolso` ← `cambios_devoluciones`, `confianza_seguridad`
  ← `desconfianza_online`, `datos_fiscales` ← `factura`, `mayoristas` ←
  `mayorista_cantidad`.
- **Falsos positivos del pre-scan** (van por ficha o tool, no por categoría):
  `especificaciones`, `material_composicion`, `origen_procedencia`,
  `contenido_caja`, `stock_disponibilidad`.

## Cuándo empezar con pruebas exigentes (DeepEval u otra)

Recién cuando el checklist de cableado esté verde por área. **DeepEval MIDE, no
CONSTRUYE robustez;** correrlo antes de cerrar la plomería es medir sobre huecos.
Orden correcto: primero fuente completa + contactor alineado + confirmación
conductual; después, testing exigente como red de regresión, no como
protagonista. (Ver `banco_pruebas/banco_deepeval.py` y `juez_deepeval.py`.)

## La regla que resume todo

El sistema **no alucina el dato duro** (lo ata el código). Parafrasea o alucina
cuando la **FUENTE o el CONTACTOR están incompletos**. Robustecer =
**completar la fuente y alinear el contactor**, no agregar código ni estampar
prosa. Simple es bueno: una pregunta compleja se resuelve simple cuando el enum
tiene la casilla y la fuente tiene el dato.
