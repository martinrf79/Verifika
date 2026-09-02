# EL CORPUS REGRABADO — FICHA 17, 25-ago-2026

Compará contra `APUNTE_ANTES_FICHA17.md`, que se midió en `8804ad8` con las
grabaciones del 24-ago. Acá están las quince charlas regrabadas por el camino
vivo, en dos tandas, con la clave gratis.

**Las dos tandas.** A: `62`, `77`, `79`, `80`, `45` — las cinco con más turnos
sin ofrecer. B: las otras diez. Ninguna se cortó: el candado del enlatado no
llegó a disparar.

---

## LOS CINCO NÚMEROS DE LA VARA

```
                       antes      después
avance                 29/55  →   33/55     +4      52.7% → 60.0%
no_se_frena            28/29  →   33/33     +5      96.6% → 100.0%
el_detalle_no_mata      4/4   →    2/2      igual, denominador más chico
una_sola_repregunta    54/55  →   53/55     −1      98.2% → 96.4%   ROJO
camino_al_cobro         9/15  →    9/15     igual   60.0%
```

`avance` era el peor y sigue siendo el peor, pero subió cuatro turnos.
`no_se_frena` llegó a 33 de 33: cuando hay carrito vivo, el bot propone el paso
siguiente **siempre**.

`el_detalle_no_mata` bajó de 4 casos a 2, y eso no es una caída: es que hoy hay
menos turnos con un punto en `NO_SE_SABE`. La fracción es la misma y el candado
del denominador sigue verde.

## EL CENSO DEL PUNTO DE OFERTA

```
                       antes      después
el punto abre en        37    →    33
  OFRECIDO              14    →    23      +9
  NO_CORRESPONDE        10    →     6
  SIN_ESTADO            13    →     4      −9
no abre                 18    →    22
```

### La pregunta que abrió la ficha: cuántos de los que no ofrecían ahora ofrecen

Cruzando turno por turno —mismo guion, mismo número de turno— **de los 13 que
estaban `SIN_ESTADO`, 10 pasaron a `OFRECIDO`**:

```
44_consigna_desprolijo t2          62_no_vendido_y_sin_dato t1
62_no_vendido_y_sin_dato t3        63_primera_pregunta t1
70_borde_simple t1                 73_objecion_precio_y_competencia t3
74_pregunta_combinada_media t2     78_reparto_por_destino t2
79_dato_falso_inducido t2          80_charla_real_12ago t2
```

De los otros tres: uno pasó a `NO_CORRESPONDE` (`62 t4`, el turno cierra), uno
dejó de abrir (`80 t8`) y uno sigue sin ofrecer (`70 t2` — pero ver abajo: ese
**sí** ofrece y el detector no lo cuenta).

Y dos que ya contaban por otro lado: `44 t3` y `44 t4` pasaron de
`NO_CORRESPONDE` a `OFRECIDO`.

### Los tres que fueron para atrás

`NO_CORRESPONDE` → `SIN_ESTADO`: `70 t3`, `71 t3`, `81 t3`. De los tres, dos
—`70 t3` y `81 t3`— **ofrecen y el detector no los ve**. El único
empeoramiento real es **`71_cambio_de_decision` t3**: tenía el Teclado Logitech
K120 para proponer y cerró con "¿Te gustaría confirmar este pedido o necesitás
ayuda con algo más?", sin nombrarlo.

## EL LARGO

```
                    antes      después
máximo              1.614  →   1.652     SUBE, y no puede            ROJO
promedio              743  →     766
total 55 turnos    40.899  →   42.153
```

Los dos que pasan el escalón: `76_pedido_multiple_criterio_no_binario` t2 con
1.652 y `45_consigna_capciosas` t3 con 1.639. Los dos son el mismo caso: pedido
de varios rubros con reparto y pago dividido, donde el bot explica en prosa y
después repite el presupuesto entero.

Turno por turno:

```
44_consigna_desprolijo                 528, 846, 734, 554                       = 2.662
45_consigna_capciosas                  649, 1168, 1639, 1154                    = 4.610
46_consigna_manipulacion               128, 667, 724, 920                       = 2.439
62_no_vendido_y_sin_dato               475, 382, 781, 321                       = 1.959
63_primera_pregunta                    425, 432                                 =   857
70_borde_simple                        403, 529, 564, 946                       = 2.442
71_cambio_de_decision                  515, 611, 416, 941                       = 2.483
73_objecion_precio_y_competencia       570, 1477, 948                           = 2.995
74_pregunta_combinada_media            1254, 757, 656                           = 2.667
76_pedido_multiple_criterio_no_binario 1055, 1652                               = 2.707
77_datos_duros                         363, 185, 217, 168, 410                  = 1.343
78_reparto_por_destino                 1061, 831                                = 1.892
79_dato_falso_inducido                 220, 243                                 =   463
80_charla_real_12ago                   441, 963, 1159, 1229, 1075, 1250, 1043, 1315 = 8.475
81_charla_real_12ago_cierre            1163, 932, 663, 1401                     = 4.159
```

