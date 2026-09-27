# FICHA 44 — Depósito del core y robustez a la vista

Esta es la orden de trabajo. No se borra nada. Lo que sobra se apaga y
va a `archivo/`. Lo que hoy le cuesta una venta al vivo se escribe como
test rojo y se cierra en la sesión que lo implemente.

Si algo de acá choca con `PLAN_REDUCCION.md` o con la FICHA 36, gana
esto: aquellas campañas ya cortaron el nexo, la puerta y las nueve
herramientas. El 30 por ciento de `app/` no se fuerza. Forzarlo saca
certificación, calculadora o el contrato.

Los números de tamaño los miden `tests/test_plan_de_la_reduccion.py` y
`banco_pruebas/peso_del_censo.py`. No se copian acá.

---

## Qué pide Martín, y cómo se cumple

1. Achicar el core, las funciones de más, lo duplicado.
2. No borrar: apagar y depositar.
3. Diagnosticar los errores que están a la vista.
4. Plan para que el sistema deje de perder ventas por un hueco conocido.

`archivo/` ya es el depósito. `reserva/` es otra cosa: capacidad
terminada que un día se enchufa. Acá no se mezcla.

Apagar es: snapshot con fecha en `archivo/`, fila en
`archivo/README.md`, el vivo deja de importar, `app/` no toca
`archivo/`. El código sigue en el repo. Git lo tiene. Si el piso de las
15 charlas baja, revert. El snapshot se queda.

---

## Dónde está el core hoy

Las fichas 31 a 36 ya hicieron el corte grande:

- una puerta al catálogo, una a la plata, el modelo ve una herramienta
- nexo en `resolver`, sin reconciliador ni reposición viva
- una higiene, un mutador: `componer`
- `reposicion.py`, `guia_pedido.py` y `aduana.py` ya están en `archivo/`

Los dos termómetros de la 36 siguen en rojo a propósito. El stay-list
del motor ya pesa más que el objetivo de aquella ficha. Prioridad uno
manda: no se recorta certificación, calculadora ni `indice_turno` para
que un número baje.

Lo que todavía infla `app/` y NO es el motor:

| qué | por qué está de más | a dónde va |
|---|---|---|
| las seis funciones viejas adentro de `herramientas.py` | `_CUERPOS` ya tiene cuatro; `consultar_productos` y `cotizar` delegan a las seis | snapshot de `herramientas.py`, después se achica el vivo |
| `invariantes.py` en `app/` | el vivo solo le pide dos helpers; el resto es termómetro | snapshot; los dos helpers a un módulo chico que ya quede |
| las reglas de `mensaje.py` que no dispara el corpus | `componer` corre una docena; el plan viejo pedía las dos que se disparan de verdad | no se apaga ninguna sin el caso que la despierta |
| `pedido.py` con el docstring del reconciliador | el reconciliador ya salió; quedan cuatro helpers vivos | no se mueve el archivo; se deja de contar como capa |
| `_norm` y `_money` repetidos | una propiedad, muchas copias; ya se pagó caro | una función, un módulo; no va a `archivo/` |
| `_bloque_hallazgo` en el hub | ida y vuelta con `salida.py`; ya es un PLAN | se muda cuando se decida de quién son los dos patrones |

Qué NO se apaga, aunque sea grande:

- `certificar_producto`, `filtros_catalogo`, `indice_turno`
- la calculadora y `calc_defensiva`
- las cuatro puertas de `salida.py` y sus piezas no auditadas
- webhooks, transcriber, leads, memoria, `llm_reintento`
- `grafo.py`: es el mapa, no el turno
- `coherencia_datos.py`: la usa el admin al subir catálogo
- `banco_pruebas/` y `reserva/`: no deployan

`test_nada_suelto.py` sigue: función sin caller o va a `archivo/` o se
borra. No se suma a `DECLARADAS` para tapar.

---

## Duplicados, con nombre

Una propiedad, una función. Hoy no es así.

**Identidad del texto.** `_norm`, `_n`, `_money`, `_normalizar` y
`_sin_acentos` están escritos en más de una docena de módulos de
`app/`. Cada copia puede diverger. El arreglo no es depositarlas: es
dejar una y llamar a esa.

