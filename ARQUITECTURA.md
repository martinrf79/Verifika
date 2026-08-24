# Arquitectura de Verifika — el turno, de punta a punta

Mapa de referencia permanente. El estado del día vive en
`RESUMEN_PARA_NUEVO_CHAT.md`, lo decidido en `DECISIONES.md`, lo medido en
`PASO0_CENSO.md`. Esto es cómo se ordena el sistema.

> **REGLA DE ESTE ARCHIVO, y nació de un defecto suyo.** Acá no se escribe
> ningún número que un script pueda medir. Este documento decía "los candados de
> salida son cuatro" y son diecisiete; antes había dicho siete herramientas en el
> diagrama y ocho en la tabla. **Los números se apuntan al script que los mide, no
> se copian.** Es la misma regla que ya rige para los temas de la FAQ y para el
> nombre del modelo, y este archivo es el tercer caso donde hizo falta.

---

## El principio

**El control está ANTES de que el modelo escriba, no después.**

Durante meses el diseño fue el contrario: el modelo escribía y once módulos lo
corregían —un juez, una red de verificadores, ocho guardas de salida—. Cada capa
juzgaba con evidencia distinta, y la que ganaba borraba a las otras. Lo medido en
producción el 1-ago: el juez declaró sin respaldo seis renglones que había
estampado el propio código. El problema no era que el modelo alucinara; era que
tres capas peleaban por la misma verdad.

El principio sigue siendo correcto. **Lo que hay que leer abajo es hasta dónde se
aplicó de verdad, porque no es lo que este archivo decía.**

---

## El turno, de punta a punta

```
webhook -> orchestrator -> hub_venta
                             |
       1. LLAMADA UNO  ------+  el modelo ve la charla + las herramientas
          "que buscar"        |  y devuelve tool calls. No traduce nada.
                              |
       2. PARALELO -----------+  asyncio.gather. Hasta 2 rondas: la segunda
          "todo junto"        |  solo para lo que desbloquea la primera.
                              |
       2-bis. REPOSICION -----+  el codigo COMPLETA lo que el modelo declaro y
          una puerta, en      |  no aplico, antes de redactar. Es UNA puerta,
          reposicion.py       |  `completar`, con las seis piezas adentro y el
                              |  orden de dependencia escrito. Ver mas abajo.
                              |
       3. LLAMADA DOS --------+  redacta con el JSON de resultados delante
          "redactar"          |
                              |
       4. SALIDA -------------+  los engranajes que tocan el texto DESPUES de
          los candados        |  que el modelo escribio. Cuantos son, y cuales
                              |  intervienen de verdad, lo mide el censo.
                              |
       5. CIERRE Y COBRO -----+  leads.py, la misma funcion de siempre
                              |
       6. MEMORIA ------------+  history, resumen, vistos, carrito, destinos
```

---

## Las herramientas

**Cuántas son NO se escribe acá.** Este archivo decía siete en el diagrama y ocho
en la tabla, y el 14-ago se midieron nueve: dos números viejos en el mismo
documento. El número lo mide `banco_pruebas/peso_del_turno.py` leyendo los moldes
vivos, y la tabla de abajo se lee como qué resuelve cada una, no como el censo.

`app/core/herramientas.py`. Molde Pydantic + una función determinista que ya
existía y estaba probada. La lógica no se reescribió: se le puso un molde adelante
y el esquema que ve el modelo se GENERA del molde, así no hay dos definiciones que
puedan divergir.

| herramienta | qué resuelve | de dónde sale el dato |
|---|---|---|
| `registrar_pedido` | DECLARA lo que entendió, antes de buscar | no toca la fuente; es lo que el reconciliador compara contra lo que pidió |
| `buscar_productos` | identidad y catálogo | certificador + catálogo Firestore |
| `consultar_catalogo` | contar, extremos, qué valores existen | catálogo entero, recorrido por código |
| `ficha_producto` | la ficha completa por id | catálogo + specs + compatibilidad |
| `consultar_temas` | qué dice la casa de cada tema | FAQ curada con sus valores estampados **+** criterio y movida de `base_conocimiento.json` |
| `cotizar_envio` | costo a un destino | tabla de tarifas + geo de códigos postales |
| `armar_presupuesto` | LA CUENTA | calculadora; devuelve el bloque ya escrito |
| `ver_compatibilidad` | si sirve para su equipo | tabla de compatibilidad |
| `tomar_pedido` | decisión de compra y cobro | marca el cierre; trae los datos de pago |

