FICHA 86 — MANUAL DEL PEDIDO POR COMANDOS

2-nov-2026, con Martín. Para Claude Code, Opus, Grok o Cursor.
Reemplaza al paso 3 y al paso 5 de la FICHA 85. El resto de la FICHA 85 sigue, con las correcciones de la parte 10.
Antes de tocar nada: el bloque 0 de CLAUDE.md, MAPA.md y este manual entero. Nada más.


PARTE 1. LO QUE ESTE MANUAL RESUELVE, EN UNA LÍNEA

El modelo interpreta bien la charla, pero nunca pudo pasarle eso al código de forma confiable. Este manual define ese paso: el modelo ya no reescribe el pedido, manda comandos cortos de una lista cerrada, y el código los valida, los aplica sobre un estado que vive entre turnos, y arma las preguntas.


PARTE 2. LO QUE SE ENCONTRÓ LEYENDO EL CÓDIGO, Y POR QUÉ ESTO NO ES EMPEZAR DE CERO

La máquina del pedido ya existe y está probada: app/core/flujo/borrador.py, de la FICHA 71, con tests/test_borrador.py. Hace exactamente lo que hace falta:

aplicar: recibe operaciones sobre lo dicho. agrega, cambia L-n, saca L-n, confirma L-n, reparto, total.
resolver: cada renglón contra el catálogo, con identidad certificada, criterio por rubro y los otros.
faltantes: lo que falta, con su tipo: modelo, color, cantidad, stock, cantidad_stock, confirmar, otros, destino, pago, medio, supuesto.
preguntas: una pregunta por faltante, escrita por el código.
libreta: el pedido en renglones de texto, L-1, L-2, con lo que falta en cada uno.

El ejecutor ya la usa: ejecutor._comprar llama a B.aplicar, y Turno.derivar resuelve, pregunta y arma la cuenta.

El problema está en un solo lugar, agente.presupuesto, en app/core/flujo/agente.py:

Uno. Llama a ejecutar con E.leer de un diccionario vacío. Cada presupuesto arranca de cero: el borrador no sobrevive al turno, no hay L-n estables, no hay propuesta ni supuesto entre turnos.
Dos. Le pasa el pedido entero con reemplaza en true. Por eso el modelo tiene que reescribir todo cada vez, y en esa reescritura inventa, omite o duplica.
Tres. La memoria del agente guarda los renglones como JSON escrito por el modelo, no lo que dijo el cliente.
Cuatro. Lo que falta lo pregunta el modelo cuando quiere, y la consigna le dice elegí vos.

Esto explica los errores 1, 2, 3, 5, 7, 9, 12, 13 y 17 de la FICHA 85 con una sola causa: la máquina del pedido está, pero el agente la saltea.

La solución es conectar el agente a la máquina que ya existe, no construir otra.


PARTE 3. EL PATRÓN, PARA ENTENDERLO SIN CÓDIGO

Es el diseño CALM de Rasa, publicado y usado en producción. El modelo entiende y propone; el código decide y ejecuta.

Cómo se traduce a Verifika:

El cliente pide algo nuevo: el modelo manda agrega. Lo aplica borrador.aplicar.
El cliente corrige algo: el modelo manda cambia con el número de renglón. Lo aplica borrador.aplicar.
El cliente saca algo: saca con el número de renglón.
El cliente acepta lo supuesto o una condición: confirma.
El cliente dice cómo paga: pago, como lo dijo. Lo valida agente._reparto con lo dicho.
Algo es ambiguo o falta: no hay comando, lo detecta borrador.faltantes y lo pregunta borrador.preguntas. El modelo no elige por el cliente.
El cliente cierra: cobrar, como hoy, con el pedido que derivó el código.

El modelo sigue haciendo lo que hace bien: buscar con sus palabras, entender qué quiso decir el cliente, y escribir la venta.

Las opciones que se consideraron:
Opción A, elegida: comandos sobre el borrador que ya existe. Reduce, no reescribe, y la máquina ya responde, ver lo que ya se probó.
Opción B: una segunda llamada que solo arme los comandos. Descartada por ahora: los modelos más grandes dieron lo mismo, así que el límite es el traspaso y no la llamada. Se reconsidera solo si el paso 6 lo pide.
Opción C: usar Rasa entero. Descartada: es reescribir el bot de cero, contra la regla de reducir lo que existe.


