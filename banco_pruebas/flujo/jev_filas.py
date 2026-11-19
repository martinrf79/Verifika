"""JEV ELIGE, FILA POR FILA, ENTRE LOS CANDIDATOS QUE TRAEN LOS EMBEDDINGS (19-nov-2026).

Orden de Martin del 19-nov: la llamada 0 solo separa y corrige la ortografia, v13; los embeddings de cada fila traen los
candidatos de la fuente de la tienda y Jev elige. Este guion mide esa eleccion sobre 300 mensajes: las 200 de control,
`bancos/las200.json`, y los 100 negativos y mixtos, `bancos/negativos100.py`.

  candidatos   por seccion, como `busqueda_fuente.py`: los 15 productos mas parecidos a la fila, los 3 documentos de
               rubro, con lo que la tienda declara que no vende, y los 3 de tema.
  filtro       si la fila trae algo de `no_vendidas.json`, palabra entera o frase sin tildes, la respuesta de producto es
               "no se vende: <clave>" y a Jev no se le pregunta el producto de esa fila.
  Jev          una llamada por mensaje, con el mensaje entero de estado y, por fila i, "p<i>" producto y "t<i>" tema.
  grabado      `grabado/jev_filas_v13.jsonl`, un mensaje por linea; lo ya grabado no se repite.
  calificacion a nivel mensaje, sin gasto, sobre lo grabado.

    python3 banco_pruebas/flujo/jev_filas.py            # corre lo que falta y califica
    python3 banco_pruebas/flujo/jev_filas.py --calificar   # solo califica
    python3 banco_pruebas/flujo/jev_filas.py --corrida b   # la segunda corrida: sin filtro de codigo y otra regla del accesorio
    python3 banco_pruebas/flujo/jev_filas.py --calificar --corrida b
"""
import collections
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(AQUI, "bancos"))
from entorno import GRABADO  # noqa: E402

PROMPT = "v13"
# Dos corridas. La "a" es la primera: el filtro de codigo decide por palabra y la regla del accesorio. La "b" saca el
# filtro (la clave de no_vendidas.json que trae la fila solo suma una opcion para Jev) y cambia la regla del accesorio.
CORRIDA = sys.argv[sys.argv.index("--corrida") + 1] if "--corrida" in sys.argv else "a"
SALIDA = os.path.join(GRABADO, "jev_filas_v13.jsonl" if CORRIDA == "a" else f"jev_filas_v13{CORRIDA}.jsonl")
CUALQUIERA = "cualquier producto de la tienda"
REGLA_A = ('Si pide un accesorio, un repuesto o algo para usar con el, como cartuchos para una impresora o un soporte para '
           'un monitor, es ninguno.')
REGLA_B = 'Si pide un producto que no es ninguno de los de la lista, aunque sea para usar con uno de ellos, es ninguno.'
INSTR_P = ('En la parte "{f}" del mensaje, ¿cual de estos tipos de producto de la tienda pide el cliente? Elegi uno solo si '
           'lo que pide esa parte ES ese producto. ' + (REGLA_A if CORRIDA == "a" else REGLA_B) + ' Si nombra opciones, como dos modelos, '
           'elegi el tipo de producto, sin elegir el modelo. Si se refiere a algo sin decir que es, como "los otros dos", '
           'es ninguno.')
if CORRIDA in ("c", "d"):
    # Consigna libre, 19-nov: sin reglas, el mensaje entero y "si ninguna corresponde, ninguno". La d ofrece los 15
    # productos candidatos en vez de los rubros.
    INSTR_P = ('Leé el mensaje entero del cliente. En la parte "{f}", ¿cual de estas opciones corresponde a lo que el cliente '
               'pide o pregunta? Si ninguna corresponde, ninguno.')
    if CORRIDA == "d":
        INSTR_P = ('Leé el mensaje entero del cliente. En la parte "{f}", ¿cual de estos productos de la tienda corresponde a lo '
                   'que el cliente pide o pregunta? Si pide un tipo de producto en general, elegí el que mejor le corresponda de '
                   'ese tipo. Si ninguno corresponde, ninguno.')
    INSTR_T = ('Leé el mensaje entero del cliente. En la parte "{f}", ¿cual de estas reglas de la tienda corresponde a lo que '
               'el cliente pregunta? Si ninguna corresponde, ninguno.')
