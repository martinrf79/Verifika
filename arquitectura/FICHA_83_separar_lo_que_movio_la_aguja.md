# FICHA 83 — Separar el mensaje: lo que movió la aguja

27-oct-2026, sesión con Martín. Sigue a la FICHA 82. **Es banco: nada de esto está en el bot.** Los instrumentos son
`banco_pruebas/momento0.py`, `razonar.py`, `sinteticas_separar.py` y `sinteticas_verifika.py`. Cada número tiene su
commit, que lo cuenta solo.

## La idea, de Martín

Primero separar bien, y solo separar. El modelo no tiene que inventar nada: tiene que leer lo que pidió el cliente y
dejar cada cosa en su lugar, con lo que mejor sabe hacer. Si esa base es firme, traducir y etiquetar vienen después.
Hasta que no llegue al 95%, no se pasa a lo siguiente.

## Lo que movió la aguja

**Cambiar lo que se le pide al modelo, para que haga algo que ya sabe hacer.** No le pedimos "partes con etiquetas",
que es un invento nuestro y necesita reglas. Le pedimos lo que pide el cliente, en primera persona y con sus palabras:

- una línea por cada producto y cada destino, con campos fijos: cosa, cantidad, destino y "si";
- la condición en su propia línea, y lo que depende de ella con su "si";
- lo que vale para todo el pedido, una vez, en "todo";
- dos ejemplos de la forma exacta: un reparto a destinos y una compra con condición.

Sobre los 91 primeros mensajes del banco, con la misma vara de una línea por cosa: **de 67 a 82**.

**Medir la información, no la forma.** La vara pedía una línea exacta por cosa. Revisadas a mano, las fallas tenían la
información completa en otra forma —"¿cuánto sale cada envío?" con los destinos en las otras líneas— que el código
puede llevar a su forma normal. Midiendo si falta algo del mensaje: **89 de 91**.

## Lo que no movió la aguja

| Lo probado | Resultado |
|---|---|
| Solo la consigna de separar, sin campos | 67 de 91: escribe preguntas al cliente, junta por destino, cruza todo con todo |
| Contar primero cuántas cosas pide | 79 contra 82: resta |
| Atar la salida al esquema, o pedirla libre, o en tabla | 89, 89 y 87: igual |
| Razonar, Gemini, sobre 30 difíciles | sin fijar 28, mínimo 28, bajo 27, medio 29; alto, dos minutos y 63.000 tokens por mensaje |
| DeepSeek sobre los mismos 30 | sin razonar 25; razonando 27, con 15 segundos de mediana |
| Mejoras de consigna sobre las de tiendas: la pregunta siempre en su línea, comprobación final, ejemplos abstractos | 47 contra 48: resta |
| Un filtro del código que elige qué bloques entran | detecta lugares 11 de 15 y "varias cosas" 52 de 86: lo que se escapa es lenguaje |
| Los ejemplos parecidos por embeddings | la acción correcta entre los 5 primeros en 76%: no alcanza |

Sin fijar, el modelo de producción no razona: igual que el nivel mínimo.

## Lo medido, con la consigna de las líneas

| Examen | Qué es | Bien |
|---|---|---|
| Primeros mensajes del banco | 91, de las 48, las 58 y las nuevas | 89 |
| El desmenuzado de la FICHA 67 | 138 primeros mensajes, escritos el 4-oct, nunca usados para la consigna | 125 |
| Muestra difícil | 30, los de más cosas y los más largos | 28 |
| Sintéticas de ocho tiendas | 48 complejas, con el rubro y los temas de cada tienda | 48 |
| Sintéticas de Verifika | 200 complejas, armadas por código con semilla | 190 |
| Con charla previa | 78 turnos, con la libreta | 68, contra 70 de la lectura de hoy |

Lo que falla en el primer mensaje casi no es de separar: es de traducir, el rubro que el cliente no nombra —"escribir
más cómodo", "algo para escuchar música en la casa" escrito como auricular—. Lo que falla con charla: cuando el cliente
pregunta por algo ya mostrado, el modelo pone un tema de la tienda en "cosa" en vez del número de la libreta.

