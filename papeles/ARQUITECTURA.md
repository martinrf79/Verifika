# Arquitectura de Verifika — el turno, de punta a punta

> **PUERTA ÚNICA: el bloque 0 de `CLAUDE.md`.** Se entra por ahí.
>
> **Y ESTE MAPA QUEDÓ ATRÁS DEL CÓDIGO (3-sep-2026).** El diagrama de abajo
> entra por `hub_venta` y sus cuatro puertas de salida. Ese camino **se apagó**
> el 3-sep a `archivo/plomeria_apagada/` —commit `f6de0c5`—: el turno vivo hoy
> es `app/core/turno.py` sobre la mesa de `app/core/tabla.py`, en seis pasos.
> Lo que sigue valiendo entero es **el principio** y **el reparto de quién
> decide qué**; lo que no vale es el cableado dibujado. Reescribirlo es trabajo
> propio y todavía no se hizo. Mientras tanto: **el camino vivo se lee de
> `app/core/`, no de acá.**

Mapa de referencia permanente. El estado del día vive en
`RESUMEN_PARA_NUEVO_CHAT.md`, lo decidido en `DECISIONES.md`. Los números
del censo salen de `banco_pruebas/peso_del_censo.py` y el candado está en
`tests/test_censo_del_grafo.py`. Esto es cómo se ordena el sistema.

> **REGLA DE ESTE ARCHIVO, y nació de un defecto suyo.** Acá no se escribe
> ningún número que un script pueda medir. Los nodos declarados viven en
> `app/verifika/grafo.py` (`NODOS`). Las piezas internas de cada puerta están
> nombradas ahí, en el campo `piezas` de ese Nodo. Los cuerpos que despacha el
> código viven en `app/core/herramientas._CUERPOS`. El modelo ve `_VISIBLES`.
> Los nombres viejos los traduce `_ALIAS`.

---

## El principio

**El control está ANTES de que el modelo escriba, no después.**

Durante meses el diseño fue el contrario: el modelo escribía y once módulos lo
corregían —un juez, una red de verificadores, ocho guardas de salida—. Cada capa
juzgaba con evidencia distinta, y la que ganaba borraba a las otras. Lo medido en
producción el 1-ago: el juez declaró sin respaldo seis renglones que había
estampado el propio código. El problema no era que el modelo alucinara; era que
tres capas peleaban por la misma verdad.

El principio sigue siendo correcto. Lo de abajo es el camino vivo, no el de
agosto.

---

## El turno, de punta a punta

```
webhook -> orchestrator -> hub_venta
                             |
       1. LLAMADA UNO  ------+  el modelo ve registrar_pedido y DECLARA.
          "que entendio"      |  No elige que buscar.
                              |
       2. RESOLVER -----------+  el codigo deriva las busquedas, arma la
          "una sola opinion"  |  cuenta, cierra el contrato. indice_turno
                              |  marca cada punto. Ver grafo.py.
                              |
       3. LLAMADA DOS --------+  redacta UNA vez con el material delante
          "redactar"          |
                              |
       4. SALIDA -------------+  cuatro puertas: procedencia, plata,
          procedencia, plata, |  obligacion, higiene. Las piezas de
          obligacion, higiene |  adentro estan nombradas en grafo.py.
                              |
       5. CIERRE Y COBRO -----+  leads.py
                              |
       6. MEMORIA ------------+  history, resumen, vistos, carrito, destinos
```

---

## Las herramientas

El modelo ve `registrar_pedido`. El código deriva el resto. Qué cuerpos
despacha el vivo y con qué nombres viejos se traducen no se copia acá: está
en `_CUERPOS` y `_ALIAS` de `app/core/herramientas.py`.

`app/core/herramientas.py`. Molde Pydantic + una función determinista que ya
existía y estaba probada. El esquema que ve el modelo se GENERA del molde, así
no hay dos definiciones que puedan divergir.

### Lo que sigue atado, y es lo único que hace falta atar

1. **La identidad la decide el código.** Regla cero del proyecto.
   `certificar_producto` devuelve encontrado, ambiguo o no_encontrado. Con ambiguo
   el modelo está obligado a preguntar; no puede elegir.
