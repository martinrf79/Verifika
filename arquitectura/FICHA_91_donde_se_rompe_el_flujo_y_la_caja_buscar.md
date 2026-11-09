# FICHA 91 — Dónde se rompe el flujo, y la caja BUSCAR

7-nov-2026, con Martín. **La sesión siguiente arranca por acá**, antes de la FICHA 89 y la 90.

## Cómo está el bot hoy, 8-nov, para que ninguna sesión lo discuta otra vez

- **El agente NO redacta libre.** `agente._llamar` obliga a llamar una herramienta, `tool_choice: required`, y la única de respuesta
  es `responder` (`respuesta.herramienta_responder`): cita por número productos, reglas y envíos, y elige columnas de la tabla, todo
  con enumeraciones cerradas por la API. Lo único libre es el saludo, la pregunta y el nombre de un dato que falta, cortos y con
  largo máximo; el control mira ahí números, marcas, valores y medios de pago. Los datos los pega el código con las filas reales.
- **Las fichas 88 y 89 que la daban por descartada están corregidas:** vale la 90 y el código.
- **Hecho el 8-nov (7-nov por fecha de commit), en `tabla.consultar`:** el corte de 25 filas lo reparte el código entre rubros, una
  fila por rubro a la vez y a la vista en el orden del modelo, y una frase del nombre que vuelve vacía se repite palabra por palabra.
  Los dos `xfail` de `tests/test_cableado_cajas.py` pasan y se sacaron. Batería: 522 pruebas. Regrabadas con el modelo gratis C38,
  C43, C52 y K12. La foto del candado cambió en un turno, `7f8cd4a5ca t1`: la lista de gaming ahora reparte los rubros y el Kumara
  K552 que citaba el modelo grabado ya no entra entre las 25. El techo de `app/` subió de 8768 a 8776, decisión marcada a Martín.
- **Falta:** terminar la corrida `--gratis` de las 26 charlas, cortada por la cuota en K13 con 46 de 49 turnos bien, y las otras dos
  corridas. Y medir en WhatsApp con las dos frases que fallaron.
- **Lo que Martín pidió ver el 8-nov** y esta ficha deja asentado: la vara que de verdad importa es el examen real, las 42 charlas
  reales con lo correcto verificado contra el catálogo, 80 de 113 turnos bien el 3-nov, 71%. El 74 de 75 de las 26 grabadas no predice
  WhatsApp. Un cambio entra solo si no rompe un turno que ya andaba.

## El problema, en palabras de Martín

Meses con el mismo cuello: el bot responde bien un caso y falla otro, se arregla una cosa y se rompe otra, y no hay forma de confiar
en una medición que dependa de lo que recuerda una sesión. Pidió un diagrama de todo el flujo, numerado, que no se pueda olvidar, y
una medición que se pueda auditar. Ejemplo que lo disparó, en WhatsApp: "pasame todas las notebooks y tablets" mostró solo notebooks.

## Lo que se hizo y se midió el 7-nov

- **El diagrama, generado del código.** `banco_pruebas/diagrama.py` lee `app/` con `ast` y escribe `arquitectura/DIAGRAMA_FLUJO.md`: 487
  funciones y clases en 10 cajas del turno y una de infraestructura, el cableado real entre cajas, la memoria del agente y lo que ninguna
  entrada alcanza. `tests/test_diagrama.py` falla si una función queda sin caja o si el archivo no es el de hoy. Para regenerarlo:
  `python3 banco_pruebas/diagrama.py`. Hay una página con el mismo contenido, privada, foto del commit `50cbfa0`:
  https://claude.ai/artifact/VZWetCiELCezwosaW3iVSw
- **La traza por cajas.** `banco_pruebas/traza_cajas.py` corre un turno por el código vivo con el modelo falso repitiendo lo grabado,
  anota cada llamada entre cajas y aplica una regla por frontera. Si el modelo es el mismo y la regla falla, la falla es del código, y la
  regla dice de qué caja. Hoy hay dos reglas, las dos de la caja 6.
