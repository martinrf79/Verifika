# FICHA 93 — La llamada 1 con candidatos: separar, traducir y elegir de lo que la tienda tiene

10-nov-2026, sesión con Martín. Sigue a la FICHA 92, paso 1 hecho. **Esta ficha se escribió para que una sesión nueva
pueda seguir sin volver al chat:** tiene lo medido, los archivos, los comandos, los errores caso por caso, las
herramientas con lo que ya se midió de cada una, y los pasos con su corte.

---

## 1. La idea, de Martín, en sus palabras ordenadas

La respuesta se arma por capas. La primera capa es la llamada 1, y tiene que ser una base firme:

1. **El modelo separa el mensaje y hace la primera traducción, desde el punto de vista del cliente.** Nada más que eso
   sale de su cabeza: no elige acciones del código, no pone ids, no calcula.
2. **El modelo recibe candidatos.** Lo que la tienda tiene y puede ser lo que el cliente dice: productos, rubros,
   temas de la FAQ, órdenes, lo ya mostrado y el pedido. Elige de ahí o dice "ninguno". La fuente de verdad es doble: la
   del repo, `data/clientes/<tienda>/`, y la del cliente, lo que dijo en la charla.
3. **El modelo recibe la forma de respuesta de la tienda.** La lista cerrada de lo que Verifika sabe hacer, cada cosa
   con una línea de qué necesita. El modelo pone cada línea del cliente en una de esas formas, o en "preguntar".
4. **Las dos listas se arman compatibles con el entrenamiento del modelo:** castellano llano, nombres naturales,
   descripciones cortas, esquema JSON con opciones cerradas, pocos ejemplos.
5. **Los candidatos no los puede armar solo el código cuando el mensaje es razonamiento.** "Rectángulo con teclas",
   "de acuerdo a la crisis", "los más económicos de cada clase", "algo parecido": ahí no hay palabra que buscar. Para eso
   están los embeddings y Jev. Qué parte hace cada uno se define y se mide en esta ficha.
6. **Se arregla primero con lo ya grabado, sin correr modelos.** Cuando la llamada 1 esté, más pruebas, y lo que vaya
   apareciendo se resuelve por clase.

Lo que Martín no quiere: un parche por caso, más campos por cada falla, el agente suelto sin atar, o una sesión
nueva que no sepa de dónde seguir.

---

## 2. Lo medido el 10-nov: la llamada 1 que solo separa y traduce

### El instrumento

`banco_pruebas/separar_charlas.py`, commit c7b68c9. Los resultados en `banco_pruebas/separar_charlas.jsonl`, una
línea por caso con `etiqueta`, `charla`, `turno`, `forma`, `texto` y `salida`. Etiquetas: `base` es la corrida del
mensaje original; `formas` es la de las cinco formas grabadas de cada mensaje.

```bash
python3 banco_pruebas/separar_charlas.py --etiqueta base                       # corre lo que falta y califica; reanuda
python3 banco_pruebas/separar_charlas.py --formas --etiqueta formas --a-la-vez 3
python3 banco_pruebas/separar_charlas.py --calificar --etiqueta base --ver     # solo califica lo grabado, sin modelo
```

- **El modelo:** el de producción, `settings.GEMINI_MODEL`, por la clave gratis `GEMINI_API_KEY` y el cliente OpenAI en
  `settings.GEMINI_BASE_URL`, temperatura 0, `response_format` con el esquema `FORMATO`.
- **La consigna:** `CONSIGNA` en el script. Es la de la FICHA 83, `momento0.LINEAS_TEMA` con su `MEMORIA`, copiada
  porque `momento0.py` usa funciones del intérprete borradas el 30-oct. Cada línea tiene `texto`, `cosa`, `tema`,
  `cantidad`, `destino`, `si`, `modo` y `senala`, más un `todo` para lo que vale para todo el pedido.
- **Lo que se sumó a la FICHA 83:** `modo`, con cuatro valores cerrados: pregunta, ver, llevar, dato. Y `senala`, el
  número de la libreta cuando el cliente habla de algo ya mostrado, del pedido o de lo que preguntó el vendedor.
- **La libreta:** `libreta(estado, historial)`. M-n lo mostrado con nombre y precio, numerado por `interprete.numeros`;
  L-n los renglones del borrador; R-n lo que preguntó el vendedor; y los dos últimos mensajes. Se arma turno por turno
  corriendo los turnos anteriores por `camino_fijo.py` con su agenda a mano: es la libreta real de ese momento.
