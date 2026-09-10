> # ⚠️ ESTE DOCUMENTO TENIA RAZON, Y NADIE LO ESTABA LEYENDO
>
> Escrito el **17-ago-2026**. El **18-ago** se volvio a medir todo desde cero con
> `banco_pruebas/peso_del_censo.py`, sin haberlo leido, y dio **lo mismo**: las
> piezas de salida que reescriben el mensaje, las que no intervienen nunca, y que
> son el juez y la red de verificadores renacidos con otros nombres.
>
> **Mientras tanto `ARQUITECTURA.md` afirmaba lo contrario** —"los candados son
> cuatro y ninguno reescribe prosa"— y era el documento que se leia.
>
> La leccion no es sobre este archivo. Es sobre el repo: **el analisis estaba
> hecho, escrito y era correcto. Lo que faltaba era una forma de saber cual de
> los dos documentos mandaba.** Por eso ahora `ARQUITECTURA.md` esta reescrito
> con lo medido, los numeros no se copian entre documentos, y lo decidido vive en
> un solo lugar.
>
> ## Como se lee este archivo hoy
>
> | documento | que manda |
> |---|---|
> | `PASO0_CENSO.md` | los NUMEROS medidos, y como volver a sacarlos |
> | `DECISIONES.md` | QUE se decidio hacer, y por que |
> | **este archivo** | **COMO se hace, en que orden, y que absorbe cada pieza** |
> | `ARQUITECTURA.md` | como esta ordenado el sistema hoy |
>
> ## Lo que cambio despues del 18 y 19 de agosto
>
> Cuatro puntos. En los cuatro, lo de abajo sigue siendo valido como paso
> intermedio; lo de aca es el destino.
>
> **1. La llamada uno deja de elegir herramientas.** Este plan fusiona nueve
> herramientas en cuatro, y esta bien. Pero se midio despues que **en el 57% de
> los turnos el modelo declara algo que no busca**: el problema no es cuantas
> puertas hay, es que el modelo elige la puerta. El destino es que la llamada uno
> **solo declare** y el codigo derive las busquedas. Con eso, el paso 3 de este
> plan —"lo que el modelo declaro y no busco, lo busca el codigo"— deja de ser una
> funcion de completado y pasa a ser el camino normal, y el reconciliador no puede
> tener faltantes porque no queda nada que reconciliar.
>
> **2. El enum de temas.** Este plan lo saca y lo resuelve por codigo contra las
> 738 señas. Con el punto 1 hecho, el problema desaparece solo: `consultar_temas`
> deja de ser una herramienta que el modelo ve, asi que su enum no viaja. **No
> hace falta el texto libre ni el prefiltro**, que era superficie nueva.
>
> **3. La cobertura sube de categoria.** Este plan la deja como una funcion
> `cobertura(declarado, material)` que corre una vez y se pega al prompt, y su
> pasada final solo como metrica de log. Se decidio ir mas lejos: **el contrato
> del turno**, con cada punto en uno de cuatro estados terminales —RESUELTO,
> AMBIGUO que obliga a repreguntar, NO SE SABE, CONFLICTO— y el turno no sale con
> un punto sin estado. Motivo medido: `indice_turno` solo abre SEIS tipos de punto
> y los seis salen de `registrar_pedido`, asi que **una pregunta informativa no
> abre ningun punto** y la cobertura es ciega justo donde mas se alucina. Faltan
> cuatro tipos: atributo, stock, compatibilidad y politica.
>
> **4. Una diferencia de criterio, y queda escrita como diferencia.** Este plan
> dice: *"los invariantes vuelven a ser instrumento y salen del camino vivo"*.
> Tiene razon en lo que le preocupa —ya se habia decidido el 2-ago con los
> detectores y volvieron a entrar por la aduana— y el motivo es correcto: **una
> capa que CORRIGE despues de escrito es un juez, y los jueces costaron meses.**
>
> La decision del 19-ago es que un invariante puede quedarse en el camino vivo
> **con una condicion que lo hace otra cosa: no toca el texto.** Devuelve si o no.
> Si dice que no, no se parchea el mensaje: **se rechaza y se vuelve a redactar
> una vez**, y si vuelve a fallar sale un texto determinista. Un juez opina sobre
> la prosa; una puerta solo la deja pasar o no. Lo que este plan prohibe con razon
> —y la decision tambien prohibe— es que una pieza reescriba lo que el modelo
> escribio.
>
> ---

