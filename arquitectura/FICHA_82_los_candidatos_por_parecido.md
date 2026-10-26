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

## El gasto

Los embeddings con la paga por orden de Martin, menos de un centavo. El endpoint no informa el uso: el libro los anota en
cero.
