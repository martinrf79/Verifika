# PENDIENTE — lo que quedó abierto

Este archivo es **CORTO a propósito** y el hook de arranque lo imprime entero, así
que toda sesión nueva lo lee sin buscarlo. **Máximo veinte líneas de contenido, un
ítem por línea.** El 21-ago tenía veinte PÁRRAFOS, uno de mil novecientos
caracteres: un archivo que se imprime en cada arranque no puede ser un diario.

**Lo que se HIZO no va acá:** lo cuenta `git log`, que el hook también imprime y
que nadie puede desactualizar.

**El PLAN tampoco va acá**, y ese es el cambio del 21-ago. El recorte vive como
tests que se cuentan solos; escribirlo además en prosa eran dos fuentes sobre lo
mismo, que es exactamente lo que venimos sacando de todos lados.

Estados: **ABIERTO** · **ESPERA A MARTIN** (falta una decisión o un dato suyo).

Ya no hay candado: `tests/test_pendiente_al_dia.py` se apagó el 2-sep con el
resto de los candados de proceso. Mantenerlo al día es a mano, y por eso es
corto.

---

## Dónde está el proyecto — dos comandos

```
python3 -m pytest -q          la batería offline
```

`banco_pruebas/oro.py` NO corre desde el apagón: importa `app.core.herramientas`,
que se apagó el 11-sep. Reescribirlo sobre el camino nuevo es otra ficha; hasta
entonces el único número es el de la batería.

Los dos números los dicen los comandos, así que acá no se escriben: un conteo
copiado a un `.md` envejece el mismo día. El mapa del cableado anota el piso del
día en que se midió, para poder comparar.

Los dos techos, `A MEDIAS` y `PLAN`, ya no los cuida nadie: vivían en
`tests/test_a_medias.py`, que se apagó. Lo que queda abierto es esta lista y los
rojos del banco de oro. La unidad de trabajo, en `arquitectura/`.

**3-sep:** el hub y sus cuatro puertas se apagaron. El turno entero es
`app/core/turno.py` sobre `app/core/tabla.py`. `app/` pasó de 22.547 líneas a
16.794 y la batería de 36.984 a 6.946.

**3-sep, tarde:** cerró la **compuerta de completitud**, que era lo único grande
que quedaba abierto del recorte y no era recortar sino editar. El estado de la
fila manda sobre lo que escribió el modelo: una fila `sin_material` o `pregunta`
queda abierta aunque el modelo escriba encima, el turno termina preguntando por
ella, la `pregunta_final` del modelo se conserva sólo si habla de ese punto, y
una casilla sin material no puede traer una cifra. Un turno incompleto ya no se
loguea como correcto: sale `turno_incompleto` con los ids. Y el instrumento
dejó de mentir por el denominador: `produccion.py --desde` audita sólo las
charlas de la ventana en vez de las mismas viejas por orden de id.

**31-ago:** El puente de lectura de produccion quedo enchufado
(`.github/workflows/puente_cowork.yml`, issue 31): se pide `/logs` en un
comentario y vuelve el volcado de Cloud Run mas la auditoria de charlas
reales, con WIF y sin ninguna clave. Con eso se leyo el turno `2dde2ad0`
de la charla de Martin y se cerro lo que mostro: el codigo ya no borra
contradicciones, y el aviso del reparto de pago distingue "sin medio" de
"al reves".

---

## Abierto

**11-sep, LO ABIERTO: EL MAPA. EL MOTOR YA ESTA.** El diseño entero esta en
`arquitectura/FICHA_50_los_tres_mapas.md`. **El motor se escribio y anda:**
`app/core/motor.py`, una sola puerta, consulta estructurada, y el modelo la
llama el. Medido con la gratis, 6 de 6 mensajes: el modelo busca sin mapa
ninguno, traduce "un rectangulo con teclas" a teclados y "acorde a la crisis" a
un orden por precio, y ante "silencioso" contesta que no lo tiene cargado.
**Falta el mapa**, y ahora se puede medir si hace falta y cuanto: la maqueta del
mapa 1 pesa 1.349 tokens con la regla de enumerar por VARIEDAD y no por tipo.
Lo que el mapa tiene que sumar y la ficha no dice: que se puede HACER con cada
campo -filtrar, ordenar, ninguna- y en cuantos productos esta cargado.

