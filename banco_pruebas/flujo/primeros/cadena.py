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


def _uno(ps):
    rubros = [n for _, n in ps if n and SECCION.get(n) == "PRODUCTOS"]
    preguntas = [n for _, n in ps if n and SECCION.get(n) == "PREGUNTAS"]
    caracts = [(p, n) for p, n in ps if n and SECCION.get(n) == "CARACTERISTICAS"]
    # La consulta es la fila entera de Luna: ya trae solo lo de ese pedido. Sacar lo marcado como pregunta perdia
    # caracteristicas que el vocabulario tiene como tema, "mecanico" en [teclado mecanico membrana].
    consulta = " ".join(p for p, _ in ps).strip()
    # Nombra un producto si trae rubro, marca o modelo, o palabras que Luna no supo poner en el vocabulario.
    suelto = any(n is None and len(re.sub(r"[^a-z0-9]", "", nrm(p))) > 2 for p, n in ps)
    identifica = any(n in ("marca", "modelo") for _, n in caracts)
    return {"rubro": rubros[0] if rubros else None, "consulta": consulta, "dato2": preguntas, "caracts": caracts,
            "identifica": identifica, "nombra": bool(rubros) or identifica or suelto}


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


def main(ver):
    ex, _ = M.cargar()
    luna = {json.loads(l)["id"]: json.loads(l) for l in open(os.path.join(AQUI, "luna_b.jsonl"))}
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
                    vr, _ = EX.existe(f["consulta"], aislado=True)
                    vr = "no_hay" if vr == "no_hay" else "hay"
                elif f["identifica"]:  # marca o modelo sin rubro, "b760m ds3h gigabyte": toda la tienda, y existe
                    pool = list(ia)
                    vr, _ = EX.existe(f["consulta"], aislado=True)
                elif variante == "sin rubro no ofrece":
                    res.append((f["consulta"], "sin rubro", []))
                    continue
                else:
                    pool = list(ia)
                    vr, _ = EX.existe(f["consulta"], aislado=True)
                res.append((f["consulta"], vr, sorted(pool, key=lambda k: -dot(q, ia[k]))[:5]))
            M.contar(e, res, n, fallas)
        print(f"\n{variante}: filas que ofrecen {n[('fila', '', 'ofrece')]}")
        for (a, g, k), c in sorted(n.items()):
            print(f"  {a:8} {g:10} {k:24} {c}")
        if ver:
            for x in sorted(fallas):
                print("   ", x)


if __name__ == "__main__":
    main("--ver" in sys.argv)