Costo: la consigna pesa unos 700 tokens con la lista de temas, contra unos 3.700 de la lectura de hoy. Una llamada, unos
1,3 segundos de mediana.

## La consigna

Está en `banco_pruebas/momento0.py`, `LINEAS`, con sus dos ejemplos `EJ1` y `EJ2` y el esquema `_formato_lineas`. Para
otra tienda cambia solo el rubro de la primera línea y la lista de temas, que salen de sus datos.

## Lo que falta antes de confiar en el 95%

1. **Clientes reales.** Los exámenes los escribimos nosotros o el código. Falta pasar los primeros mensajes reales de
   producción, `produccion.py`, y los siete casos de producción.
2. **Lo que entra de más.** La vara mide que no falte nada, no que no sobre: en un caso inventó un pago, en otro repitió
   una compra. Falta contar las líneas de más.
3. **La misma pregunta dicha de otra forma.** Las 200 de Verifika salen de plantillas: comparten forma. Falta medir
   variantes de redacción de las mismas compras.
4. **Con la paga.** Las de tiendas, las 200 y la memoria corrieron con la clave gratis. Es el mismo modelo; conviene una
   corrida de control con la paga antes de llevarlo al bot.

## Cosa y tema en campos separados, 28-oct

Con un solo campo, la regla de poner el tema de la lista se llevaba lo que no es una regla: "algo para tipear" salía
"asesoramiento". Con "cosa", el producto o su número de la libreta, y "tema", solo si pregunta una regla, la separación
no empeora —primeros 90 de 91, desmenuzado 124 de 138, con charla 69 de 78— y la búsqueda de rubros por la cosa sube de
76 a 106 de 132 entre los tres primeros. Está en `momento0.py`, `consigna_tema` y `formato_tema`.

## La búsqueda de cada línea, 28-oct

`banco_pruebas/buscar_sinteticas.py` y `buscar_mejoras.py`: 238 frases escritas a mano —132 de rubro dichas de seis
formas, 48 de tema, 58 de producto por apodo— separadas por el modelo y buscadas en un solo índice de la tienda: rubros
con sus alias, temas con sus palabras de la FAQ, y productos.

| Criterio | Lo correcto entre los tres primeros, de 238 |
|---|---|
| Las palabras del cliente y la cosa del modelo, sumadas | 216 |
| Lo mismo, con el tipo de tarea de los embeddings: consulta y documento, por la puerta nativa de Google | **224** |
| Más datos de la tienda en el índice, o la frase sin relleno | 218 a 222 |
| Primero lo exacto por nombre y alias, después embeddings | 219 |

El mejor criterio: embeddings con tipo de tarea, las dos búsquedas sumadas, y para los temas el tema que eligió el
modelo de la lista. Demora: una sola llamada por mensaje con todas sus líneas, unos 0,3 segundos. Las palabras del
cliente buscan mejor los rubros; la cosa del modelo, los productos y los temas. Donde no coinciden está el error de
traducción: "algo para escuchar música en la casa" es parlante por las palabras y auricular por la cosa.

## La regla de duda, 28-oct

Sobre las 238 frases grabadas, sin modelo. El primer candidato acierta 201; entre los tres primeros, 224. La mejor señal
es que la búsqueda con las palabras del cliente y la de la cosa no elijan lo mismo: marca 83 y caza 30 de los 37
errores; lo que no marca está bien en 148 de 155. Que el primero gane por poco suma casi nada. Los cinco errores que no
caza ninguna señal piden consejo, no búsqueda: "la notebook va lenta" es memoria, "el procesador llega a 90 grados" es
cooler.

## La respuesta, 28-oct: quién hace qué después de separar

Pedido de Martín: con las líneas y sus candidatos, ¿responde el código solo, o una segunda llamada al modelo? Todo se
mide igual, por el webhook entero, con las casillas del turno en `vara_58.json`; los turnos de antes con la agenda a mano.
Tres exámenes: los primeros mensajes de las 58 y las complejas, 65; fuera de muestra, los primeros de las K y las J que no
están en la batería, 24, separados y leídos con la gratis, `responder_lineas.py --grabar`; y los turnos con charla, 40.

