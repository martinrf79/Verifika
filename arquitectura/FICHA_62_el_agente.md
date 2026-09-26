# FICHA 62 — El agente: búsqueda agéntica con herramientas chicas

26-sep-2026. Sigue a las fichas 59, 60 y 61. Es el cambio de camino en
producción: el turno deja de traducir a una ficha y el modelo busca solo.

## Qué es

`app/core/agente.py`, llamado desde `respuesta.procesar_turno`.

- **Búsqueda agéntica.** El modelo llama herramientas con sus propias palabras,
  lee lo que vuelve y decide el paso siguiente. Es la forma que Anthropic
  eligió para Claude Code en lugar de un índice vectorial.
- **Siete herramientas chicas, una por boca:** buscar, producto, envío,
  política, compatibilidad, cuenta y reservar. Por adentro son el mismo
  `motor.buscar`, así que la identidad, la plata y las tarifas siguen
  certificadas por el código.
- **El tablero en tres capas, generado de la fuente:** las reglas universales,
  los rubros de la tienda, y todo lo demás lo encuentra el índice. El prompt
  no crece con el catálogo.
- **Los alias**, escritos una vez por tienda con `scripts/generar_alias.py` en
  `data/clientes/<tienda>/alias.json`: "el coso de internet" es router sin un
  modelo ni un vector en cada consulta.
- **Dos arreglos del buscador** que salieron de medir: un filtro que deja cero
  con el dato en otro campo se repite donde vive, y varias condiciones que
  juntas dejan cero se buscan por separado con un aviso.

Lo que no cambió: la guarda de procedencia de la plata, el cierre y el cobro,
y la memoria de la charla.

## Lo que dio, por el clon, que es producción entera

La vara de las 58 más diez de jerga, `banco_pruebas/vara_58.py`.

| | casillas | charlas enteras | segundos por turno |
|---|---|---|---|
| el camino del intérprete | 99 de 112 | 57 de 68 | 3,2 |
| el agente | 105 de 112 | 62 de 68 | 2,2 |

Los fallos del intérprete eran de fondo: decía que el G203 no figura, que no
hay DDR5, perdía "el otro". Los que quedan en el agente son respuestas
correctas que no nombran la palabra que la casilla pide, o incompletas: el
reparto de pago sale como total final, y comparar dos no ofrece reservar.

## Cómo se vuelve atrás

Un solo commit reemplaza al intérprete y lo borra. Si en WhatsApp sale mal, se
revierte ese commit con git.
