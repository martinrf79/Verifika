# Lo que la FICHA 11 dejó abierto — y por qué, contado entero

> Esto no es el `PENDIENTE.md`, que es una línea por ítem y se imprime en cada
> arranque. Acá va el **relato**: qué se intentó, con qué se chocó, y cuál es la
> decisión que hace falta para destrabarlo. La orden de trabajo se lee para
> hacer; esto se lee para entender por qué la próxima no arranca de cero.

Fecha: 24-ago-2026. Commits `7d78fc1` y `70e2a44`.

---

## 1. La cuenta NO subió a la etapa de resolución

**Qué pedía el plan.** `DECISIONES.md` #8 lo dice con todas las letras: *"La
cuenta sube a la etapa de resolución. `_cuenta_con_lo_declarado` interviene en el
44% de los turnos: no es un parche de salida, es la resolución del punto `precio`
puesta en el lugar equivocado."* Y la marca `xfail` de la ficha lo repetía: la
más grande no se borra, sube.

**Qué se hizo en cambio.** Las seis quedaron fundidas en una puerta,
`reposicion.completar`, y la cuenta corre tercera adentro, en su orden de
dependencia. La etapa siguió llamándose reposición.

**Con qué se chocó, dicho en una línea.** **La condición que gobierna a la cuenta
la emite el reconciliador, y el reconciliador corre después de lo que sería la
etapa de resolución.**

Desarmado:

```
hoy                          si la cuenta "sube"
───────────────────────────  ──────────────────────────────
1. el modelo declara         1. el modelo declara
2. el codigo deriva busquedas 2. el codigo deriva busquedas
3. RECONCILIADOR             3. la cuenta se arma  <-- sin saber
   emite `falta_la_cuenta`       si el cliente pidio precio
4. la cuenta se arma         4. RECONCILIADOR
   sabiendo si la pidieron
```

Armar la cuenta antes del reclamo es exactamente el defecto que la FICHA 04
curó el 21-ago: **la condición pasa a ser "hay productos" en vez de "el cliente
pidió precio"**, que es el código decidiendo por el cliente. Y tiene costo
visible: le pega el bloque de precios a turnos que no lo pidieron, que es
mensaje más largo por nada.

**Qué haría falta para hacerlo bien.** Que el reclamo tipado —`falta_la_cuenta`,
`falta_el_reparto`— salga de algo que corra **antes**, o que el reconciliador
suba con ella. Las dos son su propia unidad de trabajo, con su propia medición
sobre las 15 charlas: hay que ver cuántos turnos ganan un total que hoy no
reciben y cuántos ganan un bloque que no pidieron.

**Lo que NO hay que hacer:** subirla "y ver qué pasa". Este módulo ya revirtió
dos veces por cambios de este tipo.

---

## 2. El barrido tenía una ceguera, y sólo se vio al juntar las piezas

Esto no es un pendiente: está arreglado. Se cuenta porque **el método lo produjo
y conviene saber que el método hace eso.**

Con seis nodos, el barrido de la mitad que decide le daba a cada uno **el mismo
estado sin tocar**. O sea que medía la cuenta sobre un turno donde la búsqueda
no había pasado. En el turno vivo la búsqueda pasa siempre, antes, en la misma
etapa.

Apenas las seis quedaron adentro de una puerta, el barrido vio la secuencia real
y marcó 14 violaciones de `no_agrega_lo_no_pedido`: **la cuenta cotizando ids que
la búsqueda de la misma puerta acababa de traer.**

El contrato decía —y sigue diciendo— que un id puede entrar a la cuenta si estaba
**en otra llamada**, en el carrito o en lo ya mostrado. La primera de las tres no
se contaba. Ahora se cuenta, y lo que caza sigue siendo lo mismo: el id que
aparece **sólo adentro de la cuenta y en ningún otro lado**, que es el auricular
del 12-ago. `test_los_contratos_frenan_de_verdad` le planta uno y lo sigue
cazando, y ése es el candado de que esto no vació el contrato.

**Lo que hay que retener:** un contrato medido pieza por pieza no ve las juntas,
y las juntas son donde vivieron los dos bugs registrados. Cada vez que la 12
junte algo, mirar qué empieza a marcar el barrido.

---

## 3. `_bloque_hallazgo` sigue en `hub_venta`, y la ida y vuelta no se fue del todo

La FICHA 10 dejó anotado que `salida.py` le pedía tres cosas al hub por import
perezoso. La 11 se llevó dos: `_cuenta_con_lo_declarado` y `_bloque_presupuesto`
viven en `reposicion`, que no importa a nadie de la salida, así que entran por la
cabecera.

Queda `_bloque_hallazgo`, y queda a propósito: usa `_RE_HAY_CUENTA` y
`_norm_renglon`, **que son de `salida.py`**. Mudarlo a `reposicion` no saca la ida
y vuelta: la da vuelta. Para cerrarlo hay que decidir de quién son esos dos
patrones, y eso es una decisión, no una mudanza.

---

## 4. Lo que la 11 NO tocó y sigue igual que ayer

- **Las nueve comprobaciones de salida que no intervienen sobre el corpus.** La
  FICHA 10 no las borró porque el corpus no tiene un CBU falso ni un "sos un
  bot". Los guiones 26 a 38 se escribieron para eso y siguen sin correrse contra
  ellas.
- **El número de VENTA.** Todo lo que este repo mide es defensivo. La 11 hizo el
  turno más barato de leer; no hizo que se supiera si vende.
- **`puerta_piso.json` guarda porcentajes contra un corpus mutable.** Sigue
  dando falsos rojos por cambio de denominador.

---

## Cómo queda el marcador

```
A MEDIAS   0   (no subió: nada quedó empezado a la mitad)
PLAN       3   (era 4; la 11 cerró el suyo)
```

`hub_venta.py`: 3.621 líneas antes de la 10 → 2.665 después de la 10 → **1.798
después de la 11.**
