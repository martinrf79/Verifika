# FICHA 97 — La llamada 0 de tres campos, el nexo de rubro y el flujo de punta a punta

15-nov-2026, sesión con Martín. Sigue a la FICHA 95 y a la FICHA 96, el contrato. **Escrita para que una sesión nueva
siga sin volver al chat.** Lo hecho, en `git log` del 15-nov.

---

## 1. Lo que decidió Martín

1. **La llamada 0 hace lo que el modelo hace de cabeza:** separa el mensaje en una línea por cosa, traduce cada producto
   al nombre común y marca el lugar de envío. Tres campos: fragmento, búsqueda y destino. Nada de cantidad, plata, orden
   ni condiciones: eso sale después del fragmento, por código, embeddings o Jev.
2. **Los embeddings van sobre lo que tradujo el modelo**, no sobre las palabras del cliente ni la fusión de los dos.
   Cuando el modelo no sabe una jerga la deja como la dijo el cliente, y los embeddings la llevan al rubro.
3. **El flujo y el contrato son los de la FICHA 96**, ya en código en el banco.
4. **El reordenador de Google se descartó** por complejidad. El umbral de puntaje sigue prohibido.
5. **Para lo dudoso, Jev o una llamada corta del modelo:** sin decidir. Se mide uno contra otro.
6. **La regla para que la llamada 0 no crezca:** un campo nuevo entra solo si se mide que el texto suelto falla, y solo
   si es de copiar, como el lugar. Nunca uno de razonar.
7. **Las respuestas a Martín, cortas y sin paréntesis:** usa lector de voz. Se le muestra la evidencia antes de proponer.

## 2. Lo medido

Dos bancos de 70 mensajes, primer mensaje de la charla, con la vara escrita antes:

- `banco_pruebas/nuevas70.py`, el de la FICHA 94.
- `banco_pruebas/nuevas70b.py`, nuevo: jerga más dura, rodeos largos, audio pasado a texto, inglés, marcas como nombre
  común, errores de tipeo, multipreguntas con destinos y preguntas de la tienda, y 14 cosas que la tienda no vende.

### La llamada 0, Gemini de producción por la clave gratis

| Versión | Qué pide | Rubros con el primero | Destinos | Inventa |
| --- | --- | --- | --- | --- |
| v2 | siete campos | 111 de 112 | 15 de 15 | 0 |
| v1 | fragmento y búsqueda | 112 de 112 | 12 de 15, el código sobre el texto | 7 |
| **la de tres campos** | fragmento, búsqueda y destino | **112 de 112; 75 de 76** | **15 de 15; 32 de 33** | **0** |

- Con los tres primeros rubros, el pedido está en 76 de 76 y en 112 de 112.
- Sin el campo destino, el padrón de localidades inventa sobre el texto libre: "el ojito" da Salta, "en alto" San Luis.
- El modelo todavía marca como destino playa, living, cuarto, primer piso, local o lo de mi vieja. El código de lugares
  no los toma: no se inventa nada.
- Latencia de la llamada 0: 1,3 a 1,5 segundos de mediana. Costo con la paga: dos centésimas de centavo por mensaje.

### Los embeddings sobre lo que tradujo, contra las palabras del cliente

| Banco | Sobre lo que tradujo | Sobre los fragmentos |
| --- | --- | --- |
| nuevas70, gemini, haiku, deepseek | 74, 75 y 76 de 76 | 75, 73 y 75 |
| nuevas70b, gemini | 111 de 112 | 105 |

El fragmento muchas veces no es el producto: es el destino o una referencia, "uno a Jujuy", "una roja". Repreguntar
cuando no coinciden se midió y no sirve: repregunta lo bien traducido y deja pasar lo que no se vende.

### El nexo de rubro, sin modelo

- **La segunda búsqueda:** dentro de los tres rubros, la traducción contra cada modelo de la tienda con sus etiquetas
  del catálogo. Cinco candidatos con su fila real. **El correcto está entre los cinco en todos los casos**, 77, 76, 77 y
  111.
- **La función de código que elige:** la primera palabra de la traducción contra el nombre, las etiquetas, el rubro y
  los alias de cada candidato. Elige bien 92 a 94 por ciento. Mal: 3, 1, 1 y 0.
