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

- **DONDE VA** · 20-oct: la FICHA 72 hecha en sus pasos 1 y 2, en `main` sin pushear. El código arma todas las lecturas que cierran con los números del cliente, el modelo elige una con la cita que la justifica, `interprete.elegir`, y queda supuesta con el presupuesto entero hasta que el cliente dice que sí. La charla de los siete artículos del 19-oct sale bien con Gemini en tres turnos. Simulador: 68% bien contra 24% de antes, y cero presupuestos equivocados sin aviso, con piso en `tests/simulador_piso.json`.
- **SIGUE 1** · El push, con el ok de Martín: toca `app/core/flujo/`, deploya, y lo que se rompería es la multipregunta con pedido. Después Martín prueba en WhatsApp la de los siete artículos y otras dichas de otra forma, y cada charla se lee con `python3 banco_pruebas/produccion.py --desde 2h --pelicula 10` y se guarda con `--juntar`; `tests/test_reales.py` la repite con la agenda exacta. Un defecto del código se marca en el caso con `debe` o `no_debe`.
- **SIGUE 2** · La FICHA 72, paso 3: la llamada de venta. El modelo redacta con los hechos del turno y el código controla que cada monto y cada producto del texto salga de los hechos; si no, va el texto del código. Las guardas viejas de texto se borraron el 20-oct por muertas: se arma de cero sobre los hechos.
- **ESPERA A MARTIN** · Las formas en que un cliente real dice cada complicada, en texto simple: cada una se vuelve un guion del simulador y suma al piso. Y la corrida nocturna que junta las charlas y corre los casos.
- **ABIERTO** · Lo que el simulador todavía marca en la de los siete artículos: la mitad de las charlas repite una pregunta, y el 32% que no llega es casi todo el modelo perdiendo el medio de pago o anotando un renglón nuevo al repetir el pedido. Sus fallas tienen probabilidades sin medir: cada charla real que se junte las ajusta en `MEDIDO`.
- **ABIERTO** · En la de los siete artículos el teclado, que el cliente no buscó, sale como la primera opción del rubro, el G915 de 512 mil, sin decir que se eligió; y "menos partes chinas" el modelo lo traduce como contenido de la caja, cuando el catálogo tiene el país de fabricación.
- **ABIERTO** · Lo que el flujo todavía no cubre, fuera de las 58: el resumen de la memoria larga cuando el historial pasa el límite, el reparto del pago sobre varios destinos, una condición de precio como C56, y las charlas K y J que faltan en la vara.
- **ABIERTO** · Complejas que siguen mal en vivo: K13 reserva en vez de contestar por mayorista; K08 deja rubros sin buscar; C46 contesta "de los que te mencioné" sin buscar el resto. Dos del mismo rubro a dos destinos ya salen el mismo modelo, por el criterio del rubro del borrador.
- **ABIERTO** · La compra por `reservar` entra al cierre, pero falta verla cerrar un pedido real con nombre y link.
- **ABIERTO** · Un medio que la tienda no toma entra al total sin aviso: "mitad en cripto" cuenta la mitad como pagable. Es el xfail de `tests/test_medio_de_pago_cerrado.py`. Con la agenda el medio lo escribe el modelo y el código lo puede validar contra la FAQ de formas de pago.
- **ABIERTO** · El cache de la clave daba cero porque el prompt fijo no llegaba al mínimo del proveedor. La consigna de la agenda pesa unos 2.300 tokens y va primero: medir si ahora entra en el cache.
- **ABIERTO** · El arranque muestra la interpretación "sin medir" porque su piso se archivó. Arreglarlo toca `scripts/`, que deploya.
- **ESPERA A MARTIN** · Decisiones de conducta. K20: la casilla pide el envío de 6.500 a Concordia y el bloque sale gratis por pasar los 250 mil, que es correcto. Ante un tema ambiguo, ¿se repregunta?
- **ESPERA A MARTIN** · Catálogo, que pide su permiso: los auriculares bluetooth figuran con cable porque `specs_por_modelo.csv` no trae bluetooth, y el origen es prosa, sin un campo normalizado.
- **ESPERA A MARTIN** · Consola y política: alerta de presupuesto y tope de cuota de la clave paga en Google Cloud, y cuánto tiempo se guardan las charlas.
