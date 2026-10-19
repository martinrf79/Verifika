"""LA FICHA 10 — la ficha 9 con la atadura de la identidad: lo que el modelo nombra lo ancla el codigo en el catalogo.

El modelo sigue llenando la ficha 9. Lo que cambia es lo que hace el codigo con la ficha antes de usarla, y todo
sale de la fuente de la tienda, sin listas escritas a mano:

  1. TIPOS. Un campo que el esquema dice booleano y llega como texto con algo adentro es true: "pide": "con envio".
  2. IDENTIDAD. Cada articulo del pedido y cada producto que el modelo escribe en texto libre —una condicion, la
     alternativa de una compatibilidad— se resuelve contra el catalogo con los tres veredictos de la regla 7.0.
     Un articulo con un solo modelo queda con su nombre del catalogo; uno ambiguo queda como lo dijo el cliente.
  3. RUBRO O PRODUCTO. Lo que el modelo puso como producto y no es ningun modelo del catalogo, pero empieza por un
     rubro y trae algo mas, es una busqueda de ese rubro: "cargador de 20W". Un rubro solo —"me llego roto el
     monitor"— queda como lo puso el modelo.
  4. UNA BUSQUEDA POR RUBRO. Una condicion que es otro rubro de la tienda es otra busqueda.

Y lo que recibe el modelo, `CASILLAS_10`: la ficha 9 con cuatro definiciones corregidas, cada una por una clase de
falla. El pedido es lo que el cliente decide llevar; una referencia a uno lista sus candidatos y el codigo pregunta si
son varios; una referencia a un grupo es una busqueda entre lo mostrado; lo que se da por cierto de la tienda va con
su tema.

  python3 banco_pruebas/nexos/ficha10.py --replay                     las salidas grabadas, ficha 9 contra ficha 10
  python3 banco_pruebas/nexos/ficha10.py --58 --replay <etiqueta>     lo mismo sobre las 58, `casos58.py`
  python3 banco_pruebas/nexos/ficha10.py --ronda58 <etiqueta> --info10    las 58 con el modelo
  python3 banco_pruebas/nexos/ficha10.py --ronda <etiqueta> --info10      los 174 con el modelo
"""
import functools
import io
import json
import os
import re
import sys
import contextlib

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.dirname(os.path.dirname(AQUI)))
import desmenuzado as D  # noqa: E402
import ficha_casillas as F  # noqa: E402

_lista = F._lista


def _tokens(t: str) -> list:
    return F._palabras(t)


# ══ EL CATALOGO, VISTO POR MODELO ════════════════════════════════════════════

_MODELOS = None


def modelos() -> dict:
    """(marca, modelo) -> productos de ese modelo, uno por color."""
    global _MODELOS
    if _MODELOS is None:
        _MODELOS = {}
        for p in D.POR_ID.values():
            if p.get("modelo"):
                _MODELOS.setdefault((p.get("marca") or "", p["modelo"]), []).append(p)
    return _MODELOS


def nombrados(texto: str, largo: int = 6) -> list:
    """Los modelos del catalogo que nombra un texto libre: "si no hay stock de la Epson L3250, la mas barata". Cada
    tramo de hasta `largo` palabras pasa por la identidad; vale el tramo que da un solo modelo, y entre dos que se
    pisan, el mas largo: "RTX 4060 Ti" no es tambien "RTX 4060". Un tramo que da varios modelos no nombra ninguno.
    Y un tramo nombra un modelo solo si trae una palabra con letras de su marca o su modelo: "300 mil" no es el
    gabinete Q300L (18-oct, C31 de las 58)."""
    ws = _tokens(texto)
    hallados = []  # (inicio, fin, modelo)
    for i in range(len(ws)):
        for j in range(min(len(ws), i + largo), i, -1):
            idt = identidad(" ".join(ws[i:j]))
            propias = set(_tokens(" ".join(idt.get("modelo") or ())))
            if idt["veredicto"] == "exists" and any(re.search(r"[a-z]", w) and w in propias for w in ws[i:j]):
                hallados.append((i, j, idt["modelo"]))
                break
    out = []
    for i, j, m in sorted(hallados, key=lambda h: h[0] - h[1]):
        if not any(i < b and a < j for a, b, _ in out):
            out.append((i, j, m))
    return list(dict.fromkeys(m for _, _, m in sorted(out)))


