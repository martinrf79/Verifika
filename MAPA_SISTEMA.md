# Mapa del sistema — auditoría 23-jun-2026

Documento de diagnóstico previo, pedido por Martín y exigido por el CLAUDE.md
antes de tocar nada. Hecho leyendo el código, no de memoria. Objetivo: ver el
sistema completo, qué corre de verdad, qué módulos están vivos y cuáles muertos,
para después consolidar con el mapa a la vista.

---

## 1. Punto de entrada y los CUATRO caminos paralelos

El mensaje entra siempre igual:

`main.py` (webhook Telegram o WhatsApp) → `orchestrator.process_message`.

Dentro del orchestrator hay **cuatro sistemas completos compitiendo**, cada uno
detrás de un flag. Se eligen en este orden de prioridad:

1. **MODO_LIBRE** → `modo_libre.py`. El modelo responde libre, sin ninguna capa.
   Experimento del 16-jun.
2. **CAMINO_NUEVO** → `camino_nuevo.py`. **Tu arquitectura de dos cañerías**:
   intérprete (LLM 1) → director aplica comandos → provider resuelve el hecho →
   planilla única → redactor (LLM 2) + render estampa el número verificado.
3. **NUCLEO_FUENTE_VERDAD** → `nucleo.py`. Las cuatro puertas.
4. **legacy** (default, si los tres de arriba están en off) → el cuerpo del
   orchestrator, unas catorce capas de Solver con herramientas más verificadores.

**Cuál corre HOY en producción no se sabe desde el repo.** Depende de las
variables de entorno de Cloud Run, que derivaron entre sesiones. Ese es el dato
que falta y que pido al final.

---

## 2. Las dos cañerías que vos describís, mapeadas al código

- **Cañería principal** (el idioma humano, lo que hace bien el LLM):
  `interpretador.py` (LLM 1, entiende y emite comandos) → `redactor` dentro de
  `camino_nuevo.py` (LLM 2, redacta y vende) → `render.py` (estampa el número ya
  verificado). El redactor NUNCA escribe un número: deja un marcador y el código
  lo reemplaza.

- **Cañería secundaria** (el dato, lo que hace bien el código): `director.py`
  (aplica agregar/sacar/cambiar al carrito) → `certificador.py` (identidad:
  existe / ambiguo / no existe) → `provider.py` + `cotizar_codigo.py` (precio,
  envío, total reales) → `estado_pedido.py` (la planilla única que viaja con
  todo) → `puentes.py` y `leads.py` + `pago.py` (cierre y link de Mercado Pago).

Es decir: **lo que pediste ya está construido y es `camino_nuevo`.** No hay que
inventarlo, hay que dejarlo solo y prenderlo bien.

---

## 3. Inventario de flags

Hay 118 variables en `config.py`. Del orden de **setenta son flags de
comportamiento**. Agrupados por para qué sirven:

### a) Perillas que ELIGEN el camino (sobran tres de cuatro)
`MODO_LIBRE`, `CAMINO_NUEVO`, `NUCLEO_FUENTE_VERDAD`, `USE_INTERPRETER`,
`USE_VERIFIKA`, `MOTOR_ENTRADA`, `USE_LEADS`.

### b) Flags que la columna limpia NECESITA prendidos para andar bien
`DIRECTOR_LLM`, `PROVIDER`, `ESTADO_PEDIDO`, `CONFIRMACION_PROVIDER`,
`PUENTES_VENTA`, `REGISTRO_SESION`, `NO_RESALUDO`, y las herramientas
deterministas de la cañería secundaria: `ENVIO_POR_ZONA`, `TARIFA_PROVINCIA`,
`STOCK_GATE`, `CP_COMPLETO`, `LINK_PAGO`, `PEDIDO_MULTI`, `PEDIDO_PENDIENTE`,
`FECHA_ENTREGA`, `POSVENTA_TOOLS`, `CALC_DEFENSIVA`.

