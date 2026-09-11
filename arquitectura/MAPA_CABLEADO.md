# MAPA DEL CABLEADO — nomenclatura, numeración y dónde se corta

**ÉSTE ES EL ÚNICO LUGAR DONDE SE NOMBRA EL CABLEADO.** Las estaciones `T`, las
juntas `J`, los puntos de modelo `L` y las desconexiones `D` se definen acá y en
ningún otro archivo. Si otro `.md` necesita hablar de una parte del sistema, la
nombra por su número y remite acá; no la vuelve a describir. Es la misma regla
de la puerta única del bloque 0 de `CLAUDE.md`, aplicada a los nombres: la
segunda descripción de lo mismo es el teléfono descompuesto.

Leído del código de `main` el 6-sep-2026. Todo lo que dice este archivo se
puede verificar abriendo el archivo y la línea que se nombra. Si algo acá
contradice al código, gana el código.

Para qué sirve: para poder decir "se rompió en T6-J3" en vez de "el bot
contestó mal". Cada pieza tiene un número estable. El número no cambia aunque
la pieza se reescriba; si una pieza se apaga, su número queda vacío y no se
reusa.

Medido antes de tocar nada:

    python3 -m pytest -q          482 verdes, 2 xfail
    python3 banco_pruebas/oro.py  48 de 65 (capa 2: 33/40, capa 4: 0/10, capa 5: 15/15)

Y después de los cuatro arreglos del 6-sep, mismo día:

    python3 -m pytest -q          493 verdes, 1 xfail
    python3 banco_pruebas/oro.py  48 de 65, sin moverse

**El estado de cada desconexión vive en la sección 4 de este archivo y en ningún
otro lado.** Lo HECHO lo cuenta `git log`; lo ABIERTO se lista en `PENDIENTE.md`
nombrando el número, sin repetir la explicación.

---

## 1. LAS DOS LEYES DE LECTURA DEL MAPA

**Ley A — sólo hay CUATRO lugares donde entra el modelo.** Todo lo demás es
código determinista. Los cuatro:

| id | dónde | archivo | cuándo corre |
|----|-------|---------|--------------|
| **L1** | decisor / intérprete | `turno.py:310 _pedir_herramientas` | siempre |
| **L2** | redactor | `turno.py:858 _redactar` | si la mesa tiene puntos |
| **L3** | extractor de datos del cliente | `cierre.py:239 extraer_datos_cliente` | sólo si la señal es `decision_compra` |
| **L4** | resumen de memoria larga | `memoria_larga.py:80` | sólo cuando el historial desborda |

L1 corre a temperatura 0 con el modelo decisor. L2 corre a 0.6 con
`response_format` de esquema estricto. L3 y L4 son auxiliares y no tocan la
respuesta que lee el cliente, salvo por lo que guardan.

**Ley B — el turno es una sola tubería, doce estaciones.** No hay ramas
paralelas ni puertas de salida alternativas desde el 3-sep. El camino vivo es
uno solo y es `app/core/turno.py:962 procesar_turno`.

---

## 2. LA TUBERÍA — doce estaciones numeradas

### T0 · ENTRADA
- **T0.1** webhook, `app/main.py` — WhatsApp y Telegram.
- **T0.2** conector, `app/connectors/whatsapp.py`, `telegram.py` — normaliza el mensaje.
- **T0.3** `orchestrator.process_message` — resuelve `tienda_id` por canal. Es el
  único lugar donde se puede asumir tienda por defecto.
- **T0.4** `turno.procesar_turno` — de acá en adelante todo es una función sola.

### T1 · CONTEXTO — determinista
- **T1.1** `get_conversation` — trae la charla de Firestore.
- **T1.2** `estado_venta.construir_estado` — arma el estado del turno.
- **T1.3** `turno._memoria_texto:131` — convierte el estado en el bloque de
  memoria que ve el modelo: resumen, productos vistos con id y posición,
  descartados, carrito con ficha, presupuesto vigente, destinos, provincia,
  producto anotado, criterio, condiciones, datos del cliente.
- **T1.4** `guardas_salida.business_name` — el nombre del negocio.

### T2 · INTERPRETAR — **L1, el modelo declara**
- **T2.1** `molde.esquemas(tienda_id)` — el molde que ve el modelo.
- **T2.2** el molde es `RegistrarPedido`, en `app/core/molde.py`. **Diez campos**,
  y ese es el formulario que ya existe: `items`, `restricciones`, `destinos`,
  `pide_precio`, `contradicciones`, `reparto_pago`, `atributos`, `stock`,
  `compatibilidad`, `temas`.
