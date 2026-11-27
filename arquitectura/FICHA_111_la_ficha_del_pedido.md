# FICHA 111 — LA FICHA DEL PEDIDO: QUE NINGUN DATO SE PIERDA ENTRE CAPAS (27-nov-2026)

Se lee antes de proponer cualquier capa nueva. Viene de la FICHA 110. Los numeros, el plan y el resultado de cada paso,
en los Planes y Resultados 7 y 8 de `banco_pruebas/flujo/lab/plan.md`.

## 1. La idea

Martin, 27-nov: un dato que el mensaje ya trae, y que Luna ya tradujo, no puede perderse al pasar de una capa a otra.
La informacion del mensaje corre por todo el flujo, aunque sea con datos de mas.

Por eso el mensaje vive en una ficha, una tabla:
- **un tramo por cada pedazo** que escribio Luna, con la fila, las palabras literales, lo que Luna le puso, a que pedido
  va y los usos;
- **ninguna funcion saca un tramo**: cada una le anota un uso, rubro, nombre, condicion, pregunta, sin dato, no
  reconocido o relleno;
- **al final, cada tramo tiene un uso**, y si ninguna funcion lo tomo, queda dicho: "no tengo ese dato" o "no lo
  reconozco". Nunca desaparece en silencio.

La ficha no resuelve nada: es el recipiente. Si la condicion, existe o Luna mejoran, cambia lo que anotan, no la ficha.

## 2. Dos cosas que no se mezclan

- **Perderse en el camino:** el dato estaba y en la capa siguiente no esta. Es culpa del transporte, y la ficha lo lleva
  a cero.
- **Quedar sin resolver:** el dato esta en la ficha, con su uso, pero la funcion que le toca no sabe que hacer. Es culpa
  de esa funcion, y tiene nombre y responsable.

Hasta el 27-nov se contaba lo que cada capa resolvia bien, nunca lo que tiraba: las perdidas eran invisibles.

## 3. Lo medido, sin modelo y sin gasto, con lo que Luna separo grabado

Con la entrada de las etiquetas, `primeros/perdidas.py`:

| | examen, 472 datos que Luna tenia | reales, 109 |
| --- | --- | --- |
| la cadena del banco, sin ficha | 62 se pierden | 9 |
| con la ficha, `primeros/ficha.py` | 0 se pierden en el camino; 37 quedan sin resolver | 0; 6 sin resolver |

Control: cada palabra que escribio Luna esta en algun tramo; quedan afuera 4 "y" de 2.809. Luna pierde 28 datos del
examen y 5 de las reales: eso es traduccion, aparte.

Los 37 sin resolver del examen, por responsable:
- existe, 4: lo que la tienda no vende, celulares, Play 5, cable de 5 metros, dicho adentro de una pregunta de stock, o
  que existe da como dudoso y dudoso se trata como hay;
- la segunda etapa de la condicion, 7: "en oferta", "titilan al ritmo de la musica", "origen Estados Unidos";
- la condicion, 10: lo vago o de uso, "para escribir mucho", "la mayor ram posible";
- el rubro sin marcar, 8: "compu", "memoria", "aparato cuadrado con teclas";
- el dato 2 dicho en otra fila, 6; el destino sin marcar que entra como nombre, "a Cordoba".

## 4. La metodologia para cada funcion que resuelve

Entra la ficha, sale un veredicto por tramo. Se mide contra las etiquetas y siempre de los dos lados: lo que resuelve
bien y lo que rompe, por ejemplo los "no lo vendemos" que caza y las falsas alarmas sobre lo que si hay, que son ventas
perdidas. El que escribe la medicion revisa a mano los casos contra lo grabado antes de dar el numero: el 27-nov el guion
tuvo dos errores que inflaban las perdidas de 62 a 91.

## 5. Lo que sigue

1. Resolver los 37 por responsable, empezando por existe: lee todos los tramos del pedido, y un dudoso sin rubro no se
   ofrece. Medido de los dos lados con `lab/existe.py`.
2. Martin, 27-nov: antes, la base de jerga, para que la traduccion temprana lleve cada palabra del cliente a un concepto
   de la tienda y de ahi a la ficha tecnica y la descripcion. Resuelve el rubro sin marcar y parte de la condicion.
3. Despues, el papel de cada tramo lo pone Luna, Plan 7 paso 2, y la ficha pasa a ser la memoria de la charla.

## 6. La base de jerga, para el chat que sigue

Martin, 27-nov, trajo la propuesta de otra guia: una base de jerga en tres capas, general, de nicho y por registro, con
la frase del cliente, la normalizada, la intencion y las entidades; 1.500 a 3.000 ejemplos, 20% reales y 80% sinteticos
hechos con un modelo grande; y un modelo chico de 1 a 4 mil millones de parametros ajustado con QLoRA, cuantizado y
corriendo en CPU. O, antes de entrenar, la misma base como diccionario mas embeddings.

Lo que se toma y lo que no, con lo medido en el repo:
- **Si:** la base como tabla, jerga a concepto de la tienda, y cada concepto apuntando a su campo de la ficha tecnica o a
  la descripcion. Es lo que falta para el rubro sin marcar y para juntar el dato 2. Empieza de lo que ya hay:
  `alias.json`, `conceptos/conceptos.json` y la jerga de la FICHA 106.
- **Si, primero la alternativa hibrida:** busqueda exacta y por tipeo en la tabla, y embeddings solo de respaldo. El
  modelo chico, cuando haya trafico real para entrenarlo.
- **No la frase normalizada como salida:** reescribir pierde el matiz, investigacion del 26-nov. Se guarda la palabra
  literal al lado del concepto.
- **Lo sintetico sirve para entrenar, no para medir:** en este repo los numeros sobre frases escritas por nosotros
  siempre salieron mejores que con reales, FICHA 91 y FICHA 110. Se mide sobre el pozo de mensajes reales.
- **No se juntan preguntas de Mercado Libre ni chats de otras tiendas** sin revisar sus condiciones de uso; el pozo
  propio alcanza para empezar.
- **El modelo chico en CPU no contesta en milisegundos** cuando tiene que escribir un JSON: se mide antes de creerlo. El
  e5 chico ajustado del 24-nov mejoro el alias correcto primero de 26 a 39 en 89, FICHA 106, y no alcanzo para traducir.

## 7. Los comandos

    python3 banco_pruebas/flujo/primeros/perdidas.py [--examen|--reales] [--ficha] [--ver]
