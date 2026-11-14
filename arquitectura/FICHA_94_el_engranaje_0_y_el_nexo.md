# FICHA 94 — El engranaje 0 y el nexo: qué sale del mensaje sin la tienda, y cómo se ancla

12 al 14-nov-2026, sesión con Martín. Sigue a las FICHAS 92 y 93, que quedan como antecedente. **Esta ficha se escribió
para que una sesión nueva pueda seguir sin volver al chat:** las decisiones, lo medido con sus archivos y comandos, el
contrato del engranaje 0 y los pasos con su corte.

---

## 1. Lo que decidió Martín

- **El flujo se piensa en engranajes.** El engranaje 0 es la primera llamada al modelo; el último es el código que
  redacta. Entre los dos va un **nexo**: el anclaje a la tienda.
- **El engranaje 0 entrega lo mínimo para que el flujo siga, y nada más.** Su única fuente es lo que escribió el cliente:
  no recibe catálogo, ni rubros, ni temas, ni ejemplos. No elige la acción, no decide el rubro ni si la tienda vende algo,
  no resuelve "ese".
- **Atar la forma, no el contenido.** El esquema obligatorio fija las líneas y sus campos; el contenido es texto libre, todo
  campo puede quedar vacío y no hay listas cerradas sobre lo que sale de la cabeza del modelo. Con la salida atada la API
  no falla: el modelo elige en silencio lo que más se parece, y eso es lo que se evita.
- **Cada escalón cierra solo lo que el anterior le dio con certeza.** Las listas cerradas van donde las arma el código, como
  los candidatos del nexo, y siempre con "ninguno".
- **La vara se escribe antes, mide solo lo que esa etapa puede saber, y no se toca después de ver el número.** Si hay que
  corregirla, en un punto, a la vista y anotado en el commit.
- **Gemini con razonamiento bajo y la temperatura por defecto**, como pide la guía de Gemini 3. Haiku no acepta
  temperatura: se regula el esfuerzo. DeepSeek solo asegura JSON válido: el código valida y reintenta.
- **Los mensajes de memoria**, "ese", "lo de antes", "cambiá el segundo", no son del engranaje 0: van cuando esté la memoria.
- Para pruebas y hasta tener producto, Martín evalúa Haiku; con el producto terminado, el que rinda mejor. Las pruebas de
  esta ficha comparan los tres.

---

## 2. Lo medido, con sus archivos

### El código con la traducción perfecta, sobre charlas sintéticas nuevas

`banco_pruebas/fragil_fijo.py`, commit 3c55811. Charlas al azar con productos, destinos y referencias reales, con la agenda
que daría una traducción perfecta, por el camino fijo. La vara sale de `productos.csv`, la FAQ y las tarifas, no del bot.

- 1.872 de 1.975 turnos bien. Plata, renglones, envíos, pago partido, tope, sacar, cambiar y memoria a cinco turnos sin errores.
- Lo que falla, cuatro causas: una afirmación falsa se contesta con "Sí"; el color compuesto, "negro y azul", se vuelve a
  preguntar y arrastra el resto; el tope "que no pase los N mil" no filtra; las condiciones de ficha se atan por lista de
  palabras, 148 de 200, con "que no tenga cable" y "que tenga luces" en 0.
- **El camino fijo no es producción**: producción corre el agente.

### La llamada 1 sobre 70 turnos de las K, las J y las C complejas

`banco_pruebas/llamada1_modelos.py`, commit 2d4131b. Deepseek atado 53, Gemini y Haiku atados 52, libres de 43 a 50. **La
vara anclaba con el código de la tienda**: "repetidor" contaba como error porque la tienda lo llama router. Sirve para ver
que atado gana; el número de rubros está contaminado. Jev, rubros y temas sobre el mensaje: 49 de 67 con 106 marcados de más.

### La entrevista a los tres modelos

`banco_pruebas/entrevista_ecommerce.py`, commit e7b79dd. Lo que hicieron vale más que lo que dijeron: en su formato
natural los tres arman el pedido por destino y reparten bien K08 y K21. Coinciden en: taxonomía de Google Shopping para la
categoría y schema.org para atributos; JSON con esquema, descripción por campo, opción "no sé", cita textual.

### El engranaje 0 sobre 70 mensajes nuevos

`banco_pruebas/nuevas70.py` y `banco_pruebas/engranaje0.py`, commit ab8836b. Setenta primeros mensajes que no están en las
58, las J ni las K: varios productos y destinos, el producto por rodeo, condiciones con otras palabras, lo que no es de la
tienda y texto de audio. La vara es permisiva: nada perdido, fragmento del cliente, búsqueda con el concepto común, nada
inventado.

| Corrida | Bien de 70 | Segundos | Centavos |
| --- | --- | --- | --- |
| Gemini v1, fragmento y búsqueda | 62 | 1,3 | 0,8 |
| Gemini v2, más cantidad, destino, plata, orden y condiciones | 67 | 1,4 | 1,4 |
| Haiku v1 | 62 | 1,1 | 0,6 |
| Haiku v2 | 67 | 1,6 | 1,2 |
| DeepSeek v1 | 63 | 1,0 | 0,5 |
| DeepSeek v2 | 64 | 1,1 | 0,8 |

- Cero inventos y cero salidas inválidas en las seis.
- **La v1 pierde destinos y pago** en 5 a 7 de los 18 pedidos de varios productos: sin un campo, no los toma como algo
  pedido. La v2 los trae, 17 o 18 de 18. **El mínimo es la v2.**
