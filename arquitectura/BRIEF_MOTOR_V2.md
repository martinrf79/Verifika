# BRIEF — MOTOR V2: el turno nuevo que reemplaza al viejo en el camino vivo

Autocontenido. Escrito para que lo ejecute cualquier modelo capaz de programar
(Claude Opus, Grok, un modelo desde Cursor) sin leer ninguna conversacion previa.
Fecha: 2-sep-2026. Repo: github.com/martinrf79/Verifika, rama main.

Leer antes de tocar nada: `CLAUDE.md` (reglas del repo, cortas) y este brief.
No leer `RESUMEN_PARA_NUEVO_CHAT.md` ni las fichas viejas de `arquitectura/`:
no hacen falta para esto y gastan contexto.

---

## 1. LA DECISION, EN CUATRO LINEAS

- El turno vivo actual (`app/core/hub_venta.procesar_venta`) tiene el reparto
  invertido: 17 piezas de codigo intentan JUZGAR prosa, y el modelo mas barato
  redacta. El codigo no razona; el modelo si. Se da vuelta.
- No se recorta el hub viejo pieza por pieza. Se escribe UN archivo nuevo,
  `app/core/turno.py`, de unas 600 lineas, que REEMPLAZA al viejo en el camino
  vivo (regla 11.6 de CLAUDE.md). El viejo pasa a `archivo/` entero.
- Se reusa todo lo determinista que ya existe y esta probado (seccion 4). No
  se reescribe una calculadora, un filtro ni un cotizador.
- Gana el que mide mejor con la MISMA vara (seccion 6). Si V2 pierde, revert
  y no se perdio nada.

Objetivos que mandan, en orden:
  1.  El bot vende, no alucina, y ante la duda hace UNA pregunta de confirmacion.
  1b. Motor multitienda: tienda nueva = carpeta en `data/clientes/<id>/`, cero Python.
  Al final, dos modos por configuracion de tienda: `lead_fuerte` (avisa al
  dueño tras la pregunta de confirmacion) y `cierre` (entrega datos de cobro).

---

## 2. EL TURNO V2 — cinco pasos, dos llamadas al modelo, una compuerta

```
mensaje del cliente
  |
  1. INTERPRETAR  llamada UNO. Esquema JSON `RegistrarPedido` (ya existe).
  |               temperature 0. Sin herramientas visibles: solo declara.
  2. RESOLVER     codigo. De lo declarado deriva busquedas, ficha, stock,
  |               compatibilidad, temas de FAQ, envios y la cuenta.
  |               Todo con las funciones de la seccion 4. Sale un dict
  |               `material` con ids certificados y un `bloque_cuenta`.
  3. REDACTAR     llamada DOS. Modelo FUERTE con razonamiento (seccion 5),
  |               con `material` como unico dato. Instruccion: contestar
  |               todo lo preguntado, pegar el bloque de cuenta tal cual,
  |               marcar cada dato con su id entre corchetes (atadura).
  4. COMPUERTA    codigo, UNA sola, booleana por oracion:
  |               - cada numero con $ del texto esta en `bloque_cuenta` o en
  |                 `material`; si no, la oracion se corta.
  |               - cada [id] existe en `material`; si no, la oracion se corta;
  |                 despues se quitan los corchetes.
  |               - cada punto declarado sin material queda como PREGUNTA
  |                 escrita por el codigo, una sola por turno, al final.
  |               - nada se reescribe, nada se repone: se corta o se pregunta.
  5. CIERRE       codigo. Segun `modo_cierre(tienda)`:
                  lead_fuerte: si el cliente confirmo (pregunta de confirmacion
                  respondida con si), `leads.crear_lead` + `notificador`.
                  cierre: `pago.datos_transferencia` o link, mensaje sellado.
                  Guardar memoria: history, carrito, vistos, destinos, criterio.
```

Lo que NO existe en V2, a proposito: reconciliador, reposiciones, indice de
cobertura con estados, obligacion, higiene de diez reglas, grafo por engranaje,
invariantes en el camino. Si el modelo fuerte no cubre un punto, la compuerta
lo convierte en pregunta; no hay una pieza que "repone" texto.

---

## 3. CONTRATOS

`app/core/turno.py` expone UNA funcion, misma firma que hoy usa el orchestrator:

    async def procesar_turno(user_id: str, mensaje: str, tienda_id: str,
                             canal: str, trace_id: str) -> str

`app/core/orchestrator.py` cambia una linea: importa `procesar_turno` en lugar
de `procesar_venta`. Nada mas cambia afuera.

Estructuras internas, sin clases nuevas:

    declarado: dict   # salida de RegistrarPedido.model_dump()
    material: dict    # {"productos":[fichas con id], "temas":[...],
                      #  "envios":[...], "bloque_cuenta": str,
                      #  "puntos": [ {"id","tipo","texto","cubierto":bool} ]}
    texto: str        # lo que le llega al cliente

