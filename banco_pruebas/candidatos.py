"""LOS SEIS CANDIDATOS SOBRE LA PRIMERA TRADUCCION — pedido de Martin del 23-oct: ¿trae el codigo lo correcto?

Por cada turno, la primera llamada traduce con la consigna unida de `actos.py`; el codigo busca por significado cada
parte traducida en cuatro capas y trae los seis mas parecidos de cada una:
  rubro, tema y producto   la tienda, como en `etiqueta.py`: un vector por rubro, tema y familia de modelos;
  charla                   lo mostrado y el borrador de la libreta de ese turno, M-n y L-n.

Lo esperado sale de lo escrito a mano antes de correr, nunca del modelo:
  las 48    el oro de `pregunta_razonada/fichas.py`: el rubro, el tema y el numero de la memoria que senala;
  las 58    las agendas de `agendas58.py`, con las K que entraron a la vara: el rubro de cada busqueda, el modelo de
            cada pregunta o compra, el tema de cada politica y el numero que senala. La memoria de cada turno es la
            del flujo vivo con las agendas a mano, como en `cableado58.py`.

Por cada cosa esperada: si esta entre los seis de alguna parte, y si es el primero de alguna.

--completa, paso 1 del plan: la consigna pide cada parte entera, que se entienda sola, una clase de producto por parte,
y lo que senala de la libreta por su numero. Eso se mide aparte, en la capa "numero". En las 48 se suma el acto.
--pulida, lo mismo y ademas: la pregunta sigue pregunta y lo que pregunta no se junta con lo que decide; y el codigo
pasa un M-n que ya esta en el pedido a su renglon.

    MARTIN_AUTORIZO_LA_PAGA=<fecha> TOPE_CORRIDA=0.20 python3 banco_pruebas/candidatos.py [--ver] [--completa] [--solo48|--solo58]
"""
import asyncio
import collections
import os
import re
import sys

VER = "--ver" in sys.argv
PULIDA = "--pulida" in sys.argv
COMPLETA = "--completa" in sys.argv or PULIDA
SOLO = "48" if "--solo48" in sys.argv else "58" if "--solo58" in sys.argv else ""
sys.argv = [sys.argv[0]]
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import etiqueta as ET  # noqa: E402  — los vectores, la tienda, la charla y el entorno
from banco_pruebas import libro_paga  # noqa: E402
from app.core import llm_reintento  # noqa: E402
from app.core.flujo import catalogo as K  # noqa: E402
from app.core.flujo import interprete  # noqa: E402

A, MO = ET.A, ET.MO
TID = A.P.TID
SEIS = 6
TOPE = float(os.environ.get("TOPE_CORRIDA", "0.20"))
CAPAS = ("rubro", "tema", "producto", "charla", "numero")
_PUERTA = llm_reintento._cliente  # la puerta al modelo, antes de que el cableado la cierre


def familia(p: dict) -> str:
    """La misma clave que `etiqueta.tienda`: el nombre sin el color."""
    return str(p.get("nombre") or "").rsplit(" ", 1)[0] if p.get("color") else str(p.get("nombre") or "")


def familias_de(nombre: str) -> set:
    """Las familias que la identidad da para un nombre: una si existe, todas las opciones si es ambiguo."""
    idt = K.identificar(nombre, "", TID)
    ps = [idt["producto"]] if idt["veredicto"] == "exists" else idt.get("opciones") or []
    return {familia(p) for p in ps}


def a_renglon(estado: dict) -> dict:
    """Lo mostrado que ya esta en el pedido, al renglon que lo tiene: "M-1" -> ["L-2"]. Sin modelo."""
    from app.core.flujo import borrador as B
    b = B.leer(estado.get("borrador"))
    res = B.resolver(b, TID) if b["renglones"] else []
    en = collections.defaultdict(list)
    for r in res:
        for a in r.get("articulos") or []:
            en[a.get("id")].append(r["L"])
    return {k: en[v] for k, v in interprete.numeros(estado).items() if k[0] == "M" and en.get(v)}


def seis(partes: list, libreta: str, mapa: dict = None) -> list:
    """Por cada parte, los seis de cada capa. "numero" es lo que la parte senala de la libreta, con --completa."""
    charla = ET._charla(libreta)
    vc = dict(zip(charla, ET.vectores(list(charla.values())))) if charla else {}
    idx = ET.tienda()
    out = []
    textos = [str(p.get("texto") or "") for p in partes]
    for p, q in zip(partes, ET.vectores(textos) if textos else []):
        c = {g: [k for k, _ in sorted(((k, ET._coseno(v, q)) for k, v in d.items()), key=lambda x: -x[1])[:SEIS]]
             for g, d in idx.items()}
        c["charla"] = [k for k, _ in sorted(((k, ET._coseno(v, q)) for k, v in vc.items()), key=lambda x: -x[1])[:SEIS]]
        c["numero"] = [y for x in p.get("senala") or [] if _ref(x, False)
                       for y in ((mapa or {}).get(_ref(x, False)) or [_ref(x, False)])]
        out.append(c)
    return out


