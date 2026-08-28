# FICHA 35 — La puerta. Una sesión.

Segundo tercio de `PLAN_REDUCCION.md`. La 34 ya está en `origin/main`
(`cda4fb4`): el hub no reconcilia ni repone. Esta sesión no toca el nexo.
Toca la salida: el modelo escribe una vez, el código pega la cuenta sellada
y corta lo que no está en el contrato. La higiene queda con un solo mutador.

No se junta con la 36. Si el piso baja, revert del corte, no un parche.

---

## Qué hay hoy, leído del vivo post-34

`procesar_venta` sigue corriendo las cuatro puertas, en este orden:

1. `procedencia` — ocho `_pieza` que RESTAN: atadura, sin_json, sin_markdown,
   sin_cobro_inventado, sin_negar_lo_traido, sin_afirmar_del_catalogo,
   sin_descuento_inventado, sin_narracion_interna.
2. `plata` — pega la cuenta sellada, tira el anuncio vacío, bloque entero o
   nada, hallazgo entero o nada.
3. `obligacion` — SUMA: honestidad_bot, saludo, `_punto_omitido_repuesto`,
   `camino_cobro.linea_de_cobro`.
4. `higiene` — DOS `_pieza` que reescriben: `mensaje.componer` y
   `aduana.revisar_salida`.

El test que cierra esta ficha ya está escrito y sigue en `xfail`:

`tests/test_plan_de_la_simplificacion.py` →
`test_la_higiene_tiene_un_solo_mutador`

Lee el AST de `salida.higiene` y cuenta cada llamada a `_pieza`. El objetivo
es `len(piezas) <= 1`. No pregunta si la pieza muta: **cuenta llamadas**.
Una aduana “solo log” adentro de `_pieza` deja el test rojo. Si el marcador
queda, no entra por `_pieza`.

El hub, al final del turno, todavía hace
`from app.core.aduana import marcador` y anota rojas/defectos/reparadas.
Si `aduana.py` sale de `app/` y esa línea sigue, el import explota o el
anote queda en cero para siempre. Se saca en el mismo commit.

`reposicion.py` SIGUE en `app/`: `resolver.py` y `salida.py` todavía lo
llaman. No se borra acá. Eso es la 36.

---

## Qué se hace, en este orden, en UNA sesión

### 1. Snapshot al archivo, ANTES de tocar el vivo

```
cp app/core/aduana.py archivo/aduana_20260828.py
```

Fila nueva en `archivo/README.md`. `app/` no importa `archivo/`. El candado
`tests/test_archivo.py` ya está. `.gcloudignore` y `paths-ignore` de
`deploy.yml` ya tienen `archivo/`: no se vuelven a agregar.

Si esta sesión apaga otra pieza de salida que deje de tener caller en `app/`,
el snapshot de ESA pieza va al archivo **antes** de editar el vivo, con su
fila. No se copia `salida.py` entero: tiene las cuatro puertas vivas.

### 2. La higiene queda con un solo `_pieza`

En `salida.higiene` se borra el bloque que llama a `revisar_salida`. Queda
`componer` nomás, que ya es lossless por contrato: borra lo demostrablemente
repetido, no reescribe una palabra del modelo.

`mensaje.py` NO se recorta a “dos reglas” en esta ficha. El módulo tiene
más de las cuatro originales: la 18 pagó `una_sola_pregunta` y el repaso
anunciado, y el piso de largo y de repregunta vive de eso. Achicar el
componedor por un número de reglas es reescribir la vara. Lo que se va es
el segundo mutador, no las reglas que el piso ya midió.

La aduana, si alguien cree que “queda como log”, no entra por `_pieza`.
El hub ya logueaba el marcador: esa línea se BORRA, no se deja en cero.
Los invariantes vuelven a ser instrumento del banco y de
`test_barrido_codigo.py` (`INV.revisar`): sí o no, nunca parche del mensaje
que sale. Eso ya estaba decidido el 2-ago, el 19-ago y en `DECISIONES.md` #5.

### 3. Si nadie en `app/` llama `aduana.py`, sale del vivo

Después del corte, buscar callers en `app/`:

- `salida.higiene` → `revisar_salida` (se va en el paso 2)
- `hub_venta` → `marcador` (se va en el paso 2)

Si no queda ninguno: `git rm app/core/aduana.py` en el **mismo** commit.
Copiar al archivo y dejar el original no achica nada.

