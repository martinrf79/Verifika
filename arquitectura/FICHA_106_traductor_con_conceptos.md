# FICHA 106 — EL TRADUCTOR CON CONCEPTOS: JERGA, LO QUE QUIERE DECIR Y DONDE ESTA EN LA FUENTE (23 y 24-nov-2026)

Esta ficha es para arrancar una sesion nueva. Se lee entera antes de tocar nada. Todo lo medido esta en el banco, nada en
`app/`, salvo la fuente corregida en `data/clientes/verifika_prod/`.

## 1. El objetivo

Que el traductor lleve lo que escribe el cliente, en jerga, a lo que eso apunta en la fuente de verdad: un producto, una
caracteristica, una compatibilidad, un tema de la FAQ o una zona. El codigo redacta la respuesta con esas filas. El
traductor nunca inventa: lo que no reconoce lo pasa al verificador, y el verificador dice que no tiene el dato.

Martin pidio, en este orden de preferencia por costo y latencia: un modelo chico propio; si no alcanza, Luna; si no,
Gemini. Y que el modelo chico maneje tres grupos de informacion: la jerga, lo que quiere decir cada frase del lado del
usuario, y como eso esta cargado en la tienda.

## 2. Lo que se midio en esta sesion, y lo que se aprendio

**Luna sin razonamiento**, la llamada 0 v14f1b con `reasoning_effort` none, sobre los 300 mensajes
(`banco_pruebas/flujo/luna_ficha.py`, columna `v14f1b·none`): 1,6 segundos de media contra 4,1 y la mitad del costo, pero
todos los rubros en 133 de 161 mensajes contra 150, sobre todo en codigos sueltos como "el G305", y lo no vendido metido
en un rubro 5 de 62 contra 1. El razonamiento de Luna paga su tiempo; queda en bajo. El caché del proveedor no se usa:
pide mas de 1.024 tokens de entrada y el prompt tiene unos 700.

**Cuantos candidatos**: en las frases de la FICHA 105 con un producto correcto, el correcto esta entre los 3 primeros de
los embeddings en todas. Para elegir producto alcanzan 5; los ordenes, "el mas barato", los resuelve el codigo.

**El reordenador chico sin ajustar**, cross-encoder mmarco-mMiniLMv2, sobre las 34 claras de la FICHA 105: 10 bien, 16
repreguntas, 8 errores. Ajustarlo con frases que escribe Luna se descarto: aprende la jerga inventada, no la real.
`banco_pruebas/flujo/chico/`.

**La base de conocimiento con codigo**, `banco_pruebas/flujo/reglas/`: conceptos con su jerga y su condicion, rubros de
`alias.json`, marcas y modelos por codigo, plata por regex, negacion por codigo, y el resto de la frase contra las
expresiones con embeddings locales, multilingual-e5-small, en el procesador. 0,15 segundos por frase, sin tokens.
- Sobre frases ya vistas y corregidas acierta casi todo: 31 de 34 sin errar en las 48 de la FICHA 105.
- Sobre frases nuevas cae: la muestra tres, 44 frases reales del repo separadas antes de todo, sin dudosas, da 18 bien,
  11 repreguntas y 7 errores.
- Ajustar e5 con la jerga del repo, 1.513 pares, 7 minutos en CPU: en 89 alias que no vio, el significado correcto
  primero pasa de 26 a 39. En la muestra tres no mueve el resultado: 17, 12 y 7.
- Seis de los siete errores de la muestra tres no son jerga: son datos en el nombre del modelo, "16 GB", "DDR4", "1 TB",
  "Flip", y la palabra "gaming" tomada como nombre de una placa.

**Lo que se aprendio:**
1. Lo conocido se resuelve exacto y rapido; lo nuevo no lo resuelve ningun modelo chico con la jerga que hay en el repo.
2. Los errores no son de un solo tipo: hay casilleros distintos, producto, atributo, compatibilidad, numeros, orden,
   negacion y modelo nombrado, y cada uno se resuelve distinto.
3. Cada muestra se gasta al mirarla. Hace falta un examen fijo que nunca se use para ajustar.

## 3. La arquitectura acordada con Martin el 24-nov

La frase se parte en casilleros, palabra por palabra, como hace Wayfair en produccion: esto es producto, esto atributo,
esto numero. Cada casillero se normaliza a la fuente por su propio camino.

