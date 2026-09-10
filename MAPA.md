# MAPA — que querés tocar, a que archivo ir

Una sola pagina, y es la que hace que Martin y cualquier sesion vean lo mismo.
No cuenta el estado del sistema ni las reglas: eso es `CLAUDE.md` bloque 0, que
sigue siendo la puerta unica, y `PENDIENTE.md`, que dice lo que esta abierto.
Esto dice DONDE ESTA CADA COSA, y nada mas.

Si movés o partís un archivo, se actualiza esta pagina en el mismo commit.

## EL BOT QUE CORRE — `app/`

| Que querés tocar | Archivo |
| --- | --- |
| Entrada de WhatsApp y Telegram, webhooks, salud | `app/main.py` |
| Despacho del turno, anti-jailbreak, reset | `app/core/orchestrator.py` |
| EL TURNO COMPLETO, las ocho etapas | `app/core/turno.py` |
| Las dos llamadas al modelo y el reintento | `app/core/llm_reintento.py` |
| EL MOLDE que ve el modelo, `registrar_pedido` y los enums | `app/core/herramientas.py` |
| Resolucion de candidatos y busquedas derivadas | `app/core/resolver.py` |
| LA MESA de puntos y el armado del mensaje final | `app/core/tabla.py` |
| Campos y filtros del catalogo, el enum de `campo` | `app/core/filtros_catalogo.py` |
| Cuenta, precios, envio | `app/core/calculadora.py`, `app/core/envio.py` |
| Cierre y cobro | `app/core/cierre.py`, `app/core/camino_cobro.py`, `app/core/pago.py` |
| Aviso de lead | `app/core/leads.py` |
| Prosa fija de la casa | `app/core/guia_venta_prosa.py` |
| Memoria de la charla y estado de venta | `app/core/estado_venta.py`, `app/core/memoria_larga.py` |
| Leer y escribir Firestore | `app/storage/firestore_client.py` |
| Configuracion y secretos | `app/config.py` |

## LA FUENTE DE VERDAD — `data/`

Catalogos y FAQ por tienda, bajo `data/clientes/<tienda>/`. En produccion el
catalogo se lee de Firestore; esto es la carga y el respaldo.

## MEDICION — `banco_pruebas/`

| Que querés medir | Archivo |
| --- | --- |
| UN turno por dentro, las ocho etapas con sus datos | `banco_pruebas/sonda_turno.py` |
| LA INTERPRETACION: ¿declara en la casilla que corresponde? | `banco_pruebas/banco_llamada_uno.py` |
| Produccion como banco: charlas reales contra invariantes | `banco_pruebas/produccion.py` |
| Charlas grabadas para reproducir sin gastar modelo | `banco_pruebas/casetes/` |
| Salidas de todas las corridas, sin recortar | `banco_pruebas/salidas/` |

Esta carpeta NO deploya y no entra a la imagen de Cloud Run.

## BATERIA OFFLINE — `tests/`

Corre sola en cada push a main, antes del deploy. Si algo se pone rojo, el
deploy ni arranca. Sin modelo y sin credenciales.

## AUTOMATICO — `.github/workflows/`

| Workflow | Que hace |
| --- | --- |
| `deploy.yml` | bateria offline y deploy a Cloud Run |
| `sonda.yml` | atiende `/sonda` y `/vara` en un issue |
| `puente_cowork.yml` | atiende `/logs`: logs de produccion e invariantes |
| `aplicar_parche.yml` | aplica lo que se deja en `archivo/parches/` |
| `test.yml`, `calidad.yml`, `diagnostico.yml` | bateria, nocturno, diagnostico |

## PAPELES — `papeles/` y `arquitectura/`

`papeles/` son los documentos de referencia que hasta el 10-sep-2026 vivian
sueltos en la raiz. `arquitectura/` son las fichas y los planes, y ahi vive
`arquitectura/MAPA_CABLEADO.md`, que nombra cada parte del cableado.

UNA ACLARACION QUE EVITA UN TELEFONO DESCOMPUESTO: las fichas y lo apagado
siguen nombrando esos documentos por su ruta VIEJA, sin `papeles/`, y es a
proposito. Una ficha del 26-ago que dice `DECISIONES.md` esta contando donde
vivia ese documento ESE DIA, y eso es cierto. Reescribir el relato para que
apunte a la ruta de hoy seria falsearlo. Si una ficha nombra un documento y no
lo encontrás, esta en `papeles/`.

## APAGADO — `archivo/` y `reserva/`

Lo que no corre. `archivo/` es lo apagado y el deposito de cambios;
`reserva/` es lo reenchufable. Ninguna de las dos deploya.

## COMO SE PIDE UNA MEDICION DESDE UNA SESION

Se comenta en el issue 31 del repo:

    /logs sev=INFO fresh=6h limit=300     logs de produccion e invariantes
    /sonda <pregunta>                     un turno completo por dentro
    /vara                                 los 36 casos de interpretacion

Las tres dejan la salida entera en `banco_pruebas/salidas/` y contestan en el
mismo issue. Nadie pega una clave en un chat.
