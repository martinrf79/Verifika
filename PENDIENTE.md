# PENDIENTE — lo que quedó abierto, con su estado

Este archivo es CORTO a propósito y lo imprime entero el hook de arranque, así
que toda sesión nueva lo lee sin buscarlo. Reglas: máximo veinte líneas de
contenido, un ítem por línea, y cada uno arranca con su estado.

Lo que se HIZO no va acá: eso lo cuenta `git log`, que el hook también imprime
y que nadie puede desactualizar. Acá va solo lo que falta.

Estados: **ABIERTO** (no empezado) · **A MEDIAS** (dice qué falta para cerrarlo)
· **ESPERA A MARTIN** (hecho lo que se podía, falta una decisión o un dato suyo).

Candado: `tests/test_pendiente_al_dia.py` falla si hay commits que tocan `app/`
más nuevos que la última edición de este archivo. No se cierra una sesión
dejándolo viejo.

---

- **ESPERA A MARTIN** · Tres pares de temas comparten una palabra y ninguno tiene una seña PROPIA que los separe: `factura`/`precios_iva` con "iva", `pedido_de_fotos`/`placa_video` con "video", `cambio_direccion`/`ubicacion` con "direccion". Hoy la guía los describe a los dos, así que el modelo elige con contexto y no a ciegas; que cada uno tenga su palabra propia es una edición de la FUENTE, no de código.
- **A MEDIAS** · El barrido del CÓDIGO ya corre sobre entradas GENERADAS (`tests/test_barrido_codigo.py`, 1.680 combinaciones) y cubre la calculadora, el split, el cobro, el componedor, la aduana y el reconciliador; encontró dos defectos de plata y los dos quedaron arreglados. Falta barrer tres caminos de la calculadora que el generador todavía no arma: `grupos_envio`, el destino único sticky, y el envío cotizado en RANGO.
- **ABIERTO** · Los contratos mecánicos hoy los declaran los 17 nodos de SALIDA. Los de decisión y reposición —decisor, herramientas, reconciliador, las cinco reposiciones, índice— no tienen ninguno, así que el barrido del grafo no los toca. Sus contratos son otros y hay que escribirlos: no inventar un id, no agregar un item que el cliente no pidió, no reclamar lo ya resuelto.
- **ABIERTO** · Los dos `G Pro X` de Logitech no resuelven por modelo pelado: sus tres palabras son una letra, `pro` —que está en la lista de genéricas— y otra letra. Con la marca adelante anda. Sacar `pro` de las genéricas toca el match de los 880 y hay que medirlo con el barrido antes.
- **ABIERTO** · El contrato NO_OMITE hoy repone solo el punto de PRECIO, que era el único que quedaba sin contestar en las charlas grabadas. Los otros tipos —un item que no se nombró, un destino que no se dijo— tienen evidencia y no tienen reposición: hay que ver cuál bloque sellado los contesta antes de sumarlos.
- **ABIERTO** · La vara de CONTENIDO. Medida el 12-ago con 1 repetición: `interpretacion.py` da **entiende 94 / contesta 94** —el 91/61 que decía acá era de antes del trabajo de esta semana—. La única falla que se repite es `criterio_de_origen`, 3 de 6 redacciones, y es del lado de la DECLARACIÓN del modelo: el banco lee los args crudos de `registrar_pedido`, así que no ve la restricción que el código completa desde los filtros. Falta medirlo con más repeticiones y sumar casos de turno largo.
- **ABIERTO** · El banco de turno largo corre OFFLINE sobre el estado, que es determinista: cubre carrito, ancla, orden de lo mostrado, tope de memoria e historial, a 1, 5, 10, 20 y 40 turnos. Lo que NO cubre es la redacción del modelo en un turno 10; eso sigue siendo prueba en real o casete grabado.
- **ABIERTO** · Bajar las llamadas al modelo por turno (hoy 2 a 4). NO mejora la calidad —está dicho y medido—, pero triplica el techo diario y baja la latencia de 26 s.
- **ESPERA A MARTIN** · Los prompts al modelo siguen en el código a propósito (`_INSTRUCCION*`, `_SISTEMA*`). Moverlos a la fuente es decisión suya, no un olvido.
- **ESPERA A MARTIN** · `villa, Buenos Aires` resuelve a un CP que el cliente no nombró. Es previo a los arreglos del 11-ago y de daño chico (misma tarifa de interior), pero es el sistema eligiendo por el cliente. Se arregla en `geo_cp.resolver`.
