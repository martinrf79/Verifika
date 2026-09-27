# FICHA 51 — El fantasma del hub: `estado_venta`, `calculate_total` y las varas que los miden. ABIERTA.

**Abierta el 12-sep-2026, con el censo del cableado ya midiendo.** Es la unidad
de trabajo viva. Se lee entera antes de tocar nada.

---

## EL PROBLEMA, en una línea

Quedó un módulo entero sosteniendo un mundo que no existe, y hay varas
midiéndolo, así que el repo no se da cuenta.

---

## LOS TRES HECHOS, medidos y verificables hoy

**1. `app/core/estado_venta.py` —417 líneas— aporta un diccionario vacío.**
Nadie llama `set_current_estado` en el camino vivo. Por lo tanto
`get_current_estado()` devuelve `{}` **siempre**, y todo lo que `calculadora`
le pide a ese módulo es esa nada. Son **15 de las 29 puntas** que cuenta
`python3 banco_pruebas/censo_cableado.py`.

**2. `calculate_total` no la llama nadie desde `app/`.** La cuenta quedó
huérfana del camino vivo cuando el turno pasó a sumar con el hueco `{{total}}`
de `app/core/numeros.py`. Es la función principal de un archivo de casi mil
líneas.

**3. Hay varas que miden ramas muertas.** `tests/test_envio.py::
test_localidad_ambigua_resuelve_con_provincia_del_estado` setea el estado a
mano para medir una capacidad que en producción no corre desde el apagón. No es
la única: hay que buscarlas.

---

## LO QUE YA SE INTENTÓ Y POR QUÉ NO ALCANZÓ

El 12-sep se sacaron las dos muletas muertas de `cotizar_envio`. **El censo
subió**: al irse los lectores, más funciones de `estado_venta` quedaron sin
llamador. Se revirtió.

**La lección, que es la regla de esta ficha: un corte a medias empeora el
cableado.** O se saca el racimo entero —módulo, lectores y varas— o no se
empieza. El techo de `banco_pruebas/cableado_techo.json` lo frena en el mismo
push, y está para eso.

---

## LO QUE SÍ SE HIZO, y es el molde a repetir

La localidad ambigua más la provincia de la charla —"Los Cóndores" con Córdoba
dicho dos turnos antes— estaba escrita en `cotizar_envio` leyendo el estado
muerto. Ahora vive en `fuente.texto_envio`, donde la provincia sale de
`ultima_localidad`, que el turno escribe de verdad.

**Ése es el molde: no se borra una capacidad, se la muda a donde el dato existe.
Y recién ahí se borra el original.**

---

## EL ORDEN, y ninguno de los pasos se saltea

1. **Inventariar qué capacidades REALES viven en el racimo.** Cada rama que lee
   `get_current_estado` es una capacidad escrita. Para cada una, dos preguntas:
   ¿el dato existe hoy en otro lado —`conv`, la memoria del turno—, y hay una
   vara que la mida de verdad?
2. **Mudar las que tengan dato vivo**, una por una, con su caso en
   `tests/test_turno_nuevo.py`, como se hizo con la localidad ambigua.
3. **Decidir qué pasa con `calculate_total`.** Es plata, y la decisión es de
   Martín: o se enchufa al turno nuevo, o se apaga con el resto. No se toca sin
   esa decisión.
4. **Recién entonces borrar** `estado_venta.py` y sus lectores, en un solo
   commit, con el censo bajando de 29 a 14 o menos.
5. **Y las varas que medían el mundo muerto se reescriben sobre el camino vivo
   o se apagan por escrito.** Una vara que mide lo que no corre es peor que no
   tener vara: da verde y tapa el agujero.

---

## LO QUE NO SE TOCA

La guarda de procedencia. El motor. El bloque de envío. La memoria con id y
precio. `data/clientes/`. El renglón `motor_turno`. El censo y su techo.

---

## CÓMO SE SABE QUE TERMINÓ

Tres números, y los tres tienen comando:

```
python3 banco_pruebas/censo_cableado.py     de 29 baja a 14 o menos
python3 -m pytest -q                        sigue verde, y no por haber borrado varas
python3 banco_pruebas/tanda_viva.py         9 de 11 o mejor, con la clave gratis
```
