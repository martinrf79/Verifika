# MAPA — qué querés tocar, a qué archivo ir

Una sola página. No cuenta el estado ni las reglas: eso es el bloque 0 de
`CLAUDE.md` y `PENDIENTE.md`. Esto dice DÓNDE ESTÁ CADA COSA.

## Con qué arranca una sesión nueva — tres archivos y ninguno más

1. El bloque 0 de `CLAUDE.md`, que son las reglas.
2. Esta página.
3. `arquitectura/FICHA_65_el_tablero_y_la_biblioteca.md`, la unidad de trabajo desde el 29-sep;
   el método de cada mejora es la `FICHA_63`.

**Arranque corto:**

1. El camino vivo es `orchestrator` → `respuesta.procesar_turno` → `agente.turno`.
   El motor busca. Lo viejo está en `archivo/` y NO se reenchufa.
2. Se leen `FICHA_65` y `FICHA_63` enteras antes de tocar una mejora. La 64 es la medición de antes. El agente vive en la 62.
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
| El turno: agente, guarda de plata, cierre, memoria | `app/core/respuesta.py` |
| El agente: herramientas chicas, índice, alias | `app/core/agente.py` |
| El motor: buscar, identidad, filtros, cuenta | `app/core/motor.py` |
| Precio y envío que el modelo no puede inventar | `app/core/numeros.py` |
| La llamada al modelo y el reintento | `app/core/llm_reintento.py` |
| Campos y filtros del catálogo | `app/core/filtros_catalogo.py` |
| Cuenta, precios, envío | `app/core/calculadora.py`, `app/core/envio.py` |
| Cierre y cobro | `app/core/cierre.py`, `app/core/camino_cobro.py`, `app/core/pago.py` |
| Aviso de lead | `app/core/leads.py` |
| Prosa fija de la casa | `app/core/guia_venta_prosa.py` |
| Memoria de la charla | `app/core/memoria_larga.py` |
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

`arquitectura/` es la orden de trabajo viva: fichas 59 a 62 y el mapa de
nombres. Las fichas cerradas (30 a 58) y los planes viejos están en
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
