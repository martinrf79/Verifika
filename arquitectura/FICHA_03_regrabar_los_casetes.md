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

## ARCHIVOS QUE SE TOCAN

```
banco_pruebas/casetes/*.json    las 15 grabaciones
banco_pruebas/casetes/_piso.json el piso nuevo
```

**NO DEPLOYA:** `banco_pruebas/**` está en `paths-ignore` desde el 21-ago.

## ARCHIVOS QUE NO SE TOCAN

```
app/            NINGUNO. Si esta unidad toca app/, esta mal.
tests/          ninguno
```

## LA CLAVE

**La GRATIS, y no se consulta.** `CLAUDE.md` es explícito: la gratis es el default
para bancos, está disponible, y ninguna sesión tiene que frenar un trabajo por
falta de clave. Es más lenta y a veces devuelve 429: **se aguanta y se reintenta.**

**PROHIBIDO** poner `BANCO_CLAVE_PAGA=true` o exportar la paga en un script. Hay
candado en `tests/` y Martín lleva gastados unos cuarenta dólares casi todo en
corridas de banco que no necesitaban la paga.

## CÓMO SE VERIFICA

```bash
# 1. regrabar NOMBRANDO los guiones, de a pocos    ← ver la trampa 1
python3 banco_pruebas/grabar_casetes.py 70_borde_simple.txt 71_cambio_de_decision.txt

# 2. el numero, sobre el corpus nuevo
python3 -m pytest tests/test_charlas_grabadas.py -q

# 3. nada roto
python3 -m pytest -q
```

## LAS TRAMPAS CONOCIDAS

**1. LA QUE YA COSTÓ UNA RESTAURACIÓN CON GIT.** `grabar_casetes.py` **sin
argumentos graba TODOS los guiones.** La última vez creó **65 casetes de más** y
hubo que restaurar con git. Hoy hay 94 guiones en la carpeta y solo 15 casetes:
correrlo pelado grabaría 79 de más **y gastaría la cuota diaria de la clave
gratis**, que son 500 requests. Se nombran los guiones. Siempre.

**2. La cuota gratis es DIARIA, no por minuto.** Son 500 requests por día y un
turno gasta de 2 a 4. Las 15 charlas son unos 55 turnos, o sea entre 110 y 220
requests: **entra, pero sin margen para regrabar dos veces el mismo día.** Si se
agota a mitad de la tanda —ya pasó— se para y se sigue al día siguiente con los
que faltan, **no se cambia a la paga.**

**3. El piso baja antes de subir, y hay que no asustarse.** Mientras la tanda
esté a medias hay casetes nuevos conviviendo con viejos, y el número global puede
dar cualquier cosa. **El piso se refija UNA sola vez, con las 15 regrabadas, no
de a una.**

**4. Un casete regrabado puede tapar un defecto real.** Si una charla que estaba
en rojo pasa a verde después de regrabar, hay que mirar POR QUÉ: si es porque el
corpus viejo cobraba una llamada que ya no existe, está bien; si es porque el
modelo esta vez contestó mejor por azar, el rojo seguía siendo real. **Un run no
es un veredicto**, y eso ya está escrito en `banco_pruebas/README.md`.

## CÓMO SE VUELVE ATRÁS

`git revert`. Los casetes viejos quedan en el historial. Como no toca `app/`,
revertir no puede afectar a un cliente.

---

## LO QUE VIENE DESPUÉS

```
FICHA 03  linea de base limpia                              ← esta
FICHA 04  el molde gana las 4 familias Y el modelo pasa a ver UNA
          herramienta. Un solo movimiento, como marco Claude Code:
          los campos nuevos no se SUMAN a los 25 KB, los REEMPLAZAN.
FICHA 05  cada punto termina con un estado terminal
FICHA 06  la cobertura deja de ser log y pasa a ser PUERTA
```

**La 04 es la de mayor riesgo del plan hasta ahora** y cierra tres pasos de una:
una sola herramienta visible, el esquema abajo de 6 KB, y —por fin— el número
REAL de omisión en vez del piso disfrazado que tenemos hoy.
