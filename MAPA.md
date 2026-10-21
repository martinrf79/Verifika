# MAPA — qué querés tocar, a qué archivo ir

Una sola página. No cuenta el estado ni las reglas: eso es el bloque 0 de
`CLAUDE.md` y `PENDIENTE.md`. Esto dice DÓNDE ESTÁ CADA COSA.

## Con qué arranca una sesión nueva — tres archivos y ninguno más

1. El bloque 0 de `CLAUDE.md`, que son las reglas.
2. Esta página.
3. `PENDIENTE.md`: dónde va el trabajo y la ficha abierta. Sólo ahí se nombra. El plan está en `CLAUDE.md`.

**Arranque corto:**

1. El camino vivo es `orchestrator` → `flujo.turno.procesar_turno`: intérprete, ejecutor, redacción, cierre.
   El motor busca. Lo viejo está en `archivo/` y NO se reenchufa.
2. Se lee entera la ficha abierta que nombra `PENDIENTE.md` antes de tocar una mejora.
3. No se crea una función sin mirar si ya existe. La identidad la certifica
   `motor.lo_nombra`; la plata, `calculadora`.
4. No se cambia el diseño sin preguntarle a Martín.
5. Cada falla real de WhatsApp entra como caso en `tests/test_agente.py`
   ANTES de arreglarla.

## El bot que corre — `app/`

| Qué querés tocar | Archivo |
| --- | --- |
| Entrada de WhatsApp y Telegram, webhooks | `app/main.py` |
| Despacho, anti-jailbreak, reset | `app/core/orchestrator.py` |
| El turno entero: leer, interpretar, ejecutar, redactar, cerrar, guardar | `app/core/flujo/turno.py` |
| Las llamadas al modelo: traducir a la agenda, elegir la lectura y explicar; la consigna, los seis ejemplos y la libreta | `app/core/flujo/interprete.py` |
| Lo que dijo el cliente, las lecturas que cierran y lo supuesto hasta que acepta | `app/core/flujo/borrador.py` |
| La agenda: el menu de acciones y el control de lo que falta | `app/core/flujo/agenda.py` |
| Lo que el codigo reconoce en el mensaje antes del modelo | `app/core/flujo/marcador.py` |
| Lo que dijo el modelo, llevado a la forma que cumple el ejecutor: la forma normal | `app/core/flujo/normal.py` |
| Cada pregunta de la agenda, cumplida con las herramientas, y el candado | `app/core/flujo/ejecutor.py` |
| Identidad de un producto y búsqueda por condiciones | `app/core/flujo/catalogo.py` |
| La respuesta al cliente, escrita por el código | `app/core/flujo/redaccion.py` |
| El estado único de la charla | `app/core/flujo/estado.py` |
| El cierre: pedido y nombre, lead, aviso y cobro | `app/core/flujo/cierre.py` |
| Índice de la tienda, rubro, cuenta, envío, compatibilidad | `app/core/agente.py` |
| El motor: buscar, identidad, filtros, cuenta | `app/core/motor.py` |
| La llamada al modelo y el reintento | `app/core/llm_reintento.py` |
| Campos y filtros del catálogo | `app/core/filtros_catalogo.py` |
| Cuenta, precios, envío | `app/core/calculadora.py`, `app/core/envio.py` |
| Textos del cierre y cobro | `app/core/cierre.py`, `app/core/pago.py` |
| Aviso de lead | `app/core/leads.py` |
| Prosa fija de la casa | `app/core/guia_venta_prosa.py` |
| Leer y escribir Firestore | `app/storage/firestore_client.py` |
| Configuración y secretos | `app/config.py` |

## La fuente de verdad — `data/`

Catálogos y FAQ por tienda, bajo `data/clientes/<tienda>/`. En producción el
catálogo se lee de Firestore; esto es la carga y el respaldo. No se toca sin
permiso.

## Medición — `banco_pruebas/`

| Qué querés medir | Archivo |
| --- | --- |
| Producción: charlas reales, invariantes, `agente_turno` | `banco_pruebas/produccion.py` |
| Las 58 por el flujo nuevo, sin modelo: el instrumento del cableado | `banco_pruebas/cableado58.py` |
| La multipregunta de los siete artículos miles de veces, con el cliente y el modelo simulados | `banco_pruebas/simulador.py` |
| Lo que devuelve el intérprete en cada turno de las 58 y las K, escrito a mano como agenda | `banco_pruebas/agendas58.py` |
| Cada compleja dicha de muchas formas, con el modelo real: la vara para cambiar la consigna | `banco_pruebas/variantes.py` |
| Si lo que recibe el modelo alcanza, sin modelo | `banco_pruebas/suficiencia.py` |
| Las traducciones grabadas de seis modelos, calificadas con el codigo de hoy, sin modelo | `banco_pruebas/forma_normal/regrado.py` |
| Una mejora contra la base, charla por charla: el instrumento oficial | `banco_pruebas/puerta.py` |
| El cableado sin modelo: las charlas grabadas, el codigo de antes contra el de ahora | `banco_pruebas/grabadas.py` |
| La vara de las 58 | `banco_pruebas/vara_58.py` |
| Un turno por dentro | `banco_pruebas/sonda_turno.py` |
| El censo del cableado | `banco_pruebas/censo_cableado.py` |

Esta carpeta NO deploya y no entra a la imagen de Cloud Run.

## Batería offline — `tests/`

Corre sola en cada push a main, antes del deploy. Sin modelo y sin credenciales.

## Automático — `.github/workflows/`

| Workflow | Qué hace |
| --- | --- |
| `deploy.yml` | batería offline y deploy a Cloud Run |
| `sonda.yml` | atiende `/sonda` y `/vara` en un issue |
| `puente_cowork.yml` | atiende `/logs`: logs de producción e invariantes |

## Papeles — `papeles/` y `arquitectura/`

`arquitectura/` guarda las fichas de diseño, de la 59 en adelante; cuál está
abierta lo dice `PENDIENTE.md`. `MAPA_CABLEADO.md` es histórico. Las fichas cerradas (30 a 58) y los planes viejos están en
`archivo/fichas_cerradas/`. `papeles/` guarda decisiones, objetivo, deploy y
el inventario de la fuente.

## Apagado — `archivo/` y `reserva/`

Lo que no corre. `archivo/` es lo apagado; `reserva/` es lo reenchufable.
Ninguna de las dos deploya. Si algo de ahí hace falta, se mueve de vuelta a
mano y en su propio commit.

## Cómo se pide una medición

Se comenta en el issue 31, o desde una sesión de nube con `GCP_SA_KEY_B64`:

    python3 banco_pruebas/produccion.py --desde 6h
    /logs sev=INFO fresh=6h limit=300
