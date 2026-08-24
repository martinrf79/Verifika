# FICHA 07 — Destrabar el nocturno de calidad

> **Va antes del resto del plan porque `calidad` es el único instrumento que
> corre el MODELO VIVO**, y acabamos de hacer el cambio más grande de todos sin
> una sola medición viva de si mejoró o empeoró.

---

## QUÉ ES `calidad` Y POR QUÉ IMPORTA MÁS QUE LOS OTROS

Corre `banco_pruebas/banco_repetido.py`: cada guión **N veces**, por la misma
función que atiende el webhook de WhatsApp, con el catálogo y la FAQ reales.
Compara contra `banco_pruebas/piso.json` —**un piso distinto** del de los
casetes— y se pone rojo si `sin_caida` o `sin_invento` caen más de cinco puntos.

Todo lo demás que tenemos es **replay de grabaciones**. Y la regla del propio
repo dice: *"un run no es un veredicto. Nunca. Ni el bueno ni el malo."* Los
casetes son **un** run por charla. `calidad` es el que repite.

**Lo que está en juego:** el modelo pasó de ver nueve herramientas a ver una, y
de 25.230 bytes a 5.936. Los números offline mejoraron todos. **Pero no hay
ninguna medición con el modelo vivo de si esa mejora aguanta cuando el modelo
decide de verdad**, repetidas veces, en vez de repetir lo que dijo una vez.

## EL PRECEDENTE, y está escrito en el propio workflow

> *"El nocturno quedó cuatro noches en rojo llamando a un archivo que ya no
> existía."*

**Una compuerta que queda roja deja de ser compuerta y pasa a ser ruido**, y
después nadie la mira. Hoy está roja sobre `1fe10c9`, que es previo al cambio.

## QUÉ SE PIDE — y el paso uno NO es arreglarla

**PASO UNO: saber QUÉ MIDE EL ROJO.** Corre con el modelo vivo y la clave
gratis, así que un rojo tiene tres causas posibles con tres arreglos **opuestos**:

```
A. CALIDAD DE VERDAD   una metrica dura cayo. Es un defecto y se arregla.
B. CUOTA               429 o quota agotada a mitad de la corrida. El numero
                       no vale y no se toca nada del bot.
C. PISO VIEJO          `piso.json` se fijo con la arquitectura anterior,
                       igual que le pasaba a `casetes/_piso.json`. Se
                       refija, y NO es aflojar la vara si se explica.
```

**No se toca nada hasta saber cuál de las tres es.** Confundirlas es exactamente
cómo se afloja una vara creyendo que se arregla un defecto.

Se lee del log de la corrida en Actions: qué métrica cayó, cuánto, y si hubo
errores de cuota.

**PASO DOS: la corrida sobre el código de HOY.** El rojo es de `1fe10c9`, previo
a la puerta única. Hay que dispararla a mano —`workflow_dispatch`, que el
workflow ya tiene— sobre el commit actual, y ahí recién se sabe si el cambio
grande mejoró o empeoró la calidad viva.

**PASO TRES: dejarla verde**, con el arreglo que corresponda a la causa.

## EL NÚMERO

```
HOY       `calidad` en rojo, causa sin diagnosticar, sobre codigo viejo
OBJETIVO  verde sobre el codigo de hoy, con las cuatro metricas de
          `piso.py` medidas y el motivo del rojo anterior escrito
```

## LA CLAVE

**LA GRATIS.** El workflow ya usa `GEMINI_API_KEY`. La cuota es diaria y
`banco_repetido` corre cada guión **varias veces**, así que **esto sí puede
agotarla**: es de las pocas cosas que gastan de verdad.

**Correr con POCOS guiones y POCAS vueltas la primera vez.** El
`workflow_dispatch` recibe los dos parámetros justamente para eso. Medir con dos
guiones y dos vueltas antes de largar la tanda entera.

**Si se agota, se para y se sigue mañana.** No se cambia a la paga: `CLAUDE.md`
es explícito y el banco vivo con repeticiones es de los pocos casos donde SÍ se
podría pedir la paga — pero se **pide a Martín**, no se toma.

## ARCHIVOS QUE SE TOCAN

```
banco_pruebas/piso.json        SOLO si la causa es C, y explicando por que
.github/workflows/calidad.yml  solo si el defecto esta ahi
app/                           SOLO si la causa es A
```

**Si la causa es B, no se toca NADA** y se vuelve a correr. Un número sacado con
la cuota agotada no es un número.

## QUÉ NO PUEDE ROMPERSE

```
casetes/_piso.json    496 puntos, largo 1.614, llamadas 2
la bateria            991 passed, cero rojos
plan_techo            7           a_medias_techo  0
```

## LA TRAMPA PRINCIPAL

**Refijar `piso.json` porque está rojo es la salida fácil y casi siempre la
equivocada.** Ya pasó el reflejo inverso con los casetes: el piso decía 491, la
regrabación dio 489, y refijarlo habría tapado un defecto vivo de prioridad uno
—el turno que cerraba sin Total—. **Se refija solo cuando se puede explicar por
qué el número viejo ya no aplica**, y esa explicación va en el commit.

Y la segunda: **`banco_repetido` mide con el modelo vivo, o sea que tiene
varianza.** Dos corridas del mismo código dan números distintos. Por eso el
workflow repite: una sola corrida verde no prueba que esté arreglado, igual que
una sola roja no prueba que esté roto.

## CÓMO SE VUELVE ATRÁS

`git revert`. Si la causa resultó ser A y el arreglo toca `app/`, vale todo lo de
siempre: el push se consulta y el piso de los casetes manda.

---

## LO QUE VIENE DESPUÉS

```
FICHA 08  cada punto termina con un estado terminal
FICHA 09  la cobertura deja de ser log y pasa a ser PUERTA
```

Y los dos pasos que achican `hub_venta.py` —la salida de 18 nodos a 4, y las seis
reposiciones a una— siguen abiertos. **Son los que bajan el costo de token por
sesión**, porque hoy el archivo son 3.548 líneas y `CLAUDE.md` obliga a leerlo
entero antes de editarlo.
