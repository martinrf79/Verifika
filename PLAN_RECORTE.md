# PLAN DE RECORTE — de 17 piezas a 3, de 9 herramientas a 4, de 4 llamadas a 2

Documento de diseño. No es estado: el estado vive en `PENDIENTE.md` y en
`git log`. Esto es qué hay que hacer y en qué orden.

Todo lo que sigue está MEDIDO sobre el código vivo, no estimado. Los números
salen de `banco_pruebas/peso_del_turno.py`, `banco_pruebas/peso_de_la_cadena.py`
y la batería de 940 tests corrida el 17-ago.

---

## EL DIAGNÓSTICO, EN CUATRO NÚMEROS

1. **17 piezas reescriben el mensaje después de que el modelo lo escribió, y 10
   no intervienen ni una vez sobre el corpus.** Es el juez y la red de
   verificadores que se borraron el 2-ago, vueltos a nacer adentro del hub como
   funciones privadas `_sin_algo`. Misma clase de código, dirección nueva.
2. **25.370 bytes de esquema viajan al modelo, el 92% del turno.**
   `consultar_temas` sola pesa 8.042 por su enum de 129 temas. `tomar_pedido`
   pesa 565 y no se llamó una sola vez en 55 turnos grabados.
3. **De 2 a 4 llamadas al modelo por turno**, y cada ronda extra vuelve a pagar
   los 25.370 bytes enteros. La latencia medida en producción es de 21 a 26
   segundos.
4. **`hub_venta.py` tiene 3.141 líneas y unas 50 funciones privadas.** El turno
   es una función imperativa larga, así que las costuras entre piezas no se
   pueden enumerar, y lo que no se enumera se descubre cuando revienta.

**Lo que NO es el problema, y conviene decirlo:** la interpretación está bien y
está medida. `interpretacion.py` da entiende 94 y contesta 94, y el barrido de
lo que el modelo declara cubre el 100% de su superficie. La premisa de la que
parte este plan es correcta.

**Lo que tampoco es el problema:** los 12 barridos y los 940 tests. Eso no es
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
| `consultar_temas` | — | queda, pero **el enum de 129 temas se va**. Tema en texto libre, resuelto por código contra las 738 señas de la fuente, con log cada vez. |
| `cotizar` | `cotizar_envio`, `armar_presupuesto` | cotizar un envío es un presupuesto con sólo envío. La calculadora ya lo calcula adentro. Una sola puerta a la plata. |

**`tomar_pedido` se borra.** Cero usos en 55 turnos. La señal de compra sale
determinista del mensaje y del carrito con `_RE_PIDE_COBRO`, que ya existe y ya
se usa en `_cerrar`.

Peso esperado: de 25.370 a unos 9.000 bytes. Y el beneficio grande no es el
peso: es que el modelo deja de elegir por cuál de las cuatro puertas del
catálogo entra. Esa elección es superficie de alucinación sin ninguna ganancia.

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
aduana. Miden una corrida, no son una capa del bot.

**Ojo con las 10 que no intervienen nunca sobre el corpus.** No están muertas:
el corpus no tiene un CBU falso ni un "sos un bot". Antes de borrar una, se le
agrega el caso que la despierta y se mira si sigue haciendo falta. Este es el
riesgo real del recorte y por eso este paso va tercero, no primero.

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

---

## PASO 5 — EL HUB, DE 3.141 LÍNEAS A UNAS 400

Con los pasos 1 a 4 hechos, `procesar_venta` queda en seis llamadas a seis
funciones con nombre. El grafo de `app/verifika/grafo.py` deja de declarar
veintipico de nodos y declara seis, así que el barrido de la decisión se achica
solo y los contratos se cobran donde importa.

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

- `_INSTRUCCION_UNO` y `_INSTRUCCION_DOS`, que ya están declaradas como decisión
  pendiente de Martín.
- `geo_cp`, que es de Argentina. Se vuelve tabla por tienda, no módulo.

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

Cada paso deploya solo y ninguno queda detrás de un flag apagado. La red es el
revert, como siempre.
