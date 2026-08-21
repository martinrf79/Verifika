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
- **ABIERTO** · Faltan dos puntos del piso, de 493 a 491, y NO son regresión: los 15 casetes se grabaron con la arquitectura de cuatro rondas y guardan una llamada que el turno ya no hace. Se recuperan regrabando las 15, y eso necesita clave.
- **ABIERTO** · **No hay ningún número de VENTA.** Todo lo que se mide es defensivo —no cae, no inventa, no omite—. No hay tasa de cierre ni dónde se cae el cliente. Un sistema que solo mide lo que no debe hacer termina siendo un bot que no hace nada mal y no vende.

## Espera a Martín

- **ESPERA A MARTIN** · Tres pares de temas comparten una palabra y ninguno tiene una seña propia: `factura`/`precios_iva` con "iva", `pedido_de_fotos`/`placa_video` con "video", `cambio_direccion`/`ubicacion` con "direccion". Es una edición de la FUENTE, no de código.
- **ESPERA A MARTIN** · El sistema SIN LLM está medido en `banco_pruebas/puerta_determinista.py` y el número es alto. Lo que ninguna pieza ve es la NEGACIÓN —"el teclado sacalo"— y lo que no tiene pieza es `pide_precio` y `contradicciones`. Sirve como modo degradado para cuando el modelo se cae; NO se deploya en paralelo al vivo.
- **ESPERA A MARTIN** · `villa, Buenos Aires` resuelve a un CP que el cliente no nombró. Daño chico —misma tarifa de interior— pero es el sistema eligiendo por el cliente. Se arregla en `geo_cp.resolver`.
- **ESPERA A MARTIN** · Cuánto tiempo se guardan las conversaciones y con qué criterio se borran. Desde el 19-ago el bot pide solo el nombre, así que la superficie es chica, pero la decisión de retención es suya y conviene tomarla antes de vender a una empresa.
