#!/usr/bin/env bash
# Prepara el entorno para que Claude (o cualquiera) pueda IMPORTAR el bot y correr
# la logica determinista offline (sin Firestore ni claves de LLM). Lo corre el hook
# de SessionStart en Claude Code web, o a mano: bash scripts/setup_test_env.sh
set -e
pip install -q -r requirements.txt pytest
# La rueda de grpc/firestore necesita el backend nativo de cffi; sin esto, importar
# google.cloud.firestore tira ModuleNotFoundError: _cffi_backend.
pip install -q --force-reinstall cffi
echo "entorno de prueba listo: el app importa y la logica pura corre offline"

# ── ESTADO ACTUAL inyectado al contexto del chat nuevo (no depende de que
# alguien lea el RESUMEN; esto entra solo por la salida del hook) ────────────
cat <<'ESTADO'

========================= ESTADO ACTUAL — LEER =========================
SE TRABAJA EN main. El push se CONSULTA siempre: pushear a main deploya
agente-bot, salvo que el cambio toque solo .md o tests/.

PRODUCCION corre el HUB DE VENTA: orchestrator -> app/core/hub_venta.py, con
HERRAMIENTAS en paralelo (function calling atado a enums de la fuente viva) y
un reconciliador que compara lo DECLARADO contra lo EJECUTADO. El flujo atado
-hub_atado, interprete, generador_v2- MURIO el 1-ago y el archivo ya no
existe: si un documento viejo lo nombra, el documento esta vencido.

LOS TRES NUMEROS QUE MANDAN, y se calculan solos:
  python3 banco_pruebas/las_40.py   -> LAS 40 preguntas de Martin, parte de
     CODIGO. Hoy 40 de 40. Es UNA capa: la herramienta con la llamada ideal.
  python3 banco_pruebas/mapa.py     -> EL MAPA: que funcion trabaja para que
     prueba. Hoy 37 de 315 funciones del camino vivo no las toca ninguna
     prueba, el 12%; venia de 143, el 47%, y bajo cuando entraron las charlas
     grabadas.
  pytest tests/test_charlas_grabadas.py -> EL TURNO COMPLETO: 10 charlas
     reproducidas enteras por el camino del webhook con el modelo grabado.
     Piso 94/100 y hasta 5 llamadas al modelo por turno, que es la LATENCIA
     medida sin reloj.
Los tres tienen candado en tests/ y corren en cada push.

OJO CON EL CI: desde el 6-ago los push a main NO disparan tests ni deploy -el
job queda en cola sin runner-. Mientras dure, el deploy es A MANO:
  cd ~/verifika && ./deploy.sh

PROXIMO PASO, acordado con Martin (detalle en la seccion 6-ago cierre del
RESUMEN):
  1) LA ALUCINACION que queda: "todos los productos que trabajo tienen
     componentes chinos" es FALSO -91 no tienen- y el propio bloque del codigo
     lo desmiente tres renglones abajo. El detector mira universales sobre EL
     CATALOGO y esta se escapa hablando de "los productos que trabajo".
  2) SIN APLICAR, espera decision: cerrar la excepcion de _cuenta_no_retipeada,
     que deja pasar la cuenta anterior copiada textual cuando el cliente pidio
     precio ahora.
  3) La latencia es inestable -8,9 a 27,7 segundos-: la palanca que queda es que
     el codigo arme la cuenta sin esperar la ronda 2.

COMO VER UNA CHARLA REAL SIN GCLOUD: la env GCP_SA_KEY_B64 trae la clave de
claude-lector (logging.viewer + datastore.viewer). Decodificar al scratchpad,
REQUESTS_CA_BUNDLE=/root/.ccr/ca-bundle.crt, y pegarle por REST a
logging.googleapis.com/v2/entries:list (filtro service_name agente-bot) y a
firestore.googleapis.com (tiendas/verifika_prod/conversaciones/<user_id>:
ahi vive el history y el summary vivos).

Detalle completo: tope de RESUMEN_PARA_NUEVO_CHAT.md.
========================================================================
ESTADO
