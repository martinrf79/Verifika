# PENDIENTE — dónde va el trabajo y lo que queda abierto

El hook del arranque imprime el titular de cada ítem de abajo de la raya. Por eso cada titular dice solo lo
esencial, y el orden importa: **la sesión nueva arranca por el primer ítem SIGUE, sin preguntar.**

- El objetivo, el plan y las reglas: `CLAUDE.md`. No se copian acá.
- Lo hecho: `git log`. Lo concluido en detalle: la ficha abierta, hoy la FICHA 70.
- Lo que Martín decidió para siempre: `papeles/DECISIONES.md`.

**Al cerrar cada sesión:** se reescribe el ítem DONDE VA, se reordenan los SIGUE y se borra lo que quedó hecho u
obsoleto. Máximo veinte ítems, lo controla `tests/test_pendiente.py`. Lo pendiente de código va además como un
test que falla, `xfail(strict=True)`, con motivo `PLAN:` o `A MEDIAS:`.

Estados: **DONDE VA** · **SIGUE** · **ABIERTO** · **ESPERA A MARTIN**.

---

- **DONDE VA** · 18-oct, FICHA 70 abierta: primero se fija la traducción del modelo, caso por caso sobre las 58, y después se escribe el código contra lo que quede; el tablero de producción no se toca en esta fase. El contrato 2, comandos con números de referencia, está en `banco_pruebas/nexos/contrato2.py` como forma de `desmenuzado.py`: Gemini 137 de 174, Haiku 151 con el contrato corregido, la ficha 9 dio 167. La versión 3 de lo que recibe el modelo, en la FICHA 70, junta lo que funcionó de la ficha 9, los nexos, los ejemplos y las entrevistas.
- **SIGUE 1** · La tabla de las 58 en el contrato 2, FICHA 70: el mensaje, el estado escrito a mano si es de memoria y los comandos correctos de cada una. La revisa Martín antes de correr nada, porque ahí se decide la conducta. Después, la versión 3 en `contrato2.py` y la vuelta caso por caso con Gemini y Haiku, con el caso probado afuera de sus propios ejemplos.
- **SIGUE 2** · Separar modelo y contrato: Gemini sobre el contrato corregido de `c2c_haiku_1`, con la gratis. Y antes, sin modelo, mirar las ocho fallas de pedido de esa corrida, que pueden ser del ejecutor del banco.
- **SIGUE 3** · `sonda_charlas` tiene que frenar al primer "cuota excedida" del día, como ya hace `desmenuzado.py` desde el 17-oct. El 16-oct mandó 334 pedidos en 10 minutos y 327 eran reintentos. La cuota gratis real del 17-oct se acabó cerca de los 220 pedidos.
- **SIGUE 4** · OpenRouter en el instrumento oficial: `desmenuzado.py` ya lo usa por `necesita.cli`; faltan `puerta.py` y `sonda_charlas`. Anthropic no acepta el esquema estricto con tantos campos opcionales: va el esquema compacto en el prompt, `contrato2.esquema_texto`.
- **ABIERTO** · El código, después de la FICHA 70: el estado único de la charla en vez de `grupos_envio`, `carrito_vigente`, `pedido_pendiente` y `reparto_pago`; el ejecutor de comandos en vez de las once capas de `tablero.py`, que son xfail en `tests/test_once_capas.py`; las 29 fallas del código con la traducción buena; y la medición en vivo de las 20 de memoria. Se escribe contra las traducciones aprobadas de la fase de las 58.
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
