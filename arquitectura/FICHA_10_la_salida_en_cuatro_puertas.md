# FICHA 10 — La salida baja de 18 nodos a 4

> **No se borró ni una comprobación.** Lo que se cortó son las diecisiete
> costuras. Los dos errores de plata de agosto no vivían adentro de una pieza:
> vivían entre dos, con las dos en verde.

---

## EL DEFECTO, EN UNA LÍNEA

Dieciocho guardias en fila sobre el texto del modelo, cada una con su `G.paso`
en `procesar_venta`, y **el orden entre ellas —que es donde estaba el defecto—
no estaba escrito en ningún lado: era el orden en que quedaron.**

---

## POR QUÉ NO SE BORRÓ NINGUNA

`PLAN_RECORTE.md` habilita borrar lo que no impide una mentira falsificable, y
nueve de las dieciocho no intervienen sobre el corpus. **No están muertas: el
corpus no tiene un CBU falso ni un "sos un bot".** El propio plan lo avisa dos
párrafos más abajo. Cambiar defensa contra la alucinación por prolijidad es lo
contrario de la prioridad uno, así que las dieciocho siguen corriendo.

---

## LAS CUATRO PUERTAS — `app/core/salida.py`

Cada una contesta **una** pregunta sobre el mismo mensaje, y por eso no se
pisan:

```
PROCEDENCIA  ¿de donde salio cada dato?     8 piezas. Lo que no vino del
                                            material del turno, no sale.
PLATA        ¿quien calculo este numero?    4 piezas. La cuenta la arma el
                                            codigo y viaja entera.
OBLIGACION   ¿que tiene que estar si o si?  3 piezas. La UNICA que suma.
HIGIENE      ¿como se lee?                  2 piezas. No decide sobre la
                                            verdad del mensaje.
```

Tres restan y una suma, y ese reparto es el que fija el orden: primero se saca
lo que no puede estar, después se pone lo que falta, y al final se mira el
mensaje entero **una sola vez**.

**El único movimiento real de orden** es que la plata pasó de correr tercera a
correr última entre las que restan. Hasta hoy el bloque sellado de la
calculadora quedaba pegado con cinco podas de prosa corriendo detrás; ninguna lo
rompió, pero la única razón era que ninguna miraba renglones de cuenta, y eso no
estaba escrito en ninguna parte. Ahora, cuando el bloque se pega, no queda
ninguna poda atrás que lo pueda tocar.

**El cierre bajó a la etapa `memoria`.** Nunca verificó nada del texto: graba el
lead y pega los datos de cobro. Era el único nodo de salida sin contrato
mecánico, o sea una excepción que había que escribir cada vez que alguien
contaba los contratos; en su etapa la excepción desaparece.

---

## LO QUE NO SE PERDIÓ

**El veredicto por engranaje.** Cada pieza sigue pasando por `G.paso` adentro de
su puerta, así que se sigue midiendo cuál tocó el mensaje —comparando el texto,
no preguntándole a la pieza— y `peso_de_la_cadena.py` ve el mismo detalle.

**La red anti-mudo.** `G.paso` por pieza también significa que una pieza que
levanta no se lleva puesto el trabajo de las otras siete de su puerta.

---

## CÓMO SE SABE QUE ESTÁ

Las tres condiciones del `README.md` de esta carpeta, y las tres cerradas:

1. **Su test pasa.** `test_la_salida_tiene_cuatro_nodos_o_menos`, sin marca, y
   el techo del `PLAN` bajó de 5 a 4. El barrido del cableado corre las cuatro
   puertas contra el corpus generado en los dos regímenes del turno: **cero
   violaciones de contrato** —ni enmudecen, ni inventan plata, ni levantan, y
   son idempotentes—.
2. **Ningún número del piso bajó.** 496 puntos sobre 500, largo máximo 1.614,
   dos llamadas. Las 19 charlas grabadas siguen en verde y el marcador de
   `las_40.py` da 40 de 40.
3. **La charla completa sigue andando**, que es lo único que ve las juntas.

Y un número que no era el objetivo pero salió del corte: la pieza más pisada de
la cadena bajó de **81,8% a 45,8%** de solapamiento, y `hub_venta.py` pasó de
3.621 líneas a 2.668.

---

## LO QUE QUEDA PARA LA 11

Las seis reposiciones. `hub_venta.py` sigue teniendo la mitad que decide, y la
cuenta que arman `_cuenta_con_lo_declarado` y `_bloque_presupuesto` la llama
`salida.py` por import perezoso: cuando la 11 las funda, esa ida y vuelta se
puede mirar de nuevo.
