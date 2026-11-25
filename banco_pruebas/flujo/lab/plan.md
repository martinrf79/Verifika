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
