# PASO 0 — EL CENSO DE ENGRANAJES

Medido el 18-ago-2026 sobre los **15 casetes** del repo, reproducidos por el
camino vivo con el modelo reemplazado por su grabación: **54 turnos**, offline,
sin clave, sin red. Cero fallos de reproducción.

Reproducible con `paso0_censo.py` y `paso0b_reposicion.py`. Ningún archivo de
`app/` fue tocado: los espías envuelven `grafo.registrar`, `grafo.anotar` y las
seis funciones de reposición desde afuera.

---

## 1. La etapa SALIDA — 17 nodos, y 8 están muertos

| clase | nodos | qué significa |
|---|---|---|
| **MUERTO** | **8** | corrió 54 veces, intervino 0 |
| **A VECES** | 9 | acá viven los bugs reales |
| **ESTRUCTURAL** | 0 | ninguno interviene siempre |

**Los 8 muertos, con 54 oportunidades cada uno:**

```
sin_json                 54 → 0
sin_cobro_inventado      54 → 0
sin_negar_lo_traido      54 → 0
sin_narracion_interna    54 → 0
hallazgo_repuesto        54 → 0
honestidad_bot           54 → 0
punto_omitido            54 → 0
aduana                   54 → 0   (0 rojas, 0 reparadas)
```

**Los 9 que sí intervienen:**

```
atadura                  54 → 25   46%
saludo                   54 → 25   46%
componedor               54 → 25   46%
la_cuenta_y_la_plata     54 → 14   26%
bloque_repuesto          54 → 13   24%
sin_anuncio_vacio        54 →  5    9%
sin_markdown             54 →  4    7%
sin_descuento_inventado  54 →  2    4%
sin_afirmar_del_catalogo 54 →  1    2%
```

**Lectura.** Los 8 muertos no prueban que sobren —prueban que **estos 54 turnos
no los ejercitan**. Pero eso ya es un dato duro: ocho piezas que corren en cada
turno de producción y cuya única evidencia de que sirven es la charla donde
nacieron. Antes de borrarlas hay que preguntarse por cada una si su barrido la
cubre; las que no tienen barrido propio y no aparecen acá **no tienen ninguna
prueba de que funcionen**.

`sin_afirmar_del_catalogo` con 1/54 y `sin_descuento_inventado` con 2/54 son
casi muertas, y son justo dos de las que pelean entre sí.

---

## 2. El instrumento tiene un agujero: mira sólo donde no importa

El grafo declara **32 nodos**. Sólo **17 registran**.

Los otros 15 —`entrada` (2), `decision` (4), `reposicion` (6), `redaccion` (1),
`memoria` (1), `cierre` (1)— están declarados con su contrato y **nunca llaman a
`registrar()`**, porque el único que registra es `G.paso`, y `G.paso` sólo
envuelve transformaciones de texto.

> **El instrumento observa exactamente la etapa que hay que achicar, y es ciego
> en la etapa donde está el problema.**

Por eso hubo que medir la reposición envolviéndola a mano.

---

## 3. La etapa fantasma, medida por primera vez

Las seis funciones que reescriben lo que el modelo declaró, **antes** de redactar:

```
_cuenta_con_lo_declarado       54 → 24   44%
_busqueda_de_lo_declarado      54 →  7   13%
_reparto_de_pago_declarado     54 →  4    7%
_supuesto_de_pago              54 →  4    7%
_condicion_faltante_aplicada   54 →  2    4%
_bloques_a_uno                 54 →  1    2%
```

**`_cuenta_con_lo_declarado` corrige al modelo en el 44% de los turnos.** No es
una guardia: es una pieza del turno que está en el lugar equivocado.

---

## 4. EL NÚMERO DEL DÍA

```
turnos donde el modelo declaró algo que NO buscó ......  31/54  = 57%
turnos donde el reconciliador manda PREGUNTAR .........  10/54  = 19%
turnos con sin_buscar .................................   7/54  = 13%
```

**En el 57% de los turnos, lo que el modelo DECLARÓ y lo que el modelo BUSCÓ no
coinciden.**

