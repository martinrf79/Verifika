"""EL LABORATORIO DEL INFORME — lo que el codigo sabe de cada parte antes de la segunda llamada, plan de Martin del 24-oct. Es banco.

La primera llamada separa el mensaje y reescribe cada parte completa: es la de `candidatos.py --pulida`, grabada en
`respuestas_modelo.jsonl`, asi que se vuelve a leer gratis. Sobre cada parte el codigo arma un INFORME, sin modelo:

  tienda    los rubros, temas y modelos mas parecidos por significado, y los que nombra por palabras.
  pedido    a que renglon del pedido o a que producto mostrado apunta, con puntaje y razones: lo que senalo el modelo,
            el destino, el modelo, el rubro y el color que la parte nombra, y el parecido con cada linea de la libreta.
  casos     los cinco casos resueltos mas parecidos del motor, `motor_casos.py`, sin los de la charla que se mide.
  premisas  lo que el cliente da por cierto y el codigo puede revisar: un monto "que me dijiste" contra lo mostrado.

La vara es la de `candidatos.py`: el rubro, el tema, el producto y lo de la charla escritos a mano en las 48 y las 58.
Cada vuelta del laboratorio se mide contra la anterior y contra la busqueda sola, sin gastar: la traduccion esta grabada
y los vectores en ~/.cache/verifika.

    python3 banco_pruebas/lab_informe.py [--ver] [--informe S01]
"""
import asyncio
import collections
import json
import os
import re
import sys

ARGS = sys.argv[1:]
VER = "--ver" in ARGS
INFORME = ARGS[ARGS.index("--informe") + 1] if "--informe" in ARGS else ""
sys.argv = [sys.argv[0]]
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import candidatos as CA  # noqa: E402  — la primera traduccion grabada, la vara y la busqueda por significado
import motor_casos as MC  # noqa: E402
from app.core.flujo import borrador as B  # noqa: E402
from app.core.flujo import catalogo as K  # noqa: E402
from app.core.flujo import interprete  # noqa: E402

CA.COMPLETA = CA.PULIDA = True
A, ET, TID = CA.A, CA.ET, CA.TID
MISMO_ESTADO = 0.05   # lo que suma al parecido un caso del mismo estado de la charla
CORTA = 4             # una parte de hasta tantas palabras solo se entiende con lo que pregunto el vendedor
# Lo que suma cada razon al puntaje de un renglon o un mostrado. El parecido con la linea de la libreta, de 0 a 1,
# desempata.
PESO = {"senala": 3.0, "senala lo mostrado": 2.0, "mostrado en el pedido": 3.0, "destino": 2.0, "modelo": 2.0,
        "rubro": 1.0, "color": 1.0, "todo": 3.0, "elige para el renglon": 3.5}
EMPATE = 0.3          # dos numeros a menos de esto del primero son la misma lectura: la parte apunta a los dos
_TODO = re.compile(r"\b(todo|todos|todas|ambos|ambas|los dos|las dos|cada uno|cada una)\b")


# ══ LA TIENDA ════════════════════════════════════════════════════════════════

def tienda(texto: str, cands: dict) -> dict:
    """Lo que la parte toca de la tienda: por significado, los tres primeros de cada capa; por palabras, lo que nombra."""
    from app.core.flujo.marcador import _productos, _rubros, _temas
    ws = [w for w in re.findall(r"[a-z0-9]+", K.n(texto)) if w not in K._RELLENO]
    nombra = {"rubro": sorted({r for _, r in _rubros(ws, TID)}),
              "tema": sorted({t for ts in _temas(texto, TID).values() for t in ts}),
              "producto": []}
    for tramo, _ in _productos(ws, TID):
        idt = K.identificar(tramo, "", TID)
        nombra["producto"].append(f"{tramo}: {idt['veredicto']}"
                                  + (f" {idt['producto']['nombre']}" if idt["veredicto"] == "exists" else ""))
    return {"parecido": {g: cands[g][:3] for g in ("rubro", "tema", "producto")}, "nombra": nombra}


# ══ EL PEDIDO ════════════════════════════════════════════════════════════════

def _familia(p: dict) -> str:
    return K.n(f"{p.get('marca') or ''} {p.get('modelo') or ''}")


