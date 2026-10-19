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

- **DONDE VA** · 20-oct, plan nuevo de Martín: el intérprete devuelve una agenda, una pregunta por cada cosa que pide el cliente, con una acción de un menú cerrado; las pruebas con el modelo van al final. Parte 1 hecha, en `main` local y SIN PUSH: `flujo/agenda.py` es el contrato, `flujo/marcador.py` le muestra al modelo lo que el código reconoce en el mensaje, `interprete.py` tiene la consigna con seis ejemplos y la libreta numerada. Medido sin modelo, `tests/test_agenda.py`: 132 de 135 preguntas de las 58 y las K tienen a la vista todo lo que necesitan, y el turno más pesado da 2.975 tokens contra 4.596 de antes. NO SE PUSHEA hasta la parte 2: el turno todavía ejecuta la ficha 10 y con la agenda en vivo no respondería. Se borró el cierre viejo de `leads`, que el flujo ya no usaba.
- **SIGUE 1** · Parte 2, el cableado: el ejecutor cumple la agenda pregunta por pregunta, y cada una termina respondida, repreguntada o imposible con su motivo; una sin estado frena la respuesta. Lo que queda sin responder y la repregunta se guardan en `estado.abiertas`, que la libreta ya muestra como R1. `cableado58.py` pasa a `agendas58.py` y se borran `traducciones58.py` y `normalizar`. La vara de `vara_58.json` no se toca.
- **SIGUE 2** · Martín revisa `banco_pruebas/agendas58.py` y los seis ejemplos de `interprete.EJEMPLOS`: es lo que se le va a pedir al modelo.
- **SIGUE 3** · Recién después de la parte 2, una sola corrida con el modelo gratis sobre las 58 y las K, comparada pregunta por pregunta contra `agendas58.py`; una falla ahí es de la consigna. Una con Gemini confirma antes del deploy.
- **ABIERTO** · Lo que el flujo todavía no cubre, fuera de las 58: el resumen de la memoria larga cuando el historial pasa el límite, el reparto del pago sobre varios destinos, una condición de precio como C56, y las charlas K y J que faltan en la vara.
- **ABIERTO** · Complejas que siguen mal en vivo: K13 reserva en vez de contestar por mayorista; K10 y K11 pierden el pedido anotado a los varios turnos; K08 deja rubros sin buscar; C46 contesta "de los que te mencioné" sin buscar el resto; "dos auriculares" a dos destinos da dos modelos distintos.
- **ABIERTO** · La compra por `reservar` entra al cierre, pero falta verla cerrar un pedido real con nombre y link.
- **ABIERTO** · Un medio que la tienda no toma entra al total sin aviso: "mitad en cripto" cuenta la mitad como pagable. Es el xfail de `tests/test_medio_de_pago_cerrado.py`. Cerrarlo contra la FAQ de formas de pago rompió K21 grabada, porque `tablero._reparto` toma "setenta" como medio cuando el cliente dijo "setenta treinta". Primero eso, después el cierre, y se mide con las grabadas.
- **ABIERTO** · El cache de la clave da cero: el prompt fijo no llega al mínimo del proveedor. Medir el umbral.
- **ABIERTO** · El arranque muestra la interpretación "sin medir" porque su piso se archivó. Arreglarlo toca `scripts/`, que deploya.
- **ESPERA A MARTIN** · Decisiones de conducta. K20: la casilla pide el envío de 6.500 a Concordia y el bloque sale gratis por pasar los 250 mil, que es correcto. Ante un tema ambiguo, ¿se repregunta?
- **ESPERA A MARTIN** · Catálogo, que pide su permiso: los auriculares bluetooth figuran con cable porque `specs_por_modelo.csv` no trae bluetooth, y el origen es prosa, sin un campo normalizado.
- **ESPERA A MARTIN** · Consola y política: alerta de presupuesto y tope de cuota de la clave paga en Google Cloud, y cuánto tiempo se guardan las charlas.
