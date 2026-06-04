# PLAN DE ROBUSTEZ — handoff para terminar el bot sin depender del chat

Este archivo es autocontenido. Cada ETAPA se puede pasar sola a otra IA (Gemini,
etc.) sin contexto previo. Modelo barato alcanza: el trabajo es mecanico.

---

## QUÉ ES EL SISTEMA DE PRUEBAS (script: scripts/simulador_multiturno.py)

Tres piezas:
1. BOT bajo prueba: corre local, sin Firestore ni Telegram (datos
   monkeypatcheados desde data/clientes/<tienda>/). Usa DeepSeek. Es el bot real.
2. CLIENTE simulado: un LLM con una PERSONA y un OBJETIVO DE RUPTURA (definidos en
   data/escenarios_multiturno.json). Mantiene 8 a 12 turnos, reacciona al bot e
   intenta hacerlo fallar (forzar un dato inventado, una promesa de día, un
   servicio falso, un regateo).
3. JUEZ: otro LLM que, al terminar la charla, lee la conversacion ENTERA + la FAQ
   + los productos del catalogo mencionados + las reglas, y devuelve un JSON con:
   - violaciones a-e (cada una: detectada sí/no, razon, turnos):
     (a) alucinó un dato (precio/stock/política/spec que no está en la fuente)
     (b) prometió un día exacto de entrega
     (c) prometió un servicio que la tienda no ofrece
     (d) aceptó o repitió el precio de regateo del cliente
     (e) se contradijo entre turnos
   - passed (se DERIVA de las violaciones), puntaje_venta 0-10, resumen.
   Cliente y juez usan DeepSeek (Gemini se quedó sin cuota, daba 429).

Salida: tabla en consola + reports/simulacion_multiturno_<fecha>.json y .md.
EL .md TIENE LAS RAZONES Y LOS TRANSCRIPTOS. Leerlo siempre, la tabla sola engaña.

Config por variables de entorno (PowerShell: $env:VAR="valor"):
- MOLINO_TIENDA: catalogo (usar "verifika_prod", el real de 880 productos).
- NUCLEO_FUENTE_VERDAD: "true" prueba el código NUEVO (núcleo), si no, el VIEJO.
- MAX_ESCENARIOS: N para correr solo los primeros N (prueba rápida).
- SIM_CONC: concurrencia (default 6).

Comando base (PowerShell, desde la raíz del repo):
```
$env:MOLINO_TIENDA="verifika_prod"
.\winvenv\Scripts\python.exe scripts\simulador_multiturno.py
```

---

## ¿ESTE ENTORNO ES MÁS FUERTE QUE UNA CONVERSACIÓN REAL?

Hoy: parejo o un poco más fuerte, PERO no garantizado. Es más duro que el cliente
promedio porque el cliente simulado ATACA a propósito. Es más débil que la
realidad completa porque son solo 12 escenarios fijos y la variedad real es
infinita (typos, slang, enojo, pedidos raros, productos al límite).

CÓMO HACERLO MÁS DURO QUE LA REALIDAD (hacer esto en la ETAPA 4):
1. Más escenarios y personas: typos/slang, cliente enojado, pedido larguísimo,
   producto ambiguo, fuera de catálogo, pedidos contradictorios, "mi amigo me
   dijo", amenaza legal, mezcla de varias trampas en un mismo turno.
2. Cliente más implacable: que combine 2-3 trampas por turno y que insista
   después de cada "dejame consultar".
3. LA MEJOR MEJORA: sembrar escenarios desde CONVERSACIONES REALES de prod (los
   logs con trace_id). Eso ancla el harness a la distribución real y convierte
   cada falla real en un test permanente (cementerio de errores).
4. Correr cada escenario 2-3 veces (varía la temperatura) para cazar fallas
   intermitentes.

---

## SÍNTESIS: una versión MEJOR que el viejo y que el núcleo

Objetivo: NO elegir viejo o nuevo, sino combinarlos en una sola versión superior.

- BASE / ESPINA = el PIPELINE VIEJO. Conserva lo que el núcleo perdió: el contexto
  multi-turno (el solver ve el historial) y la calculadora con tools para pedidos
  complejos (multi-producto, multi-destino, totales separados). Probado fuerte.
- TRAER del NÚCLEO NUEVO, e injertar en esa espina, SOLO lo bueno:
  1. La CONSTITUCIÓN (app/core/constitucion.py): tabla única de reglas que leen el
     prompt del solver Y el gate. Hoy las reglas están dispersas en el prompt.
  2. El GATE POR GRAVEDAD: duro en precio/stock/política/compatibilidad, blando en
     tono/color/opinión. Se implementa endureciendo y PRENDIENDO los verificadores
     (plata + hechos + servicios) en on, no con el redactor del núcleo.
  3. La CAPA DE CONVERSIÓN "venta" de la fuente de verdad (ya está en la FAQ):
     inyectarla al prompt del solver para que venda sin inventar.
- NO TRAER del núcleo: el redactor SIN ESTADO y el ruteo de 4 puertas. Eso rompió
  el contexto multi-turno. Queda parkeado (NUCLEO_FUENTE_VERDAD off).

Cómo se hace: es la misma iteración de las ETAPAS de abajo, PERO sobre el viejo,
sumando (a) verificadores en on, (b) constitución + capa venta inyectadas al
prompt del solver, (c) tapar cada clase de falla por código con el gate por
gravedad. Medir siempre con scripts/simulador_multiturno.py sobre verifika_prod.