- **Lo que no se vende:** 7 de 7 en nuevas70; **8 de 14 en nuevas70b, no pasa su corte de 80 por ciento.** Elige algo
  cuando la palabra pedida está en el vocabulario de la tienda en otra parte de una frase: celulares por "los que se
  enchufan al celu", escritorio por "silla de escritorio", aire acondicionado por "el coso que tira aire", cámara de
  fotos por "cámara web", pad por "mouse pad".

### El flujo de punta a punta, 140 mensajes

Cero cortes, cero filas fuera del catálogo. Producto coincide 204 y no hay 30; destino coincide 78 y repreguntar 9.

## 3. Lo que se probó y se descartó

| Qué | Por qué no |
| --- | --- |
| El ancla de palabras con reglas de gramática | se retocó dos veces después de ver; frágil |
| Fundir la búsqueda del modelo y el fragmento | un punto peor: el fragmento corto mete ruido, "1 mesh" da tablet |
| Cortar el mensaje en partes y buscar cada una | en las 70 el modelo no pierde productos; 20 a 60 rubros sobrantes |
| El reordenador de Google | la API está apagada en el proyecto; Martín lo descartó por complejidad |
| La taxonomía de Shopify | FICHA 95: homónimos |
| Subir el razonamiento o cambiar de modelo | no hizo falta: el asado era de pedir siete campos y de un defecto mío |

## 4. Dónde está cada cosa

| Qué | Dónde |
| --- | --- |
| El flujo y el contrato en código | `banco_pruebas/flujo_nuevo.py` |
| La llamada 0 de tres campos, grabada | `banco_pruebas/flujo_nuevo_llamada0.jsonl` |
| El nexo de rubro: llamada 0, segunda búsqueda y la función que elige | `banco_pruebas/nexo_rubro.py` |
| La llamada 0 v1 y v2 sobre nuevas70b | `banco_pruebas/momento0_b.py` |
| Fragmentos contra traducción | `banco_pruebas/momento0_suma.py` |
| El nexo de destino | `banco_pruebas/nexo_destino.py` |

```bash
python3 banco_pruebas/flujo_nuevo.py            # el flujo de punta a punta, sin gasto
python3 banco_pruebas/nexo_rubro.py             # el nexo de rubro sobre los dos bancos, sin gasto
python3 banco_pruebas/momento0_b.py v1          # la llamada 0 v1 sobre nuevas70b, sin gasto
```

**Los vectores enteros no están en el repo**: pesan decenas de megas y quedaron en el cache de la sesión. En el repo
quedan los puntajes, y con ellos todo se califica sin gasto. Si cambian las consultas o los documentos, hay que volver a
calcular con `--embeddings` y la paga: el catálogo entero cuesta menos de dos centavos.

## 5. Defectos conocidos, para la auditoría

1. **El padrón de lugares inventa sobre texto libre**, y el agente vivo lo usa así en `agente._lugares`: "el ojito"
   puede salir como Salta en producción.
2. **Hay dos variables de configuración para el modelo de embeddings** en `app/config.py`, `EMBEDDING_MODEL` y
   `EMBEDDINGS_MODEL`, una vieja.
3. **El banco tiene la tienda escrita a mano**, `verifika_prod`, y el camino del cache de la sesión. Al pasar a `app/`,
   todo recibe `tienda_id` y el índice se calcula al subir el catálogo.
4. **Pantalla táctil va a monitor y cajita de música a fuente** en la función que elige: "pantalla" está en las
   etiquetas de monitor y "cajita" en un alias de fuente.

## 6. Lo que sigue

1. **Hechos el 15-nov:** el nexo de tema de la FAQ con Jev en lo dudoso, sección 8, y el de producto nombrado, sección 9.
   Cómo busca cada nexo, en un solo lugar: `banco_pruebas/busquedas.py`.
2. **El nexo de condición, el último**: el más cargado, 188 líneas por el ruteo grueso, y el más difícil. Su borde con
   el nombrado: el catálogo mete atributos en el nombre del modelo, "Mesh", "Curvo", "DDR4", y ahí corren los dos.
3. **Espera a Martín:** "hyperx cloud 2" da el Cloud Stinger 2 en vez del Cloud II. Arreglarlo es leer números romanos,
   una lista.
4. **Lo que no se vende del nexo de rubro**, 8 de 14 en nuevas70b: probar Jev en lo dudoso igual que en el de tema.

## 7. Lo que aportó Martín sobre variantes de embeddings, para considerar

Un texto que trajo Martín el 15-nov. Lo que sirve para lo que sigue:

- **Lo que se vectoriza y lo que se devuelve van separados.** Ya se hace así: el vector busca y el código devuelve la
  fila por id, tal cual de la fuente. Por eso no hay alucinación de datos; el riesgo que queda es el falso positivo.
- **La búsqueda híbrida, vectorial más palabras exactas**, es la herramienta del nexo de producto nombrado: los
  embeddings confunden G203 con G305, la palabra exacta no.
- **Pregunta contra pregunta.** Para la FAQ conviene vectorizar las formas de preguntar cada tema, que son los alias de
  `alias.json`, no el texto largo de la respuesta.
- **Modelos locales en el servicio**, Model2Vec o FastEmbed, sin llamar a una API: menos latencia y sin costo por
  consulta, a cambio de más memoria y paquetes nuevos en `requirements.txt`. Se pueden medir contra los embeddings de
  Gemini en los mismos dos bancos antes de decidir.
- **El umbral de rechazo que propone el texto sigue prohibido** por la FICHA 95: los puntajes de lo que se vende y lo
  que no se pisan. Lo dudoso va a Jev o a la llamada corta.

## 8. El nexo de tema de la FAQ, 15-nov

Sobre los mismos 140 mensajes y la misma llamada 0. La vara y los cortes, escritos antes, en `banco_pruebas/nexo_tema.py`:
15 preguntas de la tienda con su línea, más una que la llamada 0 no dejó en ningún fragmento, "factura A" de B12.

- **Los candidatos:** el fragmento de cada línea, las palabras del cliente, contra los alias de cada tema, pregunta contra
  pregunta. Tres temas. **El pedido está entre los tres en 15 de 15.** Los fragmentos ya van en el pedido de embeddings
  del mensaje: el nexo no suma pedidos.
- **La función de código que elige:** el primer candidato que comparte una palabra clave de la FAQ con el fragmento, menos
  las palabras con que el catálogo nombra productos. Con los alias en vez de las palabras clave inventaba en 115 de 254
  líneas: "una silla gamer" daba los DPI del mouse. Con las palabras clave, elige bien 15 de 15 e inventa 12.
- **Lo dudoso:** toda línea donde el código eligió tema, 27. Una pregunta por mensaje, cada línea elige entre sus tres
  candidatos o ninguno.

| Lo dudoso con | Elige bien | Inventa | Ningún tema | Demora |
| --- | --- | --- | --- | --- |
| Jev, dos corridas | 15 de 15 | 3 y 2 de 254 | 7 de 7 | 0,15 s |
| Gemini corta, dos corridas, gratis | 15 de 15 | 9 y 9 | 5 de 7 | 1 a 15 s |

Jev pasa los cuatro cortes; Gemini no pasa el de inventar ni el de ningún tema. Lo que Jev deja: "si tienen en color azul"
como stock, "su mother que sea compatible" como compatibilidad, y en una corrida "service de lavarropas" como garantía.

- **Redactar:** el texto curado con los valores estampados por `curadas.estampar_valores`, como en producción.
- **En el flujo:** el tema mira todas las líneas, no solo las sin búsqueda; la garantía de B62 y el descuento de B64
  estaban en la línea del producto. Rubro y destino dan lo mismo que antes, cero cortes.

```bash
python3 banco_pruebas/nexo_tema.py --con jev            # califica con lo grabado, sin gasto
python3 banco_pruebas/nexo_tema.py --correr jev --corrida 3   # otra corrida de Jev
```

## 9. El nexo de producto nombrado, 15-nov

La búsqueda híbrida: los embeddings ponen el rubro, la palabra exacta pone el modelo. Sin vectores nuevos por mensaje.

- **El banco:** las 140 nombran casi solo marcas, "mouse logitech", y ningún par de gemelos. Se sumó
  `banco_pruebas/nombrados38.py`, 38 mensajes con la vara escrita antes: G203 contra G305, Ryzen 5 5600 contra 5600X,
  RTX 4060 contra 4060 Ti, modelos que la tienda no tiene de una marca que sí, y una marca que no vende. La llamada 0 con
  la gratis; los embeddings con la paga, porque la gratis se trabó con la cuota. Los vectores del catálogo recalculados
  dieron diferencia cero contra los puntajes de la sesión anterior.
- **El rubro:** el que elige el nexo de producto. Si no elige ninguno, lo propone la palabra exacta cuando la búsqueda
  nombra una marca y un modelo de un solo rubro: "lenovo legion 5 i7" no traía notebook entre los tres rubros.
