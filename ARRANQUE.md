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
> Comprobá que `HEAD` es `origin/main`. Si no lo es, **no arranqués a laburar
> sobre ese árbol**. Qué hacer depende de por qué no lo es:
>
> - Árbol limpio, en `main`, y `git merge-base --is-ancestor HEAD origin/main`:
>   estás atrás, el fast-forward es seguro. `git pull --ff-only origin main` y
>   seguí. El 28-ago un chat de la FICHA 35 paró acá con dos commits atrás y
>   devolvió la sesión: no era el caso del 26-ago.
> - Árbol sucio, commits locales que no están en `origin`, o no hay
>   fast-forward: **PARÁ y avisá**. No se pisa trabajo.
>
> Pasó dos veces laburar una sesión entera sobre un árbol viejo: el 3-ago, y
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
> Cowork y un entorno `build` a veces no corren ese hook: por eso el bloque de
> abajo dice el fast-forward a mano.

---

## Bloque para pegar al abrir una sesión nueva (Cowork o Claude Code)

```
Repo: github.com/martinrf79/Verifika (rama main).
git fetch origin main && git checkout main && git status.
Si HEAD no es origin/main: árbol limpio y fast-forward posible →
git pull --ff-only origin main y seguí. Si el árbol está sucio, hay
commits locales que no están en origin, o no hay fast-forward: PARÁ y avisá.
Leé en este orden y nada más: ARRANQUE.md,
arquitectura/PLAN_REDUCCION.md, arquitectura/FICHA_36_el_numero.md,
DECISIONES.md.
Corré pytest -q y anotá los dos techos.
Soy Martín, escucho por transcriptor: contestame en prosa plana, corto.
Código sólo dentro de un bloque, y sólo si es una consigna a ejecutar.
Prioridad uno, no negociable: el bot vende y alucina lo menos posible.
Si sabe, contesta; si es ambiguo, repregunta; si no sabe, dice que no sabe.
Un detalle nunca tira una venta.
Esta sesión hace la FICHA 36, tercer tercio de PLAN_REDUCCION, y nada más.
reposicion.py sale de app/ si nadie la llama. Nueve cuerpos a cuatro.
Los termómetros 181 y 7306 tienen que pasar. No se toca el razonamiento
ni data/clientes. Si el piso baja, revert del corte, no un parche.
PUSHEÁ A main ANTES DE CERRAR. Toca app/: pedí el OK del push una vez,
al final. Nada de ramas.
```

---

## LO QUE RESTA — el número sale de `pytest`, no de esta tabla

El número de `PLAN:` y de `A MEDIAS:` sale de `pytest`, no de esta línea. Cada
fila de abajo es un test que existe hoy, con su ficha, salvo las que dicen
*(sin test propio todavía)*: esas no se trabajan hasta que el test exista.
**Si esta tabla nombra un `test_*` que no existe, o `pytest -rx` muestra un
`PLAN:`/`A MEDIAS:` sin fila acá, algo se desincronizó** —se arregla ese
mismo día, no se acumula. El candado está en
`tests/test_plan_de_la_simplificacion.py`.

