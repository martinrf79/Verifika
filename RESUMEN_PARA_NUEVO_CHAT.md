# Estado del sistema — fuente ÚNICA de verdad

Este es el único documento de estado. `CLAUDE.md` tiene las reglas e instrucciones
permanentes; acá vive QUÉ es el sistema hoy. Si algo viejo contradice esto, manda esto.

---

## COMANDOS — cambiar de proveedor y deploy (13-jul-2026)

Contexto: el gasto de julio fue 96% Gemini, 9.65 USD, casi todo tokens de ENTRADA
del solver Gemini que reenvía el esquema de 14 tools en cada vuelta del loop.
Cloud Run inocente, 9 centavos. Golpe 1 hecho en la rama
`claude/gcloud-spending-review-it3bdg`: PERILLA ÚNICA `LLM_PROVIDER` que manda
intérprete + solver (ver regla técnica 7 de CLAUDE.md). PENDIENTE mergear a main.

**PASO 0 — ver qué variables tiene el servicio SIN exponer secretos (solo nombres):**
```bash
gcloud run services describe agente-bot --project memory-engine-v1 \
  --region southamerica-east1 \
  --format="value(spec.template.spec.containers[0].env[].name)"
```
Antes de pasar a openai, confirmar que `OPENAI_API_KEY` figura en esa lista. Si NO
está, el bot se rompe al cambiar: primero cargar la clave. Si aparece
`INTERPRETER_PROVIDER` pegada, conviene sacarla para que herede de `LLM_PROVIDER`.

**PASO 1 — deployar el Golpe 1 (sin esto, el gate no existe y el solver Gemini
corre igual aunque LLM_PROVIDER diga openai):** mergear la rama a main; el CI
gateado testea y deploya a `agente-bot`. O `./deploy.sh` desde `~/verifika`.

**PASO 2 — cambiar el proveedor vivo (una sola variable):**
```bash
# Pruebas / ahorro: intérprete + solver en gpt-4o-mini barato
gcloud run services update agente-bot --project memory-engine-v1 \
  --region southamerica-east1 --update-env-vars LLM_PROVIDER=openai
# si PASO 0 mostró INTERPRETER_PROVIDER pegada en gemini, sumar:
#   --remove-env-vars INTERPRETER_PROVIDER

# Volver a producción Gemini
gcloud run services update agente-bot --project memory-engine-v1 \
  --region southamerica-east1 --update-env-vars LLM_PROVIDER=gemini

# Probar Groq (necesita GROQ_API_KEY en el servicio)
gcloud run services update agente-bot --project memory-engine-v1 \
  --region southamerica-east1 --update-env-vars LLM_PROVIDER=groq
```

**TRADE-OFF MEDIDO (13-jul, mismos bancos):** intérprete gpt-4o-mini 87% en
multiturno adversarial vs Gemini 100%; en casos sueltos empatan 29/29. Las 3
fallas de gpt mini: ironía leída como compra, referencia al histórico,
dato-no-compra. Si se quiere el solver barato pero el intérprete fuerte, override:
`LLM_PROVIDER=openai` con `INTERPRETER_PROVIDER=gemini`.

**TOPE DE GASTO:** poner presupuesto con alerta en Billing → Presupuestos y
alertas (5 USD), red para que no se repita el susto.

**Última actualización: 13-jul-2026 — TANDA DE ROBUSTEZ (orden de Martín:
prueba-error hasta robusto). MEMORIA DEL SOLVER + 3 FLACOS CAZADOS EN BANCO
ADVERSARIAL + GUÍA DE VENTA 16 TEMAS. ARRANCAR ACÁ.**

Corrida de validación 13-jul (todo por el pipeline VIVO del sim, Gemini
solver conduciendo):
- Batería viva: 1ª corrida 30/33 (03_stock, 04_mas_barato, 15_multipregunta
  marcaron y pasan al repetirlos = variación del LLM); 2ª corrida COMPLETA
  con los fixes adentro: **33/33 LIMPIO**. Guiones nuevos 34-37 también
  verdes por el arnés (4/4). Total del día: 37/37 con los fixes.
- Interpretación medida HOY, mismo día, mismos bancos:
  gpt-4o-mini (prod): suelto 29/29, multiturno 20/23 (87%, arriba del piso).
  Gemini: suelto 29/29, multiturno 23/23 = 100%.
  Las 3 fallas de gpt mini: guía dato-no-compra, ironía leída como compra,
  referencia al histórico. DECISIÓN ABIERTA con Martín: pasar el intérprete
  a Gemini (hoy mide mejor y unifica proveedor con el solver; riesgo: todo
  el turno depende de un solo proveedor, y gpt mini queda de fallback por
  config si hiciera falta volver).
- 478 tests offline en verde.

LO NUEVO CABLEADO (13-jul, OK directo de Martín "corrígelo directamente"):
1. **Bloque MEMORIA DE LA CHARLA del solver** (`solver_gemini._bloque_memoria`):
   el solver veía SOLO los últimos 3 turnos crudos; ni resumen de memoria
   larga, ni producto anotado, ni carrito, ni destino sticky, ni criterio,
   ni datos del cliente. Ahora todo eso entra como contexto (con la orden de
   que números salen de las tools). Verificado vivo: destino dado en turno 1
   cotizado bien en turno 6 (guion 37). Locks test_solver_memoria.py.
2. **Verificador de stock, ancla por tokens con límite de palabra**: 'model'
   (Glorious Model O) matcheaba por substring adentro de 'modelo' y acusaba
   sin_stock_falso a un producto AUSENTE del texto (falso positivo visto en
   banco). Lock en test_stock.py.
3. **Pendiente de categorías de memoria no se sella con otra categoría
   nombrada**: '¿un ssd externo me sirve?' dejaba pendiente (1, ssd) y 'el
   más barato de esos auriculares' sellaba un pedido de SSD que nadie pidió.
   `categorias_nombradas` nueva en guia_pedido + descarte del pendiente
   (evento `interprete_libre_pendiente_descartado`). Lock test_guia_pedido.
