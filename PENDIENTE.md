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

**15-sep: LA UNIDAD DE TRABAJO ABIERTA ES `arquitectura/FICHA_54_el_tablero_y_las_bocas.md`.**
Consigna de Martin: lo que el modelo VE en el tablero tiene que ser exactamente
lo que las bocas PUEDEN contestar. **NO se construyen bancos nuevos** —ya se
ramifico por ahi tres veces—; se corre el que hay antes y despues de cada
cambio. El orden de los cuatro trabajos esta en la seccion 6 de la ficha.

**15-sep: EL NUMERO DE LA ATADURA, y es el "antes" contra el que se compara.**
`python3 banco_pruebas/tanda_tablero.py`, clave gratis, 17 mensajes, cero
caidos: **pidio el campo que hacia falta en 13 de 16, 81%**, con 2,65 vueltas
por turno. Los ceros son `compatibilidad` 0 de 1, `criterio` 0 de 1, y `cuenta`
1 de 2. El banco ahora mide QUE CAMPOS declaro el modelo contra los que hacian
falta, cuenta aparte los turnos caidos por cuota, y espera 20 segundos entre
mensajes: sin la pausa medía la cuota gratis, no al bot.

**15-sep: EL PROMPT SE CONTRADICE SOBRE LA PLATA, y lo escribi yo el 14-sep.**
`respuesta._REGLAS` dice que el precio es el unico numero de plata que el modelo
puede escribir, y seis renglones despues que el total de la cuenta se copia
igual que un precio. Seccion 5 de la ficha 54.


**14-sep: LA CUENTA DEL RETORNO, y con ella el setenta treinta.** `{{total}}` lo
resolvia `numeros` SUMANDO las cifras ya escritas en el mensaje, DESPUES de
redactar. Esa suma no conoce el descuento por transferencia ni el reparto entre
medios, asi que el 70/30 no existia: `calculate_total` es la unica que llama a
`pago_split` y el total del pedido no la llamaba desde el apagon. Ahora se pide
por el campo `cuenta` de la MISMA puerta, con los ids certificados; los destinos
NO se declaran, salen de los `envios` de esa misma llamada. Toda la plata la
sigue haciendo `calculadora`, el envio incluido, que entra como `items_extra`
con el concepto que ella deriva de la provincia. Medido: 2 mouse a Cordoba con
70/30 dan total $82.500 y total final $76.725. El total calculado es FUENTE
—el modelo lo puede escribir— y si deja el hueco, el hueco se llena con ESE
total. **LO QUE FALTA ES MEDIRLO VIVO:** renglones `cuentas` y
`cuentas_sin_total` de `motor_turno`, que ya los lee `produccion.py`.

**14-sep: LA PROSA SE PIDE Y LAS SPECS VIAJAN, al reves del 13-sep.** Lo que se
midio entonces estaba medido con la prosa adentro. Medido ahora, cinco fichas
por rubro: la prosa es el 60 al 63 por ciento del retorno de TODA lista, y las
specs completas son mas baratas que ella en los cuatro rubros -teclado -1.404,
notebook -411, mouse -1.377, silla gamer -2.798-. Decide `busco`, que el modelo
ya declara, asi que no costo un campo nuevo: con `uno` viaja todo, con `varios`
no viaja prosa. Retornos: teclado 4.628 -> 2.719, mouse 4.626 -> 2.744, silla
5.038 -> 1.735, y **ocho notebooks pasaron de 8.932 a 7.478, o sea que dejaron
de romper el recorte de 8.000**. El campo `specs` de la consulta se borro y
devolvio 62 tokens del tablero. **LO QUE FALTA ES MEDIRLO VIVO:** si al modelo
le alcanza para redactar una lista sin los parrafos.