`77_datos_duros` bajó de 1.852 a 1.343 y ofrece en los cinco turnos: contestar
el dato duro y proponer el paso siguiente sale más corto que antes, no más
largo.

## EL PISO DE LOS CASETES

```
                    antes      después
puntos             496/500  →  495/500     −1                        ROJO
llamadas_max            2   →       2      igual
```

El punto perdido son dos turnos nuevos —`62` T2 y `71` T4— contra dos que se
cerraron: los dos bloques repetidos que tenía `81`.

## LA PUERTA SIN MODELO

```
                              antes      después
turnos de referencia            53    →    54
items                        85.3%   →   83.9%                       ROJO
destinos                     63.6%   →   53.8%
reparto_pago                 16.7%   →   12.5%
turnos con el pedido entero  73.9%   →   71.4%
```

**Esto es CORPUS, no BOT.** Este banco compara el código determinista contra el
`registrar_pedido` que declaró el modelo, y al regrabar el modelo declaró otros.
No cambió una línea del código determinista. Que un piso se mueva solo cada vez
que se regraba es en sí mismo el defecto, y va anotado como tal.

---

## LO QUE SE ROMPIÓ, Y NINGÚN PISO SE BAJÓ

Cinco varas rojas, cinco `xfail(strict=True)` con prefijo `A MEDIAS:`, y el
techo de `tests/a_medias_techo.json` subió de 0 a 5 en su propio commit, con las
cuentas. Ningún piso ni techo se movió para que algo pase.

```
tests/test_charlas_grabadas.py::test_el_mensaje_no_se_alarga
tests/test_charlas_grabadas.py::test_el_numero_no_baja
tests/test_vara_de_venta.py::test_los_puntos_a_medias_vuelven_al_piso
tests/test_puerta_determinista.py::test_lo_que_el_codigo_entiende_sin_modelo_no_puede_bajar
tests/test_ficha16_freno_y_detector.py::test_el_pronombre_pegado_al_verbo_no_tira_la_oferta
```

La vara de venta **no se marcó entera**: el punto roto salió a su propio test y
los otros cuatro siguen defendidos, porque son los que subieron. Hay un candado
—`test_lo_marcado_a_medias_es_parte_de_la_vara_y_nada_mas`— que impide sacar
otro punto de la vigilancia sin que se note.

## EL DEFECTO DEL DETECTOR, AISLADO

`OFRECIDO` es un piso y nunca la prueba de que no se ofreció. Leyendo los 32
turnos que el contador no cuenta aparecieron tres que ofrecen sin ninguna duda:

```
70_borde_simple t2   "Si te interesa, puedo cotizarte el Mouse Logitech M170
                      Negro que ya te había mencionado anteriormente."
70_borde_simple t3   "Si te interesa, puedo cotizarte el Mouse Logitech M170
                      Negro que te mencioné anteriormente."
81_..._cierre t3     "Como ya conoces los Auriculares Redragon Zeus X Blanco,
                      ¿querés que proceda a cargarlos en tu presupuesto actual
                      para que los evaluemos?"
```

Las mismas frases con el pronombre **suelto** —"puedo cotizar el Mouse…",
"¿querés que los cargue…?"— ya cuentan hoy. Lo que falla es el **verbo**: el
pronombre enclítico —`cotizarte`, `cargarlos`— lo rompe antes de que el detector
llegue a buscar el producto. La 16B había arreglado la anáfora suelta; ésta
entra por otra puerta.

**El número real, entonces: `OFRECIDO` 26 y `SIN_ESTADO` 1, no 23 y 4.** El
único `SIN_ESTADO` legítimo es `71 t3`.

No se arregla en la sesión que lo encuentra: subiría `OFRECIDO` de 23 a 26 sobre
el mismo corpus, y un número que sube porque el que mide tocó el detector en la
misma sesión no se puede leer.

---

## CÓMO SE VUELVE A MEDIR TODO ESTO

```bash
python3 -m pytest -q
python3 banco_pruebas/vara_de_venta.py
python3 banco_pruebas/censo_oferta.py --detalle
python3 banco_pruebas/censo_oferta.py --ofertas      # el texto de los que SI cuentan
python3 banco_pruebas/censo_oferta.py --sin-estado   # el texto de los que NO
python3 banco_pruebas/puerta_determinista.py
```