def _dice(txt: str, frase: str) -> bool:
    frase = K.n(frase).strip()
    return bool(frase) and re.search(rf"\b{re.escape(frase)}\b", txt) is not None


def anclar(parte: dict, estado: dict, lib: str, mapa: dict) -> list:
    """Los numeros de la libreta a los que apunta la parte, del mas probable al menos, con su puntaje y sus razones."""
    txt = K.n(f"{parte.get('texto') or ''} {parte.get('destino') or ''}")
    nums = interprete.numeros(estado)
    b = B.leer(estado.get("borrador"))
    res = {x["L"]: x for x in (B.resolver(b, TID) if b["renglones"] else [])}
    nota = collections.defaultdict(float)
    razones = collections.defaultdict(list)

    def suma(ref, razon):
        nota[ref] += PESO[razon]
        razones[ref].append(razon)

    for s in parte.get("senala") or []:
        r = CA._ref(s, False)
        if r.startswith("L-") and r in nums:
            suma(r, "senala")
        elif r.startswith("M-") and r in nums:
            suma(r, "senala lo mostrado")
            for L in mapa.get(r) or []:
                suma(L, "mostrado en el pedido")
    elegidos = {}  # el rubro de cada producto mostrado que la parte senala o nombra
    for k, pid in nums.items():
        if k[0] == "M":
            p = K.por_id(pid, TID)
            if k in [CA._ref(s, False) for s in parte.get("senala") or []] or (_familia(p) and _familia(p) in txt):
                elegidos[pid] = p.get("categoria")
    todo = bool(_TODO.search(txt))
    for r in b["renglones"]:
        L = r["L"]
        if todo:
            suma(L, "todo")
        if r.get("destino") and _dice(txt, r["destino"]):
            suma(L, "destino")
        prods = [K.por_id(a["id"], TID) for a in (res.get(L) or {}).get("articulos") or []]
        if any(_familia(p) and _familia(p) in txt for p in prods):
            suma(L, "modelo")
        rubros = {p.get("categoria") for p in prods} | ({r["que"]} if K.solo_rubro(r["que"], TID) else set())
        if any(_dice(txt, x) for x in rubros if x):
            suma(L, "rubro")
        colores = {r.get("color")} | {p.get("color") for p in prods}
        if any(_dice(txt, c) for c in colores if c):
            suma(L, "color")
        # Un mostrado del rubro del renglon, que el renglon no tiene, es elegir para ese renglon: "el JBL, el de mi hija".
        ids = {str(p.get("id")) for p in prods}
        if any(rub in rubros and pid not in ids for pid, rub in elegidos.items()):
            suma(L, "elige para el renglon")
    for k, pid in nums.items():
        if k[0] != "M":
            continue
        p = K.por_id(pid, TID)
        if _familia(p) and _familia(p) in txt:
            suma(k, "modelo")
    # El parecido con cada linea de la libreta desempata, y trae lo que ninguna razon nombra.
    charla = ET._charla(lib)
    if charla:
        q = ET.vectores([str(parte.get("texto") or "")])[0]
        for k, v in zip(charla, ET.vectores(list(charla.values()))):
            nota[k] += ET._coseno(v, q)
    return [(k, round(nota[k], 2), razones[k]) for k in sorted(nota, key=lambda x: -nota[x])]


def primeros(pedido: list) -> list:
    """Los numeros a los que apunta la parte: el primero y los empatados con el, si tienen alguna razon. Sin ninguna
    razon, el parecido solo no alcanza para senalar: no apunta a nada."""
    if not any(z for _, _, z in pedido):
        return []
    top = pedido[0][1]
    return [k for k, s, z in pedido if s >= top - EMPATE and (z or k == pedido[0][0])]


# ══ LOS CASOS Y LAS PREMISAS ═════════════════════════════════════════════════