PARTE 4. LA GRAMÁTICA CERRADA

4.1 Las herramientas quedan así

buscar: igual que hoy.
calcular: igual que hoy.
cobrar: igual que hoy por fuera; por dentro lee el pedido derivado, parte 7.
pedido: NUEVA. Reemplaza al presupuesto con anotar en true. Cambia el pedido del cliente con comandos.
cotizar: es el presupuesto de hoy con anotar en false, sin tocar el pedido. Para cuánto sale esto a tal lugar.

4.2 El esquema de la herramienta pedido

```json
{"name": "pedido",
 "description": "Cambia el pedido del cliente con lo que dijo en este mensaje. Solo los cambios, nunca el pedido entero.",
 "parameters": {"type": "object", "properties": {
   "agrega": {"type": "array", "items": {"type": "object", "properties": {
       "producto": {"type": "string", "description": "el nombre tal como salio del buscador"},
       "entre": {"type": "array", "items": {"type": "string"}, "description": "si el cliente no eligio: los nombres entre los que duda, en lugar de producto"},
       "cantidad": {"type": "integer"}, "color": {"type": "string"}, "destino": {"type": "string"},
       "cita": {"type": "string", "description": "las palabras del cliente que piden esto"}},
     "required": ["cita"]}},
   "cambia": {"type": "array", "items": {"type": "object", "properties": {
       "es": {"type": "string", "description": "el renglon, L-1, L-2"},
       "producto": {"type": "string"}, "cantidad": {"type": "integer"}, "color": {"type": "string"},
       "destino": {"type": "string"}, "cita": {"type": "string"}},
     "required": ["es", "cita"]}},
   "saca": {"type": "array", "items": {"type": "string"}},
   "confirma": {"type": "array", "items": {"type": "string"}},
   "pago": {"type": "string", "description": "como lo dijo el cliente: 70 transferencia, 30 mercado pago"},
   "tope": {"type": "integer"},
   "total": {"type": "integer", "description": "cuantos articulos dijo que son en total"}}}}
```

Decisiones de diseño, y por qué:

cita es obligatoria. Es lo que permite al código rechazar un dato inventado, parte 5.
Los productos van por nombre, no por id. El id en lo que lee el modelo se midió peor el 1-nov, commit 3e04b67 revertido.
Los renglones sí van por número, L-1, L-2. Es un número de renglón del pedido, no de producto, y el modelo lo lee al lado del texto en la libreta.
Si el cliente no eligió entre varios, el modelo manda entre con los candidatos, en lugar de producto. El handler pasa esa lista como producto al ejecutor, y ejecutor._comprar con ejecutor._uno ya pregunta cuál cuando son modelos distintos. Esto es el error 5, C50. Un agrega sin producto y sin entre se rechaza.

4.3 La consigna, lo que cambia

Se borra:
La línea que dice que para cambiar el pedido se manda entero corregido con anotar en true.
La línea que dice elegí vos con el criterio que dio, o el más barato con stock.
La línea que dice que si el cliente compra, cambia o confirma se arma el presupuesto con el pedido entero.

Se escribe en su lugar, con estas ideas y en el estilo de la consigna actual:
Si el cliente compra, cambia, saca o confirma algo, usá pedido con solo ese cambio y las palabras del cliente en cita.
Para cambiar o sacar algo que ya está, usá el número de renglón de la libreta.
Si el cliente no eligió entre opciones, mandá las opciones en entre: el sistema le pregunta.
Lo que el sistema pregunta y el pedido como queda los pega el sistema: escribí [[PEDIDO]] donde van.

La consigna no crece: lo que se suma ocupa menos que lo que se borra. Lo controla el techo de líneas.

4.4 Lo que lee el modelo del pedido

memoria_texto deja de mostrar el JSON del pedido. Muestra borrador.libreta, que ya existe. libreta pide el borrador resuelto y sus faltantes: se llama con borrador.resolver y borrador.faltantes sobre el borrador guardado. Se ve así:

