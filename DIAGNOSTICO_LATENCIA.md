# Diagnóstico de latencia — descripción de pruebas (sin diagnóstico ni solución)

Documento para segunda opinión en contexto limpio. Solo hechos y números.

## Sistema
- Bot de ventas WhatsApp/Telegram, FastAPI sobre Google Cloud Run, región southamerica-east1 (São Paulo).
- Base de datos Firestore. Tienda en uso: verifika_demo (50 productos, 22 FAQ).
- Modelo LLM: DeepSeek (deepseek-chat) vía api.deepseek.com.
- Flujo de un mensaje: Interpretador (1 llamada al modelo) → Solver (varias llamadas, usa herramientas: search_products, query_faq, calculate_total, etc.) → Verificador determinista (por código) → Leads/cierre.
- Cloud Run: instancia mínima 1, 1 vCPU, 512 MB RAM, sin conector VPC, CPU throttling por defecto.
- Flags activos: USE_VERIFIKA, USE_LEADS, USE_INTERPRETER, VERIFICADOR_MODE=on, DIAG_TRACE=on, MAX_TOOL_ITERATIONS=6.

## Problema
- En producción las respuestas tardan entre 30 y 70 segundos.
- Dato del dueño: antes del 25 de mayo, con una configuración más simple y otro catálogo, el bot en Telegram respondía en pocos segundos, cualquier día y hora.

## Pruebas realizadas y resultados

1. DeepSeek medido desde la notebook local (fuera de Cloud Run): llamada simple 1,1 s; con prompt grande 1,3 s; con herramientas 1,7 a 4,7 s.
2. Producción con DeepSeek (config actual): interpretador 2 a 4 s, solver 21 a 29 s, total 35 a 39 s.
3. Cambio de modelo a OpenAI gpt-4o-mini en producción: total 57 y 63 s; cada llamada del solver 10 a 13 s. Peor.
4. Procesar el mensaje dentro del request en vez de en segundo plano (para evitar el throttling de CPU): sin mejora.
5. Prompt de instrucciones recortado (PROMPT_LEAN): sin mejora medible; un cierre de venta cayó a fallback; revertido.
6. Precalentado del caché de catálogo y FAQ al arranque: activado.
7. Logueo de tokens por llamada del solver: entrada 2.000 a 7.000 tokens; gran parte de caché (cache hit 3.840 a 6.400); salida 21 a 188 tokens.
8. Botón de diagnóstico (endpoint /admin/diag-latencia que mide una llamada pelada a DeepSeek desde dentro de Cloud Run): 0,8 a 1,5 s de forma consistente, incluso cuando el flujo completo tarda 40 a 60 s. Con esquema de herramientas: 0,9 a 1,5 s.
9. Reintentos: se buscó en logs reintentos de red (tenacity) y del interpretador por JSON inválido: cero en ambos. El interpretador resuelve en una sola llamada.
10. Compresión del historial conservando productos y precios: prueba de no perder datos 8/8; batería interna 11/11; en producción un mensaje ofreció productos para un artículo inexistente y pidió datos sin mostrar precio.
11. Memoria reducida a 1 turno (HISTORY_LIMIT=1): interpretador 10 a 17 s, solver 11 a 22 s.
12. Medición pareada (mismo mensaje, mismo instante): interpretador 1,5 s, solver 14,6 s, botón pelado simultáneo 1 s.
13. Desglose de una respuesta del solver: 2 llamadas, de 3.982 y 6.449 tokens de entrada, que tardaron 7,3 y 6 s.
14. Configuración combinada final (PROMPT_LEAN + compresión de historial + atajo de saludo, todos activos): solver 15 a 41 s, total 45 a 53 s; llamadas individuales del solver 5,6 a 11,8 s con 2.357 a 4.394 tokens de entrada; el interpretador en esas mismas varió entre 3 y 18 s.

## Datos de referencia
- Catálogo: 50 productos, 22 FAQ.
- El solver hace entre 2 y 5 llamadas al modelo por mensaje.
- Cada llamada del solver manda entre 2.000 y 6.500 tokens de entrada.
- El interpretador hace 1 llamada.

## Cambios que quedaron en el código (detrás de flags, reversibles)
- SALUDO_DIRECTO: atajo que responde saludos sin invocar el solver.
- PRECALENTAR_CACHE: precarga catálogo/FAQ al arranque.
- SOLVER_HISTORIAL_LEAN + SOLVER_HIST_MAXCHARS: comprime mensajes largos del historial conservando productos/precios.
- PROCESAR_EN_REQUEST: procesa el mensaje dentro del request.
- OpenAI cableado como provider opcional (LLM_PROVIDER=openai), claves en config.
- Logueo de tokens (prompt_tokens/completion_tokens/cache_hit) en el evento agent_llm_call.
- Endpoint /admin/diag-latencia (ampliado con 5 variantes que aíslan factores).

## CAUSA RAÍZ CONFIRMADA (2026-06-01)
El procesamiento corre en segundo plano (FastAPI BackgroundTask, después de que el webhook responde 200 a Telegram) y Cloud Run estrangula la CPU una vez respondido el request. El flujo pesado (interpretador + solver multi-iteración + verificador + leads) se arrastra con la CPU estrangulada.

Prueba pareada definitiva:
- Con CPU throttling (default): solver 69,6 s, total 85 s.
- Con `--no-cpu-throttling` (CPU siempre asignada): el MISMO flujo dio solver 3 s, total 6 s.
- El botón de diagnóstico, replicando el peso completo del solver (system grande + historial + esquema de herramientas, 4.917 tokens), da 1,2 s, porque corre dentro de un request activo (CPU plena).

Quedó descartado: payload, tokens, historial, prompt largo, herramientas, tool_choice, modelo, red, distancia a Asia, rate limit, reintentos.

Por qué antes (mayo) no pasaba: el flujo era más liviano, el poco trabajo en segundo plano terminaba antes de sentir el estrangulamiento.

## Opciones de solución (de gratis a paga)
1. PROCESAR_EN_REQUEST=true: procesar dentro del request, CPU plena, sin pagar always-on. Gratis. Re-confirmar (medición previa salió sucia).
2. minScale=0 + lo anterior: no pagar instancia idle; solo cold start en la primera tras inactividad.
3. Cloud Tasks: webhook encola y responde ya; una tarea procesa en un request activo. Robusto, requiere setup.
4. --no-cpu-throttling + minScale=1: siempre rápido, ~50-65 USD/mes.

El "fallback técnico" era consecuencia de la demora (timeout de 45 s), no causa; al bajar el solver a 3 s desaparece.
