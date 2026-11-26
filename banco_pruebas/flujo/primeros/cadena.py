"""LA CADENA DESDE LA FILA DE LUNA, SIN COPIA APARTE (26-nov-2026, orden de Martin). FICHA 108, capas 0 a 2.

Luna con el v14f1b, el que se midio robusto, sin pedirle nada mas: `luna_b.jsonl`. Cada fila trae partes
"{palabras del cliente}[nombre del vocabulario]". El codigo lee el nombre por la seccion de la ficha:
  PRODUCTOS        el rubro: dato 1, y filtra la busqueda.
  CARACTERISTICAS  como tiene que ser, o lo que pregunta de la ficha: dato 1 si trae un valor, dato 2 si lo pregunta.
  PREGUNTAS        dato 2: precio, stock, o un tema de la FAQ.
La consulta de embeddings son las palabras de las llaves que no son una pregunta, y ordena solo dentro del rubro del
corchete. Una fila que nombra algo sin corchete de producto queda "sin rubro": eso se resuelve abajo. Se miden dos salidas
para lo sin rubro: no ofrecer nada, o buscar en toda la tienda y que decida `existe`.

Se cuenta igual que `medir.py`, contra la misma etiqueta congelada, para comparar con lo de ayer, el circuito con lo pedido.

    python3 primeros/cadena.py [--ver]
    python3 primeros/cadena.py --dato2 [--ver]
    python3 primeros/cadena.py [--dato2] --examen [--ver]   # lo mismo sobre las 138 reales del examen fijo   # el dato 2 desde los corchetes, contra dato2.py
"""
import collections, json, os, re, sys
AQUI = os.path.dirname(os.path.abspath(__file__))
FL = os.path.join(AQUI, "..")
sys.path[:0] = [AQUI, os.path.join(FL, "lab"), os.path.join(FL, "examen"), FL]
sys.dont_write_bytecode = True
import medir as M  # noqa: E402
import existe as EX  # noqa: E402
import busqueda as B  # noqa: E402
import luna_ficha as LF  # noqa: E402
X = EX.X
nrm = X.nrm

SECCION = {}
for _linea in LF._f1().split("\n"):
    _sec, _nombres = _linea.split(":", 1)
    for _x in _nombres.split(","):
        SECCION.setdefault(nrm(_x), _sec.strip())


def partes(texto):
    """[(palabras, nombre o None)]. Luna escribe "{palabras}[nombre]", y a veces el corchete adentro de la llave,
    "{una camarita [webcam] para hablar}": cada corchete corta una parte, y lo que queda sin corchete es una parte sola."""
    out = []
    for m in re.finditer(r"\{([^}]*)\}\s*(?:\[([^\]]*)\])?|\[([^\]]*)\]", texto):
        if m.group(3) is not None:  # corchete suelto, fuera de llaves: nombra la parte anterior
            if out and out[-1][1] is None:
                out[-1] = (out[-1][0], nrm(m.group(3)))
            continue
        adentro, despues = m.group(1), m.group(2)
        trozos = re.split(r"\[([^\]]*)\]", adentro)  # texto, nombre, texto, nombre, ..., texto
        for j in range(0, len(trozos), 2):
            nombre = trozos[j + 1] if j + 1 < len(trozos) else None
            if trozos[j].strip() or nombre:
                out.append((trozos[j].strip(), nrm(nombre) if nombre else None))
        if despues:
            out[-1] = (out[-1][0], nrm(despues))
    return [(re.sub(r"[¿?¡!,.]", " ", p).strip(), n) for p, n in out]


INTERROGA = re.compile(r"\b(decime|contame|explicame|detallame|traduci|traducime|cual|cuales|cuanto|cuanta|cuantos|como|tiene|tienen|trae|traen|viene|vienen|es|son|anda|"
                       r"andan|sirve|sirven|incluye|soporta|aguanta|cuantas)\b")
CAMPOS = {"garantia meses": "garantia", "garantia detalle": "garantia", "memoria video": "memoria_video",
          "ram ampliable": "ram_ampliable", "lector huella": "lector_huella", "lector tarjetas": "lector_tarjetas",
          "resistencia agua": "resistencia_agua", "switch teclado": "switch_teclado", "conexion": "conexion"}


PRODUCTO_D2 = {"compatibilidad": "compat", "especificaciones": "caracteristicas", "descripcion": "caracteristicas",
               "caracteristicas extra": "caracteristicas"}


def nrm_corchetes(texto):
    return re.sub(r"\[([^\]]*)\]", lambda m: "[" + nrm(m.group(1)) + "]", texto)


