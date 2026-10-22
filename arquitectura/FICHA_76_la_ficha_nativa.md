# FICHA 76 — La ficha nativa: el pedido como documento, con los nombres del modelo

22 y 23-oct-2026, sesión con Martín. Viene de la FICHA 75. **Lo que está en el bot:** el índice en `catalogo.atar`,
commit bc9bcf4, deployado. **Lo que no:** la ficha nativa. **El procedimiento de abajo es una recomendación:** es un cambio grande y se
arranca solo si Martín lo decide en la sesión.
El experimento entero está en `banco_pruebas/pregunta_razonada/` y `banco_pruebas/pedido_documento/`.

## Lo medido, en orden

Todo sobre las mismas 16 charlas de razonamiento con memoria, tres turnos cada una, 48 turnos:
`pregunta_razonada/fichas.py`. Las escribió Claude antes de correr, con lo correcto de cada turno. Cada una nace de una
multipregunta real del repo. Gasto total de las pruebas: unos 24 centavos con la paga.

| Prueba | Resultado |
| --- | --- |
| Partir, decir en común y escribir Python con nuestro menú, en una llamada | 28 de 48 bien, 20 mal sin avisar, nunca pregunta |
| Lo mismo en tres llamadas encadenadas | peor y tres veces más lento: se descartó |
| Jev partiendo el mensaje | 36 de 81 cortes y 32 de más: se descartó |
| Paso libre, 100 mensajes, sin menú ni campos ni fuente | pares conservados: natural 166, JSON 149, Python 131 de 264 |
| **Ficha nativa**, JSON con los nombres que eligió el modelo, sin menú, ejemplos ni fuente | **38 de 48 bien**, igual en tres repeticiones |
| La misma ficha, contra el paso libre, en los mismos 48 | conserva 128 de 132 pares; el natural libre, 89 |

**La lectura:**
- **No es Python, ni el modelo, ni la información de la fuente.** De las 20 fallas del Python con menú, 10 eran la
  estructura del pedido —qué va a cada destino, cambiar un renglón— y la información estaba toda en el mensaje. Es lo
  que ya decía la FICHA 73: el cuello es llevar el pedido al menú.
- **El modelo entiende mejor en su propia forma.** En JSON libre repite solos `pedido`, `producto`, `cantidad`,
  `destino`, `consulta` y `metodo_pago`, y cuando reparte bien arma una lista de envíos con sus artículos. La ficha es
  esa forma, fija.
- **El pedido va entero, como queda, no los pasos para llegar.** Ahí está la memoria: el estado entero está adelante
  del modelo y no tiene que acordarse de nada. Los turnos con memoria dan 14 y 12 de 16.
- **El campo de la duda se calibra.** Abierto, se llenaba en 31 de los 38 turnos bien; acotado a "lo que impide cumplir
  este mensaje", 0. Con eso, lo mal sin avisar pasó de 3 a 8.

## De la ficha a la fuente

Con la ficha bien, el cuello pasó al paso siguiente: atar sus palabras a la fuente, sin modelo.
`pedido_documento/atar_ficha.py` lo mide, gratis.

| Qué | v2 | v3, el contrato | v3 con el índice en el código |
| --- | --- | --- | --- |
| Producto, correcto | 113 de 119 | 113 de 118 | igual |
| Destino, correcto | 96 de 103 | 95 de 102 | igual |
| Orden atado | 0 de 42 | 48 de 50 | igual |
| Condición atada | 53 de 144 | 39 de 63 | **52 de 63** |

- **El contrato, v3:** el orden es un campo cerrado con las claves de `catalogo.ORDEN`; la condición es una lista sin
  relleno; el tope del total y el medio van en el pago; cada tipo de consulta tiene una línea que lo define. Está en
  `pedido_documento/ficha.py`, `FICHA_V3`. Lo que en la fuente es cerrado se le ofrece cerrado al modelo.
- **El índice, en el bot:** `catalogo.atar` ata el origen partido en país de la marca y de fabricación, y los campos
  de sí o no por su clave de `specs_preguntables`. Test: `tests/test_atar_indice.py`. Las 3.107 grabadas, igual.
- **Lo que sigue sin atar:** "silencioso", "chiquito", "que entre en el bolsillo", "de malla", "marca conocida", que
  son vagas de verdad; y comparar, que no tiene herramienta.

## El procedimiento recomendado: llevar la ficha al bot

Una sesión. El intérprete deja de devolver la agenda y devuelve la ficha; un adaptador la lleva a la agenda que el
ejecutor ya cumple. El ejecutor, el borrador, la redacción y el cierre no cambian.

### 1. La base, antes de tocar nada

Correr el intérprete de hoy con el modelo, sobre:
- las 48 charlas de `pregunta_razonada/fichas.py`, calificando el pedido que queda en el borrador con la vara de
  `pedido_documento/medir_ficha.py`, que mira el resultado y no las acciones;
- los siete casos de producción, `jev/prod7.py`: hoy 15 de 21.

Es la comparación justa que falta: la ficha dio 38 de 48 con su vara, y lo de hoy nunca se midió con esa vara.

