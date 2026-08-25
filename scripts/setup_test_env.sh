#!/usr/bin/env bash
# Prepara el entorno para que Claude (o cualquiera) pueda IMPORTAR el bot y correr
# la logica determinista offline (sin Firestore ni claves de LLM). Lo corre el hook
# de SessionStart en Claude Code web, o a mano: bash scripts/setup_test_env.sh
set -e

# ── LA RAMA SE PONE SOLA, NO SE PIDE POR ESCRITO ────────────────────────────
#
# POR QUE ESTO EXISTE (Martin, 7-ago-2026, dicho ya varias veces). La regla "se
# trabaja en main" estaba escrita en CLAUDE.md, en el RESUMEN y abajo en este
# mismo hook, y aun asi cada sesion nueva arrancaba en la rama `claude/<tema>`
# que asigna el arnes y Martin tenia que volver a aclararlo a mano. Un texto que
# hay que leer y obedecer no es un mecanismo: es un pedido. Esto lo HACE.
#
# El arnes de la sesion puede asignar la rama que quiera; el checkout de aca
# corre despues y manda. Nunca pisa trabajo: si el arbol viene sucio o el
# checkout falla por lo que sea, avisa y sigue, porque un hook de arranque no
# puede voltear la sesion.
# EL AGUJERO QUE TENIA ESTO, Y POR EL QUE MARTIN LO TUVO QUE REPETIR UNA DECIMA
# VEZ (10-ago). La version anterior se rendia ante CUALQUIER arbol sucio: si el
# arnes dejaba un archivo tocado -o la sesion se reanudaba con trabajo a medio
# hacer-, el hook imprimia "no se cambia de rama sola" y la sesion se quedaba en
# la rama `claude/<tema>` del arnes. O sea que el mecanismo se apagaba solo justo
# en el caso mas comun, y volvia a depender de que Martin lo dijera a mano.
#
# Ahora se INTENTA siempre. `git checkout main` con cambios sin commitear los
# ARRASTRA a main cuando no hay conflicto, que es lo que queremos; y cuando si
# hay conflicto git se niega solo y no pisa nada. La proteccion la da git, no
# una condicion nuestra de mas.
# EL TERCER AGUJERO, Y EL QUE COSTO TRES SESIONES (26-ago). Lo de arriba
# INTENTABA pasar a main y despues DABA POR HECHO que lo habia logrado. El
# `merge --ff-only` lleva `|| true`, asi que cuando el main local es una historia
# SIN ancestro comun con origin/main -el snapshot viejo que trae la imagen del
# contenedor- el merge se niega, no pasa nada, y el hook igual imprime "se paso a
# main automaticamente". La sesion arrancaba 56 commits atras, parada en la FICHA
# 06, con un cartel diciendole que estaba al dia.
#
# Intentar no es comprobar. Ahora, despues de intentar, se VERIFICA que HEAD sea
# origin/main, y segun por que no lo es se hace una cosa distinta:
#   - sin ancestro comun  -> es el arbol viejo de la imagen, jamas trabajo real:
#                            se corrige solo con reset --hard, y se avisa.
#   - con commits propios -> puede ser trabajo sin pushear: NO se toca, se PARA.
# El reset solo corre con el arbol limpio. Si hay cambios sin commitear no se
# pisa nada: se para y lo resuelve la sesion.
if git rev-parse --git-dir >/dev/null 2>&1; then
  git fetch --quiet origin main 2>/dev/null || true

  if [ "$(git branch --show-current)" != "main" ]; then
    if git checkout --quiet main 2>/dev/null; then
      echo "RAMA: se paso a main automaticamente. Se trabaja SIEMPRE en main."
    else
      echo "AVISO: no se pudo pasar a main solo -git se nego, hay conflicto real-."
      echo "       NO se trabaja en esta rama: resolvelo y volve a main a mano."
    fi
  fi
  git merge --quiet --ff-only origin/main 2>/dev/null || true

  # ── Y ACA SE COMPRUEBA, QUE ES LO QUE FALTABA ─────────────────────────────
  REMOTO="$(git rev-parse origin/main 2>/dev/null || true)"
  LOCAL="$(git rev-parse HEAD 2>/dev/null || true)"
  if [ -n "$REMOTO" ] && [ -n "$LOCAL" ] && [ "$LOCAL" != "$REMOTO" ]; then
    BASE="$(git merge-base HEAD origin/main 2>/dev/null || true)"
    SUCIO="$(git status --porcelain 2>/dev/null || true)"
    if [ -z "$BASE" ] && [ -z "$SUCIO" ]; then
      VIEJO="$(git rev-parse --short HEAD)"
      if git reset --hard -q origin/main 2>/dev/null; then
        echo "ARBOL VIEJO CORREGIDO: el main local era una historia SIN ancestro"
        echo "       comun con origin/main -el snapshot que trae la imagen-. Se"
        echo "       reapunto main a origin/main. Lo viejo queda en $VIEJO."
      fi
    else
      echo "PARA: HEAD no es origin/main y NO se corrige solo."
      if [ -z "$BASE" ]; then
        echo "       Historias sin ancestro comun y el arbol esta sucio: no se pisa."
      else
        echo "       main local tiene $(git rev-list --count origin/main..HEAD 2>/dev/null || echo '?') commit(s) propios: puede ser trabajo sin pushear."
      fi
      echo "       NO TRABAJES ASI. Es la REGLA CERO BIS de ARRANQUE.md."
      echo "       Miralo con: git status && git log --oneline origin/main..HEAD"
    fi
  fi