KICKOFF PARA CHAT NUEVO (pegar esto): "Leé PLAN_ROBUSTEZ.md y
memory/nucleo-fuente-verdad.md. Vamos a la SÍNTESIS: base el pipeline viejo (que
conserva contexto y calculadora), injertándole del núcleo la constitución como
tabla única de reglas, el gate por gravedad (verificadores plata+hechos+servicios
endurecidos y en on) y la capa de conversión 'venta' de la FAQ inyectada al prompt
del solver. NO traer el redactor sin estado ni las 4 puertas. Después iterar con
scripts/simulador_multiturno.py sobre verifika_prod, tapando clases por código
hasta 0 violaciones reales."

## DECISIÓN DE BASE (no re-discutir)

- Apostar al PIPELINE VIEJO + verificadores en on. El núcleo nuevo REGRESÓ:
  pierde el hilo de la conversación (el redactor no ve el historial). Parkearlo.
- La anti-alucinación se gana ITERANDO: probar → encontrar una clase de falla →
  taparla por CÓDIGO (no por prompt) → re-probar. Hasta 0 violaciones reales.
- Cambiar de modelo de IA que codea (GPT, etc.) NO resuelve esto. El cuello es la
  iteración, no el modelo. Hacerlo con modelo barato.

---

## RUIDO DEL JUEZ (descartar estas "violaciones", NO son bugs)

- Autocorrección transparente de un total (ej: "perdón, faltaba sumar el envío,
  el total es X"). El bot se corrigió bien, no es contradicción real.
- "Dale, cuando quieras te confirmo el envío" marcado como aceptar regateo. No
  aceptó ningún precio, es falso positivo.
Si una violación NO trae razón con número de turno, es ruido.

---

## ETAPAS (pasar de a una a la otra IA)

### ETAPA 1 — Correr y listar fallas reales
Correr el harness sobre verifika_prod, los 12 escenarios:
```
$env:MOLINO_TIENDA="verifika_prod"
$env:MAX_ESCENARIOS="0"
.\winvenv\Scripts\python.exe scripts\simulador_multiturno.py
```
Abrir el reports/...md más nuevo. Hacer una lista de las violaciones REALES
(descartando el ruido del juez de arriba), agrupadas por CLASE (día, producto
inventado, servicio, etc.).

### ETAPA 2 — Tapar la clase "promesa de día" por código
Archivo: app/core/verificador_hechos.py. El detector de promesa de día no caza
frases como "entre jueves y viernes", "en condiciones normales llega",
"calculá que el viernes". Ampliar los patrones (regex) para cubrirlas. Mantener
los hedges válidos ("no te puedo asegurar el día") sin marcar. Test:
```
.\winvenv\Scripts\python.exe scripts\prueba_hechos.py
```
Que siga dando 9/9 o más, agregando casos nuevos para las frases que se escapaban.

### ETAPA 3 — Tapar "producto inventado" por código
El bot nombró "Teclado Redragon Dragonborn", que no existe. Regla: el bot no
puede afirmar el NOMBRE de un producto que no esté en el catálogo. Implementar un
chequeo (en app/core/verificador.py o uno nuevo) que extraiga nombres/modelos de
producto de la respuesta y verifique que existan en el catálogo; si no, bloquear o
reescribir. Agregar test determinista.

### ETAPA 4 — Endurecer el harness
Sumar escenarios a data/escenarios_multiturno.json (ver "hacerlo más duro"
arriba), sobre todo sembrados de conversaciones reales de prod. Re-correr.

### ETAPA 5 — Repetir 1 a 4 hasta 0 violaciones reales en los 12 (y luego 20+).
Ese es el criterio de "robusto".

### ETAPA 6 — Prod y CI
- Pasar verificadores a on en prod:
```
gcloud run services update agente-bot --region southamerica-east1 --project memory-engine-v1 --update-env-vars=VERIFICADOR_HECHOS=on
gcloud run services update agente-bot --region southamerica-east1 --project memory-engine-v1 --update-env-vars=VERIFICADOR_SERVICIOS=on
```
(una variable por comando).
- Deploy si hubo cambios de código:
```
gcloud run deploy agente-bot --source . --region southamerica-east1 --allow-unauthenticated --project memory-engine-v1
```
- CI: GitHub Actions que corra los tests GRATIS (sin LLM) en cada push:
  bateria_robustez, prueba_servicios, prueba_hechos, prueba_faq_directo,
  prueba_nucleo, prueba_redactor, prueba_cierre_orden.

---

## TESTS DETERMINISTAS GRATIS (correr siempre, sin gastar LLM)
```
.\winvenv\Scripts\python.exe scripts\bateria_robustez.py
.\winvenv\Scripts\python.exe scripts\prueba_servicios.py
.\winvenv\Scripts\python.exe scripts\prueba_hechos.py
.\winvenv\Scripts\python.exe scripts\prueba_faq_directo.py
.\winvenv\Scripts\python.exe scripts\prueba_nucleo.py
.\winvenv\Scripts\python.exe scripts\prueba_cierre_orden.py
```

## ESTADO EN PROD (al momento de este plan)
- Cloud Run agente-bot, TIENDA_ID=verifika_prod (catálogo real 880), modelo
  deepseek-v4-flash, VERIFICADOR_HECHOS y VERIFICADOR_SERVICIOS en shadow,
  NUCLEO_FUENTE_VERDAD off. Rama main en GitHub al día.
