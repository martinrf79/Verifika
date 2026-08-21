# PENDIENTE — lo que quedó abierto

Este archivo es **CORTO a propósito** y el hook de arranque lo imprime entero, así
que toda sesión nueva lo lee sin buscarlo. **Máximo veinte líneas de contenido, un
ítem por línea.** El 21-ago tenía veinte PÁRRAFOS, uno de mil novecientos
caracteres: un archivo que se imprime en cada arranque no puede ser un diario.

**Lo que se HIZO no va acá:** lo cuenta `git log`, que el hook también imprime y
que nadie puede desactualizar.

**El PLAN tampoco va acá**, y ese es el cambio del 21-ago. El recorte vive como
tests que se cuentan solos; escribirlo además en prosa eran dos fuentes sobre lo
mismo, que es exactamente lo que venimos sacando de todos lados.

Estados: **ABIERTO** · **ESPERA A MARTIN** (falta una decisión o un dato suyo).

Candado: `tests/test_pendiente_al_dia.py` falla si hay commits que tocan `app/`
más nuevos que este archivo.

---

## Dónde está el proyecto — dos números, y salen de correr `pytest`

```
A MEDIAS   algo que se EMPEZÓ y no se terminó.  Tiene que llegar a CERO.
PLAN       el recorte. Baja a medida que se hace.
```

El detalle de cada paso, con su número de hoy y su objetivo, está en
`tests/test_plan_del_recorte.py`. La unidad de trabajo abierta, en `arquitectura/`.

---

## Abierto

- **ABIERTO** · El rubro que cambia de producto quedó cerrado en sus dos mitades; falta mirar si el mismo defecto entra por otra puerta que no sea la reposición.
- **ABIERTO** · Veintiocho funciones se alcanzan pero no las llama nadie: están DECLARADAS con su motivo en `tests/test_nada_suelto.py`, que se pone rojo si aparece una nueva. Hay que decidir de a una si se enchufan o se borran.
- **ABIERTO** · `cierre` sale MUERTO en el censo: corre en los 54 turnos y no mueve el texto en ninguno. Antes de borrarlo hay que escribir el caso que lo despierta —vale para los nueve muertos, y los guiones 26 a 38 se escribieron para eso.
- **ABIERTO** · El tope de largo del piso está en 1.882 caracteres y subió dos veces. No es regresión: es el número real. Es el primero que tiene que bajar cuando se ataque la concisión, y hoy nada lo obliga a bajar —el piso solo impide que crezca.
- **ABIERTO** · `garantia_detalle` factorizado sale sin la marca: si un día dos productos de la misma categoría tienen plazos distintos, el campo no se factoriza y la repetición vuelve. No hay ningún caso así en el catálogo hoy.
- **ABIERTO** · Los dos `G Pro X` de Logitech no resuelven por modelo pelado: sus tres palabras son una letra, `pro` —que está en las genéricas— y otra letra. Sacar `pro` de las genéricas toca el match de los 880 y hay que medirlo con el barrido antes. El guion 30 lo ejercita.
- **ABIERTO** · La vara de CONTENIDO dio entiende 94 / contesta 94 con UNA repetición. Falta medirla con más repeticiones y sumar casos de turno largo; la única falla que se repite es `criterio_de_origen`.
- **ABIERTO** · El banco de turno largo corre offline sobre el estado, que es determinista. Lo que NO cubre es la redacción del modelo en un turno 10: eso sigue siendo prueba en real o casete grabado.
- **ABIERTO** · **EL TOTAL PERDIDO SE ARREGLO (21-ago) y el piso subio de 489 a 495, pero el piso NO se refijo y hay que decir por que.** El defecto era doble y los dos estaban tapados por el corpus viejo. **(1)** `_certifico_algo` apagaba la memoria ENTERA cuando el turno certificaba cualquier cosa: en el turno 8 de la charla real del 12-ago el cliente dice "agregá un teclado" y, por certificar teclados, se le negaba el carrito donde vivían los otros seis artículos. Ahora la memoria la gobierna el reclamo TIPADO del reconciliador, `falta_la_cuenta`, y no la certificación. **(2)** Las búsquedas que hace EL CODIGO en las reposiciones no pasaban por `certificar_ids_de_resultado`, así que la calculadora rechazaba sus propios ids: `id_no_certificado sueltos=['AUR0019','MOU0023','RAM0001']` y el turno 6 cerraba sin un peso. **Los turnos 6 y 8 ahora cierran con la cuenta**, en 1.644 y 1.821 caracteres, y `llamadas_max` sigue en 2. **LO QUE FALTA para refijar el piso es el LARGO:** un solo turno del corpus queda en 2.060 contra el tope de 1.882 —el turno 2 de `76`, el más difícil que hay— y **ya medía 2.060 antes de tocar `app/`**, o sea que viene de la regrabación y no del arreglo. Refijar el piso ahora subiría el tope de largo a 2.060, que es justo el número que tiene que bajar. **El piso se refija cuando ese turno entre en 1.882.**
- **ABIERTO** · **No hay ningún número de VENTA.** Todo lo que se mide es defensivo —no cae, no inventa, no omite—. No hay tasa de cierre ni dónde se cae el cliente. Un sistema que solo mide lo que no debe hacer termina siendo un bot que no hace nada mal y no vende.

