# Estado del sistema — fuente ÚNICA de verdad

Este es el único documento de estado. `CLAUDE.md` tiene las reglas e instrucciones
permanentes; acá vive QUÉ es el sistema hoy. Si algo viejo contradice esto, manda esto.

**Última actualización: 3-jul-2026.** Sesión larga de blindaje determinista + reorganización
con pytest/CI. Todo lo de abajo está deployado y verificado en verde salvo lo marcado como
PENDIENTE.

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
- **PENDIENTE (bug conocido):** en multi-destino el envío gratis se calcula sobre la SUMA de los
  destinos, no por destino. En envíos separados el umbral debe mirar cada destino. (Visto en real:
  4 destinos chicos → "todo gratis" incorrecto.)

## CIERRE — modo A (lead) vivo (3-jul)

Un solo juez: el interpretador (`decision_compra` con confianza ≥ 0.85) + pregunta suave de
cierre + gatillo determinista por respuesta a la pregunta. Modalidad por tienda (`MODO_CIERRE`
en config.py, pisable con Firestore `modo_cierre`):

- **`A` / `lead` (DEFAULT ACTUAL):** el cliente confirma → capta el lead fuerte, avisa al dueño
  y **sigue iterando SIN pedir datos** (nombre/teléfono/documento). El lead fuerte ya se logra
  captando + avisando; cierra un humano. Si ya hay lead fuerte activo, no re-avisa.
- **`B` / `venta`:** el bot cierra y manda el cobro (link de Mercado Pago o CBU).
- **`off`:** no actúa; el bot vende igual.

**DECIDIDO, PENDIENTE de implementar:** la **pregunta del sistema debe mandar sobre el score de
intención**. Un "sí" a una pregunta bien formulada dispara el lead; no depender del score de
`decision_compra`. Es la forma más simple y abarcativa. (En una charla real el lead disparó por
score, no por la pregunta, porque la pregunta de cierre exacta no apareció.)

## FAQ — endurecido (3-jul)

Ruteo determinista por keywords (`query_faq`): el tema ESPECÍFICO le gana al genérico (score por
la keyword más específica, no la suma) y la puntuación no rompe el match ("pago contra entrega?"
rutea bien). Locks en `tests/test_faq.py`.
**PENDIENTE:** que las FAQ con NÚMERO (precios, %, plazos) se estampen del valor estructurado, no
que el modelo las parafrasee.

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
- **Cobertura:** hoy ~70% de las afirmaciones de hecho garantizadas (precio, total, envío,
  identidad, promesas). Techo útil ~90-95% aplicando el patrón a stock/disponibilidad, FAQ
  numérica y guardas de salida. El ~5-10% restante es irreducible (abierto, del LLM).
- **Diferenciador vendible:** "un bot de ventas que no puede mentir sobre precio, stock ni total
  porque el código lo garantiza". No prometer conversación impecable (es del LLM); prometer que
  no miente en los números.

## Hallazgos de pruebas reales (2-jul)

- **Cero alucinaciones de PRECIO/total** en dos charlas reales largas: todos los precios, stocks
  informados coincidentes y cuentas correctas venían de la fuente. El blindaje de plata funcionó.
- **Hueco de STOCK (por acá se filtró):** el solver inventó faltantes ("DX-110 no tiene stock",
  "Zeus X no tiene stock" — falso, tenían) y upselleó a lo caro; y eligió mal "el más barato con
  stock". El verificador cubre la plata, NO la disponibilidad. Es el próximo campo a blindar.

---

## PENDIENTES (en orden de prioridad)

1. **Enforcer de STOCK (calculadora)** — donde una alucinación llegó al cliente. Dos piezas del
   mismo patrón:
   - **Pieza 1:** "más barato con stock" DETERMINISTA (el código lo computa por categoría, filtro
     `stock>0` ordenado por precio; extender `find_within_budget`). El solver usa ese, no elige.
     Diseño acordado: inyectarlo como GUÍA determinista, no como tool opcional.
   - **Pieza 2:** verificador de afirmación de stock (safe-override): detectar "sin stock / N
     unidades" atado a un producto y pisar si contradice el catálogo.
2. **FAQ numérica**: estampar los números de la FAQ desde el valor estructurado, no parafrasear.
3. **Guardas de salida (baratas):** malas palabras (blocklist + reescritura, ej. "al pedo") y
   **disclaimer legal** (aclarar que es una herramienta automática; determinista: línea fija en el
   primer mensaje + gatillo regex sobre "sos humano/quién sos/con quién hablo"). El prompt solo ya
   falló en real.
4. **Cierre**: la pregunta del sistema manda sobre el score (ver CIERRE).
5. **Envío multi-destino**: envío gratis por destino, no por la suma (ver ENVÍO).
6. **Confirmar el disparo del lead** por logs (qué camino disparó: `lead_decision_via_interpretador`
   vs `cierre_gatillo_determinista_fuerte`).
7. **Sugerencias externas de Martín** para FAQ y calculadora (las trae al chat nuevo).
8. Costo DeepSeek (varias llamadas LLM por turno), seguridad (recortar log del webhook, rotar
   tokens): pendientes de arrastre, atacar cuando toque.

**Metodología no negociable al tocar cada herramienta:** primero escribir el test que captura el
comportamiento bueno de HOY, después cambiar. El gate del CI + el test lockean contra regresión.

---

## Probar en el entorno de Claude

`pytest` corre los 122 tests offline (Python puro, catálogo+FAQ reales por la fixture
`firestore_doble` en `tests/conftest.py`, sin LLM ni Google). El intérprete y el solver (DeepSeek)
NO corren offline (van marcados `vivo`, excluidos por default); se prueban en WhatsApp/Telegram o
leyendo logs de Cloud Run.