| Casillero | Ejemplo | Quien lo resuelve | Su base |
|---|---|---|---|
| producto | "auris", "la caja de la pc" | modelo chico, jerga a concepto | rubros con su jerga |
| atributo | "sin cable", "gamer", "con luces" | modelo chico, y la tabla del par B | `conceptos.py` |
| compatibilidad | "para la play 5", "mi placa es DDR5" | codigo | `compat.py` y `compatibilidad.csv` |
| numeros | "16 gigas", "24 pulgadas", "hasta 30 lucas" | codigo | `numeros.py` |
| orden | "el mas barato", "el mas liviano" | codigo | `conceptos.py`, tipo orden |
| negacion | "que no sea Genius", "sin luces" | codigo | palabras que niegan |
| modelo nombrado | "G305", "Fury Beast" | codigo, el nexo de nombrado del bot | catalogo |

Dos pares separados:
- **Par A, jerga a concepto del usuario.** Lo hace el modelo chico. Primero la memoria verificada: si la frase ya se
  resolvio y se confirmo, se reusa, con controles de que coinciden numeros, colores, marcas, modelos y negacion; la
  similitud sola deja pasar falsos aciertos. Si no, el modelo chico. Si queda lejos, el verificador.
- **Par B, concepto a como esta cargado en la tienda.** Tabla fija por tienda, sin modelo, controlada contra el catalogo.
  Si el catalogo cambia, se ajusta solo el par B y la jerga sigue sirviendo.

Lo exigido filtra; lo que es preferencia, el uso, ordena pero no vacia. Si el filtro deja vacio, se dice que condicion no
se cumple. Lo que la fuente no trae no se infiere: se dice que no hay dato.

## 4. El plan, en orden, y donde quedo

1. **HECHO: administracion de datos**, `banco_pruebas/flujo/conceptos/`:
   - `fuente.py`: la vista de cada modelo con productos, compatibilidad y ficha juntos, y los numeros ya leidos.
   - `conceptos.py`: la lista cerrada de conceptos del lado del usuario con su id fijo, `rubro:auriculares`,
     `atributo:inalambrico`, y su condicion, el par B. Al armar `conceptos.json` controla que cada uno apunte a filas.
   - `numeros.py`: plata, capacidad, potencia, hz, pulgadas y cantidad, con numeros en letras; casos propios que pasan.
   - `compat.py`: el equipo del cliente por familias de requiere y provee, memoria, socket, disco y formato; casos que pasan.
   - **La fuente corregida**, orden de Martin, `corregir_fuente.py`: la caracteristica de plantilla que repetia lo mismo en
     todos los modelos de la mayoria de los rubros se reescribio desde la ficha, la compatibilidad o el dato del
     fabricante. Se sumaron pulgadas, microfono, cancelacion de ruido, fuente recomendada y nucleos. Lo dudoso quedo
     vacio. Indice de embeddings rehecho; la vara sigue en 58 de 75; la bateria pasa.
   - Falta en este paso: sumar a `conceptos.py` los atributos de los campos nuevos, `microfono`, `cancelacion_ruido`, y
     `silencioso` como teclas de membrana o tijera; y que `fuente.py` lea `pulgadas` de la ficha, hoy en None.
2. **SIGUE: el examen fijo.** Unas 150 frases reales, de produccion, del examen real y de los bancos, que no esten en las
   muestras ya usadas, etiquetadas por casillero con los ids de `conceptos.json`: que palabras son que casillero y a que
   concepto apuntan, y la respuesta correcta como regla sobre el catalogo. Congelado con hash. Nunca se usa para entrenar
   ni para fijar umbrales. Las dudosas, marcadas y con la decision de Martin cuando haga falta. El formato de etiqueta es
   uno solo y sirve para la memoria, para entrenar y para medir.
3. **La memoria verificada**, con sus controles. Se mide sobre frases repetidas del repo.
4. **La jerga por tandas:** el repo primero; despues sintetica que escribe Sonnet por personas, un abuelo, un gamer,
   alguien apurado, con errores de tipeo; despues expresiones de foros publicos. Cada tanda en el mismo formato y medida
   contra el examen. El techo: cuando sumar un 20% mas de frases sube menos de un punto, se para. Se estima entre 20 y 50
   mil frases por tienda, unos 4 MB de texto y 19 MB de vectores comprimidos; el modelo pesa unos 120 MB comprimido, y
   con eso Cloud Run necesita alrededor de 1 GB de memoria, cambio que se mide antes y es reversible.