`puntos` se arma en RESOLVER, uno por cada renglon de `declarado`
(item, atributo, stock, compatibilidad, tema, destino, contradiccion, pago).
`cubierto` lo decide el codigo mirando si `material` trajo algo para ese
renglon. La COMPUERTA no vuelve a calcularlo sobre el texto: pregunta por lo
que ya sabia que faltaba. Excepcion: `contradiccion` nunca es `cubierto`;
siempre sale como pregunta.

---

## 4. QUE SE REUSA, TAL CUAL, Y DE DONDE

| paso | funcion | archivo |
|---|---|---|
| 1 | `RegistrarPedido`, `esquemas(tienda_id)` | `app/core/herramientas.py` |
| 2 | `ejecutar("consultar_productos", args, tienda)` proyecciones lista, ficha, compatibilidad, catalogo | `app/core/herramientas.py` |
| 2 | `certificar_temas(temas, tienda)`, `ejecutar("consultar_temas", ...)` | `app/core/herramientas.py` |
| 2 | `resolver_exclusion / resolver_inclusion / resolver_orden / categorias_nombradas / cantidades_por_categoria` | `app/core/filtros_catalogo.py` |
| 2 | `ejecutar("cotizar", {"items":[{product_id,cantidad,destino}], "destinos":[...], "pago":[...]}, tienda)` devuelve `bloque` | `app/core/herramientas.py` → `calculadora.calculate_total` |
| 2 | `_completar_el_declarado`, `_hitos_destinos`, `_grupos_del_mensaje` (item→ciudad leidos del mensaje) | `app/core/resolver.py`, se COPIAN a turno.py |
| 2 | `certificar_ids_de_resultado`, `construir_estado`, `set_current_estado` | `app/core/estado_venta.py` |
| 2 | `geo_cp.resolver`, `es_lugar_conocido` | `app/core/geo_cp.py` |
| 3 | `identidad(negocio)`, `mensaje(clave, defecto)` | `app/core/guia_venta_prosa.py` (lee `base_conocimiento.json`) |
| 3 | `_cliente()`, `llamar_con_reintento` | `app/core/hub_venta.py` → copiar a turno.py; `app/core/llm_reintento.py` |
| 4 | `AP.INSTRUCCION` y el parser de `[id]` | `app/core/atadura_prosa.py` |
| 5 | `modo_cierre`, `crear_lead`, `actualizar_lead`, `_RE_PIDE_COBRO` | `app/core/leads.py` |
| 5 | `datos_transferencia`, `mensaje_transferencia`, `elegir_medio_pago` | `app/core/pago.py` |
| 5 | `notificar_lead` | `app/core/notificador.py` |
| 5 | `get_conversation`, `save_conversation` | `app/storage/firestore_client.py` |
| 5 | `evaluar_mensaje` antijailbreak, `actualizar_resumen` memoria larga | ya lo llama el orchestrator / `memoria_larga.py` |

Todo lo que no esta en la tabla y vive en `app/core/` se evalua al final: si
V2 en verde no lo importa, va a `archivo/` con fila en `archivo/README.md`.

---

## 5. EL MODELO QUE REDACTA — el experimento mas barato y el que mas mueve

Hoy redacta el modelo mas barato con `REDACTOR_REASONING` bajo. Tau-bench
muestra diferencias enormes entre modelos en esta misma tarea. Antes de
escribir V2, UN DIA de medicion con el hub actual:

    GEMINI_MODEL=<modelo con razonamiento> REDACTOR_REASONING=medium \
      python3 banco_pruebas/objetivo.py --vivo

Tres corridas por configuracion. Se anota promedio y PEOR CASO en la tabla de
`OBJETIVO.md`. Si el peor caso sube solo con cambiar el modelo, ese es el
redactor de V2 y se justifica el costo por turno con el numero.
El DECISOR (llamada uno) se queda como esta: mide 94.

---

## 6. LA VARA — por CAPA, con casos de oro escritos a mano, no con casetes

Lo que fallo dos veces: medir de punta a punta con casetes grabados. Un casete
graba lo que el modelo DIJO, incluso cuando lo dijo mal, y despues la bateria
verde "confirma" un comportamiento equivocado. Y cuando el vivo falla, nadie
sabe en que capa se perdio el dato, asi que se le echa la culpa al modelo.

