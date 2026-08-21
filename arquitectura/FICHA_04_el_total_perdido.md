# FICHA 04 — El Total perdido

> **Se adelanta al molde porque es un defecto VIVO en producción.** El turno de
> dos llamadas fijas está online desde el 17-ago; los casetes viejos replayaban
> respuestas de cuando había cuatro rondas, así que la batería nunca lo vio.
> **Hace cinco días el bot puede cerrar sin Total cuando le piden la cuenta.**
>
> Prioridad uno: el cliente pide el precio y no lo recibe.

---

## QUÉ SE PIDE

Que un turno donde el cliente pidió la cuenta **no pueda cerrar sin la cuenta**.

## CÓMO SE VE DESDE EL CLIENTE

Hoy: pide el total de un pedido concreto y recibe un mensaje **sin Total**.
Después: recibe el bloque de la cuenta, calculado por el código.

## EL DEFECTO, reproducido

Regrabado **dos veces**, mismos turnos 6 y 8, mismo motivo. El reconciliador lo
ve y lo dice en el log:

```
"El cliente pidio precio y todavia no armaste la cuenta"   (pedido.py:638)
```

Pero:

- **Con dos llamadas fijas ya no hay ronda** que le devuelva el faltante al
  modelo. Antes la ronda dos lo tapaba.
- **`_cuenta_con_lo_declarado` no lo cubre**, porque el turno SÍ certificó
  productos: esa función nació para el caso del 5-ago —un rubro declarado que se
  cayó de la cuenta—, no para el caso de que no haya cuenta.

**El reclamo existe y nadie lo atiende.** Ese es el defecto, en una línea.

## EL NÚMERO

```
HOY       piso 489 sobre el corpus regrabado, con -12 concentrados en
          turnos que cierran sin Total. Largo 2.060.
OBJETIVO  493 o mas, y el largo NO por encima de 1.882.
          El piso se refija DESPUES del arreglo, nunca antes.
```

> **El piso no se toca hasta que el defecto esté arreglado.** Refijarlo primero
> sería mover la vara para acomodar el defecto, que es la única forma de
> corromper este método. Claude Code ya lo frenó una vez; que quede escrito.

## POR DÓNDE VA EL ARREGLO

**Por el código, no por otra ronda.** Está escrito en el docstring de
`_cuenta_con_lo_declarado` y sigue valiendo: devolvérselo al modelo cuesta una
vuelta entera —entre 3 y 8 segundos— y **no garantiza nada**; medido el 5-ago,
ante una corrección del reconciliador el modelo pidió cero herramientas 3 de 3
veces. Rehacer la cuenta cuesta cero tokens y milisegundos.

La forma natural: **cuando el reconciliador reclama que falta la cuenta y el
turno tiene productos certificados, el código arma el presupuesto** con lo que ya
certificó este turno, igual que hace hoy con el rubro perdido.

**No es el código decidiendo por el cliente:** se arma solo con lo que el modelo
mismo declaró que el cliente pidió, y solo con productos que este turno ya
certificó y mostró. Es la misma regla que ya rige.

## ARCHIVOS QUE SE TOCAN

```
app/core/hub_venta.py     `_cuenta_con_lo_declarado`, o la pieza que
                          atienda el reclamo del reconciliador
banco_pruebas/casetes/_piso.json   DESPUES del arreglo, no antes
```

**DEPLOYA.** Toca `app/`. El push se consulta con Martín.

## ARCHIVOS QUE NO SE TOCAN

```
los casetes regrabados    ya estan bien: 0 huecos, 0 turnos mudos
tests/                    ninguno se afloja para que pase
app/core/herramientas.py  el molde es la ficha SIGUIENTE
```

## QUÉ NO PUEDE ROMPERSE

```
la bateria offline        989 passed
el largo                  NO puede quedar arriba de 1.882
el resto de los casetes   los +7 que ya subieron no pueden bajar
```

Y la condición propia:

> **El arreglo tiene que cerrar los turnos 6 y 8 de `80`, que son los medidos.**
> Si el piso sube pero esos dos siguen sin Total, el número subió por otro lado y
> el defecto sigue vivo.

## CÓMO SE VERIFICA

```bash
python3 -m pytest tests/test_charlas_grabadas.py -q   # el piso, sobre el corpus nuevo
python3 -m pytest -q                                   # nada roto
```

Y a ojo, el que importa: **el mensaje de esos dos turnos tiene que traer el
bloque de la cuenta.**

## LAS TRAMPAS CONOCIDAS

**1. La tentación de devolverle la vuelta al modelo.** Está medido que no
funciona: cero herramientas 3 de 3 veces ante una corrección. Y agrega una
llamada, que el piso defiende con `llamadas_max: 2`. **El arreglo no puede subir
ese número.**

**2. Armar la cuenta cuando el cliente NO la pidió.** Sería el código decidiendo
por el cliente, y además alarga el mensaje —que es el número que ya está alto—.
La condición es que el reconciliador lo reclame, no que haya productos.

**3. El largo.** El bloque de la cuenta suma caracteres. Si al arreglar esto el
largo se va arriba de 1.882, **el arreglo no está completo**: hay que ver qué
relleno sale para compensar. Un mensaje correcto es prioridad sobre uno corto,
pero el tope existe y `PENDIENTE.md` dice que tiene que bajar, no subir.

---

## LO QUE ESTA FICHA ENSEÑÓ SOBRE EL MÉTODO

Dos cosas, y las dos son correcciones a lo que yo había escrito:

**1. La condición de aceptación de la FICHA 03 estaba incompleta.** Yo escribí
"cero huecos". Faltó: **cero turnos MUDOS**. Un turno puede grabarse con las
llamadas presentes pero vacías —`content: ""`, `tool_calls: []`—, el modelo no
dice nada y el cliente lee el enlatado. Para el contador de huecos **eso no es un
hueco**, porque la grabación existe. Degrada el corpus igual de silenciosamente.

**2. `puerta_piso.json` mide dos cosas a la vez.** Guarda RAZONES —porcentajes—
contra un corpus mutable, así que cuando el corpus cambia, el numerador y el
denominador se mueven juntos y **no se puede decir cuál se movió**. Dio
`reparto_pago` 11,1% → 9,1% como si el código entendiera menos, y saca los mismos
turnos: cambió el denominador. Es un defecto del instrumento, no del código.
