# FICHA 53 — EL TABLERO. Abierta.

**Es el diseño del componente 7 de la FICHA 52, y de nada más.** El tablero es
el índice de lo que se puede preguntar: viaja siempre, antes del motor, y su
único trabajo es que el modelo escriba UNA consulta que pegue a la primera.
Las bocas, los ramales y el retorno se nombran acá por su número de la 52 y no
se vuelven a describir.

Escrita el 13-sep-2026, **antes de tocar una línea de código**, igual que la 52.
No describe lo que corre hoy: describe a dónde va. Lo que corre lo dice el
código, siempre.

**Arranca con el número puesto:** la FICHA 50 dejó medida la maqueta del mapa 1
en **1.349 tokens** con la regla de enumerar por variedad. Remedido hoy sobre
la tienda viva da **1.422 a 1.476** según el umbral —el método está en la
sección 7—. El orden de magnitud se sostiene y el techo se fija sobre el
número de hoy, no sobre el de ayer.

---

## 1. QUÉ ES Y QUÉ NO ES

**El tablero NO TIENE UN SOLO DATO.** No dice qué producto hay ni a qué precio.
Dice **con qué palabras se pregunta**: los campos, lo que se puede hacer con
cada uno, los valores que la fuente usa, y las cinco bocas con lo que contesta
cada una.

**Un valor enumerado NO es un dato, es vocabulario.** Que la fuente escriba
`china` no dice qué producto es chino: dice que ésa es la palabra. La
diferencia es la que hace que el tablero no crezca con el catálogo.

**Un resumen del catálogo crece con el catálogo; un vocabulario crece con la
VARIEDAD.** Siete mil productos de las mismas veintidós categorías tienen el
mismo tablero que ochocientos. Es la salida de la FICHA 50 y no se rediscute.

---

## 2. EL DEFECTO DE HOY, MEDIDO

Leído el 13-sep de `app/core/motor.py:esquema` sobre `verifika_prod`: **4.191
bytes, ~1.047 tokens**. Da los 41 nombres de campo y las 22 categorías. Le
faltan cuatro cosas, y cada una tiene su costo medido.

**1. No dice qué VALORES usa la fuente.** `pais_fabricacion` tiene CINCO
valores en 880 productos:

    633  china
     96  taiwan o china segun linea
     72  tailandia o malasia segun linea
     60  china, taiwan o corea segun linea
     19  malasia o vietnam segun linea

El modelo escribe `pais_fabricacion igual china` y trae **633**. Escribe
`contiene china` y trae **789**. Son **156 productos de diferencia, el 18% del
catálogo**, decididos por un operador que el modelo eligió a ciegas. Y los NO
chinos de verdad son **91**, no los 247 que sale de restar mal. Un filtro que
devuelve de menos no se ve como un error: se ve como que no hay.

**2. No dice EN CUÁNTOS productos está cargado el campo.** `memoria_video` está
en 18 de 880; `sensor` en 52; `potencia` en 85. Filtrar por ellos devuelve casi
nada, y ese casi nada se lee como "no lo tenemos" en vez de "la fuente no lo
tiene cargado". Es la confusión entre la respuesta 2 y la 3 de la FICHA 52, que
la misma ficha llama el defecto más caro del nicho.

**3. No dice qué se puede HACER con cada campo.** Filtrar, ordenar, las dos o
ninguna. `dimensiones` tiene 850 valores distintos en 880 productos: ordenar
por él no significa nada y enumerarlo es basura.

**4. No nombra las cinco bocas.** Nombra dos: el catálogo y los temas. **Una
boca que el tablero no nombra no existe para el modelo, aunque tenga cable.**
Es la otra mitad de lo que la FICHA 52 midió el 13-sep: donde no hay cable no
hay a quién llamar, y donde no hay nombre tampoco.

---

## 3. LAS OCHO DECISIONES