| Cómo se responde | Instrumento | Primeros, de 65 | Fuera de muestra, de 24 | Con charla, de 40 |
|---|---|---|---|---|
| La agenda a mano, el techo del código | | 65 | 13 de 14 | 40 |
| La lectura de hoy, la del bot | | 64 | 19 | 37 |
| El código solo, con las líneas y los embeddings | `responder_lineas.py` | 64 | 18 | sin medir |
| El modelo llama al menú de la agenda como herramientas | `herramientas_modelo.py` | 59 | 18 | 35 |
| Lo mismo, con tres reglas más en la consigna | `herramientas_modelo.py --v2` | 60 | 18 | 35 |
| Herramientas de asistente de compras y el estado como carrito | `carrito_modelo.py` | 55 | 17 | 37 |
| El modelo solo clasifica cada línea y el código pone los datos | `hibrido.py` | 62 | 18 | 32 |
| Lo mismo, separando y clasificando en una llamada | `hibrido.py --a` | 59 | 16 | 31 |
| El modelo responde como vendedor y deja huecos que llena el código | `agente_ventas.py` | 58 | 23 | 33 |
| Lo mismo, con las cinco mejoras | `agente_ventas.py --libre` | **60** | **22** | **36** |
| Lo mismo, con la salida atada a un esquema | `agente_ventas.py --atado` | 54 | 16 | 33 |

Una corrida de cada una. El código solo con las líneas llegó a 64 de 65 escrito mirando esas 65; fuera de muestra cada
falla nueva pedía otra regla, que es el patrón de la maraña.

**Lo que movió la aguja: pedirle al modelo que responda, no que traduzca.** El agente de ventas con huecos, idea de
Martín: el modelo escribe la respuesta como vendedor y, donde va un dato que no sabe —precio, stock, opciones, envío,
total, regla—, deja un hueco con lo que necesita, `[[OPCIONES clase=mouse orden=mas barato cantidad=2]]`. El código llena
todos los huecos en una sola agenda, como un turno, con el ejecutor de siempre, y cada hecho va a su hueco. Es lo que el
modelo ya sabe hacer: contestar. En las herramientas, en cambio, usaba su entrenamiento solo en la forma; los
significados eran nuestros —lo supuesto, el orden para todo, los números L y M— y fallaba justo ahí.

Las cinco mejoras de la versión libre, sacadas de las fallas de la primera: el producto en el hueco como lo nombró el
cliente o por su número del estado; los campos del hueco por nombre; no afirmar lo que dice un hueco; contestar solo lo
que preguntó; lo señalado de la charla por su número. Con charla sube de 33 a 36.

**Lo que no movió la aguja:** atar la salida a un esquema, igual que al separar: con los temas y las clases como listas
cerradas los usa donde no van. Darle los productos candidatos: los nombra donde el código tiene que elegir por el orden.
La segunda vuelta de embeddings sobre los candidatos, descartada antes de medir: los candidatos ya son las etiquetas.

Costo: la versión libre, unos 1.030 tokens de entrada y 56 de salida, menos de un segundo; con la separación, dos
llamadas por mensaje. Entrevista al modelo sobre cómo prefiere hacer este paso: `entrevista_respuesta.py`.

## Lo que sigue

1. Repetir el agente libre dos veces más, con la gratis, para ver cuánto varía antes de confiar en dos o tres casos.
2. Sus fallas: pide precio de una clase en vez de opciones, K09; deja el total cuando pregunta "cuánto sale", K16; y lo
   que señala de turnos anteriores, C27, C55, K20 y K21.
3. El limado como parte del código: cada hueco validado, el producto por el catálogo y el destino por el padrón; lo que
   no pasa, pregunta al cliente. Hoy vive en `agente_ventas.py`.
4. Los siete casos de producción y las charlas enteras, antes de llevarlo al bot.
