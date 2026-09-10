# INVENTARIO DE LOS BARRIDOS — todos, en un solo lugar y medidos

**Este documento NO se escribe a mano.** Lo genera
`python3 banco_pruebas/inventario_barrido.py` corriendo cada barrido y
pidiendole su numero. `tests/test_inventario_barrido.py` vuelve a medir en cada
push: si el documento y la medicion no coinciden, se pone rojo. Y si aparece un
`tests/test_barrido_*.py` que no esta acá, tambien.

## POR QUE EXISTE

Martin, 12 y 13-ago-2026: *"siempre se me dice que el barrido esta listo, y
despues que esta a medias. Es desgastante"*.

Reconstruido con git: **nadie mintio nunca. La palabra "barrido" nombraba siete
cosas distintas** y no habia donde verlas juntas. La sesion que barrio catalogo,
FAQ, geo y coherencia dejo escrito en `PENDIENTE.md` que faltaba el del codigo
— y esa linea no aparecio en el resumen que Martin leyo. Asi, "hecho" y "a
medias" eran objetos distintos con el mismo nombre.

**Hoy son DOCE (12), y el numero de arriba no lo tipeo nadie: sale de la
lista del generador. La regla que queda: no se dice "el barrido" sin apellido, y
el estado se lee de acá, no de la memoria de nadie.**

---

## LOS 12 BARRIDOS