- **La vara:** `_quiere(agenda)` saca de la agenda a mano, `agendas58.py`, lo que pide el cliente en el turno; `_es`
  decide si alguna línea lo trae. Mide la información, no la forma: el rubro por `catalogo.solo_rubro` y
  `catalogo.rubro`, el modelo por `catalogo.identificar`, el número M o L en `senala`, el tema, el destino y la
  cantidad. Una lista de M exige señalar al menos dos: "y ese cuánto" entre varios se deja abierto, no se adivina.

### Los números

| Corrida | Resultado |
| --- | --- |
| `base`, mensaje original, 138 turnos de las 58, las J y las K | **125 de 138** |
| · C primeros turnos | 57 de 58 |
| · C con charla | 19 de 20 |
| · J | 9 de 10 |
| · K primeros turnos | 19 de 21 |
| · K con charla | 21 de 29 |
| `formas`, las cinco formas, hasta donde dio la cuota gratis del día | 258 de 525 grabadas |
| · de esas, las que contestó el modelo, todas C | **183 de 184** |
| · sin respuesta por el 429 de la cuota diaria | 74, más 9 de la vuelta de reintento |

**Para completar las formas:** correr de nuevo el comando de `--formas` con la gratis otro día. Reanuda: lo que dio
error no cuenta como hecho. Faltan todas las J y las K, que son las difíciles.

**Lo que dice:** separar y traducir desde el cliente el modelo lo hace bien casi siempre. Lo que falla está casi todo en
las K con charla, donde hay que razonar sobre el pedido o sobre la tienda entera.

---

## 3. Los 13 que fallan en `base`, caso por caso, con lo grabado

Salen de `--calificar --etiqueta base --ver`. Para cada uno: lo que dijo el cliente, lo que devolvió el modelo, la
clase y qué lo arregla. **Ninguno se arregla cambiando la vara ni sumando una palabra a una lista.**

| Caso | El cliente | Lo que devolvió el modelo | Clase | Qué lo arregla |
| --- | --- | --- | --- | --- |
| C52 T2 | "y ese cuánto?" con doce mostrados | pregunta por M-10, adivinado | modelo adivina | Código: "ese" con varios mostrados se deja abierto y el código pregunta; o la forma "preguntar cuál" en la lista |
| K10 T8 | "el envío va a Rosario, cuánto me queda?" con pedido abierto | `dato`, "el envío va a Rosario", sin señalar renglón | forma de respuesta | La forma "cambiar el destino del pedido" en la lista; con pedido abierto, un destino nuevo es eso |
| K16 T3 | "mejor volvé a ponerlo, y mandalo todo a Rosario" | `dato` "manda todo a Rosario"; el teclado como L-1 sin decir K120 | forma de respuesta | Igual que K10; y "volver a ponerlo" necesita en la libreta lo que se sacó |
| K21 T3 | "los más económicos de cada clase" con cuatro clases en el pedido | solo dos líneas, teclado y mouse | razonamiento | Código: "cada clase" se expande a los rubros del pedido; Jev midió 11 de 11 en esto |
| K21 T2 | "son 7 artículos, el teclado va a Concordia, lo demás está bien" | una sola línea, el teclado | razonamiento y vara | El "lo demás está bien" no cambia nada; revisar si la agenda a mano pide de más |
| K01 T1 | "los dos más baratos de la tienda y los dos más caros" | lo toma como tema `precios_iva`; inventa dos preguntas de pago y descuento | forma de respuesta | La forma "ver la tienda entera ordenada" no existe en la lista; con ella, es elegir |
| K18 T1 y T2 | "el artículo más caro que vendés", "y el más barato?" | pregunta sin cosa ni forma | forma de respuesta | La misma: "ver la tienda entera ordenada" |
| C41 T1 | "soy jubilado, tienen descuento?" | tema `promociones` | tema de la FAQ | Candidatos de temas por Jev o embeddings; la agenda espera `descuento_transferencia` |
| K13 T2 | "está muy cara, en otro lado la consigo más barata, mejorame el precio" | dos preguntas sin tema | tema de la FAQ | Candidatos de temas: regateo es `promociones` |
| K13 T3 | "y si te llevo dos me hacés precio?" | tema `promociones` | tema de la FAQ | Candidatos de temas: la agenda espera `mayoristas`. Ojo: Jev marcaba de más las reglas con umbral |
| K12 T2 | "y algo parecido?" después de ver una tablet | ver "algo parecido a celulares" | nexo | Código: "parecido" sin cosa es el rubro de lo último mostrado |
| J07 T1 | "el bicho ese para que ande el wifi en toda la casa" | cosa "repetidor wifi" | vara o nexo | El modelo tradujo bien; el rubro de la tienda es router. Lo resuelve el candidato del rubro |

