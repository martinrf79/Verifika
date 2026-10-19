# FICHA 71 — El borrador: un solo objeto por charla, que el código re-deriva entero en cada turno

20-oct-2026, con Martín. Plan escrito para codificarse en una sesión nueva, con el contexto limpio.

## Por qué

La agenda resolvió la interpretación: en la primera charla real del 20-oct el modelo escribió casi la misma agenda
que la escrita a mano. Lo que falla es el cableado y la memoria. En la segunda charla real del 20-oct, 13:43 UTC, el
bot preguntó "¿lo sumo el teclado?", el cliente dijo que sí dos veces, y el bot volvió a preguntar lo mismo:

- La memoria vive en seis piezas sueltas de `estado`: `pedido`, `por_rubro`, `abiertas`, `sin_anotar`, `reparto` y
  `busqueda`, más `nombre_pedido` y `cerrado` para el cierre. Cada turno el ejecutor rearma la charla juntándolas.
- Lo que el cliente pidió y no se pudo resolver no tiene un lugar propio: queda como texto en una repregunta.
- Cada arreglo suma una pieza, y las piezas chocan. Es el loop de arreglos.

## Qué es

Un único documento por charla, `estado.borrador`, que es la verdad de todo lo que la charla construye. Guarda **lo
que dijo el cliente**, no lo que calculó el código: lo calculado se vuelve a derivar entero en cada turno.

- **renglones**: cada cosa que el cliente quiere llevar o presupuestar, `L-1`, `L-2`... Cada renglón guarda lo dicho:
  qué es —un modelo, un rubro o "los otros"—, cantidad, color, destino, la condición de la que depende, y la cita.
- **criterios**: por rubro, cómo eligió el cliente —"los más baratos", "que no sea chino", "Logitech"—. Un renglón
  de rubro se resuelve con el criterio de su rubro.
- **total_dicho**: cuántos artículos dijo el cliente que son, si lo dijo —"son 7"—.
- **pago**: los porcentajes y los medios, lo dicho.
- **cliente**: nombre, localidad, quién es.
- **etapa del cierre**: se deriva, no se guarda suelta: armando, completo, falta el nombre, cerrado con su huella.

Afuera del borrador quedan solo `mostrados` —lo que el cliente leyó, para las referencias M-n— y el historial corto.

## Cómo lo llena el código — un orden fijo, un dueño por paso

En cada turno, después del intérprete y sin volver a leer el mensaje:

1. **Aplicar** las operaciones del modelo sobre lo dicho: agrega renglones, cambia un campo de `L-n`, saca `L-n`, fija
   `total_dicho`, el criterio de un rubro, el pago o un dato del cliente. Solo escribe campos dichos.
2. **Resolver** cada renglón desde lo dicho, todos, en cada turno:
   - un modelo, por `catalogo.identificar`, con los tres veredictos;
   - un rubro, por la búsqueda de ese rubro con su criterio: la primera fila;
   - "los otros", contando: lo pedido por rubro, o `total_dicho`, menos lo ya asignado;
   - el color, por la variante con stock;
   - la condición, por el resultado de la consulta de la que depende.
3. **Validar** las invariantes del borrador entero: las cantidades suman lo dicho; cada porcentaje tiene medio; con
   varios destinos, cada renglón tiene el suyo.
4. **Marcar lo que falta**: lo que no se resuelve o no cierra no se borra ni se anota a medias. Queda en su renglón con
   un tipo de faltante: modelo, color, cantidad, destino, stock, medio o confirmar.
5. **Derivar**: la cuenta por destino, el total general, el reparto, el cobro y el lead, solo con renglones resueltos y
   solo si no falta nada. El cierre se deriva de borrador completo más nombre.
6. **Preguntar**: una pregunta por tipo de faltante, armada por un solo generador desde el faltante, con los datos del
   renglón. Ningún paso escribe una pregunta suelta.

Como todo se re-deriva desde lo dicho, una corrección cambia una entrada y todo lo de abajo se recalcula solo. Esas son
las "correcciones automáticas acorde al caso": no se escriben por caso, salen de recalcular.

## Cuándo interviene el modelo

Una vez por turno, como hoy, y solo para traducir el mensaje. Nunca resuelve, cuenta, decide una pregunta ni escribe
la respuesta. Su salida tiene dos partes, las dos con el menú cerrado de la agenda:

- **consultas**: buscar, producto, política, compatibilidad, envío, explicar. Se contestan en el turno y lo leído
  pasa a `mostrados`.
- **operaciones sobre el borrador**, que reemplazan a `comprar`: agrega, cambia `L-n`, saca `L-n`, total, criterio,
  pago. Señala con `L-n` y `M-n`, nunca con nombres reescritos.

Cómo cae cada grupo de las 58:

- **A, base**: una consulta. **I, lo que no entra**: otro.
- **B, multipregunta**: varias entradas en la misma agenda, en el orden del cliente.
- **C, alcance**: cada condición, cantidad o destino va en su renglón o en el criterio de su rubro.
- **D, dependencia**: la condición va en el renglón y apunta a una consulta; la evalúa el código.
- **E, corrección**: una operación cambia o saca sobre `L-n`; si es del mismo mensaje, otro con "corrige".
- **F, dueños**: compatibilidad o afirma, consultas.
- **G, memoria**: referencias `L-n` y `M-n`; la respuesta a una repregunta es una operación sobre el renglón que la
  pidió.
