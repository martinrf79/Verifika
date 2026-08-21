# FICHA 03 — Regrabar los 15 casetes y refijar el piso

> **Esta ficha no estaba en el plan y la trajo la FICHA 02.** Al cerrarla se
> midió que las cuatro familias nuevas **no se abren en ninguna charla real**:
> 190 puntos y 24 sin contestar, exactamente los mismos de antes del cambio.
>
> **Va antes del molde por una trampa que arruinaría la medición.** Ver abajo.

---

## QUÉ SE PIDE

Regrabar los 15 casetes con el código de hoy, y volver a fijar el piso sobre esa
grabación nueva.

## POR QUÉ VA ANTES DEL CAMBIO GRANDE — la trampa

**El piso está medido contra casetes viejos.** Se grabaron con la arquitectura de
cuatro rondas, y `PENDIENTE.md` ya lo registra: faltan dos puntos —de 493 a 491—
que **no son una regresión**, sino que el corpus castiga al turno nuevo por no
consumir una llamada que ya no hace.

Ahora viene el cambio grande: el molde gana cuatro familias y el modelo pasa a
ver una sola herramienta. Si eso se hace **y** se regraba en el mismo movimiento,
y un número baja, **no hay forma de saber cuál de las dos cosas lo bajó.**

> Ese es exactamente el momento en que se cuela una regresión disfrazada de
> ruido. Dos variables moviendo el mismo número al mismo tiempo no es una
> medición, es una opinión.

Primero se limpia la línea de base. Después se mide el cambio contra ella.

## CÓMO SE VE DESDE EL CLIENTE

**No se ve. No se toca `app/`.** Esta unidad solo regraba material de prueba.

## EL NÚMERO

```
HOY       piso 491 puntos sobre 15 casetes grabados con 4 rondas
OBJETIVO  493 o mas, sobre casetes grabados con el turno de hoy.
          Los dos puntos que faltan se recuperan; no son regresion.
```

Probado ya una vez: regrabada sola con la clave gratis,
`81_charla_real_12ago_cierre` pasa de ser el rojo a 100 sobre 100 y el reparto de
envíos vuelve a resolver.

## ⚠️ LA CONDICIÓN QUE IMPORTA: **CERO HUECOS**

Esto manda sobre el número del piso, y es el motivo por el que esta ficha puede
salir mal sin que nada se ponga rojo.

**Si un 429 se escapa, el casete queda grabado con un turno faltante.** Y
`test_charlas_grabadas.py` trata los turnos con hueco de forma especial: **no los
juzga** —saltea el chequeo del enlatado, porque el modelo nunca habló en ese
turno—. O sea que **un hueco degrada el corpus en silencio y la batería sigue
verde.**

Sería peor que no regrabar: menos cobertura creyendo que hay más. Y encima justo
antes de la FICHA 04, que es la más riesgosa del plan y **se mide contra este
corpus**. Un corpus con huecos convierte esa medición en una opinión.

```bash
# los huecos se MIRAN, no se asumen
python3 -c "
import sys; sys.path.insert(0,'.')
from banco_pruebas import sim_firestore; sim_firestore.install()
from banco_pruebas.casete import CASETES, reproducir_charla
tot=0
for p in sorted(CASETES.glob('*.json')):
    if p.name.startswith('_'): continue
    h = reproducir_charla(p).get('huecos') or []
    if h: print(p.stem, h); tot += len(h)
print('HUECOS TOTALES:', tot)"
```

**`HUECOS TOTALES: 0` o la ficha no cierra.** Si aparece alguno, se regraba ese
casete solo —nombrándolo— y se vuelve a contar.

## LA CLAVE: LA GRATIS, Y NO SE CONSULTA

**El motivo principal no es el costo:** gratis y paga son **el mismo modelo**
—`config.py` declara un solo `GEMINI_MODEL`—, así que lo que cambia es la cuota y
la velocidad, **no la salida**. Pagar no mejora la grabación.