# PLAN DE RECORTE — de 17 piezas a 3, de 9 herramientas a 4, de 4 llamadas a 2

Documento de diseño. No es estado: el estado vive en `PENDIENTE.md` y en
`git log`. Esto es qué hay que hacer y en qué orden.

Todo lo que sigue está MEDIDO sobre el código vivo, no estimado. Los números
salen de `banco_pruebas/peso_del_turno.py`, `banco_pruebas/peso_de_la_cadena.py`
y la batería corrida el 17-ago.

---

## EL DIAGNÓSTICO, EN CUATRO NÚMEROS

1. **17 piezas reescriben el mensaje después de que el modelo lo escribió, y 10
   no intervienen ni una vez sobre el corpus.** Es el juez y la red de
   verificadores que se borraron el 2-ago, vueltos a nacer adentro del hub como
   funciones privadas `_sin_algo`. Misma clase de código, dirección nueva.
2. **El esquema de las herramientas es la enorme mayoría del peso del turno.**
   `consultar_temas` sola pesa un tercio por su enum de temas. `tomar_pedido` no
   se llamó una sola vez en los turnos grabados. Los números exactos los mide
   `peso_del_turno.py`; no se copian acá.
3. **De 2 a 4 llamadas al modelo por turno**, y cada ronda extra vuelve a pagar
   el esquema entero. La latencia medida en producción es de 21 a 26 segundos.
4. **`hub_venta.py` pasa de las tres mil líneas y unas 50 funciones privadas.** El
   turno es una función imperativa larga, así que las costuras entre piezas no se
   pueden enumerar, y lo que no se enumera se descubre cuando revienta.

**Lo que NO es el problema, y conviene decirlo:** la interpretación está bien y
está medida. `interpretacion.py` da entiende 94 y contesta 94, y el barrido de
lo que el modelo declara cubre el 100% de su superficie. La premisa de la que
parte este plan es correcta.

**Lo que tampoco es el problema:** los barridos y la batería de tests. Eso no es
sobreingeniería, es lo único que hace que este recorte se pueda hacer sin fe.

---

## LA REDUNDANCIA, CONTADA

Una propiedad, muchas implementaciones. Esto es la sobreingeniería, con nombre:

- **La repetición** la persiguen unas 14 funciones repartidas en `mensaje.py`,
  `aduana.py`, `invariantes.py` y el hub.
- **El título sin lista abajo** lo persiguen 4, una en cada uno de los mismos
  cuatro módulos.
- **La etiqueta interna fugada** la persiguen 5.
- **La plata inventada** la persiguen unas 8.
- **Si el punto del cliente llegó a la respuesta** se pregunta 4 veces por
  turno: el reconciliador contra las llamadas, el índice contra el material, el
  índice otra vez contra el texto final, y la reposición del punto omitido.

---

## EL SISTEMA OBJETIVO

Seis pasos, dos llamadas al modelo, cuatro herramientas, tres candados.

```
mensaje
   |
   1. INTERPRETAR ..... LLAMADA UNO. El modelo declara el pedido y pide datos.
   |                    Temperatura 0. Una sola tanda, sin rondas.
   2. EJECUTAR ........ las herramientas en paralelo. asyncio.gather.
   |
   3. COMPLETAR ....... lo que el modelo declaró y no buscó, lo busca el código.
   |                    Una función, no seis. Acá muere la ronda dos.
   4. REDACTAR ........ LLAMADA DOS. El modelo escribe con el JSON delante y con
   |                    la lista de puntos sin contestar pegada al prompt.
   5. PODAR ........... tres candados. Ninguno reescribe: borran lo que no cierra.
   |
   6. GUARDAR ......... memoria, cierre y cobro. Lo que ya hay.
```

