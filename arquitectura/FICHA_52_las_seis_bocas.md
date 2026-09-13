# FICHA 52 — LAS SEIS BOCAS

**Es el croquis del turno entero, con cada parte nombrada.** Se escribió el
13-sep-2026, antes de tocar una línea, y su único trabajo es que todos los que
entren al proyecto llamen igual a las mismas cosas.

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
| 8 | ¿Cuánto sale todo junto? | cuenta |
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
      ┌────────┬─────────┬─┴───────┬─────────┬──────────┐   LOS RAMALES
      ▼        ▼         ▼         ▼         ▼          ▼
  CATÁLOGO  POLÍTICAS  COMPAT.   ENVÍO    CUENTA    CRITERIO   LAS BOCAS
      └────────┴─────────┴────┬────┴─────────┴──────────┘
                              ▼
                          RETORNO      las seis respuestas,
                              │        con veredicto e id
                              ▼
                        REDACCIÓN      el modelo escribe
                              ▼
                          NÚMEROS      el código estampa la plata
                              ▼
                           GUARDA      sin retorno no sale dato
                              ▼
                           CIERRE      lead · nombre · link
                              ▼
                           SALIDA ──▶ CLIENTE
                              ▼
                          MEMORIA      escribe: charla · vistos ·
                                       carrito · destino
```

---

## 4. LOS VEINTITRÉS COMPONENTES

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
   filtrables, las categorías, los operadores, y **las seis bocas con lo que
   contesta cada una**. Viaja como esquema de herramienta del proveedor, no como
   texto, así un campo que no existe no se puede ni nombrar. **El tablero no
   tiene un solo dato.**
8. **LOS MOLDES** — las formas de la respuesta. Hoy `app/core/tipos.py`.

**El motor**

9. **EL MOTOR** — la única puerta. Ejecuta la consulta que escribió el modelo y
   certifica lo que devuelve. No razona, no elige, no escribe plata.
10. **LOS RAMALES** — el cableado del motor a cada boca. Uno por boca. Un ramal
    se puede cortar, medir y contar; por eso tiene nombre propio.

**Las bocas**

11. **CATÁLOGO** — las fichas, las tres capas de specs —`specs_preguntables`,
    `specs_por_categoria`, `specs_por_modelo`— y `no_vendidas` adentro del "no
    lo vendemos".
12. **POLÍTICAS** — la FAQ, con las curadas estampadas: el texto y sus valores
    salen juntos, nunca un número viejo pegado en la prosa.
13. **COMPATIBILIDAD** — la tabla de pares y su vocabulario. Boca propia a
    propósito: identidad y compatibilidad son dos ejes y no se cruzan, regla
    10.0.
14. **ENVÍO** — destino, tarifa y plazo. Es boca de CÁLCULO: el número no está
    escrito en ningún archivo, lo deriva el código del código postal.
15. **CUENTA** — total, reparto de pago, descuento, y la comparación entre dos
    fichas que ya volvieron. También de cálculo.
16. **CRITERIO** — para qué sirve, cuál conviene, qué significa gama baja acá.
    Sale de las 106 entradas de `categorias` en `base_conocimiento.json`, cada
    una con sus disparadores y su texto. **Es la boca que falta entera.**

**La vuelta**

17. **EL RETORNO** — lo que vuelve por el ramal: filas certificadas, con id y
    con una de las seis respuestas de la sección 2.
18. **LA REDACCIÓN** — el modelo escribe con el retorno delante. **No es otra
    llamada**: es la última vuelta de la misma. Tres llamadas por turno ya se
    probaron y daban casi seis segundos comiéndose la cuota de a tres.

**Después del modelo**

19. **LOS NÚMEROS** — el código estampa el envío, el total y el reparto, y tira
    abajo la respuesta entera si quedó una cifra que la fuente no tiene.
20. **LA GUARDA** — la regla que reemplaza a obligar el motor: **si el texto
    nombra un producto, un precio, un plazo, una política o una cuenta, y no
    hubo retorno, no sale.** Un saludo no necesita motor; un dato sí. Es de
    contenido, no de llamada, y por eso es determinista y se mide.
21. **EL CIERRE** — lead, nombre y link de pago. **No es una boca: es una
    salida.** La boca contesta; el cierre actúa.
22. **LA SALIDA** — el texto que lee el cliente.
23. **LA MEMORIA, en escritura** — la charla, los vistos, el carrito y el
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

---

## 7. DÓNDE ESTÁ CADA COSA HOY

Medido el 12 y el 13-sep sobre `main`. Se verifica abriendo el código; si esta
tabla y el código se contradicen, gana el código.

| Componente | Estado |
|---|---|
| Voz, pregunta, memoria, moldes, turno | vivos |
| Tablero | vivo, 940 tokens, **sin las seis bocas listadas** |
| Motor | vivo, una puerta |
| Ramal a CATÁLOGO | vivo, **sin las tres capas de specs ni `no_vendidas`** |
| Ramal a POLÍTICAS | vivo desde el 12-sep |
| Ramal a COMPATIBILIDAD | **no existe** |
| Ramal a ENVÍO | el dato llega, pero **lo empuja el código**, no lo pide el modelo |
| Ramal a CUENTA | **no existe**; `pago_split` está entero y no lo alcanza nadie |
| Ramal a CRITERIO | **no existe** |
| Retorno, redacción, números, cierre, memoria | vivos |
| Guarda | **a medias**: `numeros.py` cuida la plata, no el resto |

La primera medición del motor, sobre 19 turnos reales: buscó en 15, cero
búsquedas vacías, toda condición se pudo aplicar. **El modelo usa el motor y
traduce bien.** Lo que falta no es que el modelo entienda: es que haya cable.
