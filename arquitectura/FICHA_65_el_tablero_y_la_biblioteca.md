# FICHA 65 — El tablero y la biblioteca

29-sep-2026. Estado: **DISEÑO, sin código.** Reemplaza el plan de la FICHA 64,
que queda como medición de dónde estábamos. El método sigue siendo el de la
FICHA 63: un cambio por vez, tres corridas, la puerta.

Los nombres de las estaciones —T, J, L, D— son los de
`arquitectura/MAPA_CABLEADO.md`. Esta ficha los nombra por número y no los
vuelve a describir.

---

## 1. El problema, medido

28 y 29-sep. Sesenta y tres mensajes nuevos, ninguno de la vara de las 58, un
turno sin memoria, tres corridas con la clave paga pedida por Martín, código
de `main`. Unos cincuenta salen bien en las tres. Lo que falla se agrupa en
cuatro clases, y ninguna es de redacción:

1. **El modelo sabe cómo se llama cada dato, no qué trae adentro.** "Parlante
   que se pueda mojar" filtró por `caracteristicas_extra` teniendo
   `resistencia_agua`, y contestó "no tenemos" con dos parlantes resistentes al
   agua en stock. "El monitor más grande" ordenó por `dimensiones`, que es una
   etiqueta, y afirmó 32 pulgadas habiendo uno de 49. "SSD de 1 tera" mostró
   dos de cinco.
2. **El tema de la FAQ lo elige el código contando palabras.** "Si me llega
   roto qué hago" contestó la política de cambios —diez días, sin uso— en vez
   de `defectuoso` —siete días, sin costo—. Tres de tres, dicho con seguridad.
3. **El modelo trata la muestra como si fuera el catálogo.** "Combo teclado,
   mouse y auriculares por menos de 100 mil" contestó que es imposible con un
   combo de 78 mil en la tienda: razonó sobre cinco filas sin orden.
4. **Un valor forzado a lo que hay.** Apareció al darle la lista de valores:
   "que las teclas hagan click" terminó en `switch red`, que no hace click, y
   se lo presentó al cliente como si lo hiciera.

Se probó darle al modelo un diccionario de campos generado de la fuente.
Arregló la clase 1 en tres de tres, trajo la clase 4 y subió el turno de unos
4.000 a unos 6.300 tokens. No se midió contra las 58 y no entró. Quedó como
borrador fuera de `main`: si se pierde, se rehace desde la sección 5.

**Lo que enseña:** cada arreglo de a un pedazo tapa un hueco y abre otro. Lo
que falta no es una regla más: es que el modelo traduzca contra un mapa
completo de lo que la tienda puede contestar, y que el código pueda revisar esa
traducción antes de usarla.

---

## 2. La idea: lo infinito es cómo escribe el cliente, lo finito es lo que puede pedir

El cliente tiene infinitas formas de escribir. Lo que puede pedirle a una
tienda online es finito, y se ordena en **tres capas**:

| capa | qué es | quién la escribe | crece con |
|---|---|---|---|
| 1 · las cosas | producto, rubro, dato, envío, pago, política, lo del cliente | se escribe una vez, igual para toda tienda | nada |
| 2 · las acciones | nombrar, filtrar, ordenar, comparar, sumar, condicionar, referirse, verificar, preguntar | se escribe una vez, igual para toda tienda | nada |
| 3 · el vocabulario | los rubros, datos, valores, temas y marcas de UNA tienda | lo genera el código de su fuente | los rubros y datos de la tienda, nunca los productos |

**Traducir un mensaje es escribir una combinación de las tres.** Las capas 1
y 2 son una gramática, no una lista de casos: una frase nueva —"que no sea una
porquería"— no agrega nada, cae en ordenar o en excluir. La lista crece sólo
si aparece una acción de verdad nueva.

**La regla que impide que crezca sin fin:** en las capas 1 y 2 nunca entra una
frase ni un ejemplo, sólo categorías. Si un caso no entra, primero se pregunta
si es vocabulario de la tienda: entonces va a la capa 3, que la genera el
código.

**Cómo se sabe que está completa:** cada caso nuevo se etiqueta contra la
gramática. Si los últimos treinta entran sin agregar nada, está saturada.

---

## 3. Capa 1 — las cosas

Universales. Ningún nombre de esta tienda.

- **producto**: siempre por un id que el código certificó. Veredictos `exists`,
  `ambiguous`, `not_found` —regla 10.0—.
