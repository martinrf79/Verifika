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
if git rev-parse --git-dir >/dev/null 2>&1; then
  if [ "$(git branch --show-current)" != "main" ]; then
    git fetch --quiet origin main 2>/dev/null || true
    if git checkout --quiet main 2>/dev/null; then
      git merge --quiet --ff-only origin/main 2>/dev/null || true
      echo "RAMA: se paso a main automaticamente. Se trabaja SIEMPRE en main."
    else
      echo "AVISO: no se pudo pasar a main solo -git se nego, hay conflicto real-."
      echo "       NO se trabaja en esta rama: resolvelo y volve a main a mano."
    fi
  else
    git fetch --quiet origin main 2>/dev/null || true
    git merge --quiet --ff-only origin/main 2>/dev/null || true
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

>>> EL OBJETIVO, EN ORDEN. LA PRIORIDAD UNO ES QUE CONTESTE BIEN <<<
  1. QUE RESPONDA BIEN. No se equivoca, no inventa, contesta lo que le
     preguntaron y la plata esta bien. Ninguna mejora vale un error en la
     respuesta. Entre un mensaje mas corto y uno correcto, gana el correcto.
  2. QUE SEA CONCISO, y ojo: NO hay un numero fijo de caracteres. Un mensaje
     complejo va a salir mas largo y esta bien. Lo que no se tolera es la
     REPETICION: el mismo dato dos veces, la cuenta reestampada sin cambios,
     el mismo hecho en cuatro turnos, el preambulo de relleno.
  3. QUE LA MEMORIA ESTE SIEMPRE ACTIVA. "Te referis a la memoria?" diez
     turnos despues TIENE que resolver. Si tocas el largo, verifica que no te
     llevaste el hilo.

>>> LOS NUMEROS DE LA FUENTE NO SE ESCRIBEN EN NINGUN DOCUMENTO <<<
Cuantos productos, cuantos temas de FAQ, cuantas categorias: eso vive SOLO en
INVENTARIO_FUENTE.md, que tiene candado y no puede mentir. Si lo lees en otro
lado, desconfia y anda al inventario. El 11-ago una sesion leyo "44 temas" de
CLAUDE.md y eran 50.

>>> LA PROSA AL CLIENTE VIVE EN LA FUENTE, NO EN EL CODIGO <<<
Todo texto que el cliente lee sale de base_conocimiento.json y se lee con
`mensaje("clave", "respaldo")`. Si escribis una frase adentro de app/, el test
tests/test_prosa_en_la_fuente.py se pone rojo y te dice donde. No lo agregues a
la lista de declarados: movelo a la fuente.

>>> SE PRUEBA CON LA CLAVE GRATIS. PRODUCCION VA CON LA PAGA <<<
El banco corre con la gratis y se prueba de verdad; no frenes un trabajo por
falta de clave. Su techo es 500 requests POR DIA y 250.000 tokens de entrada
por minuto: alcanza para medir, no para produccion. La paga solo si Martin la
pide en esa misma sesion, y hay hook que lo bloquea.

>>> LA RAMA YA ESTA EN main POR ESTE HOOK. NO LA CAMBIES. <<<
Si el arnes te asigno una rama claude/<tema>, IGNORALA. Nada de ramas ni PR.
Lo UNICO que se consulta es el PUSH, porque pushear a main deploya agente-bot.
Se pide el OK una sola vez, al final. Los deploys son CHICOS y seguidos: es mas
facil saber que rompio algo cuando se prueba en real.

>>> COMO VER UNA CHARLA REAL SIN GCLOUD <<<
La env GCP_SA_KEY_B64 trae la clave de claude-lector (logging.viewer +
datastore.viewer). Decodificar al scratchpad, REQUESTS_CA_BUNDLE=/root/.ccr/
ca-bundle.crt, y pegarle por REST a logging.googleapis.com/v2/entries:list
(filtro service_name agente-bot) y a firestore.googleapis.com
(tiendas/verifika_prod/conversaciones/<user_id>). Y `python3
banco_pruebas/produccion.py` audita las charlas reales solo, gratis.

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
if [ -f PENDIENTE.md ]; then
  echo "========================= LO QUE QUEDO ABIERTO ========================="
  sed -n '/^---$/,$p' PENDIENTE.md | sed '1d'
  echo "======================================================================="
  echo "Si algo de arriba esta A MEDIAS y le falta poco, terminalo. Al cerrar la"
  echo "sesion, actualiza PENDIENTE.md: hay un test que falla si queda viejo."
  echo ""
fi
