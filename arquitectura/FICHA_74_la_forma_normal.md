# FICHA 74 — La forma normal: lo que dijo el modelo, en la forma que cumple el ejecutor

21-oct-2026, sesión con Martín. Viene de la FICHA 73. **Está en el bot**, en `app/core/flujo/normal.py`, y sin push.

## El diagnóstico

Las 525 de `traduccion58` ya estaban grabadas con seis modelos: producción, DeepSeek, Haiku, Luna, Mini y Terra.

- **El modelo entiende; lo que falla es la forma.** De las 70 fallas de producción, en casi todas el sentido está
  bien y la agenda está escrita de otra forma que la agenda a mano. "Cuánto me sale con envío" llega como producto y
  envío, sin cuenta. Un "sí" con el pedido completo llega como confirmar renglones que no esperaban nada.
- **Es el contrato, no el modelo.** 52 casos fallan en cuatro o más de los seis modelos; solo 37 fallan en uno solo.
  Un modelo más grande no lo arregla.
- **El modelo pide lugares que el menú no tiene.** Pone una condición dentro de la compra 19 veces, y 15 fallan.
  Marca "otro, corrige" 164 veces, y el código no hace nada con eso.

## El método

`banco_pruebas/forma_normal/regrado.py` pasa por el flujo vivo cada agenda grabada de los seis modelos, sin modelo,
con los turnos anteriores en su agenda a mano, y la califica con la vara. Son 3.107 casos en un minuto, gratis.

Una regla entra si arregla alguna y no rompe ninguna, en ningún modelo, y si la batería sigue verde. Cada regla define
una forma de decir, no un caso, y lee la agenda, el estado y la fuente. Nunca el mensaje: de lo dicho, solo la cita que
el modelo le puso a esa pregunta, y solo para buscar ahí un lugar o un producto de la fuente.

**Lo que no es todavía:** las reglas se escribieron mirando las fallas de los seis modelos. El candado es que no rompen
ninguna de las 3.107, no una reserva limpia. La primera reserva real es la corrida de mañana con el menú nuevo: son
traducciones que nadie vio.

## El resultado

| modelo | grabado | con la forma normal | de |
|---|---|---|---|
| producción | 455 | **507** | 525 |
| DeepSeek | 453 | 509 | 525 |
| Haiku | 468 | 517 | 525 |
| Luna | 457 | 506 | 525 |
| Mini | 440 | 487 | 525 |
| Terra | 429 | 468 | 482 |
| **todos** | **2.702** | **2.994** | **3.107** |

Sin romper ninguno, sin cambiar lo que recibe el modelo y sin segunda llamada. La FICHA 73 llegaba a 521 con la tabla
nueva y diecisiete avisos, pero con otra entrada y una segunda llamada en uno de cada diez mensajes.

## Las reglas, en `normal.py`

Arreglan 289 casos de las 3.107: 231 por una regla de forma y 58 por los arreglos del código de abajo. Un caso puede
contar en dos reglas.

| regla | la forma | casos |
|---|---|---|
| `si_sin_efecto` | un sí que no cambia nada, con el pedido completo, es la cuenta | 51 |
| `cuenta_de_lo_buscado` | la cuenta sin pedido de lo buscado entra al pedido, como la agenda a mano | 36 |
| `precio_con_envio` | precio y envío sin pedido suman | 29 |
| `un_destino_para_el_pedido` | un solo destino en el mensaje es el del pedido que no lo tiene | 26 |
| `dato_del_producto` | la garantía de un producto nombrado es un dato suyo | 23 |
| `politica_de_envio_con_lugar` | la regla de envíos con un lugar, o con el del cliente, es un envío | 17 |
| `referencias_cruzadas` | confirmar un M es llevarlo; agregar un L es cambiarlo; cambiar un M es preguntar de nuevo | 15 |
| `compatibilidad_de_un_rubro` | la compatibilidad de un rubro con algo que no es un equipo es una búsqueda | 10 |
| `envio_a_varios` | un destino con varios lugares es un envío por cada uno | 10 |
| `color_ajeno` | un color que la tienda no tiene no es un cambio: "indistinto" | 10 |
| `un_medio_es_todo` | un solo medio de pago sin porcentaje es el cien | 5 |
| `cuenta_de_lo_nombrado` | la cuenta sin pedido de productos con cantidad entra al pedido | 3 |
| `el_pedido_sin_pedido` | otro orden para el pedido, sin pedido, es para la última búsqueda | 3 |
| `uno_por_cada_nombrado` | varios productos nombrados son una pregunta por cada uno | 0, mejora la respuesta |

