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
- **ABIERTO** · El barrido del CÓDIGO puro, que es la otra mitad y no la cubre ninguna fuente: el componedor, la aduana, el reconciliador, la calculadora y el split de pago no tienen entradas que enumerar. El equivalente es correr `verifika/invariantes.py` sobre entradas GENERADAS, no sobre charlas que alguien escribió. Ahí vivió el error de plata del 10-ago, entre dos módulos que estaban los dos en verde.
- **ABIERTO** · Que cada engranaje registre su propio veredicto, para saber CUÁL falló cuando la respuesta sale mal. Las piezas ya existen sueltas —`indice_turno`, `pedido.reconciliar`, `aduana`, `huecos`, `_log_fuente`—; falta que el que se abstiene o adivina deje su marca con el trace_id.
- **ABIERTO** · Los dos `G Pro X` de Logitech no resuelven por modelo pelado: sus tres palabras son una letra, `pro` —que está en la lista de genéricas— y otra letra. Con la marca adelante anda. Sacar `pro` de las genéricas toca el match de los 880 y hay que medirlo con el barrido antes.
- **ABIERTO** · La vara de CONTENIDO, que es la que coincide con lo que Martín ve. Hoy `interpretacion.py` dice entiende 91 / **contesta 61**, y ningún tablero lo mira. Cada error real que Martín encuentra se vuelve un caso con la respuesta correcta al lado; el número a mover es ese 61.
- **ABIERTO** · Bajar las llamadas al modelo por turno (hoy 2 a 4). NO mejora la calidad —está dicho y medido—, pero triplica el techo diario y baja la latencia de 26 s.
- **ESPERA A MARTIN** · Los prompts al modelo siguen en el código a propósito (`_INSTRUCCION*`, `_SISTEMA*`). Moverlos a la fuente es decisión suya, no un olvido.
- **ESPERA A MARTIN** · `villa, Buenos Aires` resuelve a un CP que el cliente no nombró. Es previo a los arreglos del 11-ago y de daño chico (misma tarifa de interior), pero es el sistema eligiendo por el cliente. Se arregla en `geo_cp.resolver`.