**Cuatro de ellas leen el MISMO catálogo cambiando la proyección**
—`buscar_productos`, `consultar_catalogo`, `ficha_producto` y
`ver_compatibilidad`—. Eso no es capacidad repetida por accidente: es la misma
puerta abierta cuatro veces, y el modelo tiene que elegir cuál.

---

## Lo que sigue atado, y es lo único que hace falta atar

1. **La identidad la decide el código.** Regla cero del proyecto.
   `certificar_producto` devuelve encontrado, ambiguo o no_encontrado. Con ambiguo
   el modelo está obligado a preguntar; no puede elegir.
2. **Los enums salen de la fuente viva.** `categoria`, `temas` y los `campo` de
   los filtros se inyectan en el esquema desde el catálogo y la FAQ. El modelo no
   puede pedir una categoría que no vendemos, ni un tema de política que no
   existe, ni filtrar por un campo que la fuente no tiene.
2-bis. **Los atributos se CONSULTAN, no se razonan.** `buscar_productos` recibe
   `filtros` estructurados —campo, operador, valor— sobre los campos reales del
   catálogo, columnas y `specs`. Antes el modelo recibía tres fichas y tenía que
   deducir de la prosa cuál era blanco o cuál pesaba menos: eso es adivinar con el
   dato cargado al lado. Si la ficha no dice, el filtro devuelve "no se sabe", que
   no es lo mismo que "no".
3. **La plata la arma el código.** `armar_presupuesto` devuelve el presupuesto
   renglón por renglón. El modelo lo pega, no lo recompone. Es la única parte del
   mensaje que el modelo no redacta.

---

## La etapa de SALIDA — lo que este archivo decía mal

**Lo que decía hasta el 21-ago:** *"Son cuatro y ninguno reescribe prosa: borran
lo que no puede salir"*, y que el juez, la red de verificadores y las ocho guardas
se habían borrado el 2-ago.

**Lo medido** (`banco_pruebas/peso_del_censo.py`, los 15 casetes reproducidos por
el camino vivo, 54 turnos, offline):

- La etapa de salida tiene **diecisiete** nodos, no cuatro.
- **Varios sí reescriben prosa**: `_bloque_entero_o_repuesto`,
  `_punto_omitido_repuesto`, `_sin_titulos_huerfanos`.
- **Ocho de los diecisiete no intervinieron nunca** en 54 turnos.

El juez y las once guardas se borraron de verdad. Y después **volvieron a crecer
con otros nombres.** La enfermedad que este documento describía como curada es la
que el sistema tiene: trece pasadas encadenadas sobre el mismo texto, ninguna
sabiendo lo que hicieron las otras.

Eso no es una opinión de estilo, tiene dos víctimas registradas en `PENDIENTE.md`:
arreglar la plata rompió el título huérfano, y un candado de descuento nuevo cortó
un renglón de pago e inventó un precio. **Un diseño con trece escritores del mismo
texto garantiza que arreglar una cosa rompa otra.**

Los números por nodo están en `PASO0_CENSO.md` y se vuelven a sacar corriendo el
censo. Acá no se copian.

### Lo que sí borran, y hay que conservar

De los diecisiete, lo que importa que exista es esto, y no depende de cuántas
funciones lo implementen:

- **Plata inventada.** Todo monto del texto tiene que estar en lo que trajeron las
  herramientas, o en el presupuesto de un turno anterior, que también lo calculó
  el código. Ve la plata con signo y sin signo, y no confunde una spec con un
  monto.
- **Cobro inventado.** Un CBU, alias, titular o banco que no coincida con la
  config de la tienda no sale. Nació de que el modelo se inventó un CBU de 22
  dígitos en una charla viva.
- **JSON filtrado.** El volcado crudo de una herramienta no es parte del mensaje.
- **Honestidad de bot y saludo inicial.** Lo único que no puede depender del
  prompt: si preguntan si es una máquina, se dice la verdad, y el primer mensaje
  avisa que es un asistente automático.