- **T2.3** `turno._INSTRUCCION_UNO:69` — la orden: declarar, no buscar.
- **T2.4** el catálogo de familias vive en `app/core/familias.py`: diez de
  declaración más `memoria` y `cierre`.

### T3 · EJECUTAR — determinista
- **T3.1** `turno._ejecutar_en_paralelo:370` — cada herramienta a un hilo, tope 10.
- **T3.2** `herramientas.ejecutar` — corre la función real contra la fuente.
- **T3.3** `estado_venta.certificar_ids_de_resultado` — los ids que volvieron
  quedan certificados en el hilo del turno.

### T4 · COMPLETAR LO DECLARADO — determinista
- **T4.1** `turno._restricciones_de_los_filtros:689` — lo que el modelo aplicó
  como filtro y no declaró como restricción, se copia a lo declarado.

### T5 · RESOLVER — determinista, el nexo
`app/core/resolver.py:716 resolver`. Devuelve `llamadas`, `contrato`, `bloque`.
- **T5.1** `_derivar_las_busquedas:92` — de lo declarado salen las búsquedas.
  Tope 14.
- **T5.2** `_id_para:45` y `pedido_helpers.certificar_producto` — la identidad.
  Tres veredictos: `encontrado`, `ambiguo`, `no_encontrado`.
- **T5.3** `_completar_el_declarado:623`.
- **T5.4** `_hace_falta_cuenta:400` y `_aplicar_la_cuenta:430`.
- **T5.5** `_cuenta_con_lo_declarado:863` — la plata, con `calculadora`.
- **T5.6** `_reparto_de_pago_declarado:1137` y `_supuesto_de_pago:1243`.
- **T5.7** `_bloques_a_uno:1327` — el bloque sellado que el modelo no escribe.

### T6 · LA MESA — determinista, `app/core/tabla.py`
- **T6.1** `puntos:149` — lo declarado se desarma en filas con id `campo:n`.
- **T6.2** `_clasificar:268` — las llamadas agrupadas: listas, fichas, compat,
  temas, envíos, agregados.
- **T6.3** `_material_del_punto:339` — a cada fila se le busca su material.
- **T6.4** `_producto_de_compra:93` y `_valor_del_campo:110` — la proyección:
  sólo los campos que esa pregunta necesita.
- **T6.5** `tabla:474` — cada fila queda en uno de cuatro estados:
  `con_material`, `sin_material`, `sellado`, `pregunta`.

### T7 · REDACTAR — **L2, el modelo escribe**
- **T7.1** `turno._INSTRUCCION_DOS:91` — devolvé la mesa llena.
- **T7.2** `tabla.ESQUEMA_RESPUESTA:548` — `apertura`, `puntos` con id y texto,
  `pregunta_final`. Esquema estricto: no hay casilla para un número de plata.
- **T7.3** `turno._parsear:903` — si no es la mesa, no se manda nada.

### T8 · ARMAR — determinista
- **T8.1** `tabla.armar:713` — el orden lo manda la mesa, no la respuesta.
- **T8.2** `tabla._limpiar:635` — la poda: plata sin respaldo, id interno, JSON
  filtrado, cifra en una fila sin material.
- **T8.3** `tabla._pregunta_por:695` y `_pregunta_del_codigo:819` — la compuerta
  de completitud: una fila abierta se pregunta aunque el modelo escriba encima.
- **T8.4** el bloque sellado se pega al final, entero.

### T9 · OBLIGACIONES — determinista
- **T9.1** `guardas_salida.asegurar_honestidad_bot`.
- **T9.2** `guardas_salida.con_saludo_inicial` / `sin_saludo_del_modelo`.
- **T9.3** `camino_cobro.linea_de_cobro`.

### T10 · CIERRE — determinista más **L3**
- **T10.1** `turno._senal_de_cierre:748` — `_RE_PIDE_COBRO` sobre el mensaje.
- **T10.2** `cierre.extraer_determinista`.
- **T10.3** `cierre.extraer_datos_cliente` — **L3**.
- **T10.4** `leads.procesar_mensaje_para_lead` y `pago.datos_transferencia`.