fi

pip install -q -r requirements.txt pytest
# La rueda de grpc/firestore necesita el backend nativo de cffi; sin esto, importar
# google.cloud.firestore tira ModuleNotFoundError: _cffi_backend.
pip install -q --force-reinstall cffi
echo "entorno de prueba listo: el app importa y la logica pura corre offline"

# ── LO QUE LA SESION NUEVA LEE SI O SI ──────────────────────────────────────
#
# POR QUE ESTO CAMBIO (Martin, 11-ago-2026). Acá vivían noventa líneas de
# ESTADO escritas A MANO, y el problema es el de siempre: envejecen. El dia que
# se armo esto, el bloque hablaba del objetivo de acortar mensajes y no decia
# una palabra de lo que se habia hecho en las ultimas cuatro sesiones. Una
# sesion nueva leia eso, lo tomaba por el estado actual y decidia con un dato
# viejo —que es exactamente como se le paso a Martin que la FAQ tenia 44 temas
# cuando tenia 50—.
#
# Ahora se imprimen TRES cosas y solo la primera esta escrita a mano:
#   1. las REGLAS, que son permanentes y por eso no envejecen;
#   2. `git log`, que es lo que de verdad se hizo. No lo escribe nadie dos
#      veces y no se puede desactualizar;
#   3. `PENDIENTE.md`, lo que quedo abierto, con un candado que no lo deja
#      quedar viejo (tests/test_pendiente_al_dia.py).
cat <<'REGLAS'

========================= COMO SE TRABAJA ACA — LEER =========================

>>> LAS REGLAS NO SE REPITEN ACA, Y ES A PROPOSITO (18-ago-2026) <<<
CLAUDE.md lo inyecta el arnes en TODA sesion, asi que volver a imprimirlo eran
4.345 bytes gastados en decir dos veces lo mismo — y por el largo total, lo de
abajo no llegaba a leerse. Las reglas estan alla. Aca van solo los MECANISMOS,
que son los que hacen algo en vez de pedirlo:
  - La rama YA esta en main por este hook. Si el arnes te asigno claude/<tema>,
    ignorala. Lo unico que se consulta es el PUSH, porque pushear deploya.
  - Se prueba con la clave GRATIS. La paga solo si Martin la pide en esa misma
    sesion, y hay hook que lo bloquea.
  - Lo que el cliente lee sale de base_conocimiento.json, no de app/.
  - Cuantos productos, temas o barridos hay NO se escribe en ningun texto:
    INVENTARIO_FUENTE.md e INVENTARIO_BARRIDO.md, que tienen candado.

>>> LOS INSTRUMENTOS, y que contesta cada uno <<<
  banco_pruebas/las_40.py          las 40 preguntas de Martin, parte de codigo
  banco_pruebas/mapa.py            que funcion no la toca ninguna prueba
  pytest tests/test_charlas_grabadas.py   el turno completo, gratis
  banco_pruebas/explorador.py      charlas que NADIE escribio, por el camino vivo
  banco_pruebas/produccion.py      las charlas REALES, auditadas solas
  banco_pruebas/objetivo.py        la nota contra el objetivo
  banco_pruebas/interpretacion.py  separa ENTENDER de CONTESTAR

Detalle historico: RESUMEN_PARA_NUEVO_CHAT.md. Reglas: CLAUDE.md.
=============================================================================
REGLAS

# ── LO QUE SE HIZO, contado por git y no por alguien ────────────────────────
echo ""
echo "===================== LO ULTIMO QUE SE HIZO (git) ====================="
git log --oneline --no-decorate -10 2>/dev/null | sed 's/^/  /'
echo ""