**Cuidado con el atajo.** Que un nodo no haya intervenido en 54 turnos prueba que
**estas charlas no lo ejercitan**, no que sobre. `sin_cobro_inventado` protege
algo que importa y nació de un incidente real. Lo que corresponde no es borrarlo a
ciegas: es ejercitarlo —para eso entraron los guiones 26 a 38— y después decidir.

---

## La etapa de REPOSICIÓN — una puerta, en `app/core/reposicion.py`

Entre la llamada uno y la redacción hay **una función, `completar`, que aplica lo
que el modelo declaró y no aplicó**. Adentro corren seis piezas, en el orden de
la dependencia, y ese orden está escrito arriba de ellas: hasta la FICHA 11 eran
seis funciones sueltas en `hub_venta` y el orden vivía en cinco comentarios de
`procesar_venta`.

```
1. _busqueda_de_lo_declarado      4. _reparto_de_pago_declarado
2. _condicion_faltante_aplicada   5. _supuesto_de_pago
3. _cuenta_con_lo_declarado       6. _bloques_a_uno
```

Cada una sigue pasando por `G.paso_datos`, así que se sigue midiendo cuál
intervino y `peso_reposicion.py` ve el mismo detalle que veía con seis nodos.

Lo que hacen, dicho sin eufemismo: **el código no confía en la interpretación y la
vuelve a hacer.** Cuánto intervienen es, literalmente, la medida de cuán robusta
es la interpretación en la práctica, y hasta el 18-ago nadie la había medido. Los
números los saca `banco_pruebas/peso_reposicion.py`.

El más grande no es una guardia: es **la resolución del punto `precio` puesta
después de que el modelo escribió**. Corrige al modelo en una fracción muy alta de
los turnos, y eso significa que está en la etapa equivocada, no que haga falta.

### Por qué existe

La llamada uno hace **dos trabajos a la vez**: declarar qué entendió, y elegir qué
herramientas llamar. El primero anda bien. El segundo falla en más de la mitad de
los turnos —el reconciliador reclama porque lo declarado y lo buscado no
coinciden— y `_busqueda_de_lo_declarado` existe **únicamente para parchear esa
diferencia después de que ocurrió**.

---

## Los contratos, en dos familias

El turno está declarado nodo por nodo en `app/verifika/grafo.py`, y cada nodo dice
qué propiedades mecánicas cumple. Son propiedades que se comprueban **sin saber
cuál era la respuesta correcta**, que es la única forma de correrlas sobre entradas
generadas.

- **Los de TEXTO**, para los nodos de salida: no enmudece, no inventa plata,
  idempotente, no levanta.
- **Los de DATOS**, para la mitad que decide y repone: no inventa id, no pierde
  evidencia, no agrega lo no pedido, no reclama lo ya resuelto, más idempotente y
  no levanta.

Un nodo sin contrato tiene que declarar POR QUÉ. El candado está en
`tests/test_barrido_decision.py` y no deja entrar un nodo nuevo sin contrato ni
motivo.

### El agujero del instrumento, tapado el 21-ago

**Las seis etapas registran: los treinta y dos nodos declarados dejan marca.**
Hasta el 21-ago registraban diecisiete, todos de salida, porque el único que
llamaba a `registrar()` era `G.paso` y `G.paso` envuelve transformaciones de
TEXTO: **el instrumento era ciego justo en la etapa donde estaba el problema**, y
por eso la reposición hubo que medirla envolviéndola a mano desde afuera.

Lo que había que resolver para taparlo es que un nodo que NO transforma texto no
se puede medir comparando lo que entró contra lo que salió, así que **hay que
decir qué significa que intervino, nodo por nodo**. Se contesta de dos formas y
ninguna le pregunta al nodo:

- `G.paso_datos` para el que recibe un estado y devuelve el estado nuevo —las
  seis reposiciones—: intervino si el estado cambió, comparado serializado. Es
  la regla de `G.paso` un piso más arriba.
- `G.veredicto` para el que produce algo que no es su propia entrada —el estado
  inicial, el decisor, el redactor, el cierre, el guardado—: el criterio se
  escribe en una línea al lado de la llamada, a la vista de quien audita.

Ninguna de las dos cambia comportamiento, y `paso_datos` **re-levanta** la
excepción en vez de tragarla: tragarla es lo correcto en `G.paso`, donde cumple
`no_enmudece`, y sería inventar un camino nuevo acá.