En las formas, de las 184 contestadas falló una: C32 redactada, "de estos dos, el G203 y el G305, dame el
inalámbrico". El modelo eligió el G305 por su cuenta. Es razonamiento dentro de la llamada 1, lo que no se quiere: la
condición "inalámbrico" va en `si` y la decide el código con la ficha.

**Por clase:** forma de respuesta 4 casos, código y nexo 4, tema de la FAQ 3, vara 2.

---

## 4. Las herramientas para los candidatos, con lo que ya se midió de cada una

### El código, lo exacto y lo del estado

- `app/core/flujo/catalogo.py`: `identificar(texto, color, tienda)` da `exists`, `ambiguous` o `not_found` con el
  producto y sus variantes; `solo_rubro` y `rubro` llevan una palabra a un rubro por alias; `atar` lleva una condición
  a un campo de la ficha.
- `app/core/flujo/normal.py`: `lugares(texto)` encuentra destinos; `orden_que_no_dijo` controla el orden con
  `orden_cita`.
- `app/core/flujo/interprete.numeros(estado)` y `borrador.leer`: los números M, L y R de la libreta.
- `app/core/flujo/marcador.RESPUESTAS["ordenes"]`: el vocabulario de órdenes, FICHA 82; "de acuerdo a la crisis" es
  más barato. Cada tienda lo cambia en su `alias.json`.

**Sirve para:** lo nombrado, como modelos, marcas, rubros con su nombre y destinos, y todo lo que depende del estado:
qué hay en el pedido, qué se mostró último, qué preguntó el vendedor.

**No sirve para:** lo dicho por rodeo o por razonamiento.

### Los embeddings, lo dicho con otras palabras

- Ya están en el bot: `agente._vectores`, `agente._base` y `agente._parecidos`, por la puerta nativa de Google,
  `settings.EMBEDDING_MODEL = "gemini-embedding-001"`, con tipo de tarea `RETRIEVAL_QUERY` y `RETRIEVAL_DOCUMENT`,
  vectores en memoria y pausa de 120 s si se caen. Hoy solo buscan temas de la FAQ, con `UMBRAL_TEMA = 0.70`.
- Medido el 29-oct: el rubro correcto da cerca de 0,78 y el ruido de 0,65 a 0,74. Separan, pero con poco margen.
- Medido en la FICHA 82, 26-oct, `banco_pruebas/candidatos82.py`: los parecidos por embeddings suman poco cuando la
  base ya está bien cubierta, de 3 a 5 por parte. Lo descartado: reemplazar lo propio de la tienda por su tipo antes del
  embedding empeora.

**Sirve para:** temas de la FAQ dichos con otras palabras, y como un canal más de rubros.

**No sirve para:** razonar. "Los dos más baratos de cada clase" no se parece a ningún producto.

### Jev, el clasificador que elige de listas cerradas y no escribe

- Es de TypeSafe AI. Recibe un texto y preguntas con opciones cerradas, y devuelve cada opción con su probabilidad.
  API `https://api.typesafe.ai/v1/systemone`, modelo `jev-latest`, clave `TYPESAFE_API_KEY`, que está en el entorno.
  Tipos de pregunta: `choice`, con criterios por opción, y `noul`, sí o no con probabilidad. Lee hasta unos 120.000
  tokens y tarda menos de un segundo. Precio de octubre: 0,042 dólares por millón de tokens de entrada, salida gratis.
- El código de cómo llamarlo y el índice en niveles están en `banco_pruebas/jev/`: `fuente.llamar`,
  `fuente.preguntas_jev`, `indice_jev.nivel1` y `nivel2`, `calibrar.py`. Cada llamada anota su gasto en
  `gasto_jev.jsonl`. Detalle completo en la FICHA 75 y en `banco_pruebas/jev/LEEME.md`.
- Medido el 22-oct, FICHA 75:

| Prueba | Resultado |
| --- | --- |
| Rubro desde el mensaje crudo, 525 casos en cinco formas | 480 de 485 |
| Producto nombrado entre los 5 primeros | 255 de 260 |
| Condición vaga al campo de la ficha: "luces psicodélicas", "sin cablerío" | 33 de 34 |
| Rubros que no se nombran y salen de la charla, "de cada clase" | 11 de 11 |
| Respuesta corta a una pregunta del bot: "el del medio", "ninguno" | 64 de 64 |
| Mensajes sin pedido, sin marcar nada | 12 de 12 |

