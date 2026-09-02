# LOS CASOS DE ORO — la vara por capa

Nacen del paso 0 de `arquitectura/BRIEF_MOTOR_V2.md`. Existen porque medir de
punta a punta con casetes fallo dos veces: un casete graba lo que el modelo
DIJO, incluso cuando lo dijo mal, y despues la bateria verde confirma un
comportamiento equivocado. Y cuando el vivo falla, nadie sabe en que capa se
perdio el dato, asi que se le echa la culpa al modelo.

**Cada capa tiene su vara propia, con la ENTRADA escrita a mano y la SALIDA
escrita a mano.** Ninguna depende de lo que el modelo haya dicho en otra
corrida.

    capa 2  RESOLVER   entrada: el `declarado` correcto   salida: que material trae
    capa 4  COMPUERTA  entrada: un texto con datos inventados   salida: que se corta
    capa 5  CIERRE     entrada: estado + respuesta del cliente  salida: que decide

Las capas 1 y 3 no tienen casos de oro aca: son del modelo y se miden en vivo.

## UN CASO DE ORO NO SE REGRABA NUNCA

Se corrige A MANO. Si el codigo cambia y un caso se pone rojo, lo que esta mal
es el codigo, salvo que el requisito haya cambiado de verdad — y entonces el
commit que edita el caso lo explica. Editar un caso para que pase es
exactamente lo que estos archivos existen para impedir.

## COMO SE CORRE

    python3 banco_pruebas/oro.py            # las tres capas, offline y gratis
    python3 banco_pruebas/oro.py --capa 2   # una sola
    python3 banco_pruebas/oro.py --fijar    # refija el piso (solo si SUBIO)

El piso vive en `banco_pruebas/oro_piso.json` y lo cuida
`tests/test_oro.py`: si baja, el CI lo grita.

## QUE DICE CADA CAMPO

Todo caso tiene `id`, `de` (de cual de las 40 sale), `que` (que mide, en una
linea) y `espera`. **Lo que no se declara en `espera` no se juzga**: cada caso
mira lo suyo y nada mas, asi un rojo señala una cosa sola.

### capa 2 — `declarado` es la entrada

`espera` acepta:

    ids                 ids que TIENEN que salir certificados del turno
    ids_prohibidos      ids que no pueden salir
    sin_marca           ninguna marca de esta lista puede aparecer
    categorias          todo producto devuelto cae en una de estas
    cuenta              true si el turno tiene que armar un Total
    total_ars           el total exacto, cuando se sabe a mano
    bloque_contiene     pedazos que tienen que estar en el bloque de la cuenta
    temas               temas certificados con material que tienen que estar
    envios              localidades que tienen que quedar cotizadas
    orden               {campo, direccion} que la busqueda derivada tiene que llevar
    cubre               renglones del declarado que TIENEN que traer material
    no_cubre            renglones que NO pueden darse por cubiertos

Un renglon se nombra `<campo>:<n>`, con `n` empezando en 1: `items:1`,
`temas:2`, `contradicciones:1`. Es el mismo nombre que usa `indice_turno`.

### capa 4 — `texto` es la entrada

`material` dice de que fuente dispone el turno: `productos` son ids del
catalogo real —el runner les trae la ficha de la fuente, no de una grabacion—,
`temas` son temas de la FAQ y `bloque` es la cuenta que armo el codigo.

`espera` acepta:

    corta       pedazos que NO pueden sobrevivir al pasaje por la compuerta
    conserva    pedazos que SI tienen que sobrevivir

`conserva` no es decoracion: una compuerta que borra todo tambien "corta" el
dato inventado, y eso es enmudecer al bot, que es peor que la alucinacion.

### capa 5 — `estado` es la entrada

`espera` acepta cualquier clave de la decision: `dispara_lead`,
`es_no_interesado`, `pide_cobro`, `medio_pago`, `faltantes`, `cobro_contiene`,
`cobro_no_contiene`.