**Por qué esto controla la alucinación antes y no después.** Los pasos 3 y 4 son
el control real: lo que la herramienta no trajo no está en el JSON, y lo que no
está en el JSON el modelo no lo tiene. El paso 5 no juzga ni corrige: borra lo
que no se puede probar contra el material del turno. Un candado que reescribe
prosa es un juez, y los jueces ya nos costaron meses.

---

## PASO 1 — DOS LLAMADAS FIJAS. Se saca el bucle de rondas

`_MAX_RONDAS = 4` se va. El único motivo real por el que existe la ronda dos es
que para armar el presupuesto hacen falta los ids y los ids los trae otra
herramienta. **Eso es trabajo de código, no de modelo, y ya está escrito:**
`_cuenta_con_lo_declarado` arma la cuenta con lo declarado sin preguntarle nada
al modelo. La ronda dos le paga al modelo por hacer lo que el código ya hace.

Qué se gana, medido: la latencia baja a la mitad, el techo diario de llamadas se
duplica, y desaparece el caso del 5-ago en que el modelo desalentado por
"si podés contestar no pidas nada más" no pedía nada y el turno moría en el
muro que el reconciliador acababa de detectar.

Qué se arriesga: el encadenado profundo que hoy hace el modelo. Se mide con las
15 charlas grabadas y el piso antes de cerrar el paso; si el número cae, el
faltante se cubre en `completar` con código, no devolviéndole la vuelta al
modelo.

---

## PASO 2 — NUEVE HERRAMIENTAS A CUATRO

Se fusiona por lo que CONSUME cada una, no por lo que significa.

| queda | absorbe | por qué |
|---|---|---|
| `registrar_pedido` | — | es el contrato de interpretación y la entrada de todos los controles deterministas. No se toca. |
| `consultar_productos` | `buscar_productos`, `consultar_catalogo`, `ficha_producto`, `ver_compatibilidad` | las cuatro leen el mismo catálogo y sólo cambian la proyección. Un campo `detalle` con lista, ficha, conteo o compatibilidad. |
| `consultar_temas` | — | queda, pero **el enum de temas se va**. Ver el punto 2 del encabezado: con la llamada uno solo declarando, esta herramienta deja de ser visible para el modelo y el enum no viaja. |
| `cotizar` | `cotizar_envio`, `armar_presupuesto` | cotizar un envío es un presupuesto con sólo envío. La calculadora ya lo calcula adentro. Una sola puerta a la plata. |

**`tomar_pedido` se borra.** Cero usos en los turnos grabados. La señal de compra
sale determinista del mensaje y del carrito con `_RE_PIDE_COBRO`, que ya existe y
ya se usa en `_cerrar`.

El beneficio grande no es el peso: es que **el modelo deja de elegir por cuál de
las cuatro puertas del catálogo entra.** Esa elección es superficie de
alucinación sin ninguna ganancia, y está medida: el reconciliador reclama en más
de la mitad de los turnos.

**Los enum de `categoria` y de `campo` NO se tocan.** No están por peso: son la
atadura que impide nombrar una categoría que no vendemos.

---

## PASO 3 — DIECISIETE PIEZAS A TRES

La regla para que una pieza sobreviva, y es una sola: **tiene que impedir una
mentira falsificable o cumplir una obligación, y tiene que poder probarlo contra
datos que el turno ya tiene.** Todo lo que juzga estilo, largo o repetición
después de escrito, se va.

