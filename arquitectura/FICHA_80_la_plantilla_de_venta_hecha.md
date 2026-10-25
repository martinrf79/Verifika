# FICHA 80 — La plantilla de venta, hecha: las 58 ampliadas y los casos resueltos para los dos motores del modelo

25-oct-2026, sesión con Martín, sin modelo y sin paga. Sigue a la FICHA 79, que era el plan. Vive en
`banco_pruebas/plantilla_venta/` y la controla `tests/test_plantilla_venta.py`.

## Lo que pidió Martín

1. Ampliar las 58 combinaciones para que cubran cualquier tienda online, o casi.
2. Sumar a los casos del repo lo que traen las bases públicas de preguntas de comercio electrónico.
3. Armar la plantilla clasificando todo, con preguntas sintéticas para subir la dificultad.
4. Que el modelo etiquete mirando los casos y el código arme la respuesta con datos deterministas. Corregido por
   Martín el mismo día: los motores son del modelo, no del código. Uno, indispensable, para que el modelo etiquete lo
   que pide cada pregunta; otro, opcional y anterior, para interpretar y hacer la primera traducción. El código, si la
   etiqueta es buena, busca los datos. El cuello de botella es que el modelo le pida bien al código lo que necesita.
5. Cargar la fuente de Verifika, completa.

## La memoria: no van charlas, va el mostrador

La pregunta de Martín: si la memoria del bot está bien armada, ¿hacen falta casos con memoria? **Casi: no hacen falta
charlas en la plantilla, pero sí el estado.** La misma frase tiene etiquetas distintas según lo que hay en la charla:
"el negro" es elegir un color si el bot lo preguntó, cambiar un renglón si ya está en el pedido, y un dato si solo se
mostró. Sin el estado, la plantilla le enseñaría al modelo a adivinar.

Por eso un caso no lleva historial: lleva `antes`, los turnos de antes como agendas. El código los corre por el
ejecutor real y el caso guarda la libreta que resulta, la misma que ve el modelo en vivo. Así la memoria la arma el
bot, como dice Martín, y el caso solo muestra la foto chica que hace falta para etiquetar bien.

## Lo que se trajo de afuera

La red de la sesión no llega a Hugging Face ni a arXiv; sí a los README de GitHub y a la búsqueda. De cada base se tomó
la forma de clasificar, no los datos:
- **Bitext**, 27 intenciones en 10 categorías, licencia CDLA-Sharing-1.0: casi toda postventa y cuenta de usuario. De
  ahí salen las clases de postventa y, sobre todo, las **marcas de variación del lenguaje** —básica, interrogativa,
  coordinada, negación, cortés, coloquial, palabras sueltas, abreviada, con errores, indirecta, mezcla de idioma,
  ofensiva—, que cada frase de la plantilla lleva puestas.
- **Gorgias**, citado por Macha: la preventa en seis intenciones, disponibilidad, detalles, uso, promoción, garantía y
  mayorista. De segunda mano.
- **Amazon PQA y AmazonQA**: la pregunta de sí o no contra la abierta, y la que la ficha no contesta.
- **EQA**, Yang y Alonso, SIGIR eCom 2024: solo se confirmó su clase de instrucción, cómo se usa o cómo se compra.
- **CraigslistBargain**: los actos del regateo, contraoferta, insistir, rechazar.
- **INSPIRED**: las estrategias del vendedor, para cuando la redacción sume la venta.
- **Wizard of Shopping**: la necesidad se achica una condición por vez.

## El mapa

`mapa.py` tiene las clases por etapa de la venta: apertura, descubrir, mostrar, dudas, decidir, armar, cerrar, no
compra, postventa, fuera de la tienda y las uniones de dos partes. Cada clase dice de dónde salió, qué situación de
`base_conocimiento.json` aplica y qué acción del menú la cumple. **Las 58, las J y las K están todas clasificadas**: el
test lo controla. Lo nuevo frente a las 58 es lo que Verifika no había visto: el regalo sin saber qué, la gama, las
fotos, la objeción de precio, el descuento, el precio que le dijeron, la competencia, la confianza, las cuotas, el
retiro, lo urgente, contra entrega, usados, envoltorio, el servicio que no está escrito, el nombre, el comprobante, el
que lo piensa, el que se enoja, el humano, la postventa y la cuenta de usuario.

Cuando el ejecutor no tiene con qué cumplir una clase, la clase dice `falta:` y su caso usa lo que hay: asesorar,
recomendar, opinar, fotos, validar el medio de pago y la reseña. No se inventó ninguna acción.

## El caso

