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

- **DONDE VA** · 20-oct: la agenda está deployada y la interpretación anda en vivo: en las dos charlas reales el modelo escribió casi la agenda a mano. Falla el cableado de la memoria: en la segunda, a las 13:43, el bot preguntó "¿lo sumo el teclado?", el cliente dijo que sí dos veces y el bot repitió la pregunta. La causa de raíz es que la memoria vive en seis piezas sueltas de `estado` que el ejecutor rearma en cada turno. La solución está escrita y acordada con Martín: `arquitectura/FICHA_71_el_borrador.md`. Esa charla es `tests/test_charla_real_20oct_b.py`, xfail con motivo PLAN.
- **SIGUE 1** · La FICHA 71, el borrador, en sesión nueva: se lee entera y se hacen sus cinco pasos en orden, cada uno en su commit. Termina con la vara verde, las dos charlas reales del 20-oct verdes y el push con el ok de Martín.
- **SIGUE 2** · Después del borrador, Martín prueba en WhatsApp y cada charla se lee con `python3 banco_pruebas/produccion.py --desde 2h --pelicula 10`, que muestra la agenda del modelo y el estado de cada pregunta. La meta: diez charlas reales seguidas sin defecto.
- **ABIERTO** · Lo que el flujo todavía no cubre, fuera de las 58: el resumen de la memoria larga cuando el historial pasa el límite, el reparto del pago sobre varios destinos, una condición de precio como C56, y las charlas K y J que faltan en la vara.
- **ABIERTO** · Complejas que siguen mal en vivo: K13 reserva en vez de contestar por mayorista; K08 deja rubros sin buscar; C46 contesta "de los que te mencioné" sin buscar el resto; "dos auriculares" a dos destinos da dos modelos distintos.
- **ABIERTO** · La compra por `reservar` entra al cierre, pero falta verla cerrar un pedido real con nombre y link.
- **ABIERTO** · Un medio que la tienda no toma entra al total sin aviso: "mitad en cripto" cuenta la mitad como pagable. Es el xfail de `tests/test_medio_de_pago_cerrado.py`. Con la agenda el medio lo escribe el modelo y el código lo puede validar contra la FAQ de formas de pago.
- **ABIERTO** · El cache de la clave daba cero porque el prompt fijo no llegaba al mínimo del proveedor. La consigna de la agenda pesa unos 2.300 tokens y va primero: medir si ahora entra en el cache.
- **ABIERTO** · El arranque muestra la interpretación "sin medir" porque su piso se archivó. Arreglarlo toca `scripts/`, que deploya.
- **ESPERA A MARTIN** · Decisiones de conducta. K20: la casilla pide el envío de 6.500 a Concordia y el bloque sale gratis por pasar los 250 mil, que es correcto. Ante un tema ambiguo, ¿se repregunta?
- **ESPERA A MARTIN** · Catálogo, que pide su permiso: los auriculares bluetooth figuran con cable porque `specs_por_modelo.csv` no trae bluetooth, y el origen es prosa, sin un campo normalizado.
- **ESPERA A MARTIN** · Consola y política: alerta de presupuesto y tope de cuota de la clave paga en Google Cloud, y cuánto tiempo se guardan las charlas.
