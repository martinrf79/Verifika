# HANDOFF — estado del proyecto para retomar rápido

Leer esto primero. Resume todo lo hecho para no re-derivar contexto.

## Qué es
Bot de ventas WhatsApp/Telegram. FastAPI en Cloud Run.
- Servicio Cloud Run: `agente-bot` | Proyecto GCP: `memory-engine-v1` | Región: `southamerica-east1`
- Base: Firestore. Tienda en uso: `verifika_demo` (50 productos, 22 FAQ).
- LLM: DeepSeek (deepseek-chat). Carpeta local del proyecto: `C:\Users\marti\Downloads\claude code verifika\agente-v4`

## Cómo se deploya (desde la notebook, sin zip)
```
cd "C:\Users\marti\Downloads\claude code verifika\agente-v4"
gcloud run deploy agente-bot --source . --region southamerica-east1 --allow-unauthenticated
```
`.gcloudignore` ya excluye winvenv, .secrets*.env y zips. Cambiar solo una variable de entorno: `gcloud run services update agente-bot --region southamerica-east1 --project memory-engine-v1 --update-env-vars=NOMBRE=valor`

## Arquitectura (flujo de un mensaje)
1. Interpretador (LLM): detecta intención y etapa de venta. Provider configurable.
2. Solver (DeepSeek + tools): busca, calcula y redacta. Usa herramientas.
3. Calculadora `calculate_total`: ÚNICA fuente de números, con PROOF. Maneja porcentajes (descuento), rangos (envío), envío gratis.
4. Verificador determinista (`app/core/verificador.py`): LÍNEA CERO anti-alucinación, por CÓDIGO. Exige que cada cifra de dinero salga del catálogo, FAQ o PROOF. Gatea la respuesta. Modo on/shadow/off.
5. Leads/Cierre (`app/core/leads.py`, `app/core/cierre.py`): captura nombre, teléfono, dirección, pago; avisa al dueño con la orden.
Anti-alucinación vive en el CÓDIGO (verificador), no en el prompt.

## Flags clave (app/config.py) — estado deseado en prod
- VERIFICADOR_MODE=on  (el código gatea; Checker LLM desconectado)
- LLM_PROVIDER=deepseek , INTERPRETER_PROVIDER=deepseek
- PROMPT_LEAN=false  (prompt original probado; lean disponible para bajar latencia)
- CALC_PORCENTAJES, TOOL_LISTAR_CATALOGO, VERIFIKA_FULL_FAQ_EVIDENCE, PROPOSER_IGNORA_CANTIDAD, VERIFICADOR_RECONCILE_NUMBERS, SOLVER_USA_PRESENTACION, FAQ_KEYWORD_FIRST = true
- AUTOFIX=false (opcional), CIERRE_COMPLETO=true
- USE_LEADS, USE_INTERPRETER, USE_VERIFIKA: setearlos en prod por env. Para CIERRE de venta: USE_LEADS=true + OWNER_TELEGRAM_CHAT_ID=<chat dueño>.
- MAX_TOOL_ITERATIONS=6, LLM_TIMEOUT_SECONDS=45
- Gemini wired (GEMINI_API_KEY/MODEL/BASE_URL) pero SIN cuota (requiere pagar). Groq wired pero límite diario gratis + tool calling flojo en el solver.

