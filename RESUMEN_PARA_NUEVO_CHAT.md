# Estado del sistema — fuente ÚNICA de verdad

Este es el único documento de estado. `CLAUDE.md` tiene las reglas e instrucciones
permanentes; acá vive QUÉ es el sistema hoy. Si algo viejo contradice esto, manda esto.

**Última actualización: 5-jul-2026.** BANCO DE CHARLAS VIVAS con JUEZ automático: los errores
que antes se estrenaban en la charla real ahora se cazan y arreglan ANTES, corriendo el pipeline
completo con DeepSeek desde el entorno de Claude (la clave está en el entorno web). La primera
tanda encontró 5 errores reales y se arreglaron por invariante (ver BANCO abajo): memoria de
productos MOSTRADOS (el solver ya no adivina ids), evidencia VIVA de vistos (los verificadores
juzgan productos de turnos anteriores con stock actual), ancla de stock con desempate de
variantes + nombre completo + ventana adelante ("tenemos el X" agotado dispara), multi-destino
que RECUERDA los destinos cotizados entre turnos, y acople sin duplicar (prosa que ya trae los
montos oficiales + gancho imperativo recortado). Segunda ola del mismo día (iterando la tanda
hasta verde): REGLA CERO mecánica en la calculadora (con pedido vigente solo acepta ids
certificados: carrito, mostrados o tools del turno; mató el total fantasma de otro producto),
evidencia con todo producto NOMBRADO en la respuesta (la melliza no juzga lo que no ve),
CUARENTENA determinista de stock (la reescritura que deja la mentira ya no sale), y ancla
exacta por nombre completo en plata y stock con dedup por id y negación que no cruza la
oración. **229 tests offline + 8 tests VIVO en VERDE ESTABLE: dos tandas completas seguidas
(5-jul). Listo para la charla real de humo.** Estrategia vigente: respuestas curadas + bloques
deterministas (el código es dueño de todo dato duro; el solver, de la prosa), acordada el 4-jul.

---

## Un solo camino (pipeline del turno)

Entrada → `orchestrator.process_message` → `app/core/interprete_libre.py`, que hace todo el turno:

1. **Intérprete** (DeepSeek, `interpretador.py`): entiende el mensaje en contexto. Devuelve
   intención, confianza, candidatos y `ofrecer_opciones`. Se loguea, no se muestra al cliente.
2. **Solver libre** (DeepSeek, `agent.run_agent`): vende libre con las tools atadas a Firestore
   (search_products, get_product_details, list_catalog, query_faq, calculate_total,
   cotizar_envio). Lista en `MODO_LIBRE_TOOLS`.
3. **Estampado determinista** (`_estampar_productos`): cada `[[PROD:id]]` se reemplaza por
   nombre + precio + stock REALES del catálogo. Un id inexistente se borra: el solver no puede
   inventar producto ni precio.
4. **Verificador de plata** (`verificador.py`): toda cifra de dinero de la respuesta tiene que
   salir de la evidencia (catálogo/FAQ/PROOF de las tools). Si no, autocorrige (candidato único)
   o bloquea (sin evidencia → fallback). Anclado al concepto (total/envío/precio).
4-bis. **Verificador de STOCK** (NUEVO, `verificador_stock.py`): afirmación de disponibilidad
   anclada al producto NOMBRADO vs stock real de la evidencia del turno. Cifra de unidades
   contradicha → safe-override determinista; "no tiene stock" falso u ofrecer un agotado →
   reescritura con la maquinaria de guardia (LLM solo en turnos que disparan). Además, GUIA
   determinista (`guia_compra.py`): si el cliente quiere "lo más barato", el CÓDIGO computa el
   más barato CON stock y lo inyecta como [[PROD:id]]; el solver no elige.
4-ter. **Verificador de FAQ NUMÉRICA** (NUEVO, `verificador_faq.py`): números chicos de política
   (X%, N cuotas, N días, N meses) contra FAQ estructurada+prosa y garantia_meses del catálogo.
   Porcentaje/meses exactos; cuotas/días/horas por rango ("hasta 6" habilita ≤6). Corrección
   SOLO anclada al tema consultado por query_faq este turno y con candidato único; si no, log.
5. **Guardia de promesas** (`guardia_promesas.py`): set CERRADO de 3 clases prohibidas
   (día de entrega, retiro en local, servicio no ofrecido) → reescribe.
6. **Guarda de divergencia A/B** (NUEVO, `interprete_libre._forzar_pregunta_si_ambiguo`): si el
   intérprete marcó `ofrecer_opciones` (dos caminos, no puede elegir) pero el solver NO planteó
   la elección, el código FUERZA la pregunta A/B. Si dispara, no se cierra ese turno.
