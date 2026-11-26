# EL LABORATORIO DE LA BUSQUEDA, DATO 1 (25-nov-2026, orden de Martin)

Que se mide: solo la busqueda por embeddings, el paso que trae los 15 candidatos. No se mide elegir ni redactar.

## Lo visto antes de medir

- El documento de cada producto en el indice, `app/core/flujo/nuevo/rubro.doc_producto`, es: los alias del rubro, marca y
  modelo, y los tags. Los alias son los mismos para todos los productos del rubro y ocupan cerca de la mitad del texto.
- Los alias afirman caracteristicas que muchos productos no tienen: todos los teclados dicen "teclado inalambrico",
  "teclado mecanico" y "teclado con luces", y todos los auriculares dicen "bluetooth". Contado contra los conceptos de la
  ficha, sin contar "notebook" como plataforma: casi 100 afirmaciones falsas en los documentos.
- El documento no trae los datos tecnicos de la ficha: conexion, tipo de teclado, luces, panel, bateria.
- La consulta, en la llamada unica, es el mensaje crudo y sus trozos cortados por puntuacion, no las filas que separa Luna.

## Hipotesis

Si el documento de cada producto dice lo que la ficha dice, y nada que no diga, los aceptables suben en la lista y los
que no cumplen bajan: elegir entre los 15 se vuelve mas facil.

## Variantes, una cosa por vez

- Documento A: el de hoy, con los vectores que ya tiene el indice.
- Documento B: armado por codigo desde `fuente.VISTA`: rubro, nombre, marca y modelo, lo extra, y los campos tecnicos con
  su nombre, conexion, tipo de teclado, luces, panel, resolucion, bateria, microfono, plataformas, uso, colores. Sin los
  alias del rubro.
- Consulta 1: el mensaje crudo y sus trozos, como la llamada unica.
- Consulta 2: el texto de cada fila que separo Luna, de `luna_conceptos.jsonl`.

## Metrica

Frases de un pedido sin dudosas cuyo pedido tiene aceptables. Para cada combinacion: en cuantas el primer candidato es
aceptable, en cuantas hay uno entre los 3 primeros, entre los 15, y cuantos aceptables hay en los 5 primeros. Mismo
modelo de embeddings que el bot, gemini-embedding-001, con la clave gratis; los vectores quedan guardados en `lab/` para
no pedirlos dos veces.

## Resultado, 25-nov

Los vectores quedan en `lab/vectores.json.gz`, fuera de git por el peso: se vuelven a pedir con la clave gratis.

- La busqueda no es el problema. En las 70 frases limpias con aceptables, el primero de la busqueda es aceptable en 69
  con el documento de hoy y el mensaje crudo. Con las filas de Luna, 67.
- En las 17 donde la condicion deja afuera parte del rubro, el primero es aceptable en las 17; de los 5 primeros, 68 de
  74 posibles son aceptables con el documento de hoy y 72 con el documento B. Al azar dentro del rubro serian 27.
- El documento B, fiel a la ficha, ordena un poco mejor y no afirma lo que el producto no tiene, pero no cambia el primero.
- Ofrecer solo el primero de la busqueda, sin ningun modelo eligiendo, y el orden por codigo con lo etiquetado: 68 de 78
  limpias aciertan y 10 yerran. La llamada unica daba 55 aciertos y 6 errores con 17 repreguntas.
- De los 10 errores, 9 piden algo que la tienda no tiene: un modelo o una marca que no trae, RTX 5070, iPad, Zyltech; un
  rubro que no vende, celulares, cable, PlayStation, alquiler; una condicion que nada cumple, teclado azul, tactil. La
  busqueda siempre trae algo. `no_vendidas.json` caza 2 de los 9 y marca 2 de mas. El otro error: "cueus" deja la Coeus
  segunda.
- Ojo: el orden sale de las etiquetas; Luna lo traduce bien en 8 de 9. Es un examen de frases sueltas, no de charlas.

## Plan 2, varios pedidos, escrito antes de correr

Frases de varios pedidos que Luna ya separo en `luna_conceptos.jsonl`. Cada fila de producto de Luna es una consulta.
Por pedido etiquetado con aceptables: si alguna fila de Luna trae un aceptable primero, entre los 3 o entre los 15. Por
fila de Luna: si su primero no es aceptable para ningun pedido, es una oferta equivocada. Los pedidos con orden y los que
esperan no hay van aparte. Correccion de la medicion de un pedido: el orden se habia aplicado sobre los aceptables del
examen, que es la respuesta; se informa aparte sin eso.