**11-sep, EL APAGON.** Se apago la arquitectura de moldes, mesa y dos llamadas
al modelo. El turno es ahora `app/core/respuesta.py`, cinco etapas: una sola llamada, con los
veinte tipos de pregunta y su respuesta generica adentro del prompt
-`app/core/tipos.py`-. El codigo busca en la fuente ANTES de hablarle al modelo
-`app/core/fuente.py`- y pone los dos unicos numeros que existen, precio y
envio, DESPUES -`app/core/numeros.py`-. `app/` paso de 17.437 lineas a 11.129.
Lo apagado esta entero en `archivo/apagado_11sep/`. **Los items de abajo que
nombran la mesa, el molde, el resolver o el indice quedaron sin objeto: no se
borran todavia porque lo que describen -un agujero de la FUENTE- puede volver
a aparecer en el camino nuevo.**


**11-sep, tarde: EL ENVIO QUEDO ENCHUFADO, y era el mapa 2.** El motor de
envio estaba entero y no lo alcanzaba nadie: la unica herramienta del modelo
mira el catalogo. Ahora el codigo cotiza ANTES de hablarle -`fuente.texto_envio`-
y el bloque viaja como el inventario: con destino, la tarifa exacta ya cotizada
y el plazo; sin destino, las zonas, el umbral y que dato falta. Cierra cuatro
agujeros: el destino ahora sale del mensaje O de la charla y se lo pregunta al
motor de envio en vez de a `geo`, asi que "CP 5121" y "a rosario" tambien
cotizan; el molde del tipo `envio_costo` pedia `{{costo_envio}}`, que nadie
llena, y el cliente leia "ese dato no lo tengo a mano" donde iba la tarifa; la
politica del RANGO ya no viaja al lado de la tarifa exacta; y el subtotal del
envio gratis dejo de sumar TODAS las fichas que devolvio la busqueda -mostrar
cinco notebooks regalaba el envio-. Cuesta 70 tokens y apaga una politica de
251 caracteres. Vara: 8 casos nuevos en `tests/test_turno_nuevo.py`.

**11-sep, noche: EL MOTOR YA TIENE NUMERO.** `motor_turno`, un renglon por
turno y sale siempre: vueltas, si re-busco, si repitio la misma consulta,
veredictos, filas, rescates, y los campos que no se pudieron aplicar. Lo agrega
`produccion.py` sobre la misma ventana que los invariantes, asi que el numero
sale por el issue 31 con `/logs`, y la tanda viva imprime el mismo con la misma
funcion. **Era lo que faltaba para mover las cuatro perillas del motor -dos
vueltas, ocho filas, seis consultas, cinco por defecto- mirando en vez de a
ojo**, y el renglon de condiciones no aplicadas es el que dice que campo agregar,
que es la discusion abierta de D8 y D16. Vara del instrumento, offline y sin
credencial: `tests/test_numero_motor.py`, 12 casos.

**LOS NOMBRES Y EL DETALLE DE CADA FALLA NO SE ESCRIBEN ACA.** Viven en
`arquitectura/MAPA_CABLEADO.md`, que es el unico lugar donde se nombra el
cableado: estaciones `T`, juntas `J`, puntos de modelo `L` y desconexiones `D`.
Aca va una linea por item, con su numero. Si un item y el mapa se contradicen,
gana el codigo y los dos estan mal.

