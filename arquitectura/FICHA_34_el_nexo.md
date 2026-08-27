# FICHA 34 — El nexo. Una sesión.

Primer tercio de `PLAN_REDUCCION.md`. Esta ficha reemplaza a las 31, 32 y 33
como **próximo trabajo**. Esas tres siguen en pytest: si este corte las pone
verdes de yapa, se les saca la marca en el mismo commit. Si no, quedan para
después. No se implementan aparte.

No se toca el turno a medias. O el hub deja de llamar al reconciliador y a la
reposición, o no se pushea.

---

## Qué se hace, en este orden, en UNA sesión

### 1. Snapshot al archivo, ANTES de tocar el vivo

```
cp app/core/reposicion.py archivo/reposicion_20260827.py
```

Del reconciliador no se copia `pedido.py` entero: ese archivo tiene funciones
vivas. Se copia la función `reconciliar` y `instruccion_de_preguntas` a
`archivo/reconciliador_20260827.py`, con un comentario arriba que dice de qué
commit salió. Se agrega la fila en `archivo/README.md`.

`app/` no importa `archivo/`. El candado `tests/test_archivo.py` ya está.

### 2. Nace `app/core/resolver.py`

Una función, este contrato:

```
def resolver(declarado, memoria, tienda_id, trace_id) -> dict
```

Devuelve `{"llamadas": ..., "contrato": ..., "bloque": ...}`.

Adentro, en este orden, y es el de la dependencia:

1. Buscar cada item y cada stock del `declarado`, certificando ids. Hoy vive
   en `hub_venta._derivar_las_busquedas`. Se MUEVE, no se duplica.
2. Traer ficha, temas, compatibilidad y envío, igual que hoy deriva esa
   función. Siguen siendo llamadas a funciones de `herramientas.py`. No se
   inventa un molde nuevo en esta ficha.
3. Armar la cuenta SI el declarado pide precio, o hay items con cantidad, o
   hay destinos. Hoy eso lo hace `reposicion._cuenta_con_lo_declarado` cuando
   el reconciliador dice `falta_la_cuenta`. Acá la condición sale del
   **declarado**, no de un reclamo. Es la decisión 8.
4. `indice_turno.cobertura` sobre ese material. El dict `contrato` es esa
   salida: puntos con estado.

En el mismo commit del primer snapshot, agregar `archivo/` a `.gcloudignore`
y `archivo/**` a `paths-ignore` de `deploy.yml`. El candado
`test_el_archivo_no_entra_a_la_imagen` lo pide en cuanto hay un `.py` acá.

No llama a `pedido.reconciliar`. No llama a `reposicion.completar`.

### 3. `procesar_venta` queda en seis pasos

Después de `registrar_pedido`:

1. Interpretar — ya está, llamada uno.
2. `out = resolver(...)`
3. Redactar con `out["contrato"]` y `out["bloque"]` delante. El JSON crudo de
   las llamadas puede viajar como respaldo, no como única evidencia.
4. Salida — **en esta ficha no se recorta**. Las dieciocho piezas siguen.
   Eso es la sesión siguiente, FICHA 35, escrita abajo.
5. Guardar — no se toca.

Se borran de `procesar_venta` las llamadas a `P.reconciliar` y `R.completar`.
Si `_derivar_las_busquedas` quedó vacía, se borra del hub.

### 4. Verificar, y si el piso baja se revierte entero

```
python3 -m pytest -q
```

Tienen que pasar, y hay que sacarles la marca:

- `test_el_hub_no_llama_a_reconciliar`
- `test_el_hub_no_llama_a_completar_de_reposicion`

El piso de `banco_pruebas/casetes/_piso.json` no baja. Si baja, `git revert`
del commit del corte, no un parche. El snapshot en `archivo/` se queda: no
es el camino vivo.

El barrido de la decisión (`test_barrido_decision.py`) se reapunta en el
mismo commit: los nodos `reconciliador` y las seis reposiciones o salen del
grafo o se declaran como internas del resolver. No se deja un nodo declarado
que ya no corre.

### 5. Push a `main`

Toca `app/`: deploya. Pedir el OK una vez, al final, con la lista de archivos.
Nada de ramas.

---

## Qué NO se toca en esta ficha

`salida.py`, `aduana.py`, `mensaje.py`, `data/clientes/`, la clave paga,
Mercado Pago, fusionar los nueve `_CUERPOS`. El redactor puede seguir viendo
herramientas internamente. El nexo es que el hub no tenga dos opiniones sobre
el pedido.

---

## FICHA 35 — la sesión de después, no esta

Cuando 34 esté en `origin/main` y el piso no haya bajado: la higiene deja un
solo mutador (`test_la_higiene_tiene_un_solo_mutador`, ya escrito) y la aduana
pasa a `archivo/` como snapshot. La prosa no se reescribe. Solo se pega
`out["bloque"]` y se corta lo que no está en el contrato.

No se hace en la misma sesión que la 34. Son dos cortes, cada uno revertible.

---

## Bloque para pegar al abrir ESTA sesión

```
Repo: github.com/martinrf79/Verifika, rama main.
git fetch && git status. Si HEAD no es origin/main, PARÁ y avisá.
Leé SOLO: ARRANQUE.md, arquitectura/FICHA_34_el_nexo.md, DECISIONES.md.
Corré pytest -q.
Esta sesión hace la FICHA 34 y nada más. Snapshot a archivo/ ANTES de
tocar el vivo. El hub deja de llamar a reconciliar y a completar.
Si el piso baja, revert del corte, no un parche.
PUSHEÁ a main al cerrar. Toca app/: pedí el OK del push una vez, al final.
```
