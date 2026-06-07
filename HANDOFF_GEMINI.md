# HANDOFF — estado, lección y plan (para seguir con Gemini)

Autocontenido. Lo que hay que entender para retomar sin contexto previo.

## TL;DR

El bot tiene un piso de seguridad sólido (no inventa precio, día de entrega ni
servicios — todo bloqueado por código determinista, rápido y barato). El
problema NUNCA fue la calidad del bot. Fueron dos cosas: (1) la latencia en
Cloud Run, y (2) una vara de éxito imposible ("0 fallas en una batería
adversaria"). El camino para salir no es más verificadores: es arreglar la
latencia, salir a producción con el piso barato + escalar a humano, y aprender
de charlas reales.

## Qué pasó en producción (incidente, ya resuelto)

Se deployó el código nuevo y se prendieron TODAS las flags juntas. Resultado:
latencia >1 minuto y respuestas que caían al fallback. Causa: CHECKER_GATEA suma
2 llamadas de modelo por turno, AUTOFIX agrega otra pasada del solver, y todo eso
sobre el CPU throttling de Cloud Run explota.
ROLLBACK hecho: el tráfico se mandó a la revisión `agente-bot-00156-n6b`
(estable, del 04-jun, código viejo sin flags nuevas) con:
`gcloud run services update-traffic agente-bot --region southamerica-east1 --project memory-engine-v1 --to-revisions=agente-bot-00156-n6b=100`

## Qué se construyó esta sesión (todo detrás de flags, default OFF = prod intacto)

Arquitectura: política (constitución, declarativa) + mecanismo (verificadores,
código) + puente por gravedad. Idea: el modelo es libre en la FORMA, nunca en el
HECHO.

Flags nuevas (app/config.py):
- PROMPT_CONSTITUCION: inyecta la constitución como preámbulo del prompt del solver.
- PROMPT_VENTA: ya existía; ahora query_faq además devuelve `sugerencia_venta` (la
  capa de venta de la FAQ, campo `venta`, antes era dato muerto).
- ESTADO_NO_REGRESA_SALUDO: guard anti pierde-el-hilo (una charla en curso no
  vuelve a "saludo"; arregla el "¡Hola! Soy vendedor..." a mitad de charla).
- CIERRE_FORZADO_MAX_ITER: al agotar iteraciones, cierra con lo que tiene en vez
  de tirar "tuve un problema técnico".
- CHECKER_GATEA: el GATE GENERAL. Revive el Checker de Verifika (Proposer+Checker
  LLM) como mecanismo general de grounding, gobernado por gravedad
  (app/core/gate_gravedad.py). CARO: +2 llamadas LLM por turno. Sacar del camino
  del cliente o correr offline.

Endurecimientos por código:
- verificador_hechos.py: caza promesa-de-día con hedge posterior y verbo "dejar"
  ("te lo deja mañana martes").
- checker.py (regla 11): negar o ser más conservador que la evidencia NO es
  contradicha (arregla falsos positivos donde el bot se abstiene bien).
- proposer.py: rescata afirmaciones de JSON truncado + max_tokens 1200.
- gate_gravedad.py (NUEVO): bloquea contradicha de cualquier tipo, y sin_evidencia
  SOLO de tipo `producto` (caza producto inventado tipo "Dragonborn" sin regex).
  Política: nunca bloquear por ausencia de evidencia salvo nombre de producto;
  lo demás lo cubren los deterministas o la señal fuerte (contradicha).
- simulador_multiturno.py: el JUEZ ahora se ancla a la FAQ real de la tienda (antes
  tenía hardcodeados servicios de la demo y juzgaba mal a prod).

Tests deterministas (gratis, sin LLM, TODOS VERDES — correr siempre antes de tocar):
bateria_robustez, prueba_servicios, prueba_hechos (12/12), prueba_faq_directo,
prueba_nucleo, prueba_cierre_orden, prueba_estado_regresion, prueba_gate_gravedad,
prueba_proposer_salvage.
Diagnóstico: scripts/diag_checker.py reproduce los turnos de un escenario grabado
por el bot real y muestra qué bloquea, sin juez ni cliente LLM (barato).

## La lección estratégica (lo más importante)

- El molino es un TERMÓMETRO, no un portón. "0 fallas adversarias" es imposible
  por diseño: el juez y el cliente atacan a propósito, la variedad es infinita,
  siempre va a faltar algo. Eso no es el bot fallando, es la vara mal puesta.
- Definición de LISTO = seguro (no inventa precio/día/servicio) + honesto (dice
  "no sé") + sabe escalar a un humano. NO perfecto. Los productos de esta clase
  que andan aceptan que 20-30% de charlas escalen, y eso es el producto funcionando.
- El piso de seguridad YA está hecho y es lo difícil. Lo demás es pulido, y el
  pulido sale de charlas REALES, no de la batería sintética.
- El único bloqueante real es la LATENCIA.

## Plan para retomar con Gemini (en orden)

1. LATENCIA primero (es el bloqueante real). Cloud Run CPU throttling: poner
   `--no-cpu-throttling` al servicio, o PROCESAR_EN_REQUEST=true + minScale. Medir
   que un turno simple baje a <10s. Sin esto, no prender nada.
2. Deploy del código nuevo y prender SOLO las flags baratas, UNA POR VEZ, midiendo
   latencia entre cada una: VERIFICADOR_MODE=on, VERIFICADOR_HECHOS=on,
   VERIFICADOR_SERVICIOS=on, ESTADO_NO_REGRESA_SALUDO=true,
   CIERRE_FORZADO_MAX_ITER=true, PROMPT_CONSTITUCION=true, PROMPT_VENTA=true.
   Estas NO agregan latencia (son código o prompt).
3. NO prender CHECKER_GATEA ni AUTOFIX en el camino del cliente al principio. Son
   los caros. Dejarlos para después, o correr el Checker offline como monitor.
4. Salir a producción así y juntar charlas REALES (logs con trace_id). Cada falla
   real, que van a ser pocas, se tapa con una pieza + un test. Eso SÍ tiene fin.
5. El molino, una corrida semanal como termómetro, no como gate.

## Reglas de deploy (aprendidas a los golpes)

- Una flag por vez, NUNCA todas juntas.
- Arreglar el throttling ANTES de prender algo caro.
- Rollback = `gcloud run services update-traffic ... --to-revisions=REV=100`
  (instantáneo, revierte código Y env vars a esa revisión).
- OJO: Cloud Shell `~/agente-v4` es una COPIA aparte, NO el repo real. El repo de
  verdad está en la PC (Windows): `C:\Users\marti\Downloads\claude code verifika\agente-v4`.

## Rutas y datos

- Catálogo de prod: `data/clientes/verifika_prod/productos.csv` (880 productos).
- FAQ de prod: `data/clientes/verifika_prod/faq.json` (22 ítems; 5 con campo `venta`).
- `data/productos.json` = fixture viejo de 100, NO se usa.
- Repo: github.com/martinrf79/Verifika
- Cloud Run: servicio `agente-bot`, región southamerica-east1, proyecto memory-engine-v1.
- Pendiente de dato real (no inventar): el ítem `redes` de la FAQ apunta a
  "verifikademo", hay que poner el handle/web real de prod.
