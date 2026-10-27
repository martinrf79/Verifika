# FICHA 82 — Que el modelo tenga de donde elegir: los ejemplos que cubren la base y los parecidos

26-oct-2026, sesion con Martin. Sigue a la FICHA 81. La mide `banco_pruebas/candidatos82.py`, sin el modelo.

## La idea, de Martin

Si el modelo no marca una casilla es porque no tiene de donde sacar el criterio. El modelo parte la multipregunta y
traduce; el codigo y los embeddings le traen los candidatos precisos, y el modelo elige entre ellos. Primero se arregla
lo que recibe el modelo, medido sin el modelo; recien despues se prueba con el modelo.

## Lo hecho en la sesion

1. **El vocabulario de ordenes**, aprobado el 26-oct, en `marcador.RESPUESTAS` bajo "ordenes", que cada tienda cambia
   en su `alias.json`: "lo mejor", "gama alta", "la mejor calidad" son mas caro; "gama baja", mas barato. Solo si el
   modelo dejo el orden vacio. Sobre lo grabado, lo mejor para todo de 4 a 7 de 10; siete articulos sigue 9 de 10.
2. **La causa de las tres que quedan**: el alcance. El cliente pide un orden para todo el pedido y los 26 ejemplos fijos
   de la consigna no tienen ningun caso asi. El modelo no tenia de donde elegir.
3. **El medidor de candidatos**, `candidatos82.py`: por turno, si las formas que tiene que dar el modelo —hace y sobre
   de cada parte, el alcance del pedido entero y el orden— estan entre los ejemplos que recibe.
4. **La calibracion sin mirar el examen**, `--calibrar`: la plantilla contra si misma, cada frase buscando en las otras
   clases; y las 48 con las partes en que las corto Gemini, que es el flujo en dos pasos.
5. **Los fijos que cubren la base**, `--cubrir`: el codigo suma a los 26 curados, de a una, la clase de la plantilla que
   mas cubre, hasta que cada acto, alcance y orden este una vez. Quedan 35 clases.

## Lo medido

| lo que recibe el modelo                     | examen, 113 turnos | plantilla, 479 | las 48 por partes |
|---------------------------------------------|--------------------|----------------|-------------------|
| los 26 fijos de hoy                         | 86                 | —              | 30                |
| los 26 fijos mas 5 parecidos                | 98                 | 423            | 37 con 3          |
| los 35 que cubren la base, mas 5 parecidos  | 112                | 442            | 40                |
| el techo de la base                         | 112                | —              | —                 |

El examen son las 58 con su agenda a mano y las diez formas de lo mejor para todo; se miro una sola vez. Lo unico que
falta es "la mas potente", C54, un orden que no esta en la base.

Lo que dice: el arreglo grande es estructural y barato, que los fijos cubran todo lo que la base sabe resolver. Los
parecidos por embeddings suman poco despues de eso, 3 a 5 por parte, y sirven para mostrar el caso mas cercano.

Lo descartado: cambiar lo propio de la tienda por su tipo antes del embedding empeora, porque el parecido pierde lo que
distingue. Por mensaje entero rinde menos que por partes. Mas de 5 parecidos no paga sus tokens.

Que el ejemplo este es necesario, no suficiente: si el modelo lo elige lo dice la prueba con el modelo.

## Lo que sigue, en orden

1. **Llevarlo al camino vivo**: los 35 a `lectura_ejemplos.json` y los parecidos por parte a `lectura.mensajes`, sin
   pasar el techo de 4.500 tokens; con los 9 nuevos y 5 parecidos el peor turno daria unos 4.800, asi que 3 parecidos o
   ejemplos mas cortos.
2. **El orden por cualquier campo numerico del indice**, no solo precio y peso: "la mas potente" como clase.
3. **Unificar los rotulos** de la plantilla con los que da el modelo: una pregunta de pago como tema o como pago.
4. **La megafuente**, idea de Martin: clases de pedido neutras de tienda, frases curadas por clase desde fuentes
   abiertas y charlas reales, cada clase cruzada con el indice de cada tienda. Cada clase nueva entra si sube la
   cobertura sin subir el ruido.