**14-sep: EL UMBRAL DE IDENTIDAD, y era el agujero grande de la busqueda.**
Medido ANTES de tocar, sobre el catalogo vivo: de doce pedidos de cosas que la
tienda no vende, OCHO volvian `existe` con los MISMOS cinco mouse -`dron`,
`bicicleta`, `zapatillas`, `guitarra`, `perfume`, `colchon`, `taladro`-. La
causa no era una palabra faltante en `no_vendidas.json`: `relevancia` es un
ORDENADOR, asi que con 880 productos siempre devuelve los cinco de arriba
aunque el mejor tenga parecido cero. **Ahora la identidad la decide
`lo_nombra`, que mira solo nombre, modelo, marca, tags y categoria, nunca la
prosa: es la regla 10.0 aplicada al texto.** NO LLEVA NUMERO -pregunta por el
estado, no por un puntaje-, asi que no hay que recalibrarlo cuando cambie el
catalogo. Solo corre SIN RECORTE: con una categoria o una condicion aplicada el
texto es caracteristica, no identidad, y `teclado retroiluminado` sigue
contestando. Y el orden explicito sirve filas igual, porque `lo mas barato que
tengas` pide un extremo que existe aunque las palabras no nombren nada. Ahora
12 de 12 y los 11 que si existen sin moverse. Vara: 8 casos nuevos en
`tests/test_motor.py`, 451 verdes. **LO QUE FALTA ES MEDIRLO VIVO:** el renglon
que lo cuenta es `vacios` de `motor_turno`, por el issue 31 con `/logs`.

**`arquitectura/MAPA_CABLEADO.md` ESTA VIEJO Y MIENTE.** Describe `turno.py`,
`tabla.py`, `molde.py`, `resolver.py` y `herramientas.py`, y ninguno de esos
archivos existe desde el apagon del 11-sep. El camino vivo es
`orchestrator` -> `respuesta.procesar_turno` sobre `motor.buscar`. Reescribirlo
es la ficha de ordenar el repo, que quedo para despues.


- **CERRADO el 13-sep** · **EL TABLERO, entero.** 2,22 vueltas por turno contra
  3,00, buscaron 35 de 36, cero busquedas vacias, y la consulta repetida ya no
  se ejecuta dos veces. Ficha 53, vara en `tests/test_tablero.py` con 20 casos,
  banco en `banco_pruebas/tanda_tablero.py` y piso en `tablero_piso.json`. **Lo
  que seguia eran los RAMALES, y el 13-sep quedaron los cinco enchufados.** La
  tabla de la FICHA 52 dice cual falta medir vivo.

**13-sep: EL DISEÑO ENTERO DEL TURNO ESTA ESCRITO, Y ES LA UNIDAD DE TRABAJO
ABIERTA.** `arquitectura/FICHA_52_las_seis_bocas.md`: los 14 pedidos posibles del
nicho, las 6 respuestas posibles, los 22 componentes con nombre, el croquis y la
tabla de que esta vivo y que falta. Decision de Martin: todo lo que se contesta
con un dato entra por el motor; solo la voz y la memoria quedan afuera.

**13-sep, LAS DOS PALABRAS, y ordenan el resto.** Una BOCA es un area de la
FUENTE DE VERDAD; un RAMAL es el cable que la conecta al motor. No se cuentan
juntos. Con eso son **cinco bocas, no seis**: CUENTA no tiene area de fuente.
**Cada boca trae su propio CALCULO adentro** -envio ya lo hace con la tarifa,
catalogo lo tiene que hacer con la cantidad-, y lo que CRUZA bocas -total,
descuento, reparto- vive en el RETORNO y se calcula ANTES de redactar, para que
el modelo escriba con los numeros resueltos en vez de dejar huecos. NUMEROS
deja de calcular y se funde con la GUARDA, que solo verifica.

**13-sep: LA BOCA CATALOGO QUEDO ORDENADA, y ninguna de las tres piezas era
un calculo nuevo.** Las specs ya se calculaban enteras en el camino vivo
-`firestore_client` llama a `enriquecer` en cada refresco- y la ficha no las
mostraba: ahora se piden POR NOMBRE, y el mapa entero sale solo con `busco:
uno`. Se midio antes de elegir: el mapa completo engorda la ficha hasta un 57%
y cinco notebooks con todo dan 8.837 caracteres. **La cantidad es el calculo de
esta boca y lo hace `calculadora`**: dos unidades vuelven con el subtotal ya
escrito, y `calculate_total` volvio a tener un llamador vivo -antes del
13-sep TODAS sus menciones en `app/` eran comentarios-. Y `no_vendidas`
se enchufo: el censo bajo de 28 a 27.