7. **Cierre** (`leads.py` + `cierre.py` + `pago.py`): capta el lead según el modo (ver CIERRE).
8. **Memoria**: historial (10 turnos) + estado + último presupuesto + proofs, en Firestore.

---

## CI / DEPLOY — cadena con GATE anti-regresión (3-jul)

- **`test.yml`**: corre en cada push y PR → `pytest` (122 tests offline, `-m 'not vivo'`).
- **`deploy.yml`**: al pushear a `main`, dos jobs: `test` (batería offline) y `deploy` con
  **`needs: test`**. El deploy arranca SOLO si los tests pasan. Una regresión determinista no
  puede llegar a producción sin que el CI la frene sola. Verificado en vivo (run #70).
- **Límite:** el gate cubre los tests OFFLINE, no los `vivo` (LLM). Y **`./deploy.sh` manual
  SALTEA el gate** (hace `git reset --hard` + `gcloud deploy` directo). Deployar por CI (push a
  main). PENDIENTE opcional: agregar `pytest` a `deploy.sh` para blindar también el camino manual.
- Verificar el verde del run antes de decir "listo". Claude puede leer el estado del run por MCP.

## Infra

- Cloud Run: `agente-bot`, región `southamerica-east1`, proyecto `memory-engine-v1`. ÚNICO
  servicio de bot; el webhook de WhatsApp apunta ahí. `video-engine` apagado, no se toca.
- Rama viva = `main`. Se desarrolla en `claude/*` y se mergea a main (dispara el CI gateado).
- LLM: **DeepSeek en todo**. Premium (Opus/Fable) solo para un Checker pago, con OK de Martín.
- Config manda desde `config.py`; el servicio solo lleva secretos + `TIENDA_ID`.
- Observabilidad: structlog emite `severity` (Cloud Logging). Logs sin gcloud local: workflow
  `diagnostico.yml` (lo dispara Martín; Claude no tiene permiso de Actions de escritura).

---

## ENVÍO — robusto (3-jul)

`cotizar_envio` es la ÚNICA fuente del costo. Clasifica zona y provincia de forma determinista
y devuelve UN número (nunca rango). Estado actual:

- **Tabla completa de localidades** (`app/core/geo_cp.py` + `data/geo/codigos_postales_ar.csv`,
  ~16 mil localidades del país). Resuelve **provincia + localidad** → provincia canónica + CP →
  zona (caba/gba/interior) y tarifa exacta de la provincia. Reemplaza las listas parciales a mano.
  Localidad ambigua (existe en varias provincias) solo resuelve si la provincia está en el texto.
- **CP pelado** vivo: "5000", "1414", "mi cp es 1425" clasifican (regex full-match; un número
  suelto en una frase NO se toma como CP). Se eliminó el flag muerto `CP_COMPLETO`.
- **Guarda de calle**: un nombre seguido de un número ("san martin 1234") NO clasifica zona
  (es una dirección); ante la duda pide el dato, no adivina.
- Tarifa interior por provincia en `config.py` (`ENVIO_INTERIOR_POR_PROVINCIA`), pisable por
  tienda con Firestore `tarifas_envio`. Umbral de envío gratis desde la FAQ `costo_envio`
  ($250.000). Cierra con la frase fija "Envío orientativo, puede variar al confirmar la compra".
- **Multi-destino ARREGLADO (3-jul):** el envío gratis se mira POR DESTINO, no por la suma. Como
  los items no declaran destino, se usa el promedio (suma/destinos): conservador, solo libera el
  envío si el reparto claramente supera el umbral. Lockeado en `test_calculadora.py`.

## CIERRE — modo A (lead) vivo (3-jul)

Un solo juez: el interpretador (`decision_compra` con confianza ≥ 0.85) + pregunta suave de
cierre + gatillo determinista por respuesta a la pregunta. Modalidad por tienda (`MODO_CIERRE`
en config.py, pisable con Firestore `modo_cierre`):

- **`A` / `lead` (DEFAULT ACTUAL):** el cliente confirma → capta el lead fuerte, avisa al dueño
  y **sigue iterando SIN pedir datos** (nombre/teléfono/documento). El lead fuerte ya se logra
  captando + avisando; cierra un humano. Si ya hay lead fuerte activo, no re-avisa.
- **`B` / `venta`:** el bot cierra y manda el cobro (link de Mercado Pago o CBU).
- **`off`:** no actúa; el bot vende igual.

**IMPLEMENTADO (3-jul): la pregunta manda sobre el score.** Una `decision_compra` que NO llega
a la confianza del umbral ya no queda en nada: si hay presupuesto mostrado (nuevo o de memoria)
se hace LA pregunta de cierre, y la respuesta decide determinista (gatillo D). El score alto
(≥0.85) sigue cerrando directo; el resto pasa por la pregunta. Lockeado en test_cierre.

## FAQ — endurecido (3-jul)

Ruteo determinista por keywords (`query_faq`): el tema ESPECÍFICO le gana al genérico (score por
la keyword más específica, no la suma) y la puntuación no rompe el match ("pago contra entrega?"
rutea bien). Locks en `tests/test_faq.py`.
**FAQ NUMÉRICA cubierta (3-jul):** `verificador_faq.py` chequea los números de política (%,
cuotas, días, meses, horas) contra la fuente y corrige anclado al tema consultado (ver pipeline
4-ter). Locks en `tests/test_faq_numerica.py`.
**RESPUESTAS CURADAS 44/44 (4-jul, `curadas.py`):** patrón "LLM compila offline, runtime
determinista". Los 44 temas de faq.json tienen `respuesta_curada` aprobada por Martín (números
como huecos `{{concepto}}` estampados desde los valores del MISMO tema; 10 valores nuevos en 7
temas para que ningún número de política viva hardcodeado). Dos caminos de salida:
- **Standalone** (pregunta PURA de política, sin producto/carrito/cierre): sale la curada TAL
  CUAL y el solver NI CORRE. Evento: `interprete_libre_curada_servida`.
