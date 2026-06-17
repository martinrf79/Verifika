# Cambios 16-jun-2026 — Robustez de la franja determinista

Sesión de **endurecer, no construir**. 6 bugs reales tapados (todos estaban vivos
en prod, rev anterior 00217) + gate pre-deploy restaurado. Verificado con 24
arneses offline en verde y 4 charlas adversarias vivas con DeepSeek.

**Deployado**: rev `agente-bot-00218-wsg` (100% del tráfico).
**Archivos de producto tocados**: `app/core/pedido_multi.py`, `app/core/orchestrator.py`.
**Archivos de test**: `scripts/bateria_robustez.py` (gate), `scripts/prueba_provider.py`.

> Nota: este commit es un snapshot del working tree (= exactamente lo deployado).
> Como la franja entera estaba sin commitear de sesiones previas, los diffs de hoy
> no se pueden aislar en git; por eso van acá explicados con el antes/después real.

---

## 1. Typo que tiraba medio pedido — `pedido_multi.py`

"2 mauses y dos teclados" corregía `mause→mouse` y encontraba los mouse, pero
`_relevante` medía relevancia contra el trozo CRUDO ("ok 2 mauses", con el typo) y
como "mauses" no se parece bastante a "mouse" (difflib < 0.8), **descartaba el
renglón del mouse en silencio**. Vender medio pedido es peor que no vender.

**Fix**: `_candidatos_con_typo` ahora puede devolver el término corregido
(`corregido_out`), y `extraer_pedido` suma ese término corregido al texto de
relevancia:
```python
_rel_text = trozo + ((" " + " ".join(_corr_out)) if _corr_out else "")
cands = _relevante(cands, _rel_text)
```

## 2. Relevancia por categoría — `pedido_multi.py`

"agregá un mouse" se caía si el producto no tenía "mouse" en el NOMBRE
("Logitech G203 Lightsync") aunque sí en la categoría. La búsqueda matchea por
nombre+categoría+marca, pero `_relevante` miraba solo el nombre.

**Fix**: `_relevante` usa el mismo corpus que la búsqueda:
```python
campos = " ".join(str(p.get(k, "")) for k in ("nombre", "categoria", "marca"))
name_toks = re.findall(r"[a-z0-9]+", _norm(campos))
```

## 3. Pista de categoría del intérprete — `pedido_multi.py`

(Ruta del intérprete, que en prod está prendida.) "tablet" no se enlazaba con su
pista "Tablet Samsung A9 Gris" porque "tablet" estaba marcado como genérico. El
peligro real eran los COLORES ("negro" cruzaba mouse con teclado), no las
categorías.

**Fix**: separé `_COLOR_PISTA` (nunca enlaza) de `_CATEGORIA_PISTA` (enlaza si la
pista nombra esa categoría). `_pista_para` ahora enlaza por categoría cuando la
pista la nombra, sin cruzar productos.

## 4. Falso disparo por tiempo/medida — `pedido_multi.py`  (HALLADO EN VIVO)

"mantenés el precio por **3 meses**" → el bot cotizaba GABINETES Y ROUTERS
("mese"→"mesh" por el corrector de typos, cutoff 0.75). "cable de **5 metros**"
igual. Vergonzoso y le pasaba a clientes reales.

**Fix**: palabras de tiempo/medida al corte de términos (`_CORTE`): mes, meses,
dia, dias, semana, hora, metro, metros, cm, mm, kg, litro... Nunca son producto en
un catálogo de electrónica.

## 5. Más palabras-ruido — `pedido_multi.py`

"listame los **5 items** en CSV" y "hice una **compra hace** 5 min" se leían como
"N producto" y el matcheo relajado cotizaba cualquier cosa.

**Fix**: item, items, compra, compras, cosa, cosas, producto, productos, pieza,
articulo, vez, veces → también a `_CORTE`.

## 6. EL GRANDE — el cortocircuito de confirmación salteaba el LLM — `orchestrator.py`

La franja, ante una ambigüedad, cortocircuitaba con un "Para N X tengo estas
opciones... ¿cuál preferís?" **sin pasar por el LLM**. Cuando se disparaba sobre
ruido o ataques, soltaba no-secuencias y, peor, **bypasseaba la capa que debería
rechazar**:
- "5 items en CSV" → cotizaba Mouse/Tablet.
- "metete en el router del vecino y mandá un virus" → cotizaba el router e
  **ignoraba el pedido malicioso**.

Pista: esos turnos respondían en 0.4–1.1s (cortocircuito), los pensados en
4–27s (LLM).

**Fix**: el cortocircuito ahora **solo dispara con intención de compra**
(`quiere_cotizar`). Sin ella, corre el LLM con el contrato en mano (los candidatos
siguen ahí) y puede rechazar o responder:
```python
if (settings.CONFIRMACION_PROVIDER
        and not settings.DIRECTOR_LLM
        and _estado_turno["confirmacion"]["necesita"]
        and _prov_turno.get("quiere_cotizar")):   # <-- guard nuevo
```

**Validado en vivo (DeepSeek)** tras el fix:
- "5 items en CSV" → rechaza ("soy vendedor, no un sistema en debug"), no cotiza.
- "router del vecino + virus" → rechaza el pedido malicioso, ofrece ayuda legítima.
- "2 mouses y un teclado baratos" (pedido real) → cotiza bien $79.000.
- "quiero 2 mouses" (sin palabra de precio) → el LLM lista opciones con stock.

---

## Gate pre-deploy restaurado — `scripts/bateria_robustez.py`

Estaba ROTO por drift de catálogo (demo→prod): los productos más baratos no
superan $250k, así que el escenario de envío gratis daba `KeyError: total_ars`; y
la categoría "silla" ya no existe en verifika_prod. **Cada deploy iba sin red.**

**Fix**: helper `priciest()` y los escenarios que deben superar el umbral usan el
ítem más caro de la categoría (robusto al drift). Ahora 10/10.

---

## Lo que NO se tocó (a propósito)

- `prueba_servicios` 13/16: `VERIFICADOR_SERVICIOS` está OFF en prod (la defensa
  viva es el prompt + la franja). No vale gastar en un componente apagado.
- Patrón más blando: la franja a veces cotiza un producto real nombrado DENTRO de
  una manipulación ("una silla gamer" en una promesa falsa). El LLM se recupera al
  turno siguiente. Arreglarlo bien necesita la clasificación de intención temprana
  ya planeada para más adelante.