2. **Los enums salen de la fuente viva.** `categoria`, `temas` y los `campo` de
   los filtros se inyectan en el esquema desde el catálogo y la FAQ. El modelo no
   puede pedir una categoría que no vendemos, ni un tema de política que no
   existe, ni filtrar por un campo que la fuente no tiene.
2-bis. **Los atributos se CONSULTAN, no se razonan.** Las condiciones van en
   filtros estructurados sobre los campos reales del catálogo. Si la ficha no
   dice, el filtro devuelve "no se sabe", que no es lo mismo que "no".
3. **La plata la arma el código.** El presupuesto vuelve renglón por renglón.
   El modelo lo pega, no lo recompone. Es la única parte del mensaje que el
   modelo no redacta.

---

## La etapa de SALIDA — cuatro puertas

Cada puerta contesta UNA pregunta sobre el mensaje, y adentro corre sus piezas
en un orden fijo. Las piezas siguen registrando una por una: están nombradas
en `grafo.py`, campo `piezas` de cada Nodo. El barrido de
`tests/test_grafo_cableado.py` barre las puertas, no las piezas. Cuáles
intervienen de verdad lo mide `banco_pruebas/peso_del_censo.py`.

```
PROCEDENCIA  ¿de donde salio cada dato?      Lo que no viene del material
                                             del turno no sale.
PLATA        ¿quien calculo este numero?     La cuenta la arma el codigo y
                                             viaja entera. Ningun peso sin
                                             respaldo.
OBLIGACION   ¿que tiene que estar si o si?   Que es un bot, el saludo la
                                             primera vez, el punto que el
                                             cliente pregunto, como se paga.
                                             La UNICA que suma.
HIGIENE      ¿como se lee?                   Sin repetir. Un mutador: componer.
```

Tres restan y una suma, y ese reparto ordena el orden: primero se saca lo que
no puede estar, después se pone lo que falta, y al final se mira el mensaje
entero una sola vez.

El juez y las once guardas se borraron de verdad. La forma volvió con otros
nombres y se agrupó: las comprobaciones siguen, las costuras entre nodos sueltos
no. Un diseño con muchos escritores del mismo texto garantiza que arreglar una
cosa rompa otra; por eso el paso del turno son estas cuatro puertas y no una
fila de piezas reordenables.

### Lo que sí borran, y hay que conservar

No depende de cuántas funciones lo implementen:

- **Plata inventada.** Todo monto del texto tiene que estar en lo que trajeron las
  herramientas, o en el presupuesto de un turno anterior, que también lo calculó
  el código.
- **Cobro inventado.** Un CBU, alias, titular o banco que no coincida con la
  config de la tienda no sale. Nació de que el modelo se inventó un CBU de 22
  dígitos en una charla viva.
- **JSON filtrado.** El volcado crudo de una herramienta no es parte del mensaje.
- **Honestidad de bot y saludo inicial.** Lo único que no puede depender del
  prompt: si preguntan si es una máquina, se dice la verdad, y el primer mensaje
  avisa que es un asistente automático.

**Cuidado con el atajo.** Que una pieza no haya intervenido en el corpus prueba
que **estas charlas no la ejercitan**, no que sobre. Lo que corresponde no es
borrarla a ciegas: es ejercitarla y después decidir. Los nombres y las clases
salen del censo, no de acá.

---

## El nexo — resolver, no reposición

Entre la declaración y la redacción hay **una función, `resolver`**. Una sola
opinión sobre el pedido, desde lo declarado. El reconciliador no corre.
`reposicion.py` salió de `app/`.

Adentro el código deriva las búsquedas y arma la cuenta. Esas piezas registran
con su id propio: están nombradas en el Nodo `resolver` de `grafo.py`.
`busquedas_derivadas` es un nodo declarado, no una pieza huérfana.
`indice_turno` cierra los puntos; `puerta_cobertura` registra el veredicto
sobre el texto que el cliente va a leer, nombrada en ese Nodo.

La cuenta es la resolución del punto `precio` en la etapa de decisión, no un
parche de salida.

---

## Los contratos, en dos familias