- **ACOPLE (4-jul):** si la FAQ se consulta DENTRO de una venta (query_faq del turno), el bloque
  curado del tema se pega en VERTICAL debajo de la prosa del solver: costura por salto de línea,
  un solo cierre por mensaje (si la prosa ya pregunta, el gancho del bloque se recorta por
  oración), sin duplicar si el solver pegó el texto tal cual. Lo decide el CÓDIGO, no un
  marcador: el marcador `[[FAQ]]` se RETIRÓ (consolidación). Evento:
  `interprete_libre_faq_acoplada`. Locks en `tests/test_acople.py`.
- **ACOPLE POR RUTEO (4-jul, charla viva):** el bloque también dispara por el ruteo determinista
  del MENSAJE (intérprete ve pregunta de política + keywords matchean tema curado), sin depender
  de que el solver llame query_faq. Además el tema acoplado ANCLA al verificador de FAQ numérica.
- **GUARDIA CON RED DETERMINISTA (4-jul, charla viva):** si la reescritura LLM de una promesa
  prohibida falla (volvió VACÍA dos veces en real y una dirección de local inventada salió al
  cliente) o deja la promesa, la CUARENTENA poda las líneas infractoras; sin mensaje decente,
  canned. La negación con "sin" pegada al match ("sin punto de retiro") no dispara, así la
  guardia no ataca a la propia curada. Verificado en vivo: el caso repetido salió limpio con el
  bloque oficial. Eventos: `interprete_libre_promesa_cuarentena` / `_promesa_bloqueada`.
**ACTIVADO EN VIVO (4-jul):** Martín cargó la FAQ 44/44 a Firestore desde Cloud Shell
(`.venv-shell/bin/python scripts/crear_cliente.py cargar_faq --tienda_id verifika_prod --faq
data/clientes/verifika_prod/faq.json` → "OK 44 preguntas cargadas"). Curadas y acople VIVOS en
producción. Nota: el Python global de Cloud Shell tiene el namespace google.cloud roto; usar
SIEMPRE el venv `.venv-shell` de ~/verifika para scripts con Firestore. PENDIENTE: validar en
charla real de WhatsApp (curada pura, acople en venta, retiro de local) leyendo los eventos
`interprete_libre_curada_servida`, `_faq_acoplada`, `_promesa_cuarentena`.

---

## Datos: un solo catálogo, una sola FAQ

- Producción: **880 productos** + **44 temas de FAQ** en `data/clientes/verifika_prod/`
  (`productos.csv` + `faq.json`). ÚNICA fuente. NO regenerar ni crear otros fixtures.
- Tabla de códigos postales: `data/geo/codigos_postales_ar.csv` (referencia estática, en el repo,
  NO en Firestore; se carga en memoria).
- El repo es la fuente; sube a Firestore por `/admin/upload-catalog` y `/admin/upload-faq`.

---

## TEORÍA / estrategia acordada (marco para lo que viene)

- **Cerrado vs abierto.** El código gana en problemas CERRADOS (fuente de verdad + chequeo
  unívoco: precio, stock, aritmética, envío, palabra prohibida). El LLM es para lo ABIERTO
  (intención en negociación enredada, compatibilidad, tono). No pedirle al código que razone lo
  abierto, ni al LLM que garantice lo cerrado.