- **variante**: el mismo modelo en otro color u otra capacidad.
- **dato de producto**: un campo de la ficha, con su clase —medida, sí o no,
  lista cerrada, texto—.
- **rubro** y **sección**: el estante y el piso de la biblioteca.
- **marca**.
- **precio** y **stock**: sólo de la fuente, nunca del modelo.
- **pedido**: productos con cantidad, destino y reparto de pago.
- **destino**: una localidad, con su tarifa y plazo.
- **medio de pago** y **reparto**: porcentajes por medio, con sus descuentos.
- **tema de la casa**: una entrada de la FAQ.
- **lo del cliente**: su equipo, su destino, su presupuesto, sus preferencias
  y exclusiones, su nombre. Nunca DNI, tarjeta ni CBU —sección 6 de CLAUDE.md—.
- **lo mostrado**: lo que el bot ya le dijo, numerado.
- **saber general**: lo que no es de la tienda —qué es un switch, Intel o AMD—.

---

## 4. Capa 2 — las acciones

Cada acción dice qué necesita y qué revisa el código. Al lado, las clases de
la vara de las 58 que cubre: cada charla tiene que caer en al menos una. Si
alguna no cae, falta una acción.

**De identidad y búsqueda**

- **nombrar**: un producto por su nombre, entero o parcial. El código certifica
  o devuelve `ambiguous`, y ante `ambiguous` se pregunta. — C01, C43, C49.
- **buscar**: un rubro con condiciones. — C02, J01 a J10 por jerga.
- **condición**, con cuatro fuerzas: **exigir**, **preferir**, **excluir**, **lo
  menos posible**. Sobre un dato que existe en ese rubro y con un valor que la
  fuente usa. — C05, C06, C07, C08, C42.
- **ordenar**: por un dato que es medida, mínimo o máximo. El criterio puede
  ser implícito: "estoy corto de plata" es precio mínimo. — C09, J01.
- **comparar**: dos o más productos en uno o varios datos. — C32.

**Sobre lo que se dice**

- **preguntar un dato**: de un producto. Si la ficha no lo trae, la respuesta
  es "no figura". — C03.
- **verificar**: lo que el cliente da por cierto de la tienda o de un producto.
  Nunca se acepta sin consultar. — C04, C12, C39, C40, C56.
- **cruzar**: si un producto anda con un equipo u otro producto. Si falta el
  dato del cliente, se pregunta. — C36, C37, C38, C54.

**De la operación**

- **mandar**: envío a uno o varios destinos, y destino por pieza. — C10, C18,
  C26, C52.
- **sumar**: el total de un pedido, con cantidad por pieza, destino y reparto.
  La cuenta la hace la calculadora. — C16, C20, C21, C25.
- **comprar**: reservar y pedir el nombre. — C15, C29.
- **política**: un tema de la casa. — C11, C19.

**Sin herramienta**

- **saber general**: se explica con lo que el modelo sabe. — C14, C22.
- **charla**: saludo, agradecimiento, lo que no es pedido. — C58.
- **sobre sí mismo**: qué es el bot, qué puede hacer. — C13, C41.

**Las dos salidas honestas, de primera clase**

- **preguntar al cliente**: cuando falta un dato suyo o hay ambigüedad. — C50.
- **no tengo ese dato**: cuando la tienda no lo sabe o no lo vende. — C57.

Son acciones como las demás, no un fracaso: son el lugar legítimo del cinco
por ciento que no se traduce bien.

**Modificadores**, que se aplican a cualquier acción:

- **alcance**: a una pieza o a todas. — C23, C24.
- **dependencia**: "si no hay, esto otro", "si da sí, compro", "si el cruce
  da no, una alternativa", "si pasa de un monto, sacá". La pieza dependiente
  corre después y según el resultado de la otra. — C28, C29, C30, C31, C53.
- **varias piezas con distinto verbo** en un mensaje. — C17, C51.
- **corrección**: en el mismo mensaje o de un turno anterior. — C33, C34.

---

## 5. Capa 3 — el vocabulario de la tienda

Lo genera el código de la fuente de cada tienda. Nadie lo escribe a mano, y no
se copia a ningún documento —sección 9 de CLAUDE.md—.

