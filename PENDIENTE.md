# PENDIENTE — dónde va el trabajo y lo que queda abierto

El hook del arranque imprime el titular de cada ítem de abajo de la raya. Por eso cada titular dice solo lo
esencial, y el orden importa: **la sesión nueva arranca por el primer ítem SIGUE, sin preguntar.**

- El objetivo, el plan y las reglas: `CLAUDE.md`. No se copian acá.
- Lo hecho: `git log`. Lo concluido en detalle: la ficha abierta, hoy la FICHA 69.
- Lo que Martín decidió para siempre: `papeles/DECISIONES.md`.

**Al cerrar cada sesión:** se reescribe el ítem DONDE VA, se reordenan los SIGUE y se borra lo que quedó hecho u
obsoleto. Máximo veinte ítems, lo controla `tests/test_pendiente.py`. Lo pendiente de código va además como un
test que falla, `xfail(strict=True)`, con motivo `PLAN:` o `A MEDIAS:`.

Estados: **DONDE VA** · **SIGUE** · **ABIERTO** · **ESPERA A MARTIN**.

---

- **DONDE VA** · 16-oct, sesión de orden: los papeles ya no se contradicen sobre el camino vivo ni sobre OpenRouter; `MAPA.md` nombra las partes, `MAPA_CABLEADO.md` queda histórico y `papeles/ARQUITECTURA.md` pasó al archivo. El plan 1 de CLAUDE.md está a medias. El código lee el estado de la charla como datos, `ficha_charla.estado`, y no un texto. Se arregló el precio cortado de la ficha, "$37.500" llegaba como "$37" en 244 de 511 charlas, y el lector viejo que sumaba todo lo mostrado. Deployado y verde. Mediciones: 511 grabadas sin modelo, sin casillas rotas; el código entrega bien 138 de los 167 casos bien interpretados. Falta medir en vivo.
- **SIGUE 1** · El banco tiene que frenar al primer "cuota excedida" del día. El 16-oct, `sonda_charlas` mandó 334 pedidos en 10 minutos y 327 eran reintentos: la cuota de 500 de la gratis se fue en eso. Es `banco_pruebas/`, no deploya.
- **SIGUE 2** · Conectar OpenRouter al instrumento oficial. La clave `OPENROUTER_API_KEY` ya está en el entorno y se usó el 14-oct, pero sólo desde `banco_pruebas/nexos/necesita.py`, con Haiku, que es paga y se anota en `libro_paga`. `puerta.py` y `sonda_charlas` todavía van sólo por Gemini o DeepSeek. Falta sumarlo como proveedor en `config.py`, que es config operativa, y elegir un modelo gratis con salida estructurada: 1.000 pedidos por día, a 20 por minuto. Así todas las sesiones miden con el mismo instrumento. Antes de deployar, Gemini confirma con una corrida.
- **SIGUE 3** · Las 29 fallas del código con la traducción ya buena: `python3 banco_pruebas/nexos/por_el_codigo.py --de f9_g174` da 138 de 167. Por clase, y un caso puede caer en varias: identidad por nombre dentro de una cuenta, 11; total del pedido que no sale, 9; condiciones "si pasa X, hacé Y", 8; búsquedas con la condición en palabras, 8. Se empieza por identidad y total: el pedido llega con nombres en vez de ids.
- **SIGUE 4** · El plan 1, la otra mitad: que el documento de la charla guarde el pedido como un solo dato. Hoy vive en `grupos_envio`, `carrito_vigente`, `pedido_pendiente` y `reparto_pago`, y lo buscado es texto en `criterio_cliente`. Lo leen también el cierre y el cobro: medir con las 511 grabadas.
- **SIGUE 5** · Las once capas de corrección, plan 3: una por commit, por `puerta.py`. Cada una es un xfail en `tests/test_once_capas.py`. Con ellas baja `app/`: 16.760 líneas, meta la mitad. Incluye los recortes de `tablero._HASTA`: sacarlos rompe G06, porque `_elegidos` descarta la notebook si el cliente no dijo "16gb".
- **SIGUE 6** · La medición en vivo de lo del 16-oct: las 20 de memoria, `gg_estado_1` contra `gp_montos_1`. Con la gratis de Gemini, o con OpenRouter cuando esté.
- **ABIERTO** · LA VARA FIJA, `pytest tests/test_casos_grabados.py`: 23 de 24 charlas grabadas bien; C35 marcada, porque "otras opciones" no deja afuera lo mostrado y el intérprete pierde "gamer". `tests/grabadas_techo.json` sólo baja.
- **ABIERTO** · Tres parches del 16-oct, a reemplazar por el arreglo en su causa: un bloque igual no suma dos veces, sin saber por qué la memoria tenía el destino repetido; se borra el renglón corto que repite plata de un bloque; "el resto" del reparto no se renombra.
- **ABIERTO** · Complejas que siguen mal en vivo: K13 reserva en vez de contestar por mayorista; K10 y K11 pierden el pedido anotado a los varios turnos; K08 deja rubros sin buscar; C46 contesta "de los que te mencioné" sin buscar el resto; "dos auriculares" a dos destinos da dos modelos distintos.
- **ABIERTO** · El redactor dice "todo es chino" aunque el origen sea Taiwán o China, y a veces pregunta en vez de armar el 70/30.
- **ABIERTO** · La compra por `reservar` entra al cierre, pero falta verla cerrar un pedido real con nombre y link.
- **ABIERTO** · `motor.esquema` ya no lo usa el turno, sólo tests y banco: se borra con sus tests en su propio commit. Baja líneas.
- **ABIERTO** · El cache de la clave da cero: el prompt fijo no llega al mínimo del proveedor. Medir el umbral.
- **ABIERTO** · El arranque muestra la interpretación "sin medir" porque su piso se archivó. Arreglarlo toca `scripts/`, que deploya.
- **ESPERA A MARTIN** · Decisiones de conducta. K18: un modelo sin color que no se mostró, ¿se pregunta el color o se nombran los que hay? K20: la casilla pide el envío de 6.500 a Concordia y el bloque sale gratis por pasar los 250 mil, que es correcto. Ante un tema ambiguo, ¿se repregunta?
- **ESPERA A MARTIN** · Catálogo, que pide su permiso: los auriculares bluetooth figuran con cable porque `specs_por_modelo.csv` no trae bluetooth, y el origen es prosa, sin un campo normalizado.
- **ESPERA A MARTIN** · Consola y política: alerta de presupuesto y tope de cuota de la clave paga en Google Cloud, y cuánto tiempo se guardan las charlas.
