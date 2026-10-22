"""LA FICHA NATIVA CONTRA LAS FICHAS — el pedido entero y las consultas, sin modelo (23-oct-2026).

EL PEDIDO: lo correcto es como queda despues del mensaje, armado con la memoria y lo que la ficha dice que cambio:
cada renglon que sigue, cada cambio aplicado, lo sacado afuera y lo agregado adentro. Se compara articulo por articulo:
que sea lo mismo, con su destino, su cantidad, su color y sus condiciones, que pueden ir en el articulo o en las
preferencias de todo el pedido. Lo que depende de otra cosa —"si es poca plata, cambialo"— vale de las dos formas.
LAS CONSULTAS: cada pregunta de la ficha tiene que estar, por lo que nombra.

Por turno: BIEN, el pedido y las consultas como la ficha; DUDO, no esta bien pero anoto una duda; MAL SIN AVISAR.
Es otra vara que la de `pregunta_razonada/calificar.py`: aquella miraba las acciones, esta el resultado.

    python3 banco_pruebas/pedido_documento/medir_ficha.py [--ver]
"""
import collections
import json
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(AQUI))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "banco_pruebas", "pregunta_razonada"))
os.chdir(REPO)
os.environ.pop("GEMINI_API_KEY_PROD", None)
from calificar import n, RUBRO_PAL, BARATO, NIEGA, producto_de, _lista  # noqa: E402
from fichas import CHARLAS  # noqa: E402
from app.core.flujo import catalogo as K  # noqa: E402


def palabras_de(que, mem: dict, rubro: str = "") -> list:
    if rubro:
        return RUBRO_PAL.get(rubro, [rubro])
    if isinstance(que, str) and re.fullmatch(r"[ML]\d+", que):
        p = producto_de(que, mem)
        return ([n(p["modelo"]).split()[0]] if p.get("modelo") else []) + RUBRO_PAL.get(p.get("categoria"), [])
    p = K.por_id(que, "verifika_prod") if isinstance(que, str) else {}
    return [n(p["modelo"]).split()[0]] if p and p.get("modelo") else []


def pedido_correcto(tu: dict) -> tuple:
    """([articulos], [renglones que tienen que salir], preferencia de orden para todo)."""
    mem = tu["mem"]
    arts = []
    for i, (cant, que, pid, dest) in enumerate(mem.get("L") or [], 1):
        p = producto_de(f"L{i}", mem)
        arts.append({"L": f"L{i}", "que": ([n(p["modelo"]).split()[0]] if p.get("modelo") else [])
                     + RUBRO_PAL.get(que, [que]), "cant": cant, "dest": dest, "color": "", "conds": [], "flex": False,
                     "opt": False})
    por_L = {a["L"]: a for a in arts}
    salen, orden_todo = [], False
    for o in tu["oro"]:
        refs = [r for r in _lista(o.get("cual")) if isinstance(r, str) and r.startswith("L")]
        if o["tipo"] == "SA":
            for r in refs:
                if o.get("si"):
                    por_L[r]["opt"] = True
                else:
                    salen.append(r)
                    arts.remove(por_L[r])
        elif o["tipo"] == "CA" and refs:
            for r in refs:
                a = por_L[r]
                if o.get("si") or o.get("preg"):
                    a["flex"] = True
                    continue
                if o.get("dest"):
                    a["dest"] = o["dest"]
                if o.get("cant") is not None:
                    a["cant"] = o["cant"]
                if o.get("que"):
                    a["que"] = palabras_de(o["que"], mem)
                if o.get("color"):
                    a["color"] = o["color"]
                a["conds"] += [c for c in o.get("conds") or [] if c["campos"] or c["pal"]]
                if o.get("orden") == "barato":
                    a["conds"].append({"pal": BARATO, "niega": False})
        elif o["tipo"] == "AG":
            q = palabras_de(o.get("que"), mem, o.get("rubro", "")) or o.get("libre") or []
            if o.get("resto"):
                q = q + ["demas", "resto", "otros"]
            arts.append({"L": "", "que": q, "cant": o.get("cant"), "dest": o.get("dest", ""), "color": o.get("color", ""),
                         "conds": list(o.get("conds") or []) + ([{"pal": BARATO, "niega": False}]
                                                                if o.get("orden") == "barato" else []),
                         "flex": False, "opt": bool(o.get("si") or o.get("opt") or o.get("alt"))})
        elif o["tipo"] == "ORD":
            orden_todo = True
    return arts, salen, orden_todo


