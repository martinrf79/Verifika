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

- **DONDE VA** · 17-oct, la reducción de `app/`, paso 1 hecho: los comentarios y docstrings quedan en su primera oración, sin tocar código, y `app/` bajó de 16.760 a 12.108 líneas en dos días. El cableado se mide sin modelo con `python3 -m banco_pruebas.grabadas`: 501 charlas, diez minutos. Sigue el paso 2, las once capas de `tablero.py`, una por commit, cada una primero por las grabadas y después por `puerta.py` en vivo. Estimado final: entre 7.000 y 8.000 líneas. El plan 1 sigue a medias: falta medir en vivo el estado de la charla.
- **SIGUE 1** · El banco tiene que frenar al primer "cuota excedida" del día. El 16-oct, `sonda_charlas` mandó 334 pedidos en 10 minutos y 327 eran reintentos: la cuota de 500 de la gratis se fue en eso. Es `banco_pruebas/`, no deploya.
- **SIGUE 2** · Conectar OpenRouter al instrumento oficial. La clave `OPENROUTER_API_KEY` ya está en el entorno y se usó el 14-oct, pero sólo desde `banco_pruebas/nexos/necesita.py`, con Haiku, que es paga y se anota en `libro_paga`. `puerta.py` y `sonda_charlas` todavía van sólo por Gemini o DeepSeek. Falta sumarlo como proveedor en `config.py`, que es config operativa, y elegir un modelo gratis con salida estructurada: 1.000 pedidos por día, a 20 por minuto. Así todas las sesiones miden con el mismo instrumento. Antes de deployar, Gemini confirma con una corrida.
- **SIGUE 3** · Las 29 fallas del código con la traducción ya buena, medidas el 16-oct con `por_el_codigo`, archivado en `archivo/nexos_17oct/` porque traía su propio traductor y una vara que no sigue la regla del color. Lo visto en las de identidad: casi todas piden la cuenta de un modelo en varios colores sin color, y la cuenta no cuenta y pregunta, que es la regla. K18 quedó decidido el 17-oct, decisión 46: se nombran los colores y se pregunta, así que esas fallas son de la vara de `por_el_codigo`, no del código. Siguen total del pedido, 9; condiciones "si pasa X, hacé Y", 8; búsquedas con la condición en palabras, 8. El cableado se mide con `python3 -m banco_pruebas.grabadas`.
- **SIGUE 4** · El plan 1, la otra mitad: que el documento de la charla guarde el pedido como un solo dato. Hoy vive en `grupos_envio`, `carrito_vigente`, `pedido_pendiente` y `reparto_pago`, y lo buscado es texto en `criterio_cliente`. Lo leen también el cierre y el cobro: medir con las 511 grabadas.
- **SIGUE 5** · Las once capas de corrección, plan 3, una por commit. Cada una es un xfail en `tests/test_once_capas.py`. Medido el 17-oct apagando cada una por separado contra las 501 grabadas, casillas rotas y turnos con montos distintos: `_sobre_lo_buscado` 0 y 0, `_elegidos` 2 y 3, `_cuenta_del_codigo` 2 y 8, `_heredar_exclusiones` 3 y 5, `_conservar` 3 y 29, `_sobre_el_pedido` 13 y 63, `_resolver_items` 88 y 171, `_normalizar` 169 y 188. Tres esperan al plan 2 porque tapan algo del intérprete: `_reparto_leido`, sin ella K21 turno 7 pierde el descuento del 70%; `_envios_juntos`, el menú dice envío a un destino; `_sobre_lo_buscado` no cambia nada, pero su campo del menú queda suelto y sacarlo se mide en vivo. Las que rompen pocas son las próximas: se mira qué charla rompe y lo que hacen pasa al estado o al menú. `app/`: 12.108 líneas, unas 9.100 de código.
- **SIGUE 6** · La medición en vivo de lo del 16-oct: las 20 de memoria, `gg_estado_1` contra `gp_montos_1`. Con la gratis de Gemini, o con OpenRouter cuando esté.
- **ABIERTO** · LA VARA FIJA, `pytest tests/test_casos_grabados.py`: 23 de 24 charlas grabadas bien; C35 marcada, porque "otras opciones" no deja afuera lo mostrado y el intérprete pierde "gamer". `tests/grabadas_techo.json` sólo baja.
- **ABIERTO** · Tres parches del 16-oct, a reemplazar por el arreglo en su causa: un bloque igual no suma dos veces, sin saber por qué la memoria tenía el destino repetido; se borra el renglón corto que repite plata de un bloque; "el resto" del reparto no se renombra.
- **ABIERTO** · Complejas que siguen mal en vivo: K13 reserva en vez de contestar por mayorista; K10 y K11 pierden el pedido anotado a los varios turnos; K08 deja rubros sin buscar; C46 contesta "de los que te mencioné" sin buscar el resto; "dos auriculares" a dos destinos da dos modelos distintos.
- **ABIERTO** · El redactor dice "todo es chino" aunque el origen sea Taiwán o China, y a veces pregunta en vez de armar el 70/30.
- **ABIERTO** · La compra por `reservar` entra al cierre, pero falta verla cerrar un pedido real con nombre y link.
- **ABIERTO** · Un medio que la tienda no toma entra al total sin aviso: "mitad en cripto" cuenta la mitad como pagable. Es el xfail de `tests/test_medio_de_pago_cerrado.py`. Cerrarlo contra la FAQ de formas de pago rompió K21 grabada, porque `tablero._reparto` toma "setenta" como medio cuando el cliente dijo "setenta treinta". Primero eso, después el cierre, y se mide con las grabadas.
- **ABIERTO** · El cache de la clave da cero: el prompt fijo no llega al mínimo del proveedor. Medir el umbral.
- **ABIERTO** · El arranque muestra la interpretación "sin medir" porque su piso se archivó. Arreglarlo toca `scripts/`, que deploya.
- **ESPERA A MARTIN** · Decisiones de conducta. K20: la casilla pide el envío de 6.500 a Concordia y el bloque sale gratis por pasar los 250 mil, que es correcto. Ante un tema ambiguo, ¿se repregunta?
- **ESPERA A MARTIN** · Catálogo, que pide su permiso: los auriculares bluetooth figuran con cable porque `specs_por_modelo.csv` no trae bluetooth, y el origen es prosa, sin un campo normalizado.
- **ESPERA A MARTIN** · Consola y política: alerta de presupuesto y tope de cuota de la clave paga en Google Cloud, y cuánto tiempo se guardan las charlas.