**13-sep: EL RAMAL A COMPATIBILIDAD QUEDO ENCHUFADO, y el dato ya estaba
calculado.** La tabla de la casa se estampa en CADA ficha al leer el catalogo
-`fuente_producto.enriquecer`- y despues se tiraba: `evaluar` y `evaluar_par`
no las llamaba nadie desde el turno, asi que la compatibilidad la contestaba el
modelo de memoria. Ahora se pide por el campo `compatibilidad` de la MISMA
puerta -no hay herramienta nueva-, consume un id certificado, y vuelve
compatible / incompatible / ambiguo / sin_dato con el motivo escrito por el
codigo. Techo del tablero: 2.100 -> 2.300, con las cuentas en
`tests/test_tablero.py`. Vara: 12 casos en `test_motor.py` y 2 en
`test_turno_nuevo.py`. **LO QUE FALTA ES MEDIRLO VIVO:** los renglones nuevos
de `motor_turno` son `compat` y **`compat_sin_dato`, que es el que dice que
FILA agregarle a `compatibilidad.csv`**, y salen por el issue 31 con `/logs`.

**13-sep: LA BOCA DE ENVIO SE PIDE, YA NO SE EMPUJA, y era el ultimo dato que
llegaba por un segundo camino.** El codigo leia el mensaje crudo con `geo_cp`,
cotizaba y ponia el bloque delante EN CADA TURNO. Ahora el modelo nombra el
destino con las palabras del cliente -campo `envios` de la misma puerta- y el
codigo sigue haciendo lo suyo: clasificar el texto a provincia y sacar el
numero de la tabla. Se borro `fuente.texto_envio` entero y con el
`geo_cp.lugares_en_texto`, que quedo sin llamador el mismo dia. El apagado de
la politica del RANGO se mudo al motor, que es donde ahora se ven las dos
cosas, y cambio de regla: sin tarifa exacta el rango SI se sirve, porque es lo
unico que la casa tiene para contestar "¿hacen envios?". La provincia NO viaja
al modelo -`estable_de` la resuelve del lado del codigo- para que no le
conteste "misiones" al que pidio a Posadas. Techo del tablero: 2.300 -> 2.400.
Vara: la seccion entera de envio de `test_turno_nuevo.py`, reescrita sobre el
camino nuevo. **LO QUE FALTA ES MEDIRLO VIVO**, y hay dos preguntas concretas:
si el modelo PIDE el envio cuando se lo preguntan -renglon `envios` de
`motor_turno`- y cuanto bajo el turno al sacarle el bloque que viajaba siempre.
El renglon `envios_sin_clasificar` dice que lugar no reconocimos.

**13-sep: EL RAMAL A CRITERIO QUEDO ENCHUFADO, y era la ultima boca sin cable.**
Las entradas de `base_conocimiento.json` estan escritas y del turno no las
alcanzaba nadie: del archivo se usaba la VOZ y nada mas, asi que "¿me sirve para
jugar?" -el pedido 5 de los catorce- lo contestaba el modelo de memoria. Ahora
se pide por el campo `criterio` de la MISMA puerta y lo certifica
`fuente.criterio_de`, con los tres veredictos y sin elegir ante un empate. **Y
se cerro el camino de al lado, que era el que hacia daño:** `_texto_del_tema`
caia al criterio cuando la FAQ no tenia el tema, asi que la prosa de `mouse`
llegaba rotulada "POLITICAS DE LA CASA" y se comia una de las tres ranuras de
las politicas de verdad. El reparto por area lo hace el codigo en las dos
direcciones: un tema que la FAQ contesta y entro por `criterio` vuelve como
politica, y al reves. Techo del tablero: 2.400 -> 2.530, con las cuentas en
`tests/test_tablero.py`; es el ultimo que se paga por una boca. Vara: 12 casos
en `test_motor.py` y 2 en `test_turno_nuevo.py`. **LO QUE FALTA ES MEDIRLO
VIVO:** los renglones nuevos de `motor_turno` son `criterio` y
**`criterio_sin_resolver`, que es el que dice que ENTRADA agregarle a
`base_conocimiento.json`**, y salen por el issue 31 con `/logs`.

