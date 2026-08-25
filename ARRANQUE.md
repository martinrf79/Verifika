# ARRANQUE — cómo se abre cada sesión de trabajo

**Regla única: una ficha, una sesión, y la sesión se cierra.**
El estado vive en el repo, no en la memoria de ningún chat. Nadie tiene que
recordar nada: se lee esto, se hace una ficha, se cierra.

> ## REGLA CERO — SE PUSHEA AL CERRAR, SIEMPRE
>
> El contenedor se recicla. **Lo que no está en `origin` no existe.**
> Se pushea al terminar la sesión, aunque quede a medias, aunque sea feo.
> El 25-ago se dio por perdida una grabación entera y seis commits por esto;
> se recuperaron de casualidad porque el contenedor viejo seguía vivo.
> Antes de abrir una sesión nueva, la anterior tiene que haber pusheado.

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
PUSHEÁ ANTES DE CERRAR, aunque quede a medias.
```

---

## Las fichas, en orden

Cada una se toma sola. No se empieza la siguiente hasta que la batería está
verde y el contador se movió.

| # | qué hace | cómo se sabe que está |
|---|---|---|
| ~~10~~ | ~~salida baja de 18 nodos a 4~~ | **HECHA el 24-ago.** 4 puertas en `app/core/salida.py`, `hub_venta.py` bajó 953 líneas, batería verde y piso intacto |
| ~~11~~ | ~~las seis reposiciones se funden en una~~ | **HECHA el 24-ago.** Una puerta en `app/core/reposicion.py`, `hub_venta.py` bajó de 2.665 a 1.798 líneas, batería verde y piso intacto |
| ~~12~~ | ~~`registrar()` en las seis etapas~~ | **HECHA el 24-ago.** El censo vive adentro de `grafo.registrar()` y `peso_del_censo.py` dejó de envolver nada: mide 39 nodos sobre 54 turnos, con candado en `tests/test_censo_del_grafo.py` |
| ~~13~~ | ~~el primer número de VENTA~~ | **HECHA el 25-ago.** `banco_pruebas/vara_de_venta.py`: cinco números sobre el estado del turno, sin juez y sin modelo. Es el primer contador que **sube** |
| ~~15~~ | ~~el punto de OFERTA~~ | **HECHA el 25-ago.** Punto sintético abierto por código en `indice_turno`, con estados terminales y exigido por `puede_salir`. El prompt no creció un byte |
| ~~16~~ | ~~el cuarto freno + el detector estricto~~ | **HECHA el 25-ago.** Cuarto freno en `punto_de_oferta` y `_RE_PRONOMBRE` borrado; sobre los 15 casetes de la sonda `OFRECIDO` baja de 16 a 7, los 3 que ofrecian encima de su propia pregunta y los 4 falsos ya no cuentan, y el piso de venta quedo intacto |
| ~~16B~~ | ~~los dos agujeros que dejó la 16~~ | **HECHA el 25-ago.** Ceder ahora DIFIERE: la oferta pendiente vive en `oferta_diferida` y el turno siguiente reabre el punto sin herramienta nueva. Y la ventana del ancla es el MENSAJE inmediato, con el subjuntivo adentro: `OFRECIDO` vuelve de 1 a 14 en el corpus viejo y da 22 en la sonda, con los cuatro falsos afuera |
| 17 | regrabar el corpus | recién con 16B verde. Antes es pagar la grabación dos veces |
| 18 | el modo degradado | hoy, si el decisor se cae, el cliente recibe "estoy con mucha demanda". No se cae un detalle: se cae la venta y el cliente |
| 19 | `camino_al_cobro` | 6 de 15 charlas terminan sin que el bot diga nunca cómo se paga |

Las fichas 10, 11 y 12 eran las que bajaban el costo de cada sesión, y lo
bajaron: leer `hub_venta.py` costaba unos 47.000 tokens **cada vez** con 3.621
líneas. Hoy tiene 1.812, y las otras dos mitades se leen sólo cuando se tocan.

---

## Las reglas que ya se pagaron caro y no se rediscuten

0. **Se pushea al cerrar la sesión, siempre.** Ver la regla cero, arriba.
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
9. Un **0 sobre 54** en un nodo de vocabulario cerrado no prueba que el nodo
   sobre: prueba que el corpus no dijo esas frases. `sin_narracion_interna` dio
   0/54 y aun así dejó pasar "el cliente pide" al cliente. **Ese censo mide
   cobertura del corpus, no utilidad del nodo.**
10. Si un número da 100% a la primera, sospechá del denominador antes que del
    bot. `el_detalle_no_mata` dio 4/4 sobre cuatro casos.
11. **Una ficha no cierra dejando más `A MEDIAS:` de los que pagó**, salvo que
    Martín lo autorice en esa misma sesión. Marcar es diferir trabajo, y una
    ficha que difiere más de lo que cierra deja el contador más arriba de como
    lo encontró. La 17 tuvo esa autorización —la regrabación destapó cinco de
    un saque y el techo subió de 0 a 5—; las que siguen, no. Al cerrar se dice
    en el reporte cuántas se pagaron y cuántas quedaron.

---

## Por qué esta modalidad

Una conversación larga se reenvía entera en cada mensaje: el costo no depende
del largo de la respuesta sino del largo del hilo. Cortar el hilo es la única
economía real. Este archivo es lo que hace que cortarlo no cueste nada.