## Espera a Martín

- **ABIERTO** · **`indice_turno.puntos` ya abre las DIEZ familias, pero cuatro no se pueden abrir todavia en una charla real, y el numero engaña.** Se sumaron `atributo`, `stock`, `compatibilidad` y `politica`, cada una con su criterio de cobertura y con anclaje donde el codigo tiene el dato. **El problema es el MOLDE: `registrar_pedido` no tiene esos cuatro campos**, asi que el modelo no puede declararlos y en el corpus grabado no se abre ni uno. Medido despues del cambio: 190 puntos, 24 sin contestar, 13% — EXACTAMENTE los mismos de antes. **Ojo con leer ese 13% como una buena noticia: sigue siendo un PISO, no el numero real.** Lo que falta es agregarle los cuatro campos a `registrar_pedido`, y eso cambia el esquema que ve el modelo, o sea que es otra unidad con otro riesgo y hay que medir el peso del esquema al hacerlo.
- **ABIERTO** · **`puerta_piso.json` guarda PORCENTAJES atados a un corpus que cambia, y eso da falsos rojos.** Al regrabar los casetes el 21-ago, `test_puerta_determinista` se puso rojo diciendo `reparto_pago: 11.1% -> 9.1%`, como si el código entendiera menos. **No entiende menos: entiende exactamente lo mismo, 1 turno.** Lo que cambió es el denominador — el modelo declaró reparto de pago en 11 turnos en vez de 9 — y el código no se tocó en esa sesión, así que una regresión ahí era imposible por construcción. Los otros cinco números subieron o quedaron igual: items 78,4→83,3, destinos 41,2→47,1, restricciones 60,0→66,7, y los turnos medidos pasaron de 51 a 53. **Un piso que guarda una razón contra un corpus mutable mide dos cosas a la vez y no puede decir cuál se movió**, que es la misma enfermedad que la FICHA 03 vino a curar en el otro piso. Guardar el NUMERADOR y el denominador por separado lo arregla.
- **ESPERA A MARTIN** · Tres pares de temas comparten una palabra y ninguno tiene una seña propia: `factura`/`precios_iva` con "iva", `pedido_de_fotos`/`placa_video` con "video", `cambio_direccion`/`ubicacion` con "direccion". Es una edición de la FUENTE, no de código.
- **ESPERA A MARTIN** · El sistema SIN LLM está medido en `banco_pruebas/puerta_determinista.py` y el número es alto. Lo que ninguna pieza ve es la NEGACIÓN —"el teclado sacalo"— y lo que no tiene pieza es `pide_precio` y `contradicciones`. Sirve como modo degradado para cuando el modelo se cae; NO se deploya en paralelo al vivo.
- **ESPERA A MARTIN** · `villa, Buenos Aires` resuelve a un CP que el cliente no nombró. Daño chico —misma tarifa de interior— pero es el sistema eligiendo por el cliente. Se arregla en `geo_cp.resolver`.
- **ESPERA A MARTIN** · Cuánto tiempo se guardan las conversaciones y con qué criterio se borran. Desde el 19-ago el bot pide solo el nombre, así que la superficie es chica, pero la decisión de retención es suya y conviene tomarla antes de vender a una empresa.
