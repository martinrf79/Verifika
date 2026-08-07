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
| estado final | 5/8 |
| comunicación | 6/6 |
| **NOTA** | **62/100** |

**Lo que falla hoy:**
- `reparto_de_pago_aplicado` — 70/30 en el argumento pago, hoy nada
- `la_parte_grande_por_transferencia` — la parte grande va por el medio CON descuento, que es lo que le conviene al cliente
- `descuento_en_la_cuenta` — el descuento por transferencia sale escrito

## Bifurcaciones abiertas

_Cuando aparezcan dos caminos, se anotan acá con su razón y su costo, para que la sesión siguiente no los vuelva a descubrir._

## Historial

| fecha | vara | nota | qué se cambió |
|---|---|---|---|
| 2026-08-07 | codigo | 62 | paso 0: nace el instrumento. Primera medicion honesta. |