- **Dos fallas de WhatsApp, ubicadas solas en la caja 6 BUSCAR** y escritas en `tests/test_cableado_cajas.py` como `xfail` estricto con
  motivo `PLAN:`: con `ORDER BY rubro` las 25 filas son notebooks y las 24 tablets no llegan al modelo; y "mouse g203" por `LIKE` vuelve
  vacío con "Mouse Logitech G203 Lightsync Negro" en la tabla.
- **Qué se ejecuta de verdad.** `banco_pruebas/funciones_ejecutadas.py` registra qué funciones corren al repetir las charlas sin modelo.
  Resultado, en `banco_pruebas/funciones_nunca_ejecutadas.json`: de 487, se ejecutan 285; 202 nunca; 49 de esas son dobles de prueba
  (Firestore, webhooks, leads) y no se juzgan; **quedan 153 candidatas, 2.389 líneas, el 25% de `app/`**. Las que más pesan: `motor`
  534 líneas, `filtros_catalogo` 396, `fuente` 258, `ejecutor` 254, `borrador` 135. Son candidatas, no sentencias: solo cubre las charlas
  grabadas. Sin referencia ni nombre en ningún lado de `app/`: `register_tienda`, `upsert_products_batch`, `set_config`,
  `set_current_estado`, `texto_de`, `sin_cupo`, `reiniciar_cupo`.

## Lo que muestra el diagrama

- Las cajas 6 BUSCAR y 7 PEDIDO Y CUENTA tienen 292 de las 487 funciones y unas 6.000 de 9.339 líneas.
- La búsqueda de productos que corre hoy es `tabla.py`, 94 líneas. El resto de BUSCAR son motores de antes del SQL del 5-nov: `motor`,
  `filtros_catalogo`, `fuente_producto`, `catalogo`. `motor.py` y `calculadora.py` siguen alcanzables desde las entradas por
  `core/agente.py` (envío y compatibilidad), aunque la documentación los da por caminos viejos.
- La caja 7 nombra 130 veces funciones de la caja 6; los controles de la caja 9 nombran 40.
- Funciones gigantes, imposibles de probar por partes: `calculate_total` 451 líneas, `motor._una` 248, la clase `Turno` de `ejecutor` 246,
  `motor.buscar` 189.

## Dónde nacen los errores (clasificación a mano, salvo las dos detectadas por la traza)

De las 25 fallas reales del 3-nov, `banco_pruebas/examen_real/fallas_3nov.md` y FICHA 87: unas 14 son de la caja 6 (el origen que el modelo
no pidió, PS5 y Samsung que no filtran), unas 4 de la 7 (pedido mal armado, pago anotado sin que el cliente lo dijera), unas 6 de la 9
(datos inventados, promesas sin cumplir). De las 7 de hoy en 72 turnos con el modelo real gratis: 3 de la 6, 3 de la 7, 1 de la 4. **Más
de la mitad nace en BUSCAR.** Varias de las reales ya las atacó la respuesta atada de la FICHA 90.

## Cómo se ordena lo que viene: las tres listas de Martín

- **Clases de pregunta, en romanos:** I nombrar un producto · II buscar por rubro o necesidad, jerga incluida · III condiciones y orden ·
  IV varias cosas en un mensaje · V la casa, envío, política, pagos · VI compatibilidad y saber general · VII comprar y pagar ·
  VIII memoria y referencias · IX charla y fuera de tema. Borrador: se verifica contra las 89 charlas de `vara_58.json`.
- **Lo que hace el modelo, en letras:** A partir el mensaje en pedidos · B decir cada pedido con sus palabras, sin SQL · C señalar a qué
  se refiere con la libreta, M, L, R · D elegir qué citar · E escribir saludo y pregunta, cortos.
- **Lo que hace el código, en números, las 9 acciones de `agenda.py`:** 1 buscar · 2 producto · 3 envío · 4 cuenta · 5 política ·
  6 compatibilidad · 7 comprar · 8 explicar · 9 otro.

## El plan, en orden

