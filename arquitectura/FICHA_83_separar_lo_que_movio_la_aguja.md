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

La versión libre se repitió dos veces el 29-oct, `agente_ventas.py --libre --rep 2` y `--rep 3`: las tres corridas dan
lo mismo caso por caso, 118 bien y 11 mal, ninguno cambia. A temperatura 0 el modelo contesta igual: la diferencia con la
lectura de hoy no es ruido de la corrida. Las demás, una corrida de cada una. El código solo con las líneas llegó a 64 de 65 escrito mirando esas 65; fuera de muestra cada
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

1. Sus fallas: pide precio de una clase en vez de opciones, K09; deja el total cuando pregunta "cuánto sale", K16; y lo
   que señala de turnos anteriores, C27, C55, K20 y K21.
2. El limado como parte del código: cada hueco validado, el producto por el catálogo y el destino por el padrón; lo que
   no pasa, pregunta al cliente. Hoy vive en `agente_ventas.py`.
3. Los siete casos de producción y las charlas enteras, antes de llevarlo al bot.

## El 29-oct: la etiqueta, el puente en grande y el buscador de la tienda

Todo es banco. Cada número tiene su commit.

**La etiqueta de cada línea**, `etiquetar.py`, sobre las 238 frases: la regla de que las dos búsquedas, su suma y lo
exacto elijan lo mismo da 121 seguras con 3 mal, el 1,3%. Las dudosas al modelo con cinco candidatos no pasan la vara:
9,2% mal. Cuando el cliente describe una necesidad, el modelo elige el equipo que nombra o asesoramiento.

**El puente del código en grande**, `lineas_agenda.py`: las 200 sintéticas traen lo correcto del generador, y se califica
la agenda por cosa pedida. Seis arreglos de clase en `responder_lineas.py` —el modelo como lo dijo el cliente, el pago
que suma cien, el tope del total y el de una cosa, la frase de la FAQ dicha tal cual, el no en el medio de la condición,
el color sin el destino—, y uno en el bot vivo, `marcador.py`: con dos modelos seguidos se perdía el primero. Semilla
2710: el código con las líneas 190 de 200, la lectura de hoy 156; semilla 3110, nunca mirada, 193. Lo que falla es la
traducción. La respuesta entera por el webhook, `--respuesta`, muestra que lo que frena a los dos caminos es la conducta
del ejecutor: pregunta el color o a dónde va antes de dar el total de lo que ya está claro.

**El buscador de la tienda**, `buscador_agente.py`, orden de Martín: adaptar las herramientas a lo que el modelo sabe por
entrenamiento. Antes, la entrevista, `entrevista_buscador.py`, sobre los 17 más difíciles: busca una cosa por búsqueda,
con su criterio, quiere pocos resultados con stock y en el orden pedido, y para el presupuesto pide un generador, no una
calculadora. Las herramientas: buscar en castellano libre sobre `catalogo.buscar`, las reglas y el envío; presupuesto,
que cumple el ejecutor y el código pega tal cual; y un candado que le devuelve al modelo una vez los montos y medidas que
no salieron de las herramientas ni de la charla, y que no deja elegir un producto que no buscó.

| Cómo se responde | Primeros, de 65 | Fuera de muestra, de 24 | Con charla, de 40 | Con datos inventados |
|---|---|---|---|---|
| La lectura de hoy, la del bot | 64 | 19 | 37 | sin medir |
| El agente con huecos, libre | 60 | 22 | 36 | sin medir |
| El buscador de la tienda | **63** | **23** | **37** | 0, con el candado |

Sobre los 17 difíciles: 8 en la primera vuelta, 14 con los arreglos de la herramienta. Lo que no movió nada: reglas en
la consigna para que busque con el criterio del cliente y para que controle las cantidades por clase. Unos 3.300 tokens
de entrada y dos segundos y medio por turno; la corrida de los 129, unos 14 centavos de la paga.

