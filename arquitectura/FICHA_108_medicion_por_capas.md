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
| 0. Separar | Una fila por pedido, sin juntar ni partir de mas, y lo pedido copiado aparte | el mensaje | llamada 0, Luna; en el banco, `examen/luna_producto.py` | copia literal de lo pedido en 122 de 125 filas, 3,7 s de mediana, 25-nov | medir los tramos contra `examen/tramos.py` |
| 1. Producto | Con lo pedido, el producto correcto primero | el tramo del pedido | embeddings, nexo de rubro y producto | con el tramo etiquetado, 135 de 138 sin orden; con lo que copia Luna, 56 de 58 | nada: anda |
| 2. Existe | Si lo pedido esta en la tienda | el tramo del pedido | en el banco, `lab/existe.py` | con lo que copia Luna, 0 falsas alarmas; de los no hay, solo "un cable" se le escapa | lo que no nombra nada de la tienda, que hoy queda dudoso |
| 3. Condicion y orden | Filtra y ordena bien sobre los candidatos | los candidatos y las condiciones etiquetadas | nexo de condicion, `conceptos.json` | con la traduccion perfecta, 77 de 78, `chico/reparto.py` | el orden sobre lo que cumple, sin usar la respuesta |
| 4. Tema | Pregunta de envio, pago, garantia o politica, al tema correcto de la FAQ | el tramo del pedido | nexo de tema | FICHAS 96 a 99 | etiqueta de tema por pedido |
| 5. Destino | La zona y el costo de envio correctos | el tramo con el lugar | nexo de destino | FICHAS 96 a 99 | etiqueta de destino por pedido |
| 6. Dato 2 | Que campo o que accion pide, y si la ficha tiene el dato | el tramo y lo global de dato 2 | en el banco, `lab/capas.py` | opcion exacta en 130 de 185; agrupado en lo base contra lo especifico, 173 de 190 | la decision de agrupar, seccion 8 |
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

1. Hecho el 25-nov: el etiquetado por tramos, `banco_pruebas/flujo/examen/tramos.py`, y las capas 0, 1, 2 y 6 medidas.
2. Sigue: la capa de condicion y orden, lo que nada cumple, el teclado azul o "menos de 200 mil", y "el mas barato" sobre
   lo que cumple, con lo que copia Luna.
3. Despues: el comando de la tabla por capas, que junte las medidas de `lab/` en una sola salida.
4. Despues: la cadena entera, por charla, y recien ahi la propuesta de llevar el circuito al bot.

## 7. Lo que ya no se repite

- Modelos mas grandes para traducir: FICHAS 100 y 102.
- El modelo chico tal como viene para decidir si una condicion se cumple: mide parecido de tema, no separa opuestos,
  7,6% de cumple falsos, `chico/condicion.py`. Sirve para decir "no tengo ese dato".
- Luna eligiendo entre los 15: la busqueda ya pone primero lo correcto; pedirle que elija agrega errores y repreguntas.
- Lo que el 25-nov dejo en el banco: `chico/reparto.py`, `examen/luna_conceptos.py`, `examen/traduccion.py`, `lab/`.

## 8. Lo medido el 25-nov: el circuito del dato 1

**El criterio de Martin para cada paso:** la mitad es que venda y la mitad es que no alucine. Cada numero se lee contando
aparte lo que pierde una venta y lo que le dice al cliente algo falso.

**El circuito que quedo medido**, todo en el banco, nada en `app/`:
1. Luna separa como hoy, el v14f1b, y en cada fila copia aparte, tal cual, las palabras con que el cliente nombra lo que
   pide: `lo_pedido`. Copiar, no traducir. Es lo unico que se le sumo, y no agrega tiempo. `examen/luna_producto.py`.
2. Con `lo_pedido`, una busqueda de embeddings trae el producto: el primero sirve en 56 de 58 frases de un pedido.
3. Una funcion de codigo dice si existe, `lab/existe.py`: lo que sigue a "para" es el uso; lo de `no_vendidas.json` sin
   un rubro de la tienda, no hay; un codigo de modelo que el catalogo no trae, con las cifras exactas, no hay; un nombre
   propio que la tienda no trae, no hay. Con lo que copia Luna no dijo nunca que no hay algo que hay.

**Lo que se aprendio, y no se repite:**
- La busqueda nunca fue el problema: con el pedido bien separado, el primero sirve casi siempre. Pedirle a Luna que elija
  entre los 15 agregaba errores.
- La regla de los nombres propios solo sirve con lo pedido aislado: con la fila entera de Luna toma "Concordia" o
  "Esteban" como marcas, 27 falsas alarmas.
- El documento de cada producto en el indice lleva los alias del rubro, que afirman lo que muchos productos no tienen,
  "teclado inalambrico" en uno con cable. Un documento fiel a la ficha, `lab/busqueda.py`, ordena un poco mejor pero no
  cambia el primero: llevarlo al bot no es urgente.
- El puntaje de la busqueda no separa lo que hay de lo que no hay.
- Un numero que use la respuesta del examen no vale: el 68 de 78 del laboratorio estaba inflado por ordenar sobre los
  aceptables.

**La decision pendiente de Martin, dato 2:** agruparlo en lo base, que se contesta mostrando el producto con precio y
stock, contra lo especifico, un campo de la ficha, compatibilidad, comparar o caracteristicas. Asi no hace falta
distinguir "quiero" de "cuanto sale", que es donde falla.

**Los guiones del 25-nov**, todos en `banco_pruebas/flujo/`: `examen/tramos.py`, las etiquetas; `lab/busqueda.py`, los
documentos del indice; `lab/capas.py`, producto, existe y dato 2 con la entrada perfecta; `lab/existe.py`, la funcion;
`examen/luna_producto.py`, Luna con `lo_pedido`. Los planes y los resultados, en orden, en `lab/plan.md`. Los vectores
quedan fuera de git, en `lab/vectores.json.gz`: se vuelven a pedir con la clave gratis, o con la paga y la marca de
Martin si la gratis se agota.