**Catálogo.** Las cuatro proyecciones siguen siendo cuatro cuerpos
adentro del archivo, con dos wrappers encima. El modelo ya no elige.
El código tampoco debería elegir entre seis nombres.

**Plata.** `armar_presupuesto` y `cotizar_envio` siguen enteros.
`cotizar` es un if.

**Repetición.** La persiguen `mensaje.componer`, restos de
`invariantes` y piezas de `salida`. La higiene ya tiene un solo
mutador. Lo que queda es que `componer` no sea doce reglas de las
cuales el corpus no despierta la mitad.

**Contrato del turno.** `indice.py` e `indice_turno.py` no son el
mismo índice. El primero es inventario del admin. El segundo es el
contrato. No se fusionan.

---

## Diagnóstico: errores a la vista

Tres familias. La que manda es la que ya le costó una venta en
producción.

### A. Tres defectos del 2-sep que la batería offline no veía

Están en `PENDIENTE.md`. No tenían ficha ni test. Los tests de esta
ficha los cuentan.

**1. Una contradicción declarada no produce pregunta.**

Turno `4cb60031` de Telegram. El decisor escribió dos contradicciones
correctas. El índice las marcó `CONFLICTO`. Salieron en `sin_contestar`
y `sin_material`. El bot le mandó el mensaje al cliente sin preguntar
nada.

El índice ya sabe la regla: una contradicción termina `AMBIGUO` si el
turno preguntó, `CONFLICTO` si no. `_punto_omitido_repuesto` no suma
pregunta: pega material sellado de un punto que el sistema sabía
contestar. Un `CONFLICTO` no es omisión de dato, es falta de pregunta.
Nadie la escribe. Es código faltante, no fuente ni modelo. Es la falla
que más venta cuesta.

Test: `test_una_contradiccion_declarada_sale_con_pregunta`.

**2. Un pedido de producto entra como pregunta de política.**

Turno `b92cae87` de WhatsApp. "dame precio de una intermedia" se ruteó
a FAQ y matcheó `cuotas`, `cuotas_financiacion` y `envio_exterior`. Las
tres quedaron sin material.

Antes de tocar `certificar_temas` hay que medir si el arreglo es cortar
el ruteo o subir el umbral. El test planta la frase y exige que esas
tres políticas no se abran. Si el test nace verde, el defecto no entra
por esa puerta y hay que mirar `_derivar_las_busquedas`.

Test: `test_un_pedido_de_producto_no_abre_politica_de_pago`.

**3. Dos extremos sueltos siguen colapsando en el primero.**

Con el extremo declarado en el item ya se resuelve: lo cerró el parche
del 2-sep. Dos extremos que viajan solo en `restricciones`, sin item
que los nombre, se quedan con el primero. No hay a qué búsqueda
atarlos. Elegir uno es inventar. El arreglo honesto es no aplicar
ninguno y dejar el punto abierto, o preguntar. No desempatar.

Test: `test_dos_extremos_sueltos_no_eligen_el_primero`.

### B. Lo que ya está escrito como PLAN y todavía no se hizo

Siguen valiendo, en este orden cuando toque robustez:

- FICHA 23. El modo degradado tira la venta y al cliente: misma frase
  de "mucha demanda" aunque el carrito ya esté armado.
- FICHA 26. Un universal sobre el catálogo sale sin que ninguna
  herramienta lo haya mirado.
- FICHA 27. Hablar del cliente en tercera persona le llega al cliente.
- FICHA 28. Se anuncia precio, plazo o stock y no va el dato abajo.
- FICHA 25. La tienda cero. Semáforo del motor. Va después de ver
  producción con el depósito encima, no antes.

### C. Lo que no es un bug de código, y no se tapa con uno

- El campo `origen` del catálogo es prosa. "Las menos partes chinas
  posibles" no se puede filtrar ni ordenar. Decisión de fuente, de
  Martín.
- `villa, Buenos Aires` resuelve a un CP que el cliente no nombró.
  Daño chico. Se arregla en `geo_cp.resolver` cuando lo pida.
- Ante un tema `ambiguous` se sirven todos los candidatos. Pedirle al
  cliente que elija entre nombres del archivero está mal. Servir de
  más en un mensaje real ya hizo daño. Si Martín quiere la repregunta,
  es una línea. Si no, se sube el umbral de la seña.