## Resultado 2, 25-nov

- Correccion de un pedido, sin usar la respuesta para el orden: de las 69 frases sin orden, ofrecer el primero de la
  busqueda acierta 59 y yerra 10, los 9 de algo que la tienda no tiene y la Coeus. Las 9 con orden quedan sin medir bien:
  hace falta ordenar sobre lo que cumple, y eso pide el filtro real, no las etiquetas.
- Varios pedidos, 18 frases, 51 filas de producto de Luna. De 31 pedidos sin orden, un aceptable queda primero en 24,
  entre los 3 en 25 y entre los 15 en 28. Los 3 sin candidato son de una frase, "proce, ram, gpu": jerga en una fila.
- 5 filas de Luna traen primero algo que no sirve a ningun pedido: 2 son preguntas que Luna marca como producto, "a
  cuanto me queda", "o explota la bateria"; 1 pide memoria DDR3 que la tienda no tiene; 1 "una compu para jugar"; 1 junta
  varios articulos en una fila.

## Plan 3, las capas con la entrada perfecta, escrito antes de correr

Entrada perfecta de cada pedido: sus tramos de `examen/tramos.py` mas lo global de tipo condicion que se le aplica.
Sin modelo; embeddings con la clave gratis. Criterio de Martin para leer cada numero: la mitad es vender, la mitad es no
alucinar. Por eso cada medida cuenta aparte lo que pierde una venta y lo que le dice al cliente algo falso.

Medida 1, capa producto. Por pedido con aceptables y sin orden: el primero de la busqueda es aceptable, y aceptables en
los 5 primeros. Documento A y documento B. Los pedidos con orden, aparte.

Medida 2, capa existe. Tres formas, todas por codigo:
- E1, el indice de rubros, que ya tiene los documentos de lo que no se vende: si el primero es uno de esos, no hay.
- E2, los codigos de modelo: una palabra con letras y numeros, o un numero de tres o mas cifras que no es plata ni lleva
  unidad, que no aparece en ningun nombre, modelo, tag ni alias de la tienda: no hay.
- E3, E1 o E2.
Se cuenta: no hay bien detectado; no hay perdido, que es ofrecer algo que no es, alucinar; y falsa alarma, decir que no
hay algo que hay, perder la venta.

Medida 3, capa dato 2. Cada opcion de la lista cerrada tiene un documento: los genericos, ofrecer, precio, stock, comprar,
caracteristicas, comparar y compat, con una frase escrita hoy antes de medir y que no se toca despues; cada campo, con su
etiqueta y sus claves de `specs_preguntables.json`, que es la fuente. La consulta: los tramos de dato 2 que se aplican al
pedido, o su tramo si no tiene. Se cuenta si la primera opcion esta entre las etiquetadas, y aparte los campos de la ficha,
que son los que llevan a un dato que puede faltar.

## Resultado 3, 25-nov

Etiquetado: `examen/tramos.py`, 138 frases y 193 pedidos con tramos, dato 2 y lo global; el control por codigo da 0
problemas. Los embeddings que faltaban se terminaron con la paga, con el ok de Martin en la sesion: menos de un centavo.

- Medida 1, producto: con el tramo bien separado, el primero sirve en 135 de 138 pedidos sin orden y en 42 de 43 con
  orden. Documento A y B dan lo mismo. Con buena separacion, esta capa anda.
- Medida 2, existe, de 12 pedidos que esperan no hay y 181 que hay:
  E1, indice de rubros: 4 bien, 8 perdidos, 7 falsas alarmas. E2, codigos ajenos: 3 bien, 9 perdidos, 0 falsas alarmas.
  E3, una u otra: 7 bien, 5 perdidos, 7 falsas alarmas. El puntaje del primero no separa: los no hay van de 0,63 a 0,76
  y los que hay arrancan en 0,60. De los 12, dos son condiciones que nada cumple, teclado azul y silla de menos de 200
  mil: son de la capa de condicion, no de esta.
