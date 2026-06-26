# Estado del sistema — fuente ÚNICA de verdad

Este es el único documento de estado. `CLAUDE.md` tiene las reglas e instrucciones
permanentes; acá vive QUÉ es el sistema hoy. Si algo viejo contradice esto, manda esto.

## Un solo camino

Entrada → `orchestrator.process_message` → `app/core/interprete_libre.py`, que hace
todo el turno:

1. **RESET_CODE** (`verifika2026`): borra la conversación. Es solo para pruebas. El bot
   mantiene CONTINUIDAD siempre; NUNCA resetea con frases naturales tipo "nueva compra".
2. **Intérprete** (DeepSeek, `interpretador.py`): entiende el mensaje en contexto. Se
   loguea (`interprete_libre_interpretacion`), no se muestra al cliente.
3. **Solver libre** (DeepSeek, `agent.run_agent`): vende libre con las tools atadas a
   Firestore: search_products, get_product_details, list_catalog, query_faq,
   calculate_total, cotizar_envio. La lista la fija `MODO_LIBRE_TOOLS` en config.
4. **Filtro determinista** (`verificador.py`) — HOY EN MODO OBSERVACIÓN: loguea las
   cifras de plata sin respaldo (`..._shadow`), NO bloquea. Falta afinarlo y volver a enforce.
5. **Cierre** (`leads.py` + `cierre.py` + `pago.py`): capta el lead, junta datos y genera
   el link de Mercado Pago con el total VERIFICADO de la calculadora.
6. **Memoria**: historial (10 turnos) + estado + último presupuesto + proofs, en Firestore
   por usuario.

## Infra

- Cloud Run: `agente-bot`, región `southamerica-east1`, proyecto `memory-engine-v1`. Es el
  ÚNICO servicio de bot. El webhook de WhatsApp apunta ahí.
- `video-engine`: otro producto, apagado (min-instances 0). No se toca.
- Deploy: push a `main` dispara CI (`.github/workflows/deploy.yml`) y deploya a `agente-bot`.
  Respaldo: `./deploy.sh`. Verificar el verde antes de decir "listo".
- Rama viva = `main`. Las ramas `claude/*` son para revisar antes de mergear.
- LLM: DeepSeek en todo (`LLM_PROVIDER=deepseek`). Nada de Gemini sin OK de Martín.

## Datos: un solo catálogo, una sola FAQ

- Producción son **880 productos**. Viven en `data/clientes/verifika_prod/`
  (`productos.csv` enriquecido + `faq.json` de 44 temas). Es la ÚNICA fuente.
- El repo es la fuente; se sube a Firestore por `/admin/upload-catalog` y
  `/admin/upload-faq`. Firestore es la copia que lee el bot vivo.
- Se borraron los fixtures `verifika_2k` (2000 sintéticos) y `verifika_demo`, más
  sus generadores. NO regenerar el catálogo ni crear otros fixtures.
- Se asume que Firestore no cambió desde el 17-jun (el conteo de 880 coincide). Si
  hay duda, comparar el repo contra un export de Firestore.

## Pendientes (en orden)

1. **Conectar el intérprete al solver.** Hoy lo que el intérprete entiende casi no gobierna
   la respuesta: llega como un susurro de texto y el `estado_conversacion` ni se le pasa al
   solver. Objetivo del chat actual.
2. **Afinar el filtro determinista** sobre los logs `_shadow` y volver a enforce. Hoy solo
   cubre plata; ampliar a existencia de producto.
3. **Bajar la config de Cloud Run al código** (`config.py` manda; el servicio solo lleva
   secretos + `TIENDA_ID`).
4. **Seguridad**: rotar `MP_ACCESS_TOKEN` y `OPENAI_API_KEY` si siguen en texto plano.

## Probar en el entorno de Claude

`bash scripts/setup_test_env.sh` (lo corre el hook de SessionStart). Después
`python3 scripts/smoke_logica.py` corre la lógica determinista offline (envío, verificador,
calculadora). Acá NO hay LLM ni Firestore: el intérprete y el solver se prueban en WhatsApp
o leyendo logs de Cloud Run.