@functools.lru_cache(maxsize=None)
def _modelos_que_nombra(texto: str) -> tuple:
    from app.core.filtros_catalogo import los_que_lo_nombran_entero
    return tuple(dict.fromkeys((p.get("marca") or "", p["modelo"])
                               for p in los_que_lo_nombran_entero(list(D.POR_ID.values()), texto) if p.get("modelo")))


def identidad(texto: str, color: str = "") -> dict:
    """Los tres veredictos de la regla 7.0 para un texto del modelo. El modelo lo decide la identidad de produccion,
    `los_que_lo_nombran_entero`; el barrido del catalogo la midio mejor que una propia. Un rubro con un dato
    —"cargador 25W"— no es un producto aunque alguno lo lleve en el nombre: es una busqueda."""
    if not texto.strip() or F.rubro_generico(texto)[0]:
        return {"veredicto": "not_found"}
    ms = list(_modelos_que_nombra(texto))
    if not ms:
        return {"veredicto": "not_found"}
    if len(ms) > 1:
        return {"veredicto": "ambiguous", "modelos": ms}
    prods = modelos()[ms[0]]
    pedido = set(_tokens(f"{texto} {color}"))
    del_color = [p for p in prods if p.get("color") and set(_tokens(p["color"])) <= pedido]
    if len(del_color) == 1 or len(prods) == 1:
        nombre = (del_color or prods)[0]["nombre"]
    else:
        # varios colores y no dijo cual: el modelo, sin color
        p = prods[0]
        nombre = re.sub(r"\s+" + re.escape(p.get("color") or "") + r"$", "", p["nombre"]) if p.get("color") else p["nombre"]
    return {"veredicto": "exists", "modelo": ms[0], "nombre": nombre}


# ══ LA ATADURA DE LA FICHA 10 ════════════════════════════════════════════════

TEXTO_LIBRE = (("condiciones", ("si", "entonces")), ("compatibilidad", ("si_anda", "si_no")), ("total", ("si_pasa",)),
               ("jerga", ("es",)))


def _cotizable(destino: str) -> bool:
    from app.core import fuente
    return bool(fuente._cotizar(destino))


def _rubro_y_resto(nombre: str) -> tuple:
    """(rubro, resto) si el texto es un rubro con un filtro que no nombra ningun modelo: "auriculares JBL" ->
    ("auriculares", "jbl"). Si lo que sigue al rubro trae una palabra del modelo de alguno de los candidatos —"Notebook
    HP 245 G9"—, nombra un producto y vuelve ("", "")."""
    from app.core import tablero as T
    w = _tokens(nombre)
    for largo in (3, 2, 1):
        rub = T._es_rubro(" ".join(w[:largo]), D.TIENDA) if len(w) > largo else ""
        if rub:
            de_modelo = {x for m in _modelos_que_nombra(nombre) for x in _tokens(m[1])}
            resto = w[largo:]
            return ("", "") if set(resto) & de_modelo else (rub, " ".join(resto))
    return "", ""


def _verdad(v) -> bool:
    if isinstance(v, str):
        return D.n(v) not in F._SIN_DESTINO and D.n(v) not in ("false", "no")
    return bool(v)


