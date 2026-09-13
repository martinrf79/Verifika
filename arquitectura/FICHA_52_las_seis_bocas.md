# FICHA 52 — LAS CINCO BOCAS

**Es el croquis del turno entero, con cada parte nombrada.** Se escribió el
13-sep-2026, antes de tocar una línea, y su único trabajo es que todos los que
entren al proyecto llamen igual a las mismas cosas.

**LAS DOS PALABRAS QUE ORDENAN TODO, y se definieron el 13-sep con Martín:**
una **BOCA** es un área de la FUENTE DE VERDAD donde el modelo busca; un
**RAMAL** es el cableado que conecta esa boca al motor. No son sinónimos y no
se cuentan juntos. La ficha nació con seis bocas y son **cinco**: CUENTA no
tiene área de fuente, así que no era una boca. El archivo conserva el nombre
viejo para no romper lo que ya lo cita.

**No describe lo que corre hoy.** Describe a dónde va. Lo que corre hoy lo dice
el código, siempre. Cuando una parte de acá se construya, el `git log` lo
cuenta y esta ficha no se actualiza para anunciarlo: se actualiza cuando el
DISEÑO cambia, que es otra cosa.

**Por qué existe.** El 12-sep se midió el turno vivo sobre una charla real de
Martín y salieron tres cableados distintos conviviendo: uno vivo, donde el
modelo pide y el motor contesta; uno a la fuerza, donde el código le mete el
inventario y el envío sin que los pida; y cinco áreas de la fuente de verdad en
disco que el turno no toca. La decisión de Martín fue una sola: **todo lo que se
contesta con un dato entra por el motor**.

---

## 1. LOS CATORCE PEDIDOS

Cualquier mensaje del cliente, en este nicho, es una combinación de estos
catorce. No hay un quinceavo, y si aparece uno, es un agujero del diseño y se
agrega acá antes de escribir código.

| # | El cliente pide | Contesta |
|---|-----------------|----------|
| 1 | ¿Lo tenés? | catálogo |
| 2 | ¿Hay stock y cuántos? | catálogo |
| 3 | ¿Qué trae? | catálogo |
| 4 | ¿Cuál cumple esto? | catálogo |
| 5 | ¿Me sirve para esto? | criterio |
| 6 | ¿Anda con aquello? | compatibilidad |
| 7 | ¿Cuánto sale? | catálogo |
| 8 | ¿Cuánto sale todo junto? | catálogo, y el retorno suma |
| 9 | ¿Envío, plazo, retiro? | envío |
| 10 | ¿Garantía, factura, cambios, cuotas? | políticas |
| 11 | ¿Me hacés precio? | políticas |
| 12 | Quiero comprar | cierre |
| 13 | ¿Dónde está mi pedido? | nadie: se deriva |
| 14 | Me llegó fallado | políticas y se deriva |

**Un mensaje complejo no es un pedido nuevo.** El del 12-sep —dos auriculares,
dos mouse, dos memorias, sin partes chinas, tres destinos, setenta treinta— es
el 4, el 7, el 8 y el 9 en un sobre. Por eso NO hay una boca de preguntas
complejas: complejo es la forma del sobre, no la clase del contenido, y una boca
que recibe todo lo que no encaja termina recibiendo todo.

**El 13 y el 14 son posventa y no tienen fuente.** Está bien que no la tengan.
Lo que no puede faltar es la salida escrita: se deriva a una persona.

**Y hay un movimiento que no es un pedido:** *"no, me refería al otro"*. Es
re-anclaje sobre la memoria. Se anota porque obliga a que la memoria sea
CONSULTABLE, no sólo guardable.

---

## 2. LAS SEIS RESPUESTAS

Toda boca devuelve una de estas seis. Ninguna otra. Son de primera clase: el
"no" no es un error, es un resultado.

1. **EL DATO** — con su id, para que se pueda verificar contra la fuente.
2. **NO TENGO ESE DATO** — el producto existe, el campo no está cargado.
3. **NO LO VENDEMOS** — el producto no existe, y esto sí tengo en su lugar.
4. **¿CUÁL DE ESTOS?** — es ambiguo y elige el cliente, no el sistema.
5. **¿ME CONFIRMÁS?** — falta un dato para poder contestar: el destino, la
   cantidad, cuál de dos lecturas.
6. **NO PUEDO, TE PASO CON ALGUIEN** — posventa, reclamo, excepción comercial.

**La 2 y la 3 son distintas y se confunden seguido.** Una dice que la ficha no
trae el dato; la otra dice que no hay ficha. Contestar una por la otra es el
defecto más caro del nicho.