- **secciones y rubros**, con cuántos productos tiene cada uno.
- **los datos de cada rubro**, con su clase:
  - **medida**: se ordena y se compara. Un valor es medida si empieza con el
    número y es corto —"75Hz", "512GB SSD"—; se mide sobre todos los valores
    del campo, no rubro por rubro.
  - **sí o no**.
  - **lista cerrada**: se muestran todos sus valores **como los únicos que
    existen**. Lo que el cliente pide y no está, no existe: se dice. Así se
    cierra la clase 4.
  - **texto**: se muestran los valores más frecuentes, tal como los escribe la
    fuente —"16gb", "inalambrico"—, para que el pedido use el vocabulario real.
- **los temas de la casa**, cada uno con una línea de qué contesta, sacada de
  la FAQ. El modelo elige el tema leyendo eso. Así se cierra la clase 2.
- **las marcas**, y **los destinos** con tarifa.

**La ingesta ordena la prosa, una sola vez.** Al subir el catálogo, lo que está
escrito en prosa —"resistente al agua" dentro de una descripción, el origen—
se pasa a datos. El modelo lo hace una vez por tienda, fuera de la charla, y
el código lo guarda al lado del catálogo, como hoy `alias.json` con
`scripts/generar_alias.py`. En la charla el modelo sólo elige entre cosas que
existen. Resuelve también la desconexión D8, el origen en prosa.

**El techo.** La capa 3 entra entera en el tablero si cabe bajo un techo de
tokens. Si no cabe, entra por niveles —sección 7—. Hoy, con el catálogo de
esta tienda, el borrador del diccionario de campos midió unos mil tokens.

---

## 6. La memoria, dentro del lenguaje

La memoria no es texto suelto que el modelo tiene que interpretar: son
**objetos que guarda el código** y a los que la traducción se refiere por
número. Así una referencia se puede validar como cualquier otra pieza.

### Lo que guarda el código, determinista

- **M1 · lo mostrado**, numerado en el orden en que el cliente lo leyó. Un
  modelo en dos colores es un renglón. Cada renglón con su id y el turno.
  Además, **si era la lista entera o una muestra**: cuántos había y cuántos se
  mostraron.
- **M2 · la última búsqueda**: rubro, condiciones y orden.
- **M3 · las condiciones vigentes del cliente**: "que no sea Redragon", "con
  cable". Valen hasta que las cambie.
- **M4 · lo del cliente**: destino, equipo, presupuesto, nombre.
- **M5 · el pedido en curso**: productos, cantidades, destino y reparto.
- **M6 · la pregunta abierta del bot**: si el bot preguntó algo, qué preguntó
  y entre qué opciones.

### Cómo se refiere el cliente, y es una lista cerrada

- **ordinal**: "el primero", "el segundo" → un renglón de M1.
- **deíctico**: "ese", "el otro", "lo mismo" → M1 o M5.
- **por atributo**: "el de 37 mil", "el blanco" → el renglón de M1 que lo
  cumple; si cumplen dos, se pregunta.
- **por nombre parcial lejano**: "el logi del principio" → M1 de cualquier
  turno, certificado por el motor.
- **de esos**: el grupo. **Si M1 era la lista entera, se elige entre M1. Si era
  una muestra, el grupo es la búsqueda entera, M2.** Esto resuelve la
  contradicción de C27 sin tocar la vara, y la clase 3 del punto 1.
- **todo**: M5 entero.

### Lo que se hace con la memoria

- **elegir entre lo mostrado**: "de esos, el más barato". — C27.
- **refinar la última búsqueda**: M2 más una condición nueva. "Y en blanco",
  "y alguno mecánico" es una búsqueda nueva, no una elección entre lo mostrado.
  — C45, C46.
- **heredar una condición vigente**: M3 viaja a la búsqueda nueva. — C46.
- **cambiar o soltar una condición**: "ya no importa la marca". — C35.
- **corregir un dato**: "era para Córdoba, no Rosario". — C34.
- **usar un dato del cliente dicho antes**: "soy de Posadas", y después el
  envío. — C47.
- **operar sobre el pedido**: sumar, agregar, quitar, cambiar cantidad,
  repartir. — C21, C48, C55.
- **contestar la pregunta abierta**: "el primero" responde a M6. — C50.
- **memoria con dependencia**: "del que me dijiste, si no hay en negro, el
  blanco". — C53.
- **cruzar lo del cliente**: "le sirve a mi pc", con M4. — C38.

**Validación:** toda referencia tiene que resolver a un id de M1 o de M5, o a
un dato de M4. Si no resuelve o resuelve a dos, la pieza pasa a **preguntar al
cliente**. El modelo nunca elige a ciegas.