`_importes` lo usan los tests del grafo y del barrido para comparar plata,
no el camino vivo. No se conserva el módulo entero por un helper. Se MUEVE
esa función a un módulo que ya queda —`invariantes.py` o `salida.py`— en el
mismo commit, y los tests se reapuntan ahí. No se duplica la regex.

`invariantes.py` NO se saca de `app/` en esta ficha. `pago.py` llama
`INV.pago_parcial`. `salida.py` usa `INV._RE_ITEM`. El banco y el barrido
del código los corren como instrumento. Apagar el parche no es borrar el
termómetro.

### 4. Reapuntar, en el MISMO commit

Estos tests y callers asumen que la aduana MUTA en el camino vivo. El día
que deje de mutar, o quedan rojos o mienten. Se tocan acá, no “después”:

- `tests/test_hub_venta.py` → `test_la_aduana_corre_en_el_camino_vivo`.
  Ese candado MUERE: el punto de esta ficha es que `revisar_salida` ya no
  corre en el turno. Se reemplaza por uno que afirma que `higiene` no
  llama a `revisar_salida` (el AST de `test_la_higiene_tiene_un_solo_mutador`
  ya cubre el conteo; este cubre que el hub no la reenchufe). El caso
  `Resumen:` huérfano lo tiene que seguir cazando `componer`
  (`sin_encabezados_huerfanos`). Si después del corte `Resumen:` fugaría,
  el piso o ese test se ponen rojos: se revierte, no se reenchufa la aduana.
- `tests/test_aduana.py`: vive con el snapshot. O se apunta a
  `archivo/aduana_20260828.py` y deja de afirmar el camino vivo, o se va
  con el módulo. No se deja importando `app.core.aduana` si ese archivo
  ya no está.
- `tests/test_barrido_codigo.py` → `test_la_aduana_no_toca_un_mensaje_sano`
  y el que lee `_ROJAS`. El combinatorio de la calculadora y de `componer`
  se queda. Lo que instancia `revisar_salida` como si fuera vivo se va o
  se apunta al snapshot. `_ROJAS` / `cobra_el_total_habiendo_sena` es
  invariante: se lee de `INV.revisar`, no hace falta el módulo de parche.
- `tests/test_grafo_cableado.py` importa `_importes`: reapuntar al nuevo
  dueño.
- `tests/test_ninguna_guardia_se_traga_una_excepcion.py` lista
  `app/core/aduana.py` en `_GUARDIAS`. Si el archivo salió, sale de la
  tupla. El test afirma el largo: se baja a mano en ese commit, con el
  motivo escrito.
- `tests/test_nada_suelto.py` declara `reiniciar_marcador`. Si la función
  desaparece, sale de `DECLARADAS`.
- `banco_pruebas/explorador.py` importa `aduana` y llama
  `reiniciar_marcador` / `marcador`. Se reapunta: sin aduana viva, esa
  ficha del explorador deja de existir o lee ceros de otro lado. No se
  deja un import a un módulo borrado.
- `app/verifika/grafo.py`, nodo `higiene`: hoy garantiza “con los
  invariantes corridos” y “las dos piezas”. Se reescribe la garantía a lo
  que queda: sin repetición, lossless, un mutador. El barrido de contratos
  sale de esta tabla: un nodo que promete lo que ya no hace miente.

El censo (`test_censo_del_grafo.py`) clava huérfanos y nodos. Si al sacar
la aduana baja un huérfano, el número se actualiza en el mismo commit con
la cuenta escrita. No se deja un nodo declarado que ya no corre.

### 5. La prosa no se reescribe. Qué se QUEDA y qué no se toca

Esta ficha no es “borrar salida.py”. Es que después del borrador del modelo
nadie vuelva a redactar. El recorte de las dieciocho piezas a “la puerta”
se termina en la 36. Acá se clava la regla y se saca el segundo escritor.

**SE QUEDA, y es prioridad uno:**

- Las ocho de `procedencia`. Restan. Son el strip de lo que no vino del
  material. No son un segundo redactor. Sacarlas acá para que un número
  baje es el defecto que la campaña prohíbe.
- La puerta `plata`: pegar `out["bloque"]` entero, tirar el anuncio vacío,
  bloque entero o nada. El hallazgo, mismo trato. Es decisión 11, bloque
  sellado.
