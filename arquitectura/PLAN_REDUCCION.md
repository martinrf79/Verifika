# PLAN DE REDUCCIÓN — de 604 funciones a 181, de 24.355 líneas a 7.306

Medido el 27-ago-2026 sobre `origin/main`. Los números los saca
`tests/test_plan_de_la_reduccion.py` leyendo `app/`. No se copian a otro
documento para actualizarlos: si este archivo y el test dicen distinto, gana
el test.

**Prioridad uno, no se negocia.** El bot vende. No inventa. Si no sabe, lo
dice o repregunta. Una línea menos que haga alucinar o que calle un cierre
no es reducción: es un defecto. El revert es la red, no una disculpa para
cortar a ciegas.

---

## Qué hay hoy, medido

| superficie | funciones | líneas | ¿deploya? |
|---|---|---|---|
| `app/` | **604** | **24.355** | sí |
| `tests/` | 1.133 | 21.008 | no |
| `banco_pruebas/` | 468 | 15.037 | no |
| `scripts/` | 57 | — | no |

Las “más de quinientas” son `app/`: 604. Ahí está el producto. Tests y banco
pesan más en tokens de cada chat, pero no salen a Cloud Run. La reducción
seria es las dos: el vivo al 30%, y el árbol sin el muerto que ya no corre.

El 30% de `app/` es **181 funciones** y **7.306 líneas**. El 25% es 151 y
6.089: es el piso si al cortar entra, no la vara para forzar. Forzar el 25%
borra certificación o calculadora y el bot vuelve a inventar.

---

## Qué queda en producción. Lo imprescindible

Una sola frase: **WhatsApp entra, el modelo declara, el código resuelve contra
la fuente de esa tienda, el modelo redacta una vez, se cobra el lead, se
guarda.** Audio a texto entra como el mensaje. Telegram es la misma puerta.

Módulos que se quedan, aunque se achiquen por dentro:

- Conexión: `main.py` (webhooks), `connectors/whatsapp.py`, `telegram.py`,
  `orchestrator.py`
- Audio: `transcriber.py`
- Turno: `hub_venta.py` flaco, `resolver.py` (nace en la 34), `indice_turno.py`
  como contrato, `registrar_pedido` nada más visible al modelo
- Fuente: `fuente_producto.py`, `filtros_catalogo.py`, `certificar` /
  `pedido_helpers.py`, `compatibilidad.py`, `firestore_client.py`
- Plata: `calculadora.py`, `pago.py` como adaptador, `leads.py`, `cierre.py`
- Memoria: `estado_venta.py`, `memoria_larga.py`
- Modelo: `llm_adapter.py`, `llm_reintento.py`, `config.py`
- Voz de tienda: `guia_venta_prosa.py` leyendo la fuente, no inventando
- Una puerta de salida: plata sellada + cortar lo que no está en el contrato

Eso es el motor. Cabe en ~180 funciones si no se duplica `_norm`, `_money`,
ni cuatro puertas al mismo catálogo.

---

## Qué se apaga. Va a `archivo/`, no a `reserva/`

`reserva/` es código puro para enchufar después. Esto se apaga para borrar
cuando el piso aguante. Snapshot **antes** de sacar del vivo. `app/` no
importa `archivo/`. Si después del corte nadie en `app/` llama el módulo,
`git rm` del vivo en el mismo commit. Copiar y dejar el original no achica.

| sale de `app/` | por qué está de más | sesión |
|---|---|---|
| `reposicion.py` (945 líneas, 6 re-interpretaciones) | el resolver ya aplica el declarado | 34 |
| `pedido.reconciliar` | segunda opinión sobre el mismo pedido | 34 |
| cinco cuerpos extra de `herramientas.py` | el catálogo y la plata no necesitan nueve puertas | 34–36 |
| `salida.py` salvo la puerta | dieciocho escritores del mismo texto | 35 |
| `mensaje.py` salvo dos reglas de `componer` | la repetición se persigue en tres módulos | 35 |
| `aduana.py` | muta después de escrito | 35 |
| `invariantes.py` en el vivo | el banco los puede seguir usando | 35 |
| `guia_pedido.py` | camino sellado, no es el vivo | 36 |
| `indice.py` si gana `indice_turno` | dos índices | 36 |
| `calc_defensiva.py`, `huecos.py` si nadie los llama | sueltos o de otro camino | 36 |
| `grafo.py` de 32 nodos a los del turno nuevo | instrumento ciego en capas muertas | 34 y 36 |