def articulos(ficha: dict) -> list:
    out = []
    for g in _lista(ficha.get("pedido")):
        if not isinstance(g, dict):
            continue
        for it in _lista(g.get("items")):
            if isinstance(it, dict):
                out.append({**it, "destino": g.get("destino") or "",
                            "texto": n(" ".join(str(v) for v in it.values() if v not in (None, "")))})
    return out


def tiene(t: str, ws: list) -> bool:
    return any(re.search(rf"(?<![a-z0-9]){re.escape(n(w))}", t) for w in ws)


def comparar_articulo(a: dict, it: dict, prefs: str) -> list:
    """Lo que no coincide; [] si es el mismo y esta bien."""
    malos = []
    if a["dest"] and n(a["dest"]).replace(" capital", "").split()[0] not in n(it["destino"]):
        malos.append("destino")
    if a["cant"] is not None and K.entero(it.get("cantidad"), 1) != a["cant"]:
        malos.append("cantidad")
    if a["color"] and n(a["color"]) not in it["texto"]:
        malos.append("color")
    for c in a["conds"]:
        donde = [x for x in (it["texto"], prefs) if tiene(x, c["pal"])]
        if not donde or (c.get("niega") and not any(any(w in " " + x for w in NIEGA) for x in donde)):
            malos.append("condicion " + c["pal"][0])
    return malos


def consultas_bien(tu: dict, ficha: dict) -> list:
    """Las preguntas de la ficha que faltan."""
    mem = tu["mem"]
    cs = [c for c in _lista(ficha.get("consultas")) if isinstance(c, dict)]
    texto_c = [n(" ".join(str(v) for v in c.values())) for c in cs]
    todo_c = " ".join(texto_c)
    pago = ficha.get("pago") or {}
    destinos = " ".join(n(g.get("destino")) for g in _lista(ficha.get("pedido")) if isinstance(g, dict))
    faltan = []
    for o in tu["oro"]:
        t, ok = o["tipo"], True
        if t == "B":
            ok = any(tiene(x, RUBRO_PAL.get(o["rubro"], [o["rubro"]])) for x in texto_c)
        elif t in ("P", "CMP", "CO"):
            refs = _lista(o.get("cual"))
            ok = any(all(tiene(x, palabras_de(r, mem)[:1] + [r.lower()]) for r in refs) for x in texto_c) \
                and (not o.get("pal") or tiene(todo_c, o["pal"]))
        elif t == "E":
            d = n(o["dest"]).split()[0]
            ok = d in todo_c or (d in destinos and tiene(todo_c, ["envio", "costo", "cuenta", "total", "cuanto"]))
        elif t == "CU":
            if o.get("tope"):
                ok = K.entero(pago.get("tope_total")) == o["tope"]
            if o.get("reparto"):
                ms = [(K.entero(m.get("porcentaje")), n(m.get("medio"))) for m in _lista(pago.get("medios"))
                      if isinstance(m, dict)]
                ok = ok and all(any(p == pct and (medio is None or n(medio) in m) for p, m in ms)
                                for pct, medio in o["reparto"])
            if not o.get("tope") and not o.get("reparto"):
                ok = tiene(todo_c, ["cuenta", "total", "cuanto", "presupuesto", "costo"])
            if o.get("dest"):
                ok = ok and n(o["dest"]).split()[0] in todo_c + " " + destinos
        elif t == "PO":
            ok = tiene(todo_c, o["pal"])
        elif t == "EX":
            ok = "saber" in todo_c or "general" in todo_c
        elif t == "CL":
            ok = tiene(n(json.dumps(ficha.get("cliente") or {}, ensure_ascii=False)), o["pal"])
        if o.get("si") and t in ("P", "CO", "CU", "PO") and ok:
            ok = any(c.get("si") not in (None, "", "no", "ninguna") for c in cs) or t == "CU"
        if not ok and not o.get("opt"):
            faltan.append(t)
    return faltan


