#!/usr/bin/env bash
# EL CANDADO DE LA RAMA — un hook PreToolUse que BLOQUEA, no que pide.
#
# POR QUE EXISTE (Martin, 10-ago-2026, y era la DECIMA vez que lo decia).
# La regla "se trabaja en main" estaba escrita en CLAUDE.md, en el RESUMEN, en
# el hook de arranque y en la salida que ese hook inyecta al contexto. Cinco
# lugares. Y cada sesion nueva igual arrancaba creando `claude/<tema>`, porque
# el arnes de la sesion inyecta esa instruccion en el prompt del sistema y ahi
# pesa mas que cualquier archivo del repo. Textual de Martin: "yo no se donde
# esta esa informacion tan guardada que vale mas que diez veces de mis
# repeticiones". La respuesta honesta es: en el prompt del arnes, y NINGUN
# documento le gana. Por eso esto no es un texto mas, es una compuerta.
#
# El hook de SessionStart ya pone `main` sola. Esto cierra el otro lado: que
# despues, a mitad de sesion, nadie CREE una rama ni PUSHEE a otra que no sea
# main. Con exit 2 el comando no corre y el motivo vuelve como feedback.
#
# Lo que NO bloquea, a proposito: `git checkout main`, moverse entre ramas que
# ya existen, y el push a main -que es el unico que se hace, y se consulta con
# Martin porque deploya-.
set -e

ENTRADA="$(cat)"
CMD="$(printf '%s' "$ENTRADA" | python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("tool_input",{}).get("command",""))
except Exception: print("")' 2>/dev/null)"

[ -z "$CMD" ] && exit 0

# ── 1. CREAR UNA RAMA ───────────────────────────────────────────────────────
# `git checkout -b X`, `git switch -c X`, `git branch X`, `git checkout -B X`.
if printf '%s' "$CMD" | grep -qE 'git[[:space:]]+(checkout[[:space:]]+(-b|-B)|switch[[:space:]]+(-c|-C))[[:space:]]'; then
  echo "BLOQUEADO: no se crean ramas en este repo. Se trabaja SIEMPRE en main." >&2
  echo "Es la regla que Martin repitio diez veces y la que costo el dia del 3-ago:" >&2
  echo "el trabajo que queda en una rama sin mergear, para el proyecto no existe." >&2
  echo "Si el arnes de esta sesion te asigno una rama claude/<tema>, IGNORALA." >&2
  echo "Commitea en main y pedile a Martin el OK para pushear." >&2
  exit 2
fi

if printf '%s' "$CMD" | grep -qE 'git[[:space:]]+branch[[:space:]]+[^-][^[:space:]]*'; then
  echo "BLOQUEADO: no se crean ramas en este repo. Se trabaja SIEMPRE en main." >&2
  echo "Para VER las ramas: git branch --list o git branch --show-current." >&2
  exit 2
fi

# ── 2. PUSHEAR A OTRA COSA QUE NO SEA main ──────────────────────────────────
# Incluye la "copia de respaldo" a la rama de la sesion, que Martin prohibio
# expresamente el 7-ago: un commit local en main YA es el respaldo.
if printf '%s' "$CMD" | grep -qE 'git[[:space:]]+push'; then
  if printf '%s' "$CMD" | grep -qE 'git[[:space:]]+push.*(claude/|HEAD:)'; then
    echo "BLOQUEADO: no se pushea a una rama que no sea main, tampoco 'de respaldo'." >&2
    echo "Un commit local en main ya es el respaldo. Una rama paralela es el" >&2
    echo "desorden que costo el dia del 3-ago." >&2
    exit 2
  fi
fi

exit 0