def atar(llena: dict) -> dict:
    llena = dict(llena or {})
    # 1. TIPOS
    tot = llena.get("total")
    if isinstance(tot, dict) and isinstance(tot.get("pide"), str):
        llena["total"] = {**tot, "pide": _verdad(tot["pide"])}
    ped = llena.get("pedido") if isinstance(llena.get("pedido"), dict) else None
    if ped is not None and isinstance(ped.get("cambia"), str):
        ped = llena["pedido"] = {**ped, "cambia": _verdad(ped["cambia"])}
    # 2. IDENTIDAD de los articulos
    if ped and ped.get("articulos"):
        arts = []
        for a in _lista(ped["articulos"]):
            if isinstance(a, dict) and a.get("producto"):
                idt = identidad(str(a["producto"]), str(a.get("color") or ""))
                if idt["veredicto"] == "exists":
                    a = {**a, "producto": idt["nombre"], "color": None}
                # EL DESTINO ES UN LUGAR QUE EL COTIZADOR CONOCE: "no especificado" o "pendiente" no lo son, y el
                # articulo queda sin destino para que el codigo lo pregunte.
                d = str(a.get("destino") or "").strip()
                if d and D.n(d) not in F._SIN_DESTINO and not _cotizable(d):
                    a = {**a, "destino": None}
            arts.append(a)
        llena["pedido"] = {**ped, "articulos": arts}
    # 2. IDENTIDAD de lo que el modelo escribio en texto libre
    ya = " ".join(str(p.get("producto") if isinstance(p, dict) else p) for p in _lista(llena.get("productos")))
    ya += " " + " ".join(str(r.get("es")) for r in _lista(llena.get("referencias")) if isinstance(r, dict))
    nuevos = []
    for casilla, campos in TEXTO_LIBRE:
        for x in _lista(llena.get(casilla)):
            if not isinstance(x, dict):
                continue
            for c in campos:
                for m in nombrados(str(x.get(c) or "")):
                    if not nombrados(ya + " " + " ".join(nuevos)) or m not in nombrados(ya + " " + " ".join(nuevos)):
                        nuevos.append(f"{m[0]} {m[1]}")
    # UN PRODUCTO CONCRETO Y UN ENVIO EN EL MISMO MENSAJE SON UNA CUENTA: "cuanto me sale el G203 con envio" (C47 de
    # las 58). El total lo arma el codigo; no depende de que el modelo lo pida.
    concretos = [p for p in _lista(llena.get("productos")) if isinstance(p, dict)
                 and identidad(str(p.get("producto") or ""))["veredicto"] == "exists"]
    if concretos and _lista(llena.get("envios")):
        tot = llena.get("total") if isinstance(llena.get("total"), dict) else {}
        llena["total"] = {**tot, "pide": True}
    # LA REFERENCIA CON VARIOS CANDIDATOS SE PREGUNTA (C52 de las 58). Cuenta el codigo, por modelo: dos colores del
    # mismo modelo no son dos productos distintos para "y ese es inalambrico?".
    for r in _lista(llena.get("referencias")):
        if not isinstance(r, dict):
            continue
        cand = {identidad(str(x)).get("modelo") or D.n(str(x)) for x in _lista(r.get("candidatos")) if str(x).strip()}
        if len(cand) > 1:
            llena["preguntar"] = _lista(llena.get("preguntar")) + [f"a cual se refiere con '{r.get('dijo')}'"]
            llena["productos"] = [p for p in _lista(llena.get("productos")) if not (
                isinstance(p, dict) and D.n(str(p.get("producto") or "")) == D.n(str(r.get("es") or "")))]
    # LO QUE SE DA POR CIERTO DE LA TIENDA se verifica contra el tema que nombro el modelo, si es de la lista
    temas = [str(a.get("tema")) for a in _lista(llena.get("afirma")) if isinstance(a, dict)
             and str(a.get("tema") or "") in D.TEMAS]
    if temas:
        llena["politicas"] = _lista(llena.get("politicas")) + [t for t in temas if t not in _lista(llena.get("politicas"))]
    # 3. RUBRO O PRODUCTO
    prods, busq = [], list(_lista(llena.get("busquedas")))
    for p in _lista(llena.get("productos")):
        nombre = str(p.get("producto") if isinstance(p, dict) else p or "")
        veredicto = identidad(nombre)["veredicto"]
        if veredicto != "exists":
            # Un rubro con un dato que ningun modelo lleva, o con un filtro que alcanza a varios modelos —"auriculares
            # JBL"—, es una busqueda de ese rubro.
            rub, resto = F.rubro_generico(nombre) if veredicto == "not_found" else _rubro_y_resto(nombre)
            if rub and resto.strip():
                busq.append({"rubro": rub, "cantidad": 1, "orden": "nada", "condiciones": [resto] if resto else []})
                continue
        prods.append(p)
    prods += [{"producto": n, "quiere_saber": "todo"} for n in nuevos]
    if prods or llena.get("productos"):
        llena["productos"] = prods
    # 5. UNA BUSQUEDA POR RUBRO
    from app.core import tablero as T
    salida = []
    for b in busq:
        if not isinstance(b, dict):
            salida.append(b)
            continue
        propio = T._es_rubro(str(b.get("rubro") or ""), D.TIENDA)
        conds, otros = [], []
        for c in _lista(b.get("condiciones")):
            r = T._es_rubro(str(c), D.TIENDA)
            if r and propio and r != propio:
                otros.append(r)
            else:
                conds.append(c)
        salida.append({**b, "condiciones": conds} if otros else b)
        salida += [{"rubro": r, "cantidad": 1, "orden": "nada", "condiciones": []} for r in otros]
    if salida or llena.get("busquedas"):
        llena["busquedas"] = salida
    return llena


