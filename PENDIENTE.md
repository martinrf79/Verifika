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

- **DONDE VA** · 21-oct, cierre: medido lo que el modelo de producción traduce, `banco_pruebas/traduccion58.py`. Los 105 turnos de las 58 y las K en cinco formas —original, mal escrita, WhatsApp, redactada y coloquial— y tres veces, con la consigna y la devuelta de hoy: 82 de 105 turnos salen bien en las cinco formas y las tres veces. Ninguno sale a veces: con temperatura cero el modelo repite, así que cada falla es fija y se puede atacar por clase. Cambiar el vocabulario no empeora nada. Las clases que fallan: pedir el costo de un envío a un lugar lo traduce como política y no como envío, C10, C26 y C47; un dato del producto como la garantía va a política, C58; un sí corto que pide la cuenta lo toma como confirmar, K21; "ese" con muchos mostrados elige uno en vez de dejar la lista, C52; elegir entre dos por una condición se aplana, C32; soltar una condición pierde la exclusión, C35. Costó 1,35 dólares reales con la paga, con el ok de Martín. Otros modelos, atados igual y una vez cada turno y forma, contra Gemini 455 de 525: Haiku 468, GPT-5.6 Luna 457, DeepSeek 453, GPT-5.4 mini 440, y GPT-5.6 Terra 429 contra 423 en 482. Nada contundente: el techo es el menú, con dos puertas para una misma pregunta, no el modelo. Haiku solo, con la fuente entera y sin código, 171 de 187 contra 164 del bot: entiende mejor pero erra el más barato del catálogo e inventa stock.
- **SIGUE 1** · Llegar a 525 de 525 en `traduccion58.py` con Gemini y la clave gratis. LA CAUSA, hallada el 21-oct al final: la tabla de pistas de `flujo/marcador.py` empuja al modelo a la puerta equivocada. A "cuánto sale el envío a Posadas" le marca el tema de política costo_envio y no marca Posadas como destino; a "el G305 tiene garantía" le marca el tema garantía además del producto. Por eso todos los modelos fallaron parecido. Pasos: 1, diagnóstico gratis con `suficiencia.py` de los 23 turnos que fallan, cada uno en una causa: pista equivocada, dos puertas, código que no acepta una lectura válida, casilla discutible o falla del modelo. 2, arreglos por clase sin modelo: el marcador marca destinos con `envio.clasificar_provincia` y no ofrece temas que repiten una acción; confirmar también muestra el total; el código elige cuando la condición decide. 3, batería y `cableado58` en 65 de 65. 4, con la gratis, primero los 23 en cinco formas una vez, después las 525. 5, las casillas discutibles, como el "Sip" de K21, se consultan a Martín.
- **SIGUE 2** · Después de SIGUE 1. La próxima compleja: K08 de la vara, siete artículos por rubro, presupuesto de crisis y tres destinos. Misma familia que la de hoy: prueba que lo hecho es de clase. Un guion nuevo en el simulador con su piso, y después WhatsApp. Siguen K13, mayorista, y C46, "de los que te mencioné", una por sesión.
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
