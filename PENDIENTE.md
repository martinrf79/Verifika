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

- **DONDE VA** · 21-oct, tercera sesión: la forma normal, `arquitectura/FICHA_74_la_forma_normal.md`. Las fallas del intérprete casi nunca son de entender: el modelo dice lo correcto en otra forma que la agenda a mano, y 52 casos fallan en cuatro o más de seis modelos, así que es el contrato. `app/core/flujo/normal.py` lleva cada forma a la que cumple el ejecutor, sin tocar lo que recibe el modelo ni hacer otra llamada. Medido sin modelo con `banco_pruebas/forma_normal/regrado.py` sobre las 3.107 traducciones grabadas de seis modelos: de 2.702 a 2.994, producción de 455 a 507 de 525, sin romper ninguna. Salieron además cinco errores del código, entre ellos C30. Todo en `main`, sin push: pushear deploya y espera el ok de Martín.
- **SIGUE 1** · El menú con la compra con condición, `si_cumple`, con la cuota gratis de Gemini, que hoy se agotó. El ejecutor ya la cumple; el menú está en `banco_pruebas/forma_normal/menu_si_cumple.patch`, con su test xfail PLAN. Se aplica, se corre `python3 -m banco_pruebas.variantes` y las 525 una vez con `traduccion58`; entra si no baja de 507 ni de los pisos de variantes. En un modelo gratis de OpenRouter dio 28 de 30 contra 24. Son la primera reserva real: traducciones que nadie vio.
- **SIGUE 2** · Lo que queda en producción, 18 de 525: información perdida, la compra con condición de C32, C56, C29 y C53 y las cantidades de C25, que es SIGUE 1; y C52, "y ese cuánto" con doce mostrados, donde la vara pide preguntar y el modelo elige el último. Los avisos de la FICHA 73 van solo para lo que la forma normal no cubre: casi todos son ahora una regla, sin segunda llamada.
- **SIGUE 3** · Una reserva de formas nuevas de las complejas, escritas antes de correr, para medir la forma normal con traducciones que no se miraron al escribir las reglas.
- **SIGUE 4** · La próxima compleja: K08 de la vara, siete artículos por rubro, presupuesto de crisis y tres destinos. Misma familia que la de hoy: prueba que lo hecho es de clase. Un guion nuevo en el simulador con su piso, y después WhatsApp. Siguen K13, mayorista, y C46, "de los que te mencioné", una por sesión.
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
