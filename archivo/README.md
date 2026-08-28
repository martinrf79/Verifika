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

La FICHA 34 dejó el primer snapshot. La 35 agregó el de aduana. La 36
copia el reposicion que todavía corre, distinto del de la 34, cuando esa
sesión lo saque del vivo. Qué se apaga y en qué sesión está en
`arquitectura/PLAN_REDUCCION.md`.

| archivo | qué era | se borra cuando |
|---|---|---|
| `reposicion_20260827.py` | la puerta de reposición: seis re-interpretaciones sobre el mismo pedido | el piso de las 15 charlas no baje después de que el resolver aplique lo declarado |
| `reconciliador_20260827.py` | `pedido.reconciliar` e `instruccion_de_preguntas`: segunda opinión sobre el mismo pedido | el piso no baje y el contrato del turno salga del índice, no de un reclamo |
| `aduana_20260828.py` | el segundo mutador de la higiene: reparaba el mensaje ya escrito | el piso no baje con un solo mutador (`componer`) y los invariantes como termómetro |
| `reposicion_vivo_20260828.py` | el reposicion que todavía corría al abrir la FICHA 36, distinto del snapshot de la 34 | el piso de las 15 charlas no baje con los helpers en el resolver y sin el archivo vivo en app/core |
| `guia_pedido_20260828.py` | el camino sellado del 8-jul; el vivo solo pedía `categorias_nombradas` y `opciones_por_categoria` | el piso no baje con esas dos funciones en `filtros_catalogo` |
| `reconciliador_vivo_20260828.py` | `pedido.reconciliar` y los helpers que solo ella usaba, al salir de `app/` | el piso no baje con una sola opinión sobre el pedido |

## Qué NO va acá

Barridos, casetes, el índice del turno, la calculadora, `certificar_producto`,
`filtros_catalogo`. Eso es el motor. Si entra acá, se apagó de más.