- **ABIERTO** · **EL UMBRAL DE ENVIO GRATIS NO SE APLICA EN EL TURNO.** Depende del PEDIDO y el pedido no existe como estado en el camino vivo. Viaja como dato para que el modelo lo diga y lo aplica la calculadora cuando el cierre arma la orden. Aplicarlo antes exige el carrito, que es el item de abajo.
- **ABIERTO** · **TRES CAMPOS DE LA MEMORIA SE LEEN Y NO LOS ESCRIBE NADIE:** `ultimo_presupuesto`, `carrito_vigente` y `descartados`. El unico que guarda charla es `respuesta.py` y no los pasa. Lo que cuesta: con `ultimo_presupuesto` vacio, `leads` corta siempre por "no cerrar sin precio mostrado", asi que una intencion fuerte de compra crea un lead tibio EN SILENCIO y el link de pago no sale. **Es el cierre, y es lo proximo.**
- **ABIERTO** · **`set_current_estado` NO LO LLAMA NADIE en el camino vivo.** Las muletas de `cotizar_envio` que leen el estado -la direccion del cliente y la provincia pegajosa- estan muertas. Hoy no hacen falta porque el destino entra por el bloque de envio y por la charla; si vuelven a hacer falta, se decide entonces y no se revive por las dudas.
- **ESPERA A MARTIN** · **D16 · EL BLOQUE BLANDO DEL BARRIDO DEL ORDEN.** El bloque duro quedo en 59 de 59 y las dos familias cerraron el 11-sep. Quedan 28 frases que el cliente puede pedir y la fuente no puede cumplir: "gama baja", "buena relacion precio calidad", "el mas rapido", "el mas vendido". La fuente tiene TRES campos numericos —`precio_ars`, `peso_gramos`, `garantia_meses`— y sobre lo demas ordenar no significa nada. **No es codigo: es decidir que campo normalizado se agrega**, la misma discusion de D8. La lista entera la imprime `python3 banco_pruebas/barrido_orden.py`.
- **ABIERTO** · **LA CASILLA GENERICA DE CADA TIPO DE PREGUNTA ES CATALOGO, NO CAMINO VIVO.** Los 20 tipos y el molde de la respuesta de cada uno estan en `banco_pruebas/preguntas.py`, con candado en `tests/test_preguntas_genericas.py`; la lista entera la imprime `python3 -m banco_pruebas.preguntas`. El bot vivo todavia no lee ese diccionario: **enchufarlo es la segunda parte y la decide Martin.**
- **ABIERTO** · **D14 · UN UNIVERSAL SOBRE EL CATALOGO SALE SIN QUE NINGUNA HERRAMIENTA LO MIRE.** Una fila `sin_material` afirma sobre los 880 productos y dos renglones despues, en el mismo mensaje, dice que no tiene el dato. Es la unica de la FICHA 49 que queda: D13 y D15 cerraron el 7-sep. Sigue abierta porque hay que DECIDIR EL MECANISMO, y la condicion tiene que ser de ESTADO y no de vocabulario: perseguir prosa con una lista de frases ya fracaso aca, fueron 4 nodos, despues 18, despues 46. Vara puesta y en rojo, dos casos, en `tests/test_plan_de_la_obligacion.py`.
- **ABIERTO** · **D2 · LA CAPA 4 DE LOS CASOS DE ORO QUEDO SIN MECANISMO.** Sus 10 casos miden `salida.procedencia` y `salida.plata`, que se apagaron el 3-sep, y su campo `texto` viene con las etiquetas `<d ID>` de la atadura, que el modelo ya no escribe. Esta como `xfail` estricto en `tests/test_oro.py`, con el detalle caso por caso: C4-01, C4-02, C4-09 y C4-10 ya los cubre la estructura y tienen vara en `test_tabla.py`; C4-07 esta a medias; y C4-03, C4-04, C4-05 y C4-08 NO estan cubiertos, porque son contenido de la prosa adentro de una casilla. **Reescribir un caso de oro es decision de Martín.**
- **ABIERTO** · **LA COMPUERTA DE COMPLETITUD NO SE MIDIO EN VIVO.** El turno nuevo SI se midio: 9 turnos por Telegram el 3-sep entre 03:12 y 03:16 UTC, y el modelo respeto el esquema en los 9 —cero `turno_respuesta_no_es_la_mesa`—. Lo que mostro fueron tres defectos: la poda que se comia el nombre del producto y la guarda de honestidad que nunca corria, las dos ya arregladas y deployadas, y la compuerta, arreglada esta tarde y todavia sin una charla real encima. Lo que hay que mirar en la proxima prueba por WhatsApp son dos renglones nuevos: `turno_incompleto`, que dice que puntos quedaron abiertos, y `casilla_podada` con motivo `dato_sin_material`. Si `turno_incompleto` aparece con `pregunto=False`, la compuerta tiene un agujero.
- **ABIERTO** · **EL CANDADO DEL MAPA DE TESTS QUEDÓ EN ARCHIVO.** `tests/test_mapa.py` se apagó con el hub; el nocturno ya no lo corre. El piso de `banco_pruebas/mapa_piso.json` es del camino viejo. Reescribirlo sobre `turno.py` es otra ficha: no se revive el test apagado contra el inventario nuevo.
- **ABIERTO** · **D9 · SIETE ROJOS DE LA CAPA 2, todos de cableado y con la interpretación perfecta escrita a mano.** C2-S05 el comparativo devuelve el propio producto de referencia; C2-S07 el uso "para jugar" no es un campo del catálogo; C2-S08 el pedido abierto no deriva rubros ni cuenta; C2-S13 "me haces ese precio" no lo certifica ningún tema; C2-S17 "ese" no ancla al producto del turno anterior; C2-E01 la G15 que no existe devuelve rubros que no son; C2-E04 el tema `defectuoso` existe con otro nombre y vuelve vacío.
- **ABIERTO** · **D5 · `contradicciones` NO LO LEE NADIE.** El modelo lo declara y la mesa lo saca como pregunta, pero ninguna búsqueda de `resolver.py` lo usa.
- **ABIERTO** · **D4 · EL CAMPO DEL ATRIBUTO SIGUE SIN CERTIFICARSE.** El verbo ya llega al campo desde el 6-sep, pero el fondo sigue: un campo que no existe se resuelve al más parecido en vez de a un veredicto. La opción está en `arquitectura/FORMULARIO_V2.md`, hueco 1.
- **ABIERTO** · **D3 · LA JUNTA J4 SIGUE BLANDA PARA LAS LISTAS.** Los atributos ya aparean por término exacto; `items`, `stock` y `restricciones` siguen apareando por palabras compartidas contra las búsquedas. Ahora al menos deja rastro: `mesa_apareada`.
- **ABIERTO** · **HUECO 4 · QUE EL CÓDIGO LLENE LA CASILLA Y NO EL MODELO.** Es la arquitectura que Martín quiere y es la ficha grande. Tres opciones escritas en `arquitectura/FORMULARIO_V2.md`; ninguna se elige hasta que D2 tenga vara.
- **ABIERTO** · **LA OFERTA PROACTIVA NO EXISTE MAS.** La abría el punto de oferta de `indice_turno`, que se apagó. `oferta_diferida` se conserva tal cual para que el bot no vuelva a ofrecer lo que el cliente ya rechazó, pero el bot dejó de ofrecer por su cuenta. **Si tiene que volver, es una decisión de venta de Martín**, no del código.
- **ABIERTO** · **D8 · LA RESTRICCIÓN DE ORIGEN SIGUE SIN PODERSE CUMPLIR CON LA FUENTE DE HOY.** El campo `origen` del catálogo es prosa —"Marca Genius de Taiwan. Fabricado en China."— así que "las menos partes chinas posibles" no se puede filtrar ni ordenar. Es una decisión de FUENTE: qué campo normalizado se agrega, y si la restricción ordena en vez de filtrar.
- **ABIERTO** · **D7 · UN TEMA `ambiguous` SIRVE HASTA TRES POLÍTICAS.** Para producto, `ambiguous` frena y se pregunta; para tema, se sirven los tres. Son dos políticas opuestas ante el mismo veredicto, y es la causa medida de que "dame precio de una intermedia" abra cuotas y envío al exterior.
- **ABIERTO** · **D12 · LOS DOS EXTREMOS SUELTOS CON ITEMS.** Si el turno declara dos extremos opuestos y además hay items, el extremo del turno no gobierna ninguna búsqueda y cada item usa el suyo. El caso sin items ya está resuelto y verde: C2-S04.

