# FICHA 95 — El equipo del momento cero y los nexos, uno por uno

14 y 15-nov-2026, sesión con Martín. Sigue a la FICHA 94, que queda como antecedente. **Escrita para que una sesión
nueva siga sin volver al chat.**

---

## 1. Lo que decidió Martín

- **El momento cero es un equipo:** el modelo separa y traduce, los embeddings suman lo que el modelo no tradujo, el
  código decide y certifica. El objetivo es que la primera traducción sea una base firme para todo lo que sigue.
- **Después del momento cero van los nexos, uno por sesión o por tramo**, cada uno medido sin modelo sobre lo ya
  grabado, con la vara escrita antes. Son cinco: rubro, producto nombrado, tema de la FAQ, destino y condición de ficha.
- **Las respuestas se escriben cortas y sin paréntesis:** Martín usa lector de voz. Se hace lo que se pide, sin
  actividades de más; cada paso se explica en una línea antes de hacerlo.

## 2. Lo medido

### El equipo: modelo más embeddings

`banco_pruebas/momento0_suma.py`, sin gasto. La regla, escrita antes: lo que el modelo tradujo mal queda rescatado si la
búsqueda del modelo y el fragmento del cliente dan el mismo rubro de la tienda por embeddings, y es el esperado.

| Modelo | Solo el modelo | Con los embeddings |
| --- | --- | --- |
| Gemini | 67 de 70 | 69 de 70 |
| Haiku | 67 de 70 | 69 de 70 |
| DeepSeek | 64 de 70 | 69 de 70 |

- Rescata los productos por rodeo: pantallita táctil, cajita de música, compu que se pliegue, plaqueta madre, trono gamer.
- Queda uno por modelo: Gemini M01 fragmento reescrito, Haiku M17 no separó la fuente, DeepSeek F10 perdió "sos un bot".
- **El riesgo:** lo que la tienda no vende coincide igual en un rubro. Mochila a notebook, cartuchos a impresora,
  zapatillas a auriculares. Hace falta el paso que confirma.

### Lo que no sirvió: embeddings contra la taxonomía de Shopify

`banco_pruebas/momento0_shopify.py`, con la paga, unos 4 centavos. Unas catorce mil categorías de cualquier comercio, sin
la tienda. **No se usa:** los homónimos ganan, fuente da fuentes de agua, mother da bancos, cartucho da vapear, notebook
da blocs de notas. Con la lista chica de la tienda los embeddings rinden; con una enorme, empeoran.

- El mensaje entero, un vector, pierde los pedidos de varios productos: 9 de 40 primeros.
- Separado por el modelo y cada fragmento por embeddings: 56 a 58 de 84 primeros.

### El nexo de destino, hecho

`banco_pruebas/nexo_destino.py`, sin modelo. El campo destino de la v2 grabada, partido como el camino vivo, por el
cotizador de producción. La vara, por geografía: zona y provincia.

- Antes, 29 a 32 de 33, con tres mal: dos lugares en un campo cotizaban uno solo.
- **Corregido en `app/core/flujo/normal.py`, deployado el 15-nov:** `lugares` reconoce el conurbano, que se perdía
  entero, y `envio_a_varios` parte dos lugares de una misma provincia.
- Ahora 32 de 33 en los tres modelos, cero mal. Queda "Comodoro" sin Rivadavia: el código pide la provincia.

## 3. Los nexos que siguen, en orden y con su corte

1. **Rubro con el paso que confirma.** Los embeddings traen tres rubros; una llamada 2 elige uno o "ninguno", releyendo
   el fragmento, solo cuando la búsqueda y el fragmento no coinciden o el producto puede no venderse. Sobre las v2
   grabadas. Corte: el rubro correcto en al menos 75 de 77 por modelo y al menos 18 de 21 no vendidos en "ninguno".
   Lleva modelo: con la gratis, o la paga con el ok de Martín.
2. **Tema de la FAQ.** Embeddings contra los temas de la tienda, sin modelo, con las líneas sin búsqueda de la v2 y las
   preguntas de las 58. La vara, el tema de la agenda a mano. Antes de medir, decidir con Martín C41, jubilado, y el alias
   de "precio por cantidad" que está en promociones y en mayoristas.
3. **Condición de ficha.** El texto de cada condición contra los campos del rubro, sin modelo; la negación y el número
   los arma el código. Es el más flojo: 148 de 200 en `fragil_fijo.py`.
4. **Producto nombrado.** La función de identidad que ya existe, exists, ambiguous o not_found, sobre las marcas y
   modelos que trae la búsqueda.

Después: el contrato entre los nexos y el código que redacta, FICHA 94 punto 4.2.

## 4. Lo que no se hace

- Embeddings contra una taxonomía general en lugar de la tienda.
- Separar lo no vendido con un umbral de puntaje.
- Subir el techo de líneas de `app/`: lo nuevo entra reemplazando.
- Pushear sin el ok de Martín, aunque sea banco.

## 5. Dónde está cada cosa

| Qué | Dónde |
| --- | --- |
| El equipo, modelo más embeddings | `banco_pruebas/momento0_suma.py` |
| La prueba de Shopify, descartada | `banco_pruebas/momento0_shopify.py` y sus `.json` |
| El nexo de destino | `banco_pruebas/nexo_destino.py` |
| El engranaje 0 y los embeddings de rubros | `banco_pruebas/engranaje0.py`, `engranaje0_embeddings.json` |

```bash
python3 banco_pruebas/momento0_suma.py      # el equipo, sin gasto
python3 banco_pruebas/nexo_destino.py       # el nexo de destino, sin gasto
python3 banco_pruebas/engranaje0.py --nexo  # los embeddings de rubros, sin gasto
```