**D1. El tablero viaja como ESQUEMA DE HERRAMIENTA, no como texto.** Ya es así
y se mantiene. Un campo que no está en el enum no se puede ni nombrar. Es el
primer candado de la FICHA 50.

**D2. El enum del proveedor cierra los NOMBRES; el código cierra los VALORES.**
Y es la decisión que más se va a querer revisar, así que queda el motivo
entero. Poner un enum por campo obligaría a partir la consulta en dos formas
—una propiedad por campo enumerado, más `condiciones` para el resto— y eso es
dos formas para lo mismo, que es la regla 2. La atadura va donde ya está
probada: en el código, igual que `certificar_temas` y por el mismo motivo de
peso que sacó el enum de los 129 temas.

**D3. El valor que no existe NO devuelve cero: devuelve el hueco.** Si el
modelo filtra por un valor que la fuente no usa, el motor **no filtra por nada,
lo dice, y devuelve los valores que sí hay**. Es la escuela de
`sin_campo_en_la_fuente`, que ya vive en `filtros_catalogo`: el pedido que la
fuente no expresa se ve como lo que es en vez de disfrazarse de filtro que no
encontró nada. Se llama **hueco de valor** y se anota en el informe.

**D4. Se enumera por VARIEDAD, con umbral, y el umbral vive en el código.**
Campo con pocos valores distintos, se enumeran todos. Campo con muchos, se dice
la variedad y tres ejemplos. Medido hoy: con umbral 8 la maqueta da 1.422
tokens, con 12 da 1.476, con 20 da 1.930. **Arranca en 12** y manda el techo de
la sección 7, no este número.

**D5. Los códigos de modelo se piden por `modelo contiene <codigo>`, y el borde
es de dígitos.** La regla ya vive en `filtros_catalogo._raices` y está medida
desde el 13-ago: el borde de un número son otros dígitos, así que `16` pega en
`16GB` y no en `160`. Con eso **`g15` no pega en `g16` ni en `g150`**, y los
482 modelos distintos no necesitan entrar en el tablero. El caso entero está en
la sección 5.

**D6. El tablero nombra las CINCO BOCAS**, una línea cada una, con lo que
contesta y lo que no. Catálogo, políticas, compatibilidad, envío y criterio,
por su número de la FICHA 52. Sin esto el modelo sólo puede pedir dos.

**D7. Dos pisos, y el segundo casi nunca corre.** El piso 1 viaja siempre. El
piso 2 —pedir los valores de un campo— es **un campo más de la misma puerta**,
nunca una herramienta nueva: el mecanismo de buscar en la fuente es el mismo.
Y casi no se usa porque **el retorno adelanta los valores cuando hacen falta**,
o sea que la desambiguación vuelve CON el resultado y no en una vuelta aparte.
El motivo es de plata: el 12-sep los seis turnos posteriores al mapa 3 gastaron
`vueltas=3`, tres llamadas al modelo por turno, y cada vuelta vuelve a pagar el
prompt entero.

**D8. Se mide o no se hace.** La sección 8 dice qué se loguea.

---

## 4. LA FORMA — tres partes y ninguna más

**PARTE A · LAS CINCO BOCAS.** Qué contesta cada una y qué no. Una línea.

**PARTE B · EL VOCABULARIO DEL CATÁLOGO.** Por campo: el tipo, en cuántos
productos está cargado, qué se puede hacer con él, y los valores **sólo si la
variedad es baja**. Más las 22 categorías con su cuenta, que ya viajan.

**PARTE C · LO QUE LA FUENTE NO TIENE.** `sin_campo_en_la_fuente` para el
pedido que ningún campo expresa, `no_vendidas` para la categoría que la tienda
no vende, y el hueco de valor de D3. **Las tres son respuestas, no errores.**

---

## 5. EL CASO G15, QUE ES EL QUE HAY QUE NO ERRAR

