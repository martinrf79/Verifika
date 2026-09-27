# FICHA 58 — La traducción en gramática: el tablero que cubre las 58 combinaciones

Escrita el 24 y 25-sep-2026, con Martín, sin tocar código. Es teoría: todavía
no se implementó nada. **El chat nuevo arranca por el paso 1 y define la
interpretación primero.** Los pasos 4 a 6 son opcionales: pertenecen a etapas
posteriores y no se empiezan hasta que la interpretación esté medida.

---

## 0. Por qué esta ficha

Hace días que el cableado termina en cascada. Las causas, leídas en el repo:

1. El contrato cambiaba seguido: la ficha del traductor tuvo siete versiones, y
   el motor todavía acepta "las dos formas".
2. Los parches iban en el medio: el código corregía después lo que el modelo
   escribía, y un parche rozaba con otro.
3. La medición mezclaba todo: no se sabía si falló el modelo o el código.
4. Convivían caminos: el traductor del banco no es el de producción.
5. Todo entraba de golpe a producción.

Cada paso de esta ficha responde a una de esas cinco.

## 1. El principio

- El modelo **traduce**: parte el mensaje, pone un verbo a cada pieza, copia
  palabras y pasa la jerga al idioma de la ficha. Nunca juzga si algo es cierto.
- El código **verifica y decide**, con veredictos de lista cerrada.
- El modelo sólo usa su cabeza para el idioma, y para el saber general en
  piezas con el verbo explicar. Los datos de la tienda, nunca.
- Lo único infinito son las palabras del cliente. El modelo las copia; el
  código las compara contra la fuente, que es finita.

## 2. La gramática

Salida del modelo: una lista de piezas, en el orden del mensaje. Cada pieza:
número, lo que dice copiado, verbo, objeto, marca o palabra copiada, fuerza,
dueño, cantidad, y las palabras copiadas que forman los enlaces.

- **Verbos:** nombrar, buscar, condicionar, preguntar, dar por cierto, ordenar,
  mandar, consultar a la casa, comprar, quitar, sumar, repartir el pago,
  explicar. Salidas: charla y otro.
- **Objetos:** producto, rubro, memoria, casa, cliente, saber general.
- **Fuerzas:** exige, prefiere, rechaza, lo menos posible.
- **Dueños de lo dado por cierto:** tienda, producto, lo suyo, sí mismo.
- **Enlaces, siempre copiando palabras, nunca números de pieza:**
  - alcance: a qué va, "el teclado" o "todo".
  - dependencia: la palabra que la dispara, "si no hay", "si pasa de".
  - referencia: lo que apunta, "ese", "el segundo", "el de antes".
  - corrección: "ah no", "mejor".
  El código arma el enlace con lo copiado y con el orden de las piezas.
- **Las siete reglas:** copiá y no juzgues; una pieza por pedazo, por producto o
  rubro y por destino; si hay marca usala, si no copiá la palabra; nunca
  escribas un dato de la tienda; lo afirmado va como dar por cierto aunque sea
  falso, y una pregunta nunca lo es; si no sabés a qué apunta, sin destino;
  lo que no entra, otro.

## 3. Las 58 combinaciones

La numeración es abierta: un caso nuevo se agrega al final.

**A. Base.** 1 nombrar "¿tenés el G305?". 2 buscar "¿qué parlantes tenés?".
3 nombrar y preguntar "¿cuántos DPI tiene el G502?". 4 nombrar y dar por
cierto "el K120, que es inalámbrico". 5 exigir "notebook con 16 GB de RAM".
6 preferir "preferentemente Sony". 7 rechazar "que no sea Genius". 8 lo menos
posible "lo menos chino posible". 9 ordenar "el monitor más barato". 10 mandar
"¿cuánto a Posadas?". 11 casa "¿hacen factura A?". 12 tienda falsa "tienen 50
por ciento off". 13 sí mismo "soy revendedor". 14 explicar "¿DDR4 o DDR5?".
15 comprar "me llevo dos G305". 16 repartir "70 transferencia, 30 Mercado Pago".

