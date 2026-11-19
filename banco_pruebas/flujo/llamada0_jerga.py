"""LA LLAMADA 0 CON LA JERGA ENTRE CORCHETES, SOBRE LAS 200 DIFICILES (18-nov-2026).

Orden de Martin del 18-nov. La llamada 0 es Luna con el prompt v8, `llamada0_modelos.PROMPTS["v8"]`: separa una linea por
cosa, traduce lo que puede, escribe el destino, y lo que no traduce lo deja con las palabras del cliente entre corchetes.
Solo lo que esta entre corchetes pasa por los embeddings: sus palabras contra los productos de la tienda traen 8
candidatos, y sus rubros, con esos productos de ejemplo, van a Jev con el mensaje entero. Jev elige uno, o ninguno. Con
eso la llamada 0 queda completa. Nada de la tienda llega a Luna.

LAS 200, `bancos/las200.json`, todas preguntas iniciales, sin memoria, elegidas por lo que ya fallo en lo grabado:
  - los 40 reales enteros;
  - las 73 preguntas de las 58 y las K, en la forma que mas perdio condiciones o marco "?" en todas las corridas;
    las 21 que fallaron en dos formas o mas, tambien en la segunda;
  - de las 140, las 60 que fallaron en alguna corrida de cualquier modelo o prompt, y las 6 de mas cosas pedidas que
    nunca fallaron.

    python3 banco_pruebas/flujo/llamada0_jerga.py --armar          # arma las 200, sin gasto
    python3 banco_pruebas/flujo/llamada0_modelos.py --correr luna v8 --banco 200
    python3 banco_pruebas/flujo/llamada0_jerga.py --jerga          # embeddings y Jev de lo que quedo entre corchetes
    python3 banco_pruebas/flujo/llamada0_jerga.py --ver            # cada mensaje con sus lineas, para leerlo
"""
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from entorno import GRABADO  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
LAS200 = os.path.join(AQUI, "bancos", "las200.json")
CORRIDA = "luna"
# El prompt de la corrida, "--prompt v10"; sin el, el v8 del 18-nov.
PROMPT = sys.argv[sys.argv.index("--prompt") + 1] if "--prompt" in sys.argv else "v8"
JERGA = os.path.join(GRABADO, f"llamada0_jerga_{PROMPT}.jsonl")
K = 8
FORMAS = ("whatsapp", "coloquial", "plano", "redactada", "original")


