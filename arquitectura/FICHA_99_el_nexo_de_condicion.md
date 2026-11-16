# FICHA 99 — El nexo de condición, el quinto: lo que el cliente pide del producto, atado o repreguntado

16-nov-2026, sesión con Martín. Sigue a la FICHA 98. **Escrita para que una sesión nueva siga sin volver al chat.** Lo
hecho, en `git log` del 16-nov.

---

## 1. Dónde estamos

Los cinco nexos de la FICHA 96 están hechos en el banco, en `banco_pruebas/flujo_nuevo.py`: rubro y producto, destino,
tema de la FAQ, producto nombrado y condición. Todavía no hay segunda llamada al modelo: el código redacta. Cómo busca
cada nexo, en `banco_pruebas/busquedas.py`.

## 2. Lo que decidió Martín el 16-nov

1. **Se contesta solo con la fuente que ya está en el repo**, sin sumarle conocimiento.
2. **Tres veredictos:** ata, se filtra y se presupuesta; no hay, el campo existe y ningún producto trae ese valor, se
   dice y se ofrece lo más cercano; no se ata, ningún campo lo dice, se repregunta.
3. **Los embeddings eligen el campo, no el valor:** "24" y "27 pulgadas" les dan casi lo mismo. El valor lo elige el
   código, y lo que razona lo confirma Jev.
4. **Jev en lo dudoso**, no una segunda llamada.

## 3. Cómo es el nexo, `banco_pruebas/nexo_condicion.py`

1. **El producto.** La primera palabra de la búsqueda, salvo que sea un valor o un número; las del nombre del rubro; y
   la cabeza de cada alias. Lo demás es condición.
2. **Lo seguro, el código, sin modelo.**
   - El tope de plata, con `catalogo._TOPE`.
   - Un número con su unidad, contra los campos del rubro que miden en ella. "2 teras" es 2tb. Si el valor no está, no
     hay. Si ningún campo mide en esa unidad, como las pulgadas de un monitor, no se ata.
   - El valor de un campo, con plural, género y negación, "no chinos" o "-redragon".
   - Un campo de sí o no, por su clave de `specs_preguntables`, como "sumergible".
   - El orden de `catalogo.ORDEN`, "barata" o "el más liviano".
3. **La segunda búsqueda.** Lo que queda va con el rubro adelante, "mouse: económico", contra un documento por campo del
   rubro, con su etiqueta y sus valores, y dos órdenes. Salen tres campos candidatos.
4. **Jev.** Lista cerrada: los valores reales de esos campos, los órdenes, "solo nombra el producto" o "ninguno", que es
   no se ata.
5. **Lo que se depura.** Lo atado que vale para todo el rubro se saca, porque no dice nada. Lo atado sin ningún producto
   con stock pasa a no hay.

**El borde con el nombrado:** si el nombrado dio exists, manda el nombrado. Si dio ambiguo o no hay, corre la condición
sobre el rubro. En la respuesta, la condición reemplaza a la del producto y a la del nombrado ambiguo. Si algo no se ata
y algo sí, se repregunta lo que no se ata y se muestra lo que cumple lo demás.

## 4. Lo medido

La vara se escribió antes de correr, en `banco_pruebas/nexo_condicion_vara.py`: por búsqueda en las 140, y por mensaje
y rubro en los reales y las 365, estas desde `agendas58.py`.

| Banco | `catalogo.atar` de producción | el código solo | con Jev |
| --- | --- | --- | --- |
| las 140, 153 líneas donde corre | 99 sin falla, 24 filtros inventados | 144, 1 | 149, 2 |
| 40 reales, 16 rubros con condición | 4 | 6 | 9 |
| las 365, 210 rubros con condición | 100, 59 repreguntas de más | 127 | 131, 4 |

**La calibración**, `--calibrar`, con un Jev perfecto: V1, V2 y V3 dan 150 en las 140. La búsqueda no es el cuello de
botella. Se eligió V2 con tres candidatos, y Jev real queda a uno del techo. V4, un documento por valor, se midió con la
paga: 151 con dos candidatos, una línea más, que no alcanza para cambiar de variante.

**Lo que no está en ningún campo** sale no se ata, como corresponde: el tamaño de los monitores, el peso que aguanta una
silla, el idioma de un teclado, si un auricular trae micrófono.