Lo que queda: los cambios del pedido en varios turnos, K20 y K21, donde ningún camino con modelo acierta; la fuente, que
trae "core i5" en los tags de la HP 245 G9 Ryzen 7 y hace ambiguo al modelo Core i5 también en el bot vivo, a corregir con
el permiso de Martín; y casillas de redacción estrictas, "no estamos trabajando con celulares".

### La memoria del buscador en la charla entera, 29-oct a la noche

Pregunta de Martín: si el primer turno salió bien, ¿el error del turno siguiente es de memoria? Sí. En los turnos con
charla, la prueba arrancaba del pedido y las respuestas que dejó el flujo viejo con la agenda a mano, donde "los otros
dos" a Posadas quedaron sin resolver; el buscador sí los había resuelto en su propio primer turno. Con su propia memoria,
la charla completa sin resumir y su pedido tal como quedó, K20 y K21 dieron 9 de 9 turnos.

`buscador_agente.py --charlas`: las 26 charlas de dos turnos o más de punta a punta. La memoria guarda las dos cosas, el
último presupuesto que vio el cliente y el pedido anotado, que solo cambia si el cliente compra, confirma o cambia; el
presupuesto lo marca con `anotar`. Tres corridas: 70, 71 y 69 de 75 turnos; 21 o 22 de 26 charlas enteras.

Lo que apareció: con el pedido cerrado, el modelo inventó un CBU, un alias, un banco y un link. Ahora el cobro es una
herramienta, `cobrar`, que da los datos del código de cobro del bot —la cuenta demo y el link demo—, y el candado mira
también links, números largos y alias. En la corrida siguiente, ningún dato inventado.

Unas 2,3 llamadas al modelo por turno: una pide las búsquedas, todas juntas; otra escribe; una más si arma presupuesto
o si el candado le devuelve un dato. No hay llamada aparte para separar: el modelo separa solo, una búsqueda por cosa.

### El verificador de afirmaciones, 29-oct a la noche

Objeción de Martín: una arquitectura libre con DeepSeek se sacó porque las alucinaciones no se distinguían de las
respuestas buenas. `banco_pruebas/verificador.py`, sin modelo, controla cada afirmación de la respuesta contra la fuente
—lo que devolvieron las herramientas, la charla y el mensaje—, sin lo que el código pegó tal cual: datos —montos,
medidas, links, CBU, alias—, productos nombrados, atributos de un producto con `catalogo.atar` y `cumple`, superlativos
contra el orden del rubro y stock. `alucinaciones.py` lo mide sobre 164 respuestas grabadas del buscador, con siete
clases de alucinación inyectadas.

| | Primera vuelta | Con los arreglos del verificador |
|---|---|---|
| Inyectadas cazadas | 838 de 995, 84% | **819 de 827, 99%** |
| Respuestas buenas marcadas | 47 de 204, 23% | **1 de 164, 0,6%** |

Las falsas alarmas eran del verificador, no del modelo: el "2x" del presupuesto leído como el modelo "Ventus 2X", la
marca de otro producto en la misma oración, "también" atado a un campo de texto libre, "no tiene latencia" leído como
sin stock, un superlativo comparado con otro color del mismo modelo. Se escapan: "es RGB" cuando el RGB está en el
nombre y no en un campo, cinco; un producto en una charla larga; un monto que coincide con otro de la fuente.

Conectado al buscador: el candado es el verificador, y lo que marca vuelve una vez al modelo. Falta medirlo con el modelo.
El tamaño: 112 líneas el verificador y 117 su banco.

### La atadura por API, medida

Con el modelo de producción, el mismo pedido con un esquema de 0, 10, 200 y los 880 nombres del catálogo cobra igual,
23 tokens de entrada, y tarda lo mismo. Atada sin "ninguno", "celular samsung" elige la tablet Samsung; con "ninguno",
contesta ninguno. La atadura asegura que no invente lo que no existe; no asegura que elija bien ni lo que escribe libre.
