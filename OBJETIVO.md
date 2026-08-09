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
| 1_textual_de_martin | **78** | 62 | 100 | 1102 |
| 2_porcentajes_en_digitos | **92** | 88 | 100 | 1528 |
| 3_orden_invertido | **83** | 73 | 88 | 1214 |
| 4_criterio_dicho_distinto | **56** | 12 | 83 | 1247 |
| 5_coloquial | **75** | 75 | 75 | 1465 |

**Promedio: 77/100 — PEOR CASO: 12/100**

El que manda para vender es el PEOR, no el promedio: es el que le puede tocar a un cliente real.

**Lo que falla, sobre 15 corridas:**
- 9/15 — cada_unidad_con_destino
- 6/15 — seis_unidades
- 5/15 — dice: china
- 2/15 — la_parte_grande_por_transferencia
- 2/15 — tres_envios_cotizados
- 1/15 — hay_total
- 1/15 — reparto_de_pago_aplicado
- 1/15 — descuento_en_la_cuenta

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
| 2026-08-08 | codigo | 100 | El muro cae en sus SEIS redacciones -se persigue la FORMA, no la frase- y las tres pedidas de confirmacion bajan de 380 a 130 caracteres. Vivo 65, largo 1.249: el largo mas bajo medido y la nota en el techo de la banda anterior. El candado cazo 8 muros en la corrida contra 3 antes, incluida una SEPTIMA redaccion nueva. |
| 2026-08-09 | codigo | 100 | LA BIMODALIDAD, CERRADA. Dos causas, las dos deterministas y ninguna de redaccion. 1) El null que el molde PEDIA y RECHAZABA: registrar_pedido volvia pedido_mal_formado y el turno salia mudo. Saneado en la puerta unica, con barrido que cubre TODOS los moldes. 2) El rubro declarado y nunca buscado: el modelo declara los tres rubros y no busca ninguno; el reconciliador se lo pide y la ronda dos vuelve VACIA. Ahora lo busca el codigo, la tercera cara de la moneda que ya estaba escrita dos veces en hub_venta. VIVO: la redaccion 5 de 6 a 71, la 2 de 50 a 78, promedio 64 a 82 y el PEOR CASO de 0 a 62, que es el que manda. Largo 1.487: subio, porque el mensaje que antes no cotizaba nada ahora entrega el presupuesto entero. |
| 2026-08-09 | codigo | 100 | A FONDO: cerrada la bimodalidad y dos defectos mas. 3) La MINIMIZACION es una forma, no una palabra: 'menos' resolvia a filtro y 'la MENOR cantidad de partes chinas posible' -como lo dijo Martin- no, asi que el unico criterio del cliente se perdia. 4) El item EN DUDA se pregunta, no se cotiza: el modelo declaraba el teclado como item Y como contradiccion, el codigo lo buscaba y la cuenta le sumaba $12.000 que el cliente no pidio. VIVO, tres corridas del dia: promedio 82, 86 y 89 contra 65 al arrancar; la redaccion 5 de 8 a 79 con un 100 en su mejor corrida; seis_unidades fallando 2 de 15 contra 4. El peor caso oscila 62-73 entre corridas. EL TECHO AHORA TIENE NOMBRE Y NUMERO: cada_unidad_con_destino falla 10 de 15 y es el proximo paso. |