## Pruebas (corren en la notebook, no en Cloud)
- `winvenv\Scripts\python.exe scripts\bateria_robustez.py`  → núcleo determinista, 11 escenarios, sin credenciales. Correr ANTES de cada deploy. Cubre el camino SIN calculadora defensiva.
- `winvenv\Scripts\python.exe scripts\banco_casos.py`  → banco de casos acumulable: tabla de casos + generador de combinaciones con invariantes (335 combos) + casos reales desde data\casos_reales.json (con total esperado). Métricas a reports\banco_metrics.json e historial a reports\banco_history.jsonl. Corre con CALC_DEFENSIVA activa (config objetivo). Marca PEND lo no implementado y LISTO? si un pendiente pasa solo. Sin credenciales.
- `winvenv\Scripts\python.exe scripts\dashboard.py`  → lee el historial y muestra estado por componente y tendencia. Sin credenciales.
- `winvenv\Scripts\python.exe scripts\clasificar_casos.py --dry-run`  → carril modelo: clasifica conversaciones reales (data\conversaciones_raw.jsonl) con DeepSeek por tipo/dificultad y marca candidatas a regresión. USA DeepSeek (gasta), correr con datos exportados. Los candidatos de cálculo se pasan a mano a data\casos_reales.json.
- `scripts\prueba_modelo.py [escenarios]`  → solver real con DeepSeek (.secrets.env), adversarios.
- `scripts\bateria_modelo_100.py 100`  → 100 pruebas variadas (DeepSeek).
- `scripts\prueba_gemini.py` / `prueba_groq.py` / `prueba_interp_groq.py` → pruebas de provider.
- Claves locales: `.secrets.env` (DeepSeek, funciona). `.secrets2/.secrets3.env` (Gemini, SIN cuota). NUNCA subir, NUNCA pegar en el chat.

## Observabilidad
- trace_id en todo, tiempos por etapa (t_interpret_ms, t_solver_ms, etc.), campo `outcome` en message_completed, eventos diag_verificador/diag_verifika (con DIAG_TRACE=true).
- Sentry cableado (SENTRY_DSN). Queries de KPIs en `scripts/kpis.txt`.

## Estado y temas abiertos
- HECHO y probado: anti-alucinación robusta (no se come trampas de precio, slang, typos, inyección), cierre de venta, observabilidad, autofix. Una venta real cerrada OK.
- LATENCIA: RESUELTA (ver sesión 2026-06-01). Causa era CPU throttling de Cloud Run sobre el procesamiento en segundo plano; ahora se procesa dentro del request (PROCESAR_EN_REQUEST=true), gratis. El solver bajó de ~70s a ~3-8s. DeepSeek NUNCA fue el problema.
- ABIERTO: (1) plan de pruebas/certificación: EN MARCHA. Hecho: banco_casos.py (tabla + 335 combinaciones con invariantes + casos reales acumulables con total esperado + métricas por componente), dashboard.py (estado y tendencia), clasificar_casos.py (carril modelo con DeepSeek, listo pero sin correr). Falta: exportar conversaciones reales de Firestore a data\conversaciones_raw.jsonl y enganchar la corrida del Solver real contra los casos reales (hoy prueba_modelo.py y bateria_modelo_100.py ya corren el Solver con DeepSeek). (2) calculadora "defensiva": HECHA con P1 a P5, detrás de flag CALC_DEFENSIVA (default false), en app\core\calc_defensiva.py. Cubre P1 deduplicar extra repetido, P2 rechazar cantidad cero/negativa, P3 normalizar capitalización del concepto, P4 fusionar producto repetido, P5 elegir un solo envío por destino (el destino lo detecta el orchestrator por keywords y lo inyecta por contextvar, el LLM no lo elige; si el destino no es claro y hay dos envíos, rechaza para preguntar). Diseño en CALCULADORA_DEFENSIVA_DISENO.md. Para activar en prod: --update-env-vars=CALC_DEFENSIVA=true (una variable, sin coma), con tu OK. Verificado local: banco 14/14 OK con CALC_DEFENSIVA activa, bateria_robustez 11/11 con el flag apagado. (3) fortificación de código: Bandit, Ruff, Safety (dev tools, no van a requirements). (4) integrar Mercado Pago: link de pago + webhook de confirmación + posventa. (5) evaluar Gemini cuando haya cliente (más rápido, co-ubicado en Google).

