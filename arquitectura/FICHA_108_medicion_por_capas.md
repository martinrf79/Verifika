# FICHA 108 — LA MEDICION POR CAPAS (25-nov-2026, orden de Martin)

Esta ficha es el formato de trabajo desde hoy. Se lee entera antes de proponer o medir. No reemplaza al plan de la 107:
ordena como se mide todo lo que viene.

## 1. Por que

Se midio mucho y suelto: cada prueba en su ficha, sin saber que capa falla ni cual va al bot. Un error de una capa tapa
el de otra, y una prueba mal armada cambia el numero sin cambiar el bot. El 25-nov se vio dos veces: la seleccion entre
los 15 parecia el problema y la busqueda ya ponia primero un aceptable en 69 de 70 frases limpias; y un numero de 68 de
78 estaba inflado porque el orden se hizo con la respuesta del examen.

## 2. La regla

1. **Cada capa se mide sola, con la entrada perfecta**: lo que recibe sale de las etiquetas del examen, no de lo que
   devolvio la capa anterior. Si falla, la falla es de esa capa.
2. **La cadena entera se mide aparte**, de punta a punta, con lo que devuelve cada capa. La distancia entre la cadena y
   las capas dice cuanto se pierde al encadenar.
3. **Un comando, una tabla**: una fila por capa con aciertos, errores y repreguntas sobre las mismas frases, y una fila
   con la cadena. Cada sesion trabaja una capa, mira su fila y no toca las demas.
4. **Antes de creer un numero**, cada falla se clasifica contra lo grabado: la capa, la etiqueta, o la prueba. Una falla
   de la prueba no es un resultado.
5. **Toda propuesta dice que capa toca** y se revisa en esta ficha si ya se probo.

## 3. Los dos procesos y los dos datos

- **Traducir** es entender lo que quiere el cliente, en sus terminos. **Enlazar** es llevar eso a la tienda. No se
  mezclan: Luna no corrige nombres ni elige productos; el enlace no reinterpreta al cliente.
- Para redactar, el codigo necesita **dos datos por pedido**:
  - **dato 1**: de que se trata: un producto con sus condiciones, un tema de la FAQ o un destino;
  - **dato 2**: que quiere el cliente de eso: el precio, un campo de la ficha, la compatibilidad, comprarlo, que se le
    explique una politica, cuanto sale el envio.
  Con solo el dato 1, el codigo sabe de que se habla pero no que contestar.

## 4. Las capas

| Capa | La pregunta | Entrada perfecta | Donde vive hoy | Lo medido | Falta |
| --- | --- | --- | --- | --- | --- |
| 0. Separar | Una fila por pedido, sin juntar ni partir de mas, y cada palabra en su pedido | el mensaje | llamada 0, Luna | 39 de 51 lineas de varios pedidos, 25-nov | etiquetar los tramos, seccion 5 |
| 1. Producto | Con la fila correcta, el producto correcto primero o entre los 15 | el tramo del pedido | embeddings, nexo de rubro y producto | primero aceptable en 59 de 69 limpias sin orden; varios pedidos, 24 de 31 primero, 28 entre 15 | medir con el tramo etiquetado |
| 2. Existe | Si lo pedido esta en la tienda, no esta o es ambiguo | marca, modelo y rubro etiquetados | nexo de nombrado, `no_vendidas.json` | 9 de los 10 errores de la capa 1 son algo que la tienda no tiene; la lista caza 2 | la regla de identidad: exists, ambiguous, not_found |
| 3. Condicion y orden | Filtra y ordena bien sobre los candidatos | los candidatos y las condiciones etiquetadas | nexo de condicion, `conceptos.json` | con la traduccion perfecta, 77 de 78, `chico/reparto.py` | el orden sobre lo que cumple, sin usar la respuesta |
| 4. Tema | Pregunta de envio, pago, garantia o politica, al tema correcto de la FAQ | el tramo del pedido | nexo de tema | FICHAS 96 a 99 | etiqueta de tema por pedido |
| 5. Destino | La zona y el costo de envio correctos | el tramo con el lugar | nexo de destino | FICHAS 96 a 99 | etiqueta de destino por pedido |
| 6. Dato 2 | Que campo o que accion pide, y si la ficha tiene el dato | el producto o el tema correcto y el tramo | sin capa propia | sin medir | etiqueta de dato 2 por pedido |
| 7. Redactar | El texto dice lo que dice la ficha y contesta el dato 2 | dato 1 y dato 2 correctos | segunda llamada, ejecutor, verificador | el verificador caza el 99,3% de las alucinaciones inyectadas | medirlo con datos perfectos |
| 8. Memoria | Lo anterior, por charla, sin perder lo dicho | la charla | `memoria_agente` | 80 de 113 turnos bien en 42 charlas reales, 3-nov | se mide al final, por charla |

