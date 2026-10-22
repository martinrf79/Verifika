"""EL PEDIDO QUE QUEDA EN EL BOT, POR LA VARA DE LA FICHA — la comparacion justa que faltaba (22-oct-2026).

`medir_ficha.py` califica la ficha que escribio el modelo. Aca se califica lo que queda en el bot despues del turno: la
memoria de cada turno de `pregunta_razonada/fichas.py` se vuelve el estado de la charla —lo mostrado, el borrador y lo
abierto—, la agenda pasa por el ejecutor de verdad, y el borrador que queda, con lo que el turno pregunto o consulto, se
escribe en la forma de la ficha y lo califica `medir_ficha.calificar`, la misma vara.

De donde sale la agenda:
  --hoy            el interprete del bot, con el modelo: la base.
  --ficha ARCHIVO  las fichas grabadas por `ficha.py`, por el adaptador `flujo/ficha.a_agenda`: sin modelo.
  --vivo           la ficha del bot, `flujo/ficha.interpretar`, con su libreta y su esquema: con el modelo. Cada ficha
                   queda en `ficha_vivo.jsonl`, que es la bateria sin modelo del adaptador.

    python3 banco_pruebas/pedido_documento/medir_pedido.py --hoy [--ver]
    python3 banco_pruebas/pedido_documento/medir_pedido.py --ficha ficha_v5.jsonl [--ver]
Con la gratis por default; con la paga, la marca de Martin. Lo ya preguntado no se vuelve a pagar: `libro_paga.recordar`.
"""
import asyncio
import collections
import copy
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(AQUI))
sys.path.insert(0, REPO)
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(REPO, "banco_pruebas", "pregunta_razonada"))
os.chdir(REPO)
if os.environ.get("MARTIN_AUTORIZO_LA_PAGA"):
    os.environ["BANCO_CLAVE_PAGA"] = "true"

from banco_pruebas import clon_produccion as C  # noqa: E402
C.preparar_entorno()
C.instalar()
from app.core.flujo import borrador as B  # noqa: E402
from app.core.flujo import catalogo as K  # noqa: E402
from app.core.flujo import interprete  # noqa: E402
from app.core.flujo.agenda import preguntas as preguntas_de  # noqa: E402
from app.core.flujo.ejecutor import ejecutar  # noqa: E402
from fichas import CHARLAS  # noqa: E402
from experimento import limpio  # noqa: E402
import medir_ficha as M  # noqa: E402

TID = "verifika_prod"
TIPO = {"buscar": "buscar", "producto": "producto", "compatibilidad": "compatibilidad", "envio": "envio",
        "cuenta": "cuenta", "politica": "regla de la tienda", "explicar": "saber general"}


def estado_de(mem: dict) -> tuple:
    """(estado, historial) desde la memoria escrita a mano. Un renglon va por su rubro, resuelto al producto que se
    eligio, salvo que el rubro tenga varios productos en el pedido: ahi va por su nombre."""
    por_id = {str(p["id"]): p for p in K.productos(TID)}
    mostrados = [{"id": pid, "nombre": por_id[pid]["nombre"], "precio": por_id[pid].get("precio_ars")}
                 for pid in mem.get("M") or []]
    b = B.leer({})
    ids_de = collections.defaultdict(set)
    for _, rubro, pid, _ in mem.get("L") or []:
        ids_de[rubro].add(pid)
    for i, (cant, rubro, pid, dest) in enumerate(mem.get("L") or [], 1):
        unico = len(ids_de[rubro]) == 1
        b["renglones"].append({"L": f"L-{i}", "que": rubro if unico else por_id[pid]["nombre"], "cantidad": cant,
                               "color": "", "destino": dest, "condicion": "", "cita": "", "confirmado": True})
        if unico:
            b["criterios"][rubro] = {"condiciones": [], "orden": "nada", "entre": [pid]}
            b["lista"][rubro] = b["lista"].get(rubro, 0) + cant
    b["siguiente"] = len(b["renglones"]) + 1
    abiertas = [{"texto": r, "cita": "", "pregunta": r} for r in mem.get("R") or []]
    estado = {"mostrados": mostrados, "pedido": [], "busqueda": {}, "abiertas": abiertas, "borrador": b}
    historial = [{"role": "assistant", "content": mem["dijo"]}] if mem.get("dijo") else []
    return estado, historial