## Resuelto en la última sesión (2026-06-01)
- LATENCIA (causa raíz CONFIRMADA): el bot procesaba en segundo plano (FastAPI BackgroundTask, tras responder 200 al webhook) y Cloud Run estrangula la CPU ahí. Prueba pareada: con throttling el solver tardó 69s; con CPU asignada, 3s. El botón /admin/diag-latencia (llamada pelada a DeepSeek desde Cloud Run) da ~1,2s SIEMPRE, incluso replicando el peso completo del solver → descartado payload/tokens/historial/prompt/red/modelo. FIX gratis: PROCESAR_EN_REQUEST=true (procesa dentro del request, CPU plena, sin pagar always-on). Alternativa paga: --no-cpu-throttling + minScale=1 (~50-65 USD/mes). Detalle en DIAGNOSTICO_LATENCIA.md.
- FALLBACK en cierres de compra grande (>250k): el bot improvisaba el total con envío gratis + descuento y el verificador lo bloqueaba (bien). FIX: calculate_total ahora fuerza envío gratis automático cuando el subtotal de productos supera UMBRAL_ENVIO_GRATIS (flag ENVIO_GRATIS_AUTO=true, umbral 250000), devuelve el total final entero + mensaje_para_llm para que el modelo no recalcule. Regla de negocio: descuento sobre subtotal de productos; envío gratis a cualquier destino si subtotal>250k. Batería F1 reescrita para este caso. 11/11 OK. Verificado en prod: cierre OK.
- Subido MAX_TOOL_ITERATIONS de 6 a 8 (el solver agotaba 6 vueltas en cotizaciones complejas → fallback técnico).
- Nuevos flags (todos en app/config.py): PROCESAR_EN_REQUEST, ENVIO_GRATIS_AUTO, UMBRAL_ENVIO_GRATIS, SALUDO_DIRECTO, PRECALENTAR_CACHE, SOLVER_HISTORIAL_LEAN (estos 2 últimos NO sirvieron para latencia, dejar en false/default). OpenAI cableado como provider opcional (LLM_PROVIDER=openai) pero DeepSeek sigue siendo el modelo.
- Nuevas herramientas de diagnóstico: endpoint /admin/diag-latencia (mide latencia pura desde Cloud Run), scripts/medir_latencia_deepseek.py, scripts/prueba_compresion.py, scripts/prueba_saludo_directo.py, scripts/prueba_interp_saludo_real.py.
- IMPORTANTE rotar: el ADMIN_TOKEN se rotó (estaba expuesto). La OPENAI_API_KEY quedó expuesta en chat viejo, conviene rotarla en platform.openai.com.

## Resuelto en sesión previa (2026-05-30)

## Resuelto en la última sesión (2026-05-30)
- BUG bot no respondía "LLM_PROVIDER inválido: deepseek": era la COMA de PowerShell. Al setear `--update-env-vars=LLM_PROVIDER=deepseek,INTERPRETER_PROVIDER=deepseek` desde PowerShell, la coma mangaba el valor y LLM_PROVIDER quedaba con todo el string pegado. NO era el código ni el prompt. FIX: setear cada variable en un comando aparte, sin coma. REGLA PowerShell: una variable por comando.
- BUG flujo: el bot pedía datos de cierre (nombre/teléfono) ANTES de mostrar el precio cuando el cliente largaba señal de compra al pedir cotización. FIX por código (flag CIERRE_PRECIO_PRIMERO, default true), tres puntos: (a) leads.py caso fuerte se degrada a tibia si no hay presupuesto; (b) orchestrator atajo del interpretador solo cierra si hubo presupuesto previo; (c) orchestrator nunca pisa una cotización fresca con el pedido de datos, muestra precio primero y datos después. Regla: no se piden datos de cierre sin haber mostrado el número.
- Prueba nueva: `scripts\prueba_cierre_orden.py` (simula el escenario sin Firestore, 2/2 OK). Batería determinista sigue 11/11. Ya deployado.
