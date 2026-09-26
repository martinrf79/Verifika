# FICHA 60 — Las 58 por tres caminos

26-sep-2026. Sigue a la ficha 59. Las 58 combinaciones de la ficha 58 quedaron
escritas como charlas en `banco_pruebas/vara_58.py`, que genera
`vara_58.json` con los datos reales del día. Las casillas miran sólo lo que
recibe el cliente, así que la misma vara puntúa cualquier camino. Donde hay
dos respuestas buenas, la casilla acepta cualquiera de las dos.

Se corrieron por `banco_pruebas/sonda_charlas.py --vara 58`:

| camino | qué es | casillas bien |
|---|---|---|
| clon | producción tal cual, el webhook entero | 84 de 96 |
| motor | el modelo conversa con herramientas; la herramienta es el buscador real, `motor.esquema` y `motor.buscar` | 93 de 96, y 89 en la segunda corrida |
| simulado | el mismo loop con las herramientas de juguete | 84 de 96, casi todo por tarifas de envío inventadas |

El informe sale de nuevo con `--informe --etiqueta v58_clon`, `v58_motor`,
`v58_motor_dura` y `v58_simulado`. La nota se recalifica desde lo guardado.

## Lo que falla en producción

Leído caso por caso, no son errores de redacción sino de datos que no llegan:

- Dice que el G203 no figura en el catálogo.
- Dice que no hay memorias DDR5, y hay nueve.
- Dice que no tiene el dato de si el G203 es inalámbrico, y está en la ficha.
- No encuentra la política de mayoristas, que existe.
- Pierde "el otro" dos veces y compra el que no era.
- Con "ya no importa la marca" vuelve a ofrecer sólo Logitech.
- Un turno sale con texto roto: "NO es así. El dato real es nombre: ...".

## Lo que falla en el loop con el motor

Pocas, y ninguna es de razonamiento:

- **El esquema del motor es demasiado complejo para escribirlo bien siempre.**
  Una vez armó mal la consulta del G305, el motor no encontró nada y el modelo
  dijo que no lo tenía. Otra vez inventó un filtro de switch que dejó afuera a
  los mecánicos.
- **El buscador tiene huecos de vocabulario.** "DDR5" contra el campo ram da
  cero. Es el mismo error que comete producción: el hueco es del buscador, no
  del camino.
- Suma plata él mismo en vez de pedir la cuenta: la cifra está bien, pero no
  viene de una herramienta.
- Sin la regla dura del final inventó los DPI; con la regla, no.
- Entre dos corridas iguales cambian cuáles fallan: con charlas de varios
  turnos y resultados largos aparece algo de azar aun a temperatura baja.

## Lo que se decide con esto

1. **El camino que conversa con herramientas le gana a producción** en la
   misma vara, con el mismo buscador y el mismo modelo.
2. **La herramienta tiene que ser más simple que el esquema del motor.**
   Varias herramientas chicas —producto por nombre, buscar por rubro,
   envío, política, compatibilidad, cuenta— sobre los mismos adentros del
   motor. El simulado, que tiene esa forma, no se equivocó al escribirlas.
3. **El buscador tiene que avisar cuando un filtro deja cero**, con lo que
   hay sin ese filtro, en vez de devolver vacío. Un vacío el modelo lo lee
   como "no tenemos".
4. **La plata la escribe una herramienta**, siempre.

## Lo que sigue

- Las herramientas chicas sobre el motor, y la misma vara por el loop.
- El aviso de filtro vacío en el buscador, y el vocabulario de RAM.
- Si gana, el loop entra a producción en un commit que borra el camino viejo,
  y se mide por el clon antes del deploy.