```
- BORRADOR:
  L-1 1 Mouse Logitech G203 a Rosario: 1 Mouse Logitech G203 Lightsync Negro
  L-2 1 Notebook Asus ROG Strix G16 a Posadas: FALTA cual modelo
- PAGA: transferencia 70%, sin decir 30%
```

Es más corto que el JSON y le dice al modelo qué falta. Error 11.


PARTE 5. LA VALIDACIÓN DE PROCEDENCIA, UN SOLO LUGAR

Una función nueva en agente.py, procedencia, que corre antes de borrador.aplicar. Reemplaza a las guardas sueltas por campo. Error 13.

Recibe los comandos y dijo, que agente.responder ya arma con todo lo que dijo el cliente en la charla.

Reglas:

cita: sus palabras normalizadas tienen que estar en dijo. Se acepta si al menos la mayoría de sus palabras de más de dos letras están. Si no, el comando se rechaza entero. Esa mayoría es un umbral: como manda CLAUDE.md, se fija en su propio commit, antes del código que lo usa, con la cuenta escrita sobre las citas de las charlas grabadas.
destino: tiene que salir de normal.lugares aplicado a dijo, o ya estar en el borrador. Si no, se rechaza ese campo, no el comando. Errores 1 y 17, C21 y C53.
pago: los medios se validan con agente._reparto pasándole dijo, que ya hace esto. Un medio no dicho queda sin decir y lo pregunta el borrador. Error 2.
producto: tiene que estar en lo visto, con agente._visto, que ya existe. Si no, vuelve al modelo la nota de buscarlo primero, como hoy.
cantidad: si la cita trae una sola cantidad, en cifras o en palabras de uno a diez, vale esa: se corrige y la nota lo dice. Si no trae, o trae varias, vale la que mande el modelo.

Lo rechazado no se aplica y vuelve al modelo en la nota de la herramienta, una línea por campo, con el motivo. No se suma un aviso nuevo por cada caso: es siempre la misma frase, ese dato no lo dijo el cliente.

Esta misma función es la vara del pedido de la FICHA 85, paso 1f: se corre sobre las charlas grabadas y cuenta cuántos datos del pedido no tienen procedencia. Error 24.


PARTE 6. EL ESTADO ENTRE TURNOS

memoria_agente suma una clave: estado. Es el estado entero que ya usa el ejecutor, con la forma de estado.VACIO: mostrados, pedido, busqueda, abiertas y borrador. Se guarda entero porque el ejecutor y interprete.numeros leen todas esas partes; guardar solo el borrador da errores de clave. MEMORIA en agente.py queda:

```python
MEMORIA = {"estado": {}, "pedido": [], "mostrado": [], "pago": "", "tope": 0, "lead": ""}
```

estado se lee siempre con estado.leer, que completa lo que falte y llena el borrador con borrador.leer. Cuidado, probado el 2-nov: estado.leer recibe el documento de la charla, no el estado. Se llama con un diccionario que tenga el estado guardado en la clave estado_charla. Si se le pasa el estado directo, devuelve uno vacío sin error y el pedido se pierde en silencio.
estado borrador es lo dicho. Es la verdad del pedido.
estado pedido es lo derivado: la salida de borrador.articulos, que deja Turno.derivar. Nadie lo escribe a mano.
pedido, mostrado, pago y tope de la memoria quedan solo para cotizar y para leer una charla vieja. El pago y el tope del pedido viven en el borrador.

La charla empezada antes: estado_de, si el estado guardado no tiene borrador y la memoria tiene un pedido viejo, lo convierte al leer en renglones dichos y confirmados. No se guarda: el estado se guarda recién cuando la herramienta pedido lo escribe. Así, mientras el bot siga con el pedido viejo, no queda un estado viejo al lado. Hecho el 2-nov: se probó primero en memoria_de y se movió por eso.

El turno que falla no guarda nada. Hoy la memoria se actualiza al final con _ultimo. El handler de pedido trabaja sobre una copia profunda del estado, la guarda en memoria con la clave _ultimo, y responder la aplica solo si la respuesta sale. Si en el mismo turno hay dos llamadas a pedido, la segunda parte de la copia que dejó la primera.

