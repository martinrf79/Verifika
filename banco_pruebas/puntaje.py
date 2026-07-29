"""
EL NUMERO — un solo puntaje de 0 a 100 sobre las charlas grabadas.

Por que hace falta. Sin un numero, "robusto" es una opinion y cada chat nuevo
opina distinto: ese es el otro motor del loop. Con un numero hay una regla dura
que no se discute -ningun cambio se mergea si el numero baja- y "las pruebas
pasan" deja de significar "los tests de unidad no se rompieron" para significar
"el bot contesta bien".

QUE MIDE. Tres cosas, en orden de dureza, todas deterministas y sin LLM:

  1. NO MIENTE (peso 3). Reusa `banco_pruebas/juez.py`, que ya estaba escrito y
     se corria a mano: stock contradicho contra el catalogo real, plata sin
     respaldo, promesas prohibidas, marcadores sin estampar. Es lo unico que no
     se negocia: una charla con una sola mentira no pasa, por mas linda que sea.
  2. CONTESTA (peso 2). Que la respuesta exista, no sea el enlatado y tenga
     sustancia. Un fallback es un turno perdido aunque no mienta.
  3. LO QUE EL GUION PIDE (peso 2). Expectativas escritas en el propio guion,
     opcionales: `> contiene:` y `> no_contiene:`. El guion sin expectativas
     puntua igual por 1 y 2, asi el numero existe HOY sobre los 65 y se afila
     solo a medida que se escriben expectativas. No bloquea nada.

Ademas se descuenta por HUECO DE CASETE: si el codigo hace una llamada al modelo
que la grabacion no tiene, la charla se corrio a medias y el puntaje lo dice, no
lo esconde.
"""
import re
import unicodedata

PESOS = {"no_miente": 3, "contesta": 2, "espera": 2}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def leer_guion(texto: str) -> list[dict]:
    """Parsea un guion a [{mensaje, contiene: [...], no_contiene: [...]}].

    El formato viejo -una linea por mensaje, `#` comentario- sigue valiendo tal
    cual: las expectativas son lineas que empiezan con `>` y cuelgan del mensaje
    de arriba. Asi los 65 guiones existentes no se tocan.
    """
    turnos: list[dict] = []
    for linea in texto.splitlines():
        cruda = linea.strip()
        if not cruda or cruda.startswith("#"):
            continue
        if cruda.startswith(">"):
            if not turnos:
                continue
            cuerpo = cruda.lstrip("> ").strip()
            clave, _, valor = cuerpo.partition(":")
            clave = clave.strip().lower()
            if clave in ("contiene", "no_contiene") and valor.strip():
                # `|` son ALTERNATIVAS: alcanza con que aparezca una. Lo escribi
                # primero como "tienen que estar todas" y me dio un rojo falso a
                # la primera corrida: el bot contesto "no comercializamos
                # celulares", que es perfecto, y la expectativa pedia la palabra
                # "no trabajamos". Un rojo falso es peor que no tener la
                # expectativa, porque ensena a ignorar el tablero. Para exigir
                # DOS cosas se ponen dos lineas.
                alternativas = [v.strip() for v in valor.split("|") if v.strip()]
                turnos[-1][clave].append(alternativas)
            continue
        turnos.append({"mensaje": cruda, "contiene": [], "no_contiene": []})
    return turnos


def _sin_sustancia(respuesta: str, fallback: str) -> bool:
    r = (respuesta or "").strip()
    if not r:
        return True
    if fallback and _norm(r)[:60] == _norm(fallback)[:60]:
        return True
    # un acuse pelado no contesta nada: sin cifra, sin producto y muy corto
    return len(r) < 25 and not re.search(r"\d", r)


def puntuar_turno(turno: dict, respuesta: str, tienda_id: str,
                  fallback: str) -> dict:
    """{puntos, total, fallas} de un turno."""
    from banco_pruebas.juez import juzgar
    fallas: list[str] = []
    obtenido = 0

    mentiras = juzgar(respuesta, tienda_id, turno.get("mensaje", ""))
    if mentiras:
        fallas += [f"miente: {m}" for m in mentiras[:4]]
    else:
        obtenido += PESOS["no_miente"]

    if _sin_sustancia(respuesta, fallback):
        fallas.append("no contesta: vacia, enlatada o sin sustancia")
    else:
        obtenido += PESOS["contesta"]

    esperadas = turno.get("contiene") or []
    prohibidas = turno.get("no_contiene") or []
    if not (esperadas or prohibidas):
        # sin expectativas escritas no se premia ni se castiga: el turno vale
        # por los dos criterios de arriba y el peso 2 no entra al total.
        return {"puntos": obtenido, "total": PESOS["no_miente"] + PESOS["contesta"],
                "fallas": fallas}
    r = _norm(respuesta)
    # cada grupo es un OR; que falten TODAS las alternativas de un grupo es la falla
    faltan = [" o ".join(g) for g in esperadas
              if not any(_norm(v) in r for v in g)]
    sobran = [v for g in prohibidas for v in g if _norm(v) in r]
    if faltan:
        fallas.append("falta en la respuesta: " + ", ".join(faltan[:3]))
    if sobran:
        fallas.append("no debia decir: " + ", ".join(sobran[:3]))
    if not (faltan or sobran):
        obtenido += PESOS["espera"]
    return {"puntos": obtenido, "total": sum(PESOS.values()), "fallas": fallas}


def puntuar_charla(turnos: list[dict], respuestas: list[str],
                   tienda_id: str = "verifika_prod", fallback: str = "",
                   huecos: list[str] | None = None) -> dict:
    """{puntaje, puntos, total, fallas} de una charla entera."""
    from banco_pruebas.juez import juzgar_charla
    puntos = total = 0
    fallas: list[str] = []
    for i, (turno, resp) in enumerate(zip(turnos, respuestas), 1):
        r = puntuar_turno(turno, resp, tienda_id, fallback)
        puntos += r["puntos"]
        total += r["total"]
        fallas += [f"T{i} {f}" for f in r["fallas"]]

    # invariantes de la charla entera: la coletilla robotica repetida
    total += PESOS["no_miente"]
    problemas_charla = juzgar_charla(respuestas)
    if problemas_charla:
        fallas += [f"charla: {p}" for p in problemas_charla[:3]]
    else:
        puntos += PESOS["no_miente"]

    # un hueco de casete significa que la charla se corrio a medias
    for h in (huecos or [])[:4]:
        fallas.append(f"casete: {h}")
    if huecos:
        puntos = max(0, puntos - PESOS["contesta"] * len(huecos))

    return {"puntaje": round(100 * puntos / total) if total else 0,
            "puntos": puntos, "total": total, "fallas": fallas}


def puntaje_global(resultados: list[dict]) -> int:
    """El numero, uno solo: puntos obtenidos sobre puntos posibles de TODAS las
    charlas. Se suma por punto y no por promedio de porcentajes, asi una charla
    larga pesa lo que tiene que pesar."""
    puntos = sum(r["puntos"] for r in resultados)
    total = sum(r["total"] for r in resultados)
    return round(100 * puntos / total) if total else 0
