# FICHA 63 — La puerta de las mejoras

27-sep-2026. Sigue a la ficha 62. Es el metodo con el que entra cada mejora
de ahora en mas, y las dos primeras que lo pasaron.

## Por que

Las mejoras se volvian cascadas por dos cosas. Se cambiaba la vara y el codigo
a la vez, y no se sabia cual movio el numero. Y se miraban totales: un 79 de 86
puede ser una charla arreglada y otra rota.

## El metodo

1. La vara no se toca mientras se trabaja una mejora. Si tiene un error, se
   corrige aparte y la base se vuelve a calificar.
2. Base: tres tandas de las 58 por el clon, guardadas.
3. Un arreglo por vez.
4. Primero el test offline que falla; despues el codigo.
5. Tres tandas del cambio y `python3 -m banco_pruebas.puerta`: compara charla
   por charla, respuesta e interpretacion. Pasa si no rompe ninguna charla que
   estaba bien en las tres de la base y arregla las que buscaba.
6. Si no pasa, se revierte. Nada de parche sobre parche.

## Lo que mide

- La RESPUESTA, lo que recibio el cliente: la vara de `vara_58.py`.
- La INTERPRETACION, lo que el modelo le pidio a las herramientas: las piezas
  de `desmenuzar.CASOS` contra las llamadas, con `pedido_agente.nota_piezas`.
  Por el clon se guardan las llamadas de cada turno desde este dia.

## Lo que entro

- **La compra sin reservar.** "Me lo llevo", "dame el que", "el primero"
  despues de "me llevo uno": si nadie llamo a reservar, la completitud se lo
  marca. Arreglo C29 y C50; C32 ahora pregunta el color en vez de reservar a
  ciegas, y la vara lo acepta por decision de Martin.
- **La marca excluida antes.** "Que no sea Redragon" y despues una busqueda del
  mismo rubro sin sacarla: se lo marca. No rompe nada; el caso medido casi
  nunca vuelve a buscar, asi que no mueve el numero.
- **"Off" es promociones**, en los alias de la tienda. De 929 preguntas de las
  varas y la FAQ, cambian solo las dos que dicen "off".

## Lo que se probo y se revirtio

- **Obligar a consultar cuando contesta de memoria.** En C46 el modelo busco
  con un filtro mal armado, "que no diga membrana", y ofrecio el K380, que es
  de membrana, como mecanico. Antes contestaba bien con lo que ya habia
  mostrado. La puerta lo freno.

## Resultado

Contra la base de tres tandas: arregla cinco, no rompe ninguna, tiembla una en
una sola tanda.