| barrido | que barre | numero | cobertura |
|---|---|---|---|
| **EL CATALOGO** | los productos de la fuente por cada forma en que un cliente los puede … | 6160 casos | — |
| **LA COHERENCIA DE LA FUENTE** | los datos de la fuente cruzados entre si: la ficha contra su planilla,… | 6 chequeos | — |
| **LA FAQ** | cada palabra con la que el cliente puede nombrar un tema, para que nin… | 738 señas | — |
| **GEO, LA TABLA DE LOCALIDADES** | la tabla entera de localidades, con provincia y sin ella, contra `geo_… | 16164 localidades | — |
| **EL CODIGO DE LA CUENTA** | la calculadora, el split de pago, el cobro, el componedor, el snapshot… | 1260 combinaciones | — |
| **LO QUE EL MODELO DECLARA** | las herramientas que el modelo llama, campo por campo, con valores val… | 427 casos | **100.0%** |
| **LA MEMORIA ENTRE TURNOS** | la transicion de un turno al siguiente: el carrito, la cuenta guardada… | 72 transiciones | **100.0%** |
| **LA COMPATIBILIDAD** | los pares de productos que la fuente hace posibles y los que no compar… | 320 pares | — |
| **LOS FILTROS DE LA FICHA** | cada campo de la ficha por cada operador, con valores leidos de la fic… | 687 casos | **100.0%** |
| **EL MENSAJE DEL CLIENTE** | el texto crudo que llega por la puerta -vacio, solo emoji, larguisimo,… | 48 casos | **100.0%** |
| **LAS SPECS PREGUNTABLES** | cada spec que la fuente declara preguntable, por su propia seña y por … | 6958 casos | **100.0%** |
| **LA DECISION Y LA REPOSICION** | los nodos que no tocan el texto sino el estado del turno -el ejecutor,… | 45 celdas | **100.0%** |

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

- **Que barre:** la calculadora, el split de pago, el cobro, el componedor, el snapshot de aduana y el reconciliador, sobre entradas generadas y no escritas.
- **Numero:** 1260 combinaciones. 12 pedidos x 7 juegos de extras x 3 destinos x 5 formas de pago.
- **Lo defiende:** `tests/test_barrido_codigo.py`.

### LO QUE EL MODELO DECLARA

- **Que barre:** las herramientas que el modelo llama, campo por campo, con valores validos, de borde y torcidos, entrando por `ejecutar` que es su puerta real.
- **Numero:** 427 casos. 4 herramientas, 45 campos, 135 de 135 celdas campo-por-clase; 139 casos de a un campo torcido y 288 de a pares.
- **Cobertura de su superficie: 100.0%** — completa.
- **Lo defiende:** `tests/test_barrido_herramientas.py`.

### LA MEMORIA ENTRE TURNOS

- **Que barre:** la transicion de un turno al siguiente: el carrito, la cuenta guardada, el reparto, el ancla, lo descartado y las decisiones del cliente.
- **Numero:** 72 transiciones. 13 campos de memoria, 13 cubiertos, 72 transiciones generadas.
- **Cobertura de su superficie: 100.0%** — completa.
- **Lo defiende:** `tests/test_barrido_memoria.py`.

### LA COMPATIBILIDAD

- **Que barre:** los pares de productos que la fuente hace posibles y los que no comparten nada, mas cada producto contra cada plataforma, por `evaluar_par` y `evaluar`.
- **Numero:** 320 pares. 880 productos con arista cargada, 22 familias de conexion, 240 pares en 4 clases y 80 casos contra las 12 plataformas del vocabulario.
- **Lo defiende:** `tests/test_barrido_compatibilidad.py`.

### LOS FILTROS DE LA FICHA

- **Que barre:** cada campo de la ficha por cada operador, con valores leidos de la ficha misma, contra `filtros_catalogo` y por la puerta real de `buscar_productos`.
- **Numero:** 687 casos. 41 campos filtrables x 5 operadores = 205 celdas, 205 cubiertas; 677 casos con valores de la fuente y 10 torcidos.
- **Cobertura de su superficie: 100.0%** — completa.
- **Lo defiende:** `tests/test_barrido_filtros.py`.

### EL MENSAJE DEL CLIENTE

- **Que barre:** el texto crudo que llega por la puerta -vacio, solo emoji, larguisimo, bytes de control, jailbreak, inyeccion, audio- contra el filtro de entrada, y las frases de cliente REAL que se le parecen.
- **Numero:** 48 casos. 13 clases de entrada, 13 cubiertas, 48 casos; el umbral de largo se lee del codigo vivo, no se tipea.
- **Cobertura de su superficie: 100.0%** — completa.
- **Lo defiende:** `tests/test_barrido_entrada_cliente.py`.

### LAS SPECS PREGUNTABLES

- **Que barre:** cada spec que la fuente declara preguntable, por su propia seña y por cada producto que la tiene: que la pregunta se reconozca y que el valor salga de la fuente y no de ningun lado.
- **Numero:** 6958 casos. 25 specs de la fuente, 25 con al menos un producto real.
- **Cobertura de su superficie: 100.0%** — completa.
- **Lo defiende:** `tests/test_barrido_specs.py`.

### LA DECISION Y LA REPOSICION

- **Que barre:** los nodos que no tocan el texto sino el estado del turno -el ejecutor, las busquedas derivadas, el resolver, el indice-, contra los contratos que declara el grafo, sobre estados de turno generados.
- **Numero:** 45 celdas. 5 nodos x 9 clases de estado = 45 celdas, 45 cubiertas; 108 estados generados, 5 contratos, 7 violaciones.
- **Cobertura de su superficie: 100.0%** — completa.
- **Lo defiende:** `tests/test_barrido_decision.py`.


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
- **Comparar por MAYOR o MENOR un campo de texto con magnitud adentro.** `ram`
  dice "16GB", `hz` dice "60Hz", `almacenamiento` dice "512GB SSD": son textos,
  asi que "de mas de 100Hz" no se puede filtrar y el codigo lo descarta con el
  motivo escrito, que es lo correcto y no es lo mismo que resolverlo. Se puede
  ORDENAR por ellos —`orden_tiene_sentido` mira el dato, no el nombre—, y
  `contiene` alcanza para el valor exacto. Convertirlos a numero es una edicion
  de la FUENTE, no de codigo.
- **La PROSA de la compatibilidad.** El barrido cubre el veredicto —compatible,
  incompatible, sin_dato— y su simetria. Como el modelo redacta ese veredicto
  para el cliente sigue siendo cosa de los casetes y del explorador.
- **QUE herramientas elige el decisor.** Es el modelo decidiendo, y ningun
  barrido determinista lo puede comprobar. Lo miden `interpretacion.py`, los
  casetes con su piso y el explorador. Lo que SI es determinista de esa mitad
  del turno —el ejecutor, las búsquedas derivadas, el resolver y el índice—
  lo barre LA DECISION Y LA REPOSICION desde el 14-ago (FICHA 34: el nexo
  reemplazó al reconciliador y a la puerta de reposición). Los nodos que quedan
  sin contrato mecanico estan declarados uno por uno con su motivo en
  `grafo.sin_contrato()`, y `test_barrido_decision.py` no deja que entre uno
  nuevo sin motivo escrito.

---

*Generado el 2026-08-28 por `banco_pruebas/inventario_barrido.py`.*
