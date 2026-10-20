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

- **DONDE VA** · 20-oct: la FICHA 72, pasos 1 y 2, deployada. La compleja de los siete artículos a tres destinos con pago partido Martín la da por casi terminada: en WhatsApp salieron bien tres charlas, la de siempre con dos correcciones distintas y una variante de diez artículos que el bot entendió en el primer mensaje. Repregunta lo que falta y cierra con nombre y pago. Se vuelve a probar al final, con los arreglos de las demás complejas.
- **SIGUE 1** · Arranque corto, sin modelo: juntar las tres charlas del 20-oct 15:26 a 15:37 con `produccion.py --juntar --desde 1d` y arreglar tres detalles del código vistos en ellas: el cierre repite el presupuesto entero del mensaje anterior y deja "Resumen:" suelto; las respuestas de la FAQ terminan en "contame qué producto te interesa" con el pedido ya armado; el teclado no buscado sale como la primera opción, el G915 de 512 mil, sin decir que se eligió.
- **SIGUE 2** · La próxima compleja: K08 de la vara, siete artículos por rubro, presupuesto de crisis y tres destinos. Misma familia que la de hoy: prueba que lo hecho es de clase. Un guion nuevo en el simulador con su piso, y después WhatsApp. Siguen K13, mayorista, y C46, "de los que te mencioné", una por sesión.
- **SIGUE 3** · La FICHA 72, paso 3: la llamada de venta. El modelo redacta con los hechos del turno y el código controla que cada monto y cada producto salga de los hechos. Resuelve "¿qué me conviene más?", que hoy se contesta en general y sin la cuenta del pedido.
- **ESPERA A MARTIN** · Las formas en que un cliente real dice cada complicada, en texto simple: cada una se vuelve un guion del simulador y suma al piso. Y la corrida nocturna que junta las charlas y corre los casos.
- **ABIERTO** · Lo que el simulador todavía marca en la de los siete artículos: la mitad de las charlas repite una pregunta, y el 32% que no llega es casi todo el modelo perdiendo el medio de pago o anotando un renglón nuevo al repetir el pedido. Sus fallas tienen probabilidades sin medir: cada charla real que se junte las ajusta en `MEDIDO`.
- **ABIERTO** · "Menos partes chinas" o "de Estados Unidos" el modelo lo traduce como contenido de la caja, cuando el catálogo tiene el país de fabricación y podría filtrar por ahí.
- **ABIERTO** · Lo que el flujo todavía no cubre, fuera de las 58: el resumen de la memoria larga cuando el historial pasa el límite, el reparto del pago sobre varios destinos, una condición de precio como C56, y las charlas K y J que faltan en la vara.
- **ABIERTO** · Complejas que siguen mal en vivo: K13 reserva en vez de contestar por mayorista; K08 deja rubros sin buscar; C46 contesta "de los que te mencioné" sin buscar el resto. Dos del mismo rubro a dos destinos ya salen el mismo modelo, por el criterio del rubro del borrador.
- **ABIERTO** · La compra por `reservar` entra al cierre, pero falta verla cerrar un pedido real con nombre y link.
- **ABIERTO** · Un medio que la tienda no toma entra al total sin aviso: "mitad en cripto" cuenta la mitad como pagable. Es el xfail de `tests/test_medio_de_pago_cerrado.py`. Con la agenda el medio lo escribe el modelo y el código lo puede validar contra la FAQ de formas de pago.
- **ABIERTO** · El cache de la clave daba cero porque el prompt fijo no llegaba al mínimo del proveedor. La consigna de la agenda pesa unos 2.300 tokens y va primero: medir si ahora entra en el cache.
- **ABIERTO** · El arranque muestra la interpretación "sin medir" porque su piso se archivó. Arreglarlo toca `scripts/`, que deploya.
- **ESPERA A MARTIN** · Decisiones de conducta. K20: la casilla pide el envío de 6.500 a Concordia y el bloque sale gratis por pasar los 250 mil, que es correcto. Ante un tema ambiguo, ¿se repregunta?
- **ESPERA A MARTIN** · Catálogo, que pide su permiso: los auriculares bluetooth figuran con cable porque `specs_por_modelo.csv` no trae bluetooth, y el origen es prosa, sin un campo normalizado.
- **ESPERA A MARTIN** · Consola y política: alerta de presupuesto y tope de cuota de la clave paga en Google Cloud, y cuánto tiempo se guardan las charlas.
