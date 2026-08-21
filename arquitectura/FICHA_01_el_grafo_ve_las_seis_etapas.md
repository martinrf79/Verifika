# FICHA 01 — El grafo registra en las seis etapas

> **Va primera por una razón:** no cambia una sola línea del comportamiento del
> bot, y **hace medible todo lo que viene después.** Hoy el instrumento es ciego
> justo en la etapa donde está el problema; sin arreglarlo, cada corte posterior
> hay que medirlo a mano, como hubo que medir la reposición el 18-ago.

---

## QUÉ SE PIDE

Que las seis etapas del turno dejen marca en el grafo, no solo `salida`.

## CÓMO SE VE DESDE EL CLIENTE

**No se ve. Y es a propósito.** Esta unidad no toca el mensaje que recibe el
cliente: solo agrega observación. Si el texto de salida cambia aunque sea un
carácter, algo se hizo mal.

## EL TEST QUE HOY FALLA

```
tests/test_plan_del_recorte.py::test_el_grafo_registra_en_las_seis_etapas
```

Hoy está marcado `xfail(strict=True)`. Cuando pase, se pone ROJO por pasar: ahí
se saca la marca y se baja `tests/plan_techo.json` de 11 a 10, **en el mismo
commit**.

## EL NÚMERO

```
HOY       registran 17 de 32 nodos declarados: solo la etapa `salida`
OBJETIVO  las seis etapas dejan marca: entrada, decision, reposicion,
          redaccion, salida, memoria
```

## ARCHIVOS QUE SE TOCAN

```
app/verifika/grafo.py      la funcion que registra, y como se llama a las
                           etapas que hoy no lo hacen
app/core/hub_venta.py      las llamadas a registrar() en las cinco etapas
                           que faltan
```

## ARCHIVOS QUE NO SE TOCAN

**Ninguna función que transforme el texto ni los datos.** Esta unidad agrega
observación, no comportamiento.

```
app/core/mensaje.py            no se toca
app/core/herramientas.py       no se toca
app/verifika/invariantes.py    no se toca
tests/  (salvo sacar la marca)  no se toca
```

## QUÉ NO PUEDE ROMPERSE

```
banco_pruebas/casetes/_piso.json    puntos, llamadas_max, largo_max
                                    NINGUNO puede empeorar
la bateria offline                  984 passed
```

Y una condición propia de esta unidad, porque es la que la hace segura:

> **El texto de salida de las 15 charlas grabadas tiene que ser idéntico,
> carácter por carácter, antes y después.** Agregar observación no puede mover
> una coma. Si se movió, se tocó comportamiento sin querer.

## CÓMO SE VERIFICA — offline, sin clave, sin red

```bash
# 1. el test de la ficha
python3 -m pytest tests/test_plan_del_recorte.py::test_el_grafo_registra_en_las_seis_etapas -q

# 2. nada roto
python3 -m pytest -q

# 3. el censo ahora ve las seis etapas solo, sin envolver nada a mano
python3 banco_pruebas/peso_del_censo.py
```

El punto 3 es la prueba real de que la unidad sirvió: hasta hoy
`peso_del_censo.py` imprime un aviso diciendo que hay nodos declarados que el
grafo no ve. **Cuando ese aviso desaparezca, la unidad está hecha.**

## LA TRAMPA CONOCIDA

Tres, y las tres ya costaron algo en este repo:

**1. `registrar()` no puede tumbar un turno.** Ya está escrito así —"un registro
roto no puede tumbar un turno"— y la regla vale para las cinco etapas nuevas. Si
una marca levanta una excepción, se traga y se sigue. Un instrumento que rompe
lo que mide no es un instrumento.

**2. `G.paso` compara para decidir si un nodo intervino.** Los nodos que NO
transforman texto —decisión, memoria, cierre— no se pueden medir comparándolos:
hay que decidir qué significa "intervino" para cada uno y escribirlo. Para la
reposición ya está resuelto y se puede copiar de `banco_pruebas/peso_reposicion.py`,
que compara el estado antes y después serializado.

**3. El detalle que arruina la medición sin que se note.** Si un nodo se registra
dos veces por turno —por ejemplo en un bucle— el censo cuenta de más y todos los
porcentajes quedan mal, en silencio. Cada nodo deja **una** marca por turno.

## CÓMO SE VUELVE ATRÁS

`git revert` del commit. No hay flag apagada, no hay camino paralelo. Como esta
unidad no cambia comportamiento, revertirla no puede afectar a un cliente.

---

## LO QUE SE DESCUBRIÓ AL ESCRIBIR ESTA FICHA

**El paso 1 de `PLAN_RECORTE.md` —sacar el bucle de rondas— YA ESTÁ HECHO.**

`hub_venta.py` dice *"DOS LLAMADAS AL MODELO POR TURNO, FIJAS"*, el bucle se
sacó el 17-ago, y `casetes/_piso.json` lo defiende con `llamadas_max: 2`, así que
no puede volver sin ponerse rojo.

Eso es exactamente lo que una ficha existe para evitar: **mandar a hacer algo que
ya está hecho.** El plan en prosa decía que era el primer paso; el código decía
que estaba cerrado. Gana el código.