Del árbol, no de `app/`, y git los guarda igual: fichas 01 a 21 cerradas,
`banco_pruebas/corridas/` (107 markdown), `interprete_viejo/`. No deployan.
Cada chat que los lee gasta contexto en un muerto.

**No va a `archivo/`:** barridos, casetes, piso, calculadora, certificador,
filtros, catálogo, FAQ, webhooks, transcriber, leads. Si entra eso, se apagó
el producto.

---

## Tres sesiones. No se juntan. Cada una pushea a `main`

### Sesión 1 — FICHA 34, el nexo

Ya está escrita en `arquitectura/FICHA_34_el_nexo.md`. Snapshot de reposición
y reconciliador. Nace `resolver`. El hub no llama a `P.reconciliar` ni a
`R.completar`. La cuenta se arma desde lo **declarado**. `salida.py` no se
toca. Deploya. Si el piso baja, revert.

Esta sesión no llega al 30%. Saca las dos opiniones. Las líneas caen de
verdad solo si `reposicion.py` sale de `app/`.

### Sesión 2 — FICHA 35, la puerta

Ya está escrita en `arquitectura/FICHA_35_la_puerta.md`. La 34 está en
`origin/main` y el piso no bajó. Un mutador en la higiene. Snapshot de
aduana a `archivo/`; si nadie la llama, `git rm` de `app/`. El modelo
escribe una vez. Se pega el bloque de la cuenta. Se corta lo que no está
en el contrato. Procedencia, plata sellada, cobro, saludo y punto omitido
se quedan. Si no sabe, el contrato ya dice NO_SE_SABE o AMBIGUO: el
redactor no inventa. Deploya.

### Sesión 3 — FICHA 36, el número

Lo apagado ya no está en `app/`. Nueve cuerpos de herramienta a cuatro
funciones. Tests de módulos archivados se van con ellos o se apuntan a
`archivo/` sin correrlos en el vivo. Fichas cerradas y corridas del banco
salen del árbol. Los doce barridos se reapuntan al resolver y al contrato.
Los dos termómetros de abajo tienen que pasar. Deploya.

Multi-tienda es este mismo paso, no un cuarto: el motor ya no tiene política
de una tienda. Semáforo: una carpeta de otro rubro. No se hace antes, porque
se copian las fugas.

---

## Cómo se verifica, en las tres

1. `python3 -m pytest -q` verde, marcas `xfail` sacadas de lo que esa sesión
   cerró.
2. El piso de las 15 charlas **no baja**. Puntos, llamadas, largo, camino al
   cobro. Si baja, revert.
3. Los barridos de identidad, filtros, cuenta, FAQ y herramientas no pierden
   cobertura. Se reapuntan en el mismo commit que el corte.
4. Los termómetros `test_app_tiene_a_lo_sumo_ciento_ochenta_funciones` y
   `test_app_pesa_a_lo_sumo_siete_mil_trescientas_lineas` bajan. Cierran en
   la 36, no antes, a menos que una sesión ya los ponga verdes.

El que implementa no reescribe la vara.

---

## Duplicados, la regla para no volver a hinchar

Una propiedad, una función, un módulo. Identidad la certifica el código.
Catálogo una puerta. Plata una puerta. Contrato un índice. Salida una puerta.
`_norm` y `_money` una vez. Si hace falta la misma actividad, se llama a esa,
no se escribe otra.

`test_nada_suelto.py` sigue: función sin caller o va a `archivo/` o se borra.
No se suma a `DECLARADAS` para tapar.

---

## Bloque para el chat que EMPIEZA la sesión 2

```
Repo: github.com/martinrf79/Verifika, rama main.
git fetch origin main && git checkout main && git status.
Si HEAD no es origin/main, PARÁ y avisá.
Leé SOLO: ARRANQUE.md, arquitectura/PLAN_REDUCCION.md,
arquitectura/FICHA_35_la_puerta.md, DECISIONES.md.
Corré pytest -q.
Prioridad uno: el bot vende y no alucina. Si no sabe, lo dice o repregunta.
ESTA SESIÓN ES LA FICHA 35, segundo tercio de PLAN_REDUCCION. Nada más.
Snapshot a archivo/ ANTES de tocar el vivo.
La higiene queda con un solo mutador (componer). Aduana no reescribe;
si nadie la llama, sale de app/.
La prosa no se reescribe: se pega el bloque de la cuenta y se corta lo
que no está en el contrato.
Si el piso baja, revert. PUSHEÁ a main. Toca app/: pedí el OK del push
una vez, al final. Nada de ramas.
```
