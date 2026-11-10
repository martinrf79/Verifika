# PLAN POR CAPAS — el tipo de pregunta es el mapa de la respuesta

9-nov-2026, orden de Martín. Reemplaza, cuando cada capa esté medida, al bucle del agente de la FICHA 83: el modelo ya
no elige herramientas ni el orden. **Este archivo es el estado del plan: cada capa con su corte, escrito antes de
medir, y lo medido.** Lo hecho lo cuenta `git log`.

## El camino

```
MENSAJE + MEMORIA            lo mostrado y lo pedido con un solo numero, las reglas pendientes "si A, B"
  [1] SEPARAR · LLM 1        una pregunta por cosa, con su tipo de una lista cerrada y sus campos: la agenda
  [2] FORMA NORMAL · codigo  `normal.py`: los contratos que el codigo impone a lo que dijo el modelo
  [3] RECETA · codigo        `ejecutor.py`: cada tipo con sus datos, sus subpreguntas y su repregunta
  [4] CONDICIONES · codigo   cada "si" contra los datos reales; lo que no se puede decidir se repregunta
  [5] REDACTAR · LLM 2       cita por numero, no escribe datos, `respuesta.py`
  [6] PEGAR + VERIFICAR      el codigo pega los datos; el verificador vuelve a [5] una vez
  [7] MEMORIA                lo mostrado, el pedido y las reglas pendientes, para el turno que sigue
```

Lo que ya existe y queda: el ejecutor, la forma normal, la tabla, la calculadora, el cobro, la respuesta atada y el
verificador. Lo que sale cuando el camino nuevo supere al agente en las mismas charlas: el bucle de `agente.responder`.

## Cómo se trabaja cada capa

1. El banco sin modelo, sobre lo que los modelos ya tradujeron y quedó grabado: `traduccion58_corridas.jsonl`, seis
   modelos, cinco formas de escribir cada mensaje.
2. La vara dura: **los mismos productos que la agenda a mano**. Las casillas de los primeros turnos son flojas: con la
   agenda vacía pasan 105 de 375.
3. El corte, escrito antes. Una regla entra si arregla y no rompe ningún caso en ningún modelo.
4. El techo de fallas en `tests/`, que sólo baja.

## Las capas, por tipo, en orden de cuántas veces aparecen en las 58 y las K

| Capa | Tipo | Estado |
|---|---|---|
| 1 | buscar | **hecha la forma normal.** Gemini 363 de 375, corte 357. Ver abajo |
| 2 | producto | forma normal a medias: Gemini 282 de 300, **no pasa el corte de 285** |
| 3 | comprar | forma normal a medias: Gemini 237 de 270, **no pasa el corte de 257**; lo que falta es de la llamada 1 |
| 4 | cuenta | — |
| 5 | otro | — |
| 6 | política | — |
| 7 | envío | — |
| 8 | compatibilidad | — |
| 9 | explicar | — |
| — | la llamada 1, su consigna | la intención de compra medida: B2 pasa su corte, una corrida; falta repetirla y llevar la llamada al bot; recuperar la consigna del intérprete, git `53a1a90^` |
| — | memoria: un solo número para lo mostrado y lo pedido | medido el 9-nov en 15 turnos, 3 corridas: arregla los 3 de "rubro en vez de número", no rompe los 18 de control |

## Capa 1, buscar — 9-nov

Instrumento: `banco_pruebas/capa_buscar.py`, candado `tests/test_capa_buscar.py`.

- Piso del código: con la agenda a mano, el ejecutor resuelve 35 de 36 primeros turnos con buscar; K12 es una frase.
- Línea de base, lo grabado por el código de ese día: Gemini 309 de 375, DeepSeek 118 de 125, Haiku 120 de 125.
- Las 66 fallas de Gemini, por causa: un orden que el cliente no dijo, "más caro" por "el precio no es tan importante";
  la corrección que deja también la búsqueda vieja; rubro con marca tomado como un producto; "si no va, qué otra hay"
  sin el equipo de la compatibilidad.
- Cuatro reglas en `normal.py`: `orden_que_no_dijo`, `lo_corregido`, `rubro_con_marca`, `alternativa_compatible`.
- Resultado: **Gemini 363 de 375**, DeepSeek 123, Haiku 121, Terra 116 de 118. Arregla 70, rompe 0.
- Lo que queda, 12 de Gemini: C06 "si es Logitech, mejor" como dos búsquedas; C30 tres formas; K20 y K21 "menos
  partes chinas" leído como una regla de la tienda.