### Casos de memoria nuevos, para sumar a la vara en el paso 0

Charlas que la vara de las 58 no tiene y que esta capa tiene que cubrir:

1. "Mostrame auriculares bluetooth" → "el más barato de esos pero en blanco":
   de esos, más orden, más variante.
2. "Soy de Mendoza" → tres turnos de otra cosa → "cuánto sale mandarme el
   segundo": dato viejo del cliente más ordinal.
3. "Quiero dos G203" → "agregale uno más del mismo": cantidad sobre el pedido.
4. Un pedido de tres cosas → "sacá el más caro": orden dentro del pedido.
5. Una cuenta con envío a Rosario → "¿y a Córdoba?": el mismo pedido con otro
   destino.
6. "Eran tres, no dos" dicho dos turnos después: corrección tardía de cantidad.
7. El bot pregunta el color → "cualquiera, el más barato": respuesta a la
   pregunta abierta con un criterio en vez de un valor.
8. "Comparame el primero con el G502": ordinal más un producto nombrado.
9. "Que no sea Redragon" en teclados → "ahora pasame mouses": ¿la exclusión
   pasa de rubro? Es una decisión de Martín, sección 12.
10. "Mostrame notebooks" → "de esas, la más liviana" cuando se mostró una
    muestra: el grupo es la búsqueda entera, no las cinco filas.
11. "El de 37 mil" cuando dos renglones cuestan 37 mil: se pregunta.
12. "¿Y ese es inalámbrico?" sobre un producto de hace cuatro turnos,
    habiéndose mostrado otros después: deíctico que apunta al último, y si no
    es claro, se pregunta.

---

## 7. El tablero y la biblioteca

**El tablero** es la lista hecha visible al modelo en la primera llamada. **La
biblioteca** es la parte de la lista que no entra en el tablero y se abre cuando
hace falta.

El tablero lleva cinco partes:

1. **La gramática**, capas 1 y 2. Fija.
2. **El índice de la tienda**, capa 3: entera si cabe; si no, el primer nivel.
3. **La memoria**, M1 a M6.
4. **La lectura del código**: lo que el código reconoce seguro en el mensaje
   —destinos, porcentajes, montos, productos que existen—. Hoy ya existe como
   el anticipo de `agente.faltantes`.
5. **El mensaje.**

**La biblioteca, en niveles.** Para una tienda grande:

- en el tablero van las **secciones** —computación, audio, hogar—;
- **abrir sección** trae sus rubros;
- **abrir rubro** trae sus datos, con clase y valores;
- **abrir tema** trae el texto entero de un tema de la FAQ; con muchos temas,
  el tablero lleva sus títulos agrupados.

**Los productos nunca van al tablero.** Los trae el motor al ejecutar. Por eso
el tablero tiene un techo fijo, sea cual sea el tamaño del catálogo. Una
tienda chica como esta entra entera y casi no abre libros; una grande abre uno
o dos. Es el mismo diseño.

---

## 8. El recorrido de un turno

**Paso 0, una vez por tienda, al cargar.** La ingesta ordena la prosa en datos
y el código genera la capa 3 en niveles.

**Paso 1, entra el mensaje.** El backend fija la tienda. El código hace su
lectura y arma M1 a M6. Todavía no hay modelo.

**Paso 2, el modelo traduce.** Es la estación T2 del mapa: el modelo declara.
Con el tablero delante escribe la traducción: una lista de **piezas**, cada una
con acción, cosas, datos del vocabulario, referencias a la memoria y de qué
pieza depende. Si le falta el detalle de un rubro o un tema, abre ese libro y
recién después escribe.

**Paso 3, el código valida antes de ejecutar.** Como el lenguaje es finito, se
puede revisar:

- cada rubro, dato, valor, tema y marca existe;
- un orden se pide sólo sobre una medida;
- una condición usa un valor que la fuente escribe;
- cada referencia resuelve a un id;
- las dependencias no forman un círculo.

Si algo no cierra, el código le devuelve al modelo el error puntual —"ese
valor no existe; los que hay son estos"— **una sola vez**. Si sigue sin
cerrar, esa pieza pasa a **preguntar al cliente** o a **no tengo ese dato**.

**Paso 4, el código ejecuta**, pieza por pieza y en orden: motor, tema,
envío, calculadora, reserva. Una pieza dependiente corre después y según el
resultado de la otra. Todo determinista.