**La 4 y la 5 también son distintas.** Una elige entre candidatos que ya están;
la otra pide un dato que todavía no existe en la charla.

---

## 3. EL CROQUIS

```
   CLIENTE ──▶ CANAL ──▶ TURNO
                           │
        ┌──────────────────┴──────────────────┐
        │   LO QUE VIAJA SIEMPRE, SIN MOTOR   │
        │   VOZ · PREGUNTA · MEMORIA (lee)    │
        │   TABLERO · MOLDES                  │
        └──────────────────┬──────────────────┘
                           ▼
                        MODELO
                           │  pide
                           ▼
                        MOTOR          una sola puerta
                           │
      ┌────────┬─────────┬─┴───────┬──────────┐          LOS RAMALES
      ▼        ▼         ▼         ▼          ▼
  CATÁLOGO  POLÍTICAS  COMPAT.   ENVÍO    CRITERIO       LAS BOCAS
   fichas     faq       pares    tarifa      uso         cada una con
   specs     curadas             plazo     conviene      su CÁLCULO
   ×cantidad                    ×destino                 adentro
      └────────┴─────────┴────┬────┴──────────┘
                              ▼
                          RETORNO      las seis respuestas, con
                              │        veredicto e id, Y LA CUENTA
                              │        que cruza bocas: total,
                              │        descuento, reparto
                              ▼
                        REDACCIÓN      el modelo escribe con los
                              │        números ya resueltos
                              ▼
                           GUARDA      no calcula: verifica.
                              │        Sin retorno no sale dato
                              ▼
                           CIERRE      lead · nombre · link
                              ▼
                           SALIDA ──▶ CLIENTE
                              ▼
                          MEMORIA      escribe: charla · vistos ·
                                       carrito · destino
```

**QUÉ CAMBIÓ Y POR QUÉ, 13-sep.** El croquis tenía CUENTA como una sexta boca y
la plata después de la redacción. Las dos cosas estaban mal, y la definición
que las corrige es una sola: **una BOCA es un área de la fuente de verdad; un
RAMAL es el cableado que la conecta al motor.**

**CUENTA no es una boca**, porque no tiene área de fuente: es aritmética sobre
datos que ya volvieron por otras bocas. Quedan cinco bocas.

**CADA BOCA TRAE SU PROPIO CÁLCULO, y ése es el criterio.** Envío ya lo hace:
su tabla de tarifas es fuente y el código deriva la del destino. Catálogo hace
lo mismo con la cantidad: "dos teclados de ésos" se resuelve contra la ficha y
la boca devuelve el subtotal de esa línea ya hecho. El cálculo vive donde está
el dato.

**LO QUE NO PUEDE VIVIR ADENTRO DE UNA BOCA es lo que CRUZA bocas:** el total
del pedido toca precios de catálogo, tarifa de envío y el descuento por
transferencia, que es política, más el reparto de pago. Meter eso en catálogo
obligaría a catálogo a leer envío y políticas, o sea una segunda puerta, que es
lo que la regla 2 prohíbe. Por eso vive en el RETORNO: es el único punto donde
ya volvió todo.

**Y LA PLATA SE CALCULA ANTES DE REDACTAR, no después.** El modelo escribe con
los números resueltos delante en vez de dejar huecos que otro llena. NÚMEROS
deja de ser la etapa que calcula y se funde con la GUARDA: su único trabajo es
verificar que toda cifra del texto salga del retorno, y tirar la respuesta
abajo si no.

---

## 4. LOS VEINTIDÓS COMPONENTES

**Entrada**

1. **CLIENTE** — WhatsApp o Telegram.
2. **CANAL** — resuelve la tienda por `phone_number_id`. El modelo nunca elige
   tienda; es la regla 10.2.
3. **TURNO** — el orquestador. Hoy `app/core/respuesta.py`.

**Antes del motor**

4. **LA VOZ** — quién habla: identidad, criterio y los cinco atributos de venta
   de la sección 5. Sale de `base_conocimiento.json`. Es fuente en el archivo y
   prompt en el turno. **No se busca, porque no es una respuesta.**
5. **LA PREGUNTA** — el mensaje del cliente, pelado, ANTES del aparato. Elegir
   entre moldes sin tener la pregunta delante es elegir a ciegas.
6. **LA MEMORIA, en lectura** — lo que ya se habló: resumen, productos vistos
   con id y precio, carrito, descartados, destino, nombre.
7. **EL TABLERO** — el índice de lo que se puede preguntar: los campos
   filtrables, las categorías, los operadores, y **las cinco bocas con lo que
   contesta cada una**. Viaja como esquema de herramienta del proveedor, no como
   texto, así un campo que no existe no se puede ni nombrar. **El tablero no
   tiene un solo dato.**
