# FICHA 36 — El número. Una sesión.

Tercer tercio de `PLAN_REDUCCION.md`. La 35 ya está en `origin/main`
(`8bbe0e1`): un mutador en higiene, aduana fuera de `app/`, piso sin bajar.
Esta sesión cierra la campaña. Los dos termómetros tienen que pasar.

No se junta con otra ficha. No se “mejoran” las herramientas que quedan.
No se arregla el razonamiento del bot. Eso es la campaña de después, cuando
Martín mire producción. Acá se saca de `app/` lo que ya no es el vivo.

Si el piso baja, revert del corte, no un parche.

---

## Qué hay hoy, leído del vivo post-35

Los números los saca `tests/test_plan_de_la_reduccion.py` leyendo `app/`.
No se copian acá. El objetivo está clavado: **181 funciones, 7306 líneas**.
El 25% es piso si entra solo, no vara para forzar.

`_CUERPOS` sigue con nueve nombres. El modelo solo ve `registrar_pedido`
(FICHA 06). El código elige entre las otras ocho. Los tests 31 y 32 ya
están escritos: una puerta al catálogo, una a la plata.

`reposicion.py` sigue en `app/`. El resolver y la salida llaman helpers:
`_producto_para`, `_buscar_certificando`, `_cuenta_con_lo_declarado`,
`_reparto_de_pago_declarado`, `_supuesto_de_pago`, `_bloques_a_uno`,
`_bloque_presupuesto`. El hub solo pide `_bloque_presupuesto`. El snapshot
de la 34 es el archivo de entonces; antes de borrar el vivo de ahora, hay
que copiar **este**.

`guia_pedido.py` no es el camino del turno. El vivo le pide
`categorias_nombradas` y `opciones_por_categoria`. El resto es el camino
sellado del 8-jul.

`calc_defensiva.py` lo usa la calculadora. `huecos.py` lo usan filtros y
herramientas. `indice.py` lo usan `main.py` (inventario) y `leads.py`.
No se borran para que un número baje.

---

## Qué se hace, en este orden, en UNA sesión

### 1. Snapshot al archivo, ANTES de tocar el vivo

```
cp app/core/reposicion.py archivo/reposicion_vivo_20260828.py
```

El de la 34 (`reposicion_20260827.py`) es el de antes del nexo. Este es el
que todavía corre. Fila nueva en `archivo/README.md`.

Si esta sesión apaga `guia_pedido.py` entero, el snapshot va **antes** del
`git rm`, con su fila. `app/` no importa `archivo/`.

### 2. `reposicion.py` sale de `app/`

Los helpers de arriba se MUDAN al resolver o a un módulo chico que ya
quede, no se copian. El hub y la salida dejan de importar `reposicion`.
Si nadie en `app/` llama el archivo: `git rm app/core/reposicion.py` en el
mismo commit. Copiar y dejar el original no achica.

Los tests que importan `app.core.reposicion` se reapuntan al dueño nuevo
en ese commit. `banco_pruebas/peso_reposicion.py` igual.

### 3. Nueve cuerpos a cuatro

En `_CUERPOS` quedan, y son estas cuatro:

- `registrar_pedido` — lo único que ve el modelo
- `consultar_productos` — una puerta al catálogo, con proyección
- `cotizar` — una puerta a la plata (envio y presupuesto)
- `consultar_temas` — la FAQ

`tomar_pedido` se borra. No queda “por si acaso”. La señal de cobro ya
sale por `camino_cobro`.

`buscar_productos`, `consultar_catalogo`, `ficha_producto` y
`ver_compatibilidad` dejan de ser cuatro cuerpos. Compatibilidad no se
apaga: se pide por proyección, no por otra puerta.

El barrido `tests/test_barrido_herramientas.py` afirma
`len(B.herramientas()) == 9`. Se reapunta en el **mismo** commit a 4.
La cobertura no baja: barre las cuatro que quedan, no las nueve que
eran. El generador de entradas lee los moldes vivos.

Marcas que se sacan cuando pasan:

- `test_el_catalogo_tiene_una_sola_puerta_interna`
- `test_la_plata_tiene_una_sola_puerta_interna`

### 4. Lo que nadie llama, sale

`guia_pedido.py`: se extraen `categorias_nombradas` y
`opciones_por_categoria` al módulo que ya las necesita (pedido_helpers o
filtros). El resto, snapshot y `git rm`.

`calc_defensiva.py` y `huecos.py` se quedan mientras la calculadora y
los filtros los llamen. `indice.py` se queda mientras `main` y `leads`
lo llamen. “Si gana `indice_turno`” no es borrar el inventario del admin.