# ══ LO QUE RECIBE EL MODELO: la ficha 9 con una definicion corregida ═════════

# EL PEDIDO ES LO QUE EL CLIENTE DECIDE LLEVAR (18-oct). Con la ficha 9 el modelo armaba un pedido cuando el
# cliente pedia ver un producto: X02 "necesito un teclado..." y C28 de las 58 "pasame el G305". La casilla decia
# "agrega", sin decir que es agregar.
CASILLAS_10 = F.CASILLAS_9.replace(
    '"cambia" es true si este mensaje agrega, saca, mueve o confirma algo, AUNQUE dependa de\n  una condicion;',
    '"cambia" es true si este mensaje agrega, saca, mueve o confirma algo, AUNQUE dependa de\n  una condicion. '
    'Agregar es cuando el cliente decide llevarlo: lo compra, lo anota, lo suma, se lo lleva o pide que se lo manden. '
    'Pedir ver, pasar, mostrar, buscar o necesitar un producto es una consulta: va en productos o busquedas, no aca;'
).replace(
    # LA REFERENCIA QUE PUEDE SER MAS DE UNA SE PREGUNTA (C52 de las 58, la vara: "pregunta cual de todos").
    'y a\n  que producto o parte del pedido apunta, con el nombre concreto. [{"dijo", "es"}]',
    'y a\n  que producto o parte del pedido apunta, con el nombre concreto. Cuando senala UNO —"ese", "el otro"—, '
    '"candidatos" son TODOS los de lo mostrado o del pedido a los que pueden apuntar esas palabras, uno o varios: no '
    'elijas, el codigo pregunta si son varios. Cuando senala un GRUPO —"de esos", "cual de todos"— no va aca: es una '
    'busqueda entre lo mostrado. [{"dijo", "es", "candidatos"}]'
).replace(
    # LO QUE SE DA POR CIERTO DE LA TIENDA SE VERIFICA CONTRA SU POLITICA (C12 de las 58): la casilla no tenia donde
    # poner el tema, y el codigo no lo encontraba por las palabras del cliente.
    'El codigo lo verifica. [{"dice", "sobre"}]',
    'El codigo lo verifica. Si es de la tienda, "tema" es el tema de la lista que lo cubre. [{"dice", "sobre", "tema"}]'
).replace(
    # LO QUE SE DICE PARA VARIAS VA EN CADA UNA (19-oct, X24 y el grupo C de las 58): "el mas barato de cada uno"
    # quedaba solo en la ultima busqueda.
    'Las exclusiones que siguen valiendo, de la ficha, van en cada busqueda nueva, de cualquier rubro.',
    'Las exclusiones que siguen valiendo, de la ficha, van en cada busqueda nueva, de cualquier rubro. Un orden o una '
    'condicion que el cliente dice para varias —"de cada uno", "los dos", "todo"— va en cada una de esas busquedas.')