Firestore no guarda listas dentro de listas. El borrador ya está hecho para eso: borrador._combo guarda la lectura como texto. No se agrega ninguna lista anidada nueva.


PARTE 7. EL HANDLER, PASO A PASO

En agente.py, una función pedido con la misma firma que presupuesto hoy: pedido de a, memoria, tienda_id, visto, dijo. Devuelve lo que lee el cliente y la nota para el modelo.

Uno. procedencia sobre a. Lo rechazado va a la nota.
Dos. Lo ambiguo por lo mostrado: cada producto que identificar da ambiguo se resuelve con lo visto, con el mismo bloque que hoy está en presupuesto, de lo ambiguo se resuelve por lo mostrado del 1-nov. Ese bloque se saca a una función propia y la usan pedido y cotizar. No se borra: sin él vuelve a fallar K18 t3.
Tres. estado igual a una copia profunda de estado.leer sobre la memoria, o sobre _ultimo si ya hubo una llamada a pedido en el turno.
Cuatro. Arma la agenda con dos preguntas, como hoy pero sin reemplaza: una comprar con agrega, cambia, saca, confirma y total, donde cada agrega con entre lleva esa lista como producto; y una cuenta con el reparto, que sale de agente._reparto con dijo, y el tope. La cuenta va solo si vino pago o tope: el ejecutor ya cuenta solo el pedido que cambió, y una cuenta con el pedido vacío le pregunta al cliente de qué productos quiere la cuenta.
Cinco. Llama a ejecutar con esa agenda y ese estado. El ejecutor aplica al borrador, deriva, pregunta lo que falta y arma la cuenta. Todo eso ya existe. ejecutar pasa la agenda por normal.normalizar por su cuenta: ver riesgos.
Seis. Lo que lee el cliente es redaccion.texto de los hechos y las preguntas, como hoy. Ahí ya van las preguntas del borrador.
Siete. La nota para el modelo es la libreta nueva más lo rechazado. Nada más.
Ocho. Deja en memoria _ultimo el estado nuevo, en la clave estado. responder lo aplica solo si la respuesta sale, como hoy. Cada herramienta actualiza solo sus claves dentro de _ultimo, sin pisar las otras: hoy presupuesto reemplaza _ultimo entero, y con pedido y cotizar en el mismo turno se perdería una de las dos.

cotizar es el presupuesto de hoy, con su nombre nuevo y siempre con anotar en false. No toca el estado.

cobrar cambia esto: el pedido sale de estado pedido, y cobra solo si borrador.etapa, con resolver, faltantes y articulos del borrador, da falta_nombre o completo. Si no, la nota dice qué falta, con las preguntas del borrador. La orden del lead se arma llamando a ejecutar con una agenda de solo cuenta sobre una copia del estado guardado. El nombre que recibe se guarda en el cliente del borrador.

pegar: [[PEDIDO]] se cambia por lo que leyó el cliente de la última llamada a pedido del turno. Si el modelo no escribió [[PEDIDO]] y hubo una llamada a pedido, el código lo pega al final, igual que ya hace con el cobro. Error 8, K21. [[PRESUPUESTO]] sigue valiendo para cotizar.


PARTE 8. LOS FLUJOS QUE EL BOT CUBRE

Consultar: buscar. Sin cambios.
Comparar: buscar dos veces, una por producto. Sin cambios.
Una regla de la tienda: buscar. La hoja de reglas ya va siempre en la consigna.
No vendemos: buscar ya lo dice.
Cotizar sin comprar: cotizar.
Armar el pedido: pedido con agrega.
Cambiar el pedido: pedido con cambia o saca, por número de renglón.
Pedido con varios destinos: un agrega por destino, cada uno con su cita.
Pago partido: pedido con pago. El reparto lo calcula el ejecutor.
Algo ambiguo: el modelo manda las opciones; el código pregunta.
Cerrar: cobrar.

Ampliar el alcance después es sumar un flujo con sus comandos, no una guarda.


PARTE 9. CHARLAS MODELO

Cada charla es un test sin modelo: se llama al handler con los comandos que el modelo debería mandar, y se controla la libreta y las preguntas. dijo lleva lo que escribió el cliente, y visto los nombres que se le mostraron, como los arma hoy responder. Los nombres de productos son del clon y ya se confirmaron, ver lo que ya se probó.