Esto es lo más grave del teléfono descompuesto: la columna buena depende de que
una decena de sub-flags estén en la posición justa. Si uno quedó en off,
`camino_nuevo` corre cojo. **Al consolidar, estos dejan de ser flags y pasan a
estar cableados prendidos en el código.**

### c) Flags que SOLO sirven al camino legacy (mueren con él)
`VERIFICADOR_MODE`, `VERIFICADOR_SERVICIOS`, `VERIFICADOR_HECHOS`,
`CHECKER_GATEA`, `COMPUERTA_UNICA`, `LIBRO_ASIENTOS`, `LIBRO_MODO`,
`GUARDA_COMPLETITUD`, `CORRECTOR_ANCLADO`, `AUTOFIX`, `VERIFICADOR_AUTOCORRIGE`,
`PROMPT_VENTA`, `PROMPT_LIGERO`, `PROMPT_CONSTITUCION`, `TOOLS_MINIMAS`,
`SOLVER_CODIGO`, `SOLVER_CODIGO_PRIMARIO`, `RESCATE_TOOLCALL_TEXTO`,
`CARRITO_DELTA`, `CARRITO_VIGENTE`, `RESCATE_*`, `CIERRE_*`, `EVIDENCIA_REGISTRO`,
`QUERY_PLATA_FUERA`, `BUSQUEDA_POR_CODIGO`, `BUSQUEDA_RELAJADA`,
`FAQ_MATCH_PALABRAS`, `FAQ_DIRECTO`, `ESTADO_NO_REGRESA_SALUDO`,
`PISO_PRESUPUESTO`, `COTIZA_CODIGO`, `COTIZA_TRANSFERENCIA`, `PRESUPUESTO_AB`,
`RESOLVER_PEDIDO`, `VERIFIKA_CHECKER_ADVISORY`. La mayoría son parches de la era
del Solver con herramientas, que la columna nueva ya no usa.

### d) Flags de experimentos muertos
`MOTOR_ENTRADA`, `RESOLVER_ASPECTOS`, `INTERPRETE_ANCLA_CATALOGO`,
`EMBEDDINGS_ON`. No los llama ningún camino vivo, o están en off y nadie los
consume.

### e) Flags operativos que se quedan
`DEEPSEEK_*`, `INTERPRETER_PROVIDER`, `LLM_*`, `MEMORIA_TTL_HORAS`,
`HISTORY_LIMIT`, `SEARCH_TOP_N`, `UMBRAL_ENVIO_GRATIS`, `RESET_CODE`,
`NUEVA_COMPRA_RESET`, `CATALOGO_CODIGO`, `SALUDO_CODIGO`, `ANTI_JAILBREAK`,
`DIAG_TRACE`, `TELEMETRIA_TURNO`, `PROCESAR_EN_REQUEST`, `PRECALENTAR_CACHE`.

---

## 4. Módulos vivos vs muertos

### VIVOS — infraestructura y cañería secundaria (se quedan)
`tools.py`, `tools_context.py`, `envio.py`, `entrega.py`, `posventa.py`,
`calc_defensiva.py`, `certificador.py`, `pedido_multi.py`, `resolver_pedido.py`,
`provider.py`, `cotizar_codigo.py`, `director.py`, `estado_pedido.py`,
`confirmacion.py`, `render.py`, `puentes.py`, `resaludo.py`, `faq_responder.py`,
`leads.py`, `notificador.py`, `pago.py`, `cierre.py`, `interpretador.py`
(intérprete LLM 1), `transcriber.py`, `telemetria.py`,
`verifika/llm_adapter.py` (adaptador de modelo por rol, lo usa `tools.py`).

### VIVOS solo en el camino LEGACY (mueren al consolidar sobre camino_nuevo)
- `agent.py` — el Solver con tool-calling. **camino_nuevo NO lo usa**: usa el
  redactor, que no llama herramientas porque el código ya le pasa el dato. Este
  es el cambio conceptual grande: tu "solver" pasa a ser el redactor.