**Paso 5, el modelo redacta** con lo que volvió. Es la estación T7. Siguen las
guardas de hoy: ninguna cifra que no haya salido de una herramienta, identidad
por id, plata de la calculadora.

### Un ejemplo completo

Turno anterior: el bot mostró tres auriculares, y el cliente dijo antes que es
de Rosario. Mensaje: *"el segundo lo tenés en blanco? y si no, alguno
inalámbrico que se pueda mojar de menos de 80 lucas. ¿Y si llega roto qué
hago?"*

- **Lectura del código**: monto 80.000.
- **Traducción**:
  - pieza 1: **nombrar**, referencia ordinal 2 de M1, variante color blanco;
  - pieza 2: **buscar**, depende de que la pieza 1 dé no: rubro auriculares,
    exigir conexión contiene "inalambrico", exigir resistencia_agua sí, exigir
    precio menor a 80.000, ordenar precio mínimo;
  - pieza 3: **mandar** a Rosario, destino tomado de M4, sobre lo que resulte
    de 1 o 2 —el cliente no lo pidió, así que es opcional y el modelo puede no
    escribirla—;
  - pieza 4: **política**, tema `defectuoso`, elegido leyendo qué contesta.
- **Validación**: todo existe, pasa.
- **Ejecución**: si el segundo no está en blanco y ninguno cumple la búsqueda,
  el motor dice qué condición falla y el bot lo dice así, con lo más cercano.

---

## 9. Cómo se obliga al modelo a usar el tablero

Por llamada de herramientas, y en dos fases:

1. **Primera llamada, con respuesta obligada a herramienta.** Las únicas
   herramientas visibles son `traducir` y las de abrir libro. Con la opción de
   herramienta obligatoria del proveedor, el modelo **no puede contestar texto**:
   o traduce, o abre un libro y después traduce. **Todo mensaje pasa por acá,
   también "hola"**, que se traduce como la acción charla. Un solo camino, sin
   bifurcación.
2. **El esquema de `traducir`** lleva lista cerrada sólo para lo chico y
   universal: las acciones, las fuerzas de una condición, las clases de
   referencia. **El vocabulario de la tienda no va como lista cerrada del
   esquema**: con una tienda grande no entra, y la FICHA 64 midió que meter los
   temas como lista obligatoria rompió ocho charlas. Se valida en el paso 3.
3. **Segunda llamada, de redacción, sin herramientas**, sólo con lo que volvió.

Lo que hay que medir en el paso 1 del plan, no suponer: que el endpoint
compatible del proveedor acepte la herramienta obligatoria, y cuánto tarda el
turno con dos llamadas más la apertura de libros.

---

## 10. Lo que no cambia

- La identidad la certifica el motor, con sus tres veredictos. Regla 10.0.
- La plata la calcula la calculadora.
- La tienda la fija el backend. El modelo nunca la elige.
- Las guardas de procedencia y de cifras.
- Un solo camino vivo: esto **reemplaza** al agente de la FICHA 62 en el
  turno, no va al lado ni detrás de un flag.

---

## 11. Riesgos, dichos de entrada

- **La FICHA 58 falló** porque el modelo tenía que escribir un esquema grande
  de una vez. Acá se diferencia en tres cosas: piezas chicas, valores vistos
  antes de escribir y una corrección puntual del código. Si alcanza, se sabe
  midiendo.
- **Latencia**: mínimo dos llamadas por turno, más las aperturas.
- **Costo**: el tablero es más largo que el prompt de hoy. A favor: la parte
  fija de hoy, de unos 1.650 tokens, no llega al mínimo del caché del
  proveedor y da cero; un tablero más largo y fijo probablemente sí llegue.
  Hay que medir ese mínimo.
- **Que el modelo abra libros de más.** Se cuenta cuántos abre por turno.

---

## 12. Decisiones de Martín

1. **El techo de tokens** del tablero y del turno.
2. **La exclusión entre rubros**: "que no sea Redragon" dicho en teclados,
   ¿vale cuando pasa a mouses?
3. **C37**, que viene de la FICHA 64: ante "tengo una notebook, qué memoria le
   sirve", ¿vale la repregunta del modelo de notebook, o tiene que mostrar
   memorias de notebook?
4. **El borrador del diccionario de campos**: se usa como punto de partida de
   la capa 3 o se rehace.

---

## 13. El plan, en pasos medibles

Un solo banco: la vara de las 58, con las piezas de `desmenuzar.CASOS`. No se
arma otro.