# ── LO QUE QUEDO ABIERTO ────────────────────────────────────────────────────
# EL TITULAR DE CADA PENDIENTE, NO EL PARRAFO ENTERO (18-ago-2026).
#
# LA CAUSA MECANICA DEL LOOP, medida: este hook imprimia 19.059 bytes y la
# sesion recibe una VISTA PREVIA DE 2 KB; el resto se guarda en un archivo que
# nadie abre. O sea que todo lo que estaba despues del primer 10% NO SE LEIA.
# Y ahi vivian, entre otras cosas, la linea que dice que GCP_SA_KEY_B64 esta en
# el entorno y la lista de instrumentos: dos cosas que sesiones enteras
# "descubrieron" o dieron por inexistentes teniendolas escritas.
#
# De esos 19 KB, PENDIENTE.md eran 13.658, el 72%. El archivo cumple su regla
# de veinte lineas y cada linea es un parrafo de 800 caracteres. Aca se imprime
# el ESTADO y la primera oracion de cada item, que es el titular; el que
# necesita el detalle abre el archivo. Mismo orden, misma informacion arriba,
# diez veces menos bytes.
if [ -f PENDIENTE.md ]; then
  echo "===================== LO QUE QUEDO ABIERTO (titulares) ================"
  sed -n '/^---$/,$p' PENDIENTE.md | sed '1d' | grep '^- \*\*' | \
    sed 's/\*\*//g' | cut -c1-150 | sed 's/$/ .../' | sed 's/^/  /'
  echo "  (el detalle de cada uno: PENDIENTE.md)"
  echo "======================================================================="
  echo ""
fi

# ── DONDE ESTAMOS HOY, GENERADO Y NO ESCRITO A MANO ─────────────────────────
# Los numeros salen de los pisos que ya estan en disco, asi que no pueden
# envejecer ni mentir. Es lo que Martin pidio: que una sesion nueva lea en UN
# solo lado donde esta parado el sistema, sin ir a buscarlo.
python3 scripts/areas.py 2>/dev/null
echo ""
echo "======================= DONDE ESTAMOS HOY (medido) ===================="
python3 - <<'PYEOF' 2>/dev/null
import json, os, subprocess
from pathlib import Path

def leer(ruta, *claves):
    try:
        d = json.loads(Path(ruta).read_text(encoding="utf-8"))
        return " ".join(f"{k}={d[k]}" for k in claves if k in d)
    except Exception:
        return "sin medir"

rama = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                      capture_output=True, text=True).stdout.strip()
sucio = subprocess.run(["git", "status", "--porcelain"],
                       capture_output=True, text=True).stdout.strip()
sin_pushear = subprocess.run(["git", "log", "--oneline", "origin/main..HEAD"],
                             capture_output=True, text=True).stdout.strip()
print(f"  rama: {rama}" + ("  <-- OJO, se trabaja en main" if rama != "main" else "")
      + ("  | arbol sucio" if sucio else "")
      + (f"  | {len(sin_pushear.splitlines())} commits SIN PUSHEAR" if sin_pushear else ""))

# LAS CREDENCIALES QUE SI ESTAN. Nunca el valor, solo si esta y cuanto mide.
# Nace de que una sesion afirmo que no habia clave de Firestore teniendola en
# el entorno, y por esa afirmacion se planifico mal medio dia.
env = []
for v in ("GCP_SA_KEY_B64", "GEMINI_API_KEY", "GEMINI_API_KEY_PROD",
          "DEEPSEEK_API_KEY", "OPENAI_API_KEY"):
    env.append(f"{v}={'SI' if os.environ.get(v) else 'no'}")
print("  claves en el entorno: " + "  ".join(env))
print("  (GCP_SA_KEY_B64 es claude-lector, SOLO LECTURA: con eso"
      " `python3 banco_pruebas/produccion.py` audita tus charlas reales gratis)")

print("  pisos medidos:")
print("    charlas grabadas   " + leer("banco_pruebas/casetes/_piso.json",
                                       "puntos", "total", "llamadas_max"))
print("    peso del turno     " + leer("banco_pruebas/peso_techo.json",
                                       "bytes_por_llamada"))
print("    cosas a medias     " + leer("tests/a_medias_techo.json", "a_medias"))
print("    puerta sin LLM     " + leer("banco_pruebas/puerta_piso.json",
                                       "_turnos", "_items_turnos_exactos_pct"))
PYEOF
echo '  el marcador del proyecto es banco_pruebas/las_40.py: correlo antes de proponer nada.'
echo "======================================================================="
echo ""