## Capa 2, producto — 9-nov

Instrumento: `banco_pruebas/capa_buscar.py --tipo producto`. Línea de base, el código antes del 9-nov: Gemini 273 de 300.
Corte, escrito antes: Gemini 285 de 300 o más, sin romper ningún caso de ningún modelo ni de la capa buscar.

- Regla `producto_del_envio`: "cuánto sale mandar un G203 a Rosario" pregunta también el precio del G203. Solo con un envío:
  "un G203 a Rosario y otro a Mendoza" manda unidades. Un número solo no es un producto: "Sabatini 2000" no es la FaceCam 2000X.
- Resultado: **Gemini 282 de 300, no pasa el corte.** Arregla 37 en seis modelos, rompe 0.
- Lo que queda: **C32, para que decida Martín.** "Entre el G305 y el G203, el que sea inalámbrico": la regla de antes,
  `lista_con_dato`, contesta por el que cumple y lo ofrece; la agenda a mano pregunta por los dos y compra el que cumpla.
  Una regla que partía la lista pasaba el corte, 288, pero rompía el test de `lista_con_dato`: no entró. Y C56 y C28,
  que son compras.

## Capa 3, comprar — 9-nov

Instrumento: `banco_pruebas/capa_buscar.py --tipo comprar`. Línea de base: Gemini 216 de 270.
Corte, escrito antes: Gemini 257 de 270 o más, sin romper ningún caso de ningún modelo ni de las capas 1 y 2.

- Regla `compra_si_sale`: "si el K120 negro sale menos de 10 mil, llevo dos" pregunta el K120 con ese tope y la compra
  depende de que dé que sí: el código mira el precio real. `cuenta_de_lo_nombrado` lee la cantidad de "cantidad 2".
- Resultado: **Gemini 237 de 270, no pasa el corte.** Arregla 27, rompe 0.
- Lo que queda es de la llamada 1, no del código: "quiero un K120 y el G305 blanco" y "me llevo el G305 si anda con Mac"
  llegan como preguntas, no como compras. Leer la intención sin listas de palabras es trabajo de la consigna.

## La llamada 1, la intención de compra — 9-nov

`banco_pruebas/llamada1/`, con su corte escrito antes en `CORTE.md`. La consigna del intérprete del 21-oct, la que grabó
`traduccion58`, contra la misma con un párrafo de LA INTENCION DE COMPRA. 120 primeros mensajes, clave gratis, una vez cada uno.

- B, comprar es "lo quiere, lo lleva, se lo mandan": gana 7 y pierde 2. **No pasa.** "Quiero un mouse inalámbrico" y
  "cuánto sale mandar un G203" pasaban a compra.
- B2, comprar es de un modelo concreto o de algo de la libreta; un rubro sin modelo busca; preguntar cuánto sale algo o
  mandarlo es producto y envío: **comprar 85 de 90 contra 79, buscar 50 de 50 contra 47, producto igual. Gana 7, pierde 0.
  Pasa.**
- Falta: dos corridas más, por la variación entre corridas, y llevar la llamada 1 al bot por camino fijo.

## Las charlas enteras — 10-nov, FICHA 92 paso 1

Instrumentos: `banco_pruebas/camino_fijo.py`, las 58, J y K por el webhook con la agenda a mano y el turno fijo, sin
modelo; `banco_pruebas/camino_grabadas.py`, lo grabado de los seis modelos turno por turno, contra la agenda a mano por
productos mostrados, pedido y montos.

- Con la traducción perfecta: 136 de 138, y 138 al respetar el orden que el cliente dice con otras palabras cuando la
  llamada 1 cita de dónde lo sacó, `orden_cita`, y al decir "No vendemos" lo que no se vende.
- Lo grabado: Gemini 423 de 525. De las 102 diferencias, 54 de la traducción, 33 del código, 11 de la agenda a mano y 4
  de la prueba. Cuatro clases del código arregladas: el destino escrito de una forma, lo que saca el tope por el producto
  que nombra, el producto del envío por producto certificado y entre lo mostrado por modelo. **Gemini 454 de 525**,
  DeepSeek 450, Haiku 463, Luna 444, Mini 398, Terra 416 de 482. Rompe 0, y las capas 1 a 3 quedan iguales.
- Lo que sigue es de la llamada 1: acción equivocada 15, número M o L equivocado 12, condición perdida 6, alcance 6,
  cantidad que suma 5, producto en vez de comprar 4, reparto como política 3, compra por destino 3.