## Espera a Martín

- **ESPERA A MARTIN** · **Ante un tema `ambiguous` el codigo SIRVE TODOS LOS CANDIDATOS en vez de repreguntar.** Repreguntar ahi seria pedirle al cliente que elija entre dos nombres de nuestro archivero —"¿garantia o garantia_como_usar?"—, que es la falla que el repo ya diagnostico el 4-ago al unir los dos enums. No se elige, que es la parte que importa de la regla cero: se sirven las dos politicas enteras y el modelo contesta la que preguntaron. Medido sobre las 785 señas: 1,37 temas servidos por seña, cero choques ciegos. **Si Martin quiere la repregunta, es una linea en `certificar_temas`.** **Y el 2-sep se vio el limite de esa medicion: 1,37 salio sobre SEÑAS, no sobre mensajes reales, y sobre un mensaje real sirvio tres politicas que no venian al caso.**
- **ESPERA A MARTIN** · Los pares de temas que comparten una palabra —`factura`/`precios_iva` con "iva", `cuotas`/`cuotas_financiacion`, `regalo`/`envoltorio_regalo`— **dejaron de hacer daño: la certificacion los sirve a los DOS y el modelo contesta con las dos politicas delante.** Cero choques ciegos sobre las 785 señas, medido en `tests/test_barrido_faq.py`. Darle a cada uno su seña propia sigue siendo una mejora de la FUENTE, pero ya no es un agujero.
- **ESPERA A MARTIN** · El sistema SIN LLM está medido en `banco_pruebas/puerta_determinista.py` y el número es alto. Lo que ninguna pieza ve es la NEGACIÓN —"el teclado sacalo"— y lo que no tiene pieza es `pide_precio` y `contradicciones`. Sirve como modo degradado para cuando el modelo se cae; NO se deploya en paralelo al vivo. **SU VARA NO ES UNA VARA Y SE PUEDE CONGELAR (FICHA 18, sin tocar).** Compara el codigo determinista contra el `registrar_pedido` que declaro el MODELO, y esas declaraciones viven adentro de los casetes: cada regrabacion cambia el blanco y el porcentaje se mueve solo -y el denominador tambien, 53 -> 54 turnos, asi que los dos numeros ni siquiera se comparan-. Congelarla es barato porque el dato ya esta en el repo: se copian las declaraciones de hoy a un archivo propio, se apunta el banco a ese archivo y no a los casetes vivos. Ahi el numero pasa a medir SOLO el codigo, que es lo que dice medir, y cambiar la referencia se vuelve un commit deliberado en vez de un efecto de otra tarea. **No hay que sacarla**: la pregunta que contesta -¿el sistema contesta con el LLM apagado?- es real y no hay otro numero para eso. Pero al cortar el juego congelado conviene AUDITARLO una vez a mano, porque hoy el techo del banco es "coincide con lo que dijo el modelo" y no "esta bien": si una declaracion estaba mal, el codigo determinista pierde puntos por acertar.
- **ESPERA A MARTIN** · `villa, Buenos Aires` resuelve a un CP que el cliente no nombró. Daño chico —misma tarifa de interior— pero es el sistema eligiendo por el cliente. Se arregla en `geo_cp.resolver`.
- **ESPERA A MARTIN** · Cuánto tiempo se guardan las conversaciones y con qué criterio se borran. Desde el 19-ago el bot pide solo el nombre, así que la superficie es chica, pero la decisión de retención es suya y conviene tomarla antes de vender a una empresa.
- **ESPERA A MARTIN** · **La restriccion de ORIGEN no se puede cumplir con la fuente de hoy, y es la unica prioridad que el cliente declaro.** Medido en el turno `2dde2ad0` del 31-ago: las cuatro busquedas con `filtros=['origen']` volvieron `ninguno_cumple_del_todo`, las cuatro. El campo `origen` del catalogo es prosa -"Marca Genius de Taiwan. Fabricado en China."-, asi que "las menos partes chinas posibles" no se puede filtrar NI ORDENAR, y el turno termino tirando el origen de dos categorias de cuatro sin contestar el criterio. Encima el modelo salio con un universal falso sobre el catalogo -`hub_venta_afirmo_sobre_el_catalogo`, `se_cumple_en=['almacenamiento externo','procesador']`- que la guardia borro bien. **La decision es de FUENTE y es tuya:** que campo normalizado se agrega -pais de fabricacion, o un grado- y si la restriccion ORDENA en vez de filtrar, que es lo que evita el cero. Mientras no exista ese campo, cualquier arreglo de codigo es cosmetico.