**Lo que hace confiable la medición nueva es que coincide con la vieja:**
`cuenta_repuesta` interviene en el 44% de los turnos, el mismo número que
`peso_reposicion.py` había sacado el 18-ago envolviendo la función desde afuera.
Dos instrumentos independientes sobre las mismas quince charlas.

---

## Hacia dónde va el turno

Decidido en la conversación de arquitectura del 18 y 19 de agosto; las cuarenta
decisiones con su motivo están en `DECISIONES.md`. El resumen en cinco líneas:

```
1. INTERPRETAR   la llamada uno SOLO declara. El codigo deriva que buscar.
                 Nadie corrige la declaracion: no hay dos versiones de la
                 intencion, asi que no queda nada que reconciliar.

2. CONTRATO      el turno se descompone en PUNTOS, y no sale hasta que cada
                 punto tenga un estado terminal: RESUELTO, AMBIGUO (repregunta),
                 NO SE SABE, o CONFLICTO. `indice_turno` ya lo calcula y hoy
                 el resultado se tira en una linea de log.

3. RESOLVER      una sola puerta de busqueda, no cuatro proyecciones del mismo
                 catalogo. Devuelve candidatos, por que califica cada uno, y
                 que NO se pudo saber. La cuenta se resuelve ACA.

4. REDACTAR      un solo escritor. El modelo recibe el contrato ya resuelto y
                 escribe una vez. Despues NO se toca el texto.

5. VERIFICAR     invariantes booleanos, nunca mutacion. Si uno se viola, se
                 rechaza y se vuelve a redactar UNA vez con la violacion como
                 aviso; si falla otra vez, sale un texto determinista.
```

Y las dos propiedades que reemplazan a los diecisiete candados, las dos medidas
sobre el texto que ve el cliente:

- **COBERTURA** — todo punto del contrato tiene renglón en el texto. Mata la
  omisión.
- **PROCEDENCIA** — todo dato del texto viene de un punto resuelto. Mata la
  invención.

La regla que protege la venta, y va en la arquitectura desde el día uno: **un
punto sin resolver bloquea su renglón, nunca el turno.** Máximo una repregunta por
turno, y solo sobre lo que bloquea el cobro.

---

## Qué NO existe más, y por qué

- **El intérprete.** Traducía el mensaje a una taxonomía nuestra de veinte campos
  con un vocabulario de 116 términos. Se caía por JSON truncado, y cuando se caía
  todo lo de abajo trabajaba a ciegas. El modelo ya entiende la charla: no hace
  falta que la traduzca a nuestro diccionario, hace falta que pida datos.
- **El solver de fragmentos y su render.** El modelo emitía fragmentos atados a
  enums y el código los estampaba. El render descartaba lo que no encajaba: en un
  turno real quedaron seis de ocho preguntas sin contestar.
- **El juez y la red de verificadores.** Corregían al modelo después de escribir,
  con evidencia distinta a la suya. Borraban dato real. **Ojo: se borraron, y la
  forma volvió** —ver la sección de salida—. Borrar una capa no alcanza si el
  diseño sigue permitiendo que crezca otra igual con otro nombre.
- **Los detectores** de stock contradicho y promesas prohibidas siguen vivos, pero
  en `banco_pruebas/detectores.py`: son instrumentos para MEDIR una corrida, no
  capas del bot.

---

## Multi-tenant

`tienda_id` lo resuelve el backend por `phone_number_id`, nunca el modelo. Viaja
por contextvar a todas las herramientas. Cada tienda tiene su catálogo, su FAQ,
sus tarifas y sus datos de cobro. **Eso está bien resuelto.**

Lo que todavía no lo está, y es lo que separa un producto de un motor: **el código
tiene política de UNA tienda adentro.** Los descuentos, los umbrales, el reparto de
pago y la prosa de venta viven en Python, no en la fuente. Y los prompts también.

La regla objetivo es una sola: **el motor no puede contener ni un dato ni una
política de ninguna tienda.** El semáforo que la vuelve verificable está en
`DECISIONES.md`: una segunda tienda de otro rubro adentro del repo, y un test que
falla si `app/` menciona el `tienda_id` de la primera.