def dato2(texto):
    """El dato 2 de una fila, desde los corchetes de Luna, por codigo:
      PREGUNTAS  stock disponibilidad -> stock; cualquier otra -> tema:<id> de la FAQ.
      CARACTERISTICAS  precio ars -> precio; preguntada, con "?" o una palabra que pregunta, -> campo:<id>; con un valor,
                 "inalambrico", es una condicion del dato 1 y no entra aca.
      nada de eso -> ofrecer.
    Devuelve (dato 2, condiciones): las condiciones son las caracteristicas con valor, para la capa 3."""
    d2, cond = [], []
    # La fila pregunta si trae "?" o una palabra que pregunta. Si lo que pregunta es stock o precio, lo demas es como
    # tiene que ser el producto; si no, lo que pregunta es la caracteristica: "{tiene} {luces}[retroiluminacion]".
    fila_pregunta = "?" in texto or bool(INTERROGA.search(nrm(re.sub(r"\[[^\]]*\]", " ", texto))))
    pide_base = bool(re.search(r"\[\s*(stock disponibilidad|precio ars)\s*\]", nrm_corchetes(texto)))
    for m in re.finditer(r"\{([^}]*)\}\s*\[([^\]]*)\]\s*(\?)?", texto):
        palabras, nombre, signo = m.group(1), nrm(m.group(2)), m.group(3)
        sec = SECCION.get(nombre)
        if nombre in PRODUCTO_D2:  # temas de la FAQ que son un dato del producto: si lo pregunta; si no, describe
            preguntado = INTERROGA.search(nrm(palabras)) or (not pide_base and ("?" in palabras or signo or fila_pregunta))
            (d2.append(PRODUCTO_D2[nombre]) if preguntado else cond.append((palabras.strip(), nombre)))
        elif sec == "PREGUNTAS":
            d2.append("stock" if nombre == "stock disponibilidad" else "tema:" + nombre.replace(" ", "_"))
        elif sec == "CARACTERISTICAS":
            if nombre == "precio ars":
                # "que no sea carisimo"[precio ars] es una condicion; "cuanto sale"[precio ars], el dato 2.
                pregunta = INTERROGA.search(nrm(palabras)) or "?" in palabras or signo or re.search(
                    r"\b(sale|salen|precio|precios|vale|valen|cuesta|cuestan)\b", nrm(palabras))
                (d2.append("precio") if pregunta else cond.append((palabras.strip(), nombre)))
            elif nombre in ("marca", "modelo"):
                continue
            elif INTERROGA.search(nrm(palabras)) or (not pide_base and ("?" in palabras or signo or fila_pregunta)):
                d2.append("campo:" + CAMPOS.get(nombre, nombre.replace(" ", "_")))
            else:
                cond.append((palabras.strip(), nombre))
    return (sorted(set(d2)) or ["ofrecer"]), cond


BASE = {"ofrecer", "precio", "stock", "comprar"}


def grupo(ds):
    """Lo base se contesta mostrando el producto con precio y stock; lo especifico pide un dato o una accion aparte."""
    return "base" if set(ds) <= BASE else "especifico"


def _codigo(w):
    """La misma regla del nexo de nombrado del bot, `app/core/flujo/nuevo/nombrado._codigo`: letras y cifras juntas."""
    return any(c.isdigit() for c in w) and any(c.isalpha() for c in w)


def _codigos():
    """Cada codigo de modelo del catalogo, "g305", "k120", "m170", con los rubros donde aparece."""
    import csv
    out = collections.defaultdict(set)
    ruta = os.path.join(FL, "..", "..", "data", "clientes", "verifika_prod", "productos.csv")
    for r in csv.DictReader(open(ruta, encoding="utf-8")):
        for w in nrm(r["modelo"]).replace("-", " ").split():
            if _codigo(w):
                out[w].add(nrm(r["categoria"]))
    return out


CODIGOS = _codigos()