- **Lo que hizo mal:** marca de más las reglas con umbral; números que no son precio; partir pedidos con varios
  destinos; una opción ambigua se marca en todo. No parte el mensaje, no calcula, no escribe.
- **La lección que manda:** como contexto en todos los mensajes, Jev empeoró. En las siete charlas reales bajó de 15 a
  9 de 21: en turnos cortos y de memoria metía ruido. **Jev no va en todos los mensajes:** va solo para las partes que
  el código no pudo atar, y lo que trae lo valida el código contra la fuente.

---

## 5. La llamada 1 que se propone

Dos pasos del modelo y uno del código en el medio. Ninguno escribe al cliente.

### Paso A, el modelo separa y traduce

Es lo medido en el punto 2, con la consigna de `separar_charlas.py`: 125 de 138 y 183 de 184. No cambia, salvo lo que
salga del punto 3.

### Paso B, el código arma los candidatos de cada línea

Por cada línea del paso A, en este orden, y se para en el primero que ata:

1. **Lo del estado:** si `senala` trae M, L o R, el código lo resuelve con `interprete.numeros` y `borrador.leer`. Si
   la línea no señala y hay un pedido o un mostrado al que puede referirse, se suman como candidatos.
2. **Lo exacto:** `catalogo.identificar` sobre `cosa`, `solo_rubro` sobre `cosa`, `lugares` sobre `destino`, el
   vocabulario de órdenes sobre `todo` y `texto`.
3. **Lo dicho con otras palabras:** embeddings de la línea contra los temas de la FAQ y contra los rubros, los tres
   primeros de cada uno por encima del ruido medido.
4. **Lo que necesita razonar:** Jev, solo si los tres anteriores no ataron nada o no coinciden. Con el índice en
   niveles, no con la fuente entera: nivel 1 rubros y temas, nivel 2 los campos y productos del rubro.
5. **Si los canales no coinciden**, la línea queda dudosa con todos sus candidatos.

### Paso C, el modelo elige, con dos listas cerradas

Recibe sus líneas, los candidatos de cada una y la forma de respuesta de la tienda. Por cada línea devuelve una forma de
la lista y un candidato de los que recibió, o "ninguno" o "preguntar". **No puede devolver nada que no esté en las
listas:** el esquema JSON lo impide con enum armados por el código en cada turno.

**La forma de respuesta de la tienda** sale de `agenda.ACCIONES`, que es lo que el código sabe cumplir, dicha en
palabras del cliente. Las que faltan y se suman según el punto 3:

| Forma | Qué necesita | Sale de |
| --- | --- | --- |
| ver opciones de un rubro | un rubro; cantidad, orden y condiciones si las dijo | buscar |
| ver la tienda entera ordenada | el orden y cuántos | buscar con rubro "toda la tienda"; **nueva**, K01 y K18 |
| preguntar por un producto | un producto o un M; qué quiere saber | producto |
| si anda con algo | un producto y con qué | compatibilidad |
| llevar | un producto, un M o un rubro; cantidad, color, destino | comprar agrega |
| sacar | un L | comprar saca |
| cambiar un renglón | un L y lo nuevo: cantidad, color o destino | comprar cambia |
| cambiar el destino del pedido | el destino | comprar cambia sobre todos los L; **nueva**, K10 y K16 |
| cuánto sale el envío | el destino | envio |
| una regla de la tienda | un tema de la FAQ | politica |
| sumar o presupuesto | tope y reparto del pago si los dijo | cuenta |
| un dato suyo | nombre o dónde vive | otro, cliente |
| saber general | la pregunta | explicar |
| preguntar cuál | los candidatos | el código pregunta; C52 |

### Por qué así

- **El modelo no razona sobre datos de la tienda que no ve:** elige entre lo que el código le trajo.
- **El código no adivina lo que dijo el cliente:** lo dice el modelo en su idioma, en el paso A.
- **Lo que ninguno resuelve no se inventa:** va a "preguntar".

---

## 6. Lo que dice la investigación, con su año