def _texto_ref(v, nums: dict, por_id: dict) -> str:
    """Un numero de la libreta con su nombre: la vara busca el producto por su nombre."""
    if isinstance(v, list):
        return " ".join(_texto_ref(x, nums, por_id) for x in v)
    if isinstance(v, dict):
        return " ".join(_texto_ref(x, nums, por_id) for x in v.values())
    x = nums.get(str(v)) if isinstance(v, str) else None
    if isinstance(x, str) and x in por_id:
        return f"{v} {por_id[x]['nombre']}"
    if isinstance(x, dict) and x.get("que"):
        return f"{v} {x['que']}"
    # Un modelo dicho con sus palabras, con el nombre que le da la identidad: lo que el bot va a consultar.
    idt = K.identificar(str(v), "", TID) if isinstance(v, str) and v else {}
    return f"{v} {idt['producto']['nombre']}" if idt.get("veredicto") == "exists" else str(v)


def como_ficha(t, estado: dict, mem: dict, agenda: dict = None) -> dict:
    """Lo que quedo despues del turno, en la forma de la ficha: el borrador entero, las consultas de la agenda y lo
    que el bot pregunto como duda."""
    por_id = {str(p["id"]): p for p in K.productos(TID)}
    b = estado["borrador"]
    res = B.resolver(b, TID) if b["renglones"] else []
    originales = {f"L-{i}" for i in range(1, len(mem.get("L") or []) + 1)}
    grupos = collections.OrderedDict()
    for x in res:
        r = x["renglon"]
        if x.get("no_aplica"):
            continue
        crit = b["criterios"].get(r["que"]) or {}
        nombres = " ".join(a["nombre"] for a in x.get("articulos") or [])
        cant = r["cantidad"] or sum(a["cantidad"] for a in x.get("articulos") or []) or 1
        item = {"producto": f"{r['que']} {nombres}".strip(), "cantidad": cant, "color": r["color"],
                "condiciones": list(crit.get("condiciones") or []) + ([r["condicion"]] if r.get("condicion")
                                                                      and r["condicion"] != "sin_saber" else []),
                "orden": crit.get("orden") or "nada",
                "renglon": r["L"].replace("-", "") if r["L"] in originales else "nuevo"}
        grupos.setdefault(r["destino"] or "sin decir", []).append(item)
    consultas, tope = [], None
    for p in t.agenda:
        acc = p.get("accion")
        if acc == "cuenta" and p.get("tope"):
            tope = p["tope"]
        # Sin pedido, el tope queda en la busqueda como "hasta $N": es donde lo guarda el bot.
        for c in p.get("condiciones") or [] if acc == "buscar" and not tope else []:
            if K.atar(str(c), [], TID).get("tope"):
                tope = K.atar(str(c), [], TID)["tope"][1]
        if acc not in TIPO:
            continue
        datos = {k: v for k, v in p.items() if k not in ("n", "accion", "si", "responde")}
        consultas.append({"tipo": TIPO[acc], "sobre": _texto_ref(datos, t.nums, por_id),
                          "si": "depende" if p.get("si") else ""})
    return {"pedido": [{"destino": d, "items": its} for d, its in grupos.items()],
            "preferencias": {"condiciones": [], "orden": (estado.get("busqueda") or {}).get("orden") or "nada"},
            "pago": {"medios": b["pago"], "tope_total": tope},
            "consultas": consultas, "cliente": b["cliente"], "dudas": list(t.preguntas) + list((agenda or {}).get("dudas") or [])}


async def turno(tu: dict, agenda_de) -> dict:
    estado, historial = estado_de(tu["mem"])
    msg = limpio(tu["msg"])
    agenda = await agenda_de(msg, historial, estado)
    if agenda is None:
        return {"error": "sin agenda"}
    prueba = copy.deepcopy(estado)
    t = ejecutar(agenda, prueba, TID, explicar=lambda q: "explicado")
    if t.lecturas:
        elegida = await interprete.elegir(msg, historial, t.lecturas, "medir_pedido")
        if elegida:
            prueba = copy.deepcopy(estado)
            t = ejecutar(agenda, prueba, TID, explicar=lambda q: "explicado", elegida=elegida)
    return {"agenda": agenda, "ficha": como_ficha(t, prueba, tu["mem"], agenda)}