- **Las palabras de identidad:** marca de la tienda; nombre de modelo del rubro, si no es atributo en otro campo ni
  describe a modelos que no lo llevan en el nombre; código de letras y números de una sola marca; y, encadenados, los
  números y palabras cortas pegados a esas, "ryzen 5 5600". Un código que la tienda no tiene, pegado a la marca, también:
  "sony xm4" da no encontrado y no todos los Sony.
- **La identidad:** la de producción, `catalogo._identificar`, sobre los productos del rubro. Lo corto que está dentro
  de un código del catálogo se lleva a ese código: "xm5" a "1000xm5".

| Banco | Bien | Exists con otro modelo | No encontrado | Marca que no vende |
| --- | --- | --- | --- | --- |
| nombrados38 | 39 de 40 | 0 | 2 de 2 | 1 de 1 |
| las 140 | 19 de 20 | 0 | 1 de 2 | 4 de 4 |

- **Iterado el 15-nov sin tocar la vara**, de 38 a 39 de 40 y de un exists con otro modelo a cero. Cada regla cubre
  una clase, sin listas:
  - un número dicho elige el modelo donde ese número termina: el sufijo no dicho, "Ti" o "Super", es otro modelo si hay
    uno sin sufijo. "rtx 4060" ya no trae las Ti; "rtx 4070" es la Trinity.
  - un número suelto que calza de casualidad no elige: si el modelo lleva un nombre no dicho y los otros de la familia
    no llevan número, es ambiguo. "hyperx cloud 2" pasa de Cloud Stinger 2 a preguntar entre los Cloud.
  - la búsqueda se acomoda a cómo escribe el catálogo sus códigos: se juntan "5600 x" y "g 305", y se parten
    "rtx4060", "flip6", "4060ti" si sus partes son códigos exactos del rubro.
  - si el rubro de los embeddings no nombra nada, lo propone la palabra exacta con una marca o un código exacto del
    rubro: "g-305" y "rtx4060" no traían rubro; "resma a4" no es un SSD A400.
  - se probó y se sacó: los nombres de modelo de otro rubro como identidad. "parlante para smart tv" tomaba la Smart
    Tank y daba un falso "no lo tengo".
- **La sonda**, `--sonda`, 27 variantes de escritura que no son vara: 25 bien. Quedan "hyperx cloud 3", los romanos, y
  "mouse logitech inalambrico", que es del nexo de condición.
- **Lo que falla:** "hyperx cloud 2" pregunta entre los cuatro Cloud en vez de dar el Cloud II: leer romanos es una
  lista y espera a Martín. "motherboard compatible ryzen 5" no corre, y la vara esperaba no encontrado: en
  motherboards "ryzen" describe compatibilidad, y las dos salidas dejan la línea al de producto y al de condición.
- **Fuera de la vara corre en 12 líneas de las 140**, por atributos que el catálogo metió en el nombre del modelo:
  "memoria ddr4", "monitor curvo", "mesh". Filtran bien según los datos; el borde se define con el nexo de condición.
- **En el flujo:** si el nombrado corre, su respuesta reemplaza a la del producto genérico. Cuando sus palabras son todas
  de otro rubro, "motherboard compatible procesador intel", no dice "no lo tengo": contesta el de producto. Rubro,
  destino y tema dan lo mismo que antes, cero cortes.

```bash
python3 banco_pruebas/nexo_nombrado.py [--ver]    # califica, sin gasto
python3 banco_pruebas/nexo_nombrado.py --sonda     # las variantes de escritura, sin gasto
python3 banco_pruebas/busquedas.py                # cómo busca cada nexo
```

## 10. La búsqueda del nexo de rubro, calibrada, 16-nov

Orden de Martín: la elección final es la función de código; se calibra la búsqueda de embeddings. Sobre la vara de las 140,
una cosa por vez, con `python3 banco_pruebas/nexo_rubro.py --calibrar`:

| Variante | Elige bien | Rubro equivocado | No se vende, nuevas70b |
| --- | --- | --- | --- |
| V0, la de antes | 71, 70, 71, 104 | 5 | 8 de 14 |
| V1, cada modelo con los alias de su rubro | 72, 71, 72, 104 | 2 | 8 |
| V2, modelo por nombre y descripción | igual que V0 | 5 | 8 |
| V3, lo que la tienda declara que no vende en el índice | igual que V0 | 5 | 10 |
| V4, dos rubros candidatos | igual que V0 | 5 | 8 |
| V5, modelo sin etiquetas | uno menos | 5 | 8 |
| **V6, V1 más V3, la viva** | **72, 71, 72, 104** | **2** | **10 de 14** |