- `honestidad_bot` y el saludo. Suman texto fijo, no reescriben al modelo.
- `camino_cobro.linea_de_cobro`. Es el cierre de la venta. La 19 lo midió.
- `_punto_omitido_repuesto`. SUMA el punto que el cliente preguntó y el
  sistema sabía. Es cobertura (`DECISIONES.md` #6), no una segunda prosa.
  El código no lee ese texto como si lo hubiera escrito el modelo
  (FICHA 21, `texto_del_modelo`). No se borra “porque el modelo escribe
  una vez”: si se borra y el piso de puntos baja, se revierte.
- `componer`, entero, como único mutador de higiene.
- `texto_del_modelo` antes de las puertas. No se toca esa frontera.

**NO SE TOCA en esta ficha:**

- Fusionar `_CUERPOS` (31/32/36).
- Borrar `reposicion.py` o inlinear sus helpers en el resolver.
- `data/clientes/`, `requirements.txt`, la clave paga, Mercado Pago.
- Los termómetros 181 / 7306. Cierran en la 36.
- Subir `tests/plan_techo.json`. Al cerrar el xfail de higiene el techo
  **baja** en ese mismo cierre, un entero, con la cuenta escrita. Hoy está
  en 18. No se sube. No se mueve en el commit del corte “para que dé”.
- Reescribir un test para que pase. El de higiene ya afirma lo correcto.
- FICHA 24 y 29. Siguen sin test propio.
- Verificar producción por WhatsApp. Martín lo mira después de toda la
  reducción. La red de esta sesión es el piso de las 15 charlas.

Si entra de yapa y el piso no baja, se le saca la marca a
`test_el_catalogo_tiene_una_sola_puerta_interna` o
`test_la_plata_tiene_una_sola_puerta_interna`. No se trabajan aparte.
No se fuerza.

### 6. Verificar, y si el piso baja se revierte entero

```
python3 -m pytest -q
```

Tiene que pasar, y hay que sacarle la marca:

- `test_la_higiene_tiene_un_solo_mutador`

Al sacarla, `tests/plan_techo.json` baja de 18 a 17 en ese cierre. El
techo solo baja. `strict=True`: si el test pasa y la marca sigue, la
batería se pone roja. Eso es el aviso, no un defecto.

El piso de `banco_pruebas/casetes/_piso.json` no baja. Puntos, llamadas,
largo, camino al cobro. Si baja, `git revert` del commit del corte, no un
parche. El snapshot en `archivo/` se queda: no es el camino vivo.

Los barridos de identidad, filtros, cuenta, FAQ y herramientas no pierden
cobertura. Los que apuntaban a la aduana viva se reapuntaron en el paso 4.

El que implementa no reescribe la vara.

### 7. Push a `main`

Toca `app/`: deploya. Pedir el OK una vez, al final, con la lista de
archivos. Nada de ramas. El hook las bloquea.

---

## Qué NO se hace “un poquito” de la 36

No se borra `guia_pedido.py`, `indice.py`, `calc_defensiva.py`, `huecos.py`.
No se fusionan las nueve herramientas a cuatro. No se sacan del árbol las
fichas 01-21 ni las corridas del banco. No se crea la segunda tienda.

`reposicion.py` sigue. Resolver y salida lo necesitan. Si esta sesión lo
borra, el nexo de la 34 se cae.

---

## Cómo se vuelve atrás

Un commit de corte. `git revert` de ese commit. El snapshot en `archivo/`
no se borra al revertir: es historia, no el vivo.

---

## Bloque para pegar al abrir ESTA sesión

```
Repo: github.com/martinrf79/Verifika, rama main.
git fetch origin main && git checkout main && git status.
Si HEAD no es origin/main, PARÁ y avisá.
Leé SOLO: ARRANQUE.md, arquitectura/PLAN_REDUCCION.md,
arquitectura/FICHA_35_la_puerta.md, DECISIONES.md.
Corré pytest -q.
Prioridad uno: el bot vende y no alucina. Si no sabe, lo dice o repregunta.
ESTA SESIÓN ES LA FICHA 35, segundo tercio de PLAN_REDUCCION. Nada más.
Snapshot a archivo/ ANTES de tocar el vivo.
La higiene queda con un solo mutador (componer). Aduana no reescribe;
si nadie la llama, sale de app/.
La prosa no se reescribe: se pega el bloque de la cuenta y se corta lo
que no está en el contrato. Procedencia, plata sellada, cobro, saludo
y punto omitido se QUEDAN.
Si el piso baja, revert. PUSHEÁ a main. Toca app/: pedí el OK del push
una vez, al final. Nada de ramas.
```
