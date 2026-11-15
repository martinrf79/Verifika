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

1. **Decidir Jev o llamada corta para lo dudoso**, midiendo los dos sobre lo que no se vende de nuevas70b y sobre los
   "no hay" de lo que se vende. Con el corte escrito antes.
2. **El nexo de producto nombrado**: 11 líneas en los 140, "parlante jbl flip azul", "procesador intel". La función de
   identidad que ya existe, existe, ambiguo o no existe, sobre marcas y modelos. Hace falta un banco con más nombrados y
   con modelos parecidos, G203 contra G305.
3. **El nexo de tema de la FAQ**: 20 líneas. Tiene que poder decir "ningún tema", porque le llegan líneas que son solo
   destino, "3 a Cipolletti". Y tiene que mirar también los fragmentos de las líneas de producto: "¿tienen garantía
   oficial las placas de video?" queda en la línea del producto.
4. **El nexo de condición, el último**: el más cargado, 188 líneas por el ruteo grueso, y el más difícil.

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