assert "de cada uno" in CASILLAS_10
assert CASILLAS_10 != F.CASILLAS_9 and '"candidatos"' in CASILLAS_10 and '"sobre", "tema"' in CASILLAS_10


def con_info_10():
    """La consigna de la ficha 9 con las casillas de la 10, para la ronda en vivo."""
    F.CASILLAS_9 = CASILLAS_10


# ══ LA VARA SIN MODELO ═══════════════════════════════════════════════════════

def replay(etiquetas=None, ver=False):
    from app.core.tablero import _json
    casos = {c[0]: c for c in D.CASOS}
    antes = despues = n = 0
    cambios = []
    por_et = {}
    reserva = [0, 0]
    ultima = {}  # la ultima salida de cada caso en cada ronda, como `ficha_casillas.filas`
    for x in open(os.path.join(AQUI, "ficha_casillas_corridas.jsonl"), encoding="utf-8"):
        f = json.loads(x)
        ultima[(f["etiqueta"], f["id"])] = f
    for f in ultima.values():
        if f["crudo"].startswith("ERROR") or (etiquetas and f["etiqueta"] not in etiquetas) or f["id"] not in casos:
            continue  # una ronda de la otra vara —las 58 o los 174— no se corrige con estos casos
        j = _json(f["crudo"])
        if not isinstance(j, dict) or "llena" not in j:
            continue
        llena = j.get("llena") or {}
        caso = casos[f["id"]]
        a = F.corregir(caso, llena)["ok"]
        b = F.corregir(caso, atar(llena))["ok"]
        n += 1
        antes += a
        despues += b
        e = por_et.setdefault(f["etiqueta"], [0, 0, 0])
        e[0] += 1
        e[1] += a
        e[2] += b
        if f["id"] in D.RESERVA:
            reserva[0] += a
            reserva[1] += b
        if a != b:
            cambios.append((f["etiqueta"], f["id"], "ARREGLA" if b else "ROMPE"))
    print(f"salidas grabadas {n}: ficha 9 {antes}, ficha 10 {despues} · de la reserva {reserva[0]} y {reserva[1]}")
    for et, (k, a, b) in sorted(por_et.items()):
        if a != b or ver:
            print(f"  {et:10s} {a:4d} -> {b:4d} de {k}")
    for c in cambios:
        print("  ", *c)
    return cambios


if __name__ == "__main__":
    with contextlib.redirect_stdout(io.StringIO()):
        D.preparar()
    if "--58" in sys.argv or "--ronda58" in sys.argv:
        # LAS 58 EN LUGAR DE LOS 174: el mismo corrector y la misma ficha, sobre `casos58.py`.
        import casos58
        D.CASOS, D.RESERVA = casos58.CASOS_58, casos58.RESERVA_58
    ronda = "--ronda58" if "--ronda58" in sys.argv else "--ronda" if "--ronda" in sys.argv else ""
    if ronda:
        # El modelo llena la ficha 9, o la 10 con --info10; la nota de la ficha 10 sale despues con --replay.
        F.FICHA["version"], F.INFO["version"] = 9, 2
        if "--info10" in sys.argv:
            con_info_10()
        solo = sys.argv[sys.argv.index("--casos") + 1] if "--casos" in sys.argv else ""
        F.ronda(sys.argv[sys.argv.index(ronda) + 1], 0, solo)
    if "--replay" in sys.argv:
        resto = [a for a in sys.argv[sys.argv.index("--replay") + 1:] if not a.startswith("--")]
        replay(etiquetas=set(resto) or None, ver="--ver" in sys.argv)
