# FICHA 30 — La simplificación de verdad

Esta es la orden de trabajo de la campaña. **Una sesión nueva lee esto, corre
`pytest`, y hace UNA de las fichas 31, 32 o 33.** No relee PLAN_RECORTE.md ni
PENDIENTE.md para saber qué hacer: esos documentos explican el porqué; este
dice qué se hace ahora.

Si algo de acá choca con una ficha vieja, gana esto. El recorte del 17-ago
tenía razón y se ejecutó como agrupamiento. Agrupar sin borrar es cómo el repo
llegó a veinticuatro mil líneas con las mismas nueve herramientas adentro.

---

## El diagnóstico, medido el 27-ago sobre `main`

No se copian números que un script puede volver a sacar. Se apunta al script.

| qué | dónde se mide | qué significa |
|---|---|---|
| cuánto pesa `app/` | `wc -l` sobre `app/**/*.py` | el producto vivo, no el banco |
| cuántas herramientas internas | `len(herramientas._CUERPOS)` | nueve cuerpos, el modelo ve uno |
| cuántos barridos hay y su cobertura | `INVENTARIO_BARRIDO.md`, generado | doce, varios al 100% |
| cuánto falta del recorte | `pytest` → marcas `PLAN:` | el número, no esta tabla |
| qué quedó a medias | `pytest` → marcas `A MEDIAS:` | tiene que llegar a cero |

**Lo que está grande no es el catálogo ni los tests. Es que una propiedad tiene
varias implementaciones, y el turno las corre a todas.**

Cuatro puertas leen el mismo catálogo: `buscar_productos`, `consultar_catalogo`,
`ficha_producto`, `ver_compatibilidad`. El modelo ya no las ve —FICHA 06, el
23-ago—, pero el código sigue eligiendo entre las cuatro en
`hub_venta._derivar_las_busquedas`. Esa elección es superficie de alucinación
sin ganancia, y está medida: en el 57% de los turnos lo declarado y lo buscado
no coincidían. Esconder la herramienta no fusiona la herramienta.

Tres puertas tocan la plata: `cotizar_envio`, `armar_presupuesto`,
`tomar_pedido`. La calculadora ya calcula adentro. `tomar_pedido` no se llamó
en los turnos grabados cuando el modelo elegía; hoy el código todavía la tiene
en `_CUERPOS`.

La repetición la persiguen `mensaje.py`, `aduana.py` e `invariantes.py` a la
vez. `salida.higiene` llama a `componer` y después a `revisar_salida`, que
también reescribe. Dos mutadores del mismo texto, uno atrás del otro, es la
forma exacta de los dos bugs de plata de agosto: arreglar una cosa rompe la
otra.

Las diecisiete piezas de salida siguen vivas adentro de cuatro funciones. FICHA
10 cortó las costuras del hub, no las piezas. El veredicto por engranaje se
conservó a propósito, y eso está bien. Lo que no está bien es que cada pieza
siga siendo un escritor del mensaje.

**Lo que NO es el problema, y no se toca para “achicar”:**

- Los doce barridos. Son lo único que deja cortar sin fe. Un corte que no
  reapunta su barrido en el mismo commit no se pushea.
- `banco_pruebas/` y `reserva/`. No deployan. Están en `.gcloudignore` y en
  `paths-ignore` de `deploy.yml`.
- La interpretación. Está medida y anda. No se reescribe.
- `data/clientes/`. Un solo catálogo, una sola FAQ.

---

## El sistema objetivo, en una pantalla

```
mensaje
   |
   1. INTERPRETAR ..... el modelo declara. Ve UNA herramienta.
   2. RESOLVER ........ el codigo deriva y ejecuta CUATRO cuerpos:
   |                    registrar_pedido, consultar_productos,
   |                    consultar_temas, cotizar.
   3. REDACTAR ........ el modelo escribe una vez, con el JSON delante.
   4. PODAR ........... tres candados que no reescriben. La higiene saca
   |                    repeticion con UNA funcion, no con tres.
   5. GUARDAR ......... memoria, cierre y cobro. Lo que ya hay.
```

Cuatro herramientas internas, no nueve. Una implementación por propiedad, no
catorce. El modelo sigue sin elegir: eso ya está hecho y no se revierte.

---

## Cómo se trabaja, para que no haya teléfono descompuesto

Esto es lo que trabó el proyecto: una sesión escribe un plan en una rama o en
un chat, la siguiente lee `main` y dice que no existe. Pasó el 3-ago y volvió
a pasar con el chat de Cursor que no aterrizó en `main`.

1. **Se trabaja en `main`.** Este repo bloquea `git checkout -b`. Una rama
   paralela, para el proyecto, no existe.
2. **Una ficha, una sesión, y se pushea al cerrar.** Lo que no está en
   `origin/main` no existe para el chat siguiente.
3. **El que implementa no reescribe la vara.** Los tres pasos de abajo ya
   están en `tests/test_plan_de_la_simplificacion.py`. Se ponen en verde. No se
   edita el assert para que pase.
4. **El corte se hace JUNTO adentro de la ficha, no de a una pieza.** Cortar
   `ficha_producto` y dejar `consultar_catalogo` es el recorte que ya se hizo y
   no achicó nada.
5. **El barrido se reapunta en el mismo commit que el corte.** Hoy
   `test_barrido_herramientas.py` afirma `len(herramientas()) == 9`. El día que
   bajen a cuatro, ese nueve se cambia en el mismo push, con el requisito
   nuevo escrito en el commit, no “para que pase”.
6. **No se agrega una guardia nueva mientras se está cortando.** Las fichas
   26, 27 y 28 ensanchan guardias que ya existen: se pueden hacer, pero no en
   la misma sesión que fusiona herramientas.