`casos.py`: un caso por clase, con huecos, igual para cualquier tienda. Lleva frases a mano en rioplatense, con su
marca de variación y las difíciles marcadas, `antes`, la agenda del menú como etiqueta, lo que tiene que volver del
ejecutor y la repregunta si la lectura puede ser otra. Las respuestas cortas a
una pregunta del bot, "sí" o "negro", van con `responde`: las ata el código, como en vivo.

## El llenado con la fuente

`llenar.py` llena los huecos con `data/clientes/verifika_prod/`, sin modelo y sin credenciales:
- el rubro, con las palabras de la base de conocimiento que el código lee como solo ese rubro, rotando por frase;
- el producto, con el nombre más corto que la identidad certifica: "el G305", no el nombre del catálogo;
- el color, uno que dicho deja un solo producto; las condiciones, de los campos que describen y que el catálogo
  filtra; los montos, redondeados como los dice un cliente;
- el tema, por su nombre universal llevado al de la FAQ de la tienda.

Después corre cada caso por el ejecutor con su mostrador, compara lo que vuelve con lo que el caso espera, y arma la
respuesta. Lo corre el test en cada batería.

## Los dos motores del modelo, y lo que cada caso le da

La primera versión de esta ficha tenía un motor de respuestas del código, `motor.py`, con una frase de vendedor por
veredicto. Era una lectura equivocada del pedido y se borró: la respuesta la arma el código que ya existe.

Cada caso dice, desde su agenda y sin modelo, lo que tiene que devolver cada motor por cada parte del mensaje:
- **la traducción**, para el motor de interpretación: lo que pide en los nombres de la tienda, sin la acción;
- **la etiqueta**, para el motor de etiquetado: la respuesta de la tienda que pide, de la lista de
  `banco_pruebas/respuestas.py`, y lo que señala de la libreta, M-n, L-n o R-n.

El test prueba que con esas dos cosas el código arma la agenda exacta del caso, sin mirar nada más. Lo que la lista de
respuestas no tiene con qué etiquetar queda como `falta:` y se ve: asesorar, recomendar, opinar, fotos, validar el
medio de pago y la reseña. El humano, el fuera de tema y el catálogo caen en "nada", y solo la traducción los separa.

Esto no calibra todavía al modelo: dice qué tiene que devolver. La calibración es correr el motor de etiquetado con
los casos más parecidos a la vista y contar contra la etiqueta de cada caso, y contra las 48 y las 58.

## Lo que encontró la plantilla en el código

Defectos reales, cada uno como xfail estricto en el test:
1. "¿Sirve para trabajo y estudio?" contesta que no tiene el dato y cita la ficha que lo dice.
2. "¿De dónde es?" contesta que no tiene el dato, y el catálogo trae el origen.
3. "Me dijeron que estaba a tanto" contesta "No tengo el dato de sale tanto": el precio afirmado no se compara.
4. "Son dos en total" con un solo renglón deja la respuesta vacía.
5. Un medio que la tienda no toma, cripto, entra al total sin aviso. Ya estaba en SIGUE 3.

Y en la fuente, palabras de la base de conocimiento que el código lleva al rubro equivocado: "compu" a monitor,
"portátil" a almacenamiento externo, "cpu" a cooler, "placa madre" a placa de video, "wifi" a impresora, "red" a placa
de video. Las lista el informe de `llenar.py`.

## Lo que queda

1. **Martín revisa los casos**: `python3 -m banco_pruebas.plantilla_venta.llenar --ver todos`, o una clase con
   `--ver DU26a`. Lo que no resolvería así un vendedor, se corrige en `casos.py`.
2. El motor de etiquetado: la búsqueda por parte con MMR y los vectores sobre esta plantilla, la consigna con los
   casos a la vista, y la calibración contra la etiqueta de cada caso, las 48 y las 58, con la clave gratis. Reemplaza a
   `casos_plantilla.py` y `motor_casos.py`, que siguen solo porque los usan `lab_informe.py` y `dos_llamadas.py`.
3. Los cinco defectos, en el código, uno por sesión, cada uno con su xfail que pasa a verde.
4. Las clases `falta:`: recomendar entre lo mostrado es la que más vende y la primera candidata a herramienta.
5. El motor de interpretación, opcional: la primera llamada de `primera_llamada.py` ya está medida; las frases de la
   plantilla le sirven de ejemplos para separar las uniones.
6. Lo fijo del llenado que es de una tienda de tecnología pasa a la configuración de la tienda —los equipos, los campos
   que describen, los medios, las localidades, la variante de talle— y se prueba con una segunda tienda.
