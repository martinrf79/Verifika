# FICHA 09 — La cobertura deja de ser un log y pasa a ser puerta

> **Es la ficha que hace que el contrato haga algo.** La 08 le puso a cada punto
> su estado terminal y dejó la omisión desnuda. Acá se decide qué hace el turno
> con ella, y la decisión se toma en una sola línea: **la puerta frena lo que
> puede PROBAR.**

---

## EL DEFECTO, EN UNA LÍNEA

El índice medía y escribía el número en el log. Nadie lo miraba a tiempo:
**"el destino no llegó al mensaje" solo se descubría leyendo una charla a mano.**

---

## QUÉ SE HIZO

`app/core/indice_turno.py` — `puede_salir(puntos)`, el veredicto, y es PURA: no
vuelve a mirar el texto ni las herramientas, así que se puede correr sobre una
charla vieja.

```
puede        False si algun punto quedo sin estado TENIENDO con que contestarse
omitidos     esos puntos. Son los que hay que reponer antes de mandar
sin_prueba   los que quedaron sin estado y sin evidencia. NO frenan, pero se
             devuelven: un numero que desaparece es un numero que nadie arregla
motivo       una linea legible para el log
```

**Un punto frena cuando pasan las dos cosas:** quedó sin estado —no se dijo, no
se preguntó, y no se dijo que no se sabía— **y** el código tenía con qué
contestarlo, o sea que hay anclaje certificado. Sin la segunda mitad la puerta
sería un adivino: frenaría el turno por algo que el sistema nunca supo, que es
otra falla y se arregla en otro lado.

**El precio es la única excepción, y la fuerza un caso real que ya estaba
escrito como test.** Su evidencia no es un texto que se pueda buscar en el
mensaje: es la cuenta, y la cuenta la arma la calculadora con ids certificados.
El caso: el cliente pregunta cuánto sale llevar dos unidades de la notebook que
venía mirando, el turno no llama a ninguna herramienta porque el producto ya está
certificado en el carrito, y el punto no tiene un solo anclaje. Exigirle uno
dejaría salir justo el turno que la guardia nació para frenar. Se le pregunta a
la calculadora, y si no puede armar la cuenta no se pega nada.

`app/core/hub_venta.py` — la guardia que SUMA, la única del turno, pasa a ser el
**actuador de la puerta**: el disparador deja de ser `faltan` —la bolsa donde
tres de cuatro casos no son un defecto— y pasa a ser lo que la puerta probó.
Repone dos cosas, y ninguna la escribe el modelo:

```
destino   la localidad CERTIFICADA, la que uso la herramienta de envio.
          "Envio a Cordoba capital, Concordia, Posadas." No afirma un peso.
precio    el bloque SELLADO de la calculadora, con ids ya certificados.
```

Y el turno cierra con el veredicto `puerta_cobertura` en la misma línea que ya
se lee, más un `turno_salio_con_omision` cuando la puerta no pudo reponer.

---

## LO QUE SE MIDIÓ, Y ES LA MITAD IMPORTANTE DE ESTA FICHA

Las 15 charlas grabadas, corridas por el camino vivo. **238 puntos.**

```
                 antes    despues
RESUELTO           178        188
AMBIGUO             15         15
NO_SE_SABE           4          4
CONFLICTO            3          3
SIN ESTADO          38         28      <- la omision
```

Y el reparto de esas 38, que es lo que decidió el diseño entero:

```
politica         20   casi todas FALSAS. Ver abajo
destino          10   REALES, y todas la misma: la omision fundadora del modulo
atributo          4   dos eran un defecto de formato, ya corregido
compatibilidad    2   no anclan a proposito: no se pueden probar
stock             1   idem
pago              1
```

**Las 20 de política son ruido de medición, no omisiones.** Un tema se contesta
con prosa y su anclaje son sus números. Dos cosas lo rompen: el nombre del tema
es vocabulario de nuestro archivero —`desconfianza_online`,
`concepto_imposible`— y no aparece jamás en un mensaje escrito para un cliente;
y cuando el tema sí tiene números, el turno contesta con el número **real** de la
cotización —$7.000— en vez del genérico de la FAQ. Las dos veces el bot contestó
bien y el índice lo marcaba omitido. Por eso `politica`, `stock` y
`compatibilidad` **nunca frenan**: la regla técnica 4 dice que lo que no se puede
mapear mecánicamente se descarta, y eso vale también para acusar.

**Las 10 de destino son reales y son todas la misma:** el cliente dice a dónde va
cada cosa, el sistema lo entiende, lo cotiza y lo guarda, y el mensaje no lo
nombra. Es la falla con la que nació el módulo el 9-ago. La puerta cerró 8; las
2 que quedan no tienen anclaje, así que salen en `sin_prueba` y no se pierden.

**El defecto de formato del atributo, que la puerta hubiera pagado caro.** La
ficha guarda `precio_ars: 12000` pelado y el mensaje escribe `$12.000`: el
anclaje no encontraba su propio número y el punto salía omitido habiendo sido
contestado en la misma oración. Se agregan **las dos** formas, nunca se reemplaza
una por la otra.

---

## CÓMO SE SABE QUE ESTÁ

```
tests/test_puerta_cobertura.py     6 tests, 9 casos declarados uno por uno
tests/test_plan_del_recorte.py     test_la_cobertura_es_una_puerta_y_no_un_log
tests/plan_techo.json              6 -> 5
casetes/_piso.json                 sin mover: 496 puntos, largo 1.614, 2 llamadas
```

Cinco de los seis tests nacieron ROJOS y se los vio rojos. El sexto —que a un
turno que preguntó no se le pega una cuenta— nació verde, y está dicho en su
docstring por qué: con el disparador viejo la guardia igual no pegaba nada,
porque sin id certificado la calculadora no puede armar la cuenta. O sea que lo
que frenaba era la regla cero, dos capas más abajo y de casualidad.

El techo baja **en este mismo commit y no antes**, porque acá no se movió una
vara: se sacó una marca que `strict=True` ya no deja puesta.

---

## LO QUE ESTA FICHA NO HACE, Y NO ES UN OLVIDO

- **No le niega el mensaje al cliente.** `DECISIONES.md` #14 —un punto sin
  resolver bloquea su renglón, NUNCA el turno— y #16 —un punto en NO SE SABE
  jamás frena el cierre—. Cambiar una omisión por un silencio es peor: **un
  detalle nunca tira una venta.** La puerta rechaza el texto como está, repone lo
  que puede, y lo que no puede lo deja marcado en el turno.
- **No vuelve a redactar.** `DECISIONES.md` #5 pide una segunda redacción con la
  violación como aviso, y hoy no se puede pagar: son dos llamadas al modelo por
  turno y el piso las tiene clavadas en 2, y los casetes no tienen grabada esa
  segunda vuelta, así que el turno saldría con el enlatado de sobrecarga.
  Regrabarlos necesita la clave paga. Queda anotado en `PENDIENTE.md`.
- **No cierra la gemela PROCEDENCIA.** Vive hoy con otro nombre —`atadura_prosa`,
  los cuatro niveles de la decisión 11—. Juntarla con el índice, para que la
  fuente sea el PUNTO y no el producto, es otra unidad de trabajo.
- **No toca el prompt.** El modelo no se entera de esto y no tiene que enterarse.