| ficha | test | qué falta |
|---|---|---|
| **36** | `test_app_tiene_a_lo_sumo_ciento_ochenta_funciones`, `test_app_pesa_a_lo_sumo_siete_mil_trescientas_lineas` | termómetros: 181 funciones, 7306 líneas. El corte de esta sesión (reposicion y guia_pedido fuera de app/, nueve cuerpos a cuatro) no llega al 30% sin sacar certificación, calculadora o el contrato. Prioridad uno manda: no se fuerza. HOY lo mide el test. |
| 11 (cola) | `test_la_cuenta_se_arma_antes_del_reconciliador` | la cuenta se arma DESPUÉS del reconciliador, no antes. Contado entero en `arquitectura/LO_QUE_QUEDO_ABIERTO_DE_LA_11.md` |
| 11 (cola) | `test_el_bloque_hallazgo_no_vive_en_el_hub` | falta decidir de quién son `_RE_HAY_CUENTA` y `_norm_renglon` antes de mudar `_bloque_hallazgo` fuera de `hub_venta` |
| 11 (cola) | `test_los_guiones_que_despiertan_las_guardias_estan_grabados` | guiones 26 a 38 sin grabar, necesita la clave paga. **También prerrequisito parcial de la 24** |
| 11 (cola) | `test_el_piso_guarda_algun_numero_de_venta` | el piso mide 8 varas defensivas y ninguna que mida si el bot vende |
| 11 (cola) | `test_el_piso_de_la_puerta_guarda_crudo_y_no_razon` | `puerta_piso.json` guarda porcentaje, no numerador y denominador por separado |
| **22** | `test_ningun_punto_termina_con_la_casilla_vacia` | **3** puntos en `SIN_ESTADO` sobre 2 de 55 turnos, contra 24 antes. Los 21 que se cerraron eran defectos de medición; los 3 que quedan son la ficha 29 y no se pueden cerrar acá |
| **23** | `test_el_modo_degradado_puede_ver_lo_que_ya_se_sabe` | la disculpa de "mucha demanda" corre con `memoria` e `idx` en el mismo scope y no los nombra; `_sobrecarga()` no recibe ningún parámetro. Es el único agujero que tira la venta **y al cliente** |
| **24** | *(sin test propio todavía)* | auditar `honestidad_bot` y `punto_omitido` como hizo la 20 —frases reales del defecto y frases legítimas que no se pueden tocar—. Las dos con 0/54. `aduana` salió del vivo en la 35. Se puede auditar por unidad sin esperar los guiones 26-38, aunque medirlas sobre corpus real sí los necesita |
| **25** | `test_app_no_menciona_el_id_de_ninguna_tienda`, `test_los_prompts_no_viven_en_el_codigo`, `test_existe_una_segunda_tienda_de_otro_rubro` | el motor multi-tienda: el id fuera del código, los prompts a la fuente, la TIENDA CERO. Va último a propósito |
| **26** | `test_no_hay_universal_sin_herramienta_que_lo_respalde` | alucinación: un universal sobre el catálogo sale sin que ninguna herramienta lo haya mirado |
| **27** | `test_la_nota_interna_no_le_llega_al_cliente` | `sin_narracion_interna` no ve hablar del cliente en tercera persona, solo nombrar la máquina |
| **28** | `test_no_se_promete_un_dato_que_no_se_da` | un anuncio de precio, plazo o stock puede salir sin el dato abajo |
| **29** | *(sin test propio todavía)* | la anti-repetición poda el bloque de cuenta que no cambió y se lleva el reparto y el pago, que son PUNTOS. No se trabaja hasta que exista el `xfail`. Es la ficha 21 al revés |
| A MEDIAS | `test_lo_que_el_codigo_entiende_sin_modelo_no_puede_bajar` | el piso compara contra el `registrar_pedido` que declaró el modelo, y eso se mueve solo en cada regrabación. **Congelado a propósito, no se toca hasta cerrar la 22** |

**Orden: 36**, una por sesión, relato en `arquitectura/PLAN_REDUCCION.md`.
La 36 cortó el vivo (reposicion, guia_pedido, nueve a cuatro) y cerró 31 y 32.
Los termómetros no cierran: el stay-list del motor ya pesa más que 7306.
Después: Martín mira producción, y recién ahí se optimizan las
herramientas que queden y se atacan los errores de razonamiento. La 24
y la 29 no se tocan sin test.

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
| ~~21~~ | la línea del cobro mataba la oferta | `punto_de_oferta` juzga `texto_del_modelo`, la frontera que `hub_venta` guarda antes de la primera puerta. Censo de oferta **OFRECIDO 22 → 26**, `NO_CORRESPONDE` 10 → 6; la vara entera sin un solo cambio turno por turno |
| ~~31~~ | una puerta al catálogo | `_CUERPOS` con `consultar_productos`; buscar/catalogo/ficha/compat salieron |
| ~~32~~ | una puerta a la plata | `_CUERPOS` con `cotizar`; `tomar_pedido` borrado |
| ~~34~~ | el nexo: interpretar → resolver → redactar | hub sin `reconciliar(` ni `R.completar`; nace `app/core/resolver.py`; snapshot en `archivo/` |
| ~~35~~ | la puerta: un mutador, la prosa no se reescribe | higiene solo `componer`; `aduana.py` a `archivo/`; techo PLAN 18→17 |
| ~~36~~ | el número, primer corte | `reposicion.py` y `guia_pedido.py` a `archivo/`; nueve cuerpos a cuatro; techo PLAN 17→15. Los termómetros siguen: llegar a 181/7306 corta el motor |

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