Lo que vale para el cliente es la charla: con un 70% por turno, una charla de cuatro mensajes sale entera bien una vez de
cada cuatro. La meta por capa se fija con eso en mente.

## 5. El etiquetado de la separacion: la base de que el codigo pueda contestar

Si un pedazo del mensaje cae en el pedido equivocado, o en ninguno, el codigo no tiene con que contestar aunque todo lo
demas ande. Por eso la separacion se etiqueta por tramos, no solo por palabras clave.

### Que es un pedido

Una cosa que el cliente pide o pregunta, con su dato 1 y su dato 2. "Dos teclados y un mouse, los mas baratos, con envio
a Cordoba" son dos pedidos de producto, el teclado y el mouse, y el envio es un dato que se aplica a los dos.

### Las reglas de los tramos

1. **Cada palabra del mensaje va a un solo lugar**: a un pedido, a lo global o al relleno.
2. **Lo global** es lo que vale para varios pedidos: el destino, la forma de pago, "todo inalambrico", un tope de plata
   del total. Se etiqueta una vez y se dice a que pedidos se aplica. Es la misma regla que ya sigue Luna: copiarlo en cada
   fila a la que se aplica.
3. **El relleno** es lo que no pide ni pregunta: saludos, contexto, quejas sin pedido.
4. **Un tramo es texto literal del mensaje**, sin corregir. Un pedido puede tener varios tramos si el cliente lo dice en
   partes.

### Que lleva cada pedido

- los tramos;
- el dato 1: los casilleros de hoy, rubro, marca, modelo, atributo, numero, orden, o el tema de la FAQ, o el destino;
- el dato 2: de una lista cerrada que se arma por codigo desde la fuente: los campos preguntables de cada rubro,
  `specs_preguntables.json`; precio, stock, compatibilidad, comprar; los temas de la FAQ; el costo y el plazo de envio;
- lo esperado, como hoy: ofrecer, no hay, repreguntar, sin dato, no compatible, rechazar.

### El proceso

1. **Propone Claude**, frase por frase, aplicando las reglas, en el formato de `banco_pruebas/flujo/examen/etiquetas.py`
   con los campos nuevos: tramos, global y dato 2.
2. **Controla el codigo**, sin modelo: que cada tramo este literal en el mensaje, que toda palabra caiga en un solo lugar,
   y que cada id exista en la fuente o en su lista.
3. **Revisa Martin** las frases dudosas y una muestra al azar. Lo que corrige vale para la clase entera y se anota como
   regla en esta seccion.
4. **Se congela con hash**, como el examen de hoy. Una etiqueta no se cambia despues de ver un resultado; si esta mal, se
   corrige en su propio commit, diciendo por que.

Las frases: las del examen fijo, y las charlas reales de WhatsApp para la capa de memoria.

## 6. El orden de trabajo

1. Etiquetar con el proceso de la seccion 5.
2. El comando de la tabla por capas, con lo ya grabado, sin gasto.
3. Una capa por sesion, empezando por la de mas errores en la tabla.

## 7. Lo que ya no se repite

- Modelos mas grandes para traducir: FICHAS 100 y 102.
- El modelo chico tal como viene para decidir si una condicion se cumple: mide parecido de tema, no separa opuestos,
  7,6% de cumple falsos, `chico/condicion.py`. Sirve para decir "no tengo ese dato".
- Luna eligiendo entre los 15: la busqueda ya pone primero lo correcto; pedirle que elija agrega errores y repreguntas.
- Lo que el 25-nov dejo en el banco: `chico/reparto.py`, `examen/luna_conceptos.py`, `examen/traduccion.py`, `lab/`.
