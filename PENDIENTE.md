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

- **DONDE VA** · 22-oct, la ficha nativa es el intérprete del bot, FICHA 76, y lo que la tienda no tiene lo dice el código: cada campo del catálogo es un dato, por su nombre o por la frase del alias; lo que no está, "no tengo el dato"; un tema fuera de la FAQ, "no tengo información escrita"; lo que nadie vende en la tienda, "no tengo X". Las 48 con memoria 36 bien, producción 6 de 7, variantes sobre sus pisos, las 3.107 igual, 544 tests.
- **SIGUE 1** · Cada pregunta del bot con su espera, orden de Martín del 21-oct. Hoy `estado.abiertas` guarda solo el texto de lo que preguntó el bot. Tiene que guardar también qué espera —un modelo de equipo, un color, un sí o no, un nombre— y qué hace con la respuesta. El código ata la respuesta corta a esa espera y la controla contra la fuente antes de seguir. El caso de la noche: "¿qué modelo es tu iPad?", "el último de Samsung", y el bot buscó tablets Samsung en vez de decir que un iPad no es Samsung y seguir con la compatibilidad del K380. Además, "falta el modelo" no hace falta cuando el equipo ya está en el vocabulario, como iPad. Se mide con `regrado.py` y con charlas de varios turnos nuevas, escritas antes de correr.
- **SIGUE 3** · El menú con la compra con condición, `si_cumple`, con la cuota gratis de Gemini: el ejecutor ya la cumple y el menú está en `banco_pruebas/forma_normal/menu_si_cumple.patch`, con su test xfail. Se corren las variantes y las 525; entra si no baja de 512 ni de los pisos de variantes.
- **SIGUE 4** · Producción como banco: los siete casos reales con casillas de Martín, `banco_pruebas/jev/casos_produccion.json`, los corre `pedido_documento/prod7_ficha.py` enteros por el camino vivo: 6 de 7. Falta su piso en la batería, con las respuestas guardadas, y sumar las fichas vivas de producción al banco del adaptador.
- **ABIERTO** · Visto en vivo el 21-oct. El pedido se cierra sin preguntar el medio de pago, y "era por transferencia" se traduce como la política de descuento. "Luces psicodélicas" se busca tal cual, cuando el catálogo tiene retroiluminación RGB. El "Ok" de las 21:52 se procesó y Meta lo aceptó, pero no llegó al teléfono, y la causa no se sabe: repetía igual el mensaje anterior, cosa que ya no pasa, y desde el 22-oct los avisos de Meta quedan en el log. El mismo "Ok" a la 01:30 llegó bien.
- **SIGUE 5** · La próxima compleja: K08 de la vara, siete artículos por rubro, presupuesto de crisis y tres destinos. Misma familia que la de hoy: prueba que lo hecho es de clase. Un guion nuevo en el simulador con su piso, y después WhatsApp. Siguen K13, mayorista, y C46, "de los que te mencioné", una por sesión.
- **ESPERA A MARTIN** · Las formas en que un cliente real dice cada complicada, en texto simple: cada una se vuelve un guion del simulador y suma al piso. Y la corrida nocturna que junta las charlas y corre los casos.
- **ABIERTO** · Lo que el simulador todavía marca en la de los siete artículos: la mitad de las charlas repite una pregunta, y el 32% que no llega es casi todo el modelo perdiendo el medio de pago o anotando un renglón nuevo al repetir el pedido. Sus fallas tienen probabilidades sin medir: cada charla real que se junte las ajusta en `MEDIDO`.
- **ABIERTO** · `catalogo.atar` ya ata el origen partido en país y los campos de sí o no por su clave, 23-oct, `tests/test_atar_indice.py`: de 63 condiciones de la ficha nativa ata 52. Siguen sin atar "silencioso", "chiquito", "que entre en el bolsillo", "de malla" y "marca conocida", que son vagas de verdad, y comparar no tiene herramienta. Se mide con `banco_pruebas/pedido_documento/atar_ficha.py`.
- **ABIERTO** · Lo que la ficha deja mal, FICHA 76: dos renglones del mismo rubro con condiciones por destino toman la del primero y lo condicional se cumple sin condición, los dos xfail de `tests/test_ficha.py`; una búsqueda con tope y sin pedido entra al pedido por `normal.cuenta_de_lo_buscado`; P06 no cierra el 70 por ciento.
- **ABIERTO** · Lo que el flujo todavía no cubre, fuera de las 58: el resumen de la memoria larga cuando el historial pasa el límite, el reparto del pago sobre varios destinos, una condición de precio como C56, y las charlas K y J que faltan en la vara.
- **ABIERTO** · Complejas que siguen mal en vivo: K13 reserva en vez de contestar por mayorista; K08 deja rubros sin buscar; C46 contesta "de los que te mencioné" sin buscar el resto. Dos del mismo rubro a dos destinos ya salen el mismo modelo, por el criterio del rubro del borrador.
- **ABIERTO** · La compra por `reservar` entra al cierre, pero falta verla cerrar un pedido real con nombre y link.
- **ABIERTO** · Un medio que la tienda no toma entra al total sin aviso: "mitad en cripto" cuenta la mitad como pagable. Es el xfail de `tests/test_medio_de_pago_cerrado.py`. Con la agenda el medio lo escribe el modelo y el código lo puede validar contra la FAQ de formas de pago.
- **ABIERTO** · Caché del proveedor, medido el 20-oct con la paga y el ok de Martín: siete llamadas, incluso el mismo pedido exacto tres veces, y el proveedor no cachea nada; cada mensaje cobra unos 3.050 tokens de entrada enteros. Lo único que queda es el caché explícito, que pide la puerta nativa de Gemini y cobra por hora guardado: no conviene con el volumen de hoy.
- **ABIERTO** · El arranque muestra la interpretación "sin medir" porque su piso se archivó. Arreglarlo toca `scripts/`, que deploya.
- **ESPERA A MARTIN** · Decisiones de conducta. K20: la casilla pide el envío de 6.500 a Concordia y el bloque sale gratis por pasar los 250 mil, que es correcto. Ante un tema ambiguo, ¿se repregunta?
- **ESPERA A MARTIN** · Consola y política: alerta de presupuesto y tope de cuota de la clave paga en Google Cloud, y cuánto tiempo se guardan las charlas.
