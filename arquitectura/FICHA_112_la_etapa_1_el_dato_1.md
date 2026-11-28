# FICHA 112 — LA ETAPA 1: EL DATO 1, TRADUCIDO DESDE EL CLIENTE (28-nov-2026)

Se lee antes de proponer o medir cualquier cosa de la traduccion. Viene de la FICHA 111. Orden de Martin del 28-nov: la
etapa 1 se deja robusta antes de tocar la etapa 2.

## 1. Las palabras, para que no se mezclen

- **Dato 1:** a que se refiere el cliente, traducido desde sus palabras: el rubro, el producto, el atributo, el orden,
  el tema. Un concepto de la lista cerrada, escrita del lado del usuario: `rubro:auriculares`, `orden:mas_barato`.
- **Dato 2:** el dato especifico de la tienda que responde: el modelo, el precio, el stock, el campo de la ficha
  tecnica. Lo pone el codigo, abajo. No es de la etapa 1.
- **El redactor:** el codigo que escribe la respuesta. Necesita el dato 1 y el dato 2.
- **Un reconocedor:** un proceso que produce el dato 1 de lo que escribio el cliente. Puede ser una funcion de codigo,
  la base de jerga, o el modelo razonando. No redacta nada.
- **Luna, en la primera llamada,** solo interpreta lo que dijo el usuario. No busca en la tienda ni pone el dato 2.
- **Etapa 1:** cada fila del cliente a su dato 1. **Etapa 2:** el dato 1 enlazado a la tienda para sacar el dato 2.

## 2. El flujo de la etapa 1

1. **Separar.** Luna separa el mensaje en filas literales.
2. **El codigo, donde sabe.** La base de jerga, `banco_pruebas/flujo/jerga/`, resuelve la fila si es exacta o esta
   contenida. Solo lo que da por claro se toma sin modelo.
3. **Los candidatos.** Lo que el codigo no da por claro va a los embeddings, sobre las expresiones de la base, no sobre
   el catalogo: los cinco conceptos mas cercanos, con el rubro de otra fila como contexto.
4. **Elegir.** El modelo elige uno de los cinco, atado por esquema, o dice ninguno y se repregunta.

## 3. La regla de reparto, de Martin el 28-nov

Una clase queda en manos del codigo solo si, cuando dice claro, acierta el 98% o mas. Lo demas va a candidatos. Lo
medido en una clase decide; lo que mueve un caso solo, no.

## 4. Las varas, en orden, con el tramo perfecto de las etiquetas

Cada una se mide sola y no se pasa a la siguiente hasta que este robusta. Comandos en `jerga/medir.py` y `jerga/elegir.py`.

1. Separar: las filas de Luna contra los tramos etiquetados. `primeros/perdidas.py`, con el tipeo corregido contado.
2. El codigo: de lo que da por claro, cuanto acierta, por clase.
3. Los candidatos: el bueno entre los cinco, sobre lo que el codigo no da por claro.
4. Elegir: con los candidatos, que elija bien o diga ninguno, sin errar.
5. La cadena de la etapa 1, de punta a punta, con la separacion de Luna.

## 5. Lo medido el 28-nov

- **Separar:** Luna no pierde datos. Lo perdido en Luna, contando el tipeo corregido, es 3 en el examen y 1 en las
  reales, y los cuatro son normalizaciones.
- **El codigo:** en las reales, 83 claros y 83 bien. En el examen, 377 claros y 359 bien. De los 18 mal, 10 son
  criterio de la etiqueta, que mezcla la etapa 2 con la 1: "airpods" esta marcado como no vendido porque no hay Apple,
  y "wifi 6" o "full hd" para ignorar. Otros 5 son el papel de la fila: "mi notebook" es el equipo del cliente, no lo que
  busca, y eso lo dice Luna. Y 3 son del tipeo, que dado por claro acerto 0 de 3: desde el 28-nov nunca es claro.
- **Los candidatos:** la fila entera, con el rubro de otra fila como contexto, deja el bueno entre los cinco en 85 de 89
  del examen y 6 de 7 de las reales. Buscar por pedazos sueltos fue peor: una palabra exacta, "tablita", tapa la frase.
  Se sumaron descripciones por funcion de cada rubro, "lo que le da energia a la pc".
- **Embeddings:** locales, multilingual-e5-large en ONNX. Los de Gemini por la gratis tienen un tope de 1.000 textos
  por dia, y la base son unos 9.000.

## 6. Lo que espera a Martin

Las etiquetas del examen mezclan las dos etapas: marcan para ignorar o como no vendido lo que el cliente si dijo bien.
Para medir la etapa 1 hace falta su casilla del lado del cliente. Cambiar una etiqueta se consulta antes.