# LA PREGUNTA COMPLETA, paso 1 del plan de Martin del 23-oct: cada parte se entiende sola, sin leer la charla, y lo
# que senala de la libreta va por su numero, no por parecido.
COMPLETA_TXT = """
Cada parte es una pregunta o un pedido COMPLETO, que se entiende solo, sin leer la charla. Si el cliente no repite de
que habla —"¿y en blanco?", "pasame otras", "el de mi hija", "de cada uno"—, lo tomas de la LIBRETA y lo escribis en la
parte: "¿el mouse viene en blanco?". Una parte habla de una sola clase de producto: "dos teclados y dos mouse" son dos
partes. En "senala" van los numeros de la libreta de lo que la parte nombra o senala —M-2 lo mostrado, L-1 un renglon
del borrador—; [] si no senala nada de la libreta."""

# LO PULIDO, 23-oct: completar no es cambiar lo que dijo. La pregunta completa volvia orden lo que era pregunta.
PULIDA_TXT = """
Completar no es cambiar lo que dijo: una pregunta sigue siendo pregunta, con su signo, y un pedido sigue siendo pedido.
No juntes en una parte lo que pregunta con lo que decide: "¿hay tres? si hay, llevo tres" son dos partes."""


def formato_completo() -> dict:
    import copy
    f = copy.deepcopy(A.formato_unido())
    item = f["json_schema"]["schema"]["properties"]["partes"]["items"]
    item["properties"]["senala"] = {"type": "array", "items": {"type": "string"}}
    item["required"].append("senala")
    return f


async def traducir(mensaje: str, libreta: str) -> list:
    consigna = A.consigna_unida() + (COMPLETA_TXT if COMPLETA else "") + (PULIDA_TXT if PULIDA else "")
    msgs = [{"role": "system", "content": consigna},
            {"role": "user", "content": libreta + f"\nULTIMO MENSAJE: {A.limpio(mensaje)}"}]
    r = interprete._json(await interprete._pedir(msgs, "candidatos", formato_completo() if COMPLETA
                                                 else A.formato_unido()))
    return [p for p in r.get("partes") or [] if isinstance(p, dict)]


class Puerta:
    """El modelo abierto solo para la traduccion y los vectores, aunque el cableado lo tenga cerrado."""
    def __enter__(self):
        self.antes = llm_reintento._cliente
        llm_reintento._cliente = _PUERTA

    def __exit__(self, *a):
        llm_reintento._cliente = self.antes


# ══ LO ESPERADO ══════════════════════════════════════════════════════════════

def _ref(x, guion: bool = True) -> str:
    """El numero de la libreta: "M-2". En las agendas va con guion, asi "M170" es un modelo; en el oro, sin guion."""
    m = re.match(r"^([MLP])-(\d+)$" if guion else r"^([MLP])-?(\d+)$", str(x or "").strip())
    return f"{'L' if m.group(1) == 'P' else m.group(1)}-{m.group(2)}" if m else ""


def esperado_48(oro: list) -> list:
    """(capa, conjunto de lo que vale, como se dijo) por cada cosa del oro."""
    out = []
    for o in oro:
        if o.get("opt"):
            continue
        if o.get("rubro"):
            out.append(("rubro", {o["rubro"]}, o["rubro"]))
        if o.get("tema"):
            t = o["tema"]
            out.append(("tema", set(t) if isinstance(t, (list, set, tuple)) else {t}, "/".join(sorted(t))
                        if isinstance(t, (list, set, tuple)) else t))
        for c in o.get("cual") if isinstance(o.get("cual"), list) else [o.get("cual")] if o.get("cual") else []:
            if _ref(c, False):
                out.append(("charla", {_ref(c, False)}, _ref(c, False)))
    return out


def esperado_58(agenda: dict, rubros: set) -> list:
    out = []

    def producto(x):
        x = str(x or "").strip()
        if not x or x in ("los otros", "el pedido"):
            return
        if _ref(x):
            out.append(("charla", {_ref(x)}, _ref(x)))
        elif x in rubros:
            out.append(("rubro", {x}, x))
        else:
            f = familias_de(x)
            if f:
                out.append(("producto", f, x))
    for p in agenda.get("preguntas") or []:
        acc = p.get("accion")
        if acc == "buscar" and p.get("rubro") in rubros:
            out.append(("rubro", {p["rubro"]}, p["rubro"]))
        elif acc in ("producto", "compatibilidad"):
            x = p.get("producto")
            if isinstance(x, list) and all(_ref(y) for y in x):
                # Lo que senala puede ser varios y el codigo pregunta: vale cualquiera, es un caso.
                out.append(("charla", {_ref(y) for y in x}, "uno de " + ", ".join(x)))
            else:
                for y in x if isinstance(x, list) else [x]:
                    producto(y)
        elif acc == "politica" and p.get("tema"):
            out.append(("tema", {p["tema"]}, p["tema"]))
        elif acc == "comprar":
            for a in p.get("agrega") or []:
                producto(a.get("producto"))
            for c in p.get("cambia") or []:
                producto(c.get("es"))
            for s in p.get("saca") or []:
                producto(s)
    return out


