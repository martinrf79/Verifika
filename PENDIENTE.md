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

- **DONDE VA** · 23-oct. Pusheado en 97134d0 y deploy verde: las otras esperas, cada pregunta cerrada del bot con su respuesta y su efecto; vocabulario del sí, el no y los ordinales en el motor, cambiable por tienda, decisión 47. En vivo, la charla de prueba de Martín falló al tercer mensaje: "sumame un Redragon Cobra" se buscó como un mouse cualquiera, el reemplazo propuso sacar los mouses y la duda "nombre del cliente" llegó al cliente. Arreglado sin pushear: lo que nombra varios modelos queda nombrado y se pregunta cuál, lo que falta elegir no cuenta como sacado, y una duda solo llega si es pregunta. La charla real entra a `tests/test_espera.py` con sus fichas; 551 tests, 3.014 grabadas, 65 de 65. Sigue la charla de prueba desde el mensaje 3; falta la corrida con el modelo de producción.
- **SIGUE 1** · DEMO. Respuestas cortas: el bot no pega texto que el cliente no pidió. Visto el 23-oct: la compatibilidad pega la nota entera de la ficha, y el "sin dato" de un equipo desconocido lista todos los equipos. Se mide con `cableado58.py --ver` y `espera_vivo.py`, contando palabras por respuesta, sin bajar la vara.
- **SIGUE 2** · DEMO. La plata difícil. El pedido se cierra sin preguntar el medio de pago, y "era por transferencia" se traduce como la política de descuento, visto en vivo el 21-oct. Un medio que la tienda no toma entra al total sin aviso, "mitad en cripto": el xfail de `tests/test_medio_de_pago_cerrado.py`; el medio se valida contra la FAQ de formas de pago. P06 no cierra el 70 por ciento en tres destinos.
- **SIGUE 3** · DEMO. El cierre visto en vivo: la compra por `reservar` entra al cierre, falta ver un pedido real cerrar con nombre y link, por WhatsApp. Y el "Ok" de las 21:52 del 21-oct que Meta aceptó y no llegó: desde el 22-oct sus avisos quedan en el log, mirar con `produccion.py`.
- **SIGUE 4** · ROBUSTO. Producción como banco: los siete casos reales con casillas de Martín, `banco_pruebas/jev/casos_produccion.json`, los corre `pedido_documento/prod7_ficha.py` enteros por el camino vivo: 6 de 7. Falta su piso en la batería, con las respuestas guardadas, y sumar las fichas vivas de producción al banco del adaptador.
- **SIGUE 5** · ROBUSTO. Observabilidad y auditoría: cada turno con su trace_id, lo que tradujo el modelo, lo que hizo el código y lo que leyó el cliente, auditable por charla con `produccion.py`; y la corrida nocturna que junta las charlas reales y corre los casos.
- **SIGUE 6** · ROBUSTO. Resiliencia: cuando el modelo cae, tarda o devuelve una ficha rota, el cliente no queda sin respuesta ni con una inventada; el guardado de la charla falla sin perder el pedido.
- **SIGUE 7** · ROBUSTO. Generalidad, decisión 47: toda regla y texto en el motor con un defecto que cada tienda cambia. Revisar lo que quedó fijo en `app/core/flujo/` y probar con una segunda tienda de juguete. Después: el menú con la compra con condición, `si_cumple`, que está en `banco_pruebas/forma_normal/menu_si_cumple.patch` con su xfail y entra si no baja de 512 de las 525 ni de los pisos de variantes; y las complejas K08, K13 y C46, una por sesión, con un guion del simulador con su piso.
- **ESPERA A MARTIN** · Las formas en que un cliente real dice cada complicada, en texto simple: cada una se vuelve un guion del simulador y suma al piso. Y la corrida nocturna que junta las charlas y corre los casos.
- **ABIERTO** · Lo que el simulador todavía marca en la de los siete artículos: la mitad de las charlas repite una pregunta, y el 32% que no llega es casi todo el modelo perdiendo el medio de pago o anotando un renglón nuevo al repetir el pedido. Sus fallas tienen probabilidades sin medir: cada charla real que se junte las ajusta en `MEDIDO`.
- **ABIERTO** · `catalogo.atar` ya ata el origen partido en país y los campos de sí o no por su clave, 23-oct, `tests/test_atar_indice.py`: de 63 condiciones de la ficha nativa ata 52. Siguen sin atar "silencioso", "chiquito", "que entre en el bolsillo", "de malla" y "marca conocida", que son vagas de verdad, y comparar no tiene herramienta. Se mide con `banco_pruebas/pedido_documento/atar_ficha.py`.
- **ABIERTO** · Lo que la ficha deja mal, FICHA 76: dos renglones del mismo rubro con condiciones por destino toman la del primero y lo condicional se cumple sin condición, los dos xfail de `tests/test_ficha.py`; una búsqueda con tope y sin pedido entra al pedido por `normal.cuenta_de_lo_buscado`; P06 no cierra el 70 por ciento.
- **ABIERTO** · Lo que el flujo todavía no cubre, fuera de las 58: el resumen de la memoria larga cuando el historial pasa el límite, el reparto del pago sobre varios destinos, una condición de precio como C56, y las charlas K y J que faltan en la vara.
- **ABIERTO** · Complejas que siguen mal en vivo: K13 reserva en vez de contestar por mayorista; K08 deja rubros sin buscar; C46 contesta "de los que te mencioné" sin buscar el resto. Dos del mismo rubro a dos destinos ya salen el mismo modelo, por el criterio del rubro del borrador.
- **ABIERTO** · Caché del proveedor, medido el 20-oct con la paga y el ok de Martín: siete llamadas, incluso el mismo pedido exacto tres veces, y el proveedor no cachea nada; cada mensaje cobra unos 3.050 tokens de entrada enteros. Lo único que queda es el caché explícito, que pide la puerta nativa de Gemini y cobra por hora guardado: no conviene con el volumen de hoy.
- **ABIERTO** · El arranque muestra la interpretación "sin medir" porque su piso se archivó. Arreglarlo toca `scripts/`, que deploya.
- **ESPERA A MARTIN** · Decisiones de conducta. K20: la casilla pide el envío de 6.500 a Concordia y el bloque sale gratis por pasar los 250 mil, que es correcto. Ante un tema ambiguo, ¿se repregunta?
- **ESPERA A MARTIN** · Consola y política: alerta de presupuesto y tope de cuota de la clave paga en Google Cloud, y cuánto tiempo se guardan las charlas.