5. **El modelo chico que traduce:** primero GLiNER2, que marca casilleros con su descripcion en texto, sin entrenar; si no
   alcanza, ajustado con la jerga etiquetada. Se compara contra el resolvedor de `reglas/` sobre el examen.
6. **Descripciones, fichas tecnicas y compatibilidades** sobre lo anterior.
7. **La cascada con el verificador podado de la FICHA 105** para lo que no se reconoce, y la latencia de punta a punta.

## 5. Las reglas de la prueba

La regla de validez de la FICHA 105, seccion 5, sin excepcion: plan escrito antes, muestra congelada con hash, una sola
cosa cambia, tres casos antes de gastar, resultados grabados al momento, diez revisados a mano, informe con N, acierta,
repregunta, erra, tiempo y costo. Ademas, lo aprendido aca:
- La respuesta correcta sale de una regla sobre el catalogo, escrita antes de correr nada sobre la frase.
- Un arreglo despues de ver una muestra invalida esa muestra: se mide con otra.
- Se informa aparte lo que no es del casillero que se mide, como los modelos nombrados.

## 6. El entorno del banco

- **El modelo chico corre en un entorno aparte, fuera de `requirements.txt`.** Se arma con
  `python3 -m venv <scratchpad>/venv_chico` y con `pip install torch sentence-transformers datasets accelerate openai`.
  El servidor de torch para procesador esta bloqueado, asi que torch sale de PyPI, que pesa cerca de 5 GB con el resto.
- **Los modelos de Hugging Face se bajan archivo por archivo con curl**, porque la API limita la IP compartida. Por ejemplo,
  `https://huggingface.co/intfloat/multilingual-e5-small/resolve/main/model.safetensors`, junto con `config.json`,
  `tokenizer.json`, `tokenizer_config.json`, `special_tokens_map.json` y `sentencepiece.bpe.model`. La red del entorno
  ya permite `cas-server.xethub.hf.co`, `cdn-lfs.hf.co` y `us.aws.cdn.hf.co`.
- **Python con el certificado del proxy:** `REQUESTS_CA_BUNDLE=/root/.ccr/ca-bundle.crt SSL_CERT_FILE=/root/.ccr/ca-bundle.crt`.
- **El tope de Luna en el banco**, 1,35 dolares en `llamada0_modelos.MODELOS["luna"]`, esta alcanzado: una corrida de la
  segunda llamada con `segunda.py --correr` se corta. Subirlo es decision de Martin.
- **Sonnet, solo para corridas largas o clasificar muchos casos**, con el prompt cerrado de la FICHA 105, seccion 6.

## 7. Lo que queda pendiente de Martin

- **El push.** Hay commits en `main` local sin pushear. El de la fuente corregida deploya, porque toca `data/`.
- **Subir `productos.csv` a Firestore despues del deploy**, con `/admin/upload-catalog`. El comando esta en el chat del
  24-nov y abajo.
- **Las reglas dudosas:** "que no sea chino" cuando todo se fabrica en China, "el mas bestia", "que no haga ruido".
- **Las pulgadas del Samsung ViewFinity S6:** se vende en 24, 27 y 32 y el nombre de la tienda no dice cual; queda vacio
  hasta que Martin diga cual vende. Lo demas se resolvio con busqueda el 24-nov: los cargadores con potencia y puertos
  del fabricante, y el Xiaomi 67W Turbo solo con la potencia porque tiene versiones con y sin USB-C; la Galaxy Tab A9 en
  64GB, la unica en Argentina; la Lenovo Tab M10 sin capacidad, porque no existe de 128GB; las demas tablets siguen en
  128GB, que es una version que existe; la ProSeat Ergo Mesh sin "reclinable", porque no se pudo confirmar. Conviene
  que la tienda ponga la capacidad en el nombre de las tablets.

Carga del catalogo, desde Cloud Shell, despues del deploy:

```bash
URL=$(gcloud run services describe agente-bot --region southamerica-east1 --project memory-engine-v1 --format='value(status.url)')
TOKEN=$(gcloud secrets versions access latest --secret=admin-token --project memory-engine-v1)
curl -sS -X POST "$URL/admin/upload-catalog/verifika_prod?upsert=false" -H "X-Admin-Token: $TOKEN" \
  -F "file=@data/clientes/verifika_prod/productos.csv"
```
