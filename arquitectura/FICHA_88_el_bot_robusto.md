# FICHA 88 — El bot robusto: cuatro arreglos antes de medir en WhatsApp

5-nov-2026, con Martín. **La sesión siguiente arranca por acá.** Cuando los cuatro estén bien medidos, se mide en
WhatsApp con charlas reales. No se abre otra línea de trabajo antes.

## Lo que quedó de la sesión del 5-nov, antes de los cuatro

1. **Regrabar la vara entera.** `tests/test_agente.py` falla porque las 26 charlas están grabadas con la búsqueda por
   frases, que se borró. Orden: `python3 banco_pruebas/agente_replay.py --gratis --etiqueta sql6nov --regrabar`. Tiene
   que dar 74 de 75 o más, con todas las herramientas iguales. Hay una tarea programada para el 6-nov a las 8:10 UTC.
2. **La tercera corrida de las 42 charlas reales** con SQL en el bot, `python3 banco_pruebas/examen_real/sql.py
   --correr r3`, calificada a mano igual que r2 en la FICHA 87. La regla pide tres corridas: r2 fue en el banco, r3 y
   r4 con el bot integrado.
3. **El push.** Hay 4 commits en `main` sin pushear: el cobro del mismo turno, la cuenta y el medio de pago, y SQL en
   el bot. Se pushea con el ok de Martín y con la vara en verde, y se verifica el deploy en verde.
4. **Bajar el techo de `app/`** de 8560 a 8526, lo que quedó al borrar la búsqueda por frases. Va en su propio commit:
   los techos solo bajan.
5. **Medir el costo y la demora del mapa de la tabla**, que va en cada turno: son unos 8 mil caracteres. Con
   `banco_pruebas/produccion.py` después del deploy, tokens de entrada y segundos por turno, antes y después.
6. **La prueba con Gemini Flash**, decidida con Martín: la misma corrida con Flash y razonamiento bajo, con la gratis,
   para separar cuánto es el modelo y cuánto el código.

## Los cuatro arreglos

El bot ya trabaja en dos pasos: el modelo planifica con herramientas, el código busca y el modelo responde con los
datos. Estos cuatro son lo que le falta a ese ciclo para no inventar ni perder nada.

### 1. El modelo solo afirma lo que devolvieron las herramientas

**Falla de hoy:** al responder, el modelo ve todo el historial y escribe datos que ninguna herramienta trajo:
"silencioso" en 8e13ecbb7c, "todos son con cable" en 33dbb56c1b t4, "la RTX 4060 calienta menos" en 7f8cd4a5ca t3.

**Dónde vive:** `agente.responder`, el texto final del modelo, y el verificador, cuya fuente incluye lo que el mismo bot
dijo antes, en `agente.py`, la variable `fuente`.

**El arreglo:** las etiquetas. Cada fila que devuelve una herramienta lleva un número, P1, R1, E1, y el modelo las cita.
El código pega la línea real. La prosa del modelo lleva solo nombre, recomendación y la pregunta de venta. Un atributo de
producto fuera de una etiqueta vuelve una vez al modelo, y si sigue, se saca. La fuente del verificador deja de incluir
lo que dijo el bot antes.

**Hecho cuando:** en las 42 charlas, cero datos de producto que no estén en lo que devolvió una herramienta, y el
candado igual.

### 2. Cada parte del mensaje tiene su búsqueda

**Falla de hoy:** si el cliente pregunta tres cosas y el modelo busca dos, lo detectan solo en parte `sin_buscar` y
`omitidos`.

**Dónde vive:** `agente.sin_buscar` y `agente.omitidos`.

**El arreglo:** un solo control que vea el mensaje parte por parte —cada rubro, producto, lugar, medio de pago, monto y
pregunta que el código reconoce con `marcador`— y que cada una tenga su herramienta en el turno. Lo que falta vuelve una
vez al modelo con la lista. Reemplaza a `sin_buscar` y a la parte de `omitidos` que hace lo mismo: no se suma una capa.

**Hecho cuando:** en las 42 charlas, cero partes del mensaje sin contestar, contadas por el código, y revisadas a mano en
las que marque.

### 3. La búsqueda por uso, al lado de SQL

**Falla de hoy:** SQL resuelve lo que está en columnas. Lo que se pregunta por uso o por razonamiento —"para oficina",
"que caliente menos", "algo para escribir mucho"— no está en una columna, y el modelo contesta de memoria.

**Dónde vive:** `app/core/flujo/tabla.py` y el `buscar` de `agente.py`.

**El arreglo:** una consulta por significado sobre la descripción de cada producto, con los embeddings que el bot ya usa
para los temas. Devuelve filas con su número, como SQL, y el modelo elige entre las dos. Si la ficha no tiene el dato
—la temperatura—, la herramienta lo dice, y el modelo dice que no tiene el dato.

**Hecho cuando:** las preguntas por uso de las 42 charlas y de la vara se contestan con filas reales, y "no tengo ese
dato" cuando la ficha no lo tiene.

### 4. El pedido vive en el código

**Falla de hoy:** el modelo reescribe el pedido entero en cada turno, `agente.presupuesto` con `reemplaza: True`. Lo
sostienen los controles del 5-nov, la cuenta que pregunta y el medio por parte, pero un cambio chico puede perder un
renglón.

**Dónde vive:** `agente.presupuesto`; y ya construido sin conectar, `agente.pedido` y `agente.procedencia`, la FICHA 86.

**El arreglo:** conectar `pedido`: el modelo manda solo el cambio con la cita del cliente, y el código lo aplica sobre el
pedido guardado. Primero arreglar lo que la FICHA 86 midió en 69 de 75: el precio que se pide va a cotizar, que no anota,
y el cambio del turno siguiente no tiene sobre qué aplicarse, K16, K20 y K21.

**Hecho cuando:** la vara no baja de 74 de 75, y en las 42 charlas cero turnos donde el pedido pierde o suma algo que el
cliente no cambió, contado con `banco_pruebas/examen_real/clases.py`.

## Cómo se mide

Cada arreglo, en este orden, uno por sesión si hace falta:

- sin modelo: `python3 -m pytest -q`, la vara y el candado;
- con modelo: las 42 charlas reales con la gratis, `sql.py --correr <etiqueta>`, tres corridas, calificadas a mano.

**La meta para pasar a WhatsApp:** de las 30 charlas de varios mensajes, 28 o más sin ningún error en las tres
corridas, y la plata sin errores. La última medida, r2 del 5-nov, dio 25.

## Lo que hizo cada sesión

- 5-nov: la ficha, con Martín.