Regla nueva: cada capa tiene su vara propia, con la ENTRADA correcta escrita a
mano y la SALIDA correcta escrita a mano. Ninguna vara de capa depende de lo
que el modelo haya dicho en otra corrida.

    capa            entrada de oro (a mano)          salida esperada (a mano)        modelo?
    1 interpretar   40 mensajes reales de Martin     el `declarado` correcto         si, vivo
    2 resolver      el `declarado` correcto          `material`: ids, cuenta,        no
                                                     envios, puntos cubiertos/no
    3 redactar      `material` correcto              texto que nombra cada punto     si, vivo
                                                     y pega el bloque tal cual
    4 compuerta     textos con datos inventados      oracion cortada / pregunta      no
                    (8 formas por defecto, a mano)   escrita por el codigo
    5 cierre        estado + mensaje de confirmacion lead creado / datos de cobro    no

Los 40 mensajes son `banco_pruebas/las_40.py` y `CONSIGNA_PREGUNTAS_REALES.md`.
Los casos de oro van en `tests/oro/<capa>/*.json`, uno por caso, escritos por
la sesion y REVISADOS por Martin, que es el unico que sabe cual era la
respuesta correcta. Un caso de oro no se regraba nunca: se corrige a mano.

Como se lee un fallo del vivo: se toma el turno real (`/logs`), se compara
su `declarado` con el de oro (capa 1), se corre el resolver con el de oro y se
compara `material` (capa 2), y asi hasta encontrar la capa donde se perdio.
Esa es la ficha que se abre, y no otra. Asi el "tenes razon, es cableado"
deja de ser una conclusion de sesion y pasa a ser una linea de un test.

Aceptacion de V2, en este orden:
1. Capas 2, 4 y 5 al 100% de sus casos de oro, offline y gratis. Sin esto no
   se toca el vivo: son cableado puro y no tienen excusa de modelo.
2. Capa 1 y 3 en vivo con clave paga desde secretos de GitHub (`/vara`),
   tres repeticiones, manda el PEOR CASO. V2 entra si iguala o supera al hub
   viejo medido el mismo dia.
3. Latencia: la linea `hub_venta_ok.latency_ms` no sube.

Los casetes quedan SOLO para una cosa: que la bateria offline pueda correr el
turno entero sin clave. No son la vara de nada.

---

## 7. EL CICLO DE APRENDIZAJE — lo que hace que mejore con uso

Fuera del camino vivo, cada semana o a pedido con `/logs`:
`banco_pruebas/produccion.py` baja las charlas reales; un modelo fuerte las
juzga con la rubrica de `banco_pruebas/juez.py` (estado final + comunicacion,
como tau-bench); cada turno juzgado mal se convierte en un guion nuevo en
`banco_pruebas/guiones/` y en un caso de `objetivo.py`. El juez NO corre en
el turno: juzga despues. Asi el sistema mejora agregando casos, no piezas.

---

## 8. MULTITIENDA — el semaforo primero

Antes de portar nada: `data/clientes/ferreteria_demo/` con 20 productos y 10
temas, y dos tests que hoy fallan y son la lista real de trabajo:
  - `app/` no contiene `verifika_prod` ni categorias de electronica.
  - la tienda demo contesta 5 charlas sin tocar Python.
Fugas ya conocidas que V2 tiene que dejar afuera del codigo desde el primer
dia: la voz y las instrucciones de las dos llamadas (a `base_conocimiento.json`),
`geo_cp` (tabla por tienda), y la politica de negocio de `calculadora.py` y
`pago.py`: descuentos, umbrales de envio gratis, reparto de pago (a la fuente).

---

## 9. ORDEN DE EJECUCION Y COMMITS

    0. Casos de oro de las capas 2, 4 y 5 sobre las 40 preguntas, y el
       resolver ACTUAL corrido contra ellos: la lista real de puntos
       flacos del cableado, capa por capa, antes de escribir nada.  1 commit
    0b. /vara en el puente. Medir el hub viejo hoy: numero base.       1 commit
    1. Experimento del redactor (seccion 5). Anotar en OBJETIVO.md.    1 commit
    2. app/core/turno.py + orchestrator apunta a V2. Tests del viejo   1 commit
       a archivo/tests_hub_viejo/. hub_venta.py, salida.py, indice_turno.py,
       grafo.py, invariantes.py, mensaje.py, resolver.py a archivo/ con fila.
    3. pytest verde. /vara. Si peor caso >= base: queda. Si no: revert. 
    4. Modo lead_fuerte y modo cierre por tienda (seccion 2, paso 5).  1 commit
    5. Semaforo multitienda (seccion 8).                               1 commit

Reglas que no se negocian mientras se hace: se trabaja en main, sin ramas;
el push se consulta una vez porque deploya; ningun flag apagado; la clave
paga no se pega en ningun chat; el bot pide solo el nombre del cliente.

Como se vuelve atras: `git revert <hash>` del commit 2 devuelve el hub viejo
entero al camino vivo.