### T11 · MEMORIA — determinista más **L4**
- **T11.1** `_productos_del_turno:451` — con turno, posición y categoría.
- **T11.2** `_carrito_del_turno:490` y `_carrito_podado:522`.
- **T11.3** `_descartados_nuevos:596` — la memoria negativa.
- **T11.4** `_preferencias_al_dia:654`.
- **T11.5** `_reparto_que_se_guarda:421`.
- **T11.6** `memoria_larga.actualizar_resumen` — **L4**.
- **T11.7** `save_conversation`.

### T12 · LO QUE QUEDA ESCRITO
- **T12.1** `turno_incompleto` — puntos abiertos y salteados.
- **T12.2** `turno_ok` — largo, latencia, etapas, puntos. **No guarda el texto.**

---

## 3. LAS JUNTAS — dónde una etapa le pasa el dato a la otra

Una junta es el único lugar donde se puede perder algo. Son siete y todas
tienen nombre propio.

| id | de → a | qué viaja | cómo se aparea |
|----|--------|-----------|----------------|
| **J1** | T1 → T2 | memoria en prosa | texto libre en el prompt |
| **J2** | T2 → T3 | `pedidos` con args | nombre de herramienta |
| **J3** | T2 → T5 | `declarado` | campo por campo del molde |
| **J4** | T3+T5 → T6 | `llamadas` | **por palabras compartidas**, `tabla._pega:84` |
| **J5** | T6 → T7 | la mesa en JSON | id de fila |
| **J6** | T7 → T8 | la mesa llena | id de fila |
| **J7** | T8 → T9…T11 | el texto | string |

**J4 es la junta blanda del sistema.** Es la única que no aparea por
identificador sino por coincidencia de palabras de tres letras o más. Todas las
demás juntas son duras.

---

## 4. LAS DESCONEXIONES — numeradas, con evidencia

Cada una dice en qué estación vive, qué se pierde y cómo se ve desde afuera, y
**si está cerrada o abierta**. Las que están medidas por el repo llevan el caso;
las que salen de leer el código llevan el archivo y la línea.

Cerradas el 6-sep-2026: **D1**, **D6**, la mitad dura de **D3**, la parte del
verbo de **D4**, y **D10** en lo que hacía falta para diagnosticar la junta.
Cerradas el 7-sep-2026: **D13** y **D15**. Cerrada el 11-sep-2026: **D16**.
Abiertas: **D2**, **D4** en su parte de fondo, **D5**, **D7**, **D8**, **D9**,
**D11**, **D12**, **D14**.
Cerrada el 11-sep-2026: **D16**, sus dos familias.
D16 se agrego el 11-sep-2026.

D13, D14 y D15 se agregaron el 6-sep-2026 leyendo las charlas REALES del 3 y 4
de septiembre por el puente de producción, issue 31, y las tres se
reprodujeron offline antes de escribirse. Vara:
`tests/test_plan_de_la_obligacion.py`. Relato en
`FICHA_49_la_obligacion_muda.md`. **D14 sigue abierta a propósito:** su arreglo
necesita decidir el mecanismo, y meterle una lista de frases prohibidas al
mensaje es el camino que este repo ya recorrió y del que ya volvió.

### D1 · CERRADA 6-sep · La movida de venta se buscaba y se caía antes del redactor
**Estación:** T6.3.
**Cómo se cerró:** la mesa devuelve un tercer carril, `guion`, con `objetivo`,
`movida` y `escape` de los temas que volvieron, y `turno._conduccion` lo entrega
al redactor **como mensaje de sistema**, no como material del turno. No es una
fila, así que no abre casilla ni la mira la compuerta de completitud. Vara:
`tests/test_guion_y_junta.py`, cinco casos.
**Lo que era, para que se entienda el número:** `tabla.py:461`.
`consultar_temas` devuelve por tema: `politica`, `valores`, `criterio`,
`objetivo`, `movida`, `escape` — está en `herramientas.consultar_temas`. La mesa copia
sólo cuatro: `tema`, `politica`, `valores`, `criterio`. **`objetivo`, `movida` y
`escape` no llegan nunca al modelo que escribe.**
Cómo se ve: el bot contesta correcto y sin vender. La prosa de venta que la casa
tiene escrita no está en la mesa, así que el redactor la improvisa o no la usa.
`turno._log_fuente:257` fue escrito justo para cazar esto y lo que muestra es
que la movida vuelve de la fuente; lo que nadie estaba mirando es que se cae una
estación después.
**Es una línea de código.**

