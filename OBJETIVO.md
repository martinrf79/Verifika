# EL OBJETIVO, Y SI LLEGAMOS

> **ESTE ARCHIVO LO GENERA `banco_pruebas/objetivo.py`. No se edita a mano.**
> Un documento escrito a mano miente a la sesión siguiente; uno calculado no
> puede. Para moverlo, se cambia el código y se vuelve a correr.

## El objetivo

Que el bot conteste BIEN la pregunta real de Martin: seis productos en tres rubros, un criterio no binario -las menos partes chinas posibles-, tres destinos de envio, una contradiccion a proposito -un teclado que no estaba en el pedido- y un reparto de pago 70/30.

## Cómo se mide, y por qué así

Copiado de **τ-bench**, el banco público de agentes de atención al cliente de
Sierra, que está probado:

1. **ESTADO FINAL** — qué quedó en la cuenta, no qué pasos se dieron. Cualquier
   camino que llegue al mismo estado pasa.
2. **COMUNICACIÓN** — ¿están las frases que sí o sí había que decir, y no están
   las que no se pueden decir?
3. **LA NOTA ES EL PRODUCTO DE LAS DOS.** Una cuenta perfecta que no dice lo que
   había que decir vale cero, y un mensaje lindo con la cuenta mal, también.
   **No se gana hablando.**

Y se mide sobre **cinco redacciones** de la misma pregunta, no una. Ésa es la
falla que más costó: el reparto de pago se arregló leyendo `70/30` y se cayó con
`setenta treinta`, que es como lo escribió Martín.

```bash
python3 banco_pruebas/objetivo.py            # la nota de código, gratis
python3 banco_pruebas/objetivo.py --vivo     # las 5 redacciones, con el modelo
python3 banco_pruebas/objetivo.py --anotar "qué cambié"
```

## La medición de hoy — vara `vivo`

| redacción | promedio de 3 | peor | mejor | largo |
|---|---|---|---|---|
| 1_textual_de_martin | **83** | 73 | 100 | 1830 |
| 2_porcentajes_en_digitos | **50** | 12 | 75 | 1741 |
| 3_orden_invertido | **54** | 12 | 75 | 1765 |
| 4_criterio_dicho_distinto | **69** | 58 | 88 | 1880 |
| 5_coloquial | **31** | 10 | 62 | 1480 |

**Promedio: 57/100 — PEOR CASO: 10/100**

El que manda para vender es el PEOR, no el promedio: es el que le puede tocar a un cliente real.

## Bifurcaciones abiertas

_Cuando aparezcan dos caminos, se anotan acá con su razón y su costo, para que la sesión siguiente no los vuelva a descubrir._

## Historial

| fecha | vara | nota | qué se cambió |
|---|---|---|---|
| 2026-08-07 | codigo | 62 | paso 0: nace el instrumento. Primera medicion honesta. |
| 2026-08-07 | vivo | 47 | paso 2: numeros en letras + compuerta del reparto |
| 2026-08-07 | vivo | 57 | paso 2 medido con 3 repeticiones por redaccion |