- **Invariantes, no casos.** No enumerar casos con listas de `if` (explota, arreglás A y rompés
  B). Enforcar UN invariante por campo ("todo precio del texto = catálogo; si no, se pisa"). Los
  invariantes componen y son ortogonales; cada uno se lockea con un test en tabla.
- **Verificador por campo con safe-override** (estado del arte 2026): pisar solo el dato que
  contradice la fuente, dejar pasar el resto. Verifika ya lo hace con la plata; el plan es
  extender el MISMO patrón a cada campo cerrado que falta.
- **Cobertura:** con el 3-jul quedaron cubiertos stock/disponibilidad y FAQ numérica: la
  estimación pasa de ~70% a ~85% de las afirmaciones de hecho garantizadas (precio, total,
  envío, identidad, promesas, stock, números de política). Falta para el techo útil (~90-95%):
  guardas de salida (disclaimer, malas palabras) y validación en vivo de lo nuevo. El ~5-10%
  restante es irreducible (abierto, del LLM).
- **Diferenciador vendible:** "un bot de ventas que no puede mentir sobre precio, stock ni total
  porque el código lo garantiza". No prometer conversación impecable (es del LLM); prometer que
  no miente en los números.

## Hallazgos del BANCO de charlas vivas (5-jul) — 5 errores cazados y arreglados

La primera tanda de 8 guiones (DeepSeek real, pipeline real) encontró y se arregló:

1. **El solver ADIVINABA ids de memoria** (pidió el total con un teclado de $172.500 en vez
   del de $12.000 mostrado, y justificó inventando que el barato no tenía stock). Causa raíz:
   los [[PROD:id]] estampados (ej. de la guía determinista) no quedaban en `productos_vistos`
   si el turno no llamó tools. ARREGLADO: todo producto MOSTRADO queda en memoria con su id
   y el estado se lo muestra al solver en el turno siguiente.
2. **Stock inventado entre variantes de color** ("Tenemos el DX-110 Blanco", stock CERO): el
   ancla del verificador de stock quedaba ambigua entre Negro y Blanco y se abstenía.
   ARREGLADO: nombre completo primero, desempate por tokens, ventana hacia adelante para
   "tenemos el X" / "no hay stock del X", y la evidencia ahora incluye los productos vistos
   re-leídos VIVOS del catálogo (precio y stock actuales).
3. **Multi-destino perdía los destinos entre turnos** (re-pedía el CP de Córdoba ya cotizado).
   ARREGLADO: `ultimas_localidades` persiste en la conversación, el estado se la muestra al
   solver y calculate_total cae a esa memoria si el turno no cotizó.
4. **Descuento por transferencia calculado a mano por el solver** (salió en sombra, la cuenta
   dio bien de casualidad). Tras los arreglos el solver llama a la calculadora y el total sale
   con proof ($19.050 verificado en la re-tanda). Vigilarlo en el banco.
5. **El acople duplicaba la política** (bloque de cuotas idéntico a la prosa + gancho
   "contame qué producto" con el producto ya elegido). ARREGLADO: tema numérico cuya prosa ya
   trae TODOS los montos oficiales se saltea (`prosa_trae_valores`), y el gancho imperativo
   final también se recorta cuando la prosa ya pregunta.

**Observaciones abiertas del banco (revisar con Martín, no se tocaron):** en modo A el solver
sigue pidiendo nombre y dirección en su prosa después de captar el lead (la regla era captar
sin pedir datos; es conducta del prompt, no del cierre); el presupuesto estampado a veces sale
con el total repetido en dos líneas (cosmético); "dale, lo compro" creó lead nivel TIBIA, no
fuerte (¿confianza del interpretador baja en ese fraseo?). En UNA corrida del guion
multi-destino se vio un "Total final: $44.500" con items listados que sumaban $33.500 (el log
completo se perdió, no se pudo reconstruir si la calculadora corrió): extensión candidata del
juez = chequear que el total declarado sea la suma de los renglones del MISMO mensaje.

## Hallazgos de pruebas reales (2-jul)

- **Cero alucinaciones de PRECIO/total** en dos charlas reales largas: todos los precios, stocks
  informados coincidentes y cuentas correctas venían de la fuente. El blindaje de plata funcionó.
- **Hueco de STOCK (por acá se filtró):** el solver inventó faltantes ("DX-110 no tiene stock",
  "Zeus X no tiene stock" — falso, tenían) y upselleó a lo caro; y eligió mal "el más barato con
  stock". **BLINDADO el 3-jul** (verificador_stock + guia_compra, ver pipeline 4-bis); queda
  verificarlo en charla real.