else:
    INSTR_T = ('En la parte "{f}" del mensaje, ¿el cliente pregunta por alguna de estas reglas de la tienda? Elegi una solo si '
               'la pregunta es sobre eso. Si pregunta algo que ninguna cubre, es ninguno.')


def _mensajes():
    """[(banco, id, texto, filas)] de los 300: las 200 y los 100 negativos, con las filas del v13."""
    from negativos100 import CASOS
    sal = {(r["banco"], r["id"]): r["salida"]["textos"] for r in map(json.loads, open(os.path.join(GRABADO, "llamada0_modelos.jsonl")))
           if r.get("prompt") == PROMPT and r.get("salida")}
    out = []
    for c in json.load(open(os.path.join(AQUI, "bancos", "las200.json")))["casos"]:
        out.append((c["banco"], c["id"], c["texto"], sal[(c["banco"], c["id"])]))
    for cid, texto, _ in CASOS:
        out.append(("neg100", cid, texto, sal[("neg100", cid)]))
    return out


def _fuente():
    import nexo_rubro as NR
    import nexo_tema as NT
    from app.core.flujo.nuevo import vectores as VV
    _, alias, rubros, modelos = NR.fuente()
    pos, vec, dim = VV.indice(NR.TID)

    def v(d):
        return vec[pos[d] * dim:(pos[d] + 1) * dim]
    rub = [(r, v(d)) for r, d in NR.indice_rubros(rubros, alias)]
    prod = [(k, v(NR.doc_producto(k, modelos[k], alias))) for k in modelos]
    faq, _ = NT.fuente()
    tema = [(t, v(a)) for t, a in NT.docs(*NT.fuente())]
    nx = SimpleNamespace(faq={f["tema"]: f for f in faq})
    nv = json.load(open(os.path.join(NR._A.DATOS, NR.TID, "no_vendidas.json"), encoding="utf-8"))["no_vendidas"]
    return SimpleNamespace(modelos=modelos, NR=NR, NT=NT, alias=alias, rub=rub, prod=prod, tema=tema, nx=nx,
                           no_vendidas=sorted(nv, key=lambda x: -len(NR.n(x))))


def _top(q, idx, n):
    s = sorted(((sum(a * b for a, b in zip(q, x)), i) for i, (_, x) in enumerate(idx)), reverse=True)[:n]
    return [idx[i][0] for _, i in s]


def _filtro(F, fila):
    """La clave de no_vendidas.json que trae la fila, palabra entera o frase, o None."""
    t = f" {F.NR.n(fila)} "
    return next((k for k in F.no_vendidas if f" {F.NR.n(k)} " in t), None)


def _candidatos(F, q):
    prods = _top(q, F.prod, 15)
    docs = _top(q, F.rub, 3)
    temas = list(dict.fromkeys(_top(q, F.tema, 3)))
    ej = collections.defaultdict(list)
    for k in prods:
        ej[k[0]].append(f"{k[1]} {k[2]}")
    rubros = list(dict.fromkeys([k[0] for k in prods] + [d for d in docs if not d.startswith(F.NR.NO_SE_VENDE)]))
    # Corrida e: los 5 productos mas parecidos de cada rubro, de los 15; si el rubro entro solo por su documento, de todo el catalogo.
    por_rubro = collections.defaultdict(list)
    for k in prods:
        por_rubro[k[0]].append(k)
    ej_e = {}
    for r in rubros:
        ks = por_rubro[r][:5] or _top(q, [x for x in F.prod if x[0][0] == r], 5)
        ej_e[r] = [F.modelos[k][0]["nombre"] for k in ks]
    return {"productos": [list(k) for k in prods], "ejemplos_e": ej_e, "rubros": rubros, "ejemplos": {r: ej[r][:5] for r in rubros}, "no_se_vende": [d for d in docs if d.startswith(F.NR.NO_SE_VENDE)],
            "temas": temas}