def casos(parte: dict, turno: dict, todos: list) -> list:
    """Los cinco casos mas parecidos. La pregunta del vendedor solo pesa en una parte corta, y el estado suma sin
    excluir: con el pedido armado, "lo de Concordia mandalo a Parana" es un cambio aunque el vendedor haya preguntado el
    pago."""
    corta = len(str(parte.get("texto") or "").split()) <= CORTA
    q = MC.vectores([MC._clave({"frase": str(parte.get("texto") or ""), "abierta": turno["abierta"] if corta else ""})])[0]
    pool = [c for c in todos if c["origen"] == "plantilla" or (c["charla"] != turno["charla"] and len(c["respuestas"]) == 1)]
    vs = MC.vectores([MC._clave(c) for c in pool])
    nota = [MC._coseno(q, v) + MISMO_ESTADO * (c["estado"] == turno["estado"]) for c, v in zip(pool, vs)]
    return [c for _, c in sorted(zip(nota, pool), key=lambda x: -x[0])[:MC.CINCO]]


_MONTO = re.compile(r"(\d[\d.]*)\s*(mil|lucas|k)?\b")
_DIJO = re.compile(r"\b(me dijiste|me pasaste|me mostraste|que vi|que me ofreciste|de antes)\b")


def premisas(parte: dict, estado: dict) -> list:
    """Lo que el cliente da por cierto y el codigo revisa. Por ahora: un monto que dice que le mostraron."""
    txt = K.n(parte.get("texto"))
    if not _DIJO.search(txt):
        return []
    out = []
    precios = {m["id"]: K.entero(K.por_id(m["id"], TID).get("precio_ars")) for m in estado.get("mostrados") or []}
    for num, por in _MONTO.findall(txt):
        monto = K.entero(num.replace(".", "")) * (1000 if por else 1)
        if monto < 1000:
            continue
        cerca = [i for i, p in precios.items() if p and abs(p - monto) <= 0.05 * monto]
        out.append(f"dice {monto}: " + (f"cierto, {', '.join(cerca)}" if cerca else "falso, nada mostrado a ese precio"))
    return out


# ══ EL INFORME ═══════════════════════════════════════════════════════════════

def informe(partes: list, estado: dict, lib: str, turno: dict, todos: list) -> list:
    mapa = CA.a_renglon(estado)
    cands = CA.seis(partes, lib, mapa)
    return [{"parte": p.get("texto"), "acto": p.get("acto"), "destino": p.get("destino"),
             "tienda": tienda(str(p.get("texto") or ""), c),
             "pedido": anclar(p, estado, lib, mapa)[:4],
             "casos": [MC.como_ejemplo(x) for x in casos(p, turno, todos)],
             "premisas": premisas(p, estado)} for p, c in zip(partes, cands)]


def en_palabras(inf: list) -> str:
    r = []
    for i, x in enumerate(inf, 1):
        r.append(f"PARTE {i}: {x['parte']}" + (f" · destino {x['destino']}" if x.get("destino") else ""))
        t = x["tienda"]
        r.append("  tienda por significado: " + "; ".join(f"{g} {', '.join(v)}" for g, v in t["parecido"].items()))
        nombra = "; ".join(f"{g} {', '.join(v)}" for g, v in t["nombra"].items() if v)
        if nombra:
            r.append("  tienda por palabras: " + nombra)
        if not any(z for _, _, z in x["pedido"]):
            r.append("  apunta a: nada del pedido ni de lo mostrado")
        else:
            r.append(f"  apunta a {' y '.join(primeros(x['pedido']))}: " + "; ".join(f"{k} {s}" + (f" ({', '.join(z)})" if z else "")
                                               for k, s, z in x["pedido"]))
        r += ["  casos:"] + [f"    {c}" for c in x["casos"]]
        if x["premisas"]:
            r.append("  premisas: " + "; ".join(x["premisas"]))
    return "\n".join(r)


# ══ LA MEDIDA ════════════════════════════════════════════════════════════════

NOTA = collections.defaultdict(collections.Counter)
FALTAS = []


def notar(fuente: str, cid: str, msg: str, inf: list, esperado: list, mapas: dict) -> None:
    for capa, vale, dicho in esperado:
        if capa == "charla":
            listas = [[k for k, _, _ in x["pedido"]] for x in inf]
            tops = [set(primeros(x["pedido"])) for x in inf]
            # El mostrado y el renglon que lo tiene son el mismo producto: se cuenta aparte, como igual.
            mismos = [t | {L for m in t for L in mapas.get(m, [])} | {m for m, Ls in mapas.items() if t & set(Ls)}
                      for t in tops]
            NOTA[(fuente, capa)]["mismo producto"] += any(vale & m for m in mismos)
        else:
            listas = [list(x["tienda"]["parecido"][capa]) for x in inf]
            tops = [set(lst[:1]) for lst in listas]
        NOTA[(fuente, capa)]["casos"] += 1
        NOTA[(fuente, capa)]["primero"] += any(vale & t for t in tops)
        NOTA[(fuente, capa)]["entre los tres"] += any(vale & set(lst[:3]) for lst in listas)
        if capa == "charla" and not any(vale & t for t in tops):
            FALTAS.append((fuente, cid, dicho, msg, [(x["parte"], x["pedido"][:3]) for x in inf]))