### D2 · ABIERTA · La capa 4 no tiene mecanismo: 0 de 10
**Estación:** T8.2.
Los diez casos de oro de la compuerta miden `salida.procedencia` y
`salida.plata`, que se apagaron el 3-sep. Hoy la anti-alucinación de salida vive
en `tabla._limpiar` y **no la mide nadie**. Cuatro de los diez ya están cubiertos
por estructura, uno a medias, y **cuatro no están cubiertos**: descuento que la
fuente no da, datos de cobro fabricados, negar lo que el turno tiene en la mano,
plazo de garantía distinto del de la ficha.
Cómo se ve: el bot dice algo mal y la batería sigue verde.

### D3 · MITAD CERRADA 6-sep · La junta blanda: pregunta y evidencia se aparean por palabras
**Estación:** J4, `tabla._pega`.
Alcanza con **una** palabra de tres letras compartida entre lo que el cliente
pidió y el pedido de la herramienta para que esa llamada conteste esa fila. Y en
`_material_del_punto` gana **la primera** que pegue, no la mejor.
Cómo se ve: dos preguntas en un mismo mensaje y la respuesta de una contesta con
el material de la otra. O una fila queda `sin_material` con el dato en la mano.
**Lo cerrado:** para los **atributos** la junta pasó a ser dura. El resolver ya
sabía exacto para qué término del cliente pedía cada ficha y tiraba ese dato;
ahora viaja en el pedido como `para` y la mesa aparea por término, con el de
palabras sólo de respaldo. Vara: `tests/test_guion_y_junta.py`, tres casos.
**Lo abierto:** las filas de `items`, `stock` y `restricciones` siguen
apareándose por palabras contra las listas.

### D4 · PARTE CERRADA 6-sep · El campo del atributo se adivina por palabras
**Estación:** T6.4, `tabla._valor_del_campo`.
`atributos[].campo` es texto libre. Cuando no coincide con una clave de la
ficha, el código elige **la clave que más palabras comparte**, y a igualdad la
más corta. Puede devolver el valor de la columna equivocada.
Cómo se ve: un número real, de otro campo, dicho con total seguridad. La poda de
T8.2 no lo caza porque la cifra sí está en la mesa. Es la alucinación con cara de
dato verificado.
**Lo cerrado:** el verbo del cliente ya llega al campo. "el que menos pesa"
devolvía None y el turno salía sin orden, mientras "el de menor peso" andaba.
El puente nuevo es una flexión, mismo largo y todo igual menos la última letra,
así que no revive el caso que el puente de cinco letras prohibió: "la más cara"
sigue ordenando por precio. Vara: `tests/test_extremo_negado.py`, dos casos
nuevos y los ocho negados de antes.
**Lo abierto, y es el fondo:** el campo sigue sin certificarse con los tres
veredictos de la regla cero. La opción está escrita en `FORMULARIO_V2.md`.

### D5 · ABIERTA · `contradicciones` no lo lee nadie
**Estación:** T5.
El modelo lo declara, la mesa abre la fila como `pregunta` — pero **ninguna
búsqueda de `resolver.py` la usa**. Está en `PENDIENTE` como abierto.

### D6 · CERRADA 6-sep · La declaración del atributo no gobernaba su búsqueda
**Estación:** T5.1.
El resolver pedía una ficha suelta por atributo, sin dejar rastro de para qué se
la pedía. Ahora los atributos se agrupan por producto: dos preguntas del mismo
producto son dos filas y **una sola consulta a la fuente**, y esa consulta lleva
los términos del cliente. Ése es el mismo cambio que cierra la mitad de D3.
Vara: `tests/test_guion_y_junta.py`.

### D7 · ABIERTA · Dos políticas opuestas ante el mismo veredicto `ambiguous`
**Estación:** T5.2 contra `certificar_temas`.
Producto ambiguo: se frena y se pregunta, regla cero. Tema ambiguo: se sirven
hasta tres políticas. Causa medida de que "dame precio de una intermedia" abra
cuotas y envío al exterior.

### D8 · ABIERTA · La restricción de origen no se puede cumplir con la fuente de hoy
**Estación:** F, la fuente. No es cableado.
El campo `origen` del catálogo es prosa: "Marca Genius de Taiwan. Fabricado en
China." No se puede filtrar ni ordenar. Medido en el turno `2dde2ad0` del
31-ago: las cuatro búsquedas con filtro de origen volvieron
`ninguno_cumple_del_todo`. **Ésta es la pregunta de prueba que el bot nunca
contestó bien, y ningún arreglo de código la arregla.** Es una decisión de
fuente: qué campo normalizado se agrega, y si la restricción ordena en vez de
filtrar.