- Medida 3, dato 2: la opcion exacta sale primera en 130 de 185 genericos y en 5 de 5 campos. Casi todas las fallas
  confunden ofrecer, comprar, precio y stock, con un verbo solo, "quiero", "necesito". Agrupado en lo base, que se
  contesta mostrando el producto con precio y stock, contra lo especifico, un campo, compatibilidad, comparar o
  caracteristicas: 173 de 190 bien agrupados; 15 base tomados como especificos y 2 al reves; de 15 especificos, 10 con la
  opcion exacta.

## Plan 4, la funcion que dice que hay y que no hay, escrito antes de correr

Orden de Martin, 25-nov: una funcion de codigo que verifique lo que hay de lo que no hay. `lab/existe.py`.

Entrada: el tramo del producto, el de `examen/tramos.py`. Salida: hay, no hay, o dudoso. Dudoso sigue como hay: la busqueda
ofrece y el resto de las capas controla; no se le dice al cliente que no hay sin una razon de la fuente.

Reglas, todas armadas desde la fuente, ninguna por caso:
1. Lo que sigue a "para" o "pa" describe el uso, no lo que se pide, y no cuenta: "un cable para el monitor" pide un cable.
2. El vocabulario de la tienda: rubros, alias, marcas, modelos, nombres, tags y valores de la ficha.
3. Si el tramo nombra algo de `no_vendidas.json` y ningun rubro de la tienda, no hay.
4. Un codigo de modelo, letras con numeros o un numero de tres o cuatro cifras sin unidad, que no esta en el vocabulario ni
   se le parece, no hay: es un modelo que la tienda no trae.
5. Un nombre propio, una palabra con mayuscula que no abre la frase, que no esta en el vocabulario ni se le parece, no hay:
   es una marca o un modelo que la tienda no trae.
"Se parece" es una diferencia de una o dos letras, la de un error de tipeo, no un umbral para un caso.

Se mide igual que E1 a E3: no hay bien, no hay perdido, que alucina, y falsa alarma, que pierde la venta. Las condiciones
que nada cumple, teclado azul y silla de menos de 200 mil, se cuentan aparte: son de la capa de condicion.

## Resultado 4, 25-nov

`lab/existe.py`, sin modelo y sin embeddings, en medio segundo para todos los pedidos.

- Con el tramo del producto aislado, el de las etiquetas: de 10 pedidos que esperan no hay, 7 bien y 3 perdidos; de 181
  que hay, 0 falsas alarmas. Los 3 perdidos: "un cable de 5 metros", que no nombra nada de la tienda y queda dudoso;
  "teclado azul", que es una condicion que nada cumple, capa de condicion; "alquilan notebooks", que es un servicio, dato 2.
- Con las filas enteras de Luna, que traen tambien destinos, nombres de personas y otras frases: la regla de los nombres
  propios da 27 falsas alarmas en 131 filas, "Concordia", "Esteban", "Envio". Sin esa regla: 4 bien, 5 perdidos y 0
  falsas alarmas; la unica que el conteo marca, DDR3, esta bien, porque esa linea de la frase espera no hay.
- Dudoso, sin rubro, marca ni modelo de la tienda: 57 veces cuando hay y 2 cuando no hay. Sigue como hay.
- Lo que se aprende: la funcion verifica sin perder ventas; cuanto caza depende de recibir aislado lo que se pide. Eso es
  la capa 0, separar.
- Dos fallas del guion, corregidas antes de contar: la unidad suelta, "2 TB", leida como nombre, y una cifra distinta
  tomada como error de tipeo, 5070 por 4070.

## Plan 5, Luna copia aparte lo pedido, escrito antes de correr

Orden de Martin, 25-nov. Capa 0. Guion: `examen/luna_producto.py`. Prompt: el v14f1b de hoy, igual, mas un parrafo: en
cada fila, `lo_pedido` copia tal cual, sin corregir ni agregar, las palabras con que el cliente nombra lo que pide, con
sus caracteristicas; sin destino, pago, nombres de personas ni preguntas de envio; vacio si la fila no pide un producto.
Misma corrida "luna" de siempre, las mismas 97 frases. Tope, 10 centavos.

Se mide:
1. Que `lo_pedido` sea literal en el mensaje: si no, Luna corrigio o agrego, y es una falla de copia.
2. La capa existe con `lo_pedido` aislado, contra lo medido con la fila entera: 4 bien, 5 perdidos, 0 falsas alarmas.
3. La capa producto con `lo_pedido` como consulta: el primero sirve.
4. La latencia de Luna, contra 4,1 segundos de mediana.