def _opciones_d(F, c):
    """Corrida d: {clave: (rubro, descripcion)} de los 15 productos candidatos. La clave es "<marca> <modelo>" y, si se
    repite, el mismo modelo en dos rubros, lleva el rubro; la descripcion, el rubro y el nombre del catalogo."""
    cuenta = collections.Counter(f"{m} {mo}" for _, m, mo in c["productos"])
    out = {}
    for r, m, mo in c["productos"]:
        clave = f"{m} {mo}" if cuenta[f"{m} {mo}"] == 1 else f"{m} {mo} ({r})"
        out[clave] = (r, f"{r}: {F.modelos[(r, m, mo)][0]['nombre']}")
    return out


def _preguntas(F, filas, cands, filtros):
    qs = {}
    for i, f in enumerate(filas):
        c = cands[i]
        if CORRIDA != "a" or filtros[i] is None:
            crit = {}
            if CORRIDA == "d":
                crit = {k: d for k, (_, d) in _opciones_d(F, c).items()}
            elif CORRIDA == "e":
                crit = {r: f"{r}: en la tienda, por ejemplo: {', '.join(c['ejemplos_e'][r])}" for r in c["rubros"]}
            else:
                for r in c["rubros"]:
                    crit[r] = f"{r}: tambien se dice {', '.join(F.alias.get(r, [])[:12])}; en la tienda, por ejemplo: {', '.join(c['ejemplos'][r])}"
            nsv = list(c["no_se_vende"])
            if CORRIDA in ("b", "c", "e") and filtros[i] is not None and F.NR.NO_SE_VENDE + filtros[i] not in nsv:
                nsv.append(F.NR.NO_SE_VENDE + filtros[i])  # la clave de la fila es solo una opcion mas: Jev decide
            for d in nsv:
                crit[d] = f"la tienda declara que no vende {d[len(F.NR.NO_SE_VENDE):]}"
            crit[CUALQUIERA] = "pregunta por todos los productos de la tienda, como el articulo mas caro"
            crit["ninguno"] = "no pide un producto, o pide uno que no es ninguno de estos"
            qs[f"p{i}"] = {"type": "choice", "criteria": crit, "instructions": INSTR_P.format(f=f)}
        crit = {t: F.NT._desc(F.nx, t) for t in c["temas"]}
        crit["ninguno"] = "no pregunta por ninguna de estas"
        qs[f"t{i}"] = {"type": "choice", "criteria": crit, "instructions": INSTR_T.format(f=f)}
    return qs


def correr():
    from jev import llamar_jev
    msgs = _mensajes()
    hechos = set()
    if os.path.exists(SALIDA):
        hechos = {(r["banco"], r["id"]) for r in map(json.loads, open(SALIDA))}
    falta = [m for m in msgs if (m[0], m[1]) not in hechos]
    print(f"{len(msgs)} mensajes, {len(hechos)} ya grabados, {len(falta)} por correr")
    if not falta:
        return
    import embeddings as EMB
    F = _fuente()
    textos = [t for m in falta for t in m[3]]
    q = dict(zip(textos, EMB.pedir(textos, EMB.CONSULTA, EMB.cargar(), callado=True)))
    lock, errores = threading.Lock(), []

    def uno(m):
        if len(errores) >= 3:
            return
        banco, cid, texto, filas = m
        cands = [_candidatos(F, q[t]) for t in filas]
        filtros = [_filtro(F, t) for t in filas]
        qs = _preguntas(F, filas, cands, filtros)
        try:
            # Sin filas no hay pregunta que hacer, y la API rechaza el pedido vacio con 422: se graba sin llamar.
            r, tokens = ({}, 0) if not qs else llamar_jev(f"MENSAJE DEL CLIENTE: {texto}", qs, "jev_filas_v13" + CORRIDA)
        except Exception as e:  # noqa: BLE001
            errores.append((banco, cid, repr(e)))
            print("ERROR", banco, cid, repr(e))
            return
        rec = {"banco": banco, "id": cid, "mensaje": texto, "filas": filas, "candidatos": cands, "filtro": filtros,
               "decide": CORRIDA == "a", "jev": r, "tokens": tokens}
        if CORRIDA == "d":
            rec["mapa"] = [{k: v[0] for k, v in _opciones_d(F, c).items()} for c in cands]
        with lock:
            with open(SALIDA, "a") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    with ThreadPoolExecutor(4) as ex:
        list(ex.map(uno, falta))
    if errores:
        raise SystemExit(f"Jev fallo, se paro: {errores}")