### 2. `app/core/flujo/ficha.py`, nuevo

- **La consigna:** `FICHA_V3` del banco, con tres cambios:
  - los números de la memoria como los escribe la libreta: M-2, L-1, R-1;
  - en cada consulta, además, `producto` —el que nombra, con su número si se mostró—, `con` para la compatibilidad, y
    `lugar` para el envío;
  - el pedido marca, con `responde`, la pregunta abierta que contesta.
- **El adaptador `a_agenda(ficha, estado)`:**

| De la ficha | A la agenda |
| --- | --- |
| `pedido`, si es distinto de los renglones del borrador | un `comprar` con `reemplaza` y `agrega` = el pedido entero; un artículo que ya estaba va con su renglón, L-1 |
| un artículo nuevo de un rubro, o con condiciones u orden distintos al criterio de su rubro | un `buscar` con su rubro, la cantidad del rubro, las condiciones y el orden |
| `preferencias` | sus condiciones y su orden, en cada `buscar` |
| `pago.medios` | `cuenta` con `reparto`; "sin decir 100" solo, no: es el relleno |
| `pago.tope_total` | `cuenta` con `tope` |
| consulta `buscar` | `buscar` con el rubro de `sobre`, condiciones y orden |
| consulta `producto` | `producto` con `producto` y `quiere_saber` = `sobre` |
| consulta `comparar` | un `producto` por cada uno, con el dato: no hay herramienta de comparar |
| consulta `compatibilidad` | `compatibilidad` con `producto` y `con` |
| consulta `envio` | `envio` con `lugar` |
| consulta `cuenta` | `cuenta` |
| consulta `regla de la tienda` | `politica` con el tema de `marcador._temas(sobre)`; sin tema, el candado |
| consulta `saber general` | `explicar` |
| `cliente` | `cliente` de la agenda |
| `dudas` | preguntas del turno, al final |

- La `cita` de cada pregunta es su `sobre` o el producto: la usan el candado y el vendedor.

### 3. Lo que se borra

Por la regla de cero cosas sueltas, de `interprete.py`: `CONSIGNA`, `EJEMPLOS`, `DEVUELTA` y la vuelta de `faltas`,
y la tabla del marcador del mensaje al modelo. `agenda.faltas` y `sin_citar` quedan sin uso: se borran si nadie más
los llama. `elegir`, `explicar` y `vender` siguen.

### 4. La batería, sin modelo

`ficha_v3.jsonl` tiene las 48 fichas que devolvió el modelo. Son la batería del adaptador: cada ficha grabada, por el
adaptador y el ejecutor, tiene que dejar el pedido que dice la vara. `tests/test_ficha.py`, con cuántos pasan, y un
techo que solo baja. `tests/test_cableado58.py` no cambia: usa las agendas a mano.

### 5. La medición con el modelo

Lo mismo que el paso 1, con la ficha. **Entra si** en las 48 no baja de la base, en `prod7.py` no baja de 15 de 21, y
la batería sigue verde. Con la gratis primero; Gemini con la paga para confirmar, unos 12 centavos.

### 6. El deploy

Con el ok de Martín. Se vuelve con `git revert` del commit del intérprete.

### Lo que queda a medias, y se escribe como xfail

- **Lo condicional:** "si es poca plata, cambialo". La ficha lo dice en palabras, en `si`, y la agenda necesita
  `{"de": n, "da": "si"}`. Primero se cumple sin condición y se marca `A MEDIAS:`.
- **Lo supuesto del borrador:** "¿Lo dejo así?" se acepta con `responde`; hay que verlo en las charlas K.
- **`regrado.py` ya no mide al intérprete:** sus 3.107 son agendas del contrato viejo. Sigue valiendo para el código de
  después del adaptador. Las fichas grabadas de producción reemplazan a esas, de a poco.

## Recomendaciones para mejorar el bot, en orden

1. **La ficha nativa,** el procedimiento de arriba.
2. **Las fichas de producción como banco:** cada ficha que devuelve el modelo en vivo queda en el log, y las grabadas
   pasan a ser la batería sin modelo, como hoy las 3.107 agendas.
3. **El error que avisa:** el modelo casi nunca pregunta. El código compara lo que reconoce en el mensaje —números,
   lugares, rubros— contra la ficha, y lo que falta vuelve una vez al modelo o se le pregunta al cliente.
4. **"Entendí:"** en los pedidos de varios artículos, el código arma desde la ficha un resumen corto. Si el modelo
   entendió mal, el cliente lo ve y lo corrige: es el recibo y la confirmación en una pieza.
5. **Comparar,** una herramienta: dos productos por un dato de la ficha. Hoy se parte en dos consultas.
6. **Las condiciones vagas,** solo cuando no atan: el modelo elige entre los valores del rubro, en una llamada chica,
   para esa condición sola. Es la escalera; no corre en todos los mensajes.
7. **El medio que la tienda no toma,** dicho al cliente: débito, efectivo o Naranja, que la FAQ no nombra. Es el xfail
   de `tests/test_medio_de_pago_cerrado.py`.
8. **Producción como banco,** el SIGUE 4: los siete casos reales como instrumento fijo con piso.