def turnos():
    """(fuente, id, mensaje, estado, libreta, turno del motor, lo esperado), las 48 y despues las 58."""
    todos = {(c["origen"], c["charla"], c["turno"]): c for c in MC.cargar() if c["origen"] in ("48", "58")}
    for ch in A.CHARLAS:
        for i, tu in enumerate(ch["turnos"]):
            estado, historial = A.P.estado_de(tu["mem"])
            yield ("48", f"{ch['id']} t{i}", tu["msg"], estado, interprete.libreta(estado, historial, TID),
                   todos[("48", ch["id"], i)], CA.esperado_48(tu["oro"]))
    from banco_pruebas import cableado58 as C58
    from banco_pruebas.agendas58 import AGENDAS
    from app.core.flujo import estado as E
    from app.storage import firestore_client as fc
    interp = C58.instalar()
    rubros = set(A.agente.indice(TID)["rubros"])
    for charla in C58.charlas():
        agendas = list(AGENDAS.get(charla["id"]) or [])
        if len(agendas) != len(charla["turnos"]):
            continue
        uid = f"lab_{charla['id']}"
        C58.C.reiniciar_cliente(uid)
        for i, (t, ag) in enumerate(zip(charla["turnos"], agendas)):
            conv = fc.get_conversation(uid, tienda_id=TID) or {}
            estado = E.leer(conv)
            yield ("58", f"{charla['id']} t{i}", t["texto"], estado,
                   interprete.libreta(estado, conv.get("history") or [], TID), todos[("58", charla["id"], i)],
                   CA.esperado_58(ag, rubros))

            async def _interpretar(*a, _ag=ag, **k):
                return _ag

            interp.interpretar = _interpretar
            asyncio.run(C58.C.turno(uid, t["texto"]))


def main() -> None:
    todos = MC.cargar()
    salida = os.path.join(MC.CACHE, "lab_informes.jsonl")
    with open(salida, "w", encoding="utf-8") as fh:
        for fuente, cid, msg, estado, lib, turno, esperado in turnos():
            with CA.Puerta():
                partes = asyncio.run(CA.traducir(msg, lib))
                inf = informe(partes, estado, lib, turno, todos)
            notar(fuente, cid, A.limpio(msg), inf, esperado, CA.a_renglon(estado))
            fh.write(json.dumps({"fuente": fuente, "id": cid, "mensaje": A.limpio(msg), "informe": inf},
                                ensure_ascii=False) + "\n")
            if INFORME and cid.startswith(INFORME):
                print(f"\n=== {fuente} {cid}: {A.limpio(msg)}\n{lib}\n{en_palabras(inf)}")
    if VER:
        for fuente, cid, dicho, msg, partes in FALTAS:
            print(f"--- {fuente} {cid} · el pedido: esperado {dicho}\n    {msg[:150]}")
            for p, ap in partes:
                print(f"      {str(p)[:60]:60} -> " + "; ".join(f"{k} {s} {'+'.join(z)}" for k, s, z in ap))
    print("\nEL LABORATORIO DEL INFORME, primera vuelta, sobre la traduccion grabada de candidatos.py --pulida")
    for fuente in ("48", "58"):
        for capa in ("rubro", "tema", "producto", "charla"):
            n = NOTA[(fuente, capa)]
            if n["casos"]:
                print(f"  las {fuente} · {capa:9} {n['casos']:3} casos · primero {n['primero']:3}"
                      f" · entre los tres {n['entre los tres']:3}"
                      + (f" · primero, el mostrado igual al renglon que lo tiene {n['mismo producto']:3}"
                         if capa == "charla" else ""))
    print(f"  los informes en {salida}")


if __name__ == "__main__":
    main()