def _n(t):
    import nexo_rubro as NR
    return NR.n(t)


def _filas_con(palabras, filas):
    """Las filas que traen todas las palabras, cada una entera o en plural: "joysticks" toma "joystick", y "mousepad" ya
    no toma "mouse". Antes eran las primeras cinco letras y "mousepad" tomaba la fila "mouse inalambrico"."""
    def igual(a, b):
        return a == b or a + "s" == b or a + "es" == b or b + "s" == a or b + "es" == a
    ws = _n(palabras).split()
    return [i for i, f in enumerate(filas) if all(any(igual(w, x) for x in _n(f).split()) for w in ws)]


def _respuesta_p(r, i):
    """La respuesta de producto de la fila i: el filtro de codigo, solo en la corrida a, o lo que eligio Jev."""
    if r["filtro"][i] is not None and r.get("decide", True):
        return "no se vende: " + r["filtro"][i]
    x = r["jev"].get(f"p{i}", "ninguno")
    return r["mapa"][i].get(x, x) if r.get("mapa") else x  # corrida d: del producto elegido a su rubro


def _rubro(x):
    return x not in ("ninguno", CUALQUIERA) and not x.startswith("no se vende: ")


def calificar():
    import flujo_nuevo as FN
    import reales as RE
    from negativos100 import CASOS
    rs = {(r["banco"], r["id"]): r for r in map(json.loads, open(SALIDA))}
    esp = {}
    for b, cid, _, cs, _ in FN.bancos():
        esp[(b, cid)] = ({r for _, r in cs if r and r != "ninguno"}, [])
    for c in RE.CASOS:
        esp[("reales", c[0])] = (set(c[2].get("rubros") or []), [])
    for cid, _, x in RE.casos_525()[0]:
        esp[("reales525", cid)] = (set(x.get("rubros") or []), [set(t) for t in x.get("temas") or []])
    casos200 = [(c["banco"], c["id"]) for c in json.load(open(os.path.join(AQUI, "bancos", "las200.json")))["casos"]]

    def elegidos(r):
        n = len(r["filas"])
        ps = [(i, _respuesta_p(r, i)) for i in range(n)]
        ts = [(i, r["jev"].get(f"t{i}", "ninguno")) for i in range(n)]
        return ps, ts
    c, errores = collections.Counter(), []
    for k in casos200:
        if k not in rs:
            continue
        r = rs[k]
        ps, ts = elegidos(r)
        rubros_e, temas_e = esp.get(k, (set(), []))
        el_r = {x for _, x in ps if _rubro(x)}
        el_t = {x for _, x in ts if x != "ninguno"}
        for x in rubros_e:
            c["200 rubros esperados"] += 1
            if x in el_r:
                c["200 rubros esperados elegidos"] += 1
            else:
                errores.append((k[1], "200 rubro no elegido", [f"p{i}={x2}" for i, x2 in ps], sorted(rubros_e)))
        for x in el_r - rubros_e:
            c["200 rubros de mas"] += 1
            fila = next(i for i, x2 in ps if x2 == x)
            errores.append((k[1], "200 rubro de mas", f"fila {fila} {r['filas'][fila]!r}: {x}", sorted(rubros_e)))
        for alt in temas_e:
            c["200 temas esperados"] += 1
            if alt & el_t:
                c["200 temas esperados elegidos"] += 1
            else:
                errores.append((k[1], "200 tema no elegido", [f"t{i}={x2}" for i, x2 in ts], sorted(alt)))
        union = set().union(*temas_e) if temas_e else set()
        for x in el_t - union:
            c["200 temas de mas"] += 1
            fila = next(i for i, x2 in ts if x2 == x)
            errores.append((k[1], "200 tema de mas", f"fila {fila} {r['filas'][fila]!r}: {x}", sorted(union)))
    for cid, texto, e in CASOS:
        k = ("neg100", cid)
        if k not in rs:
            continue
        r = rs[k]
        ps, ts = elegidos(r)
        el_r = {x for _, x in ps if _rubro(x)}
        el_t = {x for _, x in ts if x != "ninguno"}
        for x in e["rubros"]:
            c["neg rubros esperados"] += 1
            if x in el_r:
                c["neg rubros esperados elegidos"] += 1
            else:
                errores.append((cid, "neg rubro no elegido", [f"p{i}={x2}" for i, x2 in ps], e["rubros"]))
        for alt in e["temas"]:
            c["neg temas esperados"] += 1
            if set(alt) & el_t:
                c["neg temas esperados elegidos"] += 1
            else:
                errores.append((cid, "neg tema no elegido", [f"t{i}={x2}" for i, x2 in ts], alt))
        for w in e["no_vende"]:
            c["neg no_vende"] += 1
            fs = _filas_con(w, r["filas"])
            if not fs:
                c["neg no_vende sin fila"] += 1
                errores.append((cid, "neg no_vende sin fila", w, "ninguno o no se vende"))
                continue
            i = fs[0]
            x = dict(ps)[i]
            if x == "ninguno" or x.startswith("no se vende: "):
                c["neg no_vende acierto"] += 1
                if r["filtro"][i] is not None and r.get("decide", True):
                    c["neg no_vende acierto por el filtro"] += 1
            else:
                c["neg no_vende error"] += 1
                errores.append((cid, "neg no_vende", f"fila {i} {r['filas'][i]!r} ({w}): eligio {x}", "ninguno o no se vende"))
        for w in e["fuera"]:
            c["neg fuera"] += 1
            fs = _filas_con(w, r["filas"])
            if not fs:
                c["neg fuera sin fila"] += 1
                errores.append((cid, "neg fuera sin fila", w, "ninguno o " + ", ".join(e["tolera"])))
                continue
            i = fs[0]
            x = dict(ts)[i]
            if x == "ninguno" or x in e["tolera"]:
                c["neg fuera acierto"] += 1
            else:
                c["neg fuera error"] += 1
                errores.append((cid, "neg fuera", f"fila {i} {r['filas'][i]!r} ({w}): eligio {x}", "ninguno o " + ", ".join(e["tolera"])))
        for x in el_r - set(e["rubros"]):
            c["neg rubros de mas"] += 1
    n200 = sum(k in rs for k in casos200)
    print(f"LAS 200 ({n200} mensajes): rubros esperados elegidos {c['200 rubros esperados elegidos']} de {c['200 rubros esperados']}"
          f" · rubros de mas {c['200 rubros de mas']} · temas esperados elegidos {c['200 temas esperados elegidos']} de {c['200 temas esperados']}"
          f" · temas de mas {c['200 temas de mas']}")
    nneg = sum(("neg100", x[0]) in rs for x in CASOS)
    print(f"LOS 100 NEGATIVOS ({nneg} mensajes): rubros esperados elegidos {c['neg rubros esperados elegidos']} de {c['neg rubros esperados']}"
          f" · rubros de mas {c['neg rubros de mas']}")
    print(f"  lo que no vende: acierto {c['neg no_vende acierto']} de {c['neg no_vende']} (por el filtro de codigo {c['neg no_vende acierto por el filtro']})"
          f" · error {c['neg no_vende error']} · sin fila {c['neg no_vende sin fila']}")
    print(f"  fuera de la FAQ: acierto {c['neg fuera acierto']} de {c['neg fuera']} · error {c['neg fuera error']} · sin fila {c['neg fuera sin fila']}")
    print(f"  temas esperados elegidos {c['neg temas esperados elegidos']} de {c['neg temas esperados']}")
    tok = sum(r["tokens"] for r in rs.values())
    print(f"JEV: {len(rs)} mensajes grabados, {tok} tokens de entrada")
    print(f"\nERRORES ({len(errores)})")
    for e in errores:
        print(f"  {e[0]:6} {e[1]:24} elegido: {e[2]} · esperado: {e[3]}")


if __name__ == "__main__":
    if "--calificar" not in sys.argv:
        correr()
    calificar()