## Resultado 5, 25-nov

Luna con el v14f1b y el parrafo de `lo_pedido`, las 97 frases, 2,8 centavos. Los embeddings de las consultas, con la paga
autorizada en la sesion, porque la gratis del dia estaba agotada.

- Copia: de 125 filas con producto, 122 literales. Las otras 3 juntan dos partes sin coma, "dos teclados los mas
  economicos no importa el color": lo pedido esta bien, solo cambia la union.
- Capa existe con `lo_pedido`: 5 no hay bien y 3 perdidos; 116 hay bien y 1 falsa alarma, que no lo es: es la memoria
  DDR3 de una frase de tres pedidos, y esa linea espera no hay. Queda igual que con el tramo perfecto: de los perdidos,
  solo "un cable de 5 metros" es de esta capa; el teclado azul es condicion y alquilar notebooks es dato 2.
- Capa producto con `lo_pedido` como consulta: el primero sirve en 56 de 58 frases de un pedido sin orden. Las 2 que no
  son mensajes de prueba de estres, donde Luna tomo como pedido "una pc" y "esos routers calentadores".
- Latencia de Luna: mediana 3,7 segundos, p90 5,6; no suma tiempo contra los 4,1 de hoy.

## Plan 6, la condicion sobre la rueda, escrito antes de correr

FICHA 109, 26-nov. Capa 3, condicion y orden. Todo en el banco, sin modelo, sin tocar el prompt de Luna. Guion nuevo:
`primeros/condicion.py`, que usa `conceptos.py`, `numeros.py`, `fuente.py` y `compat.py` tal cual.

**Decision de Martin, 26-nov:** la lista `INTERROGA` de `cadena.py` la decide la sesion, porque no cambia vender ni
alucinar por si sola: si una caracteristica se lee como pregunta en vez de condicion, el producto se ofrece igual y el
dato se contesta de la ficha. Se mide su efecto en los numeros; si un cambio a la lista mueve ventas u ofertas
equivocadas, se anota.

### La capa, por pedido

Entrada: el rubro y las condiciones `(palabras, caracteristica)` de `cadena.dato2()`. Salida: los productos que cumplen,
ordenados, y el veredicto: ofrecer, no hay con lo mas cercano, repreguntar o sin dato.

1. Atar cada condicion por codigo. La caracteristica dice el campo y las palabras el valor:
   - con nombre, a un concepto de `conceptos.json` del tipo atributo, color, plataforma u origen;
   - con numero, `numeros.leer`: tope de plata, capacidad, ram, pulgadas, hz, potencia;
   - marca y modelo, contra el catalogo;
   - la negacion, "que no sea", "sin", "nada de", saca en vez de exigir;
   - el orden, a un concepto de tipo orden.
2. Filtrar la vista de la fuente con lo atado, con la misma regla que `examen.aceptables`.
3. Si nada cumple: no hay, y lo mas cercano, el que cumple todo menos una condicion, dicho como alternativa.
4. El orden corre sobre todo lo que cumple en el rubro; los embeddings solo desempatan cuando no hay orden.
5. Lo que no se ata no filtra y queda como sin dato de esa condicion.
6. De la rueda: la fila sin producto que solo trae condicion u orden se pega al pedido anterior, o a todos si es global;
   sin rubro y con orden, el orden corre sobre toda la tienda; ante una correccion del cliente vale lo ultimo.

### Como se mide, en este orden

1. Guion revisado a mano con diez casos contra lo grabado antes de contar.
2. Techo, con entrada perfecta: los `cas` de la etiqueta contra la capa, en el examen y las muestras.
3. Con la entrada de la rueda: las condiciones de `dato2()`. La distancia al techo es lo que se pierde al atar.
4. De punta a punta: `cadena.py` con la capa puesta, el primero con el orden aplicado, `examen._orden_ok`.
5. En los cuatro conjuntos, contado aparte: venta perdida, oferta equivocada, no hay cuando nada cumple, sin dato.
   Lo que importa primero es que las ofertas equivocadas bajen de 16 en 135 en las muestras y de 17 en 194 en el examen,
   sin perder ventas contra la linea de base de la FICHA 109, seccion 4.
6. Cada falla clasificada: capa, etiqueta o prueba. Si atar un caso pide sumar una palabra a una lista de conceptos,
   se anota y se consulta con Martin antes de sumarla.