- **Lo que no se vende gana solo si queda primero y la búsqueda lo dice.** Sin esa confirmación, "sony xm5" caía en
  "play 5" por Sony, y "escritorio en L" acertaba por casualidad cerca de una heladera.
- **Las cuatro que siguen fallando la tienda no las declara:** cámara de fotos, escritorio, pad de mouse. Es dato, no
  búsqueda.
- **Los "no hay" con lo más cercano bien**, "repetidor wifi", "fotocopiadora", "trono gamer", quedan: la palabra no está
  en la fuente y se ofrece lo más cercano verificado.
- **La convivencia:** el índice calibrado movía el rubro de los nombres de modelo, "jbl tune 520" caía en parlantes. En
  el nombrado ahora el rubro lo decide la palabra exacta, regla 7.0, y los embeddings desempatan: 39 de 40 y la sonda 25
  de 27, igual que antes. Tema, destino y el flujo, iguales; cero cortes.

### Jev en lo dudoso del nexo de rubro, 16-nov

Dudoso, sin umbrales: el código dijo "no hay", o eligió por una palabra que solo está en etiquetas o alias y no en el
nombre ni en el rubro del candidato. Entre 20 y 38 líneas por banco. Jev, una pregunta por mensaje, elige entre los cinco
candidatos o ninguno. Cada candidato va con los alias de su rubro: sin eso Jev decía ninguno a "headset" y "charger 65w".

| | Elige bien | Rubro equivocado | No se vende, nuevas70b |
| --- | --- | --- | --- |
| Antes del 16-nov | 71, 70, 71, 104 | 5 | 8 de 14 |
| Búsqueda calibrada | 72, 71, 72, 104 | 2 | 10 de 14 |
| Calibrada, con Jev | **74, 72, 73, 106** | **1** | **14 de 14** |

Lo que no se vende pasa por primera vez su corte del 80 por ciento. En el flujo de punta a punta Jev cambia 11
decisiones: 10 mejoran, escritorio, pad de mouse y cámara de fotos a "no hay", cajita de música a parlante, airpods a
auriculares; una empeora, "keyboard gamer switches red" queda en "no hay" porque "keyboard" no es alias de teclado.

```bash
python3 banco_pruebas/nexo_rubro.py --jev                 # califica con lo grabado, sin gasto
python3 banco_pruebas/nexo_rubro.py --correr-jev [--flujo]  # Jev sobre lo dudoso que falte
```

## 11. Los nexos sobre mensajes reales que nunca vieron, 16-nov

`banco_pruebas/reales.py`: 40 mensajes únicos de las charlas reales de WhatsApp de Martín, `examen_real/charlas.json`,
los que se entienden solos. La vara, escrita antes de correr. Llamada 0, embeddings y Jev con la paga: medio centavo de
dólar en la llamada 0, anotado en el libro, y menos de un centavo en vectores. Los nexos no se tocaron para correrla.

| | Primera corrida | Con el arreglo |
| --- | --- | --- |
| Mensajes sin ninguna falla | 37 de 40 | 38 de 40 |
| Rubros pedidos | 44 de 45, ninguno de más | 45 de 45 |
| Lo que no se vende | 1 de 1 | 1 de 1 |
| Temas de la tienda | 12 de 13, ninguno inventado | igual |
| Modelos nombrados | 15 de 16, ninguno cambiado | igual |

- **El arreglo:** "auriculares que anden con la PS5" daba no hay, porque "ps5" está en lo que no se vende. Lo no vendido
  gana ahora solo si es lo primero de la búsqueda, lo pedido, como en la función que elige. Las 140, el nombrado y el
  flujo dan lo mismo.
- **Lo que queda no es de los nexos:** "el G502 Hero y el G305" pierde el G502 en la llamada 0, que deja una línea sola;
  "tienen 50 off" no da tema porque "off" es alias de promociones y no palabra clave de la FAQ.
- **Lectura:** en mensajes nuevos los nexos rinden como en los bancos. Lo que sigue es el nexo de condición.

```bash
python3 banco_pruebas/reales.py [--ver]      # califica, sin gasto
```