**Los otros cuatro nexos no cambiaron:** reales 39 de 40, las 365 312, y la batería 532.

## 5. Lo que falla, por causa

1. **La llamada 0 pierde la condición antes del nexo**: 58 de las 79 pérdidas en las 365 y 6 de las 7 en los reales.
   - C07, "que no sea Genius", llega como "mouse".
   - C24 y K06, "el más barato", llegan como "teclado".
   - R14, K20 y K21: "menos partes chinas posibles" vale para todo el mensaje y no llega a ninguna línea.
   Es lo primero de la sección 6.
2. **El tope sin "de"**: "menos 200 mil" y "200000" no los toma `catalogo._TOPE`, que es de producción. C42.
3. **Jev elige algo general**:
   - "tablet para dibujar" sale con el uso que tienen todas, y se pierde la repregunta;
   - "motherboard compatible ryzen 5" sale con un socket preciso.
4. **"Silla gamer negra"**: todas las sillas dicen negro, también las negro y rojo. El filtro no saca nada y se pierde.
5. **La casilla mal**: "monitor curvo 32 pulgadas" sale no hay curvo, y está bien, porque el único curvo no tiene stock.
   La vara pedía ata.

## 6. Lo que sigue, en este orden, orden de Martín del 16-nov

1. **Mejorar la llamada 0.** Primero el prompt con Gemini por la gratis; después otros modelos de costo parecido.
   - Lo que tiene que lograr, medido con los cinco nexos sobre los cuatro bancos:
     - que la condición quede en la búsqueda de cada línea, también la que vale para todo el mensaje, como "menos
       partes chinas";
     - separar dos modelos en una frase;
     - no perder preguntas en mensajes largos.
   - La vara ya existe y no se toca:
     - `nexo_condicion.py` cuenta "perdidas en la llamada 0": hoy 58 de 79 en las 365 y 6 de 7 en los reales;
     - `flujo_nuevo.py` cuenta rubros y destinos;
     - `reales.py` y `reales.py --525` cuentan rubros, temas y nombrados.
   - La salida de cada modelo se graba por mensaje, como `flujo_nuevo_llamada0.jsonl`, y los nexos corren sobre lo
     grabado sin gasto. Se paga solo la llamada 0.
2. **Afinar los nexos sobre la llamada 0 nueva.** Las búsquedas nuevas piden sus vectores y lo dudoso nuevo pide Jev.
   Se miran las fallas que queden, por causa.
3. **Calibrar todo si la llamada 0 mejoró.** Cada nexo con su `--calibrar`, de a una cosa por vez, y la confirmación en
   los bancos que no se usaron.
4. **La memoria.** Acoplar al flujo nuevo la del agente, `memoria_agente`, con el pedido anotado, lo mostrado, el pago y
   el tope, o una más efectiva si se mide mejor. Los bancos son:
   - las 32 claves de memoria que quedaron fuera de las 525;
   - las charlas de varios turnos K10, K11, K16 y K21.
5. Después: modelos de embeddings locales, que suma Martín a `requirements.txt`; la segunda llamada que redacta; la
   auditoría; y el pase a `app/` reemplazando al agente.

## 7. Cómo se corre, sin gasto

```bash
python3 banco_pruebas/nexo_condicion.py [--ver]   # con lo que contestó Jev, grabado
python3 banco_pruebas/nexo_condicion.py --sin-jev # el código y la búsqueda solos
python3 banco_pruebas/nexo_condicion.py --base    # catalogo.atar de producción, para comparar
python3 banco_pruebas/nexo_condicion.py --calibrar   # las variantes de la búsqueda con Jev perfecto
python3 banco_pruebas/flujo_nuevo.py              # el flujo de punta a punta, con los cinco nexos
```

Con gasto:
- `--embeddings V2` pide los vectores que falten, con la gratis, de a lotes con pausa.
- `--correr-jev` pregunta lo dudoso nuevo a Jev. El 16-nov fueron 96 llamadas, 0,2 centavos de dólar, anotadas en
  `banco_pruebas/jev/gasto_jev.jsonl`.

Los vectores no están en el repo; quedan los puntajes.