Medido hoy sobre el catálogo vivo:

    modelo contiene g15  →  9 filas, 3 modelos distintos, marca Dell
    modelo contiene g16  →  9 filas, 3 modelos distintos, marca Asus

Son productos de marcas distintas y de precios distintos. Un vecino cercano por
embedding los mezcla; un `contiene` con borde de dígito no puede.

El cliente pregunta *"tenés la G15?"*:

1. El modelo escribe UNA consulta: categoría `notebook`, condición
   `modelo contiene g15`, `busco: uno`.
2. El motor trae 9 filas y 3 modelos. Nueve está arriba del `TOPE_AMBIGUO`, que
   son 4.
3. El retorno devuelve la **respuesta 4 de la FICHA 52 —¿cuál de estos?—**
   agrupada **por el eje que las distingue**, que acá es el procesador y el
   almacenamiento, con su precio. El color va aparte porque no cambia el
   precio: tres modelos, no nueve filas casi iguales.
4. El modelo pregunta **una sola cosa**, que es el atributo de venta 4.

**Lo que no puede pasar, y es lo que esta ficha compra:** que `g15` traiga una
G16; que el motor elija una de las tres; que las nueve filas entren enteras al
prompt; y que el modelo tenga que hacer una vuelta más para saber cuáles son
los tres modelos.

---

## 6. LO QUE NO SE HACE

- **Embeddings**, ni como mecanismo principal ni como respaldo. Regla 10.4: una
  cita tiene que poder mapearse a un id, y un vecino cercano no se verifica
  mecánicamente.
- **Mandar fichas, o un resumen del catálogo.** Crece con la cantidad.
- **Mezclar los tres mapas en un solo enum.** Ya se pagó.
- **Un segundo motor, o una herramienta nueva al lado de `buscar`.** Serían dos
  puertas para lo mismo.
- **Una flag apagada para medir.** Regla 2-bis: el cambio se hace vivo y se
  vuelve con git.

---

## 7. EL PRESUPUESTO, Y EL TECHO SÓLO BAJA

El método, para que el número se pueda repetir: se serializa el esquema como
viaja, se cuentan los bytes y se divide por 4. **No hay tokenizador en el
repo**, así que es una estimación pareja, no un conteo exacto; lo que importa es
que siempre se mida igual.

    hoy, el esquema vivo          4.191 bytes   ~1.047 tokens
    maqueta de campos, umbral 12  5.904 bytes   ~1.476 tokens

**Sumados no entran, y ahí está el trabajo.** Lo que se recorta es la parte de
ejemplos y de prosa, **nunca los enums**: el enum es el candado. El techo del
piso 1 se fija en **1.500 tokens**, vive en un test y **sólo baja**, igual que
los dos techos del bloque 1 de `CLAUDE.md`. Un umbral se cambia en su propio
commit, antes del trabajo que lo hace pasar, con las cuentas escritas.

---

## 8. QUÉ SE MIDE

Por turno, sobre lo que `motor_turno` ya loguea:

- tokens del tablero,
- si el modelo llamó al motor y cuántas consultas mandó,
- qué campos pidió, y cuáles no existían,
- cuántos `sin_campo_en_la_fuente` y cuántos huecos de valor,
- los veredictos que volvieron,
- las vueltas al modelo, que son el costo.

**Sin esto no se optimiza nada**, y además es la regla 10.5: sin logs no hay
deploy. El número de referencia es el del 12-sep, en la sección 8 de la FICHA
52: buscó en 15 de 19 turnos, y en 6 de 6 después del mapa 3.

---

## 9. QUÉ SE ROMPE Y CÓMO SE VUELVE

**Toca el camino vivo**, porque el esquema viaja en cada turno: `motor.esquema`
y lo que `respuesta._preguntar` le pone delante al modelo. Si el tablero
engorda, **paga cada mensaje del día**, y por eso el techo es un test y no una
intención.

Se vuelve con `git revert`. No hay flag, no hay camino viejo al lado.