**13-sep: DOS ARREGLOS DEL MOTOR, los dos medidos antes de tocar.** La
AMBIGUEDAD colgaba de un `elif`: una consulta con `ordenar_por` no calculaba
parecido, asi que "Teclado Logitech K380" con `busco: uno` devolvia `ambiguo`
con dos candidatos y el MISMO pedido con un orden por precio devolvia `existe`
con cinco y el modelo eligiendo -la regla 10.0 se perdia por una perilla de
paginado-. Y el `_n` del deduplicador viajaba adentro del retorno al modelo.

**13-sep: EL AGUJERO GRANDE DE LA BUSQUEDA, MEDIDO Y ABIERTO.** El arreglo de
`no_vendidas` tapa SOLO las palabras escritas en el json. Medido sobre el
catalogo vivo: `celular` y `heladera` vuelven `no_existe` bien, pero **`dron`,
`bicicleta` y `zapatillas` vuelven `existe` con cinco mouse y teclados**. La
causa NO es que falte una palabra en la lista: `relevancia` es un ORDENADOR, no
un filtro, asi que con 880 productos siempre devuelve los cinco de arriba
aunque el mejor tenga parecido cero. **El arreglo es un UMBRAL de puntaje**, de
ESTADO y no de vocabulario: bajo el piso, `no_existe` y sin filas. Perseguirlo
con una lista de palabras es el camino que este repo ya recorrio tres veces
-4 nodos, 18, 46- y del que ya volvio.

**13-sep: Y LA PROSA PESA MAS QUE LAS SPECS, al reves de lo que parecia.** De
los 4.412 caracteres de cinco fichas de teclado, **2.900 son prosa (65%)**:
`descripcion`, `descripcion_rica`, `contenido_caja`, `uso_recomendado`,
`garantia_detalle`. Las siete specs estructuradas suman 1.501 si van todas y
306 si se pide una. **Lo que corresponde a futuro es al reves de lo que se
hizo: que las specs viajen siempre y que la PROSA se pida.** No se cambio
todavia porque sacar prosa toca lo que el modelo usa para redactar, y eso se
mide antes de tocarlo.

**LOS DOS DEFECTOS QUE DESTAPO EL TRABAJO, los dos medidos:** a "tenes
celulares?" el motor contestaba **`existe` con cinco productos que no son
celulares** -la relevancia SIEMPRE devuelve algo, asi que no puede ser la que
decida si algo existe-, y el retorno se recortaba con `json.dumps(r)[:8000]`,
o sea que un retorno grande le llegaba al modelo **partido al medio**, sin
cerrar y con la ultima ficha mutilada. Ahora se recorta sacando FILAS y se le
dice que hay mas. Vara: 10 casos nuevos en `test_motor.py` y `test_turno_nuevo.py`.

**YA NO FALTA CABLEAR NINGUN RAMAL: LO QUE FALTA ES LA CUENTA DEL RETORNO.** Los
cinco se enchufaron el 13-sep. El setenta treinta lo cierra esa cuenta:
`calculate_total` **ya tiene un llamador vivo** -el subtotal de la boca
CATALOGO- pero el TOTAL del pedido sigue sin llamarla, y ella es la unica que
llama a `pago_split`.

**13-sep, LA MEDICION DEL MOTOR, leida por el issue 31 sobre los 19 turnos.**
Busco en 15 de 19, cero busquedas vacias, toda condicion se pudo aplicar. Los
cuatro que no buscaron tienen nombre: uno pidio el ENVIO, que el codigo ya le
habia puesto delante; uno pidio una POLITICA y era antes del mapa 3; uno es el
setenta treinta, que no tiene a quien llamar; y uno es variabilidad. **Partido
por deploy el numero es otro: en los seis turnos posteriores al mapa 3 -12-sep
20:13 a 20:20- llamo al motor en 6 de 6.** El agujero no es que el modelo
esquive el motor: es que hay datos que llegan por un segundo camino.

**13-sep, EL COSTO NUEVO Y NADIE LO ESTABA MIRANDO.** Esos seis turnos gastaron
`vueltas=3` y `llamadas=2` TODOS, contra `vueltas=2` y una llamada antes: son
tres llamadas al modelo por turno, que es justo lo que el apagon del 11-sep
vino a matar, con 4 consultas repetidas sobre 47. Se mide con `motor_turno` y
hay que mirarlo ANTES de agregar el proximo ramal.


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

