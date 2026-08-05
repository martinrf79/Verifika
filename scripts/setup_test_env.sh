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

LOS DOS NUMEROS QUE MANDAN, y se calculan solos:
  python3 banco_pruebas/las_40.py   -> LAS 40 preguntas de Martin, parte de
     CODIGO. Hoy 40 de 40. Es UNA capa: la herramienta con la llamada ideal.
  python3 banco_pruebas/mapa.py     -> EL MAPA: que funcion trabaja para que
     pregunta. Hoy 143 de 304 funciones del camino vivo NO las toca ninguna
     de las 40, el 47%. El hub tiene 26 de 38 a ciegas, incluidas las once
     guardas de salida. AHI viven las fallas que se ven en WhatsApp.
Los dos tienen candado en tests/ y corren en cada push.

PROXIMO PASO, acordado con Martin el 5-ago:
  A) Poner al dia la maquina de CASETES. banco_pruebas/casete.py apunta bien
     al hub vivo, pero los 65 casetes grabados son del flujo muerto y el test
     que los reproducia -tests/test_charlas_grabadas.py- NO EXISTE; el CI lo
     llama con "|| true" y dice "sin casetes grabados". Regrabar con el flujo
     vivo y escribir el test: el TURNO COMPLETO gratis en cada push.
  B) Sacarle trabajo al modelo: que el codigo arme la cuenta desde el pedido
     ya declarado, corte el bucle cuando no hay faltante ejecutable, y
     componga el mensaje en un solo lugar. Medido en produccion el 5-ago: 26,6
     segundos por turno, 4 llamadas al modelo, una ronda entera al pedo, un
     rubro entero afuera de la cuenta.

COMO VER UNA CHARLA REAL SIN GCLOUD: la env GCP_SA_KEY_B64 trae la clave de
claude-lector (logging.viewer + datastore.viewer). Decodificar al scratchpad,
REQUESTS_CA_BUNDLE=/root/.ccr/ca-bundle.crt, y pegarle por REST a
logging.googleapis.com/v2/entries:list (filtro service_name agente-bot) y a
firestore.googleapis.com (tiendas/verifika_prod/conversaciones/<user_id>:
ahi vive el history y el summary vivos).

Detalle completo: tope de RESUMEN_PARA_NUEVO_CHAT.md.
========================================================================
ESTADO
