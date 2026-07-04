# Estado del sistema — fuente ÚNICA de verdad

Este es el único documento de estado. `CLAUDE.md` tiene las reglas e instrucciones
permanentes; acá vive QUÉ es el sistema hoy. Si algo viejo contradice esto, manda esto.

**Última actualización: 4-jul-2026.** Multi-destino con tarifa REAL por destino (bug de la
última tarifa repetida, arreglado), FAQ 44/44 curada aprobada por Martín, y ACOPLE: el bloque
curado del tema consultado se pega en vertical a la prosa del solver (marcador `[[FAQ]]`
retirado). 191 tests offline en verde. Todo lo de abajo está deployado y verificado en verde
salvo lo marcado como PENDIENTE. Estrategia vigente: respuestas curadas + bloques deterministas
(el código es dueño de todo dato duro; el solver, de la prosa), acordada el 4-jul.

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

## Hallazgos de pruebas reales (2-jul)

- **Cero alucinaciones de PRECIO/total** en dos charlas reales largas: todos los precios, stocks
  informados coincidentes y cuentas correctas venían de la fuente. El blindaje de plata funcionó.
- **Hueco de STOCK (por acá se filtró):** el solver inventó faltantes ("DX-110 no tiene stock",
  "Zeus X no tiene stock" — falso, tenían) y upselleó a lo caro; y eligió mal "el más barato con
  stock". **BLINDADO el 3-jul** (verificador_stock + guia_compra, ver pipeline 4-bis); queda
  verificarlo en charla real.

---

## PENDIENTES (en orden de prioridad)

1. **Verificar en VIVO el blindaje nuevo** (stock, FAQ numérica, pregunta de cierre, multi-destino):
   charla real por WhatsApp/Telegram + leer los eventos nuevos en logs
   (`interprete_libre_stock_*`, `interprete_libre_faq_numerica_*`, `interprete_libre_guia_mas_barato`).
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

## Probar en el entorno de Claude

`pytest` corre los 153 tests offline (Python puro, catálogo+FAQ reales por la fixture
`firestore_doble` en `tests/conftest.py`, sin LLM ni Google). El intérprete y el solver (DeepSeek)
NO corren offline (van marcados `vivo`, excluidos por default); se prueban en WhatsApp/Telegram o
leyendo logs de Cloud Run.

**Desde la NOTEBOOK (Windows):** la receta completa (clon + rama nueva + venv + batería) está en
`CLAUDE.md` → "Correr la batería desde la NOTEBOOK". Mismo doble de Firestore que en el celular.