- `validator.py`, `guardian.py` — validan la salida del Solver viejo.
- `verificador.py`, `verificador_servicios.py`, `verificador_hechos.py` — los
  tres verificadores de la era del Solver.
- `compuerta.py`, `gate_gravedad.py`, `libro.py`, `corrector.py`,
  `constitucion.py` — capas anti-alucinación del legacy.
- `responder_codigo.py`, `carrito_delta.py` (reemplazado por `director.py`),
  `redactor.py` (el de núcleo, distinto del redactor de camino_nuevo).
- `nucleo.py`, `objecion.py` — el camino NUCLEO.
- `modo_libre.py` — el camino MODO_LIBRE.
- `verifika/pipeline.py`, `verifika/proposer.py`, `verifika/checker.py` — el
  Checker LLM. camino_nuevo no lo usa.
- `antijailbreak.py`, `interprete_ancla.py` — opcionales, se pueden conservar.

### MUERTOS hoy mismo (no los llama ningún camino vivo, solo scripts)
`comprension.py` (el OTRO intérprete), `motor_entrada.py`,
`resolver_aspectos.py`, `responder_simple.py`.

---

## 5. Diagnóstico: por qué anda mal

No es falta de código bueno. Es exceso de sistemas vivos a la vez:

1. **Cuatro caminos completos** compiten por flag en el mismo orchestrator.
2. **El camino bueno depende de una decena de sub-flags** en la posición justa.
   Un solo flag mal seteado en Cloud Run lo deja cojo.
3. **La config vive en la nube y derivó entre sesiones**, así que nadie sabe con
   certeza qué combinación corre hoy.
4. **Dos intérpretes** en el repo, uno vivo (`interpretador`) y uno muerto
   (`comprension`), más bancos que prueban el muerto.

El resultado es impredecible: el mismo mensaje puede tomar caminos distintos
según cómo quedaron los flags.

---

## 6. Target de consolidación propuesto

Un solo camino, un solo intérprete, un solo redactor, una sola verificación.

- **Único camino:** `camino_nuevo` pasa a ser EL sistema, sin flag, default y
  obligatorio. Se borran del orchestrator las ramas MODO_LIBRE, NUCLEO y el
  cuerpo legacy entero.
- **Único intérprete:** `interpretador.py`. Se borra `comprension.py`,
  `motor_entrada.py`, `resolver_aspectos.py`, `responder_simple.py` y sus flags.
- **Sub-flags cableados:** los del grupo (b) dejan de ser flags y quedan prendidos
  en el código. Se borran del config.
- **Se borran** los módulos legacy del grupo "vivos solo en legacy" y sus flags
  del grupo (c) y (d).
- **Se conserva** toda la cañería secundaria determinista (grupo de módulos vivos).

### El único punto flojo a vigilar
La "verifica/filtro" del final de tu cañería principal hoy en camino_nuevo es
estructural, no un verificador aparte: el número lo estampa el render, las URLs
se borran, y la identidad la gatea el certificador. Pero la PROSA no numérica del
redactor no pasa por un filtro final. Ahí es donde un dato real puede caer en el
cajón equivocado. Cuando lleguemos a esa etapa, se puede reusar una versión
liviana del verificador como filtro final, sin resucitar las catorce capas.

---

## 7. Lo que necesito de Martín para avanzar seguro

1. **La config real de producción:** salida de
   `gcloud run services describe agente-v4 --region southamerica-east1`, o las
   env que tiene prendidas. Sin esto no sé desde dónde parto ni qué está
   corriendo cuando decís que anda mal.
2. **El comando de prueba** que mencionaste, para validar `camino_nuevo` contra
   casos reales ANTES y DESPUÉS de cada recorte. Un banco que corra ESTE camino,
   no una copia del prompt.