- **Paso 0 · La vara completa.** Se suman a la vara los sesenta y tres casos
  nuevos del punto 1 y los doce de memoria del punto 6, con casillas que no
  dependen de la redacción: si la fuente tiene un producto que cumple, la
  respuesta no puede decir que no hay; el tema servido incluye el que
  corresponde; si el valor pedido no existe, la respuesta lo dice. La sonda
  de esta sesión no entra al repo. Sin modelo.
- **Paso 1 · La gramática escrita.** Las capas 1 y 2 como un archivo de datos,
  único, y cada pieza de la vara etiquetada contra ella. Se mide cobertura:
  piezas que entran sobre el total. Cada pieza que no entra es un hueco de la
  gramática y se cierra antes de seguir. Sin modelo.
- **Paso 2 · La capa 3 generada**, con los temas y lo que contestan. Se miden
  sus tokens y el mínimo del caché.
- **Paso 3 · Traducir y validar, sin ejecutar.** En el clon, contra las piezas
  de la vara. Base de hoy: la interpretación da 61 a 62 de 68. Se mide
  también con los casos nuevos.
- **Paso 4 · Ejecutar y redactar.** Reemplaza al agente en el camino vivo.
  Tres corridas y la puerta.
- **Paso 5 · Producción**, con consulta del push, y prueba por WhatsApp
  leyendo el issue 31.

Cada paso en su propio commit. Si un paso no pasa, se revierte y se anota por
qué en esta ficha.

---

## 14. Primera medición, 29-sep: NO PASA, se revirtió

Se construyó el prototipo entero —traducir con herramienta obligatoria,
validar, ejecutar, redactar— y se midió por el clon con la clave paga pedida
por Martín. El código quedó en `archivo/tablero_ficha65_29sep/`: el módulo, el
parche que lo cableaba, sus veinte tests offline y los sesenta y tres mensajes
nuevos. El camino vivo quedó como estaba.

**Los sesenta y tres mensajes nuevos, tres corridas: mejora clara.** Se
arreglaron en tres de tres el parlante que se moja, el producto roto con su
tema, el combo con tope, el mouse inalámbrico que no sea negro, las marcas
excluidas, el SSD de 1 tera con sus cinco modelos y el pago mitad y mitad. El
monitor más grande pasó de afirmar 32 pulgadas a contestar bien o decir que no
puede ordenar por tamaño.

**La vara de las 58, tres corridas contra `v58_p_`: rompe más de lo que
arregla.** La puerta dio arregla 6, rompe 18. Respuesta 60, 59 y 60 contra 62,
61 y 63 de la base; interpretación 53 de 68 en las tres contra 61 y 62. El
turno pasó de unos 4.200 a unos 5.100 tokens y el caché siguió en cero.

**Por qué rompe.** Lo que rompió son dependencias y memoria: "si anda con Mac
me lo llevo", "si no hay en negro el blanco", "era para Córdoba, no Rosario",
"el primero", "ah no, el otro, y ese me lo llevo". La FICHA 59 ya había medido
que el modelo hace eso solo **dentro del bucle del agente**, porque ve el
resultado antes de decidir el paso siguiente. Traducir todo de una vez, antes
de ver nada, le saca justo esa capacidad. Es el mismo límite que cerró la
FICHA 58.

**Lo que sí sirvió** vive en la frontera de las herramientas, no en la fase
de traducción: el vocabulario de la tienda delante, el tema elegido por el
modelo, y el código revisando cada pedido contra la fuente —dato que no está
en el rubro, valor que el rubro no escribe, orden sobre una etiqueta, marca
excluida perdida, reparto en fracciones, rubro usado como producto, "no
tenemos" sin consultar—.

### La próxima iteración propuesta

**El bucle del agente se queda; la validación entra en cada llamada.** El
modelo sigue llamando herramientas y viendo resultados, como hoy. Lo nuevo:

1. el prompt fijo lleva el vocabulario de la tienda —rubros, temas con qué
   contestan y datos con su clase—;
2. `politica` recibe el tema que elige el modelo, y el código suma los suyos;
3. cada llamada se valida **antes** de ejecutarse con las mismas reglas del
   prototipo, y si no cierra vuelve como resultado de esa herramienta con lo
   que sí existe;
4. "no tenemos" lo confirma el catálogo, y una búsqueda sin orden dice que
   es una muestra.

Se mide igual: las 58 por la puerta y los sesenta y tres nuevos.
