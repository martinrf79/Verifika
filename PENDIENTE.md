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

- **DONDE VA** · 19-oct, orden de Martín: el cableado desde cero sobre las 58, sin modelos. El flujo nuevo está en `banco_pruebas/flujo/` —estado, ejecutor, catálogo, redacción, cierre— y corre por el webhook entero con `python3 -m banco_pruebas.cableado58`. Con las traducciones escritas a mano en `banco_pruebas/traducciones58.py`, 58 de 58. Con las que grabó Gemini, `--grabadas f10e_58_gg1`, `gg2` y `gg3`, 57 de 58 las tres: falla C40 porque el intérprete elige el tema `envios`, cuyo texto no dice lo del envío gratis, y no `costo_envio`. Ninguna llamada al modelo en todo el camino: el corredor las bloquea.
- **SIGUE 1** · Martín revisa `banco_pruebas/traducciones58.py`: es lo que se le va a pedir al intérprete en cada turno de las 58. Y decide si la respuesta al cliente queda escrita por el código, como ahora, o vuelve un redactor encima.
- **SIGUE 2** · El deploy del flujo: pasa a `app/core/flujo/`; `interprete.interpretar` se escribe contra el modelo con el prompt de la ficha 10, el estado de `estado.texto` y un menú de temas con SOLO los que tienen política escrita para el cliente —49 de 129; el resto es criterio para un redactor y no se muestra—, con lo que abarca cada uno, que es lo que arregla C40; el orchestrator llama a `flujo.turno.procesar_turno`; se borran `tablero.py`, `respuesta.py`, `ficha_charla.py`, las piezas de `agente.py` que releen el mensaje y los tests de ese camino; el techo de líneas baja. Antes del push, Martín ve el diff y lo que se borra.
- **SIGUE 3** · Lo que el flujo todavía no cubre, fuera de las 58: el resumen de la memoria larga cuando el historial pasa el límite, el reparto del pago sobre varios destinos, una condición de precio que el código podría evaluar —C56 hoy pregunta—, y las charlas K y J. Se suman como casos a la vara, con su traducción a mano.
- **ABIERTO** · LA VARA FIJA, `pytest tests/test_casos_grabados.py`: 23 de 24 charlas grabadas bien; C35 marcada, porque "otras opciones" no deja afuera lo mostrado y el intérprete pierde "gamer". `tests/grabadas_techo.json` sólo baja.
- **ABIERTO** · Complejas que siguen mal en vivo: K13 reserva en vez de contestar por mayorista; K10 y K11 pierden el pedido anotado a los varios turnos; K08 deja rubros sin buscar; C46 contesta "de los que te mencioné" sin buscar el resto; "dos auriculares" a dos destinos da dos modelos distintos.
- **ABIERTO** · La compra por `reservar` entra al cierre, pero falta verla cerrar un pedido real con nombre y link.
- **ABIERTO** · Un medio que la tienda no toma entra al total sin aviso: "mitad en cripto" cuenta la mitad como pagable. Es el xfail de `tests/test_medio_de_pago_cerrado.py`. Cerrarlo contra la FAQ de formas de pago rompió K21 grabada, porque `tablero._reparto` toma "setenta" como medio cuando el cliente dijo "setenta treinta". Primero eso, después el cierre, y se mide con las grabadas.
- **ABIERTO** · El cache de la clave da cero: el prompt fijo no llega al mínimo del proveedor. Medir el umbral.
- **ABIERTO** · El arranque muestra la interpretación "sin medir" porque su piso se archivó. Arreglarlo toca `scripts/`, que deploya.
- **ESPERA A MARTIN** · Decisiones de conducta. K20: la casilla pide el envío de 6.500 a Concordia y el bloque sale gratis por pasar los 250 mil, que es correcto. Ante un tema ambiguo, ¿se repregunta?
- **ESPERA A MARTIN** · Catálogo, que pide su permiso: los auriculares bluetooth figuran con cable porque `specs_por_modelo.csv` no trae bluetooth, y el origen es prosa, sin un campo normalizado.
- **ESPERA A MARTIN** · Consola y política: alerta de presupuesto y tope de cuota de la clave paga en Google Cloud, y cuánto tiempo se guardan las charlas.
