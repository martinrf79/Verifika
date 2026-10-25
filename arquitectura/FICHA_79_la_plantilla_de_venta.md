# FICHA 79 — La plantilla de venta: casos resueltos y el motor, con nuestra fuente

25-oct-2026, sesión con Martín. **Es el plan para la sesión nueva: nada de esto está hecho.** Sigue a la FICHA 78.
Reemplaza la plantilla de `banco_pruebas/casos_plantilla.py` y los 491 casos de la sesión anterior, que se borraron el 25-oct y quedan en git, 684b2a1.

## El objetivo

El objetivo de Verifika es la mitad vender o conseguir el lead, y la mitad no alucinar. **La no alucinación la
garantiza el código**: los montos, el stock y las tarifas salen de las herramientas. **Los casos resueltos son para
vender**: que el modelo entienda qué quiere el cliente en cada momento de la venta y le pida al código lo justo.
La posventa queda para después.

## Por qué no sirven los 491 casos de la sesión anterior

Revisados uno por uno el 25-oct:
1. **Frases de robot**: el hueco se llena con el nombre interno del rubro, "¿y en motherboard que tenes?", "busco
   memoria ram, algo que no sea muy caro". El vector compara la palabra del rubro, no la forma de la pregunta.
2. **Copias**: seis llenados por forma que cambian solo el producto. Los cinco más parecidos son cinco copias con la
   misma etiqueta.
3. **Temas rotos**: "¿que onda con sin interes?", "¿como es lo de de donde es?", pedazos de las palabras clave de la FAQ.
4. **Datos sin sentido**: "lo de parlante, ¿como es la retroiluminacion?", "lo de ssd mejor en negro".
5. **Nombres de catálogo enteros**: "el Lenovo LOQ 15 Core i7 16GB 1TB SSD". El cliente dice "la Lenovo LOQ".
6. **Sin mostrador**: los casos con pedido no traen el pedido, y ninguna respuesta apunta a un L-n o un M-n.
7. **Sin las clases de venta difíciles**: indecisión, cambio de idea, objeción de precio, para quién es, condicional.
8. **Las 48 y las 58 van con el mensaje entero** como un caso; la FICHA 78 midió que la búsqueda va por parte.

## Lo que se aprendió afuera

No hay un banco de casos de venta en castellano para una tienda de tecnología. Hay métodos que se copian:
- **Wizard of Shopping, ACL 2025**: genera charlas de compra recorriendo un árbol hecho con los atributos del catálogo,
  rubro, característica, valor, producto. Nuestro árbol ya existe: `specs_preguntables.json` y los valores del catálogo.
- **NeMo Guardrails, NVIDIA**: el mensaje se busca por embeddings entre frases de ejemplo con su forma canónica; vuelven
  las cinco más parecidas y el modelo elige; si hay un flujo o un mensaje escrito para esa forma, lo usa el código. Es
  nuestro diseño: casos, búsqueda, el modelo elige, el código cumple.
- **INSPIRED**: cada frase del vendedor con su estrategia —opinar, dar confianza, alentar—, asociadas a más
  recomendaciones aceptadas. Va en la respuesta del vendedor, junto con las movidas de `base_conocimiento.json`.
- **ProductAgent, EMNLP 2025**: preguntas de aclaración que achican la búsqueda, una por vez.
- **CraigslistBargain**: los actos de la negociación, para la objeción de precio y el pedido de descuento.
- **LangChain MMR**: traer casos parecidos pero distintos entre sí.
- **U-NEED, de Alibaba**: preventa anotada con las necesidades del cliente. Solo para investigación: se copia la forma
  de anotar, no los datos.

## El caso

Un caso es **una parte**: una sola cosa que pide el cliente. La combinación la separa la llamada 1.