def calificar(tu: dict, salida: str) -> dict:
    try:
        ficha = json.loads(salida)
    except ValueError:
        return {"veredicto": "MAL SIN AVISAR", "fallas": ["no se pudo leer"], "dudas": []}
    arts, salen, orden_todo = pedido_correcto(tu)
    its = articulos(ficha)
    prefs = n(" ".join(str(x) for x in _lista(ficha.get("preferencias"))))
    fallas, usados = [], set()
    for a in sorted(arts, key=lambda a: a["opt"]):
        cand = [(comparar_articulo(a, it, prefs) if not a["flex"] else [], i) for i, it in enumerate(its)
                if i not in usados and (tiene(it["texto"], a["que"]) or (a["L"] and a["L"].lower() in it["texto"]))]
        if not cand:
            if not a["opt"]:
                fallas.append(f"falta {a['que'][0]} a {a['dest'] or 'sin destino'}")
            continue
        malos, i = min(cand, key=lambda x: len(x[0]))
        usados.add(i)
        if malos and not a["opt"]:
            fallas.append(f"{a['que'][0]}: {', '.join(malos)}")
    for i, it in enumerate(its):
        if i not in usados:
            fallas.append(f"sobra {it.get('producto')} a {it['destino']}" +
                          (" (tenia que salir)" if any(s.lower() in it["texto"] for s in salen) else ""))
    if orden_todo and not (tiene(prefs, BARATO) or all(tiene(it["texto"], BARATO) for it in its)):
        fallas.append("el orden para todo")
    fallas += [f"falta la consulta {t}" for t in consultas_bien(tu, ficha)]
    dudas = [d for d in _lista(ficha.get("dudas")) if str(d).strip()]
    return {"veredicto": "BIEN" if not fallas else ("DUDO" if dudas else "MAL SIN AVISAR"), "fallas": fallas,
            "dudas": dudas}


def main(ver: bool = False) -> None:
    filas = {(r["charla"], r["turno"]): r for r in map(json.loads, open(os.path.join(AQUI, "ficha.jsonl"),
                                                                          encoding="utf-8")) if not r.get("error")}
    cuenta, tipos, por_t = collections.Counter(), collections.Counter(), collections.Counter()
    dudas_en_bien = 0
    for ch in CHARLAS:
        for t, tu in enumerate(ch["turnos"]):
            r = filas.get((ch["id"], t))
            if not r:
                continue
            c = calificar(tu, r["salida"])
            cuenta[c["veredicto"]] += 1
            por_t[(t, c["veredicto"] == "BIEN")] += 1
            dudas_en_bien += c["veredicto"] == "BIEN" and bool(c["dudas"])
            for f in c["fallas"]:
                tipos[re.sub(r" a .*| [a-z0-9]+:.*", "", f) if f.startswith(("falta", "sobra")) else f.split(": ")[-1]] += 1
            if ver and c["veredicto"] != "BIEN":
                print(f"--- {ch['id']} t{t} {c['veredicto']}: {' '.join(tu['msg'].replace('|', '').split())[:200]}")
                print("    " + "\n    ".join(c["fallas"]))
                if c["dudas"]:
                    print(f"    dudas: {c['dudas']}")
    total = sum(cuenta[v] for v in ("BIEN", "DUDO", "MAL SIN AVISAR"))
    print(f"\nFICHA NATIVA · {total} turnos")
    print(f"  BIEN {cuenta['BIEN']} · DUDO {cuenta['DUDO']} · MAL SIN AVISAR {cuenta['MAL SIN AVISAR']}")
    print("  por turno de la charla: " + " · ".join(f"t{t}: {por_t[(t, True)]} de {por_t[(t, True)] + por_t[(t, False)]}"
                                                    for t in range(3)))
    print(f"  las fallas: {dict(tipos.most_common())}")
    print(f"  anoto dudas aunque estaba bien: {dudas_en_bien} de {cuenta['BIEN']}")
    fs = list(filas.values())
    print(f"  tokens por turno {sum(r['entrada'] + r['sale'] for r in fs) // len(fs)}, "
          f"de salida {sum(r['sale'] for r in fs) // len(fs)}, tiempo {sum(r['ms'] for r in fs) // len(fs)} ms")


if __name__ == "__main__":
    main("--ver" in sys.argv)
