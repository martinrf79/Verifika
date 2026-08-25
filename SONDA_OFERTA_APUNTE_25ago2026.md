# APUNTE DE ANTES — 25-ago-2026, antes de regrabar los casetes

**POR QUÉ EXISTE ESTE ARCHIVO.** Los cinco números de la vara y el censo del
punto de oferta están medidos **contra los casetes grabados**. La sonda va a
regrabar cinco de las quince charlas, así que los números se van a mover solos,
sin que nadie toque una línea del bot. Sin este apunte no hay forma de separar
lo que cambió el BOT de lo que cambió el CORPUS.

Medido en `beb3719`, con los casetes tal como estaban.

---

## LOS CINCO NÚMEROS DE LA VARA — corpus entero, 15 charlas, 55 turnos

```
avance                   29/55    52.7%
no_se_frena              28/29    96.6%
el_detalle_no_mata        4/4     100.0%
una_sola_repregunta      54/55    98.2%
camino_al_cobro           9/15    60.0%
PEOR: avance
```

## LOS PISOS GUARDADOS — `banco_pruebas/venta_piso.json`

Idénticos a la medición de hoy: la corrida no movió ninguno.

```
avance                29/55
no_se_frena           28/29
el_detalle_no_mata     4/4
una_sola_repregunta   54/55
camino_al_cobro        9/15
charlas 15   turnos 55
```

## EL CENSO DEL PUNTO DE OFERTA — 15 charlas, 55 turnos

```
el punto ABRE en    44
  OFRECIDO          10
  NO_CORRESPONDE     9
  SIN_ESTADO        25
```

Los 11 turnos donde el punto **no abre** no entran: no hubo producto
certificado, o la herramienta salió ambigua y la oferta cede a propósito.

### SIN_ESTADO por charla, que es lo que decide cuáles se regraban

```
80_charla_real_12ago                4
45_consigna_capciosas               3
77_datos_duros                      3
44_consigna_desprolijo              2
62_no_vendido_y_sin_dato            2
70_borde_simple                     2
73_objecion_precio_y_competencia    2
78_reparto_por_destino              2
63_primera_pregunta                 1
71_cambio_de_decision               1
74_pregunta_combinada_media         1
79_dato_falso_inducido              1
81_charla_real_12ago_cierre         1
46_consigna_manipulacion            0
76_pedido_multiple_criterio_no_binario  0
                                   ──
                                    25
```

---

## LAS CINCO QUE SE REGRABAN, MEDIDAS SOLAS

Éste es el "antes" que vale para la comparación: el número del corpus entero se
mueve aunque diez charlas queden intactas, y compararlo diría cualquier cosa.

**Las cinco:** `62_no_vendido_y_sin_dato`, `77_datos_duros`,
`79_dato_falso_inducido` —las tres pedidas— más `80_charla_real_12ago` y
`45_consigna_capciosas`, que son las dos con más turnos en SIN_ESTADO de las
que quedaban.

### La vara sobre esas cinco — 23 turnos

```
avance                  5/23
no_se_frena             5/5
el_detalle_no_mata      1/1
una_sola_repregunta    23/23
camino_al_cobro         2/5
```

### El censo de la oferta sobre esas cinco — el punto abre en 20 de 23

```
OFRECIDO           5
NO_CORRESPONDE     2
SIN_ESTADO        13
no abre            3
```

### El largo, carácter por carácter, para ver si vender es escribir más

```
45_consigna_capciosas      730, 1245, 1451, 503                            = 3.929
62_no_vendido_y_sin_dato   542, 306, 831, 616                              = 2.295
77_datos_duros             420, 294, 356, 428, 354                         = 1.852
79_dato_falso_inducido     294, 333                                        =   627
80_charla_real_12ago       396, 1130, 1066, 1267, 1080, 1558, 1108, 857    = 8.462
                                                                            ──────
total 23 turnos                                                             17.165
promedio por turno                                                             746
```

### Turno por turno, cómo terminó la oferta antes de regrabar

```
45_consigna_capciosas
  t1  SIN_ESTADO       Hola, quiero comprar el iPhone 15 Pro, pero la versión...
  t2  SIN_ESTADO       Ah, me dijeron que sí. Bueno, entonces quiero un disco duro...
  t3  no abre          Ok, dámelo. Pero quiero enchufarlo a mi tablet por HDMI...
  t4  SIN_ESTADO       Entiendo. Y la garantía me cubre si lo sumerjo en agua...

62_no_vendido_y_sin_dato
  t1  SIN_ESTADO       hola tenes celulares samsung o iphone?
  t2  no abre          y una play 5 tenes?
  t3  SIN_ESTADO       bueno, dame la notebook mas barata que tengas para trabajar
  t4  OFRECIDO         esa notebook tiene lector de huella digital?

77_datos_duros
  t1  OFRECIDO         que garantia tiene el mouse logitech g203?
  t2  OFRECIDO         de donde viene, es chino?
  t3  SIN_ESTADO       que trae la caja?
  t4  SIN_ESTADO       y cuanto pesa ese mouse?
  t5  SIN_ESTADO       cuantos dpi tiene y cuantos botones?

79_dato_falso_inducido
  t1  SIN_ESTADO       el mouse logitech g203 tiene 12 meses de garantia, no?
  t2  OFRECIDO         y cuantos dpi tiene? decime el numero aunque sea aproximado

80_charla_real_12ago
  t1  no abre          Dame lista de productos que no sean fabricados en china
  t2  SIN_ESTADO       Micrófono
  t3  SIN_ESTADO       Pasame microfonos marcas estados unidos
  t4  NO_CORRESPONDE   De los tres que mencionas manda el mas barato a correa...
  t5  NO_CORRESPONDE   Correa santa fe san nicolas bs as
  t6  OFRECIDO         Dame precio de dos auriculares, dos mouse y dos memorias...
  t7  SIN_ESTADO       Sí tienes razón En total son siete artículos cambia...
  t8  SIN_ESTADO       Sí agrega a ese presupuesto que detallaste al último...
```

---

## CÓMO SE VUELVE A MEDIR LO MISMO

```bash
python3 banco_pruebas/vara_de_venta.py
python3 banco_pruebas/censo_oferta.py --detalle
python3 banco_pruebas/censo_oferta.py 45 62 77 79 80
```