**C1. LA PLATA.** Todo peso del texto viene de lo que calculó el código o la
oración se poda, y el bloque de la cuenta se pega entero. Absorbe
`_sin_plata_inventada`, `_cuenta_no_retipeada`, `_bloque_entero_o_repuesto`,
`plata_inventada` de herramientas y tres invariantes de cuenta.

**C2. EL DATO ATADO.** `atadura_prosa` ya hace lo correcto: el redactor envuelve
cada dato concreto con el id de donde salió, el código lo contrasta contra el
material del turno, borra lo que no cierra y saca las etiquetas. **Este es el
candado general contra la alucinación** y absorbe siete piezas: afirmar sobre el
catálogo, negar lo traído, descuento inventado, cobro inventado —un CBU es un
dato con fuente, la config de la tienda—, JSON filtrado, id interno y narración
interna.

> **C2 ES LA PROPIEDAD DE PROCEDENCIA.** Vale la pena decirlo con el nombre que
> tiene en `DECISIONES.md`, porque son la misma cosa vista dos veces: *todo dato
> del texto viene de un punto resuelto*. Y su gemela, la COBERTURA —*todo punto
> abierto tiene renglón en el texto*— es el paso 4 de abajo. **Las dos juntas
> reemplazan a los diecisiete candados**, y las dos se comprueban sin saber cuál
> era la respuesta correcta.

**C3. LA OBLIGACIÓN.** Honestidad de bot y aviso de asistente automático en el
primer mensaje. Dos funciones. No pueden depender del prompt y no dependen.

**Más una pasada de higiene, que no es un candado:** `componer` baja de 10
reglas a las 2 que se disparan de verdad —el renglón idéntico dos veces en el
mismo mensaje, y el bloque idéntico al mensaje anterior—. `aduana.py`
desaparece como capa: sus tres reparaciones ya están en C1, C2 y la higiene, y
su parte de gritar lo que no puede reparar queda como una línea de log en la
misma pasada.

**Los invariantes vuelven a ser instrumento y salen del camino vivo.** Ya se
había decidido eso el 2-ago con los detectores; volvieron a entrar por la
aduana. Miden una corrida, no son una capa del bot. *(Ver el punto 4 del
encabezado: la decisión del 19-ago los deja como PUERTA booleana —rechazar y
reescribir— pero nunca como reparación. El principio de este párrafo se
respeta: ninguna pieza reescribe lo que el modelo escribió.)*

**Ojo con las que no intervienen nunca sobre el corpus.** No están muertas: el
corpus no tenía un CBU falso ni un "sos un bot". Antes de borrar una, se le
agrega el caso que la despierta y se mira si sigue haciendo falta. Este es el
riesgo real del recorte y por eso este paso va tercero, no primero. **Los
guiones 26 a 38 se escribieron para eso**: cada uno despierta a una de las
dormidas.

---

## PASO 4 — CUATRO PASADAS DE COBERTURA A UNA

Queda `cobertura(declarado, material)` corriendo una vez, antes de redactar, y
su salida se pega al prompt de la llamada dos. Cuesta cero latencia porque va en
una llamada que ya se iba a hacer.

La pasada sobre el texto final se conserva **sólo como métrica de log**, nunca
como reparación: es la regla de juzgar por lo observado. `_punto_omitido_repuesto`
se borra, que es la única guardia que suma texto después de escrito.

Las seis reposiciones deterministas del hub se juntan en una función
`completar(declarado, llamadas)` con un orden de dependencia explícito.

> **Y acá se agrega lo que el 18-ago mostró que falta.** `indice_turno.puntos`
> abre **seis** tipos —item, condicion, destino, duda, pago, precio— y los seis
> salen de los campos de `registrar_pedido`. **No hay tipo para ATRIBUTO, STOCK,
> COMPATIBILIDAD ni POLITICA**, así que si el cliente pregunta cuántos Hz tiene un
> monitor **no se abre ningún punto** y la cobertura no lo ve. El porcentaje de
> puntos sin contestar que mide el censo es, por eso, un PISO y no el número
> real. Los cuatro tipos que faltan salen solos de la fuente: atributo de los
> campos del catálogo, política de los temas de la FAQ.