- Lo que falla en los tres: el producto por rodeo que queda con las palabras del cliente, "cajita de música", "pantallita
  táctil", "trono gamer".
- Corrección de la vara a la vista: en la v2 el destino y la plata vienen en su campo y la vara solo los buscaba en el
  fragmento. Gemini v2 pasó de 55 a 67.

### El nexo por embeddings

`engranaje0.py --embeddings` y `--nexo`, commit 9a0ae0e. La búsqueda de cada producto de la v2 contra los rubros de la
tienda con sus alias, `gemini-embedding-001` con la paga.

| Con qué se busca | Gemini | Haiku | DeepSeek |
| --- | --- | --- | --- |
| La búsqueda del modelo, rubro correcto primero | 75 de 77 | 75 de 76 | 77 de 77 |
| El fragmento crudo del cliente | 75 de 77 | 73 de 76 | 75 de 77 |

- Rescata lo que el engranaje 0 no tradujo: "cajita de música" a parlante, "pantalla táctil" a tablet.
- **Lo que la tienda no vende no se separa por puntaje**: lo anclado bien va de 0,61 a 0,80 y lo no vendido de 0,57 a
  0,71. Mochila cae en notebook, fundas en motherboard, cartuchos en impresora. Hace falta un paso que confirme.

Gasto de la sesión: unos 18 centavos de dólar entre DeepSeek, Haiku, Jev, embeddings y la paga de Gemini.

---

## 3. El contrato del engranaje 0, la v2

El prompt y el esquema están en `banco_pruebas/engranaje0.py`, `PROMPT["v2"]` y `esquema("v2")`. Por cada cosa que el
cliente pide o pregunta, una línea con:

| Campo | Qué es |
| --- | --- |
| fragmento | La parte del mensaje que lo dice, con las palabras del cliente. Va primero: copia antes de traducir |
| busqueda | Lo que escribiría en el buscador de cualquier tienda online. Vacío si no busca un producto |
| cantidad, destino, plata, orden, condiciones | Solo si los dijo, en palabras simples; si no, vacíos |

Unos 150 tokens de prompt, sin ejemplos ni datos de la tienda. Sirve igual para cualquier tienda.

---

## 4. Los pasos, con su corte escrito antes

1. **El nexo en dos pasos, sobre las salidas v2 ya grabadas.** Los embeddings traen los tres rubros candidatos; una llamada
   2 elige uno de esos tres o "ninguno", releyendo el fragmento. Lista cerrada armada por el código.
   - Corte: el rubro correcto en al menos 75 de 77 por modelo, y al menos 18 de los 21 productos no vendidos en "ninguno".
   - Después, lo mismo para temas de la FAQ y para productos nombrados, que el nexo todavía no probó.
2. **Qué recibe el código.** Definir con Martín el contrato entre el nexo y el engranaje que redacta, y llevar la salida
   v2 más el anclaje a la agenda que el código ya cumple. Se mide pasando las 58, las J y las K por el camino fijo.
3. **Las cuatro causas del código** que encontró `fragil_fijo.py`, cada una medida con su semilla, después de que el
   contrato esté definido: la afirmación falsa, el color compuesto, el tope de precio y las condiciones de ficha.
4. **La memoria**, con los mensajes de "ese", "lo de antes" y "cambiá el segundo".
5. **El cableado al bot** cuando el camino nuevo supere al agente en las mismas charlas: es la FICHA 92 paso 3.

---

## 5. Lo que espera a Martín

- K21 T2, "lo demás está bien": la agenda a mano reescribe el pedido entero. ¿Lo que no cambia se escribe o no?
- C41, "soy jubilado, ¿tienen descuento?": ¿promociones o descuento por transferencia?
- En `alias.json`, "hacen precio por cantidad" figura en promociones y en mayoristas a la vez.

---

## 6. Lo que no se hace

- Darle al engranaje 0 el catálogo, los rubros, los temas o ejemplos sacados de los casos de prueba.
- Listas cerradas en el engranaje 0 sobre lo que el modelo saca de su cabeza.
- Separar lo que la tienda no vende con un umbral de embeddings: los puntajes se pisan.
- Medir el engranaje 0 con el código de la tienda, ni cambiar la vara después de ver el número sin dejarlo escrito.
- Correr con la clave paga o gastar cuota sin el ok de Martín en esa sesión.

---

## 7. Dónde está cada cosa

| Qué | Dónde |
| --- | --- |
| El código con la traducción perfecta, sintéticas | `banco_pruebas/fragil_fijo.py` |
| La llamada 1 sobre 70 turnos viejos | `banco_pruebas/llamada1_modelos.py`, `llamada1_corridas.jsonl` |
| La entrevista | `banco_pruebas/entrevista_ecommerce.py`, `entrevista_ecommerce.json` |
| Los 70 mensajes nuevos y su vara | `banco_pruebas/nuevas70.py` |
| El engranaje 0, v1 y v2, y el nexo | `banco_pruebas/engranaje0.py`, `engranaje0_corridas.jsonl`, `engranaje0_embeddings.json` |

```bash
python3 banco_pruebas/engranaje0.py --calificar --ver       # el engranaje 0, sin modelo
python3 banco_pruebas/engranaje0.py --nexo                  # el nexo, sin modelo
python3 banco_pruebas/fragil_fijo.py --n 400 --semilla 11   # el código, sin modelo
```