| Campo | Qué es |
| --- | --- |
| `etapa` | la etapa de la venta, de la lista de abajo |
| `situacion` | el id de `base_conocimiento.json` que aplica, si hay: `indecision`, `objecion_precio` |
| `mostrador` | la foto chica de la charla, con la forma de `interprete.libreta`: renglones L-n con rubro, producto, cantidad, color, destino y para quién; mostrados M-n; la pregunta abierta R-n y lo que espera. Vacío si es el primer mensaje |
| `frases` | tres a cinco formas de decirlo, escritas a mano en rioplatense, con voseo, jerga y tipeo; productos con nombre corto |
| `traduccion` | lo que pide en nombres de la tienda: rubro, campo y valor, orden, tema, "otro" o "duda" |
| `respuesta` | la etiqueta de la lista de `respuestas.py`, con el L-n o M-n al que apunta |
| `agenda` | el pedido al código, en la forma de `app/core/flujo/agenda.py` |
| `vendedor` | la respuesta del vendedor, corta, con huecos que llena el código: "el {producto} sale {precio}, ¿te lo sumo?". Nunca un número escrito |
| `confirma` | si la lectura es dudosa, la frase de confirmación o la repregunta |

**Las uniones van como forma aparte**, no como caso: "si sí, ese", "si no hay, el otro", "uno para cada uno", "y
además". Son pocas y se repiten en todas las charlas.

## El esqueleto: las etapas de la venta

Cruzadas con las 106 situaciones de `data/clientes/verifika_prod/base_conocimiento.json`:
1. **Apertura**: saludo, o pregunta directa por un producto.
2. **Descubrir la necesidad**: "necesito algo para…", para quién es, presupuesto, uso, el problema que cuenta. Una
   pregunta por vez.
3. **Mostrar y recomendar**: opciones con precio, "¿cuál me recomendás?", el más barato, el mejor, el más algo.
4. **Dudas y objeciones**: comparar, compatible con lo suyo, si es original, caro, descuento, desconfianza, lo que la
   tienda no vende, un precio que dice que le dijeron.
5. **Decidir**: indecisión, cambio de idea, "mejor el otro", la condición, "si viene en negro me lo llevo".
6. **Armar el pedido**: cantidad, color, destino y para quién, varios destinos, cambiar o sacar un renglón, el total.
7. **Cerrar**: el medio de pago, el reparto, el nombre, el link.
8. **No compra todavía**: "lo pienso", "después te aviso": guardar el lead sin presionar.

Cada etapa se cruza con los estados del mostrador: sin pedido, un renglón, varios del mismo rubro para personas o
destinos distintos, y cada tipo de pregunta abierta.

## Cómo se llena

1. **Las formas y las frases, a mano**, sin mirar las 48, las 58, las cien difíciles, el examen ni `alias.json`.
2. **Los huecos, con la fuente**: `productos.csv` con nombre corto, `specs_preguntables.json` dicho como lo dice un
   cliente, `faq.json` con una pregunta escrita a mano por tema, `compatibilidad.csv`, `no_vendidas.json`.
3. **Las charlas de descubrir y mostrar, con el método de Wizard of Shopping**: el árbol del catálogo da el camino, de
   la necesidad al producto, y cada paso es un turno.
4. **La validación, por el ejecutor**: cada `agenda` se corre por `app/core/flujo/ejecutor.py` con su `mostrador`; el
   caso entra solo si se cumple y devuelve lo que el caso dice. Gratis, sin modelo.
5. **El examen afuera**, como en `motor_casos.UMBRAL_EXAMEN`.

## La búsqueda

- Por parte, sobre la traducción de la llamada 1, y con el estado del mostrador como peso, no como filtro.
- MMR: como mucho dos casos por forma, para que vuelvan etiquetas distintas.
- Junto a los casos, la situación de `base_conocimiento.json` y los datos de la tienda que la parte toca: el rubro con
  sus campos y valores, el tema con su respuesta.

## La sesión nueva, y cuándo está hecha

Sin modelo y sin paga. Sin instrumentos nuevos de medición.
1. El cruce de las 106 situaciones contra las etapas: qué etapa cubre cada una y qué falta.
2. El esquema del caso en código, en `banco_pruebas/`, reemplazando `casos_plantilla.py` y `motor_casos.py`, en el mismo
   commit.
3. **Veinte escenas de muestra**, de las ocho etapas, con mostrador, frases, agenda y vendedor, validadas por el
   ejecutor.
4. **Martín las revisa** antes de llenar el resto. Si no le parecen como las resolvería un vendedor, se corrigen ahí.

**Está hecha** cuando Martín aprobó las veinte. El llenado entero, los vectores y la medición con
`banco_pruebas/cobertura_lecturas.py` van en la sesión siguiente.
