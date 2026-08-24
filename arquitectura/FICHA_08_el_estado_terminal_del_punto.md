# FICHA 08 — Cada punto termina en un estado, y el estado se puede nombrar

> **Es la ficha que separa observar de ser puerta.** No frena nada todavía —eso
> es la 09—, pero sin esto la puerta no tendría de qué agarrarse: hoy el turno
> que pregunta bien y el turno que se olvida algo **se ven idénticos en el log.**

---

## EL DEFECTO, EN UNA LÍNEA

`indice_turno` sabía decir `ok` o `FALTA`. Y **`FALTA` mete cuatro cosas
distintas en la misma bolsa:**

```
el bot se lo olvido                     ← el UNICO defecto
el bot pregunto cual de los tres era    ← esta bien
la fuente no tiene el dato              ← esta bien
el cliente se contradijo                ← esta bien
```

Tres de cuatro no son un defecto. Mientras sean indistinguibles, frenar el turno
por `FALTA` frenaría también al bot que hizo bien las cosas, **y eso vende menos
que la omisión que se quiere evitar.**

---

## QUÉ SE HIZO

`app/core/indice_turno.py` — `estado_terminal(punto, texto, llamadas, atendido)`,
que devuelve uno de cuatro, o **cadena vacía**:

```
RESUELTO     llego al texto que lee el cliente.
AMBIGUO      no se podia cerrar sin elegir por el cliente, y el turno PREGUNTA.
NO_SE_SABE   no hay con que contestarlo. Jamas frena el cierre (DECISIONES #16).
CONFLICTO    lo que el cliente pidio no cierra y el turno NO lo pregunto.
""           tenia con que contestarse y no salio dicho. ESO ES LA OMISION.
```

**La cadena vacía no es un estado a propósito.** Si la omisión fuera un final
más, un turno que se olvida algo estaría tan "terminado" como uno que contesta,
y la puerta de la 09 no tendría nada que frenar.

`cobertura()` le pone la casilla `estado` a **todos** los puntos: puede salir
vacía, no puede faltar. Y `hub_venta` anota el censo del turno —`estados` y
`sin_estado`— al lado de `sin_contestar`, así el número se ve sin leer una
charla a mano.

---

## DE DÓNDE SALE CADA FINAL, Y POR QUÉ NO SE LE PREGUNTA AL MODELO

La evidencia ya está del lado del código. Pedírsela al modelo sería pagar por un
dato que tenemos, y cambiar el contrato obliga a regrabar los casetes con la
clave paga.

```
la EVIDENCIA   el `estado` que devolvio cada herramienta: `ambiguo` y
               `depende_de_la_variante` -> AMBIGUO; `no_encontrado`,
               `no_vendemos`, `sin_dato_en_la_fuente` y sus hermanos ->
               NO_SE_SABE. No es vocabulario nuevo: es el que ya existe.

el TEXTO       una pregunta o un "no tengo ese dato" que caigan EN LA MISMA
               ORACION que el punto.

la DUDA        una contradiccion declarada no puede terminar RESUELTA por el
               codigo: preguntada queda AMBIGUA, callada queda en CONFLICTO.
```

**La atadura de la misma oración es lo que hace que esto no sea un colador.** Sin
ella, un `¿te lo despacho hoy?` de cortesía al final del mensaje dejaría en
AMBIGUO a todo lo que el bot se olvidó, y toda omisión se volvería un final
feliz. Ese caso es la sexta prueba del archivo, y está escrita para eso.

---

## CÓMO SE SABE QUE ESTÁ

```
tests/test_estado_terminal.py     4 tests, 12 casos declarados uno por uno
tests/test_plan_del_recorte.py    test_el_punto_tiene_estado_terminal, sin marca
tests/plan_techo.json             7 -> 6
```

El techo baja **en este mismo commit y no antes**, porque acá no se movió una
vara: se sacó una marca que `strict=True` ya no deja puesta.

---

## LO QUE ESTA FICHA NO HACE

- **No frena ningún turno.** Es la 09: `puede_salir`, la cobertura como puerta.
- **No cambia el número de omisión.** Lo desarma en cuatro, que es otra cosa.
  El número real de `SIN_ESTADO` recién se lee corriendo las charlas.
- **No toca el prompt.** El modelo no se entera de esto y no tiene que enterarse.