4. **Prompt del solver endurecido**: compatibilidad con consolas/equipos y
   tipo de conector SOLO si la ficha lo dice ('cable USB ideal para la Play
   5' salía sin respaldo; ahora responde honesto que la ficha no lo
   especifica). Y el acople NO re-pega una curada de texto puro cuando el
   bloque nace del query_faq que el solver mismo llamó (salía 'decime qué
   producto mirás' después de haberlo detallado).
5. **Guía de venta en prosa 6→16 temas** (`guia_venta_prosa.py`): notebook,
   memoria_ram, ssd_almacenamiento, componentes_pc (método de cruce de
   fichas), auriculares, monitor, perifericos_conexion, sillas_gamer,
   streaming, tablet. Cero números (invariante con test). Match por ALIAS
   de palabra antes del difuso ('ram' caía en streaming, 'router' en mouse).
   Es la semilla para preguntas técnicas/compatibilidad de la demo; para un
   cliente real se llena con la prosa del cliente.
6. **Guiones nuevos 34-37** (memoria+ancla+ruido, compatibilidad técnica,
   negación+cambio de decisión ida y vuelta, memoria de destino lejano):
   las charlas adversariales del 13-jul lockeadas al banco vivo.

PENDIENTE inmediato al retomar: resultado de la 2ª corrida completa de la
batería (medir consistencia de los 3 flakes), decidir intérprete
(gpt-4o-mini vs gemini) con Martín, y el merge a main (CI gateado deploya).

---

**12-jul-2026 (3ª tanda) — SOLVER GEMINI CABLEADO
AL CAMINO VIVO (conservador) + verificador de stock reparado.**

CABLEADO (OK de Martín para verificador + cableado, con él offline):
- **`app/core/solver_gemini.py`** (NUEVO): el solver de producción. Loop de
  function calling con las tools reales del sistema + la guía de venta; el
  modelo llama, el código ejecuta, devuelve `(respuesta, meta)` con
  `meta['tools_called']` en el formato que consume TODO el downstream
  (evidencia, verificadores, envío, presupuesto, carrito, cierre, memoria).
  Ante error/timeout/sin-clave devuelve `(None, None)` y cae al compositor.
- **`app/core/guia_venta_prosa.py`** (NUEVO): la prosa de venta de criterio
  (uso, comparativa, marcas, durabilidad, compatibilidad), tool
  `consultar_guia_venta`. Semilla; se extiende sumando texto, no tocando código.
- **`interprete_libre.py`**: en la rama general (no curada, no pedido sellado)
  el solver es PRIMARIO; el selector+compositor quedan de RED. Cuando la
  respuesta viene del solver (`_via_solver`), las guardas de FORMATO del viejo
  solver libre (reanclar más barato/producto, forzar A/B, forzar opciones) NO
  corren: peleaban con la prosa natural de Gemini y la reescribían aunque el
  dato fuera correcto. Los verificadores REALES (plata, stock, promesas, FAQ)
  siguen corriendo igual como red.
- **Verificador de stock**: guarda de variante por COLOR (reparado el falso
  positivo real: "KB-110X Blanco... el negro sin stock" ya no acusa al Blanco).
  4 locks nuevos en tests/test_stock.py.

PROBADO por `process_message` en el sim (pipeline vivo entero, sin crashes):
el solver conduce el caso general (ej "mouse más barato": sale la prosa de
Gemini con el dato real, sin clobber). CI no tiene GEMINI_API_KEY -> los tests
offline caen al compositor y pasan igual.

**AMPLIADO A "REAL = BANCO" (opinión de Martín, 12-jul): el solver conduce
TODOS los casos salvo el pedido SELLADO por la calculadora.** Corre primario
antes de las curadas/opciones; sólo cede cuando el código ya selló un total
(garantía de plata dura). Corrección importante: mi reparo del "Uruguay" era al
revés. Probado por REST/sim: el solver conectado a las tools contesta el
exterior BIEN ("envíos únicamente dentro de Argentina, no llegamos a
Montevideo", vía query_faq envio_exterior); la respuesta engañosa "llegamos a
todo el país" venía de la CURADA vieja, no del solver. O sea el solver
conectado se porta MEJOR que la curada. La tabla de envío YA existe (16.164
localidades en cotizar_envio, no 1.200): localidad/CP -> zona -> costo; el
solver la consulta sola.

**BUG cazado y arreglado al ampliar (verificador.py):** el solver escribe el
stock en prosa ("quedan 11 unidades en stock") y 'quedan' es verbo de precio,
así que el verificador de plata tomaba el 11 como precio y lo autocorregía a
$8.500 dejando "11.11 unidades". Fix: un número seguido de
unidades/en stock/disponibles es CONTEO, no plata (`_UNIDAD_CANT_RE`). 2 locks
nuevos en test_verificador.py; los 36 tests de plata siguen verdes.

**Probado end-to-end por process_message (pipeline vivo, sim):** el solver
conduce mouse más barato, factura, Uruguay, razonamiento Razer (consulta la
guía), bot; el multiproducto usa el total sellado del código; cero tracebacks;
stock sin corromper. Cuando la respuesta viene del solver, las guardas de
formato del viejo solver libre no corren; los verificadores reales sí.

**DEPLOYADO (OK directo de Martín, 12-jul): run 109 de deploy.yml VERDE**
(test gateado + deploy a Cloud Run agente-bot, commit 1a1053d). El camino vivo
ahora es: solver Gemini primario salvo pedido sellado, con el compositor de red
y los verificadores como filtro. OJO: el solver se activa en prod SOLO si la env
GEMINI_API_KEY está cargada en el servicio agente-bot; si no, cae al compositor
(comportamiento previo). Validación en red PENDIENTE: Martín manda un WhatsApp y
se leen los logs de Cloud Run (evento `interprete_libre_solver_gemini_ok` =
el solver condujo; si no aparece, revisar la env de la clave). El CI no tiene la
clave, por eso sus tests offline caen al compositor y pasan.

---

**12-jul-2026 (2ª tanda) — SOLVER GEMINI QUE LLAMA LAS HERRAMIENTAS EL MISMO.**

DECISIÓN de Martín (12-jul): probar a Gemini como SOLVER con function
calling REAL, que use TODAS las herramientas (search, ficha, FAQ,
calculadora, envío). La tesis: si el modelo maneja bien las tools, borra un
montón de configuración porque el código no tiene que pre-armar cada caso; y
sigue atado a la fuente porque el DATO sale de la tool, no del modelo. Se
prueba en el banco; si anda, se piensa deploy.

**Banco nuevo `banco_pruebas/banco_gemini_tools.py`:** Gemini recibe las
MISMAS tools del sistema (`app.core.tools.get_tools_schema`), decide cuál
llamar, el CÓDIGO la ejecuta contra Firestore/FAQ/calculadora deterministas y
le devuelve el resultado, en loop, hasta que redacta. Reporta la SECUENCIA de
tool calls (cómo las usa) y mide la salida con los verificadores reales.
- **Resultado: 3 corridas → 9/9, 9/9 y 8/9 LIMPIO** (el único MARCA fue un
  desliz de stock que el filtro cazó). Gemini usa las tools bien y en orden
  sensato: search→cotizar_envio→calculate_total con envío; query_faq para
  política; recommend_product en la objeción.
- **Gana el caso que la arq de fragmentos erraba:** el SPLIT multiproducto.
  Gemini arrastró el destino Rosario del turno previo, llamó
  cotizar_envio(Rosario) y calculate_total con items+envío+reparto de pago, y
  dio el total final CON envío. La arq de fragmentos (generador_v2) perdía el
  envío ahí porque la localidad no persiste en `localidades_envio` (agujero
  del pipeline vivo, aguas arriba, NO tocado).
- **Detalle técnico clave (para que no se repita):** Gemini 3 por el endpoint
  compat de OpenAI EXIGE que se le reenvíe la `thought_signature` que genera
  en cada tool_call (viene en `tool_call.extra_content.google`); sin eso el
  2º request tira 400 "missing a thought_signature". El banco ya la preserva.
  `reasoning_effort: none` NO la desactiva en `gemini-flash-latest`.
- **Residual honesto (por eso los filtros quedan):** Gemini a veces adorna en
  prosa datos NO numéricos que el verificador de plata no chequea (ej. llamó
  "mecánico" a un teclado, dijo "despachamos desde Buenos Aires", "garantía
  mínima 6 meses"). No son inventos de PLATA, pero son afirmaciones blandas
  que sólo cazan los filtros de salida (stock/promesas) o una curada. Ese es
  el trade-off a vigilar antes de cablear.

**Ajustes menores al generador_v2 (banco) de la 1ª tanda de hoy, quedaron:**
la poda de prosa ya NO descarta un fragmento por nombrar un producto REAL del
universo (sólo descarta si trae un dígito), así una pregunta de consejo no
pierde la respuesta razonada; y el cierre enlatado no se pega si la prosa ya
cerró con pregunta (fin del doble cierre). Son mejoras a un módulo de banco,
no al camino vivo.

**TOKENS Y COSTO (pedido de Martín, el banco ya lo mide por mensaje):**
promedio ~12.500 tokens por mensaje, ~$0,0045, proyección 1000 mensajes
~$4,5 (tarifa aprox editable, ajustar con la factura real). CLAVE: casi todo
es INPUT (169k in vs 5k out en 14 mensajes) porque cada vuelta del loop de
tools REENVÍA el schema completo + los resultados; ahí está el gasto, no en la
redacción. Optimizable recortando el schema y los resultados que se reenvían.

**FUENTE DE PROSA DE VENTA (para las de razonamiento):** el banco expone una
tool LOCAL `consultar_guia_venta` con prosa semilla (uso, comparativa, marcas,
durabilidad, compatibilidad, sin números). Gemini LA CONSULTA sola antes de
opinar (verificado: llama consultar_guia_venta→search_products→responde). Para
un cliente real esa prosa sería mucho más extensa y por producto; acá es
semilla de prueba. NO toca el catálogo real ni el camino vivo.

**RESIDUALES REPRODUCIBLES que cazan los filtros (dato de config):** (a) en
preguntas de presupuesto Gemini hace la resta de cabeza ("te sobran $5.500")
aunque se le dice no calcular → el verificador de plata lo marca; (b) a veces
ofrece "retiro en local" que no existe → la guardia de promesas lo marca; (c)
algún desliz de stock. Todos los caza la red; se tapan con prompt más duro o
curada. La atadura garante el DATO, no la prosa blanda: por eso el filtro se
queda.

**PENDIENTE para decidir cablear el solver-con-tools a producción:** correr
contra los 33 guiones reales + charlas reales de Martín, varias corridas,
medir latencia (el loop de tools son varias llamadas), recortar el input que
se reenvía (costo), y definir qué residual blando se tapa con curada/filtro.
El camino vivo sigue en el compositor/selector (gpt-4o-mini); NADA de esto
está cableado todavía. Próximo acordado con Martín: agregar prosa donde haga
falta y DEPLOY para probar en red.

---

**12-jul-2026 (1ª tanda) — ARQUITECTURA DE FRAGMENTOS EN EL BANCO
(generador de fragmentos con Gemini).**

DECISIÓN DE ARQUITECTURA acordada con Martín (12-jul), en construcción y
prueba EN EL BANCO, NO cableada a producción todavía:

**El problema de fondo:** hoy el CÓDIGO redacta el mensaje final (selector +
compositor); cada pregunta nueva es un parche. El intento viejo (DeepSeek de
solver redactando libre + verificadores corrigiendo) se abandonó el 8-jul
porque corregir texto libre no tiene fondo. La síntesis acordada NO es ni una
ni otra.

**La arquitectura nueva (`app/core/generador_v2.py`, en la rama):** UNA
llamada a Gemini compone la respuesta como FRAGMENTOS atados por enum
(structured outputs). El modelo elige QUÉ, en qué ORDEN y con qué TONO
(prosa libre de venta), pero JAMÁS escribe un dato: emite referencias
(producto, opciones, calculo, presupuesto, ficha, faq, envio, cierre) y el
CÓDIGO estampa cada número/spec desde la fuente. La prosa se poda de
cualquier dígito/nombre colado. Garantía por CONSTRUCCIÓN (prevenir), no por
corrección.
- El ENUM se arma SOLO en cada turno desde Firestore (productos, temas de
  FAQ, campos de ficha): automático, sin intervención humana. Cargar un
  producto/FAQ nuevo a Firestore lo suma al enum solo. Yo configuro el
  MECANISMO una vez, no el contenido.
- Lo CERRADO al código: `presupuesto_precalculado` calcula el total cuando
  el pedido es determinable (cantidades+criterio, o carrito+total/split); el
  modelo solo lo POSICIONA. Así el total no depende de que el modelo lo arme
  bien (la inconsistencia que anticipó Martín y que se vio en el banco).
- El universo de productos es ACOTADO (mostrados+carrito+baratos/intermedio
  de las categorías en juego, capado a 16): enum chico y siempre real.

**Estado de la prueba (`banco_pruebas/banco_arquitectura_nueva.py`):** 9
áreas (venta, multiproducto+envío, ficha mixta = el ejemplo de Martín con
procedencia/garantía/material reales, FAQ, envío, objeción, pregunta
abierta, desconfianza, split) → 9/9 LIMPIO en verificadores, 2 corridas
seguidas, prosa MUY superior al código con datos atados. Gemini 29/29 y
23/23 en los bancos de interpretación. PENDIENTE de pulir: envío en el
split, doble cierre cosmético; y lo grande: correr contra los 33 guiones
reales + más casos + varias corridas hasta CONSISTENTE antes de decidir
cablear a producción. Herramientas de diagnóstico: `exp_gemini_libre.py`
(muestra el agujero del verificador con catálogo grande) y
`banco_gemini_solver.py` (Gemini libre, para contraste).

**Método acordado:** queda en el banco hasta pasar todos los casos en varias
corridas; recién ahí se cablea y deploya. Gemini ya operativo
(`GEMINI_API_KEY` bien cargada, modelo `gemini-flash-latest`, thinking off);
producción sigue en gpt-4o-mini. FAQ en Firestore real: 46 (verificado).

---

**11-jul-2026 (noche) — TODO EN PRODUCCIÓN
(deploys 99-104 verdes). SELECTOR v2 con la primitiva de plata: fin del
parche-por-regex para las acciones de datos.**

0. **SELECTOR v2 (la mejora "en serio" que pidió Martín).** El menú suma
   `calcular_pedido` con argumentos estructurados atados por schema: items
   (el pedido completo como debe quedar), destinos y reparto de pago. El
   ejecutor (`guia_pedido.ejecutar_calculo_plan`) valida TODO contra la
   fuente antes de sellar (nombres→ids todo-o-nada, porcentajes que suman
   cien, destinos que resuelven, proofs de cada tramo); algo no valida →
   cascada. Las combinaciones nuevas (editar + destino + split en un
   mensaje) las resuelve UN camino general, no un regex por caso. Guion 32
   lo lockea. Las tres charlas reales de Martín del 11-jul quedaron como
   guiones 30, 31 y 32; batería completa: **32/32 guiones con juez limpio,
   459 tests offline**.
0-bis. **Fixes de las charlas reales del 11-jul (todos deployados):**
   reparto de envíos por grupo con proof por tramo (10:42); split de pago
   sobre el pedido vigente + error de PLATA cazado (es_mercado_pago no
   reconocía 'mercado_pago' y descontaba el 10% a la mitad de MP) (17:22);
   'modalidades de pago' en keywords; el enlatado de envío no se acopla
   con destinos ya cotizados; 'va todo junto a X' parsea el destino.
   GEMINI OPERATIVO: la clave AQ. quedó activa (modelos Gemini 3; los 2.5
   no aceptan usuarios nuevos), thinking apagado para todos los que
   razonan, default `gemini-flash-latest`; bancos con Gemini intérprete:
   29/29 y 23/23 = 100%. Falta solo renombrar la env `GEMINI_APY_KEY` →
   `GEMINI_API_KEY` para activarlo sin puente.

1. **SELECTOR construido (la arquitectura del 10-jul, viva).** `selector.py`:
   una llamada LLM (gpt-4o-mini, schema estricto, también corre en Gemini)
   ve lectura del intérprete + estado sellado completo y elige 1-3 secciones
   del MENÚ (ficha, opciones, más barato, intermedio, envío, faq, movida,
   rechazo, not_found, preguntar). El código arma cada sección desde la
   fuente; sin respaldo se saltea; error/timeout → cascada determinista de
   red (mismo patrón que el redactor). La movida emocional (B17/B18/B19)
   manda SOBRE el plan.
2. **ANCLA `producto_anotado`** (falla madre del banco): "me gusta X,
   anotalo" persiste el ancla; "el que te dije al principio" resuelve y
   sella el pedido con ese id. Verificado vivo: guion 28 cierra con el M170
   anotado ($19.500 con envío), no con el más barato. El ancla viaja como
   contexto del intérprete; la limpia solo una negación que la NOMBRA.
3. **Más mejoras de la tanda 11-jul, todas con test y verificadas vivo:**
   criterio INTERMEDIO (enum + escalón arriba del mínimo; "no lo más barato"
   ya no arma los más baratos); búsqueda certificada del candidato único
   (HyperX nombrado de cero → ficha o A/B de variantes); not_found honesto
   ("tenés joysticks" → no derecho + categorías); rechazo reconocido y
   edición de carrito con recálculo sellado ("sacalo"); asignación parcial
   de destino que NO pisa el pedido (cotiza todos los destinos CON proof);
   destino dado cotiza sin keyword ("va todo a San Francisco"); filtro de
   pronombres ("a donde te dije" no es localidad); sellos 5-6 del redactor
   (sin saludo a mitad de charla, sin frase cortada); guarda del más barato
   solo con criterio del TURNO y jamás sobre pedido sellado; una objeción
   B4/B5 no deja criterio sticky; reparación determinista del JSON truncado
   del intérprete (whitespace-runaway de gpt-4o-mini: banco 26/29 → 29/29,
   disparaba en 8 de 29 casos).
4. **Gemini listo para probar**: el schema estricto ya se manda con provider
   gemini y el default es 2.5-flash. FALTA la clave: la env está mal
   (`GEMINI_APY_KEY`, valor inválido tipo `AQ.`); cargar una AIza real de
   aistudio.google.com como `GEMINI_API_KEY` y abrir sesión nueva.
5. **Firestore real verificado por REST** (service account claude-lector):
   880 productos exactos, FAQ ok, tarifas reales coinciden con el doble
   (córdoba 7500), `modo_cierre` sin doc → corre default "A" del código.
6. **Curadas de venta B25-B30 redactadas** (compatibilidad, reserva/seña,
   edición de pedido, cambio de destino, split, estado del pedido) en
   BORRADORES_CURADAS_VENTA.md, PENDIENTES DE APROBACIÓN de Martín, sin
   cablear.
7. **BATERÍA COMPLETA GPT-4 mini (11-jul, tarde): interpretación 29/29 =
   100% y los 29 guiones de punta a punta con juez limpio.** 146 turnos:
   CERO fallbacks "no te entendí", el selector eligió en 74 turnos (la
   cascada cubrió el resto), los sellos del redactor rechazaron 20
   redacciones (salió compositor puro, nunca dato falso). La batería cazó
   y se arregló un bug de PLATA: el proof del split de pago no respaldaba
   el envío y el VERIFICADOR "autocorregía" $6.000 correcto a $5.000 de la
   FAQ; el proof ahora respalda renglones, subtotal y extras.
8. **Fuente de verdad ampliada (orden de Martín):** faq.json pasa a 46
   temas (nuevos: teclado_mecanico_membrana y mouse_dpi, conocimiento sin
   dígitos; reservas con keywords reales "me lo guardás"). B31 DESPEDIDA
   nueva ("no quiero nada más" → cierre cordial). PREGUNTA SIN FUENTE:
   lo que ninguna sección responde ya no cae a "no te entendí": honesto
   "no lo tengo confirmado" + derivación, y el evento
   `compositor_pregunta_sin_fuente` en el log es la mina de curadas
   nuevas. PENDIENTE DE MARTÍN: cargar la FAQ 46 a Firestore tras el
   merge (`.venv-shell/bin/python scripts/crear_cliente.py cargar_faq
   --tienda_id verifika_prod --faq data/clientes/verifika_prod/faq.json`).
   Conducta pendiente conocida: criterio mixto por categoría ("teclados
   intermedios y mouse baratos") no se arma en un solo total; B25
   compatibilidad podría usar el producto anotado en vez de re-preguntar;
   el selector a veces suma una sección de más (inofensivo).

---
1. **La arquitectura decidida:** una llamada LLM (SELECTOR/planificador)
   recibe la lectura del intérprete + el estado sellado (pedido vigente,
   destinos, presupuesto) + contexto completo de las áreas, y su ÚNICA salida
   posible, atada por enum/schema, es elegir del MENÚ: curadas de texto o
   primitivas de datos (calculadora, cotizador, reagrupar pedido por destino,
   re-servir presupuesto). El modelo VE todo para elegir bien; JAMÁS reescribe
   un dato: el dato nace de la herramienta o del bloque. Regla de las dos
   mitades: pregunta de TEXTO → curada; pregunta de ESTADO/CÁLCULO →
   primitiva; PROHIBIDO tapar cálculo con texto enlatado. El filtro de salida
   (verificadores/juez, Martín lo llama "Benifica") queda como fiscal final:
   la atadura garantiza salida EN el menú, no la elección correcta.
   Evidencia que la motiva: charla real 20:07-20:14 ("armame bien con cada
   cosa que te pedí con cada localidad" x3 → el sistema cayó al flujo genérico
   e inventó un envío a Corrientes; son turnos de razonamiento sobre estado,
   sin flujo escrito posible).
2. **Primer paso del build: AUDITORÍA de cobertura.** Cada caso difícil del
   repo (CATEGORIAS_PREGUNTAS_VENTA.md, guiones, bancos) y de las charlas
   reales, marcado como curada-o-primitiva; lista de huecos con textos
   propuestos PARA APROBACIÓN DE MARTÍN (las curadas las aprueba él).
3. **Gemini 2.5 Flash** (clave en env GEMINI_API_KEY): probarlo como selector
   y solver (banco de interpretación + multiturno). Su atadura dura requiere
   adaptar el schema estricto que hoy solo corre con provider openai
   (interpretador._llamar_llm); Gemini tiene generación restringida propia.
4. **Acceso directo a producción (solo lectura):** clave de service account
   en env `GCP_SA_KEY_B64` (base64). Decodificarla al SCRATCHPAD (nunca al
   repo), y usar REST con `REQUESTS_CA_BUNDLE=/root/.ccr/ca-bundle.crt`:
   logs → POST logging.googleapis.com/v2/entries:list (filtro service_name
   agente-bot); Firestore → firestore.googleapis.com REST. Cuenta:
   claude-lector@memory-engine-v1 (logging.viewer + datastore.viewer). Sirve
   para leer charlas reales AL INSTANTE y para correr el banco contra el
   Firestore REAL (lecturas reales, escrituras al doble en RAM: pendiente
   cablearlo como modo del banco). Además sigue la ventana automática de
   diagnostico.yml cada 6h (3:17/9:17/15:17/21:17 ART).
5. **Método que manda (acordado tras la charla honesta del círculo):** los
   bancos solo demuestran fallas, la única prueba es el tráfico real; se toca
   código SOLO atado a una falla vista en charla real; toda charla real de
   Martín se lockea como guion del banco.
Pendientes menores arrastrados: grupos_envio (qué item va a cada destino),
"no es lo que pregunté" (leído como despedida), "colores distintos" ignorado,
doble pregunta de cierre cosmética, evento save_conversation_kwargs_desconocidos
en logs (mirar), ADMIN_TOKEN con default público en main.py (pisarlo con
secreto).

---

**10-jul-2026 (noche) — MULTI-DESTINO + ACCESO DIRECTO
A PRODUCCIÓN.** La segunda charla real del día (15:16, tres destinos) cobró UN
envío: arreglado de punta a punta. `cotizar_destinos_del_mensaje` ahora corre
en el camino SELLADO (cubre "será enviado a X"), calculate_total cobra una
tarifa por destino (ya sabía), y un destino AMBIGUO (Isla Verde existe en 3
provincias) no se calla: el mensaje sellado pide la provincia
(`pregunta_destinos_pendientes`, completitud). Verificado con la charla real
como guion 27: "Envio (3 envios): $19.500" y juez limpio. Locks en
`tests/test_multidestino.py`. PENDIENTE del multi-destino fino: agrupar QUÉ
item va a cada destino (campo `grupos_envio` del intérprete, para el envío
gratis por destino exacto y el detalle por grupo).
**ACCESO DIRECTO (10-jul): Claude tiene clave de service account de SOLO
lectura (`claude-lector@memory-engine-v1`, roles logging.viewer +
datastore.viewer) para leer logs y Firestore reales por REST al instante. La
clave NO vive en el repo (se pega por chat al inicio de sesión o via entorno);
se revoca con `gcloud iam service-accounts keys list/delete`. Además sigue la
ventana automática de `diagnostico.yml` cada 6h. DIAGNÓSTICO por logs de la
charla 15:16: corrió con el código PREVIO a los fixes (deploy 16:4x), el
intérprete dio pedido vacío conf 0.5 y el flujo salió del regex de categorías
con destinos=1 — consistente con lo arreglado.**

---

**10-jul-2026 (tarde) — NIVEL 2 DE LA ESCALERA: REDACTOR
con sellos mecánicos, OK de Martín.** La ESCALERA acordada (contingencia de
redacción, decidida ANTES de necesitarla, para que ningún chat futuro rediscuta
arquitectura): nivel 1 compositor puro; nivel 2 (VIVO ahora) el código arma los
bloques sellados y el modelo escribe SOLO la prosa de unión; nivel 3 (si el 2
no alcanza) el modelo propone un PLAN de bloques y el código valida y renderiza.
En ningún nivel el texto crudo del modelo viaja al cliente; degradación siempre
hacia abajo: el peor caso es un mensaje soso, nunca un dato falso.
- **`redactor.py`**: con 2+ bloques del compositor, una llamada LLM cose la
  prosa usando marcadores [[B1]]..[[Bn]]; el código estampa los bloques reales.
  Sellos todo-o-nada: marcadores exactos y en orden, prosa sin dígitos ni
  nombres de producto, tope de largo; violación → sale el compositor puro.
  Lockeado en `tests/test_redactor.py` (8 tests).
- **Multi-envío en el intérprete**: campo `destino` por renglón del pedido
  (plano, no anidado: Firestore prohíbe listas anidadas) + instrucción con el
  ejemplo real de Martín (Carlos Paz / Villa María / Río Tercero). El código
  que CONSUME el destino (cotizar por grupo) está pendiente.
- **Bancos de interpretación**: DeepSeek v4-flash 29/29 (100%) en casos sueltos
  y 23/23 (100%) en el banco multi-turno nuevo
  (`banco_pruebas/banco_interpretacion_multiturno.py`, 6 charlas de 3-4
  turnos); GPT-4o mini (prod) 22/23 (96%: leyó "se me rompió el mouse,
  necesito algo ya" como compra). Cambio de intérprete a DeepSeek: decisión
  ABIERTA (trade-off: fuera de OpenAI no hay schema estricto a nivel token,
  queda el parseo validado + redes).
- **Ventana de producción**: `diagnostico.yml` corre SOLO cada 6h (3:17, 9:17,
  15:17 y 21:17 hora argentina) volcando eventos INFO de las últimas 7h;
  Claude LEE esas corridas por la API de GitHub (no puede dispararlas: 403).
- **376 tests offline + 25 vivos con juez limpio (DeepSeek punta a punta).**
MÉTODO acordado (10-jul, tras la charla honesta del círculo): los bancos solo
demuestran fallas, nunca éxito; la única prueba es el tráfico real. Prohibido
tocar código salvo atado a una falla vista en charla real, de a una. Pendiente:
prueba real de Martín por WhatsApp del nivel 2 + leer los logs de la ventana.

---

**10-jul-2026 — LIMPIEZA GRANDE (orden directa de Martín):
se borró todo el código muerto que dejó el compositor.** El diagnóstico fue que
los "errores infantiles" son plomería entre capas acumuladas, así que se trazó el
camino vivo desde el webhook y se eliminó todo lo que no se ejecuta:
- **Módulos borrados de `app/core/`** (nadie los llamaba en el camino vivo):
  `certificador.py` (la identidad la garantizan la reconciliación por nombre +
  el enum del intérprete + el estampado; ojo, la regla 0 de CLAUDE.md sigue
  nombrándolo, pendiente de ajuste con Martín), `divergencia.py` (el chequeo de
  producto quedó inline en la guarda), `memoria_ref.py`, `guia_venta.py` (los
  briefs iban a un solver que ya no corre; las movidas viven en el compositor,
  constante `_MOVIDAS_FIJAS`), `rescate_toolcall.py`.
- **`agent.py` quedó reducido a cliente LLM compartido**: se borró `run_agent`
  (el solver libre) y `_call_llm`. Quedan `_get_client`, `modelo_solver`,
  `_get_schema` y `_build_system_prompt`, que usan la guardia, la memoria larga
  y el diag de latencia.
- **`interprete_libre.py` sin plomería muerta**: se borró `mensaje_enriquecido`
  (se armaba con briefs y guías en 5 lugares y NO lo consumía nadie desde que
  el solver murió), `_PROMPT_LIBRE`, `_schema_acotado`, `_guia_para_solver` y
  la medición de divergencia. Las guardas y verificadores siguen todos vivos.
- **Flag muerta `MODO_LIBRE_TOOLS` retirada** de config.py (regla 2-bis).
- **`bloque_para_solver` retirado** de estado_venta (solo lo usaban tests).
- **Raíz y scripts**: se borraron los arneses viejos de la raíz (arnes_*,
  correr_molino_*, 13 guiones sueltos, ver_*.py, pruebas/ entera) y ~75 scripts
  de experimentos (banco_*, bench_*, prueba_*, dbg_*, ping_*, probe_*...). En
  `scripts/` quedan SOLO los 7 operativos: crear_cliente, cargar_firestore,
  cargar_tarifas_envio, borrar_productos_tienda, generar_embeddings,
  registrar_whatsapp, setup_test_env.sh. El banco vigente es `banco_pruebas/`.
- **Batería: 368 tests offline en verde** (los ~39 que faltan respecto de 407
  eran tests de los módulos muertos, borrados con ellos).
PENDIENTE inmediato: mergear a main con OK de Martín (CI gateado deploya) y la
charla real de humo. Diagnóstico banco-vs-real y opciones de modelo (DeepSeek
V4 Pro sin thinking) charladas el 10-jul, decisión abierta.

---

**9-jul-2026 (tarde) — DOS INTÉRPRETES DEL CRITERIO +
curada que tapaba las categorías.** Charla real de Martín: pidió "4 notebooks,
3 teclados y 5 mouse... dame el precio con envío", eligió "Lo mas eco" y el bot
respondió la pregunta boba "¿qué producto estás mirando?". Dos causas raíz:
1. **"Lo mas eco" no lo cazaba el regex del código** (solo cubría barato/
   económico). Solución acordada con Martín: SEGUNDO intérprete. El LLM ya corre
   cada turno; se le agregó el campo `criterio` al schema estricto (entiende
   "eco", "lo más conveniente", abreviaturas). `concordancia_criterio` cruza los
   dos: ambos coinciden → se arma; divergen → se CONFIRMA con pregunta corta
   ("¿te armo el total con los más baratos?"), nunca sellar un total dudoso ni la
   pregunta boba. Un "sí" del turno siguiente cuenta como coincidencia (flag
   `criterio_confirmar_pendiente`). `criterio_cliente` sticky ahora lo alimentan
   los dos.
2. **La curada de envío tapaba el pedido por categorías** (causa de fondo que el
   banco no veía por variación del LLM). "...dame el precio con envío" servía la
   curada standalone de envío y salteaba las opciones por categoría; el pedido
   pendiente nunca se persistía, así que "Lo mas eco" del turno siguiente no
   tenía a qué engancharse. Fix DETERMINISTA en `servir_curada`: con pedido en
   juego (campo `pedido` del intérprete o cantidades por categoría en el mensaje)
   NO se sirve enlatado, lo maneja el flujo de pedido. Además el guard
   `_forzar_opciones_si_presupuesto` ya no pisa una respuesta que compuso el
   código (mi confirmación decía "presupuesto" y la confundía).
Verificado con el guion 25 (la charla real, textual): turno 1 las 3 categorías
con stock + destinos, turno 2 la confirmación corta, turno 3 el total completo
sellado $2.850.500 con envío gratis. Juez limpio. Banco de interpretación 29/29
(3 casos nuevos: "lo mas eco", "mandame lo mas conveniente", "los mas baratos").
407 tests offline. Pendiente: correr la suite vivo entera y mergear a main.

---

**9-jul-2026 — COMPOSITOR (decisión de Martín, "hacelo").**
Cambio de arquitectura del camino vivo: **el modelo NUNCA MÁS le escribe al
cliente.** Una sola llamada LLM por turno (el INTÉRPRETE con Structured Outputs
estricto) devuelve solo DATOS: intención, producto resuelto, pedido atado por
enum. El CÓDIGO (`app/core/compositor.py`) compone el 100% del texto de salida
desde plantillas y curadas aprobadas con los números sellados: ficha, opciones
por categoría, más barato, envío cotizado, FAQ curada, movidas B fijas, fallback
cordial fijo. `agent.run_agent` (el solver libre) quedó FUERA del camino vivo;
los verificadores y guardias siguen atrás como red, pero ya no hay prosa libre
que corregir. Muere la clase entera de errores de "corregir al solver".
Evidencia antes de tocar main: **24 guiones vivos limpios con juez (incluido el
24, la charla real de Martín, con la curada de confianza en el turno 2), 399
tests offline, banco de interpretación 26/26 = 100%** (tanda 2 completa: "sacale
uno" edita el pedido, "el segundo" resuelve ordinal, "ponele que sí" confirma,
sarcasmo no compra, "cumple 15" no es cantidad, pedido múltiple enredado sale
entero). Los cambios de decisión del cliente quedan cubiertos: el estado
persistido (pedido pendiente, destino único sticky, producto en foco, memoria
larga) se reinterpreta CONTRA cada mensaje nuevo y el presupuesto se recompone
de cero con datos sellados en cada turno. Pendiente inmediato: que Martín
repita su guion real de 3 mensajes por WhatsApp contra producción.

---

**8-jul-2026 (2ª tanda).** MEMORIA LARGA (C2-C4) + pedido
sellado del turno + carrito que no se envenena. Validado: dos rondas vivas 9/9
seguidas (guion nuevo de 14 turnos incluido). Cuatro piezas:
1. **Memoria larga** (`memoria_larga.py`): los turnos que caen del tope de 10 se
   FUNDEN en el campo `summary` (existía, iba vacío) con una llamada corta al modelo
   del solver SOLO en turnos que desbordan; red determinista si el LLM falla, tope
   1500 chars. El resumen entra al contexto del intérprete y al bloque del solver
   (`resumen_charla` en el estado). Verificado vivo: a los 14 turnos el bot retomó el
   producto elegido en el turno 2 y el destino del turno 1, total exacto $16.000.
2. **Pedido sellado del turno** (`calculate_total`): cuando la guía de pedido calculó,
   un calculate_total del solver que AGREGA productos fuera del pedido (+carrito) se
   rechaza (mató el micrófono fantasma de $76.500 que el cliente nunca eligió).
3. **Carrito sin veneno**: un turno con intención "otra" (rechazo, off-topic) NO
   actualiza el carrito desde una calculadora especulativa del solver.
4. Guion vivo nuevo `09_memoria_larga.txt` (14 turnos, dato clave al principio y ruido
   en el medio). **358 tests offline + 9 vivos, dos rondas seguidas en verde.**
PENDIENTE: OK de Martín para mergear a main (deploya el CI) y arrancar el /loop de
robustez (charlas complejas generadas, prueba-error hasta producto robusto).

**8-jul (PRIORIDAD 1 de Martín, caso real de WhatsApp): INTERPRETACIÓN + BUG
CRÍTICO DE PERSISTENCIA.** La charla real mostró: (a) el bot armó un presupuesto
1x-de-cada inventado ante "4 notebooks, 3 teclados y 5 mouse" sin modelos, con un
K120 al precio del Acer; (b) en el turno 2 saludó de cero: LA CONVERSACIÓN NO
PERSISTÍA. Causa raíz de (b): save_conversation de producción enumera sus
parámetros sin **kwargs y el campo nuevo destino_unico tiraba TypeError en CADA
turno (el doble del banco acepta cualquier kwarg y no lo cazó). ARREGLADO: firma
tolerante que persiste kwargs desconocidos con warning — la deriva sim/prod ya no
puede tirar la memoria. Para (a), módulo de PEDIDO POR CATEGORÍAS (guia_pedido):
cantidades+categorías sin modelos → opciones reales con stock por categoría +
pregunta de modelos; PROHIBIDO armar presupuesto, guarda que lo reemplaza si el
solver lo intenta, y pendiente STICKY entre turnos (el turno siguiente inventaba
$607.000 de items fantasía). Además: ancla del corrector desempata por nombre del
MISMO renglón (K120 a $732.500 del renglón del Acer ahora se corrige), B6 detecta
la forma afirmativa ("las calidades son buenas, los envíos son seguros"), y el
sello de la guía ya trae envío y transferencia dichos en el mismo mensaje.
Verificado con el guión 24 (la charla real de Martín, textual): turno 1 opciones
perfectas 4/3/5 + destinos, turno 2 sin presupuesto fantasma. 388 tests offline.
**PRÓXIMO MÓDULO acordado: interpretación con categorías difíciles (el bot es
50% venta / 50% no alucinar; sin interpretar bien no es viable).**

**MÓDULO DE INTERPRETACIÓN — banco nuevo (8-jul, prioridad 1).**
`banco_pruebas/banco_interpretacion.py`: mide al INTÉRPRETE aislado, caso por caso
(mensaje difícil + contexto → lectura esperada), con piso 80% y lock vivo en
`tests/test_vivo_interpretacion.py`. 16 casos: ironía, decisión condicionada
("dale pero antes..."), correcciones a mitad de frase ("2... no, mejor 3"),
negación doble, despedida-que-parece-compra, jerga ("metele q va"), typos.
Primera corrida: 15/16 — la falla ("el barato no, el otro" con dos baratos
empatados: el modelo elige confiado la otra variante barata) es un sesgo del
modelo y se corrigió por CÓDIGO (`_corregir_referencia_comparativa`: la
comparación de precios es cerrada; único caro → se corrige, varios → candidatos
con confianza baja). Segunda corrida: 16/16 = 100%. 392 tests offline.

**LOOP DE ROBUSTEZ — ciclos 2 y 3 (8-jul, deploy indirecto por ciclo verde).**
Guiones 14-20 (desprolijo, multipregunta, contradicción lejana, reserva/split,
cliente que vuelve, jailbreak comercial, stock al límite). Salieron BIEN de fábrica:
split 70/30, factura A, cliente desprolijo, stock al límite (verdad + sellado),
antijailbreak (0 ms), memoria del que vuelve. Se cazaron y cerraron con red + test:
(1) destinos sin cotizar ya no se rellenan duplicando tarifa (E13 v2: se pide
cotizar; caso mudanza cobraba dos envíos), (2) DESTINO ÚNICO sticky ("mandalo todo
a X"/"me mudé" deja obsoletos los destinos viejos aunque el solver los re-cotice),
(3) fallback bloqueado sirve la CURADA del tema si el ruteo matchea (caso seña),
(4) guarda del MÁS BARATO: si el solver afirma un "más barato" distinto del que
computó la guía, se re-ancla al real (caso M170 por DX-110), (5) ASIENTOS: el
Subtotal declarado se corrige a la suma de los renglones del mismo mensaje si la
suma está respaldada (candidata vieja del RESUMEN, vista dos veces), (6) guardia
clase promo_inventada ("te confirmo el 2x1" del falso gerente → niega honesto y
ofrece transferencia). 381 tests offline.

**LOOP DE ROBUSTEZ — ciclo 1 (8-jul, Martín deployó y dejó el loop corriendo cada
20 min).** Cuatro guiones complejos nuevos (10-13: regateo+precio falso,
urgencia+cancelación, regalo+presupuesto, queja+humano+exterior). Juez limpio en
datos; la LECTURA de conducta cazó tres mentiras de texto y se cerraron con redes
deterministas + test: (1) guardia clase `descuento_inventado` ("descuento especial"
prometido que no existe; transferencia/mayorista eximen), (2) guardia clase
`envio_exterior` ("hacemos envíos a Montevideo" — falso, solo Argentina; la negación
honesta no dispara), (3) gatillo determinista de HONESTIDAD DE BOT ("¿sos un robot?"
→ si el solver esquiva, el código antepone la verdad; era el pendiente del
disclaimer). B21 ahora detecta ciudades (montevideo, etc.). Verificado en vivo: las
tres redes dispararon y reescribieron. En el guion de regalo se vio el pedido
sellado rechazando un item agregado en producción simulada. 367 tests offline.

**Última actualización: 8-jul-2026.** SALUDO INICIAL + GUÍA DETERMINISTA DE PEDIDO +
tres bugs de verificación cazados con el caso real de multi-envío de Martín. Todo
validado de punta a punta en el banco (dos rondas vivas 8/8 seguidas + caso multi-envío
con juez limpio). Cinco piezas:
1. **Saludo inicial determinista** (`_con_saludo_inicial`, interprete_libre): el PRIMER
   mensaje de cada charla lleva saludo cordial + "soy el asistente automático de X",
   una sola vez (pedido de Martín; era el pendiente del disclaimer). Si el solver ya
   saludaba, su saludo se recorta para no saludar dos veces.
2. **GUÍA DETERMINISTA DE PEDIDO** (`guia_pedido.py` + campo `pedido` en el schema del
   intérprete): cuando el cliente define el pedido (productos MOSTRADOS + cantidades,
   atado por enum), el CÓDIGO llama calculate_total con los ids reconciliados (todo o
   nada) y sella el presupuesto; el solver redacta alrededor. Es el primer paso real de
   "forzar herramientas": mata el caso visto de ids equivocados + cuenta tipeada a mano.
   El cálculo entra a meta.tools_called al final (gana en reversed sobre un calc del
   solver con items equivocados).
3. **cotizar_envio con provincia de la charla**: una localidad ambigua ('Los Cóndores')
   reintenta con la provincia sticky o la dicha en el MISMO mensaje; ya no re-pide el CP
   que el cliente ya dio. La provincia del mensaje entra al estado al ARRANQUE del turno.
4. **Tres bugs de verificación arreglados** (cazados por el banco con el caso nuevo):
   (a) el sello del precio de lista pisaba los renglones multiplicados del presupuesto
   sellado ("3x X: $693.000 c/u = $2.079.000" → corregía a 693.000); ahora exime por
   IDENTIDAD el monto computado en el proof PARA el producto nombrado. (b) el detalle de
   calculate_total entraba a la evidencia sin precio_ars (trae precio_unitario) y el
   ancla corregía un precio CORRECTO al del hermano (NX-7000 → 8.500); se normaliza en
   la fuente. (c) el candado Corsair anulaba al sello para todo precio del pool: en un
   RENGLÓN de presupuesto (cifra pegada al nombre) el ancla ahora manda (caso
   Zeus/Pandora); en prosa suelta el candado sigue. Además `_contexto_total` tolera
   negrita markdown y merge_productos sube el tope a 60 (30 productos de un turno
   tiraban la primera categoría y rompían el enum del intérprete).
5. **Tests: 350 offline + 8 vivos en verde, dos rondas vivas seguidas.** PENDIENTE con
   OK de Martín: mergear a main (CI deploya). Conducta abierta a vigilar: en el primer
   turno el solver a veces arma un presupuesto provisorio 1x-de-cada en vez de preguntar
   modelos (los datos son reales, es presunción); y ante pedido sin modelos el gancho
   ideal es preguntar. Lo tapa la iteración de casos con Martín.

---

**Última actualización: 7-jul-2026 (tarde).** CURADAS DE VENTA AMPLIADAS A B1-B24 +
CONSOLIDACIÓN DE PROVIDERS (todo el camino vivo en GPT-4 mini). Cuatro cambios:
1. **Doce categorías nuevas de venta** (B13-B24: urgencia, mayorista, presupuesto
   acotado, regalo, queja, pedir humano, cancelación, pago no ofrecido, envío
   exterior, pedido de fotos, reclamo posventa, multi-pregunta) con su movida
   redactada en `BORRADORES_CURADAS_VENTA.md`, detector determinista en
   `ruteo_venta.py` y brief en `guia_venta.py`. B3 (negación intra-turno) tenía
   brief pero NINGÚN detector que lo disparara (movida muerta): ahora rutea. B9
   tenía movida sin brief: ahora lo tiene. Test nuevo de coherencia: toda
   categoría que rutea a movida DEBE tener brief (no más movidas muertas).
2. **Reescritor de la guardia consolidado**: usaba DeepSeek HARDCODEADO (quedó
   así cuando el sistema pasó a OpenAI) y corría deepseek-v4-flash SIN apagar el
   thinking — causa probable de las reescrituras VACÍAS del 4-jul. Ahora usa el
   MISMO cliente y modelo del solver (`modelo_solver()` en agent.py, un solo
   lugar), con el apagado de thinking si el provider razonador vuelve.
3. **llm_adapter (rol proposer: extractor del cierre + fallback de query_faq)**:
   el default era deepseek-chat, que SE DA DE BAJA EL 24-JUL — se rompía solo ese
   día. Ahora default openai/gpt-4o-mini (se vuelve por env). Y DeepSeek directo
   v4 en el adapter ahora apaga thinking como NVIDIA/OpenRouter/Gemini.
4. Los textos de B1-B12 se retocaron (criterio sticky en B1, cruces B4→B14 y
   B11→B19, fuentes FAQ explícitas). PENDIENTE: retoque fino de Martín sobre los
   24 textos; lo corregido se pasa al brief y se deploya.
**324 tests offline en verde (20 nuevos).** Los LLM del camino vivo quedan:
intérprete (structured outputs), solver, reescritor de guardia y proposer — los
CUATRO en GPT-4 mini; el dato duro sigue saliendo solo del código.

---

**Última actualización: 7-jul-2026.** CONSTRAINED GENERATION + FUENTE DE VERDAD DE VENTA,
DEPLOYADO. Con OK explícito de Martín el sistema pasó a GPT-4 mini de OpenAI para correr la
restricción por código en su forma DURA. Se validó primero que GPT-4 mini respeta constrained
generation a nivel token (imposible emitir un valor fuera de la fuente de verdad: precio, stock,
identidad, todo atado a enum con escape). Seis piezas nuevas, un solo cambio coherente:
1. **Taxonomía de venta** (`CATEGORIAS_PREGUNTAS_VENTA.md`): categorías comunes, complejas y las de
   memoria (listadas para después). Semilla de la fuente de verdad de venta y del espacio de
   etiquetas que leen los dos LLM.
2. **Curadas de venta B1-B12** (`BORRADORES_CURADAS_VENTA.md`): movidas con bloque sellado + nexos
   adaptativos. Registro universal, no atado a un modelo. Pendientes de retoque fino de Martín.
3. **Router de venta** (`ruteo_venta.py`): elige la movida o manda preguntar (escape), determinista
   y conservador. Fuente de verdad del espacio de etiquetas.
4. **Movidas en vivo** (`guia_venta.py`, enchufado en `interprete_libre.py`): el brief de la movida
   se inyecta al solver por el mismo carril que `guia_mas_barato`/`guia_memoria`; el dato duro sigue
   sellado. El LLM redacta los nexos, el código no le suelta ningún número.
5. **Intérprete constreñido** (`interpretador.py`): en OpenAI usa Structured Outputs con schema
   estricto (intención y estado por enum, `producto_resuelto` atado al enum de lo mostrado o null),
   con fallback seguro. Provider a OpenAI gpt-4o-mini en `config.py` (config, no camino apagado).
6. **Sello del precio de lista** (`verificador.py`): el ancla de precio por NOMBRE ahora corre aunque
   la cifra figure en el pool. Cierra el hueco del $16.500 del KB-110X: si el solver tipea un precio
   que no coincide con el del producto nombrado, el código lo autocorrige antes de salir. Candado
   Corsair intacto.
La regla DeepSeek-por-default sigue en pie a nivel código: se vuelve cambiando un default. **304 tests
offline en verde, banco vivo por OpenAI 8/8 limpio.** Próximo frente: cerrar y aprobar las curadas de
venta con Martín, y la capa de memoria (categorías C).

**Última actualización: 6-jul-2026 (noche).** ERRORES DE PLATA DE CHARLA REAL ATACADOS Y
DEPLOYADOS + el cuello de botella se MOVIÓ. Tres deploys nuevos (runs #80, #81, #82 verdes):
1. **Guarda de promesas** (`guardia_promesas.py`): ahora caza el día de entrega con la forma
   'tengas' y 'la semana que viene'/'próxima semana' ("entre miércoles y viernes de la semana que
   viene ya tengas todo" se filtraba). 'cuando tengas los datos', sin un día, sigue sin disparar.
2. **Split de pago en la calculadora** (`pago_split.py` + param `pago` de `calculate_total`): UNA
   función genérica reparte el total entre medios por porcentaje (50/50, 70/30, tres medios, etc.),
   aplica el 10% de la FAQ a todo lo que NO es Mercado Pago (regla de Martín: no-MP = transferencia,
   Ualá incluido). El solver no calcula nada: pasa `pago` y recibe el bloque sellado por
   [[PRESUPUESTO]]. Mata el error de la charla donde el bot hizo la cuenta a mano ($1.617.375 mal
   vs $1.593.150 real).
3. **Sellado del split** (`verificador.py`, `numeros_confiables`): el verificador reconoce los
   montos del reparto (base, total final, descuento, cada parte) del proof, así la respuesta
   correcta no se bloquea en falso, y un total escrito a mano y mal se AUTOCORRIGE al del proof. Es
   el sellado SEGURO (autocorrige, no bloqueo bruto): el código dueña la cuenta sin frenar ventas.

**EL CUELLO DE BOTELLA SE MOVIÓ (2ª charla real 6-jul, mismo pedido):** las tres piezas de plata
están BIEN pero NO se ejecutaron, porque la charla nunca llegó a calcular. El bot se quedó pidiendo
colores y modelos aunque el cliente delegó ("confío en tu elección") TRES veces, y NUNCA llamó a la
calculadora. El bloqueante ya no es la cuenta, es que **el solver no COMPROMETE la venta y no llama
las herramientas**. Persisten además: (a) tarifas de envío INVENTADAS (Jujuy $11.000 real $9.000,
Correa $7.000 real $6.000; el solver no llama cotizar_envio, las tipea); (b) plazo contradictorio
("4 a 7 días" bien, pero después "3 o 4 días" bajo el piso y "una semana tenés todo en mano", una
promesa blanda que la guarda aún no caza); (c) lee mal el split ("10% transferencia + 10% MP" por
50/50). Precios, stock, distribución de destinos y carriers (Andreani/OCA de la FAQ): TODO correcto.

**PRÓXIMO PASO (los cambios grandes, arrancar acá):** FORZAR el uso de herramientas. No se puede
obligar a un LLM a llamar una tool, pero sí hacer que no importe: (1) el CÓDIGO hace la llamada
determinista cuando se dan las condiciones cerradas —igual que `guia_compra` ya elige el más barato—
: si hay localidades en la charla, el código cotiza el envío y lo inyecta; si el cliente delegó y
el pedido está definido, el código elige los modelos recomendados y llama `calculate_total` con el
split; (2) el verificador BLOQUEA una afirmación de envío/total sin su proof del turno. Los dos
juntos hacen que la plata ya deployada por fin se ejecute. Área 3 (piso de plazo) y el huequito de
la guarda ('una semana en mano') son chicos y van con eso.

---

**6-jul-2026 (tarde).** ARBITRAJE DE DIVERGENCIA intérprete↔solver por ejes
CERRADOS + primera pieza del ENSAMBLADOR, todo DEPLOYADO a producción (runs #78 y #79 verdes).
Cuatro cambios nuevos, mismo patrón de guarda determinista, con test cada uno:
1. **Medición de divergencia** (`app/core/divergencia.py`): loguea, sin tocar la respuesta,
   cuándo el solver hizo algo distinto a lo que leyó el intérprete en producto, opciones A/B y
   estado del embudo. Evento `interprete_libre_divergencia`. En el banco solo disparó un falso
   positivo del eje estado (el "te confirmo el producto" re-muestra el mismo producto): dato para
   afinar antes de enforzar el embudo.
2. **Guarda de producto** (`_reanclar_si_producto_divergente` en interprete_libre + reconciliación
   por nombre): si el intérprete resolvió con confianza un nombre que reconcilia con UN único
   producto del catálogo y el solver mostró otro, re-ancla al correcto con su línea real y
   pregunta; nunca cierra sobre un id inferido. Triple candado. OJO: el certificador de queries da
   'ambiguous' para un nombre completo (comparte 'mouse' con medio catálogo), por eso se reconcilia
   por nombre, no con el certificador.
3. **Memoria borrosa** (`app/core/memoria_ref.py`): "el que te dije, no me acuerdo" → el código
   ancla el único visto, manda preguntar si hay varios, manda no inventar si no hay ninguno.
   Inyección previa al solver, mismo patrón que la guía del más barato.
4. **ENSAMBLADOR** (`app/core/ensamblador.py`, `colocar_bloque`): el código arma el mensaje final
   cuidando la congruencia; un dato de una línea va donde el solver puso el marcador, un bloque de
   varias líneas (presupuesto, política) se levanta a su propio párrafo y no queda incrustado en
   una oración; marcador sin dato se quita limpio. Reemplaza el replace crudo de [[PRESUPUESTO]] y
   [[ENVIO]]. **260 tests offline en verde, 8 vivos con juez limpio.**

**ESTRATEGIA NUEVA acordada con Martín (6-jul), el norte de lo que viene:** salir del loop de
"parchar error por error" invirtiendo quién genera. Hoy el solver genera todo y el código corrige
atrás (whack-a-mole infinito). El destino es el **ENSAMBLADOR**: el código corre las tools, arma
los bloques duros CERRADOS y sella una plantilla con huecos; el LLM NO elige ni escribe ningún
dato, solo redacta la prosa de unión entre bloques que no puede tocar. La garantía no sale de
confiar en el solver sino de SACARLE EL DATO DE LAS MANOS: el mensaje final lo concatena el código,
100% predecible. Único residual: la prosa del hueco (acotada, la filtra lo de siempre) y una mala
lectura del INTÉRPRETE en la etapa 1 (respuesta: si la confianza es baja, el Ensamblador PREGUNTA,
no afirma). Por qué los marcadores fallaron antes y esta vez no: antes se los dábamos al solver
como obligación opcional (podía olvidarlos o escribir el dato por fuera); el Ensamblador hace al
código dueño de la colocación. Ya está la COHERENCIA; falta el SELLADO (que ningún dato duro entre
por fuera de un marcador y podar lo suelto) para la garantía total.

**PRÓXIMO PASO (arrancar acá el chat que viene):** el SELLADO de datos por marcador — todo precio/
producto/total que el solver escriba por FUERA de un marcador se poda o se marca. Eso tapa el
"teclado fantasma" de abajo. Y DEFINIR CON MARTÍN la regla de Ualá (decisión de negocio, no la
puede tomar Claude): ¿Ualá cuenta como transferencia para el 10%? ¿el descuento va a TODO el
pedido o solo a la parte pagada por transferencia?

**HALLAZGOS charla real de WhatsApp (6-jul), verificados contra catálogo+FAQ del repo:**
- **Precios y stock: TODOS correctos**, sin una alucinación de plata. El blindaje funcionó.
- **ERROR grave — teclado fantasma:** el bot metió "Logitech G915 TKL $512.500" (producto real,
  precio real) que el cliente NUNCA pidió, en un turno de "lo más barato". Causa: el solver emitió
  un [[PROD:id]] con el id equivocado (TEC0001) y el estampado lo renderizó con dato real; los
  verificadores no lo frenan porque la plata ES verdadera, solo que de OTRO producto. Es selección
  MAL de producto por fuera de la intención → lo tapa el SELLADO del próximo paso.
- **Ualá / descuento:** la cuenta del 10% la hace el CÓDIGO (calculate_total) y está bien
  ($705.000 −$70.500 = $634.500). El problema es que el SOLVER decidió que Ualá = transferencia y
  aplicó el 10% a TODO (incluida la notebook que el cliente dijo pagar por Ualá), sin regla de
  fuente: en ninguna FAQ está definido si Ualá cuenta. Hueco de política, pendiente con Martín.
- **Envío: NO le falta infraestructura.** La tabla de 16.164 localidades YA resuelve: "Villa Los
  Aromos" sola, sin CP, cae a Córdoba/interior/$7.500; hasta "Pcia de córdoba no sé CP" resuelve.
  El defecto es que el SOLVER pidió el CP igual teniendo todo para cotizar. Es conducta del solver,
  no tabla faltante. En esta charla el envío fue GRATIS bien (compra > umbral $250.000 de la FAQ).
- Menor: dio el Asus Vivobook como "agotado" pero la variante i5 Plata tiene 6 unidades (el
  verificador de stock se abstiene sin color nombrado).

---

**5-jul-2026.** BANCO DE CHARLAS VIVAS con JUEZ automático: los errores
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
