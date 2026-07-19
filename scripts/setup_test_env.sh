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