| Fuente | Año | Qué aporta |
| --- | --- | --- |
| Adaptar los esquemas de herramientas a modelos chicos, arXiv 2510.07248 | octubre de 2025 | Nombres y descripciones naturales, opciones cerradas: los modelos chicos eligen mejor |
| LLM-Guided Attribute Graphs, arXiv 2604.27410 | abril de 2026 | El modelo propone candidatos y alias, el código los valida contra la base: no entra nada que no exista. Es el paso B con Jev |
| Multi-Perspective Evidence Synthesis, arXiv 2604.20283 | abril de 2026 | Varios canales de búsqueda sumados en un solo pozo de candidatos, y un modelo que reordena |
| Select, Don't Train, arXiv 2608.27470 | agosto de 2026 | Elegir con un modelo entre candidatos, por módulos, sin entrenar: es el paso C |
| Despliegue de comercio electrónico en SIGIR | 2026 | Búsqueda densa para los candidatos y un modelo que los ordena con atributos estructurados |
| FnCTOD, el estado del diálogo como llamada a función | 2024 | El estado de la charla se llena con funciones de esquema fijo |
| Rasa CALM | 2024 | El modelo emite comandos; el código cumple los flujos |

---

## 7. Los pasos, con su corte escrito antes

Cada paso se mide antes de pasar al siguiente. **Los cortes no se mueven después de ver el número.**

1. **Sin modelo, lo del código del punto 3:** C52, K10, K16, K21 T3 y K12. Se prueba sobre las salidas ya grabadas
   en `separar_charlas.jsonl`, sin llamar a nadie.
   - Corte: los cinco casos cubiertos por clase, no por palabra, y 0 casos de `base` que empeoren.
2. **Sin modelo, el pozo de candidatos del paso B:** sobre los 138 turnos de `base`, con las líneas grabadas, medir si
   el candidato correcto está en el pozo, por canal y sumado. Sale un instrumento nuevo, `banco_pruebas/candidatos93.py`.
   - Corte: el correcto está en el pozo en al menos 134 de 138 turnos. Lo que no esté se clasifica antes de seguir.
   - Embeddings con la gratis; Jev con su clave, gasto anotado, tope de 0,10 dólares por corrida.
3. **Con la gratis, el paso C:** el modelo elige con las dos listas, sobre los mismos 138.
   - Corte: más que 125 de 138, y ninguno de los 125 que hoy pasan empeora. Tres corridas, por la variación.
4. **Completar las formas** del paso A cuando haya cuota: las 525, con J y K. Si baja de 183 de 184 en lo que ya
   corrió, se para.
5. **Con todo medido, el cableado:** `camino_fijo.turno_fijo` pasa a `app/core/flujo/turno.py` con la llamada 1 nueva
   y reemplaza al bucle del agente si lo supera en las mismas charlas. El techo de `app/` baja de 8776. Eso es la
   FICHA 92, paso 3.

---

## 8. Lo que no se hace

- Jev en todos los mensajes: ya se midió que empeora.
- Que el modelo elija algo que no esté en las listas, o que razone sobre la ficha en el paso A, como en C32.
- Cambiar `agendas58.py` o la vara de `separar_charlas.py` para que pase un caso. Si una casilla está mal, se consulta
  a Martín.
- La clave paga. Todo con la gratis; Jev con su clave y tope.
- Meter a Fable 5.2 en el repo o en el bot: es caro y es un modelo general. Sirve, si Martín quiere, para pedirle un
  plan de arquitectura afuera, con esta ficha y las 75, 82, 83 y 92 como evidencia.

---

## 9. Dónde está cada cosa

| Qué | Dónde |
| --- | --- |
| La llamada 1 de hoy, su consigna, la libreta y la vara | `banco_pruebas/separar_charlas.py` |
| Lo que devolvió el modelo, `base` y `formas` | `banco_pruebas/separar_charlas.jsonl` |
| Las agendas a mano, la vara de lo correcto | `banco_pruebas/agendas58.py` |
| El camino fijo que arma la libreta de cada turno | `banco_pruebas/camino_fijo.py` |
| Lo que tradujeron seis modelos en cinco formas | `banco_pruebas/traduccion58_corridas.jsonl` |
| La traducción grabada por el camino fijo, Gemini 454 de 525 | `banco_pruebas/camino_grabadas.py` |
| La forma de respuesta de hoy | `app/core/flujo/agenda.ACCIONES` |
| Los embeddings | `app/core/flujo/agente._vectores`, `_parecidos` |
| Jev, su llamada, su índice y lo medido | `banco_pruebas/jev/`, FICHA 75 |
| Los candidatos por parecido y el vocabulario de órdenes | FICHA 82, `banco_pruebas/candidatos82.py` |
| La consigna de líneas de la que sale esta | FICHA 83 |
| El plan por capas | `arquitectura/PLAN_CAPAS.md`, FICHA 92 |