**B. Multipregunta.** 17 varios productos con distinto verbo. 18 productos y
mandar. 19 productos y casa. 20 productos y sumar. 21 sumar y repartir.
22 tienda y saber general.

**C. Alcance.** 23 condición a una sola pieza. 24 condición a todas.
25 cantidad por pieza. 26 destino por pieza. 27 ordenar dentro de un grupo dado.

**D. Dependencia.** 28 si no hay, esto otro. 29 si da sí, comprar. 30 si el
cruce da no, alternativa. 31 si el total pasa un monto, quitar. 32 comparar
dos y elegir.

**E. Corrección.** 33 en el mismo mensaje. 34 de otro turno. 35 cambiar una
condición vigente.

**F. Dueños.** 36 lo suyo con un producto: cruzar. 37 lo suyo con un rubro.
38 lo suyo sin el dato que el cruce pide. 39 dato falso de producto. 40 dato
falso de la tienda. 41 sí mismo pidiendo un permiso. 42 condiciones imposibles
juntas.

**G. Memoria.** 43 "ese" o posición. 44 "el otro". 45 modificar la búsqueda
anterior. 46 heredar una condición vigente. 47 dato del cliente dicho antes.
48 destino o pedido anterior. 49 referencia lejana por nombre parcial.
50 respuesta a una repregunta. 51 a otra pieza del mismo mensaje. 52 sin destino.

**H. Cadenas.** 53 memoria con dependencia. 54 lo suyo con dependencia y orden.
55 memoria, corrección y compra. 56 multipregunta con dato falso y compra
condicional.

**I. Lo que no entra.** 57 otro. 58 charla mezclada con pedido.

Cruza a todas: el idioma desprolijo, la cantidad y el uso ("para la oficina").

**Salidas cuando falta algo**, veredictos del código y no traducción: no
existe, no figura, no hay campo, no está escrito, falta un dato del cliente,
ambiguo, no entendí. Una sola repregunta por mensaje; queda pendiente en la
memoria para entender la respuesta.

## 4. El tablero: estático, en cuatro partes

Estático porque la tienda de hoy entra entera, se arma una vez y va en caché.

- **A. La gramática.** Sirve para cualquier proyecto. Con unos diez ejemplos
  cortos sacados de las 58, sobre todo de enlaces y memoria.
- **B. El vocabulario del comercio electrónico.** Sirve para cualquier tienda:
  conceptos universales, medios de pago, palabras gatillo.
- **C. La tienda.** Generada de la fuente, nunca a mano: rubros, conceptos con
  su etiqueta y unidad, los valores de los conceptos que tienen pocos, marcas,
  nombres de los temas de la FAQ, equipos y conectores del cliente.
- **D. La charla.** Lo único que cambia por turno: la libreta numerada y el
  mensaje.

**Queda afuera a propósito:** modelos, precios, stock y texto de la FAQ. La
identidad y los datos los resuelve el código.

**Tamaño estimado, a medir:** entre 2.600 y 3.000 tokens en total, casi todo
fijo. Si la parte C de otra tienda pasa de unos 2.000 tokens, se manda sólo lo
de los rubros que el mensaje nombra; A, B y D no cambian.

**Contra el carácter mal escrito:** las listas cerradas del esquema salen del
mismo archivo que el tablero, y un test compara el tablero con la fuente.

## 5. Los componentes de la interpretación

Antes del modelo: el **índice** fuera del turno, el **marcador** que marca en
el mensaje lo que reconoce, la **libreta** con la memoria numerada y la
gramática. El **traductor** es el modelo. Después: el **validador** es la
puerta única; el **coordinador** arma los enlaces con lo copiado; el
**resolvedor** cambia cada referencia por un id o un dato; el **rescatador**
busca lo que no tuvo marca y, sólo si empata, hace una llamada chica con los
candidatos.

Al modelo sólo le dan datos el tablero, la libreta y, en la llamada chica, el
rescatador. Con un catálogo diez veces mayor crece el índice, no lo que lee el
modelo.