**11-sep, noche: DOS DE ROBUSTEZ DEL MOTOR, y un candado que faltaba.** La
AMBIGUEDAD dejo de leerse desde `cuantos` -una perilla de paginado usada como
intencion- y la declara el modelo en `busco`: un producto puntual pedido con
cinco filas no recibia la ambiguedad NUNCA, que es donde elegir es inventar. La
FILA DEL RESCATE dejo de viajar muda: lleva `no_cumple` con el dato real de la
ficha, con `dato_que_falla`, que estaba escrita para esto y no la llamaba nadie.
Y LA GRILLA DE FILTROS -687 casos, cubierta al 100% desde el 12-ago- LA CORRIA
UNA SESION A MANO: ahora la corre la bateria y dice sobre cuantos casos paso. El
dia que se corrio encontro un agujero real: una condicion de texto SIN VALOR se
aplicaba igual y dejaba el catalogo en cero, en silencio.

**11-sep, noche: LA TANDA VIVA ESTABA ROTA DESDE EL APAGON.** `clon_produccion.
instalar` importaba `banco_pruebas.archivo_vivo`, que le pisaba funciones a
`app.core.pedido` y `app.core.resolver`: los dos se apagaron con la FICHA 48, el
import reventaba y se llevaba puesto el unico instrumento que corre el camino
vivo ANTES del deploy. No se noto porque nadie la corrio. Se saco el enchufe, no
se revivio el modulo. **Primera corrida con el numero puesto: 9 de 11 turnos
limpios y las 2 fallas son 429 de la clave gratis, no defectos.** El motor
busco en 7 de 11, cero re-busquedas, cero repetidas, cero rescates, los 7
veredictos `existe`. Ojo con el 4 de 11 que contesto SIN buscar: dos son los
turnos que murieron por 429.

**12-sep: EL CENSO DEL CABLEADO. 32 PUNTAS SUELTAS, Y CASI LA MITAD SON DE UN
SOLO MODULO.** `python3 banco_pruebas/censo_cableado.py`, con techo en
`cableado_techo.json` y candado en `tests/test_censo_cableado.py`. Cinco
detectores mecanicos: modulo que ni importa, campo que se lee y nadie escribe,
funcion viva sin llamador, hueco que nadie llena, y capacidad ofrecida al modelo
que el codigo no consume. Primera corrida: **6 modulos rotos, 9 campos sin
escritor, 17 funciones sin llamador**. Las desconexiones no eran fallas
independientes: son puntas de los dos apagones, el del 3-sep y el del 11-sep.
Por eso se pueden contar y por eso tiene final.

**LA PUNTA GRANDE ES `app/core/estado_venta.py`: 15 de las 32, el 47%, en 417
lineas.** Nadie llama `set_current_estado` en el camino vivo, asi que
`get_current_estado` devuelve `{}` SIEMPRE: todo lo que ese modulo le aporta a
`calculadora` es un diccionario vacio.

**SE INTENTO CORTARLO EL 12-SEP Y EL CENSO LO FRENO, con razon.** Sacar sus dos
muletas de `cotizar_envio` SUBIO el censo: al irse los lectores, mas funciones
quedaron sin llamador. Un corte a medias empeora el cableado. Y ademas destapo
dos cosas que agrandan la ficha: **`calculate_total` no la llama NADIE desde
`app/`** -la cuenta quedo huerfana del camino vivo cuando el turno paso a sumar
con `{{total}}`-, y **hay varas que miden ramas muertas**: `test_envio.py::
test_localidad_ambigua_resuelve_con_provincia_del_estado` setea el estado a mano
para medir una capacidad que en produccion no corre desde el apagon.

**La ficha entonces es una sola y es de tres partes: `estado_venta`,
`calculate_total` y las varas que las miden. Esta escrita entera en
`arquitectura/FICHA_51_el_fantasma_del_hub.md` y es la unidad de trabajo
ABIERTA.** Toca el modulo de la plata. **La decide Martin.** Lo unico que se saco por ahora es lo que se pudo REEMPLAZAR sin
perder nada: la localidad ambigua mas la provincia de la charla, que estaba
muerta en `estado_venta` y ahora vive en `fuente.texto_envio`, donde el dato si
existe.

