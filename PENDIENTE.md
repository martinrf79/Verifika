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

- **DONDE VA** · 20-oct, plan de Martín: el intérprete devuelve una agenda, una pregunta por cada cosa que pide el cliente, y el ejecutor la cumple pregunta por pregunta; las pruebas con el modelo van al final. Partes 1 y 2 hechas, en `main` local y SIN PUSH. Sin modelo: la vara da 65 de 65 por el webhook entero, con K10, K11 y K21 adentro, que son la memoria a varios turnos y la charla real de los siete artículos; ninguna pregunta queda sin estado, lo cuida un candado; y en 4 de 181 preguntas el modelo tendría que adivinar el tema, porque la fuente no trae la frase. El turno más pesado da 2.943 tokens. Se borraron las traducciones a la ficha 10, las lecturas del mensaje del cierre viejo y `normalizar`.
- **SIGUE 1** · Martín revisa los seis ejemplos de `interprete.EJEMPLOS` y, si quiere, `banco_pruebas/agendas58.py`: es lo que se le va a pedir al modelo.
- **SIGUE 2** · Una sola corrida con el modelo gratis sobre las 58 y las K, unos 105 turnos, comparada pregunta por pregunta contra `agendas58.py`: una falla ahí es de la consigna o de los ejemplos, no de la información. Falta escribir el comparador. Después, una con Gemini confirma, y el push con el ok de Martín.
- **ESPERA A MARTIN** · Fuente, que pide su permiso: tres frases que la FAQ no trae y harían que el marcador reconozca el tema: "off" para promociones, "envío gratis" para costo_envio y "tarjeta de débito" para formas_pago. Hoy el modelo los elige por el nombre del tema.
- **ABIERTO** · Lo que el flujo todavía no cubre, fuera de las 58: el resumen de la memoria larga cuando el historial pasa el límite, el reparto del pago sobre varios destinos, una condición de precio como C56, y las charlas K y J que faltan en la vara.
- **ABIERTO** · Complejas que siguen mal en vivo: K13 reserva en vez de contestar por mayorista; K08 deja rubros sin buscar; C46 contesta "de los que te mencioné" sin buscar el resto; "dos auriculares" a dos destinos da dos modelos distintos.
- **ABIERTO** · La compra por `reservar` entra al cierre, pero falta verla cerrar un pedido real con nombre y link.
- **ABIERTO** · Un medio que la tienda no toma entra al total sin aviso: "mitad en cripto" cuenta la mitad como pagable. Es el xfail de `tests/test_medio_de_pago_cerrado.py`. Con la agenda el medio lo escribe el modelo y el código lo puede validar contra la FAQ de formas de pago.
- **ABIERTO** · El cache de la clave da cero: el prompt fijo no llega al mínimo del proveedor. Medir el umbral.
- **ABIERTO** · El arranque muestra la interpretación "sin medir" porque su piso se archivó. Arreglarlo toca `scripts/`, que deploya.
- **ESPERA A MARTIN** · Decisiones de conducta. K20: la casilla pide el envío de 6.500 a Concordia y el bloque sale gratis por pasar los 250 mil, que es correcto. Ante un tema ambiguo, ¿se repregunta?
- **ESPERA A MARTIN** · Catálogo, que pide su permiso: los auriculares bluetooth figuran con cable porque `specs_por_modelo.csv` no trae bluetooth, y el origen es prosa, sin un campo normalizado.
- **ESPERA A MARTIN** · Consola y política: alerta de presupuesto y tope de cuota de la clave paga en Google Cloud, y cuánto tiempo se guardan las charlas.