La cuenta: 15 charlas son ~55 turnos por 2 llamadas = **~110 requests**, contra
**500 diarias** de la gratis. Entra cuatro veces. Lo que pasó antes —que se agotó
a mitad de tanda— tenía dos causas que ya no existen: el banco y producción
compartían la clave gratis, y el turno tenía **cuatro** rondas.

**PROHIBIDO** poner `BANCO_CLAVE_PAGA=true` o exportar la paga en un script. Hay
candado en `tests/`, y de los ~40 dólares que Martín gastó en un mes, casi todo
fueron corridas de banco que no la necesitaban.

**Cuándo SÍ se pide la paga**, para que quede dicho: el banco vivo con
repeticiones —medir si el modelo mejoró o empeoró corriendo lo mismo cinco
veces— y las pruebas reales por WhatsApp. Grabar casetes, no.

## ARCHIVOS QUE SE TOCAN

```
banco_pruebas/casetes/*.json     las 15 grabaciones
banco_pruebas/casetes/_piso.json el piso nuevo
```

**NO DEPLOYA:** `banco_pruebas/**` está en `paths-ignore` desde el 21-ago.

## ARCHIVOS QUE NO SE TOCAN

```
app/            NINGUNO. Si esta unidad toca app/, esta mal.
tests/          ninguno
```

## CÓMO SE VERIFICA

```bash
# 1. regrabar NOMBRANDO los guiones, de a pocos    <- ver la trampa 1
#    con pausa, para no gatillar 429 en rafaga
BANCO_PAUSA_S=8 python3 banco_pruebas/grabar_casetes.py 70_borde_simple.txt 71_cambio_de_decision.txt

# 2. CERO HUECOS  <- la condicion dura, ver arriba

# 3. el numero, sobre el corpus nuevo
python3 -m pytest tests/test_charlas_grabadas.py -q

# 4. nada roto
python3 -m pytest -q
```

## LAS TRAMPAS CONOCIDAS

**1. LA QUE YA COSTÓ UNA RESTAURACIÓN CON GIT.** `grabar_casetes.py` **sin
argumentos graba TODOS los guiones.** La última vez creó **65 casetes de más** y
hubo que restaurar con git. Hoy hay 94 guiones en la carpeta y solo 15 casetes:
correrlo pelado grabaría 79 de más **y se comería la cuota diaria entera**. Se
nombran los guiones. Siempre.

**2. La cuota gratis es DIARIA.** 500 requests por día. Las 15 charlas entran con
margen, **pero no alcanza para regrabar dos veces el mismo día.** Si se agota a
mitad de la tanda —ya pasó— se para y se sigue al día siguiente con los que
faltan; **no se cambia a la paga.**

**3. El piso baja antes de subir, y hay que no asustarse.** Mientras la tanda
esté a medias hay casetes nuevos conviviendo con viejos, y el número global puede
dar cualquier cosa. **El piso se refija UNA sola vez, con las 15 regrabadas.**

**4. Un casete regrabado puede tapar un defecto real.** Si una charla que estaba
en rojo pasa a verde después de regrabar, hay que mirar POR QUÉ: si es porque el
corpus viejo cobraba una llamada que ya no existe, está bien; si es porque el
modelo esta vez contestó mejor por azar, el rojo seguía siendo real. **Un run no
es un veredicto**, y ya está escrito en `banco_pruebas/README.md`.

## CÓMO SE VUELVE ATRÁS

`git revert`. Los casetes viejos quedan en el historial. Como no toca `app/`,
revertir no puede afectar a un cliente.

---

## LO QUE VIENE DESPUÉS

```
FICHA 03  linea de base limpia, sin huecos                  <- esta
FICHA 04  el molde gana las 4 familias Y el modelo pasa a ver UNA
          herramienta. Un solo movimiento: los campos nuevos no se
          SUMAN a los 25 KB, los REEMPLAZAN.
FICHA 05  cada punto termina con un estado terminal
FICHA 06  la cobertura deja de ser log y pasa a ser PUERTA
```

**La 04 es la de mayor riesgo del plan hasta ahora** y cierra tres pasos de una:
una sola herramienta visible, el esquema abajo de 6 KB, y —por fin— el número
REAL de omisión en vez del piso disfrazado que tenemos hoy.
