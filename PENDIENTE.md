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

- **ABIERTO** · El pedido por categoría cambia de producto entre turnos y dentro del turno: "2 mouse" salió Genius y Logitech juntos, y los auriculares pasaron de Negro a Blanco sin que el cliente lo pidiera. Casetes `80` turno 7 y `81` turno 2. En la charla real del 12-ago el modelo mandó además un auricular que NO estaba en el carrito y la regla cero lo frenó, que es la red pero no el arreglo: falta que una categoría ya resuelta no vuelva a elegirse.
- **ESPERA A MARTIN** · `app/core/posventa.py` es una capacidad ENTERA sin cablear: plazo de devolución, garantía vigente y validación de CUIT. Nadie importa el módulo. Está declarado en `tests/test_nada_suelto.py` para que no se pierda de vista; enchufarlo o borrarlo es decisión suya.
- **ABIERTO** · Las 39 funciones que no llama el código vivo quedaron DECLARADAS con su motivo en `tests/test_nada_suelto.py`, que se pone rojo si aparece una nueva. La mitad son el camino sellado de `guia_pedido` y las piezas de compatibilidad: hay que decidir de a una si se enchufan o se borran, sin que la lista crezca mientras tanto.
- **ABIERTO** · El tope de largo del piso subió de 1.591 a 1.882 caracteres al entrar la charla real del 12-ago, que es la más pesada que se grabó, y creció otra vez cuando el turno 6 pasó a contestar con la cuenta que antes no armaba. No es una regresión: es el número real de hoy. Es el primero que tiene que bajar cuando se ataque la prioridad 2 (concisión).
- **ESPERA A MARTIN** · Tres pares de temas comparten una palabra y ninguno tiene una seña PROPIA que los separe: `factura`/`precios_iva` con "iva", `pedido_de_fotos`/`placa_video` con "video", `cambio_direccion`/`ubicacion` con "direccion". Hoy la guía los describe a los dos, así que el modelo elige con contexto y no a ciegas; que cada uno tenga su palabra propia es una edición de la FUENTE, no de código.
- **ABIERTO** · Los SIETE barridos y qué cubre cada uno se leen en `INVENTARIO_BARRIDO.md`, que lo genera un script y tiene candado doble. No se dice "el barrido" sin apellido: eso fue lo que hizo que un mismo día se reportara "hecho" y "a medias" sobre objetos distintos. Lo que sigue abierto ahí está escrito en su sección de límites.
- **ABIERTO** · Los contratos mecánicos hoy los declaran los 17 nodos de SALIDA. Los de decisión y reposición —decisor, herramientas, reconciliador, las cinco reposiciones, índice— no tienen ninguno, así que el barrido del grafo no los toca. Sus contratos son otros y hay que escribirlos: no inventar un id, no agregar un item que el cliente no pidió, no reclamar lo ya resuelto.
- **ABIERTO** · Los dos `G Pro X` de Logitech no resuelven por modelo pelado: sus tres palabras son una letra, `pro` —que está en la lista de genéricas— y otra letra. Con la marca adelante anda. Sacar `pro` de las genéricas toca el match de los 880 y hay que medirlo con el barrido antes.
- **ABIERTO** · El contrato NO_OMITE hoy repone solo el punto de PRECIO, que era el único que quedaba sin contestar en las charlas grabadas. Los otros tipos —un item que no se nombró, un destino que no se dijo— tienen evidencia y no tienen reposición: hay que ver cuál bloque sellado los contesta antes de sumarlos.
- **ABIERTO** · La vara de CONTENIDO. Medida el 12-ago con 1 repetición: `interpretacion.py` da **entiende 94 / contesta 94** —el 91/61 que decía acá era de antes del trabajo de esta semana—. La única falla que se repite es `criterio_de_origen`, 3 de 6 redacciones, y es del lado de la DECLARACIÓN del modelo: el banco lee los args crudos de `registrar_pedido`, así que no ve la restricción que el código completa desde los filtros. Falta medirlo con más repeticiones y sumar casos de turno largo.
- **ABIERTO** · El banco de turno largo corre OFFLINE sobre el estado, que es determinista: cubre carrito, ancla, orden de lo mostrado, tope de memoria e historial, a 1, 5, 10, 20 y 40 turnos. Lo que NO cubre es la redacción del modelo en un turno 10; eso sigue siendo prueba en real o casete grabado.
- **ABIERTO** · Bajar las llamadas al modelo por turno (hoy 2 a 4). NO mejora la calidad —está dicho y medido—, pero triplica el techo diario y baja la latencia de 26 s.
- **ESPERA A MARTIN** · Los prompts al modelo siguen en el código a propósito (`_INSTRUCCION*`, `_SISTEMA*`). Moverlos a la fuente es decisión suya, no un olvido.
- **ESPERA A MARTIN** · `villa, Buenos Aires` resuelve a un CP que el cliente no nombró. Es previo a los arreglos del 11-ago y de daño chico (misma tarifa de interior), pero es el sistema eligiendo por el cliente. Se arregla en `geo_cp.resolver`.