## Lo que era del código, no de la traducción

- **La negación de varias palabras**, `catalogo.atar`: "que no sea Kingston Fury Beast DDR4 16GB" sacaba todo lo
  Kingston y todo lo de 16 GB. Ahora saca lo que tiene todas.
- **Las condiciones entre lo mostrado** se ataban solo contra lo mostrado: "que no sea Redragon" salía como que no
  figura en las fichas. Ahora se atan en todo el rubro.
- **Lo mismo de nuevo**: una búsqueda que trae solo lo ya visto muestra lo que no vio, y entre lo mostrado sin nada que
  cumpla busca en la tienda, y lo dice.
- **El reparto a medias**: "70 por ciento transferencia" con el 70/30 ya dicho se completa con lo que estaba.
- **C30, la compatibilidad**: daba compatible a una DDR4 con "placa DDR5". Ahora el conector dicho cuenta si la nota de
  la ficha dice que ahí no va, y un equipo dicho solo por su ranura se juzga por la familia del conector. Antes le
  mostraba al cliente el mensaje interno de que no reconocía el equipo.

## La compra con condición

"Entre el G305 y el G203, dame el inalámbrico", "si el K120 sale menos de 10 mil llevo dos", "me lo llevo si anda con
Mac". Es la clase que más queda: el modelo pierde el "dame" o la condición, porque el menú no tiene dónde ponerlos.

- **En el ejecutor ya está**: `"si_cumple"` en una compra. El código mira cada producto contra la condición con las
  herramientas de siempre, lleva el que la cumple, dice cuando ninguno la cumple y pregunta si la cumplen varios.
  Tests con la vara de C32, C56 y C29.
- **El menú que la ofrece no entró.** Está en `banco_pruebas/forma_normal/menu_si_cumple.patch`, con su test xfail.
  `test_variantes` exige medir toda consigna nueva con Gemini, y la cuota gratis del día, 500 pedidos, se agotó.
- **Medido en un modelo gratis de OpenRouter**, `minimax_gratis`, en seis turnos y cinco formas: con el menú de hoy 24
  de 30, con el parche 28 de 30, sin romper ninguno.
- Para entrar en el tope de tres mil tokens, el parche saca de la consigna lo que ya resuelve la forma normal: que pedir
  un envío no es política, y la garantía como ejemplo de política.

## Lo que queda en producción: 18 de 525

- **Información perdida**, 13: C32, C56, C29 y C53, la compra con condición; C25, las cantidades en "afirma".
- **Ambigüedad**, 5: C52, "y ese cuánto" con doce mostrados. La vara quiere que pregunte; el modelo elige el último.

## Cómo se repite

```bash
python3 banco_pruebas/forma_normal/regrado.py                       # las 3.107, contra lo grabado
python3 banco_pruebas/forma_normal/regrado.py --guardar /ruta/x.json
python3 banco_pruebas/forma_normal/regrado.py --contra /ruta/x.json # lo que arregla, lo que rompe y por qué regla
python3 -m pytest -q tests/test_forma_normal.py                      # una por regla, la compra con condición y el piso
```

`base.json` es la referencia de antes de la forma normal.

## Lo que sigue

1. **El menú con `si_cumple`**, con la cuota gratis de Gemini: `git apply` del parche, `python3 -m banco_pruebas.variantes`
   y las 525 una vez. Entra si no baja de 507 ni de los pisos de variantes.
2. **Los avisos de la FICHA 73**, solo para lo que la forma normal no cubre: casi todos son ahora una regla, sin segunda
   llamada. Quedan los de información perdida.
3. **Una reserva** de formas nuevas, escritas antes de correr.