`test_nada_suelto.py` sigue: función sin caller o va a `archivo/` o se
borra. No se suma a `DECLARADAS` para tapar.

El grafo se queda en los nodos del turno nuevo. Un nodo declarado que ya
no corre se saca en el mismo commit, con la cuenta del censo escrita.

### 5. El árbol, no `app/`

Fichas 01 a 21 cerradas y `banco_pruebas/corridas/` (markdown de corridas
viejas) no deployan y le comen contexto a cada chat. Salen del árbol si
ningún candado los lee. Git los guarda. Si un test se pone rojo porque
buscaba ese archivo, se deja: no se gasta la sesión en prosa.

Esto **no mueve** los termómetros. Se hace después de que `app/` ya esté
en camino al 30%, no en lugar de cortar el vivo.

### 6. Los termómetros tienen que pasar

```
python3 -m pytest -q
```

Sacarles la marca:

- `test_app_tiene_a_lo_sumo_ciento_ochenta_funciones`
- `test_app_pesa_a_lo_sumo_siete_mil_trescientas_lineas`

Y las de 31 y 32 si el paso 3 las puso verdes.

Al sacar marcas, `tests/plan_techo.json` baja en ese cierre, un entero
por test, con la cuenta escrita. Hoy está en 17. El techo **solo baja**.
No se sube. No se mueve el objetivo 181 / 7306.

El piso de `banco_pruebas/casetes/_piso.json` no baja. Si baja,
`git revert` del commit del corte. El snapshot en `archivo/` se queda.

Prioridad uno manda: si para llegar al número hay que sacar
certificación, calculadora o el contrato, el corte está mal y se
revierte. El 25% (151 / 6089) es piso si el corte lo da, no una vara.

El que implementa no reescribe la vara.

### 7. Push a `main`

Toca `app/`: deploya. Pedir el OK una vez, al final, con la lista de
archivos. Nada de ramas. El hook las bloquea.

Árbol limpio y fast-forward posible al abrir: `git pull --ff-only origin
main` y seguí. Parar solo si está sucio, hay commits locales que no
están en origin, o no hay fast-forward.

---

## Qué NO se toca en esta ficha

- El razonamiento del bot. Los errores de la prosa se miran **después**,
  cuando Martín vea producción con la reducción encima.
- “Optimizar” las cuatro herramientas que queden. Fusionar puertas no es
  retocar el match ni el ranking. Eso es la campaña siguiente.
- `data/clientes/`. La segunda tienda de otro rubro es el semáforo del
  motor (FICHA 25) y se hace **después** de esta, para no copiar fugas y
  porque Martín quiere ver si producción sigue igual.
- `requirements.txt`, la clave paga, Mercado Pago.
- Subir `plan_techo.json`. Reescribir un test para que pase.
- FICHA 24 y 29. Siguen sin test propio.
- Procedencia, plata sellada, cobro, saludo, punto omitido, `componer`.
  La 35 los dejó. No se borran para que un número baje.
- Verificar producción por WhatsApp. Lo mira Martín al cerrar la campaña.

La cola de la 11 (`test_la_cuenta_se_arma_antes_del_reconciliador` y
hermanas) no se trabaja de memoria. Si al cortar un xfail pasa solo
(XPASS), se le saca la marca. No se fuerza.

---

## Cómo se vuelve atrás

Un commit de corte. `git revert` de ese commit. El snapshot en `archivo/`
no se borra al revertir.

---

## Bloque para pegar al abrir ESTA sesión

```
Repo: github.com/martinrf79/Verifika, rama main.
git fetch origin main && git checkout main && git status.
Si HEAD no es origin/main: árbol limpio y fast-forward posible →
git pull --ff-only origin main y seguí. Si el árbol está sucio, hay
commits locales que no están en origin, o no hay fast-forward: PARÁ y avisá.
Leé SOLO: ARRANQUE.md, arquitectura/PLAN_REDUCCION.md,
arquitectura/FICHA_36_el_numero.md, DECISIONES.md.
Corré pytest -q.
Prioridad uno: el bot vende y no alucina. Si no sabe, lo dice o repregunta.
ESTA SESIÓN ES LA FICHA 36, tercer tercio de PLAN_REDUCCION. Nada más.
Snapshot a archivo/ ANTES de tocar el vivo.
reposicion.py sale de app/ cuando nadie la llama. Nueve cuerpos a cuatro.
Los termómetros 181 funciones y 7306 líneas tienen que pasar.
No se toca el razonamiento. No se optimizan las herramientas que quedan.
No se toca data/clientes. Si el piso baja, revert.
PUSHEÁ a main. Toca app/: pedí el OK del push una vez, al final.
Nada de ramas.
```