---

## PENDIENTES (en orden de prioridad)

1. **Charla real de HUMO por WhatsApp/Telegram** (después de mergear y deployar esta rama):
   el banco ya validó el pipeline con DeepSeek real; falta solo el transporte (webhook,
   reintentos) y confirmar las asunciones del doble contra Firestore real (tarifas_envio por
   provincia, modo_cierre). Leer los eventos en logs (`interprete_libre_stock_*`,
   `interprete_libre_faq_numerica_*`, `_curada_servida`, `_faq_acoplada`, `_promesa_cuarentena`).
1-bis. **Revisar con Martín las observaciones abiertas del banco** (modo A pidiendo datos en
   prosa, total repetido cosmético, lead tibia con "dale, lo compro" — ver HALLAZGOS 5-jul).
2. **Guardas de salida (baratas):** malas palabras (blocklist + reescritura, ej. "al pedo") y
   **disclaimer legal** (aclarar que es una herramienta automática; determinista: línea fija en el
   primer mensaje + gatillo regex sobre "sos humano/quién sos/con quién hablo"). El prompt solo ya
   falló en real.
3. **Confirmar el disparo del lead** por logs (qué camino disparó: `lead_decision_via_interpretador`
   vs `cierre_gatillo_determinista_fuerte`, y ahora también `cierre_pregunta_suave` con score bajo).
4. Costo DeepSeek (varias llamadas LLM por turno), seguridad (recortar log del webhook, rotar
   tokens): pendientes de arrastre, atacar cuando toque.

**Metodología no negociable al tocar cada herramienta:** primero escribir el test que captura el
comportamiento bueno de HOY, después cambiar. El gate del CI + el test lockean contra regresión.

---

## Probar en el entorno de Claude — BANCO DE CHARLAS VIVAS (5-jul)

`pytest` corre los 217 tests offline (Python puro, catálogo+FAQ reales por la fixture
`firestore_doble` en `tests/conftest.py`, sin LLM ni Google).

**El camino VIVO también se prueba desde acá** (la DEEPSEEK_API_KEY está en el entorno web de
Claude): método acordado el 5-jul para que la primera charla real de Martín sea confirmación,
no descubrimiento. El ciclo es: batería offline verde → tanda viva verde → recién ahí charla
real. Piezas, todas en `banco_pruebas/`:

- **`charla_sim.py`**: corre una charla de punta a punta por el pipeline REAL (intérprete +
  solver DeepSeek + verificadores + cierre) sobre el doble de Firestore. Un guion por charla:
  `python3 banco_pruebas/charla_sim.py banco_pruebas/guiones/03_stock.txt`.
- **`juez.py`**: JUEZ de invariantes determinista sobre cada respuesta (reusa los detectores
  de producción contra el catálogo completo): stock contradicho, promesa prohibida, marcador
  sin estampar, precio de lista pisado, narración interna filtrada. La tanda falla sola.
- **`guiones/`**: 8 guiones que replican los errores de charlas reales (curada pura, retiro
  de local, stock, más barato, multi-destino, cierre, negaciones, acople). Son también los
  primeros tests `vivo` DE VERDAD: `tests/test_vivo_charlas.py` los corre por el pipeline y
  exige juez limpio. Correr a propósito antes de mergear cambios del camino LLM:
  `python -m pytest -m vivo tests/test_vivo_charlas.py -v`.
  **Cómo leer una marca:** el solver varía entre corridas, así que una marca del juez merece
  LEER esa charla antes de tocar código: puede ser una mentira real que el pipeline dejó pasar
  (se arregla el invariante en producción), un falso positivo del juez (se afina el juez, ej.
  la tarifa de envío pegada al producto) o una variación puntual del LLM que en la siguiente
  corrida no aparece. Verde estable dos corridas seguidas = listo para charla real.
- **El doble ahora simula el cierre REAL**: `modo_cierre: "A"` como producción y leads en RAM
  (solo se dobla el almacenamiento y el aviso al dueño). Antes el cierre era un no-op y no se
  probaba nunca.

Límites del doble que siguen: tarifas_envio por provincia sembradas como asunción
(cordoba=7500, confirmar contra Firestore real) y el transporte WhatsApp/Telegram en sí
(webhook, reintentos), que se valida con UNA charla corta de humo después de la tanda limpia.

**Desde la NOTEBOOK (Windows):** la receta completa (clon + rama nueva + venv + batería) está en
`CLAUDE.md` → "Correr la batería desde la NOTEBOOK". Mismo doble de Firestore que en el celular.
