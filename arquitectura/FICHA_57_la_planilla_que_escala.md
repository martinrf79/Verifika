# FICHA 57 — LA PLANILLA QUE ESCALA

**Abierta el 21-sep-2026. Es una PROPUESTA DE DISENO, no una implementacion.**
No toca una linea de codigo. Existe para que la decision se tome con todo
sobre la mesa y en UN solo lugar, que es la regla del bloque 0: la segunda
descripcion de lo mismo es el telefono descompuesto.

**LA CONSIGNA DE MARTIN:** resolver el cuello real —la interpretacion de
multipreguntas en la PRIMERA llamada— con una forma que sirva **con este
catalogo y con catalogos mucho mas grandes**, para que cambiar de tienda no
obligue a replanificar.

---

## 0. EL INVARIANTE, Y ES LO QUE HACE QUE ESCALE

> **Nada que crezca con las FILAS entra al tablero. Solo entra lo que se
> deriva del ESQUEMA de la fuente, o lo que es universal.**

**La prueba:** multiplica el catalogo por cien. Si el tablero cambia de
tamano, el diseno esta mal.

**EL TABLERO DE HOY NO PASA ESA PRUEBA, y hay que decirlo antes que nada.**
La leyenda enumera VALORES: 75 marcas, los colores, los cinco de
`pais_fabricacion`. La variedad crece mas despacio que las filas, pero crece:
a 100.000 productos serian 500 marcas y la leyenda no entra. **La leyenda es
la pieza que hay que reemplazar, no ajustar.**

---

## 1. SON TRES PROBLEMAS, Y CADA UNO TIENE SU LUGAR

Venimos tratando de resolver los tres con el tablero. Por eso cada vez que se
agranda mejora un poco y no cierra.

    1 · CRITERIO     "por la crisis" → barato
                     VIVE EN: el entrenamiento del modelo. Ya esta resuelto.
                     EL TABLERO LLEVA: los NOMBRES de los conceptos, en
                     idioma del cliente. ~40-60 nombres.
                     TAMANO: constante. No depende de las filas.

    2 · ATERRIZAJE   "memoria" → "memoria ram"
                     VIVE EN: el motor, DESPUES del modelo.
                     EL TABLERO LLEVA: nada.
                     TAMANO: cero.

    3 · HUECO REAL   "el mas vendido" y no hay campo
                     VIVE EN: el veredicto.
                     EL TABLERO LLEVA: la frase negativa, una vez.
                     TAMANO: ~25 tokens, constante.

**Separados asi, el tablero pasa a ser O(1) en el catalogo.** La respuesta a
"¿escala?" deja de ser una esperanza y pasa a ser una propiedad del diseno.

---

## 2. LA FORMA DE LA PLANILLA

El modelo llena renglones. **Un renglon por cada cosa que el cliente dijo.**

    renglones: [                       OBLIGATORIO, primero, un solo nivel
      { dice:  "<las palabras del cliente>",   texto LIBRE
        es:    <enum de conceptos>,            CERRADO
        sobre: "<a que se aplica>" }           texto LIBRE, opcional
    ]

**Las dos mitades hacen cosas distintas, y esa es toda la idea:**

- **`dice` es libre.** El modelo usa su potencial entero. Traduce cualquier
  rodeo, cualquier frase desprolija, cualquier audio transcripto.
- **`es` es cerrado.** No puede nombrar un concepto que no existe.
- **`sobre` resuelve el ALCANCE**, que en multipregunta es el error callado:
  "dos auriculares y dos mouse que no sean chinos" —¿los dos rubros o solo
  los mouse?—. Hoy eso no tiene donde escribirse.

**Y `sin_clase` es un veredicto VALIDO**, no un error. Es la regla 10.0
aplicada al concepto: un renglon que no encaja en nada se declara, se cuenta
y el codigo decide si pregunta. Asi el sistema deja de fallar en silencio.

**LO QUE DEJA DE SER TRABAJO DEL MODELO:** `categoria`, `condiciones`,
`operador`, `ordenar_por`. Todo lo que habla en idioma de base de datos lo
deriva el codigo desde los renglones. Es la FICHA 55 §4.1 con la pieza que le
faltaba.

---

## 3. EL ENUM, EN TRES CAPAS — y esto contesta "no replanificar por tienda"

**CAPA 1 · UNIVERSAL.** No depende de la tienda. Se escribe una vez, para
siempre, para cualquier e-commerce.

    lo_mas_barato · lo_mas_caro · rango_de_precio · hasta_tanto
    cantidad · total · reparto_pago · envio_a
    compatible_con · politica_de
    no_quiero · prefiero · parecido_a · ese_de_antes
    no_estoy_seguro · ya_intente · afirma_un_dato

**CAPA 2 · DERIVADA DEL ESQUEMA.** Automatica, cero codigo por tienda.
Por cada campo ordinal de la fuente salen dos nombres. Con `precio_ars`,
`peso_gramos` y `garantia_meses` salen seis. Una tienda con `potencia` gana
`lo_mas_potente` sola, sin que nadie escriba nada.

