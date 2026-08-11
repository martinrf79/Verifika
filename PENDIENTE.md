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

- **ABIERTO** · El barrido de las otras dos fuentes: catálogo (¿resuelve cada producto por nombre corto, código de modelo pelado, marca?) y FAQ. El de localidades encontró 281 rotos y los cerró de una; falta saber cuántas clases quedan en las otras. Gratis y sin tokens: es el camino para que cada arreglo cierre cientos de casos en vez de uno.
- **ABIERTO** · La vara de CONTENIDO, que es la que coincide con lo que Martín ve. Hoy `interpretacion.py` dice entiende 91 / **contesta 61**, y ningún tablero lo mira. Cada error real que Martín encuentra se vuelve un caso con la respuesta correcta al lado; el número a mover es ese 61.
- **ABIERTO** · Bajar las llamadas al modelo por turno (hoy 2 a 4). NO mejora la calidad —está dicho y medido—, pero triplica el techo diario y baja la latencia de 26 s.
- **ESPERA A MARTIN** · Los prompts al modelo siguen en el código a propósito (`_INSTRUCCION*`, `_SISTEMA*`). Moverlos a la fuente es decisión suya, no un olvido.
- **ESPERA A MARTIN** · `villa, Buenos Aires` resuelve a un CP que el cliente no nombró. Es previo a los arreglos del 11-ago y de daño chico (misma tarifa de interior), pero es el sistema eligiendo por el cliente. Se arregla en `geo_cp.resolver`.