# ══ LA NOTA ══════════════════════════════════════════════════════════════════

NOTA = collections.defaultdict(collections.Counter)
ACTOS = collections.Counter()
FALTAS = []


def notar(fuente: str, cid: str, msg: str, partes: list, cands: list, esperado: list) -> None:
    if COMPLETA:
        esperado = esperado + [("numero", v, d) for c, v, d in esperado if c == "charla"]
    for capa, vale, dicho in esperado:
        en6 = any(vale & set(c[capa]) for c in cands)
        uno = any(vale & set(c[capa][:1]) for c in cands)
        NOTA[(fuente, capa)]["casos"] += 1
        NOTA[(fuente, capa)]["en los seis"] += en6
        NOTA[(fuente, capa)]["primero"] += uno
        if not uno:
            mejor = [c[capa][:3] for c in cands]
            FALTAS.append((fuente, cid, capa, dicho, en6, msg, [p.get("texto") for p in partes], mejor))


def gastado(desde: float) -> float:
    return libro_paga.gastado(libro_paga._hoy()) - desde


def las_48(desde: float) -> None:
    for ch in A.CHARLAS:
        for i, tu in enumerate(ch["turnos"]):
            if gastado(desde) >= TOPE:
                return
            estado, historial = A.P.estado_de(tu["mem"])
            lib = interprete.libreta(estado, historial, TID)
            with Puerta():
                partes = asyncio.run(traducir(tu["msg"], lib))
                cands = seis(partes, lib, a_renglon(estado) if PULIDA else None)
            notar("48", f"{ch['id']} t{i}", A.limpio(tu["msg"]), partes, cands, esperado_48(tu["oro"]))
            quiere = {A.DEL_ORO[x["tipo"]] for x in tu["oro"] if not x.get("opt")}
            puso = {p.get("acto") for p in A.definir([dict(p) for p in partes], tu["mem"])}
            ACTOS["BIEN" if puso == quiere or puso in A.TAMBIEN.get((ch["id"], i), []) else "MAL"] += 1


def las_58(desde: float) -> None:
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
        uid = f"candidatos_{charla['id']}"
        C58.C.reiniciar_cliente(uid)
        for i, (t, ag) in enumerate(zip(charla["turnos"], agendas)):
            if gastado(desde) >= TOPE:
                return
            conv = fc.get_conversation(uid, tienda_id=TID) or {}
            estado = E.leer(conv)
            lib = interprete.libreta(estado, conv.get("history") or [], TID)
            with Puerta():
                partes = asyncio.run(traducir(t["texto"], lib))
                cands = seis(partes, lib, a_renglon(estado) if PULIDA else None)
            notar("58", f"{charla['id']} t{i}", t["texto"], partes, cands, esperado_58(ag, rubros))

            async def _interpretar(*a, _ag=ag, **k):
                return _ag

            interp.interpretar = _interpretar
            asyncio.run(C58.C.turno(uid, t["texto"]))


def main() -> None:
    desde = libro_paga.gastado(libro_paga._hoy())
    if SOLO != "58":
        las_48(desde)
    if SOLO != "48":
        las_58(desde)
    if gastado(desde) >= TOPE:
        print(f"TOPE de la corrida: {TOPE} dolares")
    if VER:
        for fuente, cid, capa, dicho, en6, msg, partes, mejor in FALTAS:
            print(f"--- {fuente} {cid} · {capa}: esperado {dicho} · {'entre los seis' if en6 else 'NO ESTA en los seis'}")
            print(f"    {msg[:160]}")
            for p, m in zip(partes, mejor):
                print(f"      {str(p)[:70]:70} -> {', '.join(m)}")
    print("\nLOS SEIS CANDIDATOS SOBRE LA PRIMERA TRADUCCION" + (", CON LA PREGUNTA COMPLETA" if COMPLETA else "")
          + (", PULIDA" if PULIDA else ""))
    for fuente in ("48", "58"):
        for capa in CAPAS:
            n = NOTA[(fuente, capa)]
            if n["casos"]:
                print(f"  las {fuente} · {capa:9} {n['casos']:3} casos · entre los seis {n['en los seis']:3}"
                      f" · primero {n['primero']:3}")
    if ACTOS:
        print(f"  el acto de las 48, con la regla del codigo: BIEN {ACTOS['BIEN']} de {sum(ACTOS.values())}")
    print(f"Gasto: {gastado(desde):.3f} dolares")


if __name__ == "__main__":
    main()