- **H, cadenas**: combinaciones de lo anterior, sin forma nueva.

Medido después, no antes: si un mensaje solo contesta un faltante y el marcador encuentra exactamente un valor de ese
tipo —un color, un número, un medio—, el código lo llena sin llamar al modelo.

## Cómo actúa la memoria

- El borrador vive en el documento de la charla, en Firestore, como hoy `estado_charla`.
- La libreta que lee el modelo es el borrador mostrado: cada `L-n` con lo dicho, su estado y lo que le falta, los
  criterios, el pago, y lo mostrado con `M-n`. El modelo solo señala.
- No crece con los turnos, crece con los renglones: una charla larga no pierde el pedido ni necesita resumen.
- Una repregunta no se guarda como texto: es el faltante de un renglón. La respuesta llena ese renglón.

## En qué se diferencia de la ficha de la charla, FICHA 68, y de la ficha 10

- **La ficha 68 era una vista para el modelo**; la verdad seguía en nueve campos y once capas. El borrador es la verdad
  única, y la libreta es su vista.
- **La ficha 68 guardaba resultados**: ids y precios. Por eso se pudrían: el "$37" en vez de "$37.500" y el envío viejo
  de Posadas de la FICHA 69. El borrador guarda lo dicho y re-deriva los resultados en cada turno.
- **Lo pendiente era otro lugar**, `pedido_pendiente`, y ahí se perdía K21. En el borrador es un estado del renglón.
- **La ficha 68 decidía cuándo preguntar comparando antes y después**, una heurística. El borrador pregunta por
  faltantes tipados, con un solo generador.
- **La ficha 10 rearmaba el pedido entero en cada mensaje**; el borrador recibe operaciones sobre renglones numerados.
- **El redactor escribía la plata**; hoy y en el borrador, la escribe el código.

## Los nexos, para las complejas

Un grafo fijo de dependencias, que se recalcula en el mismo orden en cada turno:

criterio del rubro → renglones de ese rubro → "los otros" contra el total → cuenta por destino → total general →
reparto del pago → cobro y lead.

- Un renglón con condición depende de una consulta del turno o de otro renglón.
- "Lo de Rosario" es el grupo de renglones con ese destino.
- "Los más baratos de cada clase" es una operación sobre los criterios: todos los renglones de rubro se re-resuelven.
- "Son 7, lo demás como te dije" fija `total_dicho`, y "los otros" se recuenta solo.
- "El teclado era una memoria" cambia lo que es `L-3`.

## Qué reemplaza y qué se borra

- De `estado`: `pedido`, `por_rubro`, `abiertas`, `reparto`, `nombre_pedido` y `cerrado` pasan al borrador.
- Del ejecutor: `_comprar`, `Turno.pedido`, la parte de `_cuenta` que arma sin pedido, el control "fuera de la lista",
  la unión de compras y `sin_anotar`.
- Del cierre: lee la etapa derivada del borrador.
- El techo de líneas de `app/` no sube.

## Cómo se mide y cuándo está hecho

- La vara: las 65 de `vara_58.json` por el webhook entero, con sus casillas sin tocar. Las agendas a mano de
  `agendas58.py` cambian solo en `comprar`, que pasa a operaciones sobre `L-n`.
- Las dos charlas reales del 20-oct como test: `tests/test_charla_real_20oct.py` y
  `tests/test_charla_real_20oct_b.py`, que hoy es xfail con motivo `PLAN: FICHA 71`.
- La suficiencia, en 181 de 181, y el peso por turno bajo 3.000 tokens.
- Hecho es: la vara verde, las dos reales verdes, y después diez charlas reales seguidas sin defecto en WhatsApp.

## Pasos, cada uno en su commit, en este orden

1. El borrador y su resolución, en un archivo nuevo de `app/core/flujo/`, con sus tests unitarios.
2. El ejecutor llama al borrador en lugar de `_comprar`; las agendas a mano pasan a operaciones; la vara verde.
3. La libreta muestra el borrador; la consigna y sus ejemplos apuntan a `L-n`; la suficiencia verde.
4. El cierre lee la etapa del borrador; se borra lo reemplazado; el techo de líneas.
5. Push con el ok de Martín, y la prueba en WhatsApp.

## Las reglas para no volver al loop

- Cada decisión tiene un solo dueño, de los seis pasos de arriba. Un arreglo que decide lo mismo en otro lado no entra.
- Toda falla real entra como test con la agenda exacta del modelo antes de arreglarla. Si un arreglo rompe un test
  anterior, se revierte el arreglo.
- Si la misma clase falla tres veces en vivo después de arreglada, se cambia de nivel: el prototipo con sandbox, en el
  banco, medido con la misma vara.

Fuentes de afuera: Andreas et al., *Task-Oriented Dialogue as Dataflow Synthesis*, TACL 2020, la charla como un grafo
con operaciones de referencia y revisión; y PyTOD, 2025, cambios cortos sobre un objeto en vez de rearmar el estado.