El turno está declarado nodo por nodo en `app/verifika/grafo.py`, y cada nodo
dice qué propiedades mecánicas cumple. Son propiedades que se comprueban **sin
saber cuál era la respuesta correcta**, que es la única forma de correrlas sobre
entradas generadas.

- **Los de TEXTO**, para los nodos de salida: no enmudece, no inventa plata,
  idempotente, no levanta.
- **Los de DATOS**, para la mitad que decide: no inventa id, no pierde
  evidencia, no agrega lo no pedido, más idempotente y no levanta.

Un nodo sin contrato tiene que declarar POR QUÉ. El candado está en
`tests/test_barrido_decision.py` y no deja entrar un nodo nuevo sin contrato ni
motivo.

Las etapas registran. Un nodo que NO transforma texto no se puede medir
comparando lo que entró contra lo que salió, así que **hay que decir qué
significa que intervino, nodo por nodo**:

- `G.paso_datos` para el que recibe un estado y devuelve el estado nuevo:
  intervino si el estado cambió, comparado serializado.
- `G.veredicto` para el que produce algo que no es su propia entrada: el
  criterio se escribe en una línea al lado de la llamada.

Ninguna de las dos cambia comportamiento, y `paso_datos` **re-levanta** la
excepción en vez de tragarla: tragarla es lo correcto en `G.paso`, donde cumple
`no_enmudece`, y sería inventar un camino nuevo acá.

---

## Hacia dónde va el turno

Decidido en la conversación de arquitectura del 18 y 19 de agosto; las
decisiones con su motivo están en `DECISIONES.md`. Del cinco, el vivo ya hace
los cuatro primeros: la llamada uno solo declara, el contrato lo cierra
`indice_turno`, resolver es una sola opinión, el modelo redacta una vez y las
cuatro puertas verifican. Lo que sigue abierto —segunda redacción, cobertura y
procedencia como una sola vara— está en `PENDIENTE.md`, no acá.

Las dos propiedades que se miden sobre el texto que ve el cliente:

- **COBERTURA** — todo punto del contrato tiene renglón en el texto. Mata la
  omisión.
- **PROCEDENCIA** — todo dato del texto viene de un punto resuelto. Mata la
  invención.

La regla que protege la venta, y va en la arquitectura desde el día uno: **un
punto sin resolver bloquea su renglón, nunca el turno.** Máximo una repregunta
por turno, y solo sobre lo que bloquea el cobro.

---

## Qué NO existe más, y por qué

- **El intérprete.** Traducía el mensaje a una taxonomía nuestra de veinte campos
  con un vocabulario de 116 términos. Se caía por JSON truncado, y cuando se caía
  todo lo de abajo trabajaba a ciegas. El modelo ya entiende la charla: no hace
  falta que la traduzca a nuestro diccionario, hace falta que declare.
- **El solver de fragmentos y su render.** El modelo emitía fragmentos atados a
  enums y el código los estampaba. El render descartaba lo que no encajaba: en un
  turno real quedaron seis de ocho preguntas sin contestar.
- **El juez y la red de verificadores.** Corregían al modelo después de escribir,
  con evidencia distinta a la suya. Borraban dato real. **Ojo: se borraron, y la
  forma volvió** —ver la sección de salida—. Borrar una capa no alcanza si el
  diseño sigue permitiendo que crezca otra igual con otro nombre.
- **La reposición como etapa y el reconciliador.** El modelo declaraba una cosa
  y buscaba otra; el código reinterpretaba después. Eso salió: una sola opinión,
  desde lo declarado, en `resolver`.
- **Los detectores** de stock contradicho y promesas prohibidas siguen vivos, pero
  en `banco_pruebas/detectores.py`: son instrumentos para MEDIR una corrida, no
  capas del bot.
- **El hub y sus cuatro puertas de salida (3-sep-2026).** `hub_venta`, `salida`,
  `mensaje`, `indice_turno`, `grafo`, `atadura_prosa` e `invariantes` están en
  `archivo/plomeria_apagada/`. El turno pasó a `app/core/turno.py` sobre la mesa
  de `app/core/tabla.py`: el modelo llena un formulario con esquema JSON, una
  casilla por punto, y el código arma el mensaje. Todo el diagrama de arriba y
  la sección de las cuatro puertas describen el camino APAGADO.

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
