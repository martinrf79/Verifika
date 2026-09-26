# FICHA 61 — Desmenuzar y traducir: con tablero o de cabeza

26-sep-2026. Mide sólo el primer paso: el modelo parte el último mensaje en
piezas y traduce cada una. No hay herramientas, buscador ni redacción. Son
las 58 de la ficha 58 más diez mensajes de jerga pura, cinco repeticiones y
la clave paga, con `banco_pruebas/desmenuzar.py`. Las piezas correctas están
escritas a mano en ese archivo.

## Las tres formas

- **A, de cabeza.** El modelo parte y traduce a palabras comunes: "aparato con
  teclas" es teclado, "acorde a la crisis" es barato. El código ubica esas
  palabras en el índice de la fuente, armado con los tags por rubro y las
  palabras clave de la FAQ.
- **B, tablero estático.** El modelo recibe el esquema —rubros, campos, temas
  de la casa y equipos— y traduce directo a esos nombres.
- **C, dos vueltas.** Primero A. Después el código le devuelve tres candidatos
  del índice por pieza y el modelo elige.

## Lo que dio

| | contenido | con la etiqueta de tipo | traducción | jerga | tokens |
|---|---|---|---|---|---|
| A | 311 de 340 | 223 | 183 de 230 | 34 de 50 | 441 |
| B | 307 de 340 | 203 | 218 de 230 | 45 de 50 | 836 |
| C | 312 de 340 | 224 | 218 de 230 | 45 de 50 | 625, y una llamada más |

- **Partir no necesita tablero.** El contenido sale igual en las tres,
  alrededor del 91 por ciento. Se parte con las palabras del cliente como
  fuente de verdad, y "ese", "el otro" y "el del principio" se resuelven
  bien.
- **Traducir sí necesita la tienda.** De cabeza traduce bien a palabras
  comunes, pero el índice simple del código se equivoca: manda notebook a
  cargadores porque los tags de los cargadores dicen notebook. Con el esquema
  delante, o eligiendo entre candidatos, sube al 95 por ciento.
- **B y C empatan en calidad.** B es una sola llamada con el doble de prompt,
  que va en caché. C escala mejor porque el prompt no crece con la tienda,
  pero agrega una vuelta.
- **La etiqueta de tipo no sirve.** Con once tipos de bordes difusos acierta
  dos de cada tres veces en las tres formas: "producto", "buscar" y
  "verificar" se mezclan. El código no tiene que decidir por la etiqueta
  sino por el contenido de la pieza.

## Lo que falla igual en las tres, y es del modelo

- "Sumame dos K120 y un G203" lo parte en dos consultas de stock y se pierde
  el pedido de sumar. Pasa en las tres cuentas.
- "Dame el que sea inalámbrico" compara bien pero pierde la compra.
- "Y alguno mecánico?" después de "que no sea Redragon" se queda con los dos
  que mostró y pierde la exclusión.
- La compra condicional del 56.

## Lo que se decide

1. El modelo parte de cabeza, con las palabras del cliente.
2. La traducción al idioma de la tienda va con el esquema delante, B, mientras
   el esquema entre en caché. Si una tienda lo desborda, C, con el mismo
   formato.
3. El tipo sale del contenido de la pieza, no de una etiqueta cerrada.
4. Lo que falla en las tres —sumar, comprar, condición heredada— se trabaja
   en las instrucciones y se vuelve a medir.
