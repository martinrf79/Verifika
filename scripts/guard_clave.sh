#!/usr/bin/env bash
# EL CANDADO DE LA CLAVE — hook PreToolUse que frena el gasto, no que lo pide.
#
# POR QUE EXISTE (Martin, 10-ago-2026). Martin lleva gastados cerca de cuarenta
# dolares en poco mas de un mes, casi todo en corridas de banco que NO
# necesitaban la clave paga: el banco mide comportamiento, no cuota.
#
# Y LO MAS IMPORTANTE: EL MECANISMO YA ESTABA BIEN Y SE GASTO IGUAL.
# `clon_produccion.preparar_entorno` elige la gratis sola desde el 4-ago y la
# paga entra solo con BANCO_CLAVE_PAGA=true. Pero CUATRO scripts la pisaban
# exportando la paga ANTES de que esa guarda corriera, asi que la guarda veia la
# paga ya puesta y la dejaba. Una regla escrita en un lugar y esquivada en
# cuatro: la misma falla que este repo ya pago varias veces.
#
# Por eso hay dos candados y no uno:
#   - este hook, que frena el comando ANTES de que corra;
#   - `tests/test_guard_sesion.py`, que falla si un script del repo vuelve a
#     pisar la clave, aunque nadie corra el hook.
#
# LA CLAVE GRATIS NO ES "no midas": es "medi con la gratis". Ninguna sesion
# tiene que frenar un trabajo por falta de clave. La gratis contesta 200 y su
# cuota se renueva sola; es mas lenta y a veces tira 429, y eso se reintenta.
set -e

ENTRADA="$(cat)"
CMD="$(printf '%s' "$ENTRADA" | python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("tool_input",{}).get("command",""))
except Exception: print("")' 2>/dev/null)"

[ -z "$CMD" ] && exit 0

# UN `git commit` NO GASTA UN PESO. Sin esta salida temprana el candado se
# bloquea a si mismo: el primer commit que lo explicaba NOMBRABA la variable en
# el mensaje, el grep la encontro y freno el commit. Un candado que no deja
# escribir por que existe es un candado roto, y la falla es de mirar texto
# suelto en vez de mirar lo que se ejecuta. Un mensaje de commit es texto.
if printf '%s' "$CMD" | grep -qE '^[[:space:]]*git[[:space:]]+commit'; then
  exit 0
fi

# ── 1. PISAR LA CLAVE VIVA CON LA PAGA ──────────────────────────────────────
# Es literalmente la linea que gasto la plata cuatro veces.
if printf '%s' "$CMD" | grep -qE 'GEMINI_API_KEY=\$?\{?GEMINI_API_KEY_PROD'; then
  echo "BLOQUEADO: no se pisa GEMINI_API_KEY con la clave PAGA." >&2
  echo "Es la linea exacta que gasto ~40 dolares en corridas que no la" >&2
  echo "necesitaban. La clave la elige UN solo lugar:" >&2
  echo "  banco_pruebas/clon_produccion.preparar_entorno" >&2
  echo "El default es la GRATIS y esta bien asi: se prueba con la gratis." >&2
  exit 2
fi

# ── 2. PEDIR LA PAGA SIN QUE MARTIN LA HAYA PEDIDO ──────────────────────────
#
# LA PUERTA, agregada el 11-ago-2026, y hace falta contar por que. Martin
# autorizo la paga en su sesion -"puedes utilizar la clave de pago"- para
# regrabar dos casetes que la gratis no aguanta, y el candado la bloqueo igual:
# no tenia forma de distinguir el reflejo automatico, que es lo que hay que
# frenar, de una orden directa, que segun la regla uno se ejecuta. Un candado
# sin puerta obliga a esquivarlo, y esquivarlo es exactamente como se gasto la
# plata las cuatro veces.
#
# La puerta NO es una contraseña ni pretende ser seguridad: es un ACTO
# EXPLICITO que deja rastro. Hay que escribir en la misma linea
# `MARTIN_AUTORIZO_LA_PAGA=<fecha>`, o sea afirmar por escrito, con fecha, que
# la orden existio. Eso no se teclea por inercia, queda en el historial y
# cualquiera puede ir a buscar la sesion donde Martin lo dijo. Sin esa marca,
# el bloqueo es el de siempre.
if printf '%s' "$CMD" | grep -qiE 'BANCO_CLAVE_PAGA=(true|1|yes)' \
   && printf '%s' "$CMD" | grep -qE 'MARTIN_AUTORIZO_LA_PAGA=[0-9]{1,2}-?[a-zA-Z]{3}-?[0-9]{4}'; then
  echo "PAGA AUTORIZADA por Martin en esta sesion (marca con fecha presente)." >&2
  echo "Recorda: solo lo que la gratis no pueda hacer. Su tope son 250.000" >&2
  echo "tokens de entrada por minuto; todo lo que entre ahi va con la gratis." >&2
  exit 0
fi

if printf '%s' "$CMD" | grep -qiE 'BANCO_CLAVE_PAGA=(true|1|yes)'; then
  echo "BLOQUEADO: BANCO_CLAVE_PAGA=true gasta plata de Martin." >&2
  echo "Solo se usa si Martin lo pidio EN ESTA sesion, con esas palabras." >&2
  echo "Si no lo pidio: corre con la clave gratis, que es el default." >&2
  echo "Si la gratis se agota veras 429; ahi se le avisa a Martin y decide el." >&2
  exit 2
fi

exit 0
