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

> ## REGLA CERO BIS — `git fetch` ANTES DE TOCAR NADA
>
> Comprobá que `HEAD` es `origin/main`. Si no lo es, **PARÁ**.
> Pasó dos veces trabajar una sesión entera sobre un árbol viejo: el 3-ago, y
> el 26-ago con un checkout **56 commits atrás**, parado en la FICHA 06
> mientras el remoto iba por la 19. Las dos veces hubo que rehacer todo.
>
> **Y a la tercera se arregló la causa, que era el propio hook de arranque.**
> Hacía `checkout main` + `merge --ff-only origin/main`, y el merge lleva
> `|| true`: cuando el `main` local es la historia **sin ancestro común** que
> trae el snapshot de la imagen del contenedor, el merge se niega en silencio y
> el hook igual imprimía *"se pasó a main automáticamente"*. Intentar no es
> comprobar. Ahora **verifica** que `HEAD` sea `origin/main`, y según por qué no
> lo es hace una cosa distinta: si no hay ancestro común y el árbol está limpio
> es el snapshot viejo y lo **corrige solo**; si hay commits propios o cambios
> sin commitear puede ser trabajo real, así que **no toca nada y PARA**.
> El candado es `tests/test_hook_arranque_arbol_viejo.py`, que corre el bloque
> real contra seis árboles armados a mano.

---

## Bloque para pegar al abrir una sesión nueva (Cowork o Claude Code)

```
Repo: github.com/martinrf79/Verifika (rama main).
git fetch && git status. Si HEAD no es origin/main, PARÁ y avisá.
Leé en este orden y nada más: ARRANQUE.md, DECISIONES.md,
arquitectura/README.md. Corré pytest y anotá tests/plan_techo.json y
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

## LO QUE RESTA — cinco cosas, al 26-ago

| # | qué | por qué importa |
|---|---|---|
| **21** | **la línea del cobro mata la oferta** | REGRESIÓN VIVA. El texto que estampa `camino_cobro` dice "link de pago" y "tu nombre", literales de `_RE_CERRANDO`: `punto_de_oferta` da el turno por CERRANDO, apaga la oferta y deja `pendientes` vacío, así que **no la difiere, la mata**. Son 4 ofertas sobre 15 charlas, entre ellas el K120 de `71 t3`. Causa de fondo: **código leyendo el texto que escribió el propio código como si lo hubiera escrito el modelo** |
| 22 | el `SIN_ESTADO` que no debería existir | La FICHA 09 declaró que ningún punto sale sin estado y salen igual. Hambrea a `NO_SE_SABE` —2 casos en 55— y traba el cierre de `62` y `63`, que llegan al total y nunca cobran porque **todos** sus turnos con total repreguntan algo |
| 23 | el modo degradado | Si el decisor se cae, el cliente recibe "estoy con mucha demanda". Es el único agujero que no tira un detalle: tira la venta **y el cliente** |
| 24 | las tres guardias sin auditar | `honestidad_bot`, `punto_omitido`, `aduana`. Las tres con 0/54. De cuatro auditadas, **tres estaban ciegas**: la presunción es ciega hasta que se pruebe lo contrario |
| 25 | el motor multi-tienda | Los tres `PLAN:` escritos: el id de la tienda fuera del código, los prompts a la fuente, y la TIENDA CERO de otro rubro adentro del repo. Es lo que convierte "adaptable en horas" de promesa en hecho. Va último a propósito |

Menores anotados: congelar la vara de `test_puerta_determinista`, que da rojo
falso en cada regrabación porque compara el código contra lo que declaró el
modelo; y `el_detalle_no_mata`, que perdió la mitad del denominador y no se
toca hasta cerrar el `SIN_ESTADO`.

---

## Las fichas hechas

| # | qué hizo | evidencia |
|---|---|---|
| ~~10~~ | salida baja de 18 nodos a 4 | 4 puertas en `salida.py`, `hub_venta.py` −953 líneas |
| ~~11~~ | las seis reposiciones se funden en una | `reposicion.py`; `hub_venta.py` 2.665 → 1.798 |
| ~~12~~ | `registrar()` en las seis etapas | el censo vive en `grafo.registrar()`, 39 nodos sobre 54 turnos |
| ~~13~~ | el primer número de VENTA | `vara_de_venta.py`: cinco números sin juez y sin modelo. El primer contador que **sube** |
| ~~15~~ | el punto de OFERTA | punto sintético abierto por código, exigido por `puede_salir`. El prompt no creció un byte |
| ~~16~~ | el cuarto freno + el detector estricto | los 3 que ofrecían encima de su propia pregunta y los 4 falsos dejan de contar |
| ~~16B~~ | los dos agujeros de la 16 | ceder ahora DIFIERE (`oferta_diferida`); la ventana del ancla es el mensaje, con subjuntivo |
| ~~17~~ | regrabar el corpus | 15 de 15 con la clave gratis. `avance` 29→33, `no_se_frena` 33/33, `OFRECIDO` 14→23. Cinco varas rotas contadas como `A MEDIAS:`, ninguna aflojada |
| ~~18~~ | el enclítico, la alucinación y el turno complejo | pagó 4 A MEDIAS de 5. Largo 1.652 → **1.570**, `una_sola_repregunta` **55/55**, puntos 495 → 498 |
| ~~19~~ | el camino al cobro | `camino_al_cobro` 8/15 → **10/15**. `sin_cobro_inventado` estaba medio ciega: 5 de 7 formas pasaban. Y el candado de las excepciones: en las guardias de salida quedan **cero** `except` que atrapan y siguen |
| ~~20~~ | auditar los engranajes ciegos | 3 ARREGLADAS, 1 PROBADA. `sin_descuento_inventado` 6 de 8 pasaban, `sin_negar_lo_traido` 6 de 8, `sin_json` 4 de 7. Y un rojo falso vivo: `sin_negar_lo_traido` borraba la aclaración honesta y le vendía una RAM de 8 a quien pidió 16 |

---

## Las reglas que ya se pagaron caro y no se rediscuten

0. **Se pushea al cerrar la sesión, siempre.** Y **`git fetch` al abrirla.**
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
   sobre: prueba que el corpus no dijo esas frases. **Ese censo mide cobertura
   del corpus, no utilidad del nodo.** De cuatro guardias auditadas, tres
   estaban ciegas.
10. Si un número da 100% a la primera, sospechá del denominador antes que del
    bot. `el_detalle_no_mata` dio 4/4 sobre cuatro casos.
11. **Una ficha no cierra dejando más `A MEDIAS:` de los que pagó**, salvo que
    Martín lo autorice en esa misma sesión. Al cerrar se dice en el reporte
    cuántas se pagaron y cuántas quedaron.
12. **Un rojo falso que mutea es peor que el defecto que caza.** Tres veces una
    guardia contra la alucinación se comió una aclaración honesta. Toda guardia
    nueva se prueba por los dos lados: las formas del defecto **y** las frases
    legítimas que no puede tocar.
13. **El código no lee como modelo lo que escribió el código.** Una puerta
    posterior que estampa texto no puede cambiar cómo se juzga lo que dijo el
    modelo. Es la causa de la ficha 21.

---

## Por qué esta modalidad

Una conversación larga se reenvía entera en cada mensaje: el costo no depende
del largo de la respuesta sino del largo del hilo. Cortar el hilo es la única
economía real. Este archivo es lo que hace que cortarlo no cueste nada.