### D9 · ABIERTA · Siete rojos de capa 2, todos de cableado
Con la interpretación perfecta escrita a mano, o sea sin el modelo en el medio:
- C2-S05 el comparativo devuelve el propio producto de referencia
- C2-S07 el uso "para jugar" no es un campo del catálogo
- C2-S08 el pedido abierto no deriva rubros ni cuenta
- C2-S13 "me haces ese precio" no lo certifica ningún tema
- C2-S17 "ese" no ancla al producto del turno anterior
- C2-E01 la G15 que no existe devuelve rubros que no son
- C2-E04 el tema `defectuoso` existe con otro nombre y vuelve vacío

### D10 · PARTE CERRADA 6-sep · El turno no dejaba rastro de sus decisiones
**Estación:** T12.
`turno_ok` anota largo, latencia y puntos, nunca el mensaje. Cuando el bot
contesta mal, el log dice que el turno estuvo bien y no hay con qué reconstruir
qué se dijo. Es el cuello de botella que ya está anotado: el error se ve en
WhatsApp y adentro del código no se ve.
**Lo cerrado:** la junta J4 ya deja rastro. Sale `mesa_apareada` con los pares
`fila<-de dónde salió su material`, y ahí se lee si la ficha se apareó exacta
o por palabras. Sin ese renglón, una respuesta contestada con la evidencia de la
pregunta de al lado era indistinguible de una correcta. También sale
`tabla_armada` con qué situación de venta condujo el turno.
**Lo abierto:** el texto de la respuesta sigue sin guardarse.

### D11 · ABIERTA · La poda puede vaciar una casilla entera
**Estación:** T8.2, `tabla._limpiar:635`.
El respaldo de cifras se calcula sobre la mesa **entera**, así que un número de
otra fila respalda cualquier oración. Y del otro lado, una casilla que se poda
entera deja el punto mudo aunque tuviera material. Ya pasó en producción el
3-sep con "SP-HF180" y se arregló el molde del id, pero el mecanismo sigue
siendo cortar por oración.

### D12 · ABIERTA · Dos extremos sueltos con items
**Estación:** T5.1.
Si el turno declara dos extremos opuestos y además hay items, el extremo del
turno no gobierna ninguna búsqueda y cada item usa el suyo. El caso sin items ya
está verde.

### D13 · CERRADA 7-sep · La línea obligatoria de que es un bot no salía nunca
**Estación:** T9.1 y T9.2, `turno._obligaciones`.
**Cómo se cerró, y son dos cosas.** El argumento de más se sacó: la función
toma la respuesta y el nombre del negocio, que ya viene resuelto. Y las tres
obligaciones dejaron de compartir un `try`: cada una corre en el suyo y deja su
nombre en `turno_guarda_error`, así que la que se cae no apaga a las de abajo y
el log dice cuál fue. Eso segundo es lo que evita la tercera vuelta: sin nombre
y sin independencia, el warning no alcanzaba para saber qué se había roto.
Vara: `tests/test_plan_de_la_obligacion.py`, dos casos.
**Lo que era, para que se entienda el número:**
`turno.py:984` llamaba `con_saludo_inicial` con TRES argumentos y
`guardas_salida.py:136` la define con DOS. En el primer turno de cada charla
eso levanta `TypeError`, el `except` lo convierte en un `warning` y el bloque
entero de obligaciones queda sin correr. El cliente nunca lee que está
hablando con un asistente automático.
Medido el 3-sep 17:37:17 UTC, turno `tg_524215785`: `turno_guarda_error` con
`con_saludo_inicial() takes 2 positional arguments but 3 were given`, y en la
charla del puente ese turno arranca con el saludo del modelo.
Cómo se ve: una obligación de la casa que no se cumple, y nadie se entera.
**Ya había pasado una vez**, el 3-sep, con `asegurar_honestidad_bot`: se
arregló esa y se rompió la de al lado, porque un solo `try` alrededor de tres
obligaciones no deja ver cuál se cayó.

