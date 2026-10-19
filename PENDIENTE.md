# PENDIENTE — dónde va el trabajo y lo que queda abierto

El hook del arranque imprime el titular de cada ítem de abajo de la raya. Por eso cada titular dice solo lo
esencial, y el orden importa: **la sesión nueva arranca por el primer ítem SIGUE, sin preguntar.**

- El objetivo, el plan y las reglas: `CLAUDE.md`. No se copian acá.
- Lo hecho: `git log`. El plan vigente, del 19-oct: `CLAUDE.md`, sección 1, el cableado desde cero sobre las 58.
- Lo que Martín decidió para siempre: `papeles/DECISIONES.md`.

**Al cerrar cada sesión:** se reescribe el ítem DONDE VA, se reordenan los SIGUE y se borra lo que quedó hecho u
obsoleto. Máximo veinte ítems, lo controla `tests/test_pendiente.py`. Lo pendiente de código va además como un
test que falla, `xfail(strict=True)`, con motivo `PLAN:` o `A MEDIAS:`.

Estados: **DONDE VA** · **SIGUE** · **ABIERTO** · **ESPERA A MARTIN**.

---

- **DONDE VA** · 19-oct, orden de Martín: el flujo nuevo es el camino vivo. `orchestrator` llama a `app/core/flujo/turno.procesar_turno`; el intérprete usa el prompt de la ficha 10 y el resto lo hace el código. Se borraron `tablero.py`, `respuesta.py`, `ficha_charla.py`, `numeros.py`, `memoria_larga.py`, `camino_cobro.py` y cuatro más, la completitud de `agente.py` y 246 tests de ese camino. La vara fija es `tests/test_cableado58.py`: las 58 sin modelo, 58 de 58; con las traducciones grabadas de Gemini, 57 de 58, C40. Sin corrida con Gemini antes del deploy: la cuota gratis del día estaba agotada. Una charla de humo de tres turnos con un modelo gratis de OpenRouter, Nemotron, anduvo entera: producto y envío, compra recordando el destino, total de $87.500, nombre, lead y cobro. Lo primero es leer las charlas reales con `banco_pruebas/produccion.py --desde 6h`.
- **SIGUE 1** · Martín revisa `banco_pruebas/traducciones58.py`: es lo que se le va a pedir al intérprete en cada turno de las 58. Y decide si la respuesta al cliente queda escrita por el código, como ahora, o vuelve un redactor encima.
- **SIGUE 2** · Las charlas reales del flujo nuevo, con `produccion.py`: lo que traduce el intérprete está en el log `interprete_ok` y lo que hizo el código en `flujo_turno`. Una falla del intérprete se arregla en su prompt, `interprete.py`; una del código, en el ejecutor; y la charla entra a la vara con su traducción a mano.
- **SIGUE 3** · Lo que el flujo todavía no cubre, fuera de las 58: el resumen de la memoria larga cuando el historial pasa el límite, el reparto del pago sobre varios destinos, una condición de precio que el código podría evaluar —C56 hoy pregunta—, y las charlas K y J. Se suman como casos a la vara, con su traducción a mano.
- **ABIERTO** · Complejas que siguen mal en vivo: K13 reserva en vez de contestar por mayorista; K10 y K11 pierden el pedido anotado a los varios turnos; K08 deja rubros sin buscar; C46 contesta "de los que te mencioné" sin buscar el resto; "dos auriculares" a dos destinos da dos modelos distintos.
- **ABIERTO** · La compra por `reservar` entra al cierre, pero falta verla cerrar un pedido real con nombre y link.
- **ABIERTO** · Un medio que la tienda no toma entra al total sin aviso: "mitad en cripto" cuenta la mitad como pagable. Es el xfail de `tests/test_medio_de_pago_cerrado.py`. Cerrarlo contra la FAQ de formas de pago rompió K21 grabada, porque `tablero._reparto` toma "setenta" como medio cuando el cliente dijo "setenta treinta". Primero eso, después el cierre, y se mide con las grabadas.
- **ABIERTO** · El cache de la clave da cero: el prompt fijo no llega al mínimo del proveedor. Medir el umbral.
- **ABIERTO** · El arranque muestra la interpretación "sin medir" porque su piso se archivó. Arreglarlo toca `scripts/`, que deploya.
- **ESPERA A MARTIN** · Decisiones de conducta. K20: la casilla pide el envío de 6.500 a Concordia y el bloque sale gratis por pasar los 250 mil, que es correcto. Ante un tema ambiguo, ¿se repregunta?
- **ESPERA A MARTIN** · Catálogo, que pide su permiso: los auriculares bluetooth figuran con cable porque `specs_por_modelo.csv` no trae bluetooth, y el origen es prosa, sin un campo normalizado.
- **ESPERA A MARTIN** · Consola y política: alerta de presupuesto y tope de cuota de la clave paga en Google Cloud, y cuánto tiempo se guardan las charlas.