La salida de la interpretación es el **pedido encaminado**: piezas con verbo,
destino certificado, condiciones llevadas a un campo, enlaces y orden. **El
pedido que recibe el motor no cambia de forma:** no hay adaptadores nuevos.

## 6. Los seis pasos

**Interpretación — se hace primero:**

1. **Las 58 escritas a mano:** mensaje y piezas correctas. Sin código. Se
   congelan antes de todo lo demás.
2. **El tablero y el marcador:** el tablero generado de la fuente, el marcador,
   y su prueba sin el modelo.
3. **La gramática y el validador,** más la primera medición del modelo contra
   las 58, peor de tres, con la clave gratis. **Primer corte:** si no llega al
   piso, por ejemplo 50 de 58, se para y se pasa al curso sencillo, antes de
   construir nada más.

**Opcionales — etapas posteriores, sólo si la interpretación pasó el corte:**

4. **Opcional.** Coordinador, resolvedor y rescatador, con prueba sin el
   modelo: piezas correctas, pedido, motor, veredictos.
5. **Opcional.** El camino nuevo entero en el banco contra el de hoy, en las 58
   y en mensajes reales que no se usaron para diseñar: el oro de la traducción,
   el oro del buscador y la vara de charlas. **Segundo corte:** si no gana, no
   se deploya.
6. **Opcional.** Paso a producción en un solo commit que borra lo viejo, y
   prueba por WhatsApp.

Los dos pisos se fijan en un commit propio antes del trabajo.

## 7. Reglas contra la cascada

- El contrato se congela primero; cambiarlo es un paso propio.
- El código y el modelo se prueban por separado: si fallan las piezas escritas
  a mano, es del código; si falla el mensaje contra las piezas, es del prompt.
- Si un caso sigue rojo después de dos arreglos, se revierte y se para.
- Reemplazar y borrar van en el mismo commit.
- Nada llega a producción antes del paso 5.

## 8. El curso sencillo, si el corte del paso 3 falla

El modelo escribe sólo piezas con verbo, sin enlaces. El alcance lo decide el
código por el orden; la dependencia se resuelve ejecutando las dos ramas y
dejando elegir al redactor; en la corrección gana la última palabra. Sigue
cubriendo las 58, con menos precisión en 28 a 32.

## 9. Lo que dice el estado del arte, septiembre de 2026

- El patrón neurosimbólico, el modelo como traductor y un motor determinista,
  es el dominante. Esta ficha es eso.
- La **capa semántica** es lo que más rinde: un benchmark de dbt Labs subió de
  84 a 100 por ciento de acierto al consultar contra una capa semántica en vez
  de la base cruda. El tablero es nuestra capa semántica y sirve para otros
  proyectos.
- Para sumar, sin infraestructura nueva: **esquema dinámico por mensaje**,
  con las listas cerradas armadas con las marcas del turno, en el paso 3;
  **memoria con vigencia**, cada dato vigente, reemplazado o contradicho, en el
  paso 4; **embeddings en el rescatador**, que el repo ya probó.
- **Opcional, después del paso 3:** optimizar el prompt con DSPy y GEPA contra
  las 58. Suma la dependencia `dspy` sólo en el banco, y se avisa antes.
- Se miró y no conviene ahora: GraphRAG completo, decodificado restringido
  sobre listas enormes con modelo propio, y los sistemas de memoria de agentes
  como producto.

Fuentes: aclanthology.org/2026.semeval-1.186 · arxiv.org/pdf/2604.25149 ·
cube.dev/articles/semantic-layer-for-ai-agents-2026 · arxiv.org/abs/2601.16492 ·
arxiv.org/html/2601.04426 · dspy.ai/tutorials/gepa_facilitysupportanalyzer ·
arxiv.org/html/2501.13956v1

## 10. Lo que falta conseguir

1. Las 58 escritas a mano: es el paso 1.
2. Más charlas reales: son el control contra aprender sólo los ejemplos.
3. El permiso para `dspy`, sólo si se hace el opcional de la sección 9.