7. **No se toca `data/clientes/` ni `requirements.txt`.**
8. **Push a `main` deploya** si el commit toca `app/`. Estas tres fichas tocan
   `app/`. Pedir el OK una vez, al final, mostrando qué archivos y que el
   gate de `pytest` está verde.

---

## Lo que hace CADA chat, y nada más

### FICHA 31 — el catálogo tiene una sola puerta interna

**Test:** `test_el_catalogo_tiene_una_sola_puerta_interna`

**Qué se hace.** Los cuatro cuerpos que leen el catálogo se fusionan en
`consultar_productos`, con un campo de proyección: lista, ficha, conteo o
compatibilidad. `_derivar_las_busquedas` llama a esa sola. Los moldes viejos
salen de `_MOLDES` y de `_CUERPOS`. No se saca capacidad: se saca la elección.

**Qué NO se toca.** `registrar_pedido`, `consultar_temas`, la calculadora, la
salida, los prompts, la fuente.

**Cómo se verifica.** El test pasa. El barrido de herramientas sigue al 100%
sobre la superficie nueva. El barrido de identidad, el de filtros, el de
specs y el de compatibilidad no bajan. El piso de las 15 charlas no baja.
`pytest -q` verde, techo PLAN baja de 14 a 13, se saca la marca `xfail`.

**Cómo se vuelve atrás.** `git revert` del commit. No hay flag.

---

### FICHA 32 — la plata tiene una sola puerta interna

**Test:** `test_la_plata_tiene_una_sola_puerta_interna`

**Qué se hace.** `cotizar_envio` y `armar_presupuesto` se fusionan en
`cotizar`. `tomar_pedido` se borra: la señal de cobro ya sale por
`camino_cobro` y `_RE_PIDE_COBRO`. Una sola puerta a la plata.

**Prerrequisito.** La 31 cerrada, o esta sesión hace las dos juntas si entra.
No deja `tomar_pedido` “por si acaso”.

**Qué NO se toca.** El catálogo, la salida, Mercado Pago, el CBU, la clave
paga.

**Cómo se verifica.** El test pasa. El barrido del código de la cuenta
(`test_barrido_codigo.py`) no baja de combinaciones. El piso no baja. Techo
PLAN baja uno.

---

### FICHA 33 — la higiene tiene un solo mutador

**Test:** `test_la_higiene_tiene_un_solo_mutador`

**Qué se hace.** `salida.higiene` deja de llamar a `aduana.revisar_salida`
como reescritura. La aduana, si queda, es log: mira y no toca el texto. La
repetición la saca `mensaje.componer` nomás. Los invariantes vuelven a ser
instrumento —sí o no, nunca parche— como ya se había decidido el 2-ago y el
19-ago.

**Antes de borrar una pieza que da 0 de 54.** No se borra a ciegas. Se le
agrega el caso que la despierta, o se deja como log. Los guiones 26 a 38
siguen sin grabar y necesitan la clave paga: no bloquean esta ficha si el
caso se planta en un test, que es lo que hizo la FICHA 20.

**Qué NO se toca.** Las herramientas, el hub salvo el import, la fuente.

**Cómo se verifica.** El test pasa. El barrido del código de la cuenta sigue
verde. Ningún casete muda. Techo PLAN baja uno.

---

## Lo que NO se hace en esta campaña

- Reescribir `indice_turno.py` ni `hub_venta.py` “para que quede lindo”. El
  hub se achica solo cuando las 31 y 32 ya no lo obligan a despachar nueve
  nombres. Si después de las tres fichas el hub sigue pasando las mil
  líneas, eso es una ficha nueva con su test, no un extra de esta.
- Crear la segunda tienda, grabar casetes con la clave paga, ni inventar un
  número de venta. Eso ya está en el plan viejo, con sus tests. Se hace
  DESPUÉS, sobre el sistema más chico.
- FICHA 24 y FICHA 29. Están nombradas en `ARRANQUE.md` y **no tienen test**.
  Un paso sin test no se trabaja: o se escribe el `xfail` en una sesión de
  diseño, o se saca el número. No se implementa de memoria.
- Integrar Mercado Pago. No es un pendiente.
- Pedir la clave paga. La 31, 32 y 33 corren offline.

---

## El bloque para pegar al abrir el chat que implementa

```
Repo: github.com/martinrf79/Verifika, rama main.
git fetch && git status. Si HEAD no es origin/main, PARÁ y avisá.
Leé SOLO: ARRANQUE.md, arquitectura/FICHA_30_la_simplificacion.md,
DECISIONES.md. Corré pytest -q y anotá los dos techos.
Esta sesión hace UNA ficha: la primera de 31, 32, 33 que pytest -rx
muestre todavía en PLAN. No toques las otras.
El que implementa no reescribe la vara. El barrido se reapunta en el
mismo commit que el corte.
PUSHEÁ a main al cerrar. Si el commit toca app/, pedí el OK del push
una vez, al final. No dejes el trabajo en una rama.
```

---

## Qué pasa con los once PLAN que ya estaban

Siguen contando. No se tiran. Son otra cola: bugs y semáforo del motor, no
tamaño. Las fichas 26, 27 y 28 ensanchan guardias ya existentes y no suman
herramientas: si Martín está viendo esas alucinaciones en real, se pueden
hacer ANTES que la 31. Si no, la 31 va primero, porque cada guardia nueva
sobre dieciocho piezas es cómo se hinchó el repo.

La cola de la 11, la 22, la 23 y la 25 se hacen sobre el sistema ya fusionado.
Fusionar no las cierra y no las empeora: cambia nombres de herramienta, y esos
nombres hay que actualizarlos en el mismo commit.