Charla 1. Pedido simple.
Cliente: quiero el mouse M220 negro, mandalo a Concordia.
Comandos: agrega producto Mouse Logitech M220 Silent Negro, cantidad 1, destino Concordia, cita mouse M220 negro mandalo a Concordia.
Libreta: L-1 con el M220 a Concordia, sin faltantes. Sale la cuenta con el envío.

Charla 2. Destino inventado, errores 1 y 17.
Cliente: sumame unos auriculares HyperX.
El modelo manda destino CABA sin que el cliente lo haya dicho.
Esperado: el renglón entra sin destino. La nota dice que CABA no lo dijo el cliente. Si ya hay otro renglón con destino, el borrador pregunta a dónde va.

Charla 3. Medio inventado, error 2.
Cliente: pago setenta treinta.
El modelo manda 70 transferencia, 30 mercado pago.
Esperado: el reparto queda 70 y 30 sin medio. Pregunta: con qué medio pagás cada parte.

Charla 4. Solo el cambio, errores 3, 7 y 9.
Turno 1, el cliente pide tres cosas a dos destinos. Tres agrega.
Turno 2, el cliente dice: el mouse cambialo por el G305.
Comando: solo cambia es L-1, producto el G305, cita el mouse cambialo por el G305.
Esperado: L-2 y L-3 quedan iguales. Ningún renglón se duplica ni se pierde.

Charla 5. Elegir entre dos, error 5, C50.
Turno 1, se mostraron el G203 y el G305.
Cliente: me llevo uno.
Comando: agrega con entre G203 y G305, sin producto, cita me llevo uno.
Esperado: pregunta cuál de los dos. Nada entra al pedido hasta que conteste.

Charla 6. Sacar sin perder.
Pedido de tres renglones. Cliente: sacá los auriculares.
Comando: saca L-2.
Esperado: quedan L-1 y L-3, con sus números de siempre. El cliente lo pidió, así que se saca sin preguntar. La protección de Turno.derivar contra perder el pedido solo corre con reemplaza, y acá no se usa.

Charla 7. Cita que no es del cliente, error 12.
El modelo manda un agrega con una cita que el cliente no escribió.
Esperado: el comando no se aplica y la nota lo dice.

Charla 8. Charla vieja.
Una memoria guardada con el formato de hoy, pedido en JSON.
Esperado: memoria_de la convierte en borrador con renglones confirmados, y la libreta muestra el mismo pedido.

Charla 9. Turno que falla.
El modelo llama a pedido y después la llamada al modelo se cae.
Esperado: la memoria guardada queda como estaba antes del turno.


LO QUE YA SE PROBÓ, 2-nov, sin modelo, con el clon y el código de main de hoy

Cuatro turnos seguidos llamando a ejecutar con comandos, y el estado pasado por JSON entre turno y turno como si fuera Firestore:
Turno 1, dos agrega a Concordia y Posadas: L-1 y L-2, con la cuenta y los dos envíos.
Turno 2, cambia L-2 cantidad 1: solo cambió L-2. Charla 4.
Turno 3, agrega con dos candidatos, G203 y G305: preguntó cuál decís, y no tocó el pedido. Charla 5.
Turno 4, saca L-1 y pago 70 y 30 sin medio: quedó L-2 con su número, y preguntó con qué medio paga cada parte. Charlas 3 y 6.
Ninguna regla de normal.py se aplicó en los cuatro.
Los cuatro nombres de la parte 9 existen en el clon. G203 y G305 se identifican como Lightsync Negro y Lightspeed Negro.
O sea: la máquina responde a los comandos como dice este manual. Lo que falta construir es procedencia, el handler, la consigna y la memoria.


LO HECHO EL 2-NOV, PASOS 1 A 4, sin conectar al modelo