async def main() -> None:
    a = sys.argv[1:]
    ver = "--ver" in a
    if "--ficha" in a:
        from app.core.flujo import ficha as F
        grabadas = {(r["charla"], r["turno"]): r["salida"] for r in
                    map(json.loads, open(os.path.join(AQUI, a[a.index("--ficha") + 1]), encoding="utf-8"))
                    if not r.get("error") and r.get("rep", 0) == 0}
        nombre = a[a.index("--ficha") + 1]
    elif "--vivo" in a:
        from app.core.flujo import ficha as F
        nombre = "ficha viva"
    else:
        nombre = "interprete de hoy"
    cuenta, tipos, salidas, vivas = collections.Counter(), collections.Counter(), [], {}
    sem = asyncio.Semaphore(int(os.environ.get("FICHA_A_LA_VEZ", "4")))

    async def uno(ch, i, tu):
        async with sem:
            if "--ficha" in a:
                crudo = grabadas.get((ch["id"], i))
                if crudo is None:
                    return ch, i, tu, {"error": "sin ficha grabada"}

                async def agenda_de(msg, historial, estado):
                    return F.a_agenda(interprete._json(crudo), estado, TID, msg)
            elif "--vivo" in a:
                async def agenda_de(msg, historial, estado):
                    crudo = await interprete._pedir(F.mensajes(msg, historial, estado, TID), "medir_pedido",
                                                    F.formato(TID))
                    vivas[(ch["id"], i)] = crudo
                    return F.a_agenda(interprete._json(crudo), estado, TID, msg)
            else:
                async def agenda_de(msg, historial, estado):
                    return await interprete.interpretar(msg, historial, estado, TID, "medir_pedido")
            try:
                return ch, i, tu, await turno(tu, agenda_de)
            except Exception as e:  # noqa: BLE001 — un turno que rompe el ejecutor es una falla, no un corte
                return ch, i, tu, {"error": f"{type(e).__name__}: {str(e)[:160]}"}

    hechos = await asyncio.gather(*[uno(ch, i, tu) for ch in CHARLAS for i, tu in enumerate(ch["turnos"])])
    for ch, i, tu, r in hechos:
        if r.get("error"):
            c = {"veredicto": "MAL SIN AVISAR", "fallas": [r["error"]], "dudas": []}
        else:
            c = M.calificar(tu, json.dumps(r["ficha"], ensure_ascii=False))
        cuenta[c["veredicto"]] += 1
        salidas.append({"charla": ch["id"], "turno": i, **c, **({"ficha": r["ficha"], "agenda": r["agenda"]} if not r.get("error") else {})})
        for f in c["fallas"]:
            tipos[f.split(":")[0][:40]] += 1
        if ver and c["veredicto"] != "BIEN":
            print(f"--- {ch['id']} t{i} {c['veredicto']}: {limpio(tu['msg'])[:200]}")
            print("    " + "\n    ".join(c["fallas"]))
            if c["dudas"]:
                print(f"    dudas: {[str(d)[:120] for d in c['dudas']]}")
    print(f"\nEL PEDIDO EN EL BOT · {nombre} · {sum(cuenta.values())} turnos")
    print(f"  BIEN {cuenta['BIEN']} · DUDO {cuenta['DUDO']} · MAL SIN AVISAR {cuenta['MAL SIN AVISAR']}")
    print(f"  las fallas: {dict(tipos.most_common(12))}")
    if vivas:
        with open(os.path.join(AQUI, "ficha_vivo.jsonl"), "w", encoding="utf-8") as f:
            f.writelines(json.dumps({"charla": c, "turno": t, "salida": x}, ensure_ascii=False) + "\n"
                         for (c, t), x in sorted(vivas.items()))
    sufijo = "vivo" if "--vivo" in a else ("hoy" if "--ficha" not in a else os.path.splitext(nombre)[0])
    with open(os.path.join(AQUI, f"pedido_{sufijo}.jsonl"), "w", encoding="utf-8") as f:
        f.writelines(json.dumps(s, ensure_ascii=False) + "\n" for s in salidas)


if __name__ == "__main__":
    asyncio.run(main())