5. Con eso, el modelo gratis con OpenRouter, y la corrida con Gemini contra el criterio de la FICHA 81, con el ok de
   Martin.

## La segunda vuelta, 26-oct a la tarde: la vara estricta y los fijos por parte entera

Martin pidio calibrar el motor de casos sin modelo antes de probar con el modelo.

1. **La vara vieja estaba llena y no mostraba nada**: con los 35 fijos daba 112 de 113 y no podia subir. Medía cada forma
   suelta: que hace, sobre que, alcance y orden. Se sumaron las casillas, `formas`, y la parte entera, `firmas`: que hace,
   sobre que, alcance y que casillas llena, junta, como la tiene que dar el modelo.
2. **Lo que dice lo grabado de Gemini**: casi todo lo que falla es el acto o el sobre, y depende de la libreta: "y en
   blanco?", "y ese cuanto?", "sumame el HyperX" con algo mostrado. Las casillas fallan menos, sobre todo condiciones.
3. **El estado de la charla en la busqueda**, `--motor`: si hay mostrado, borrador o pregunta abierta. Calibrado con la
   plantilla contra si misma suma de 6 a 9 frases con 3 parecidos, sin tokens. En el examen, con los fijos que cubren la
   base, los parecidos no suman nada.
4. **Los fijos desde cero, con presupuesto**, `--armar`: no se suman a los 26 curados, se eligen de toda la plantilla, de a
   uno, el que mas partes comunes suma por token. La libreta del ejemplo lleva cada producto mostrado con nombre, precio y
   stock, y solo los datos que nombran la frase o la salida; la salida va sin espacios.

| lo que recibe el modelo | la plantilla, 479 frases, parte entera | el examen, 105 turnos de las 58, parte entera | el peor turno |
|---|---|---|---|
| los 26 curados de hoy | 303 sin su clase | 52 | 4.332 tokens |
| los 33 de `--armar`, 2.100 tokens | 455 | 78 | 4.292 tokens |
| toda la base, 41 clases | 479 | 87 | unos 5.000, pasa el techo |

El examen se miro una vez. Pasar el techo de 4.500 para llegar a 87 es un umbral: lo decide Martin.

**Por que no esta en produccion**: la consigna cambia y `tests/test_variantes.py` pide correr las variantes con el modelo.
La clave gratis agoto la cuota del dia en la corrida de comparacion. Las respuestas que alcanzaron quedaron en
`respuestas_modelo.jsonl`: al repetir no se vuelven a pedir.

## La tercera vuelta, 26-oct a la noche: la mejor config sin modelo, y el modelo dijo que no

1. **Doce clases nuevas en la plantilla**, UN08 a UN19: las casillas de la base juntas como en una compra real. El techo
   del examen sube de 87 a 98 de 105.
2. **El ejemplo compacto**: sin la libreta si es el primer mensaje y sin el cliente de la parte que es el mensaje entero,
   de 68 a 52 tokens. Con 2.250 tokens entran 47 fijos: el examen sin modelo da 90 de 105 contra 52.
3. **Con Gemini y la paga, una corrida**, contra la grabada de la FICHA 81:

| | FICHA 81, 26 fijos | 47 fijos compactos |
|---|---|---|
| las 58, turnos con todos sus datos | 76 de 105 | 75 |
| las 48, turnos con todos sus datos | 28 de 48 | 25 |
| las 48, el pedido BIEN y MAL SIN AVISAR | 35 y 4 | 29 y 7 |
| las 58 sueltas, lo que lee el cliente | 70 de 74 | 71 |
| variantes: siete, mejor y vendido | 9, 7 y 5 | 8, 6 y 5 |

No entra: empeora las 48 mas que el ruido de unos cuatro turnos y baja de los pisos de variantes. En las 48 el modelo
pone mas destinos y acierta menos, 28 de 45 contra 32: los reparte mal; el acto baja de 92 a 83.

