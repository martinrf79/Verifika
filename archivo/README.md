# ARCHIVO — capas apagadas, no se ejecutan, se borran cuando el bot esté robusto

Esta carpeta **no es `reserva/`**. La reserva es código puro, que compila, que
un día se puede volver a enchufar. Acá va lo contrario: copias de capas que
**salieron del camino vivo** y se guardan hasta que el piso de las 15 charlas
no baje. Después se borran. Git las sigue teniendo.

No deploya. Está en `.gcloudignore` y en `paths-ignore` de `deploy.yml`.

## Las tres reglas

1. **`app/` no importa `archivo/`.** Si hace falta una función, se copia a
   `app/` con su prueba, no se llama desde acá. Lo defiende
   `tests/test_archivo.py`.
2. **Lo de acá no corre.** No se importa, no se testea como camino vivo, no
   hace falta que compile. Es un snapshot con fecha.
3. **Cada archivo tiene fila en la tabla.** Sin fila no entra. Cuando el piso
   aguante y Martín lo pida, se borra el archivo y la fila juntos.

## Qué hay guardado

Todavía nada. La FICHA 34, cuando apague el reconciliador y la reposición del
camino vivo, deja acá el snapshot con la fecha del commit.

| archivo | qué era | se borra cuando |
|---|---|---|
| *(vacío)* | — | — |

## Qué NO va acá

Barridos, casetes, el índice del turno, la calculadora, `certificar_producto`,
`filtros_catalogo`. Eso es el motor. Si entra acá, se apagó de más.