0. **Mirar el CI del último commit.** Terminó en verde con `25f0132` (corrida 1093). El de `fef875e` había fallado por mi culpa: usé
   `sys.monitoring`, de Python 3.12, y el CI corre 3.11. Cualquier cosa nueva de `banco_pruebas` se compila también con `python3.11`.
1. **La consulta tipada de `buscar`, caja 6.** Reemplaza al SQL libre; no es un camino al lado (`CLAUDE.md`, reglas 3 y 4). El modelo manda
   rubros, marca, condiciones y orden; los embeddings resuelven cada palabra contra los valores reales de la tienda; el código arma el
   SQL, reparte el corte entre rubros sin depender de ningún `ORDER BY`, y cuenta. Un vacío se cita con lo más parecido. Si los dos
   mejores resultados están parejos, o la condición no encuentra nada, el código repregunta; se extiende `lo_nombra`
   (`exists`, `ambiguous`, `not_found`) de la identidad a la búsqueda. Antes de conectarla, se mide sobre las ~130 consultas grabadas.
   Cuidado: la FICHA 87 descartó por medición la lectura que traduce el mensaje entero a una forma para el código, 47%. Esto es más
   angosto, solo la búsqueda, pero se mide antes de creerlo.
   **La vara:** los dos `xfail` de `tests/test_cableado_cajas.py` pasan; `tests/test_agente.py` no baja de 74 de 75; el candado de las 42
   reales no cambia; tres corridas con `agente_replay.py --gratis`. **El tamaño:** el techo de `app/` no sube; al terminar se borra lo
   que la consulta tipada hace sobrar, `sin_buscar`, `omitidos` y parte de `hoja_reglas`, y baja el techo.
2. **Reglas de frontera para el resto de las cajas**, 4, 7 y 9, con las 25 fallas reales y las 89 charlas, para que cada falla se ubique
   sola. Una caja por sesión.
3. **Archivar candidatas**, empezando por `motor`, una a la vez: moverla a `archivo/`, sin flags apagadas, con la vara, `test_diagrama.py`
   y un día de `produccion.py` antes de dar algo por muerto.
4. **Probar Haiku 5.5** cuando el flujo esté arreglado, no antes: no se sabría si la mejora es del modelo o del arreglo. Precios por
   millón de tokens: Haiku 5.5 $0,10 entrada y $0,50 salida; el modelo actual $0,25 y $1,50. Ojo: Haiku 5.5 da error 400 con
   `temperature` distinto del default, y el código manda `temperature=0`. Necesita clave de Anthropic, que es paga: solo si Martín lo pide.

## Descartado, con el motivo

- **Programmatic tool calling:** es de la API de Anthropic y producción corre en Gemini; además el problema no es el tamaño del contexto.
- **Rasa:** el repo abierto es el NLU clásico; CALM no está.
- **Parlant y tau2-bench:** solo como lectura. De Parlant: recuperar por turno lo relevante con embeddings, con señales y antiseñales por
  regla, y el texto de desambiguación de `responder.py`, línea 258. De tau2: calificar por estado final del pedido, herramientas llamadas
  e información comunicada. Se copian las ideas, no las dependencias.
- **Phoenix:** licencia Elastic 2.0, prohíbe ofrecerlo como servicio. **Langfuse:** MIT salvo `ee/`, cuya licencia no se leyó.
- **pydeps, code2flow, graphviz:** no se instalaron; con la librería estándar alcanzó.

## Para decidir con Martín

- La asignación de funciones a cajas es criterio de quien la escribió: está en `REGLAS` de `diagrama.py`; conviene revisarla juntos.
- Borrar `arquitectura/MAPA_CABLEADO.md`, que describe caminos ya borrados; lo reemplaza el diagrama generado.
- El CI tiene un paso, "El numero de las charlas grabadas", que busca `tests/test_charlas_grabadas.py::test_el_numero_no_baja`, que ya no
  existe, y queda en verde igual. Se limpia en un commit aparte, porque toca `.github/workflows/`.
- Si `funciones_ejecutadas.py` se suma al CI: con `sys.setprofile` las pruebas corren varias veces más lento.
