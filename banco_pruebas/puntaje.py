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
  4. SIRVE (peso 2). Que la respuesta le sirva a quien la lee. NACE DE UNA
     MEDICION, no de una idea: el 31-jul se corrieron en vivo cuatro preguntas
     faciles pero COMPUESTAS -guion 70- y el juez las dio LIMPIAS las cuatro
     con las cuatro respuestas mal. Verde en todo y roto en WhatsApp no era una
     contradiccion: era que nadie medía si la respuesta servia. Tres defectos,
     los tres mecanicos y los tres vistos en esa corrida:
       a. DA EL DATO Y LO NIEGA. "Envio: $6.000 ... el costo exacto depende de
          tu localidad y se confirma cuando cerremos". Le da el numero y en la
          oracion siguiente le dice que no se lo puede dar.
       b. PREGUNTA LO QUE YA SABE. "Decime que producto estas mirando" en el
          mismo mensaje donde acaba de listar dos productos con su precio.
       c. REPITE UN BLOQUE ENTERO de un turno anterior, textual.
     Es deliberadamente conservador: un rojo falso ensena a ignorar el tablero,
     asi que solo entra el patron inequivoco que ya se vio salir al cliente.

Ademas se descuenta por HUECO DE CASETE: si el codigo hace una llamada al modelo
que la grabacion no tiene, la charla se corrio a medias y el puntaje lo dice, no
lo esconde.

SUMAR UN CRITERIO NO PUEDE TIRAR EL GATE. `test_el_numero_no_baja` compara los
PUNTOS crudos, y un criterio nuevo solo agrega puntos posibles: los obtenidos
suben o quedan igual, nunca bajan. Lo que baja es el PORCENTAJE, y eso es
exactamente lo que se quiere ver -el agujero que estaba tapado-.
"""
import re
import unicodedata

PESOS = {"no_miente": 3, "contesta": 2, "espera": 2, "sirve": 2}

# ── criterio 4: SIRVE ───────────────────────────────────────────────────────
# (a) el monto de envio ESTAMPADO por el codigo, que es el dato duro del turno
_RE_ENVIO_ESTAMPADO = re.compile(r"env[ií]o[^.\n]{0,20}\$\s?\d")
# ...y la frase que dice que ese mismo costo todavia no se sabe. Solo formas
# inequivocas: "el costo exacto depende", "depende de tu localidad", "te vamos
# a confirmar el detalle final". Una que hable de otra cosa no entra.
# El primer corte listaba tres frases y el modelo escribio una cuarta: se corto
# "el costo exacto depende de tu localidad" y volvio con "el costo exacto se
# calcula desde la plataforma al momento de avanzar". Perseguir la redaccion es
# perder, asi que se persigue la FORMA: el costo CALIFICADO como exacto o final
# y postergado. El primer intento fue mas ancho -cualquier "costo/valor/monto"
# cerca de un verbo de postergar- y dio rojo falso sobre prosa de cierre normal
# ("confirmame asi te paso los datos"). Un rojo falso ensena a ignorar el tablero.
# Es el MISMO patron que poda `generador_v2._sin_negar_lo_estampado`, importado
# de ahi a proposito: escritos por separado, uno marcaba y el otro no podaba.
from app.core.generador_v2 import _RE_ENVIO_POSTERGADO as _RE_COSTO_INDEFINIDO

# (b) preguntar por el producto cuando el mismo mensaje ya lo nombra con precio
_RE_PREGUNTA_QUE_PRODUCTO = re.compile(
    r"dec[ií]me qu[eé] (producto|modelo)|qu[eé] (producto|modelo) est[aá]s "
    r"(mirando|buscando|viendo)")
_RE_LINEA_PRODUCTO = re.compile(r"-\s*\$\s?\d|\$\s?\d[\d.]*\s*\(\d+ en stock\)"
                                r"|total\s*:\s*\$\s?\d", re.IGNORECASE)
# (c) bloque repetido textual entre turnos: una oracion larga, misma charla
_MIN_BLOQUE_REPETIDO = 70
_RE_CORTE_ORACION = re.compile(r"(?<=[.!?])\s+|\n")
# El renglon de presupuesto y la linea de producto los ESTAMPA el codigo desde
# la fuente, y repetirlos cuando el cliente pide reconfirmar el pedido es lo
# correcto, no una coletilla. Salieron como rojo falso en la primera corrida
# -guiones 24 y 48- y un rojo falso ensena a ignorar el tablero. Lo que se
# persigue es la PROSA repetida, no el dato reestampado.
_RE_RENGLON_ESTAMPADO = re.compile(r"c/u\s*=|^-?\s*\d+\s*x\s")


def _no_sirve(respuesta: str) -> list[str]:
    """Los defectos de un turno suelto. Vacio = el turno sirve."""
    r = _norm(respuesta)
    fallas: list[str] = []
    if _RE_ENVIO_ESTAMPADO.search(r) and _RE_COSTO_INDEFINIDO.search(r):
        fallas.append("da el costo de envio y en el mismo mensaje dice que "
                      "todavia no se sabe")
    if _RE_PREGUNTA_QUE_PRODUCTO.search(r) and _RE_LINEA_PRODUCTO.search(r):
        fallas.append("pregunta que producto mira en el mismo mensaje donde "
                      "ya lo nombra con su precio")
    return fallas


def bloques_repetidos(respuestas: list[str]) -> list[str]:
    """Oraciones largas que salen TEXTUALES en dos turnos distintos.

    Visto en la corrida del 31-jul: el bloque de compatibilidad -puertos USB y
    sistemas operativos- salio identico en el turno 1 y en el 2, y en el 2 el
    cliente habia dicho "de ese SOLO quiero saber si sirve para jugar". El tope
    de 70 caracteres deja pasar la linea de producto repetida al confirmar, que
    es legitima."""
    visto: dict[str, set] = {}
    for i, r in enumerate(respuestas or []):
        for o in _RE_CORTE_ORACION.split(r or ""):
            o = re.sub(r"\s+", " ", _norm(o)).strip()
            if len(o) >= _MIN_BLOQUE_REPETIDO and not _RE_RENGLON_ESTAMPADO.search(o):
                visto.setdefault(o, set()).add(i)
    return [f"bloque repetido en {len(t)} turnos: '{o[:70]}'"
            for o, t in visto.items() if len(t) >= 2]


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

    inservible = _no_sirve(respuesta)
    if inservible:
        fallas += [f"no sirve: {p}" for p in inservible]
    else:
        obtenido += PESOS["sirve"]

    base = PESOS["no_miente"] + PESOS["contesta"] + PESOS["sirve"]
    esperadas = turno.get("contiene") or []
    prohibidas = turno.get("no_contiene") or []
    if not (esperadas or prohibidas):
        # sin expectativas escritas no se premia ni se castiga: el turno vale
        # por los criterios de arriba y el peso 2 de `espera` no entra al total.
        return {"puntos": obtenido, "total": base, "fallas": fallas}
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

    # ...y el bloque entero repetido de un turno a otro, que la coletilla no ve:
    # aquella mira la ULTIMA linea en 3 turnos, esta mira cualquier oracion larga
    # en 2.
    total += PESOS["sirve"]
    repetidos = bloques_repetidos(respuestas)
    if repetidos:
        fallas += [f"charla: {p}" for p in repetidos[:3]]
    else:
        puntos += PESOS["sirve"]

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