Y esto **no contradice** que la interpretación esté robusta — la explica. La
llamada 1 hace **dos trabajos a la vez**:

1. **declarar** lo que entendió (`registrar_pedido`)
2. **elegir** qué herramientas llamar

El trabajo 1 anda bien. El trabajo 2 es el que falla, en más de la mitad de los
turnos. Y `_busqueda_de_lo_declarado` existe únicamente para parchear esa
diferencia después.

### La consecuencia, y es grande

**Si la llamada 1 sólo DECLARA, y el código deriva las búsquedas de la
declaración, el reconciliador no puede tener faltantes: no queda nada que
reconciliar.** Hay una sola fuente de verdad sobre qué buscar.

Y arrastra el problema de peso que ya tenías medido:

| | hoy | sólo declarando |
|---|---|---|
| esquema en la llamada decisora | 25.370 bytes | ~3.046 bytes (`registrar_pedido`) |
| rondas de herramientas | hasta 2 | 1, fija |

**~88% menos de peso en la llamada decisora**, y las rondas extra desaparecen
—que es donde tu propio `peso_del_turno.py` dice que se paga de más—. El enum de
129 temas deja de viajar. La optimización que tenías en el backlog sale gratis
como efecto secundario del corte arquitectónico, no como un trabajo aparte.

---

## 5. La cobertura: el contrato ya está construido, y se usa como log

`indice_turno` ya descompone cada turno en **puntos** y ya los marca `ok` /
`FALTA`. Sobre los 54 turnos:

```
puntos abiertos, total ...........................  190   (3,5 por turno)
puntos SIN MATERIAL (la fuente no trajo nada) ....   55   29%
puntos SIN CONTESTAR al terminar el turno ........   24   13%

turnos con ≥1 punto sin material .................  29/54   54%
turnos con ≥1 punto sin contestar ................  12/54   22%
```

Tres conclusiones:

1. **3,5 puntos por turno confirma que las preguntas COMPONEN.** Categorizar
   preguntas explota; descomponer en puntos, no.
2. **1 de cada 5 turnos se manda con algo que el cliente preguntó y no se
   contestó.** Ésa es la falla por omisión, medida.
3. **El único nodo que debería reponer un punto omitido —`punto_omitido`—
   intervino 0 veces en 54 turnos.** O sea que hoy la omisión no tiene defensa.

**El contrato de cobertura está el 80% escrito**: `indice_turno` calcula todo lo
necesario y después lo tira en una línea de log. Falta convertirlo de
**observación** en **puerta**.

---

## 6. Qué se desprende, en orden

1. **Llamada 1 declara, no elige herramientas.** El código deriva las búsquedas.
   Mata el 57%, mata la reposición de búsqueda, y baja el peso ~88%.
2. **`indice_turno` pasa de log a contrato.** Cada punto termina en uno de cuatro
   estados —RESUELTO / AMBIGUO→repregunta / NO SE SABE / CONFLICTO— y el turno no
   sale si algún punto quedó sin estado. Máximo una repregunta, y sólo sobre lo
   que bloquea el cobro.
3. **La cuenta sube de etapa.** `_cuenta_con_lo_declarado` interviene en el 44%:
   no es un parche, es la resolución del punto `precio`. Va en la etapa 2.
4. **Los 8 muertos se revisan uno por uno** contra su barrido. El que no tiene
   barrido ni evidencia acá, no tiene ninguna prueba de que ande.
5. **`registrar()` en las seis etapas, no sólo en salida.** Sin esto el censo hay
   que rehacerlo a mano cada vez.

---

## Aviso sobre la validez

Los casetes se grabaron con la arquitectura de cuatro rondas (lo dice
`PENDIENTE.md`), así que las cifras de **salida** son sólidas —el código de
salida corre entero y de verdad— pero las de **decisión** cargan las
herramientas que pidió el modelo grabado, no el de hoy. El 57% es un piso
razonable, no un número exacto: regrabando los 15 casetes se afina.

Ninguna de las conclusiones cambia de signo por eso.
