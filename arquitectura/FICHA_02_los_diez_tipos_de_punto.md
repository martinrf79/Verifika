# FICHA 02 — `indice_turno.puntos` abre las diez familias

> **Va segunda por dos razones.** Es **puramente aditiva**: agrega tipos de
> punto, no saca nada, y hoy `puntos()` solo lo consume el índice, que escribe en
> el log. Y porque **las dos fichas que siguen dependen de ésta**: el estado
> terminal y la cobertura-como-puerta nacerían ciegos en las preguntas
> informativas si las diez familias no existen, que es justo donde más se alucina.

---

## QUÉ SE PIDE

Que el turno se descomponga en las **diez** familias de punto respondible, no en
las seis transaccionales de hoy.

## POR QUÉ, MEDIDO

`indice_turno.puntos` abre hoy seis tipos —`item`, `condicion`, `destino`,
`duda`, `pago`, `precio`— y **los seis salen de los campos de
`registrar_pedido`**. O sea que el sistema solo sabe abrir puntos sobre la parte
transaccional: qué comprar, adónde, cómo pagar.

**No hay tipo para ATRIBUTO, STOCK, COMPATIBILIDAD ni POLÍTICA.**

Consecuencia directa, y es la que importa: si el cliente pregunta cuántos Hz
tiene el monitor, **no se abre ningún punto**. No queda nada sin contestar,
porque nunca se declaró que había algo que contestar. El contrato de cobertura es
ciego exactamente en las preguntas informativas, que son la mitad de una
conversación de venta.

Por eso **el 13% de puntos sin contestar y el 22% de turnos con algo sin
responder son un PISO, no el número real.** El número real es peor y no se puede
medir hasta que existan las diez.

## CÓMO SE VE DESDE EL CLIENTE

**No se ve todavía, y es a propósito.** Esta unidad hace que el sistema *sepa*
que hay un punto abierto. Que ese punto obligue a contestarlo es la ficha
siguiente. Si el texto de salida cambia en esta unidad, algo se hizo de más.

## EL TEST QUE HOY FALLA

```
tests/test_plan_del_recorte.py::test_se_abre_un_punto_por_cada_familia_respondible
```

Cuando pase, se pone ROJO por pasar: ahí se saca la marca y se baja
`tests/plan_techo.json` de 10 a 9, **en el mismo commit**.

## EL NÚMERO

```
HOY       `puntos()` abre 6 tipos, y ninguno cubre atributo, stock,
          compatibilidad ni politica
OBJETIVO  10 tipos. Dada una declaracion que los traiga, se abre un punto
          por cada uno, con id estable.
```

## ARCHIVOS QUE SE TOCAN

```
app/core/indice_turno.py    la funcion `puntos()` y sus ANCLAJES: que evidencia
                            contesta cada tipo nuevo
```

## ARCHIVOS QUE NO SE TOCAN

**Ninguno que cambie lo que el modelo ve o lo que el cliente lee.**

```
app/core/herramientas.py    NO se toca en esta ficha  ← ver la trampa 1
app/core/hub_venta.py       NO se toca
los prompts                 NO se tocan
```

## QUÉ NO PUEDE ROMPERSE

```
banco_pruebas/casetes/_piso.json   puntos, llamadas_max, largo_max
la bateria offline                 985 passed
test_indice_turno.py               los seis tipos de hoy siguen abriendo igual
```

Y la condición propia de esta unidad:

> **El texto de salida de las 15 charlas tiene que ser idéntico.** Un punto que
> se abre y nadie obliga a contestar no puede cambiar una coma del mensaje.

## CÓMO SE VERIFICA — offline, sin clave, sin red

```bash
python3 -m pytest tests/test_plan_del_recorte.py::test_se_abre_un_punto_por_cada_familia_respondible -q
python3 -m pytest -q
python3 banco_pruebas/peso_reposicion.py   # mira la linea de PUNTOS al final
```

## LAS TRAMPAS CONOCIDAS

**1. LA GRANDE, y es la que puede dar un verde falso.** Para que un punto de
`atributo` se abra en una charla REAL, la declaración tiene que traer el
atributo, y hoy `registrar_pedido` no tiene ese campo. **Esta ficha NO agrega el
campo al molde**, porque eso cambia el esquema que ve el modelo y es otra unidad,
con otro riesgo.

Entonces: el test pasaá —prueba que la función abre los diez dada una declaración
que los trae— pero **el corpus grabado va a seguir mostrando pocos puntos
nuevos**, porque los casetes se grabaron con el molde viejo. Eso **no es un
fracaso de esta ficha**: es que el número real todavía no se puede medir. Lo que
no se puede hacer es declarar que la omisión bajó mirando ese corpus.

**Lo que SÍ hay que dejar hecho:** que el motivo quede escrito donde se vea, para
que la sesión siguiente no lea un número bajo y crea que está todo bien.

**2. El punto sale de lo DECLARADO, nunca de lo BUSCADO.** Es tentador derivar
un punto de `politica` del hecho de que se llamó a `consultar_temas`. **Eso es
circular y destruye el instrumento:** si el punto existe porque se buscó,
entonces una pregunta que nadie buscó no abre punto, y la omisión —que es
exactamente lo que queremos cazar— se vuelve invisible. El punto nace de lo que
el cliente pidió, no de lo que el sistema hizo.

**3. El id tiene que ser estable dentro del turno.** Es `tipo:n` con `n` en el
orden en que el modelo declaró, que es el orden del mensaje. Si el id se mueve
entre la apertura y el cierre del turno, la cobertura compara contra otra cosa y
el número queda mal en silencio.

**4. Un punto de `atributo` sin campo no vale.** "El monitor" no es un punto de
atributo; "los Hz del monitor" sí. Un punto que no se puede contestar con un dato
concreto es ruido que infla el denominador y hace bajar el porcentaje de
cobertura sin que nada mejore.

## CÓMO SE VUELVE ATRÁS

`git revert`. Como la unidad no cambia el mensaje, revertirla no puede afectar a
un cliente.

---

## LO QUE VIENE DESPUÉS, para que se entienda el orden

```
FICHA 02  el sistema SABE que hay un punto abierto          ← esta
FICHA 03  cada punto termina con un estado terminal
FICHA 04  la cobertura deja de ser log y pasa a ser PUERTA
```

Recién con las tres, un turno no puede salir dejando algo sin contestar. Y recién
ahí **la omisión deja de ser un número de log y pasa a ser imposible.**