8. **LOS MOLDES** — las formas de la respuesta. Hoy `app/core/tipos.py`.

**El motor**

9. **EL MOTOR** — la única puerta. Ejecuta la consulta que escribió el modelo y
   certifica lo que devuelve. No razona, no elige, no escribe plata.
10. **LOS RAMALES** — el cableado del motor a cada boca. Uno por boca. Un ramal
    se puede cortar, medir y contar; por eso tiene nombre propio. **Boca y ramal
    no son sinónimos:** la boca es el área de la fuente, el ramal es el cable
    que la conecta. Un área sin cable existe en el disco y no la alcanza nadie,
    que es lo que le pasa hoy a `no_vendidas.json`.

**Las bocas**

11. **CATÁLOGO** — las fichas, las tres capas de specs —`specs_preguntables`,
    `specs_por_categoria`, `specs_por_modelo`— y `no_vendidas` adentro del "no
    lo vendemos". **Trae su cálculo: la cantidad.** "Dos teclados de ésos" se
    resuelve contra la ficha y la boca devuelve el subtotal de esa línea ya
    hecho. Es cerrado sobre el catálogo, así que no necesita a nadie más.
12. **POLÍTICAS** — la FAQ, con las curadas estampadas: el texto y sus valores
    salen juntos, nunca un número viejo pegado en la prosa.
13. **COMPATIBILIDAD** — la tabla de pares y su vocabulario. Boca propia a
    propósito: identidad y compatibilidad son dos ejes y no se cruzan, regla
    10.0.
14. **ENVÍO** — destino, tarifa y plazo. **La tarifa SÍ es fuente**, vive en
    Firestore bajo `config/tarifas_envio`; lo que el código calcula es la
    clasificación del texto a provincia y zona, no el número. Trae su cálculo
    adentro, uno por destino nombrado: es el modelo del que copian las demás.
15. **CRITERIO** — para qué sirve, cuál conviene, qué significa gama baja acá.
    Sale de las 106 entradas de `categorias` en `base_conocimiento.json`, cada
    una con sus disparadores y su texto. **Es la boca que falta entera.** Ojo
    con el archivo: el MISMO `base_conocimiento.json` sirve también la voz, y
    por eso la voz queda afuera del motor y el criterio no.

**La vuelta**

16. **EL RETORNO** — lo que vuelve por los ramales: filas certificadas, con id y
    con una de las seis respuestas de la sección 2, **más la cuenta que cruza
    bocas**: el total del pedido, el descuento y el reparto de pago. Eso vive
    acá y no adentro de una boca porque toca tres a la vez —precios de
    catálogo, tarifa de envío, descuento de políticas— y ninguna boca puede
    leer a otra sin abrir una segunda puerta. Es determinista y corre ANTES de
    redactar, con `calculadora` y `pago_split`, que ya están escritas.
17. **LA REDACCIÓN** — el modelo escribe con el retorno delante, **y con los
    números ya resueltos**: no deja huecos para que otro los llene, copia lo
    que el retorno trajo. **No es otra llamada**: es la última vuelta de la misma. Tres llamadas por turno ya se
    probaron y daban casi seis segundos comiéndose la cuota de a tres.

**Después del modelo**

18. **LA GUARDA** — **no calcula: verifica**, y por eso se come lo que antes
    era una etapa aparte. Son dos reglas. La primera ya vive en `numeros.py`:
    toda cifra del texto tiene que salir del retorno, y si no sale, la
    respuesta entera se tira abajo. La segunda todavía no existe y es la que
    reemplaza a obligar el motor: **si el texto nombra un producto, un precio,
    un plazo, una política o una cuenta, y no hubo retorno, no sale.** Un
    saludo no necesita motor; un dato sí. Es de contenido, no de llamada, y por
    eso es determinista y se mide.
19. **EL CIERRE** — lead, nombre y link de pago. **No es una boca: es una
    salida.** La boca contesta; el cierre actúa.
20. **LA SALIDA** — el texto que lee el cliente.
21. **LA MEMORIA, en escritura** — la charla, los vistos, el carrito y el
    destino. **Es la misma caja que la 6, con dos cables.** El carrito vive
    adentro de la memoria: es estado, no fuente.

---

## 5. LOS CINCO ATRIBUTOS DE VENTA

Viven en la voz y se aplican en la redacción. Los cinco salieron de charlas
reales, no de una lista de buenas prácticas.

1. No repetir lo que ya dijiste en el mensaje anterior.
2. Nombrar el destino con la palabra del cliente: "Posadas", no "misiones".
3. No volver a ofrecer lo que el cliente ya rechazó.
4. Una sola pregunta por mensaje.
5. Con precio mostrado y señal de compra, ofrecer el cierre.

