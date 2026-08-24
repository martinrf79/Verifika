# FICHA 11 — Las seis reposiciones se funden en una

> **No se borró ni una reposición.** Lo que se cortó son las cinco costuras. El
> orden entre las seis —que es lo único que las hace correctas— vivía en cinco
> comentarios de `procesar_venta`, o sea en el mismo lugar donde vivía el
> defecto que la FICHA 10 sacó de la salida.

---

## EL DEFECTO, EN UNA LÍNEA

Seis funciones sueltas en `hub_venta`, cada una con su `G.paso_datos` en
`procesar_venta`, y **ninguna sabía de las otras**: para saber por qué el
supuesto de pago va después del reparto había que leer el hub entero.

---

## LA PUERTA — `app/core/reposicion.py`

Una sola función, `completar`, y el orden adentro es el de la dependencia:

```
1. BUSQUEDA    que el producto EXISTA. Sin esto las cinco de abajo no
               tienen material y el turno sale mudo.
2. CONDICION   el filtro del cliente que el plan no aplico, sobre lo que
               la busqueda ya trajo.
3. CUENTA      la plata, por la calculadora, sobre ids certificados.
               Necesita 1 y 2.
4. REPARTO     el split de pago, aplicado SOBRE la cuenta de 3.
5. SUPUESTO    lo que se asumio, dicho sobre la cuenta que ya tiene el
               reparto adentro.
6. UN BLOQUE   las cuentas parciales se funden en una, y eso solo se
               puede hacer cuando ya estan todas.
```

**Y la condición de la memoria bajó con ellas.** La de la FICHA 04 —se abre si
el reconciliador reclamó la cuenta o si el turno no certificó nada— vivía en
`procesar_venta`, a nueve líneas de la única pieza que la usa. Esa distancia es
la forma exacta del defecto del total perdido.

---

## LO QUE NO SE PERDIÓ

**El veredicto por engranaje.** Cada pieza sigue pasando por `G.paso_datos`
adentro de la puerta, así que se sigue midiendo cuál intervino comparando la
huella del estado, y `peso_reposicion.py` ve el mismo detalle que veía con seis
nodos.

**El comportamiento ante una excepción.** `G.paso_datos` re-levanta, igual que
antes. Una guardia de salida que se cae devuelve el texto tal como entró porque
dejar mudo al bot es peor que no podar; una reposición que se cae dejaría la
cuenta a medio armar, y eso es plata mal contada.

---

## LO QUE EL BARRIDO VIO APENAS SE JUNTARON

Y no lo podía ver antes, que es lo interesante: **la cuenta cotizando ids que la
búsqueda de la misma puerta acababa de traer.** Con seis nodos el barrido le
daba a cada uno el mismo estado sin tocar, o sea que medía la cuenta sobre un
turno donde la búsqueda no había pasado. En el turno vivo pasa siempre.

El contrato `no_agrega_lo_no_pedido` decía —y sigue diciendo— que un id puede
entrar a la cuenta si estaba **en otra llamada**, en el carrito o en lo ya
mostrado. La primera de las tres no se contaba, y ahora se cuenta. **Lo que caza
es exactamente lo mismo:** un id que aparece sólo adentro de la cuenta y en
ningún otro lado, que es el auricular del 12-ago;
`test_los_contratos_frenan_de_verdad` le planta uno y lo sigue cazando.

---

## LO QUE **NO** SE HIZO, Y POR QUÉ

`DECISIONES.md` #8 pide que la cuenta **suba a la etapa de resolución**, porque
no es un parche de salida sino la resolución del punto `precio`. Acá la cuenta
quedó en la etapa de reposición, adentro de la puerta.

**El motivo es el orden.** Subirla a resolución la pone antes del reconciliador,
y la condición que la gobierna —`falta_la_cuenta`— la emite el reconciliador. La
cuenta pasaría a armarse sin saber si el cliente pidió precio, que es
exactamente lo que la FICHA 04 arregló. Mover eso es su propia unidad de
trabajo, con su propia medición. Queda anotado en `PENDIENTE.md`.

---

## CÓMO SE SABE QUE ESTÁ

Las tres condiciones del `README.md` de esta carpeta:

1. **Su test pasa.** `test_la_reposicion_es_una_sola_funcion`, sin marca, y el
   techo del `PLAN` bajó de 4 a 3. El barrido de la mitad que decide corre las
   nueve clases de estado contra la puerta: cero violaciones de contrato y 100%
   de celdas cubiertas.
2. **Ningún número del piso bajó.**
3. **La charla completa sigue andando**, que es lo único que ve las juntas.

`hub_venta.py` pasó de 2.665 líneas a 1.798.