def _uno(ps):
    rubros = [n for _, n in ps if n and SECCION.get(n) == "PRODUCTOS"]
    if not rubros:
        # Un codigo suelto del catalogo que Luna no puso en un rubro, "Quiero un Logitech M170": el rubro lo da el
        # catalogo, si el codigo esta en un solo rubro. Como el nexo de nombrado del bot.
        rs = set().union(*[CODIGOS.get(w, set()) for p, _ in ps for w in nrm(p).replace("-", " ").split()] or [set()])
        if len(rs) == 1:
            rubros = [rs.pop()]
            ps = ps + [("", "modelo")]
    preguntas = [n for _, n in ps if n and SECCION.get(n) == "PREGUNTAS"]
    caracts = [(p, n) for p, n in ps if n and SECCION.get(n) == "CARACTERISTICAS"]
    # La consulta es la fila entera de Luna: ya trae solo lo de ese pedido. Sacar lo marcado como pregunta perdia
    # caracteristicas que el vocabulario tiene como tema, "mecanico" en [teclado mecanico membrana].
    consulta = " ".join(p for p, _ in ps).strip()
    # Nombra un producto si trae rubro, marca o modelo, o palabras que Luna no supo poner en el vocabulario.
    suelto = any(n is None and len(re.sub(r"[^a-z0-9]", "", nrm(p))) > 2 for p, n in ps)
    identifica = any(n in ("marca", "modelo") for _, n in caracts)
    return {"rubro": rubros[0] if rubros else None, "consulta": consulta, "dato2": preguntas, "caracts": caracts,
            "identifica": identifica, "nombra": bool(rubros) or identifica or suelto, "partes": ps,
            # Lo que nombra el producto, aislado con las marcas de Luna, para `existe`: lo marcado como rubro, marca o
            # modelo; si no hay nada marcado asi, lo que quedo sin marcar. La fila entera trae nombres, destinos y
            # comandos, "Esteban", "Concordia", "System": medido el 26-nov, 29 falsas alarmas en las 138 reales.
            "nombre": " ".join(p for p, n in ps if n and (SECCION.get(n) == "PRODUCTOS" or n in ("marca", "modelo")))
                      or " ".join(p for p, n in ps if n is None)}


def leer(texto):
    """Lo que el codigo saca de una fila de Luna: uno o varios pedidos, uno por rubro, con su consulta, dato 2 y
    condiciones. Si Luna junto dos productos en una fila, "{cargador}[cargador] {65w}[potencia] y {parlante}[parlante]",
    cada rubro abre un pedido; lo de antes del primero va con el primero."""
    ps, grupos = partes(texto), [[]]
    for p, n in ps:
        # Un rubro dicho con "con", "notebook con ryzen", "auriculares con mic", es como tiene que ser el producto que
        # ya esta en la fila, no otro pedido: Luna lo marca con el nombre del rubro porque el vocabulario lo tiene.
        otro = n and SECCION.get(n) == "PRODUCTOS" and any(SECCION.get(m) == "PRODUCTOS" for _, m in grupos[-1])
        if otro and not re.match(r"(con|de|para)\b", nrm(p)) and not (grupos[-1] and (" " + nrm(grupos[-1][-1][0])).endswith(" con")):
            grupos.append([])
        elif otro:
            n = None
        grupos[-1].append((p, n))
    pregs = [x for g in grupos for x in g if x[1] and SECCION.get(x[1]) == "PREGUNTAS"]
    return [_uno(g + [x for x in pregs if x not in g]) for g in grupos]


EXAMEN = "--examen" in sys.argv  # las 138 reales del examen fijo, con su etiqueta y el dato 2 de `examen/tramos.py`
CONJ = next((c for c in ("reales", "muestras") if "--" + c in sys.argv), None)  # las 52 del pozo, las 137 muestras


def cargar():
    """La etiqueta y lo que separo Luna con el v14f1b: las 300 primeras, o con --examen las 138 reales."""
    if CONJ:
        ex = json.load(open(os.path.join(AQUI, f"{CONJ}.json"), encoding="utf-8"))
        ruta = os.path.join(AQUI, f"luna_{CONJ}.jsonl")
    elif EXAMEN:
        ex = json.load(open(os.path.join(FL, "examen", "examen.json"), encoding="utf-8"))
        ruta = os.path.join(FL, "examen", "luna_b.jsonl")
    else:
        ex, _ = M.cargar()
        ruta = os.path.join(AQUI, "luna_b.jsonl")
    return ex, {json.loads(l)["id"]: json.loads(l) for l in open(ruta)}


def etiqueta_dato2(i):
    """(dato 2 por pedido, temas aparte): de `dato2.py` para las 300; de `examen/tramos.py` para el examen."""
    if EXAMEN:
        from tramos import T
        t = T[i]
        return [list(d) for _, d in t["p"]], [x for _, x in t.get("t", []) if x != "fuera"]
    from dato2 import D
    return D[i]