### D14 · ABIERTA · Un universal sobre el catálogo sale sin herramienta que lo mire
**Estación:** T8.2, `tabla._limpiar:635`.
Una fila `sin_material` puede afirmar sobre los 880 productos y la poda no lo
ve: corta plata sin respaldo, id interno, JSON filtrado y cifra en fila sin
material, ninguna de las cuatro mira un universal en prosa.
Medido el 3-sep 17:38:51 UTC, turno `tg_524215788`: `busquedas_derivadas` con
`hechas=[]` y el cliente leyó `no contamos con ningun producto que disponga de
mas de 5 variantes`, y dos renglones más abajo, en el MISMO mensaje, que no
tiene el dato.
La guarda que cazaba esto —`hub_venta_afirmo_sobre_el_catalogo`, hoy en
`archivo/plomeria_apagada/salida.py:844`— se apagó con el hub el 3-sep y no la
reemplazó nadie.
Cómo se ve: el bot afirma y se desdice en el mismo mensaje.
**La condición es de ESTADO, no de vocabulario.** Perseguir prosa con una
lista de frases ya fracasó: fueron 4 nodos, después 18, después 46. Vara:
`tests/test_plan_de_la_obligacion.py`, dos casos.

### D15 · CERRADA 7-sep · La pregunta del código llamaba política a una pregunta del cliente
**Estación:** T8.3, `tabla._pregunta_del_codigo`.
**Cómo se cerró.** Los `temas` tienen molde propio, y la decisión se toma por
FORMA, no por vocabulario: un tema de verdad es una clave de la FAQ, y las 50
claves tienen tres palabras como máximo —`teclado_mecanico_membrana`— y
ninguna arranca con un interrogativo. Cuando lo que quedó después de sacarle
`la politica de ` no cumple eso, no es el nombre de una política y no se lo
nombra: sale una frase neutra que no pega el renglón crudo. Vara:
`tests/test_plan_de_la_obligacion.py`, dos casos y un verde de contracara para
que el caso legítimo —`la politica de garantia`— no quede mudo.
**Lo que era, para que se entienda el número:** la fila `temas` trae su
`pregunto` como `la politica de ` más la frase cruda, y el molde genérico la
pegaba entera. Cuando el modelo declaró como tema algo que no es política de
la casa, salía
`Sobre la politica de que producto tienen en mas de 5 tipos no tengo el dato
confirmado`.
Medido el 3-sep 17:38:51 UTC, turno `tg_524215788`, leído tal cual en la
charla del puente.
Cómo se veía: el bot le atribuía a la casa una política que el cliente nunca
nombró, en el renglón donde estaba admitiendo que no sabe.
Los moldes de `restricciones`, `stock`, `pide_precio` y `reparto_pago` ya se
habían corregido por esta misma razón; el genérico había quedado.

### D16 · CERRADA 11-sep · La restriccion en prosa se traduce al orden equivocado
**Estacion:** T5.1, `filtros_catalogo.resolver_orden:710`.
**Vara:** `tests/test_barrido_orden.py`, y el barrido entero en
`banco_pruebas/barrido_orden.py`. Offline y gratis: doble local de Firestore
con el catalogo real, cero llamadas al modelo, un segundo.

    python3 banco_pruebas/barrido_orden.py     45 -> 54 -> 59 de 59, el 11-sep-2026

**Como se encontro.** Con la sonda, el 11-sep, sobre "necesito un aparato
rectangular con varias teclas, que sea bueno, pero dada la crisis armame un
presupuesto acorde". **L1 interpreto BIEN**: declaro `categoria: teclado` y las
dos restricciones. El que fallo fue este paso: salio `precio_ars direccion max`
y el cliente leyo un presupuesto por un teclado de $512.500 cuando el mas
barato de la tienda sale $12.000. **Es el caso que muestra que la
interpretacion no era el cuello.**

