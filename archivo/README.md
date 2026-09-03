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

### `archivo/tests_apagados/` — la batería vieja, apagada el 2-sep-2026

**73 archivos, 15.464 líneas.** No se borró ninguno: si mañana hace falta uno,
se vuelve con `git mv` y corre igual.

**Por qué se apagaron.** Medido el 2-sep contra el árbol de main: 36.984 líneas
de test contra 22.061 de `app/`, 1.209 tests en verde, y el bot sin contestar
bien una pregunta de dificultad media-alta. De 966 definiciones, 120 no miraban
nunca lo que recibe el cliente —candados sobre archivos `.md`, sobre el hook de
git, sobre el guard de ramas, sobre el propio arnés— y el test más lento de toda
la batería, 10,71 segundos, verificaba que un inventario en `.md` coincidiera
con el código. En todo el repo había **14 asserts** que afirmaban que el bot
contestó lo que le preguntaron.

Y los casetes eran un circuito cerrado: `grabar_casetes.py:252` calcula el piso
reproduciendo la grabación recién hecha, y `test_charlas_grabadas.py:170` exige
que ese número no baje. La salida grabada del modelo producía el número, y el
test exigía que el número no bajara. Un error que ninguna guardia cazaba quedaba
consagrado adentro del piso. Estaba escrito con todas las letras en
`tests/oro/README.md:4` desde antes.

**Qué se quedó, y por qué.** 31 archivos, 6.433 líneas, 429 tests en 13,5
segundos contra 208. Dos grupos y nada más:

- **`tests/test_oro.py` y los 65 casos de `tests/oro/`** — entrada y salida
  escritas a mano, nunca regrabadas. Es la única vara del repo que mide la nueva
  prioridad 1b, que interprete y responda bien, y es con la que se midió que la
  capa 2 da 32 de 40 **con la interpretación perfecta**: o sea que 8 de los
  fallos son de cableado y no del modelo.
- **Los tests de las herramientas deterministas que se quedan** — calculadora,
  envío, pago, geo_cp, cierre, filtros, herramientas, compatibilidad, fuente,
  curadas, índice, familias, prosa de la casa, y las puertas de entrada del
  webhook. Son las piezas que hacen posible la respuesta: apagar su red sería
  quedarse sin nada justo en lo que se conserva.

**Lo que se apagó con esto, y hay que saberlo:** los dos techos, `A MEDIAS` y
`PLAN`, ya no los cuida nadie —vivían en `test_a_medias.py`—; el candado de
`PENDIENTE.md`; el candado de que los `.md` no mientan sobre el modelo; y la
medición de regresión de las 15 charlas grabadas. `banco_pruebas/` no se tocó:
sigue entero y `python3 banco_pruebas/oro.py` corre offline y gratis.

### `archivo/plomeria_apagada/` — el hub y sus cuatro puertas, 3-sep-2026

**7 modulos, 7.442 lineas.** `hub_venta.py`, `salida.py`, `mensaje.py`,
`indice_turno.py`, `grafo.py`, `atadura_prosa.py` e `invariantes.py`, mas el
`__init__.py` del paquete `app/verifika/`, que quedo vacio.

Los reemplaza **`app/core/turno.py`**, que hace el turno entero de punta a punta
usando **`app/core/tabla.py`**. Se vuelve con `git revert` del commit que los
movio: el camino viejo esta completo, no se toco una linea.

**Por que se apagaron y no se recortaron.** Entre la segunda llamada al modelo y
el mensaje al cliente corrian 23 piezas a nivel puerta y 46 mutadores contando
los internos, todos reescribiendo prosa que el modelo ya habia escrito. Dos de
ellos hacian lo contrario entre si sobre el mismo bloque, uno detras del otro en
el mismo turno: `mensaje.sin_cuenta_que_no_cambio` resumia la cuenta a una linea
y `salida.asegurar_cuenta_si_abrio` la reponia entera.

Y no era arreglable pieza por pieza, porque la causa era el reparto: el codigo
calculaba punto por punto que habia preguntado el cliente y que material tenia
para cada uno, **no se lo pasaba al modelo**, le mandaba un volcado crudo mas un
reto en prosa al final del prompt, y despues le parcheaba el texto que volvia.
Vigilar prosa libre no tiene fondo: fueron 4 nodos, despues 18, despues 46.

Ahora el modelo devuelve la mesa llena, con esquema, y el codigo la arma. Las
reglas dejaron de ser guardias y pasaron a ser la forma del formulario:

```
plata inventada    no hay casilla donde escribir un numero de plata
punto omitido      hay una casilla por punto y el esquema las pide todas
dos preguntas      `pregunta_final` es un campo, no una lista
dato inventado     si la fuente no lo tiene, el material sale VACIO
identidad elegida  `ambiguo` sale como pregunta CON los candidatos
```

**Lo que NO se apago, porque era comportamiento y no plomeria**, y se mudo entero
en vez de dejarse morir: `indice_turno.puntos` esta ahora en `tabla.py` -era la
unica de sus 1.738 lineas que abria los puntos del turno-; `invariantes.pago_parcial`
esta en `pago.py` con su regex tal cual; y la puerta al modelo -`_cliente`,
`_modelo` y los tres del decisor- vive en `llm_reintento.py`, que ya era el unico
lugar por donde pasan las dos llamadas. Esa ultima mudanza saco de un movimiento
los tres ciclos de import que `cierre`, `memoria_larga` y `main` escondian con un
import perezoso adentro de una funcion.

**Lo que queda pendiente y hay que saberlo:** los 10 casos de oro de la capa 4
miden `salida.procedencia` y `salida.plata`, que estan aca adentro, y su campo
`texto` viene con las etiquetas `<d ID>` de la atadura. La capa 4 quedo sin
mecanismo que medir y esta declarada como `xfail` estricto en `tests/test_oro.py`
con el detalle de cual caso ya cubre la estructura y cual hay que reescribir.
Reescribir un caso de oro es decision de Martin.

**Tamaño, medido:** `app/` paso de 51 archivos y 22.547 lineas a 45 y 16.794.