def main(ver):
    ex, luna = cargar()
    filas = {e["id"]: [f for t in (luna[e["id"]]["salida"] or {}).get("textos") or [] for f in leer(t)] for e in ex}
    v = B.vectores([(f["consulta"], "RETRIEVAL_QUERY") for fs in filas.values() for f in fs if f["nombra"] and f["consulta"]])
    ia = B.indice_a()
    dot = lambda a, b: sum(x * y for x, y in zip(a, b))
    for variante in ("sin rubro no ofrece", "sin rubro busca en toda la tienda"):
        n, fallas = collections.Counter(), []
        for e in ex:
            res = []  # por fila que nombra un producto: (consulta, veredicto, top5)
            vistos = set()
            for f in filas[e["id"]]:
                if not (f["nombra"] and f["consulta"]):
                    continue
                clave = (f["rubro"], nrm(f["consulta"]))
                if clave in vistos:  # Luna repite la misma fila para la pregunta: es el mismo pedido
                    continue
                vistos.add(clave)
                q = v[(f["consulta"], "RETRIEVAL_QUERY")]
                if f["rubro"]:
                    # Existe tambien con rubro: "rtx 5090" trae placa de video y la tienda no tiene ese modelo.
                    pool = [k for k in ia if nrm(k[0]) == f["rubro"]] or list(ia)
                    vr, _ = EX.existe(f["nombre"] or f["consulta"], aislado=True)
                    vr = "no_hay" if vr == "no_hay" else "hay"
                elif f["identifica"]:  # marca o modelo sin rubro, "b760m ds3h gigabyte": toda la tienda, y existe
                    pool = list(ia)
                    vr, _ = EX.existe(f["nombre"] or f["consulta"], aislado=True)
                elif variante == "sin rubro no ofrece":
                    res.append((f["consulta"], "sin rubro", []))
                    continue
                else:
                    pool = list(ia)
                    vr, _ = EX.existe(f["nombre"] or f["consulta"], aislado=True)
                res.append((f["consulta"], vr, sorted(pool, key=lambda k: -dot(q, ia[k]))[:5]))
            M.contar(e, res, n, fallas)
        print(f"\n{variante}: filas que ofrecen {n[('fila', '', 'ofrece')]}")
        for (a, g, k), c in sorted(n.items()):
            print(f"  {a:8} {g:10} {k:24} {c}")
        if ver:
            for x in sorted(fallas):
                print("   ", x)


def medir_dato2(ver):
    """El dato 2 contra `dato2.py`, por pedido: las filas de Luna del mismo rubro, o todas si ninguna lo trae.
    Exacto: alguna opcion de Luna esta entre las etiquetadas. Grupo: base contra especifico. Y los temas de la FAQ que
    la frase pregunta aparte: cuantos trae Luna."""
    ex, luna = cargar()
    n, fallas = collections.Counter(), []
    for e in ex:
        ts = (luna[e["id"]]["salida"] or {}).get("textos") or []
        filas = [(f["rubro"], dato2(t)[0]) for t in ts for f in leer(t)[:1]]
        todo = sorted({x for _, d in filas for x in d})
        por_pedido, temas = etiqueta_dato2(e["id"])
        # Los temas de la FAQ se contestan por la tienda, no por producto: van a la frase, vengan en la fila que vengan.
        # La garantia de un producto se cuenta como el tema garantia: la contesta la ficha o la FAQ, lo decide el codigo.
        prod = lambda ds: sorted(x for x in ds if not x.startswith("tema:") and x not in BASE)
        tema = lambda ds: {("garantia" if x == "campo:garantia" else x.split(":", 1)[1]) for x in ds
                           if x.startswith("tema:") or x == "campo:garantia"}
        for p, et in zip(e["pedidos"], por_pedido):
            rs = {X.CONC[i]["nombre"] for c in p["cas"] if c["tipo"] == "rubro" for i in X._ids(c)}
            mias = [d for r, d in filas if r and r in {nrm(x) for x in rs}]
            luna_d = sorted({x for d in mias for x in d}) if mias else todo
            et_p = [x for x in prod(et) if x != "campo:garantia"]
            lu_p = [x for x in prod(luna_d) if x != "campo:garantia"]
            n["pedidos"] += 1
            k = ("base" if not et_p else "dato de la ficha") + " -> " + ("base" if not lu_p else "dato de la ficha")
            n["pedido " + k] += 1
            if bool(et_p) != bool(lu_p):
                fallas.append(f"{e['id']} pedido {k}: etiqueta {et} luna {luna_d} {e['texto'][:60]!r}")
        et_t = tema([x for d in por_pedido for x in d]) | set(temas)
        lu_t = tema(todo)
        n["temas etiquetados"] += len(et_t)
        n["temas que trae Luna"] += len(et_t & lu_t)
        n["temas de mas"] += len(lu_t - et_t)
        if et_t != lu_t:
            fallas.append(f"{e['id']} temas: falta {sorted(et_t - lu_t)} de mas {sorted(lu_t - et_t)} {e['texto'][:60]!r}")
    print(f"\ndato 2: pedidos {n['pedidos']}")
    for k in sorted(k for k in n if k.startswith("pedido ")):
        print(f"  {k:40} {n[k]}")
    print(f"  temas de la FAQ: etiquetados {n['temas etiquetados']}, los trae Luna {n['temas que trae Luna']},"
          f" de mas {n['temas de mas']}")
    if ver:
        for f in fallas:
            print("   ", f)


if __name__ == "__main__":
    if "--dato2" in sys.argv:
        medir_dato2("--ver" in sys.argv)
    else:
        main("--ver" in sys.argv)
