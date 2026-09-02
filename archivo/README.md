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
| `herramientas_20260902.py` | las seis puertas viejas todavía como `def` público; el vivo ya entra por cuatro `_CUERPOS` | el piso no baje con los seis cuerpos como helpers privados y alias para tests |
| `invariantes_20260902.py` | el termómetro completo en `app/verifika/` | el piso no baje con `_RE_ITEM` y `pago_parcial` en el vivo y `revisar` en el banco |
| `llm_adapter_20260902.py` | el adaptador de ocho proveedores; el vivo habla por `hub_venta._cliente` | el piso no baje con una sola puerta al modelo |
| `config_providers_20260902.py` | claves y `*_thinking_off` de proveedores que no son Gemini | el piso no baje con Gemini como única puerta |

## Qué NO va acá

Barridos, casetes, el índice del turno, la calculadora, `certificar_producto`,
`filtros_catalogo`. Eso es el motor. Si entra acá, se apagó de más.


## PASO 1 DEL RECORTE DEL 2-SEP — lo que estaba alrededor de `app/`, no adentro

`arquitectura/PLAN_RECORTE_2SEP.md` midio que en `app/` NO hay codigo muerto:
el 94% de las funciones corren en cada turno. Lo que hacia grande e ilegible al
repo era lo de alrededor. Esto es eso, movido entero y sin tocar `app/`.

Efecto colateral bueno: la imagen de Docker deja de llevar los bancos viejos,
porque el Dockerfile copia `data/` entera.

Se borran todos juntos cuando el motor V2 este en verde y el piso de las 15
charlas no baje. Hasta entonces git los sigue teniendo igual.

### `archivo/instrumentos/` — bancos que ya no contesta nadie

| archivo | qué era |
|---|---|
| `banco_atado_charlas.py` | banco que ataba las charlas grabadas a su declaración |
| `charla_sim.py` | simulador de charla anterior al explorador |
| `duelo_interprete.py` | el duelo entre el intérprete viejo y el de hoy, ya resuelto y anotado adentro de `herramientas` |
| `fiscalizador.py` | auditoría de turnos anterior al banco de producción |
| `peso_reposicion.py` | midió a mano el 44% de `cuenta_repuesta`; hoy lo mide el grafo, y `tests/test_plan_del_recorte.py` guarda el número |

### `archivo/scripts_viejos/` — scripts de una sola vez

| archivo | qué era |
|---|---|
| `planilla_specs.py` | volcó las specs a planilla cuando se armó el catálogo |
| `planilla_compatibilidad.py` | lo mismo para la tabla de compatibilidad |
| `generar_embeddings.py` | embeddings de la búsqueda semántica, que ya no se usa |

### `archivo/datos_viejos/` — los bancos de `data/` que no son fuente

Salieron todos los archivos de `data/` que no viven en `data/clientes/` ni en
`data/geo/`, que son las dos fuentes vivas. Son juegos de preguntas y de
escenarios de bancos ya retirados: `_h21`, `_s3`, `_serv_shadow`, `_serv_trap`,
los `molino_*`, los `preguntas_*`, los `escenarios_*`, `casos_reales`,
`comprension_casos`, `mini_check`, `mini_prompt`, `productos_prod`, `puentes` y
`solver_casos`. **La fuente NO se toco**: el catálogo, la FAQ y las tarifas
siguen en `data/clientes/<tienda>/`, con su candado en `INVENTARIO_FUENTE.md`.

### `archivo/documentacion/` — apuntes de una ficha ya cerrada

`APUNTE_ANTES_FICHA17.md`, `APUNTE_DESPUES_FICHA17.md` y
`SONDA_OFERTA_APUNTE_25ago2026.md`. Se citan entre ellos y a nadie más.

### `archivo/config_viejo/` — presets de caminos que ya no existen

`camino_nuevo.env`, `columna_simple.env`, `llm_carritos.env` y
`maquina_determinista.env`. Prendían combinaciones de flags de las que hoy no
queda ninguna: un repo, un camino vivo, cero flags sueltas.
