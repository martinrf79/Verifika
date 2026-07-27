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
PRODUCCION corre el FLUJO ATADO: orchestrator -> app/core/hub_atado.py
(interprete Gemini con schema strict + solver generador_v2 por fragmentos
atados a enums de la fuente). interprete_libre YA NO es el camino vivo.

EL CONTACTOR = la config declarativa (enums/campos del schema atados a listas
cerradas de la fuente) que ata y enruta al modelo SIN decidir por el. Cada
contacto: 1) trigger mutuamente excluyente; 2) solo ata el dato, nunca
reescribe la prosa.

ULTIMO TRACK (27-jul, rama claude/context-memory-review-1x5n7n): CONTEXTO Y
MEMORIA, diagnosticado sobre la charla REAL del 24-jul leida de los logs.
Arreglado: 1) el universo ya no se contamina por palabra suelta del mensaje
cuando el interprete resolvio el producto en foco; 2) el prompt del solver
lleva resumen de la charla, productos mostrados, FOCO del interprete e
historial mas ancho; 3) la poda de prosa poda PLATA, no cualquier digito
(antes borraba la respuesta de spec en silencio); 4) la ficha contesta specs
(caracteristicas, medidas, contenido_caja, uso); 5) el hub vuelve a
PERSISTIR preferencias_cliente, producto_anotado y grupos_envio, que se
leian y no se guardaban desde el pase al atado.

COMO VER UNA CHARLA REAL SIN GCLOUD: la env GCP_SA_KEY_B64 trae la clave de
claude-lector (logging.viewer + datastore.viewer). Decodificar al scratchpad,
REQUESTS_CA_BUNDLE=/root/.ccr/ca-bundle.crt, y pegarle por REST a
logging.googleapis.com/v2/entries:list (filtro service_name agente-bot) y a
firestore.googleapis.com (tiendas/verifika_prod/conversaciones/<user_id>:
ahi vive el history y el summary vivos).

PROXIMO PASO — TRACK FUENTE DE VERDAD DE PRODUCTO (5 pasos, plan cerrado con
Martin el 27-jul): 1) perfil de campos por categoria en specs_por_categoria.json;
2) el bot lee ese perfil y la consulta de spec entra como slot REQUERIDO del
schema; 3) extractor verificado contra texto bajado; 4) corridas por lote;
5) compatibilidad como veredicto del codigo. Pasos 1, 2 y 5 con Opus; 3 y 4 con
Sonnet. El plan entero esta al tope del RESUMEN.

Detalle completo: tope de RESUMEN_PARA_NUEVO_CHAT.md (seccion 27-jul).
Bancos: BANCO_PAUSA_S=8 python banco_pruebas/banco_atado_charlas.py banco_pruebas/guiones/68_*.txt
========================================================================
ESTADO