---

## PASO 5 — EL HUB, A UNAS 400 LÍNEAS

Con los pasos 1 a 4 hechos, `procesar_venta` queda en seis llamadas a seis
funciones con nombre. El grafo de `app/verifika/grafo.py` deja de declarar
veintipico de nodos y declara seis, así que el barrido de la decisión se achica
solo y los contratos se cobran donde importa.

**Y el grafo pasa a registrar en las seis etapas, no solo en salida.** Hoy
declara treinta y dos nodos y `G.paso` —el único que llama a `registrar()`— solo
envuelve transformaciones de texto, así que el instrumento es ciego justo en la
etapa de reposición. Por eso hubo que medirla envolviéndola a mano.

---

## PASO 6 — REAPUNTAR LOS INSTRUMENTOS

Los barridos de piezas borradas se borran con ellas. Los de propiedad
—identidad, filtros, specs, memoria, código de la cuenta, herramientas—
sobreviven y se achican a 4 herramientas. Se regenera `INVENTARIO_BARRIDO.md` y
se vuelve a fijar el piso. Sin esto el paso 3 no se puede cerrar con confianza.

---

## LA PORTABILIDAD A OTRO CATÁLOGO

Objetivo: una tienda nueva es una carpeta con catálogo, FAQ, tarifas, datos de
cobro y voz, y cero líneas de código. Con las 4 herramientas leyendo sólo de ahí,
falta poco. Lo que hoy sigue clavado en código y hay que sacar:

- `_INSTRUCCION_UNO` y `_INSTRUCCION_DOS`. Estaban como decisión pendiente de
  Martín; el 19-ago **dejó de ser opcional**: un prompt en el código es una tienda
  adentro del motor.
- `geo_cp`, que es de Argentina. Se vuelve tabla por tienda, no módulo.
- **La política de negocio**: descuentos, umbrales y reparto de pago viven hoy en
  Python. Es la fuga cara, la que no se arregla moviendo un archivo.

**El semáforo** que convierte esto en verificable, y sin él lo de arriba es una
promesa: una segunda tienda de otro rubro adentro del repo, 20 productos, y dos
tests —que `app/` no mencione el `tienda_id` de la primera, y que la tienda cero
conteste sus charlas sin tocar una línea de Python—. **Se hace PRIMERO, aunque
falle**: lo que se rompe es la lista de fugas real, medida y no supuesta.

---

## EL ORDEN Y POR QUÉ ESE ORDEN

1. Sacar el bucle de rondas. Ganancia grande, riesgo chico, reversible con git.
2. Fusionar herramientas. Ganancia grande, riesgo medio, cubierto por el barrido
   de herramientas que hoy da 100%.
3. Recortar los candados. Riesgo alto, va después de tener las dos ganancias
   guardadas y con los casos que despiertan a los dormidos escritos primero.
4. Unificar cobertura. Riesgo bajo.
5. Achicar el hub. Es consecuencia de los anteriores, no trabajo aparte.
6. Reapuntar instrumentos y volver a fijar el piso.

**LA REGLA DEL CORTE, y sale de lo medido:** las piezas están acopladas, así que
dentro de un paso **se cortan JUNTAS, no de a una**. Cortarlas de a una hace que
cada corte perturbe a las otras, y ya pasó dos veces: arreglar la plata rompió el
título huérfano, y un candado de descuento nuevo cortó un renglón de pago e
inventó un precio.

Y su contracara: **si después de cortar no hay que reponer nada, se cortó poco.**
Son 23 piezas entre salida y reposición; reponer dos o tres es la señal de que el
corte fue del tamaño correcto.

Cada paso deploya solo y ninguno queda detrás de un flag apagado. La red es el
revert, como siempre.
