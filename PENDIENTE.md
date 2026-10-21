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

- **DONDE VA** · 21-oct, segunda sesión: los avisos, `arquitectura/FICHA_73_los_avisos.md`. Sobre la tabla mejorada, 468 de 525, diecisiete avisos de clase con devuelta solo donde saltan dan 521 de 525 sin romper ninguno: saltan en 53 casos, todos de los que fallaban, y en los demás el modelo ni se vuelve a llamar. Un aviso entra solo si, medido sin modelo sobre la primera traducción, no salta en ningún caso que anda. Antes se probó cambiar toda la entrada —pistas, un idioma de comandos, fichas por tipo—: 43 de 60 en los veinte turnos difíciles, pero en las 525 rompió 32, y no se usa. Las dos entrevistas al modelo: se desconoce; sirve probarlo, no preguntarle. Todo vive en `banco_pruebas/avisos/`, nada en el bot. Gasto de la paga, cerca de 1,80 dólares, con el tope subido a 4 por el día por orden de Martín y vuelto a 1 al cerrar.
- **SIGUE 1** · DeepSeek con el método de la FICHA 73, en sesión nueva. Sus 525 ya están grabadas en `traduccion58_corridas.jsonl`: se miden sin modelo los diecisiete avisos sobre esas traducciones, se corre la devuelta solo donde saltan y se compara con el modelo de producción. Prueba además si los avisos son de clase, porque no se escribieron mirando a DeepSeek. Junto con eso, el paso 1 de la lengua de salida que propone la FICHA 73: en los 60 difíciles, español controlado, Python con nuestras funciones, y Python libre primero como mapa y después llevado al menú.
- **SIGUE 2** · Los 4 que quedan, sin romper. C30 original y coloquial es del código: la herramienta de compatibilidad da compatible a una DDR4 con una PC con placa DDR5, aunque la ficha del producto dice que no entra; se arregla en `app/` con el ok de Martín. C52 redactada y K20 WhatsApp todavía sin una señal limpia para un aviso. Después, una reserva de formas nuevas escritas antes de correr.
- **SIGUE 3** · Llevar los avisos al bot, con su ficha y el ok de Martín: la tabla de `traduccion58._tabla_ideal` pasa a `flujo/marcador.py`, y los diecisiete avisos van como faltas de la devuelta en `interprete.interpretar`, cada uno con su test. Cuesta una segunda llamada en uno de cada diez mensajes.
- **SIGUE 4** · Después de SIGUE 3. La próxima compleja: K08 de la vara, siete artículos por rubro, presupuesto de crisis y tres destinos. Misma familia que la de hoy: prueba que lo hecho es de clase. Un guion nuevo en el simulador con su piso, y después WhatsApp. Siguen K13, mayorista, y C46, "de los que te mencioné", una por sesión.
- **ESPERA A MARTIN** · Las formas en que un cliente real dice cada complicada, en texto simple: cada una se vuelve un guion del simulador y suma al piso. Y la corrida nocturna que junta las charlas y corre los casos.
- **ABIERTO** · Lo que el simulador todavía marca en la de los siete artículos: la mitad de las charlas repite una pregunta, y el 32% que no llega es casi todo el modelo perdiendo el medio de pago o anotando un renglón nuevo al repetir el pedido. Sus fallas tienen probabilidades sin medir: cada charla real que se junte las ajusta en `MEDIDO`.
- **ABIERTO** · "Menos partes chinas" o "de Estados Unidos" el modelo lo traduce como contenido de la caja, cuando el catálogo tiene el país de fabricación y podría filtrar por ahí.
- **ABIERTO** · Lo que el flujo todavía no cubre, fuera de las 58: el resumen de la memoria larga cuando el historial pasa el límite, el reparto del pago sobre varios destinos, una condición de precio como C56, y las charlas K y J que faltan en la vara.
- **ABIERTO** · Complejas que siguen mal en vivo: K13 reserva en vez de contestar por mayorista; K08 deja rubros sin buscar; C46 contesta "de los que te mencioné" sin buscar el resto. Dos del mismo rubro a dos destinos ya salen el mismo modelo, por el criterio del rubro del borrador.
- **ABIERTO** · La compra por `reservar` entra al cierre, pero falta verla cerrar un pedido real con nombre y link.
- **ABIERTO** · Un medio que la tienda no toma entra al total sin aviso: "mitad en cripto" cuenta la mitad como pagable. Es el xfail de `tests/test_medio_de_pago_cerrado.py`. Con la agenda el medio lo escribe el modelo y el código lo puede validar contra la FAQ de formas de pago.
- **ABIERTO** · Caché del proveedor, medido el 20-oct con la paga y el ok de Martín: siete llamadas, incluso el mismo pedido exacto tres veces, y el proveedor no cachea nada; cada mensaje cobra unos 3.050 tokens de entrada enteros. Lo único que queda es el caché explícito, que pide la puerta nativa de Gemini y cobra por hora guardado: no conviene con el volumen de hoy.
- **ABIERTO** · El arranque muestra la interpretación "sin medir" porque su piso se archivó. Arreglarlo toca `scripts/`, que deploya.
- **ESPERA A MARTIN** · Decisiones de conducta. K20: la casilla pide el envío de 6.500 a Concordia y el bloque sale gratis por pasar los 250 mil, que es correcto. Ante un tema ambiguo, ¿se repregunta?
- **ESPERA A MARTIN** · Catálogo, que pide su permiso: los auriculares bluetooth figuran con cable porque `specs_por_modelo.csv` no trae bluetooth, y el origen es prosa, sin un campo normalizado.
- **ESPERA A MARTIN** · Consola y política: alerta de presupuesto y tope de cuota de la clave paga en Google Cloud, y cuánto tiempo se guardan las charlas.
