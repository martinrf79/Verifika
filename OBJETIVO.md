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

## La medición de hoy — vara `codigo`

| vara | resultado |
|---|---|
| estado final | 8/8 |
| comunicación | 6/6 |
| **NOTA** | **100/100** |

**Lo que falla hoy:**
- nada: la vara de código está en verde.

## Bifurcaciones abiertas

_Cuando aparezcan dos caminos, se anotan acá con su razón y su costo, para que la sesión siguiente no los vuelva a descubrir._

## Historial

| fecha | vara | nota | qué se cambió |
|---|---|---|---|
| 2026-08-07 | codigo | 62 | paso 0: nace el instrumento. Primera medicion honesta. |
| 2026-08-07 | vivo | 47 | paso 2: numeros en letras + compuerta del reparto |
| 2026-08-07 | vivo | 57 | paso 2 medido con 3 repeticiones por redaccion |
| 2026-08-07 | vivo | 61 | paso 3: el codigo CREA la cuenta cuando el modelo no la armo |
| 2026-08-08 | codigo | 100 | El componedor: cuatro reglas lossless que sacan lo repetido, y la voz sin preambulo ni resumen. Vivo 69 y 58 contra un control de 55 corrido el mismo dia; largo promedio 1633 -> 1393. El tope por caracteres se probo y se descarto: tiro la nota a 23. |
| 2026-08-08 | codigo | 100 | REDACTOR ATADO POR MOLDE: probado y descartado. Vivo 56 contra control 55 y contra 69/58 de lo que ya estaba puesto, sin acortar mas (largo 1.366). El molde no se cayo ni una vez y el turno SIN bloque quedo garantizado en 417-465, pero cuesta regrabar los casetes en cada cambio de contrato. Se revierte. |
