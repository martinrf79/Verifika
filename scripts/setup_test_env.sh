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
TRACK ACTIVO (rama claude/session-lg1xff, NO en produccion aun): construir el
FLUJO ATADO (app/core/hub_atado.py) que reemplaza la pila de ~40 guardas de
interprete_libre. Los dos modelos atados (interprete + solver) SIN guardas.
Produccion sigue en interprete_libre (orchestrator NO cambio).

EL CONTACTOR = la config declarativa (enums/campos del schema atados a listas
cerradas de la fuente) que ata y enruta al modelo SIN decidir por el (a
diferencia del codigo duro que decide/reescribe). Cada contacto: 1) trigger
mutuamente excluyente; 2) solo ata el dato, nunca reescribe la prosa.

MODELO (medido): interprete en Gemini (json_schema strict, atadura DURA) 32/32.
DeepSeek V4 = fallback blando 91% (su API rechaza json_schema strict, 400).
Cuota gratis de Gemini throttlea: bancos usan BANCO_PAUSA_S=22 / BANCO_PACE_SEG.

HECHO Y COMMITEADO: hub_atado, prompt v5, schema con productos_consultados y
solicitud_nueva (categoria pedida no mostrada, atada al enum de categorias),
forzado de cotizar_envio por config, ancla del pedido al id real, guia mas
barato, traza por costura (hub_atado_traza), fix contaminacion id de ejemplo,
anti-coletilla. 615 tests offline verdes.

PROXIMO PASO (en orden): 1) correr guion 53 VIVO cuando la cuota de Gemini se
libere y confirmar que el teclado sobrevive toda la charla; 2) evolucionar el
Contactor a abarcativo mapeando cada categoria de ruteo_venta.py (B1..B20) a un
contacto con las 2 condiciones; 3) con el banco firme, apuntar el orchestrator
a hub_atado y retirar las guardas.

Detalle completo: tope de RESUMEN_PARA_NUEVO_CHAT.md (seccion 22-jul).
Bancos: BANCO_PAUSA_S=22 python banco_pruebas/banco_atado_charlas.py banco_pruebas/guiones/52_*.txt
========================================================================
ESTADO
