# Resumen para el chat nuevo — estado al 25-jun-2026

Este doc MANDA sobre el estado actual. `CLAUDE.md` y `MAPA_SISTEMA.md` describen
la etapa ANTERIOR (cuatro caminos, ~70 flags, SOLO_INTERPRETE): quedaron viejos
tras la consolidación de hoy. Guiarse por ESTE doc.

## Qué es el bot hoy: UN solo camino

Entrada → `orchestrator.process_message` (despachador mínimo: anti-jailbreak +
delega) → `app/core/interprete_libre.py`, que hace todo el turno:

1. **RESET_CODE**: si el mensaje es exactamente `verifika2026`, borra la
   conversación y confirma. Es la palabra de PRUEBA para arrancar de cero. El bot
   NUNCA resetea con frases naturales ("nueva compra"): continuidad siempre.
2. **Intérprete** (DeepSeek): entiende el mensaje en contexto. La interpretación
   se loguea (evento `interprete_libre_interpretacion`), no se muestra al cliente.
3. **Solver libre** (DeepSeek, `agent.run_agent`): vende libre con las tools
   atadas a Firestore: search, get_product_details (ficha), list_catalog,
   query_faq (FAQ), calculate_total (calculadora), cotizar_envio (envío). La lista
   la fija `MODO_LIBRE_TOOLS` en config.
4. **Filtro determinista** (`verificador.py`) — HOY EN MODO OBSERVACIÓN: loguea
   las cifras sin respaldo (evento `interprete_libre_numero_no_respaldado_shadow`)
   pero NO bloquea. El bloqueo+autofix se sacó porque era lento y cortaba ventas
   legítimas a fallback. Volver a enforce recién cuando esté afinado sobre logs.
5. **Cierre** (`leads.py` + `cierre.py` + `pago.py`): capta el lead, avisa al
   dueño, junta nombre/teléfono/dirección/pago, y genera el link de Mercado Pago
   con el total VERIFICADO. Necesita `config/mp_access_token` en Firestore o
   `MP_ACCESS_TOKEN` por entorno para el link.
6. **Memoria**: historial de texto (últimos 10 turnos) + estado + último
   presupuesto + proofs recientes, en Firestore por usuario.

## Infra (sin cambios)

- Servicio Cloud Run: `agente-bot`, región `southamerica-east1`, proyecto
  `memory-engine-v1`. Es el ÚNICO. Webhook de WhatsApp apunta ahí.
- Deploy por CI: push a `main` dispara `.github/workflows/deploy.yml` y deploya a
  `agente-bot`. Verificar el verde antes de decir listo.
- Rama viva = `main` (todo el trabajo del 25-jun ya se mergeo, el trigger apunta a
  main). Las ramas claude/* son para revisar antes de mergear.
- LLM: DeepSeek en todo. `LLM_PROVIDER=deepseek`.

## La consolidación de hoy (Fase B)

- De 60 a 24 módulos en `app/core`: se borraron los 4 caminos paralelos
  (modo_libre, camino_nuevo, nucleo, legacy), su cañería, los verificadores
  legacy y el Checker LLM (verifika/proposer-checker-pipeline).
- De 110 a 59 campos en `config.py`: se podaron 52 flags muertos.
- Se conservan: anti-jailbreak (cableado, activo) y posventa/garantía (código
  presente, no expuesto al solver todavía).

## Cómo probar en el entorno de Claude

`bash scripts/setup_test_env.sh` (lo corre solo el hook de SessionStart) instala
deps y arregla cffi. Después:
- `python3 scripts/smoke_logica.py` corre la lógica determinista offline (envío,
  verificador, calculadora). Sin Firestore ni LLM.
- Se puede importar TODO el app para verificar que no hay imports rotos.
- Lo que NO se puede acá: llamadas reales a Firestore o al LLM (faltan claves).
  El intérprete y el solver se prueban en WhatsApp.
- Logs de runtime del bot: Claude NO los ve. Pedir a Martín la salida de
  `gcloud logging read 'resource.type="cloud_run_revision" AND
  resource.labels.service_name="agente-bot" AND severity>=WARNING'
  --project=memory-engine-v1 --limit=40 --freshness=30m`.

## Pendientes (orden sugerido para el chat nuevo)

1. **Limpiar env de Cloud Run**: sacar las ~63 vars de flags muertos de
   `agente-bot` (ya están ignoradas por el código; es higiene). Comando entregado.
2. **Segunda pasada de flags legacy**, dentro de `agent.py`, `interpretador.py` y
   `tools.py` (ej `DIRECTOR_LLM`, `CONFIRMACION_PROVIDER`, `PROMPT_VENTA`,
   `PROMPT_LIGERO`, `PROMPT_CONSTITUCION`, `LIBRO_*`, `TOOLS_MINIMAS`,
   `CIERRE_FORZADO_MAX_ITER`, `RESCATE_TOOLCALL_TEXTO`). Varios están PRENDIDOS en
   prod, así que sacarlos cambia el prompt del intérprete/solver: hacerlo con el
   harness, verificando, no a ciegas. NO tocar `FECHA_ENTREGA`/`POSVENTA_TOOLS`
   (posventa se conserva).
3. **Afinar el filtro determinista** sobre los logs `_shadow` y recién ahí volver
   a enforce (sin el autofix romo: un diseño mejor).
4. **Errores abiertos a diagnosticar con logs**: latencia y algún fallback que
   Martín reporte. La causa del fallback anterior era el filtro+autofix, ya sacado.