---

## 6. LO QUE NO PASA POR EL MOTOR

Dos cosas, y son las únicas.

**LA VOZ**, al principio. Si hubiera que buscarla, el bot no tendría identidad
hasta después de buscar.

**LA MEMORIA**, al final. No es fuente de verdad: es lo que pasó recién.

Todo lo demás entra por el motor. Si aparece una tercera excepción, se discute
acá antes de cablearla.

**LA CUENTA NO ES UNA TERCERA EXCEPCIÓN, y conviene decirlo para que nadie la
cuente como tal.** No pasa por el motor porque no hay dónde buscarla: no es un
área de la fuente, es aritmética sobre lo que las bocas ya devolvieron. Por eso
no es una boca ni necesita un ramal: es una etapa del retorno.

---

## 7. LAS CUATRO ÁREAS DE LA FUENTE, Y QUÉ LECTOR LAS ALCANZA

Las bocas no son una idea: son los archivos que están en el disco. Leído el
13-sep de `data/clientes/verifika_prod/`, son **nueve archivos en cuatro
áreas**, más una quinta que vive en Firestore.

| Boca | Dónde vive | Lo lee |
|---|---|---|
| CATÁLOGO | `productos.csv`, `specs_preguntables.json`, `specs_por_categoria.json`, `specs_por_modelo.csv`, `no_vendidas.json` | `filtros_catalogo` y `fuente_producto`; **`no_vendidas` sólo lo lee `guia_compra`, que no lo importa NADIE en `app/`** |
| POLÍTICAS | `faq.json` | `curadas` y `fuente` |
| COMPATIBILIDAD | `compatibilidad.csv`, `compatibilidad_vocabulario.json` | `compatibilidad.py`, al que el turno no llega |
| CRITERIO | `base_conocimiento.json`, bloque `categorias` | nadie; el archivo sí lo lee `guia_venta_prosa` para la VOZ |
| ENVÍO | Firestore, `config/tarifas_envio` | `calculadora.cotizar_envio` por `fuente.texto_envio` |

---

## 8. DÓNDE ESTÁ CADA COSA HOY

Medido el 12 y el 13-sep sobre `main`. Se verifica abriendo el código; si esta
tabla y el código se contradicen, gana el código.

| Componente | Estado |
|---|---|
| Voz, pregunta, memoria, moldes, turno | vivos |
| Tablero | vivo, 940 tokens, **sin las cinco bocas listadas** |
| Motor | vivo, una puerta |
| Ramal a CATÁLOGO | vivo, **sin las tres capas de specs, sin `no_vendidas` y sin el cálculo de cantidad** |
| Ramal a POLÍTICAS | vivo desde el 12-sep |
| Ramal a COMPATIBILIDAD | **no existe** |
| Ramal a ENVÍO | el dato llega, pero **lo empuja el código**, no lo pide el modelo |
| Ramal a CRITERIO | **no existe** |
| Retorno | vive, pero **sin la cuenta**: `calculate_total` no la llama nadie desde `app/`, y ella es la única que llama a `pago_split` |
| Redacción, cierre, memoria | vivos |
| Guarda | **a medias**: `numeros.py` cuida la plata, y todavía calcula en vez de sólo verificar |

**LA MEDICIÓN DEL MOTOR, 19 turnos reales, leída el 13-sep por el issue 31.**
Buscó en 15 de 19, cero búsquedas vacías, toda condición se pudo aplicar. Los
cuatro que no buscaron tienen nombre y no son aleatorios: uno pidió el envío,
que el código ya le había puesto delante; uno pidió una política, y era ANTES
del mapa 3; uno es el setenta treinta, que no tiene a quién llamar; y uno es
variabilidad, porque el mismo mensaje sí buscó en las otras tres corridas.

**Partido por deploy, el número dice otra cosa que el promedio:** en los seis
turnos posteriores al mapa 3 —12-sep, 20:13 a 20:20— el modelo llamó al motor
en **6 de 6**. El agujero no es que el modelo esquive el motor: es que hay
datos que llegan por un segundo camino, y donde no hay cable no hay a quién
llamar. **Lo que falta no es que el modelo entienda: es que haya cable.**

**Y el costo nuevo, que sale de los mismos logs:** esos seis turnos gastaron
`vueltas=3` y `llamadas=2` todos, contra `vueltas=2` y una llamada antes. Son
tres llamadas al modelo por turno, que es justo lo que el apagón del 11-sep
vino a matar, con 4 consultas repetidas sobre 47. Se mide con `motor_turno` y
hay que mirarlo antes de agregar el próximo ramal.