- La segunda redacción de `DECISIONES.md` #5 son dos llamadas por
  turno. El piso las tiene clavadas en 2. Regrabar pide la clave paga.

### D. Lo que un 0 de 54 no prueba

`honestidad_bot` y `punto_omitido` corren en todos los turnos del
corpus y no intervienen. El corpus no dijo esas frases. No se
depositan a ciegas. FICHA 24: auditarlas como la 20, con frases
reales del defecto y frases legítimas que no se pueden tocar. Los
guiones 26 a 38 siguen sin grabar y necesitan la clave paga; no
bloquean la auditoría por unidad.

---

## Plan de robustez, en orden

La prioridad uno manda sobre el tamaño. Un core más chico que calla
una contradicción no es un core mejor.

### Sesión 45 — la contradicción pregunta

Una función, en la puerta de obligación. Si el índice tiene un punto
`contradicciones` en `CONFLICTO`, el texto que sale lleva UNA pregunta
sobre esa contradicción. Material sellado: la pregunta nombra el
hecho, no lo resuelve. Máximo una repregunta por turno, y esta gana
porque bloquea el cobro.

No se toca el redactor. No se le pide al modelo que se acuerde. El
índice ya decidió. La puerta escribe.

Si el piso baja, revert.

### Sesión 46 — el ruteo de la política

Primero se mide. El test de esta ficha es la vara. Si falla por
`certificar_temas`, se sube el umbral o se corta el ruteo a FAQ
cuando el declarado ya tiene items o `pide_precio`. Si pasa, el
defecto entra por `_derivar_las_busquedas` y se corta ahí.

No se toca la fuente. No se unen temas a mano.

### Sesión 47 — dos extremos sueltos

Si no hay item que nombre el extremo, no se aplica el del turno a
todas las búsquedas. El punto queda abierto. No se elige el primero.

`test_orden_dos_extremos.py` no se afloja. Esa vara ya cubre el caso
con el extremo en el item.

### Sesión 48 — depósito de la grasa, sin borrar

Snapshot de `herramientas.py` a `archivo/` ANTES de achicar el vivo.
Las seis funciones viejas dejan de ser el camino público. Los
wrappers dejan de ser un if que llama a otro nombre.

En la misma campaña, o en la siguiente si no entra: `invariantes.py`
sale de `app/` salvo los dos helpers que el vivo usa. Una sola
`_norm`. Una sola `_money`.

Los termómetros de la 36 no se sacan. Si al depositar pasan solos,
se les saca la marca. No se fuerza.

No se toca `data/clientes/`. No se pide la clave paga. No se
regraban casetes.

---

## Cómo se verifica, en cada sesión

1. `python3 -m pytest -q` verde. La marca `xfail` de lo que esa
   sesión cerró se saca, y el techo de `plan_techo.json` baja.
2. El piso de las 15 charlas no baja.
3. Los barridos de identidad, filtros, cuenta, FAQ y herramientas no
   pierden cobertura.
4. `app/` no importa `archivo/`.

El que implementa no reescribe la vara.

---

## Qué NO se hace en esta ficha

Esta ficha no toca `app/`. Es el diseño. Los tres tests nacen en
rojo. La implementación es la 45.

No se crea la segunda tienda. No se graban los guiones 26 a 38. No
se integra Mercado Pago. No se cambia el modelo. No se sube un
umbral para que un test pase.

---

## Bloque para pegar al abrir la sesión que implementa

```
Repo: github.com/martinrf79/Verifika, rama main.
git fetch origin main && git checkout main && git status.
Si HEAD no es origin/main: árbol limpio y fast-forward posible →
git pull --ff-only origin main y seguí. Si el árbol está sucio, hay
commits locales que no están en origin, o no hay fast-forward: PARÁ y avisá.
Leé SOLO: ARRANQUE.md, arquitectura/FICHA_44_deposito_y_robustez.md,
DECISIONES.md.
Corré pytest -q y anotá los dos techos.
Prioridad uno: el bot vende y no alucina. Si no sabe, lo dice o repregunta.
ESTA SESIÓN ES LA FICHA 45, la contradicción pregunta. Nada más.
No se deposita grasa en esta sesión. No se toca certificar_temas.
No se toca data/clientes. Si el piso baja, revert.
PUSHEÁ a main. Toca app/: pedí el OK del push una vez, al final.
Nada de ramas.
```