**FAMILIA A — nueve casos, salian AL REVES. CERRADA el 11-sep.** La marca de superlativo gana sobre
el adjetivo que la sigue: "el de precio mas bajo", "el de mas bajo precio", "el
mejor precio", "el de peso mas bajo" y "la garantia mas corta" ordenan de mayor
a menor. El bot entrega lo contrario de lo que le pidieron, y lo dice con
seguridad. Ahi cae tambien `presupuesto acorde a la crisis (economico)`: el
parentesis no se saca antes de partir en palabras, la palabra queda como
`(economico)` y no pega con el mapa de adjetivos. `economico` suelto daba `min`;
`(economico)`, `max`.
**Como se cerro, y son dos cosas.** La puntuacion se saca antes de partir la
frase en palabras, asi que un parentesis ya no esconde un adjetivo. Y la
direccion dejo de salir solo de `_MENOR`: hay una tabla aparte,
`_MENOR_ADJETIVO`, con las raices que apuntan al extremo bajo del eje —`baj`,
`cort`, `chic`, `reducid`— que NO son marca de superlativo y solo deciden hacia
donde cuando la frase ya trajo la suya. Va aparte de `_MENOR` a proposito:
`_MENOR` alimenta ademas `_NIEGA_EL_ADJETIVO`, y meter estas raices ahi
cambiaria en silencio que negacion da vuelta el extremo. Aparte, "el mejor
precio" es el mas barato y se decide DESPUES de saber el campo, porque es el
unico eje donde "mejor" apunta para abajo: la mejor garantia es la mas larga.

**FAMILIA B — cinco casos, ordenaban por OTRO campo. CERRADA el 11-sep.** Nombrar el rubro le roba
el campo al precio. De las 22 categorias del catalogo vivo, cinco lo hacen:
`teclado` se va a `switch_teclado`, `memoria ram` y `placa de video` a
`memoria_video`, `procesador` a `procesador`, `almacenamiento externo` a
`almacenamiento`. "El teclado mas barato" no ordenaba por precio, y pegaba en
el camino normal: `resolver.py:236` le pasa el texto del item entero porque el
modelo declara "teclado mas barato" sin partirlo.
**Como se cerro.** Las palabras que nombran el RUBRO dejan de poder elegir el
campo del orden. La categoria no se adivina: sale de `get_categories` por la
fuente viva, con limite de palabra y sus plurales, asi que no es una lista
escrita a mano y no crece con el catalogo. Se le saca al eje y nada mas: esas
palabras siguen contando para el mapa de adjetivos y para la direccion. Si
despues de sacarlas ninguna nombra un campo, cae al mapa y "barato" resuelve a
`precio_ars`, que es lo que el cliente pidio. Lo que se pierde, y se acepta: si
el eje se llama igual que el rubro —"el almacenamiento externo con mas
almacenamiento"— la frase queda sin orden en vez de ordenar por el campo
homonimo. Sin orden es honesto; ordenar por la columna equivocada no.

**Es la misma enfermedad que D3 y D4**, un escalon mas arriba: aparear por
palabras compartidas en vez de por un veredicto.

**Lo que el barrido NO llama rojo, y es a proposito.** Veintiocho frases mas
—"gama baja", "buena relacion precio calidad", "el mas rapido", "el mas
vendido"— quedan en un bloque blando que no puntua. La fuente tiene **tres**
campos numericos, `precio_ars`, `peso_gramos` y `garantia_meses`, y sobre lo
demas ordenar no significa nada: devolver None ahi es lo honesto. Cuales de
esas frases merecen un campo normalizado nuevo es **decision de FUENTE**, la
misma discusion de D8, y no se decide desde el codigo.

---

## 5. RESUMEN DE UNA LÍNEA

De las dieciséis desconexiones, **una es de la fuente** (D8, la más cara), **dos
son de instrumentación** (D2 y D10: el sistema falla y nadie lo ve), y **trece
son plomería**, de las cuales cuatro viven todas en la misma enfermedad —aparear
por palabras compartidas en vez de por un veredicto— en la junta blanda J4, en
la proyección del campo y en la traducción de la restricción al orden (D3, D4,
D6, D16).

**Las tres del 6-sep son de otra familia y hay que decirlo aparte: D13, D14 y
D15 son las tres que el cliente LEE.** Una obligación que no se cumple, una
afirmación sobre el catálogo sin nada que la respalde, y un "no sé" que le
atribuye a la casa una política inventada. Las tres estuvieron a la vista en
una charla de diez mensajes que nadie había leído hasta que el puente la
trajo. **Eso es lo que mide la distancia entre la batería verde y el teléfono
del cliente.** D13 y D15 cerraron el 7-sep; D14 sigue abierta porque es la
única de las tres que necesita decidir un mecanismo.

La pregunta "por qué en teoría funciona y en la práctica no" tiene, medida, esta
respuesta: **porque las dos únicas juntas que no aparean por identificador son
justo las que deciden qué evidencia contesta qué pregunta**, y porque desde el
3-sep la capa que atajaba lo que el modelo escribe de más no tiene vara que la
mida.
