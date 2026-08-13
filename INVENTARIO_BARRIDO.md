# INVENTARIO DE LOS BARRIDOS — todos, en un solo lugar y medidos

**Este documento NO se escribe a mano.** Lo genera
`python3 banco_pruebas/inventario_barrido.py` corriendo cada barrido y
pidiendole su numero. `tests/test_inventario_barrido.py` vuelve a medir en cada
push: si el documento y la medicion no coinciden, se pone rojo. Y si aparece un
`tests/test_barrido_*.py` que no esta acá, tambien.

## POR QUE EXISTE

Martin, 12 y 13-ago-2026: *"siempre se me dice que el barrido esta listo, y
despues que esta a medias. Es desgastante"*.

Reconstruido con git: **nadie mintio nunca. La palabra "barrido" nombra SIETE
cosas distintas** y no habia donde verlas juntas. La sesion que barrio catalogo,
FAQ, geo y coherencia dejo escrito en `PENDIENTE.md` que faltaba el del codigo
— y esa linea no aparecio en el resumen que Martin leyo. Asi, "hecho" y "a
medias" eran objetos distintos con el mismo nombre.

**La regla que queda: no se dice "el barrido" sin apellido, y el estado se lee
de acá, no de la memoria de nadie.**

---

## LOS 7 BARRIDOS

| barrido | que barre | numero | cobertura |
|---|---|---|---|
| **EL CATALOGO** | los productos de la fuente por cada forma en que un cliente los puede … | 6160 casos | — |
| **LA COHERENCIA DE LA FUENTE** | los datos de la fuente cruzados entre si: la ficha contra su planilla,… | 6 chequeos | — |
| **LA FAQ** | cada palabra con la que el cliente puede nombrar un tema, para que nin… | 738 señas | — |
| **GEO, LA TABLA DE LOCALIDADES** | la tabla entera de localidades, con provincia y sin ella, contra `geo_… | 16164 localidades | — |
| **EL CODIGO DE LA CUENTA** | la calculadora, el split de pago, el cobro, el componedor, la aduana y… | 1260 combinaciones | — |
| **LO QUE EL MODELO DECLARA** | las herramientas que el modelo llama, campo por campo, con valores val… | 359 casos | **100.0%** |
| **LA MEMORIA ENTRE TURNOS** | la transicion de un turno al siguiente: el carrito, la cuenta guardada… | 72 transiciones | **100.0%** |

---

### EL CATALOGO

- **Que barre:** los productos de la fuente por cada forma en que un cliente los puede nombrar, contra `certificar_producto`.
- **Numero:** 6160 casos. 880 productos x 7 formas de nombrarlos.
- **Lo defiende:** `tests/test_barrido_identidad.py`.

### LA COHERENCIA DE LA FUENTE

- **Que barre:** los datos de la fuente cruzados entre si: la ficha contra su planilla, la compatibilidad contra las specs, las filas huerfanas y las columnas que no lee nadie.
- **Numero:** 6 chequeos. 6 chequeos sobre la fuente real, 0 problemas encontrados.
- **Lo defiende:** `tests/test_barrido_fuente.py`.

### LA FAQ

- **Que barre:** cada palabra con la que el cliente puede nombrar un tema, para que ninguna obligue al modelo a adivinar entre dos temas distintos.
- **Numero:** 738 señas. 738 señas de la fuente, ninguna ciega.
- **Lo defiende:** `tests/test_barrido_faq.py`.

### GEO, LA TABLA DE LOCALIDADES

- **Que barre:** la tabla entera de localidades, con provincia y sin ella, contra `geo_cp.resolver`.
- **Numero:** 16164 localidades. 16164 localidades de la tabla del Correo, con y sin provincia, y el tope de n-gramas que sale de la tabla y no de un numero escrito a mano.
- **Lo defiende:** `tests/test_geo_cp.py`.

### EL CODIGO DE LA CUENTA

- **Que barre:** la calculadora, el split de pago, el cobro, el componedor, la aduana y el reconciliador, sobre entradas generadas y no escritas.
- **Numero:** 1260 combinaciones. 12 pedidos x 7 juegos de extras x 3 destinos x 5 formas de pago.
- **Lo defiende:** `tests/test_barrido_codigo.py`.

### LO QUE EL MODELO DECLARA

- **Que barre:** las herramientas que el modelo llama, campo por campo, con valores validos, de borde y torcidos, entrando por `ejecutar` que es su puerta real.
- **Numero:** 359 casos. 9 herramientas, 42 campos, 126 de 126 celdas campo-por-clase; 135 casos de a un campo torcido y 224 de a pares.
- **Cobertura de su superficie: 100.0%** — completa.
- **Lo defiende:** `tests/test_barrido_herramientas.py`.

### LA MEMORIA ENTRE TURNOS

- **Que barre:** la transicion de un turno al siguiente: el carrito, la cuenta guardada, el reparto, el ancla, lo descartado y las decisiones del cliente.
- **Numero:** 72 transiciones. 13 campos de memoria, 13 cubiertos, 72 transiciones generadas.
- **Cobertura de su superficie: 100.0%** — completa.
- **Lo defiende:** `tests/test_barrido_memoria.py`.


---

## LO QUE NINGUNO DE ESTOS BARRIDOS CUBRE, dicho adelante

Para que no aparezca como sorpresa tres sesiones despues:

- **La redaccion del modelo.** Que la frase sea buena, clara y vendedora no lo
  decide un barrido: son deterministas y el modelo no lo es. Eso lo miden las
  charlas grabadas (`tests/test_charlas_grabadas.py`), `banco_pruebas/explorador.py`
  y `banco_pruebas/produccion.py`.
- **Tres o mas campos torcidos a la vez.** Se barre de a uno y de a pares sobre
  lo que toca plata. El costo de barrer de a tres crece al cubo y los defectos
  de interaccion triple son raros.
- **Encadenados de mas de dos turnos con el modelo real.** La memoria se barre
  determinista sobre sus funciones; la charla larga con modelo vivo la cubren
  los casetes y el explorador.
- **El envio cotizado en RANGO.** La rama existe en la calculadora y hoy NO es
  alcanzable: las 24 provincias de la fuente tienen tarifa fija. Queda con
  guardia en `test_barrido_codigo.py`: el dia que se cargue una tarifa en rango,
  ese test pide el barrido en el mismo push.

---

*Generado el 2026-08-13 por `banco_pruebas/inventario_barrido.py`.*