**12-sep, MADRUGADA: CUATRO CABLES, TODOS MEDIDOS ANTES DE TOCAR.** La sonda
por WhatsApp desmintio dos sospechas —`busco` SI se declara, `puntuales: 1`, y
la restriccion de origen SI se aplica, `rescates: 1`— y confirmo las otras dos.
Lo que se cerro: **(1)** el modelo lee la PREGUNTA antes de los veinte moldes, y
la fuente dejo de viajar DUPLICADA en cada vuelta; **(2)** el formato se OBLIGA
con `response_format` y el tipo solo puede ser uno de los veinte —medido contra
el proveedor: sin esquema contestaba en markdown, que era el `tipo_vacio` de
tres de cada cuatro turnos—; **(3)** el envio cotiza CADA destino que el cliente
nombro, con `{{envio:<destino>}}` por cada uno, y lo nombra CON LA PALABRA DEL
CLIENTE —"Posadas", no "misiones"—, que es regla de venta y ademas lo unico que
viaja fuera de la tabla argentina; **(4)** el MAPA 3: las politicas las pide el
modelo por el motor con el campo `temas`, sin herramienta nueva, y las certifica
`fuente.politicas_de`. `politicas_relevantes` se borro. Censo 29 -> 28.

**LO QUE FALTA MEDIR DE ESOS CUATRO: la tanda por WhatsApp posterior al deploy
de las 02:4x.** Los renglones a mirar son `tipo` —tiene que dejar de venir
vacio—, `envio_cotizado_varios`, y los dos nuevos de `motor_turno`: `temas` y
**`temas_sin_resolver`, que es el renglon que dice que tema agregarle a la
FAQ** y antes no existia.

**LOS NOMBRES Y EL DETALLE DE CADA FALLA NO SE ESCRIBEN ACA.** Viven en
`arquitectura/MAPA_CABLEADO.md`, que es el unico lugar donde se nombra el
cableado: estaciones `T`, juntas `J`, puntos de modelo `L` y desconexiones `D`.
Aca va una linea por item, con su numero. Si un item y el mapa se contradicen,
gana el codigo y los dos estan mal.

- **ABIERTO** · **FICHA 55 · EL RUTEO ES DEL MOTOR, NO DEL MODELO.** La unidad nueva, abierta el 16-sep: el modelo llena una planilla plana con las palabras del cliente y el codigo rutea cada renglon con las certificaciones que YA existen y hoy corren tarde. Es la decision 1 del 19-ago, hecha chica. **El paso 4.2 —una sola definicion de las bocas— cerro el 16-sep: el indice del tablero, el encabezado del retorno y la regla de la plata salen de `app/core/bocas.py`.** Queda el 4.1, la planilla plana, y el 4.3, el pedido como estado. La ficha tiene los siete conflictos con su arreglo, las seis reglas contra la cascada y el numero que la mide: la consistencia entre turnos, hoy cero de tres.
- **CERRADA** · **FICHA 54.** Los seis pasos hechos y medidos en vivo el 15 y 16-sep. Lo que mostro la medicion: el modelo declara `consultas` y `envios` siempre, y `cuenta`, `criterio` y `compatibilidad` casi nunca. Eso es lo que la FICHA 55 viene a arreglar, y no con mas prompt.
- **ABIERTO** · **LA GUARDA DE ESTADO YA CORRIGE, Y FALTA EL NUMERO DE LA CORRECCION.** Desde el 16-sep, si la respuesta afirma sobre un campo que el turno no miro, el codigo le devuelve lo que la fuente SI tiene de ese campo y le pide de nuevo, una sola vez, con tablero. No se tira la respuesta ni se edita la prosa. **Lo que hay que mirar en la proxima tanda es `correcciones` en `motor_turno` y el renglon `correccion_de_estado` en la pelicula:** cuantas veces salta, si la segunda respuesta es mejor que la primera, y cuanto cuesta la vuelta de mas. **Y el hueco que esta pieza NO tapa:** si el modelo tira la restriccion y NO afirma nada sobre el campo, no hay nada que corregir y el cliente se queda sin lo que pidio. Eso es el ruteo, o sea la FICHA 55 §4.1.
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
