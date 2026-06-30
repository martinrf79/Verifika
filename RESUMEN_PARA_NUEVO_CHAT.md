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
4. **Filtro determinista** (`verificador.py`) — ENFORCE por autocorrección (flag
   `AUTOCORRIGE_MONTOS`, default true). El MISMO motor de las tools que le dio los números
   al solver audita su respuesta: si el solver cambió un total y la verdad está en el PROOF,
   el código reescribe la cifra por la buena, sin LLM; si ya está bien, pasa intacta. Es una
   sola función (`autocorregir_montos`), ANCLADA AL CONCEPTO: clasifica cada cifra por contexto
   y la corrige con el pool de ESE concepto. Cubre total (banda 15%), envío (banda 50%, pool de
   cotizar_envio) y precio de producto (anclado al NOMBRE que nombró el solver, no a la cercanía
   numérica). Cada corrección loguea su `concepto`. Pendiente: la reescritura de texto FAQ que
   no es una cifra (garantía, devoluciones) y existencia de producto.
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
- **Observabilidad (arreglado 29-jun)**: la app loguea con structlog y ahora emite el campo
  `severity` que Cloud Logging entiende (antes mandaba solo `level`, todo caía en DEFAULT y
  cualquier consulta `severity>=INFO` lo descartaba: estuvimos ciegos sin saberlo). Para leer
  logs sin gcloud local: disparar el workflow `diagnostico.yml` (Run workflow, severity INFO,
  freshness 1h) y Claude lee la salida del job. Claude NO puede dispararlo (403, sin permiso
  Actions de escritura); lo dispara Martín. El workflow sanitiza los inputs.

## Cambios deployados el 29-jun (probados offline, vivos en main)

1. **Corrector determinista anclado al concepto** (`verificador.py`): además de totales,
   corrige precio (anclado al NOMBRE del producto) y envío. Bancos `prueba_autocorrige` y
   `prueba_autocorrige_concepto` en verde.
2. **Logger** (`logger.py`): emite `severity`/`message`, conserva `event`. Ver Observabilidad.
3. **Bug de cierre por "mercado pago"** (`leads.py`): `_RE_PIDE_LINK` matcheaba el NOMBRE del
   medio de pago, así que nombrar "mercado pago" en una cotización forzaba el cierre y pedía
   datos en vez de mostrar el presupuesto (trace a1f2ea32). Ahora el regex solo reconoce un
   pedido REAL de link. CAUSA DE FONDO sin resolver: la decisión de cierre la toman TRES
   jueces que se pisan (intérprete `decision_compra`, regex `_RE_PIDE_LINK`, detector legacy
   `detectar_intencion`); conviene unificarlos en UN motor alimentado por el intérprete.
4. **Preview de respuesta en logs** (`interprete_libre.py`): el evento `interprete_libre_ok`
   ahora lleva `respuesta_preview` (300 chars). Antes el texto que el bot CONTESTA no quedaba
   en Cloud Logging y se diagnosticaba a ciegas. Leer con: filtro `jsonPayload.event="interprete_libre_ok"`,
   formato `value(timestamp,jsonPayload.trace_id,jsonPayload.respuesta_preview)`.

## ENVÍO — bug de zona RESUELTO (commit 16fce67, 29-jun)

`cotizar_envio` quedó como ÚNICA fuente del costo de envío. `calculate_total` ya no elige
zona ni concepto: cuando el total incluye envío, le pide el monto a `cotizar_envio` con el
subtotal real y lo cobra una vez por destino. El corrector dejó de tratar el envío como
total candidato. Banco `prueba_envio_calculadora` 9/9. El síntoma viejo (costo de envío que
cambiaba turno a turno y zona equivocada a Córdoba) ya no aplica.

## CIERRE — unificado y aditivo (commit nuevo, 30-jun)

Se borraron los TRES jueces que se pisaban: ahora la decisión de cierre la toma UN solo juez,
el interpretador (`decision_compra` con confianza ≥ 0.85). Fuera el regex `_RE_PIDE_LINK` y el
detector legacy `detectar_intencion`. Cuando hay interés pero NO decisión confirmada y recién
se mostró un precio NUEVO, el bot suma una pregunta suave de cierre ("¿Te parece si avanzamos
con la compra?"); un "sí" vuelve como `decision_compra` y cierra. Ante duda, todo cae en la
pregunta, no en un juez paralelo.
El cierre es ADITIVO y tiene modalidad por tienda (`MODO_CIERRE` en config.py, pisable con la
config `modo_cierre` en Firestore): `venta` (capta el lead + manda link de Mercado Pago),
`lead` (capta el lead y avisa al usuario, sin link) y `off` (no actúa; el bot vende igual).
Default `venta`. Pendiente a futuro dentro de `venta`: datos de cuenta bancaria/CBU como
segunda opción al link.

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

1. **COSTO DeepSeek (prioridad nueva, 29-jun)**: hubo un disparo de gasto. Hay VARIAS llamadas
   LLM por turno (intérprete + solver + extractor de datos que se prende ante cualquier número
   + reintentos del intérprete por JSON malo + modo "pensante" de DeepSeek que quema tokens).
   Leer el evento `llm_usage` (cuántas llamadas y tokens por turno) y capar: apagar pensante,
   frenar reintentos, prender el extractor solo cuando hace falta. Es config, no toca la
   interpretación. Va ANTES del motor de intenciones.
2. ~~**Motor de decisión de cierre unificado**~~ HECHO (30-jun): un solo juez (el intérprete) +
   pregunta suave de cierre + modalidad por tienda (`MODO_CIERRE`). Ver sección "CIERRE".
3. **Ampliar la autocorrección** a lo que NO es una cifra: texto de FAQ (garantía,
   devoluciones) y existencia de producto. Total, envío y precio ya se corrigen.
4. **Calidad de interpretación / deducción** (NORTE del proyecto): el bot dejó de deducir
   bien casos simples (ej: 6 ítems en 3 envíos, deducir qué va al tercer destino). Es
   razonamiento del modelo, no lo causaron los cambios deterministas. Es el objetivo madre;
   atacar después de estabilizar costo y envío.
4. **Seguridad**: el bot loguea el cuerpo crudo del webhook de WhatsApp (`whatsapp_webhook_received`,
   `message_received`); recortar para no guardar datos sensibles. Rotar `MP_ACCESS_TOKEN` y
   `OPENAI_API_KEY` si siguen en texto plano.
5. **Bajar la config de Cloud Run al código** (`config.py` manda; el servicio solo lleva
   secretos + `TIENDA_ID`).

## Probar en el entorno de Claude

`bash scripts/setup_test_env.sh` (lo corre el hook de SessionStart). Después
`python3 scripts/smoke_logica.py` corre la lógica determinista offline (envío, verificador,
calculadora). Acá NO hay LLM ni Firestore: el intérprete y el solver se prueban en WhatsApp
o leyendo logs de Cloud Run.