def armar():
    import llamada0_modelos as L
    import flujo_nuevo as F
    import nexo_rubro as NR
    import reales as RE
    # Las 140: cuantas corridas fallaron cada mensaje, con la vara de `llamada0_vara.py`.
    bancos = {cid: (b, t, d, cs) for b, cid, t, cs, d in F.bancos()}
    fallas = collections.Counter()
    for _, rs in L.corridas().items():
        for cid, r in rs.items():
            if r.get("salida") and L.calificar_mensaje(cid, bancos[cid][1], bancos[cid][2], r["salida"]["lineas"])[1]:
                fallas[cid] += 1
    # El "?" de la v7, por mensaje.
    q7 = collections.Counter()
    for r in L.filas():
        if r["prompt"] == "v7" and r.get("salida"):
            q7[(r["banco"], r["id"])] += sum(l.get("producto") == "?" for l in r["salida"]["lineas"])
    # Las 365: las condiciones perdidas en todas las corridas.
    alias = NR.fuente()[1]
    esp = L.esperado_reales("reales525")
    textos = {cid: t for _, cid, t in L.casos_de("reales525")}
    perd = collections.Counter()
    for _, rs in L.corridas_reales("reales525").items():
        for cid, e in esp.items():
            r = rs.get(cid)
            if e and r and r.get("salida"):
                c = L.donde_se_pierde(textos[cid], r["salida"]["lineas"], e, alias)
                perd[cid] += c["condiciones"] - c["en la busqueda"]
    casos = [{"banco": "reales", "id": c[0], "texto": c[1], "por": "real"} for c in RE.CASOS]
    por_pregunta = collections.defaultdict(list)
    for cid, t, _ in RE.casos_525()[0]:
        p, tu, forma = cid.split(".")
        por_pregunta[f"{p}.{tu}"].append((perd[cid] + q7[("reales525", cid)], -FORMAS.index(forma), cid, t))
    for k, fs in por_pregunta.items():
        fs.sort(reverse=True)
        casos.append({"banco": "reales525", "id": fs[0][2], "texto": fs[0][3], "por": f"la forma mas dificil, {fs[0][0]}"})
        if sum(1 for f in fs if f[0]) >= 2:
            casos.append({"banco": "reales525", "id": fs[1][2], "texto": fs[1][3], "por": f"segunda forma dificil, {fs[1][0]}"})
    falla140 = [cid for cid in bancos if fallas[cid]]
    multi = sorted((cid for cid in bancos if not fallas[cid]), key=lambda c: (-len(bancos[c][3]), -len(bancos[c][2]), c))
    for cid in falla140:
        casos.append({"banco": bancos[cid][0], "id": cid, "texto": bancos[cid][1], "por": f"fallo en {fallas[cid]} corridas"})
    for cid in multi[:200 - len(casos)]:
        casos.append({"banco": bancos[cid][0], "id": cid, "texto": bancos[cid][1],
                      "por": f"{len(bancos[cid][3])} cosas pedidas, nunca fallo"})
    assert len(casos) == 200, len(casos)
    json.dump({"de_donde": "18-nov, orden de Martin: las 200 dificiles, preguntas iniciales sin memoria, "
                           "`llamada0_jerga.py --armar`. Congeladas: no se tocan.", "casos": casos},
              open(LAS200, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(collections.Counter(c["banco"] for c in casos))


def salidas():
    """{(banco, id): lineas} de la v8 sobre las 200."""
    import llamada0_modelos as L
    return {(r["banco"], r["id"]): r["salida"]["lineas"] for r in L.filas()
            if r["corrida"] == CORRIDA and r["prompt"] == PROMPT and r.get("salida")}


def entre_corchetes(producto):
    m = re.search(r"\[([^\]]*)\]", str(producto or ""))
    return m.group(1).strip() if m else None


def jerga():
    """Los embeddings y Jev de cada linea con corchetes. Graba en `llamada0_jerga_v8.jsonl`; lo hecho no se repite."""
    import embeddings as EMB
    import nexo_rubro as NR
    from jev import llamar_jev
    from app.core.flujo.nuevo import vectores as VV
    from app.core.flujo.nuevo.rubro import DESC_NINGUNO, NINGUNO
    filas_, alias, _, modelos = NR.fuente()
    ms = list(modelos)
    docs = [NR.doc_producto(k, modelos[k], alias) for k in ms]
    pos, vec, dim = VV.indice(NR.TID)
    hechos = {(r["banco"], r["id"]) for r in map(json.loads, open(JERGA, encoding="utf-8"))} if os.path.exists(JERGA) else set()
    casos = {(c["banco"], c["id"]): c["texto"] for c in json.load(open(LAS200, encoding="utf-8"))["casos"]}
    sal = salidas()
    pend = [(k, t) for k, t in casos.items() if k in sal and k not in hechos
            and any(entre_corchetes(l.get("producto")) for l in sal[k])]
    print(f"[{len(pend)} mensajes con corchetes por resolver]", flush=True)
    cache = EMB.cargar()
    qs_txt = [entre_corchetes(l.get("producto")) for k, _ in pend for l in sal[k] if entre_corchetes(l.get("producto"))]
    vq = dict(zip(qs_txt, EMB.pedir(qs_txt, EMB.CONSULTA, cache)))
    for k, texto in pend:
        qs, info = {}, {}
        for i, l in enumerate(sal[k]):
            q = entre_corchetes(l.get("producto"))
            if not q:
                continue
            pts = []
            for m, d in zip(ms, docs):
                v = vec[pos[d] * dim:(pos[d] + 1) * dim]
                pts.append((round(sum(a * b for a, b in zip(vq[q], v)), 4), m))
            cerca = [m for _, m in sorted(pts, reverse=True)[:K]]
            rubros = list(dict.fromkeys(m[0] for m in cerca))
            ej = {r: [f"{m[1]} {m[2]}" for m in cerca if m[0] == r] for r in rubros}
            info[f"p{i}"] = {"linea": i, "palabras": q, "candidatos": cerca, "rubros": rubros}
            qs[f"p{i}"] = {"type": "choice",
                           "criteria": {r: f"{r}, que tambien se dice {', '.join(alias.get(r, [])[:12])}; en la tienda, "
                                           f"por ejemplo: {', '.join(ej[r][:5])}" for r in rubros} | {NINGUNO: DESC_NINGUNO},
                           "instructions": f"En la parte \"{l.get('fragmento')}\" del mensaje, el cliente escribio "
                                           f"\"{q}\". Que tipo de producto de la tienda pide? Si la tienda no tiene ese "
                                           "tipo de producto, ninguno."}
        r, tok = llamar_jev(f"MENSAJE DEL CLIENTE: {texto}", qs, f"llamada0_jerga_{PROMPT}")
        with open(JERGA, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"banco": k[0], "id": k[1], "jev": r, "tokens": tok,
                                 "preguntas": {q: {**info[q], "elige": r.get(q)} for q in qs}}, ensure_ascii=False) + "\n")
        print(f"  {k[1]}: " + "; ".join(f"[{info[q]['palabras']}] -> {r.get(q)}" for q in qs), flush=True)


def ver():
    casos = json.load(open(LAS200, encoding="utf-8"))["casos"]
    sal = salidas()
    jg = {(r["banco"], r["id"]): r for r in map(json.loads, open(JERGA, encoding="utf-8"))} if os.path.exists(JERGA) else {}
    for c in casos:
        k = (c["banco"], c["id"])
        print(f"\n{c['id']} [{c['banco']}] {c['texto']}")
        if k not in sal:
            print("   SIN SALIDA")
            continue
        for i, l in enumerate(sal[k]):
            el = (jg.get(k) or {}).get("preguntas", {}).get(f"p{i}")
            print(f"   - {l.get('producto')!r} | {l.get('condiciones')!r} | @{l.get('destino') or ''}"
                  + (f"  => Jev: {el['elige']} de {el['rubros']}" if el else ""))


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--armar" in a:
        armar()
    elif "--jerga" in a:
        jerga()
    else:
        ver()
