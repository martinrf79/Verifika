# ARRANQUE — cómo se abre cada sesión de trabajo

**Regla única: una ficha, una sesión, y la sesión se cierra.**
El estado vive en el repo, no en la memoria de ningún chat. Nadie tiene que
recordar nada: se lee esto, se hace una ficha, se cierra.

---

## Bloque para pegar al abrir una sesión nueva (Cowork o Claude Code)

```
Repo: github.com/martinrf79/Verifika (rama main).
Leé en este orden y nada más: RESUMEN_PARA_NUEVO_CHAT.md, DECISIONES.md,
arquitectura/README.md, PLAN_RECORTE.md, ARRANQUE.md.
Corré pytest y anotá los dos contadores: tests/plan_techo.json y
tests/a_medias_techo.json.
Soy Martín, escucho por transcriptor: contestame en prosa plana, corto.
Código sólo dentro de un bloque, y sólo si es una consigna a ejecutar.
Prioridad uno, no negociable: el bot vende y alucina lo menos posible.
Si sabe, contesta; si es ambiguo, repregunta; si no sabe, dice que no sabe.
Un detalle nunca tira una venta.
Esta sesión hace UNA sola ficha, la que sigue en la lista de abajo.
No reescribas documentos enteros por una corrección chica.
```

---

## Las fichas que faltan, en orden

Cada una se toma sola. No se empieza la siguiente hasta que la batería está
verde y el techo bajó.

| # | qué hace | cómo se sabe que está |
|---|---|---|
| ~~10~~ | ~~salida baja de 18 nodos a 4~~ | **HECHA el 24-ago.** 4 puertas en `app/core/salida.py`, `hub_venta.py` bajó 953 líneas, batería verde y piso intacto |
| ~~11~~ | ~~las seis reposiciones se funden en una~~ | **HECHA el 24-ago.** Una puerta en `app/core/reposicion.py`, `hub_venta.py` bajó de 2.665 a 1.798 líneas, batería verde y piso intacto |
| 12 | `registrar()` en las seis etapas, no sólo en salida | el censo se rehace solo, sin espías a mano |

Las fichas 10 y 11 eran las que bajaban el costo de cada sesión, y lo bajaron:
leer `hub_venta.py` costaba unos 47.000 tokens **cada vez** con 3.621 líneas.
Hoy tiene 1.798, y las otras dos mitades se leen sólo cuando se las toca.

---

## Las reglas que ya se pagaron caro y no se rediscuten

1. El umbral se cambia en su propio commit, **antes** del trabajo que lo hace
   pasar, y con la aritmética escrita.
2. El que implementa nunca reescribe la vara.
3. Un test tiene que afirmar **cuántos casos corrió** (si no, pasa por vacío).
4. El tope de largo **baja de escalón** y no vuelve a subir.
5. Todo paso o filtración se convierte en un test rojo `xfail(strict=True)`,
   con prefijo `A MEDIAS:` (empezado) o `PLAN:` (no empezado).
6. Se cierra lo prohibido, no lo permitido.
7. La identidad la decide el código, nunca el modelo. `ambiguous` obliga a
   preguntar.
8. `grabar_casetes.py` **sin argumentos graba todos los guiones**. Nombralos.

---

## Por qué esta modalidad

Una conversación larga se reenvía entera en cada mensaje: el costo no depende
del largo de la respuesta sino del largo del hilo. Cortar el hilo es la única
economía real. Este archivo es lo que hace que cortarlo no cueste nada.