Commits en main, en este orden: los tests como plan; el estado; el umbral de la cita en su propio commit; procedencia; el handler y el pegado; y la corrección de la charla vieja.
Lo que quedó distinto de lo escrito arriba, y ya está corregido en este manual: la conversión de la charla vieja vive en estado_de y no se guarda; la cantidad se corrige a la de la cita; cada agrega con entre va en su propia compra, porque si el ejecutor pregunta cuál, corta esa compra entera.
tests/test_agente_pedido.py tiene 13 tests en verde. La batería offline pasa entera, 456, salvo el techo de líneas.
El techo: app/ quedó en 8.322 líneas de código contra 8.250. Subirlo es decisión de Martín. Lo que el paso 7 archive de presupuesto y del pedido en JSON tiene que devolver al menos esas 72.
Lo que falta para el paso 5, además de lo de la parte 4: en responder, sumar pedido a las herramientas cuyo texto va al cliente, que hoy son presupuesto y cobrar, en los dos lugares donde aparecen. Sin eso, pegar no encuentra lo que pegar.
Se vio en la prueba: si el ejecutor pregunta cuál entre dos, la pregunta no queda guardada para el turno siguiente. El modelo resuelve con la respuesta del cliente mandando el agrega. Si en el paso 6 eso falla, se mira abiertas en el estado.


PARTE 10. LOS PASOS DE EDICIÓN

Regla para cada paso: primero el test, después el código, después la medición. Un paso por sesión. Antes de cada paso se lee el archivo entero que se va a editar. El push se consulta con Martín, como dice el bloque 0.

Paso 0. El instrumento, prerrequisito.
Es el paso 1 de la FICHA 85, al menos 1a, 1b y 1c, y tres corridas de la base. Sin eso no se puede saber si lo de abajo mejora.

Paso 1. Los tests de las charlas modelo.
Archivo nuevo: tests/test_agente_pedido.py, con el clon como en tests/test_agente_plata.py.
Las nueve charlas de la parte 9, cada una como xfail strict con motivo que empieza con PLAN: FICHA 86.
Criterio: la batería offline pasa, con nueve xfail nuevos.
Comando:
```bash
python3 -m pytest -q tests/test_agente_pedido.py
```

Paso 2. El estado entre turnos.
Archivo: app/core/flujo/agente.py, MEMORIA y memoria_de.
Se suma la clave estado, y la conversión de la charla vieja de la parte 6.
Criterio: pasa la charla 8. tests/test_agente.py sigue en 74 de 75: con el formato viejo nada cambia todavía.

Paso 3. procedencia.
Archivo: app/core/flujo/agente.py.
La función de la parte 5, usando normal.lugares, agente._reparto y agente._visto.
Criterio: pasan las charlas 2, 3 y 7 llamando a procedencia sola.

Paso 4. El handler pedido y pegar.
Archivo: app/core/flujo/agente.py.
La función de la parte 7, y el cambio en pegar.
La resolución de lo ambiguo por lo mostrado se saca a su propia función y la usan pedido y cotizar.
El arreglo del mismo producto con y sin destino queda solo en cotizar. En pedido no hace falta: el modelo manda solo el cambio, y si igual llegan dos renglones, el borrador pregunta el destino del que no lo tiene.
Los tests de tests/test_agente_plata.py se corren por el camino nuevo. Si alguno cambia de resultado, se para y se consulta con Martín: no se edita el test.
Criterio: pasan las nueve charlas. Se quita el xfail de cada una. La batería offline entera pasa.

Paso 5. El esquema y la consigna.
Archivo: app/core/flujo/agente.py, HERRAMIENTAS, CONSIGNA, memoria_texto y el despacho de herramientas en responder.
Lo de las partes 4.1 a 4.4.
Esto cambia lo que lee el modelo. tests/test_agente.py va a fallar en las llamadas iguales: es lo esperado.
Criterio: el techo de líneas no sube. La batería offline pasa salvo tests/test_agente.py.

Paso 6. Regrabar y medir.
Las 26 charlas con la gratis:
```bash
python3 banco_pruebas/agente_replay.py --gratis --regrabar
```
Después, tres corridas con la gratis y la regla de decisión de la FICHA 85, paso 1d.
Después, el examen real de 42 charlas, tres corridas.
Criterio para que entre: la vara no baja del piso de la base medida en el paso 0, y en el examen real bajan los errores de destino, medio, omisión y duplicado sin que suba otra clase.
Si no entra: se revierte con git y se anota en PENDIENTE.md qué clase falló, con lo grabado del caso.