**CAPA 3 · EL DICCIONARIO COMERCIAL.** Lo unico escrito a mano, y es el eje D
de la FICHA 56: `para_jugar`, `para_oficina`, `para_regalo`, `para_viajar`.
Cada uno mapea a condiciones sobre campos de la capa 2. **Unas 30 entradas.**

    TIENDA NUEVA:  capa 1 intacta · capa 2 se regenera sola · capa 3, 30 lineas

Eso es el requisito que pediste, escrito como propiedad y no como promesa.

---

## 4. LA DECISION QUE ESTA ARRIBA DE TODAS: ¿HERRAMIENTA O CONTENIDO?

**Dos hallazgos independientes apuntan al mismo lugar y hay que medirlo ANTES
de construir nada.**

**1 · La cache no cubre las herramientas.** El descuento del 90% sobre tokens
cacheados no aplica cuando hay `tools`. Justo nuestro caso, porque el tablero
viaja como herramienta. Mientras siga ahi, el presupuesto se paga entero en
cada turno.

**2 · Tool Suppression.** Un estudio sobre modelos de pesos abiertos reporta
que con tool calling Y restriccion de esquema prendidos a la vez, el modelo
**deja de llamar a las herramientas** mientras el cumplimiento del esquema
sigue alto. Las mascaras de la gramatica dejan los tokens de llamada
inalcanzables. **Y es silencioso: los tableros de observabilidad muestran un
sistema sano mientras el agente contesta de memoria.**

**Para este proyecto eso es lo peor que puede pasar**, porque es exactamente
la alucinacion que toda la arquitectura existe para impedir, disfrazada de
salud.

**La salida que proponen los dos** es la misma: sacar la planilla de la
llamada a herramienta y pedirla como contenido estructurado. Ahi entra en
cache Y no compite con el tool calling.

**No se decide por lectura. Se mide.** Es la puerta de entrada a todo lo demas.

---

## 5. LO QUE FALTABA EN LA IDEA, Y HAY QUE PONERLO AHORA

Seis cosas que no estaban y que si se agregan despues, se agregan mal.

**5.1 · LA PREMISA FALSA — eje F2.** "El K120 inalambrico" cuando es con
cable. La alucinacion no la trae el modelo: la trae el CLIENTE, y aceptarla es
mentir con sus palabras. Necesita su propio concepto —`afirma_un_dato`— para
que el codigo pueda verificar la afirmacion contra la ficha ANTES de
contestar. Es el unico vector que hoy pasaria por todos los candados.

**5.2 · LA MEMORIA ENTRE TURNOS.** Todo este diseno es sobre la PRIMERA
llamada. "Ese", "el anterior", "el que me mostraste" —el eje A11— necesitan el
estado del turno previo. En PENDIENTE ya hay tres campos de memoria que nadie
escribe. **Sin eso, la planilla resuelve el turno uno y se rompe en el dos.**

**5.3 · EL ALCANCE.** Resuelto arriba con `sobre`, pero se anota como
requisito y no como detalle: en multipregunta es el error mas callado.

**5.4 · EL RENGLON QUE NO SE PUEDE CUMPLIR.** Medio mensaje sale y medio no.
Ya existe `turno_incompleto`; tiene que ser parte del diseno desde el
principio, no un parche.

**5.5 · LA VARA TIENE QUE CRECER.** Hoy mide SEIS mensajes y el diseno cubre
52 clases. **Optimizar contra seis mensajes es optimizar contra seis
mensajes.** Antes de editar nada, la vara tiene que cubrir las clases, o el
numero va a subir sin que el sistema mejore.

**5.6 · LA PRUEBA A ESCALA.** La robustez no se prueba a 880. Choca con la
regla 9 —un solo catalogo, sin fixtures nuevos— asi que se hace **en memoria,
solo durante la medicion**, sin dejar archivo. Necesita el OK de Martin.

---

## 6. EL ORDEN, CON SU COMPUERTA

Cada paso tiene un numero que decide si se sigue. Ninguno se hace "porque
estaba en el plan".

    PASO 0   La vara crece a las 52 clases.           SIN ESTO NADA MIDE.
    PASO 1   Medir herramienta vs contenido.          Decide la arquitectura.
    PASO 2   Prueba a escala en memoria.              Decide si hace falta trie.
    PASO 3   El enum de conceptos, capas 1 y 2.       Se mide contra el piso.
    PASO 4   El diccionario comercial, capa 3.        El eje D.
    PASO 5   El codigo deriva las consultas.          Recien cuando 3 y 4 midan.
    PASO 6   Alias offline escritos por el modelo.    Cierra el aterrizaje.

**Anotado y NO en el plan:** trie, cambio de proveedor, Qwen, gramatica
propia. Son la consecuencia del paso 1 y del paso 2, no una tarea suelta.

---

## 7. LO QUE ESTA PROPUESTA NO HACE

No edita. No elige proveedor. No toca el catalogo.

Y no reemplaza a la FICHA 56: aquella dice QUE hay que traducir —52 clases—,
esta dice CON QUE FORMA. Las dos juntas son la unidad de trabajo.