**Lo que se aprende**: que el ejemplo este a la vista no mejora al modelo; con mas ejemplos rinde peor. La vara sin modelo
mide una condicion necesaria y no predice el resultado. La corrida cambio tres cosas a la vez —cuantos ejemplos, el
formato compacto y las clases nuevas— y no aisla cual empeora. Los 47 quedan en `candidatos82_fijos.json`; la
consigna sigue con los 26.

## El cierre, 27-oct: lo que dijo lo grabado y el plan

**Lo grabado, turno por turno**, sin modelo: entre los 26 y los 47 ejemplos solo cambian 10 de 169 turnos. 54 fallan en
las dos: los ejemplos no mueven al modelo. Esas 54, por clase: cambiar lo pedido, unas 12; pedir comprar leido como ver
opciones, 9; elegir entre dos o lo ambiguo, 6; tope, pago o exclusion para todo, 5; el envio de un producto a un lugar,
4; politica con otro rotulo, 4; compatibilidad como pregunta tecnica, 3; "si" a una pregunta del bot, 2. Una regla que
pasa "ver con cantidad" a comprar arregla el acto en las 48 y lo rompe en las 58: no entro.

**Las entrevistas ya lo decian**: el modelo pide entidades resueltas por el codigo, el estado ordenado, unos cinco
ejemplos de borde y separar consulta de compra por el verbo; con varios destinos, uno por destino.

**Afuera**: no hay una skill que lo resuelva. La referencia de Anthropic, github.com/anthropics/commerce-agents, es un
agente con herramientas y candados en el codigo: el carrito solo acepta ids que devolvio una herramienta en la sesion.
En tau-bench, el banco de agentes de venta minorista, los mejores resuelven del 70 al 90 por ciento y repetir la misma
tarea baja mucho: ningun sistema llega a cien, los que andan hacen que lo que falla falle seguro.

**El agente de la FICHA 62, recalificado con la vara de hoy** sobre las 58 que comparte: 55, 54 y 55 de 58 contra 53, 52
y 53 del flujo de hoy. Su codigo ya no esta en el repo; las J y las K no se pueden comparar.

**La vara de las dificiles**, `cableado58 --dificiles`: las 21 K con su traduccion a mano. Con la traduccion perfecta el
codigo resuelve 18 de 21: el multienvio, las cantidades repartidas y el pago dividido andan; lo que falla ahi es la
traduccion. Quedan K09, un renglon sin stock frena el presupuesto entero; K15, no contesta si le alcanza el tope, con su
arreglo en `banco_pruebas/forma_normal/k15_me_alcanza.patch`, que pasa K15 y excede en 3 el techo de lineas de `app/`;
y K12, redaccion contra una vara estricta.

**El defecto que aparecio**: `normal.lugares` perdia el lugar junto a un modelo con numeros, "un G203 a Rosario". Esta
arreglado y con test; no mueve ningun numero grabado.

**El paso 1, hecho el 27-oct**: `--dificiles` da 20 de 21. K15 contesta "Te alcanza: con $30.000 te sobran $2.500"
dentro de la cuenta. K09: el elegido por criterio es el primero del orden con stock para todo lo pedido del rubro, y el
texto dice por que salteo al primero; y un envio que no se pudo cotizar pregunta en vez de dar un total sin envio, que
era un error sin avisar. Sin subir el techo de lineas; las respuestas grabadas de Gemini iguales, 70 de 74 y 35 BIEN.

**El plan, en orden, con su numero**: cada paso se cierra antes del siguiente.
1. Codigo, sin modelo: K09 y K15. Meta, 20 de 21 en `--dificiles`.
2. La traduccion real: una corrida del bot de hoy sobre las 21 K, unos 0,15 dolares con la paga y el ok de Martin.
3. Candados: donde la traduccion falla, el codigo repregunta. Meta, cero errores sin avisar.
4. Recien ahi, comparar arquitecturas con la misma vara.

## El gasto

Los embeddings con la paga por orden de Martin, menos de un centavo. La tercera vuelta, con la paga y el ok de Martin:
0,40 dolares, los sueltos y las variantes. El endpoint no informa el uso: el libro los anota en
cero.