Paso 7. Lo que quedó muerto.
Con el camino nuevo vivo, se mira con cobertura qué partes de presupuesto, memoria_texto y los arreglos del pedido JSON ya no corren, y se pasan a archivo en su propio commit.

Corrección a la FICHA 85, paso 2a: NO se archivan borrador.py, el comprar y el derivar del ejecutor, ni normal.py. Con este manual vuelven a ser el camino vivo. Lo que se mide como muerto se mide después del paso 6, no antes.


PARTE 11. LO QUE NO SE HACE

No se agrega una segunda llamada al modelo. El pedido por comandos resuelve el traspaso dentro de la misma llamada. El paso 5 de la FICHA 85 queda descartado salvo que el examen real lo vuelva a pedir.
No se cambia el modelo de producción.
No se pone el id del producto en lo que lee el modelo.
No se tocan las casillas de la vara sin el ok de Martín.
No se toca la fuente de verdad ni la FAQ.
No se suma una regla de normal.py ni una guarda por caso. Si una charla falla, se mira primero si falta un comando, después si falta un tipo de faltante en el borrador.


PARTE 12. CÓMO CUBRE LOS 30 ERRORES

Del modelo:
1, destinos inventados: procedencia, destino.
2, medios inventados: procedencia, pago.
3, omisiones en mensaje largo: comandos por cambio, la libreta muestra lo que falta.
4, niega una regla a la vista: sigue en el verificador como hoy. Este manual no lo cubre; se mide si baja al achicar lo que lee el modelo.
5, elige solo: el modelo manda entre, pregunta el código.
6, inventa etiquetas: no lo toca este manual. FICHA 85, 4c.
7, reenvía el pedido entero: comandos por cambio.
8, no muestra el presupuesto: pegar lo pone siempre que hubo pedido.
9, no compara pedido con lo pedido: lo hace el código con resolver, faltantes y el total.

Del cableado:
10, una sola llamada: se mantiene, ahora con el traspaso resuelto.
11, 7.000 tokens: la libreta en lugar del JSON; el resto en FICHA 85, paso 2.
12, el código no guarda lo dicho: el borrador entre turnos y la cita.
13, guardas por campo: procedencia en un solo lugar.
14 y 15, capas viejas y líneas muertas: pasan a ser el camino vivo o se archivan en el paso 7.
16, identidad por nombres copiados: los renglones se refieren por L-n y el borrador guarda el color dicho.
17, destino suelto: el destino va por renglón y pasa por procedencia.
18, notas ruidosas: la nota de pedido es solo la libreta y lo rechazado.

Del banco:
19 a 23: FICHA 85, paso 1, que es el paso 0 acá.
24, la vara mira el texto: procedencia corrida sobre lo grabado.

De la sesión, 25 a 30: FICHA 85, paso 1, reglas de método.


PARTE 13. RIESGOS CONOCIDOS

El borrador viene del flujo anterior y tiene partes complejas: lecturas, propuestas y supuestos. Si alguna se comporta raro con el agente, primero se escribe la charla que lo muestra como test, después se decide.
El modelo puede confundir los números de renglón. Por eso cada renglón de la libreta lleva el texto al lado, y la cita permite controlar el cambio.
ejecutar pasa la agenda por las reglas de normal.py. Con una agenda de solo comprar y cuenta casi ninguna aplica, pero alguna puede tocarla, por ejemplo las que miran el pedido o el destino. El log del ejecutor dice qué reglas aplicó: se mira en cada charla modelo. Si una regla cambia un comando ya validado por procedencia, se consulta antes de tocarla.
Llamar a resolver en cada turno para la libreta identifica cada renglón contra el catálogo. No usa el modelo ni embeddings, pero se mide el tiempo del turno antes y después.
Regrabar cambia lo grabado. CLAUDE.md lo permite cuando el código cambia lo que lee el modelo; el commit lo dice.


FUENTES DEL PATRÓN

Rasa, dialogue understanding: https://rasa.com/docs/learn/concepts/dialogue-understanding/
Rasa, command generator: https://rasa.com/docs/pro/customize/command-generator
