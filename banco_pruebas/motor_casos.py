"""EL MOTOR DE CASOS RESUELTOS — la plantilla llenada para una tienda, FICHA 78, paso 2, 24-oct. Es banco.

Un caso es una frase de cliente con el estado de la charla y las respuestas de la tienda que pide. Salen de tres lados:
  plantilla  `casos_plantilla.FORMAS`, igual para cualquier tienda, con los huecos llenos con la fuente de la tienda:
             catalogo, FAQ, specs preguntables y compatibilidades. Cada caso se valida contra la fuente con el codigo:
             el producto lo certifica la identidad, el color lo tiene el producto, el dato aplica a su rubro, el tema
             y el medio estan en la FAQ, el equipo esta en las compatibilidades. Lo que no pasa no entra.
  las 48     cada turno de `pregunta_razonada/fichas.py`, con su oro llevado a respuestas por `respuestas.valen_48`.
  las 58     cada turno de la vara con las K, con su agenda llevada a respuestas por `respuestas.oro_58`, y la memoria
             del flujo vivo con las agendas a mano, como en `cableado58.py`.

El examen queda afuera: un caso de la plantilla que se parece por significado a una frase de las pruebas de la
traduccion —las 108, las cien dificiles y el examen— a mas de UMBRAL_EXAMEN no entra. Al medir un turno de las 48 o
las 58, los casos de su misma charla no se traen: se mide cada charla sin sus casos.

La busqueda trae los CINCO mas parecidos del mismo estado, por coseno sobre `gemini-embedding-001` en 768.
Los casos y los vectores van fuera del repo, en ~/.cache/verifika, porque copian la fuente: se rearman con --llenar.

    python3 banco_pruebas/motor_casos.py --llenar          arma los casos y dice cuantos entraron y por que no
    python3 banco_pruebas/motor_casos.py --muestra 20      una muestra de la plantilla llenada, para Martin
    python3 banco_pruebas/motor_casos.py --vecinos         sin modelo: las 48 y las 58 por el voto de sus vecinos
"""
import asyncio
import collections
import csv
import json
import os
import random
import re
import sys
import time

ARGS = sys.argv[1:]
sys.argv = [sys.argv[0]]
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import casos_plantilla as PL  # noqa: E402
import respuestas as R  # noqa: E402  — las varas de las 48 y las 58, y el entorno
from app.core.flujo import catalogo as K  # noqa: E402
from app.core.flujo import interprete  # noqa: E402

A, CA = R.A, R.CA
TID = R.TID
FUENTE = os.path.join(os.path.dirname(AQUI), "data", "clientes", TID)
CACHE = os.path.expanduser("~/.cache/verifika")
CASOS = os.path.join(CACHE, f"casos_{TID}.jsonl")
VECTORES = os.path.join(CACHE, "casos_vectores_768.json")
EMBEDDINGS, DIMENSION = "gemini-embedding-001", 768
POR_FORMA = 6          # llenados por forma de la plantilla
CINCO = 5
UMBRAL_EXAMEN = 0.92   # coseno desde el que un caso se parece demasiado a una frase de las pruebas
SEMILLA = 78
# Temas que no son una regla de como trabaja la tienda: su respuesta es otra clase.
NO_REGLA = {"compatibilidad", "stock_disponibilidad", "costo_envio", "especificaciones", "contenido_caja",
            "material_composicion", "teclado_mecanico_membrana", "mouse_dpi"}
# Como dice el cliente cada plataforma de las compatibilidades.
EQUIPOS = {"ps5": "la PS5", "ps4": "la Play 4", "xbox": "la Xbox", "nintendo_switch": "la Switch",
           "android": "mi celular Android", "ios": "el iPhone", "notebook": "mi notebook", "smart_tv": "la smart TV",
           "windows": "Windows", "pc_escritorio": "la PC de escritorio", "macos": "una Mac", "linux": "Linux"}
MEDIOS = ["transferencia", "Mercado Pago", "Visa", "Mastercard", "American Express", "efectivo", "debito"]


# ══ LA FUENTE DE LA TIENDA, para los huecos ═══════════════════════════════════

def fuente() -> dict:
    prods = [p for p in K.productos(TID) if K.con_stock(p) and p.get("modelo")]
    familias = {}
    for p in prods:
        familias.setdefault((p["marca"], p["modelo"], p["categoria"]), []).append(p)
    specs = json.load(open(os.path.join(FUENTE, "specs_preguntables.json"), encoding="utf-8"))["specs"]
    faq = json.load(open(os.path.join(FUENTE, "faq.json"), encoding="utf-8"))
    pago = next((x["respuesta"] for x in faq if x["tema"] == "formas_pago"), "")
    compat = collections.defaultdict(set)
    for r in csv.DictReader(open(os.path.join(FUENTE, "compatibilidad.csv"), encoding="utf-8")):
        compat[(r["marca"], r["modelo"])] |= {x for x in r["plataformas"].split("|") if x}
    return {
        "familias": familias,
        "rubros": sorted(A.agente.indice(TID)["rubros"]),
        "campos": {s["id"]: s for s in specs},
        "temas": {x["tema"]: x["keywords"] for x in faq if x["tema"] not in NO_REGLA},
        "medios": [m for m in MEDIOS if K.n(m) in K.n(pago)],
        "compat": compat,
    }


def _nombre(fam: tuple) -> str:
    return f"{fam[0]} {fam[1]}"


def _frase_tema(kws: list, rnd: random.Random) -> str:
    """Como pregunta un cliente por un tema: una clave de la FAQ de varias palabras que no sea algo que dice el cliente
    de si mismo —"ya te pague"—, o la primera clave, en una pregunta corta."""
    largas = [k for k in kws if " " in k and not k.split()[0] in ("ya", "me", "te", "se", "lo", "puse")] or kws[:1]
    k = rnd.choice(largas)
    return rnd.choice([f"como es lo de {k}", f"que onda con {k}", f"me explicas lo de {k}"])


def llenar_forma(forma: tuple, f: dict, rnd: random.Random) -> dict:
    """Un caso de una forma, con sus huecos llenos y lo que hace falta para validarlo."""
    estado, resp, frase, abierta = forma
    fams = list(f["familias"])
    fam = rnd.choice(fams)
    rub = fam[2]
    otras = [x for x in fams if x[2] == rub and x != fam]
    fam2 = rnd.choice(otras) if otras else None
    colores = sorted({p.get("color") for p in f["familias"][fam] if p.get("color")})
    # La etiqueta de la tienda dice el dato como lo pregunta un cliente; "si la RAM se puede ampliar" no entra en una forma.
    campos = [c for c in f["campos"].values() if rub in (c.get("aplica_a") or []) and not c["etiqueta"].startswith("si ")]
    campo = rnd.choice(campos) if campos else None
    equipos = sorted(f["compat"].get((fam[0], fam[1])) or [])
    tema = rnd.choice(sorted(f["temas"]))
    lugar, lugar2 = rnd.sample(PL.LUGARES, 2)
    medio, medio2 = rnd.sample(f["medios"], 2) if len(f["medios"]) > 1 else (None, None)
    rubro2 = rnd.choice([r for r in f["rubros"] if r != rub])
    huecos = {
        "producto": _nombre(fam), "producto2": _nombre(fam2) if fam2 else None, "rubro": rub, "rubro2": rubro2,
        "rubro_pedido": rub, "color": K.n(colores[rnd.randrange(len(colores))]) if colores else None,
        "campo": campo["etiqueta"] if campo else None,
        "tema": _frase_tema(f["temas"][tema], rnd), "equipo": EQUIPOS.get(rnd.choice(equipos)) if equipos else None,
        "lugar": lugar, "lugar2": lugar2, "n": rnd.choice(PL.CANTIDADES), "plata": rnd.choice(PL.PLATA),
        "medio": medio, "medio2": medio2, "nombre": rnd.choice(PL.NOMBRES), "uso": rnd.choice(PL.USOS),
    }
    usados = set(re.findall(r"\{(\w+)\}", frase))
    if any(huecos.get(h) is None for h in usados):
        return {"falta": sorted(h for h in usados if huecos.get(h) is None)}
    return {"origen": "plantilla", "charla": "", "estado": estado, "abierta": abierta,
            "frase": frase.format(**{h: huecos[h] for h in usados}), "respuestas": sorted(resp),
            "forma": frase, "pedido": rub if estado != PL.SIN else "",
            "_valida": {"producto": _nombre(fam) if {"producto"} & usados else "",
                        "producto2": huecos["producto2"] if "producto2" in usados else "",
                        "color": huecos["color"] if "color" in usados else "",
                        "rubro": rub, "tema": tema if "tema" in usados else "",
                        "campo": campo["id"] if campo and "campo" in usados else ""}}


def validar(c: dict, f: dict) -> str:
    """"" si el caso pasa contra la fuente; si no, por que no."""
    v = c.pop("_valida")
    for k in ("producto", "producto2"):
        if v[k]:
            idt = K.identificar(v[k], v["color"] if k == "producto" else "", TID)
            if idt["veredicto"] != "exists":
                return f"{k} {idt['veredicto']}"
            if v["color"] and k == "producto" and K.n(idt["producto"].get("color")) != K.n(v["color"]):
                return "color"
    if v["rubro"] not in f["rubros"]:
        return "rubro"
    if v["tema"] and v["tema"] not in f["temas"]:
        return "tema"
    if v["campo"] and v["rubro"] not in (f["campos"][v["campo"]].get("aplica_a") or []):
        return "campo"
    return ""


def plantilla() -> tuple:
    f = fuente()
    rnd = random.Random(SEMILLA)
    casos, fuera, vistos = [], collections.Counter(), set()
    for forma in PL.FORMAS:
        for _ in range(POR_FORMA):
            c = llenar_forma(forma, f, rnd)
            if "falta" in c:
                fuera["hueco sin dato: " + ",".join(c["falta"])] += 1
                continue
            if (c["estado"], c["frase"]) in vistos:
                fuera["repetido"] += 1
                continue
            por = validar(c, f)
            if por:
                fuera[por] += 1
                continue
            vistos.add((c["estado"], c["frase"]))
            casos.append(c)
    return casos, fuera


# ══ LAS 48 Y LAS 58, como casos ══════════════════════════════════════════════

def _estado_de(estado: dict) -> str:
    if estado.get("abiertas"):
        return PL.ABIERTA
    return PL.CON if (estado.get("borrador") or {}).get("renglones") else PL.SIN


def de_las_48() -> list:
    out = []
    for ch in A.CHARLAS:
        for i, tu in enumerate(ch["turnos"]):
            estado, historial = A.P.estado_de(tu["mem"])
            quiere = sorted({R.DEL_ACTO[A.DEL_ORO[x["tipo"]]] for x in tu["oro"] if not x.get("opt")})
            out.append({"origen": "48", "charla": ch["id"], "turno": i, "estado": _estado_de(estado),
                        "abierta": " ".join(tu["mem"].get("R") or []), "frase": A.limpio(tu["msg"]),
                        "respuestas": quiere,
                        "libreta": interprete.libreta(estado, historial, TID),
                        "valen": [sorted(R.DEL_ACTO[x] for x in v) for v in R.valen_48(ch, i, tu)]})
    return out


def de_las_58() -> list:
    from banco_pruebas import cableado58 as C58
    from banco_pruebas.agendas58 import AGENDAS
    from app.core.flujo import estado as E
    from app.storage import firestore_client as fc
    interp = C58.instalar()
    out = []
    for charla in C58.charlas():
        agendas = list(AGENDAS.get(charla["id"]) or [])
        if len(agendas) != len(charla["turnos"]):
            continue
        uid = f"motor_{charla['id']}"
        C58.C.reiniciar_cliente(uid)
        for i, (t, ag) in enumerate(zip(charla["turnos"], agendas)):
            conv = fc.get_conversation(uid, tienda_id=TID) or {}
            estado = E.leer(conv)
            out.append({"origen": "58", "charla": charla["id"], "turno": i, "estado": _estado_de(estado),
                        "abierta": " ".join(str(a.get("pregunta") or "") for a in estado.get("abiertas") or []),
                        "frase": t["texto"], "respuestas": sorted(R._58(R.oro_58(ag))),
                        "libreta": interprete.libreta(estado, conv.get("history") or [], TID),
                        "valen": [sorted(v) for v in R.valen_58(ag)]})

            async def _interpretar(*a, _ag=ag, **k):
                return _ag

            interp.interpretar = _interpretar
            asyncio.run(C58.C.turno(uid, t["texto"]))
    return out


# ══ LOS VECTORES ═════════════════════════════════════════════════════════════

_VEC: dict = {}


def vectores(textos: list) -> list:
    """Cada texto como vector de 768, guardado en disco: lo ya pedido no se vuelve a pedir."""
    if not _VEC and os.path.exists(VECTORES):
        _VEC.update(json.load(open(VECTORES, encoding="utf-8")))
    faltan = [t for t in dict.fromkeys(textos) if t not in _VEC]
    for i in range(0, len(faltan), 90):
        for intento in range(12):
            try:
                r = CA._PUERTA().embeddings.create(model=EMBEDDINGS, input=faltan[i:i + 90], dimensions=DIMENSION)
                break
            except Exception as e:  # noqa: BLE001 — la gratis corta por minuto: se espera y se sigue
                if "429" not in str(e) or intento == 11:
                    raise
                time.sleep(35)
        _VEC.update(zip(faltan[i:i + 90], (d.embedding for d in r.data)))
        os.makedirs(CACHE, exist_ok=True)
        json.dump(_VEC, open(VECTORES, "w", encoding="utf-8"))
    return [_VEC[t] for t in textos]


def _coseno(a: list, b: list) -> float:
    return sum(x * y for x, y in zip(a, b)) / ((sum(x * x for x in a) ** .5) * (sum(y * y for y in b) ** .5))


def _clave(c: dict) -> str:
    """Lo que se compara: la frase, con la pregunta del bot si la hay, porque "el negro" solo dice algo con ella."""
    return (f"el vendedor pregunto: {c['abierta']} / el cliente: " if c.get("abierta") else "") + c["frase"]


# ══ EL EXAMEN AFUERA ═════════════════════════════════════════════════════════

def frases_del_examen() -> list:
    import traduccion_sola as TS
    from traduccion_dificil import CIEN
    from traduccion_tercera import TERCERA
    return [f for _, f, _ in TS.casos()] + [f for _, f, _ in CIEN] + [f for _, f, _ in TERCERA]


def sin_examen(casos: list) -> tuple:
    examen = frases_del_examen()
    ve = vectores(examen)
    vc = vectores([_clave(c) for c in casos])
    quedan, fuera = [], []
    for c, v in zip(casos, vc):
        mas = max(((_coseno(v, x), f) for x, f in zip(ve, examen)), key=lambda y: y[0])
        if mas[0] >= UMBRAL_EXAMEN:
            fuera.append((c, mas))
        else:
            quedan.append(c)
    return quedan, fuera


# ══ LA BUSQUEDA ══════════════════════════════════════════════════════════════

def cargar() -> list:
    return [json.loads(x) for x in open(CASOS, encoding="utf-8")]


def buscar(caso: dict, casos: list, k: int = CINCO, sin_charla: str = "") -> list:
    """Los k casos mas parecidos del mismo estado, sin los de la charla que se mide."""
    q = vectores([_clave(caso)])[0]
    pool = [c for c in casos if c["estado"] == caso["estado"] and not (sin_charla and c["charla"] == sin_charla)]
    vs = vectores([_clave(c) for c in pool])
    return [c for _, c in sorted(zip((_coseno(q, v) for v in vs), pool), key=lambda x: -x[0])[:k]]


def como_ejemplo(c: dict) -> str:
    """Un caso como lo leeria el modelo."""
    previo = f'(el vendedor pregunto "{c["abierta"]}") ' if c.get("abierta") else ""
    return f'- {previo}"{c["frase"]}" -> {" + ".join(c["respuestas"]) or "nada"}'


# ══ LA CORRIDA ═══════════════════════════════════════════════════════════════

def llenar() -> None:
    casos, fuera = plantilla()
    quedan, examen = sin_examen(casos)
    vara = de_las_48() + de_las_58()
    todos = quedan + vara
    os.makedirs(CACHE, exist_ok=True)
    with open(CASOS, "w", encoding="utf-8") as fh:
        for c in todos:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")
    vectores([_clave(c) for c in todos])
    print(f"EL MOTOR DE CASOS de {TID}: {len(todos)} casos en {CASOS}")
    print(f"  la plantilla: {len(PL.FORMAS)} formas, {len(PL.FORMAS) * POR_FORMA} llenados, {len(casos)} validos, "
          f"{len(quedan)} despues del examen")
    print("  no entraron por la fuente: " + (", ".join(f"{k} {v}" for k, v in fuera.most_common()) or "ninguno"))
    print(f"  no entraron por parecerse al examen, a {UMBRAL_EXAMEN} o mas: {len(examen)}")
    for c, (cos, f) in examen[:10]:
        print(f"      {cos:.3f}  {c['frase'][:60]}  ~  {f[:60]}")
    print(f"  de las 48: {sum(c['origen'] == '48' for c in vara)} · de las 58: {sum(c['origen'] == '58' for c in vara)}")
    por = collections.Counter((c["estado"], "+".join(c["respuestas"])) for c in quedan)
    print("  la plantilla por estado: " + ", ".join(
        f"{e} {sum(v for (ee, _), v in por.items() if ee == e)}" for e in (PL.SIN, PL.CON, PL.ABIERTA)))
    print("  la plantilla por respuesta: " + ", ".join(
        f"{r} {v}" for r, v in collections.Counter(x for c in quedan for x in c["respuestas"]).most_common()))


def muestra(n: int) -> None:
    rnd = random.Random(SEMILLA)
    pl = [c for c in cargar() if c["origen"] == "plantilla"]
    for c in sorted(rnd.sample(pl, min(n, len(pl))), key=lambda c: (c["respuestas"], c["estado"])):
        print(f"{c['estado']:10} {' + '.join(c['respuestas']):24} "
              + (f"[bot: {c['abierta']}] " if c["abierta"] else "") + c["frase"])


def vecinos() -> None:
    """Sin modelo: cada turno de las 48 y las 58 con las respuestas de su vecino mas cercano, sin su charla; y si
    entre los cinco esta lo que vale. Es el piso de lo que los casos traen, no la etiqueta."""
    casos = cargar()
    nota = collections.Counter()
    for c in casos:
        if c["origen"] not in ("48", "58"):
            continue
        cinco = buscar(c, casos, CINCO, sin_charla=c["charla"])
        valen = [set(v) for v in c["valen"]]
        uno = set(cinco[0]["respuestas"]) if cinco else set()
        uno = R._58(uno) if c["origen"] == "58" else uno
        nota[(c["origen"], "casos")] += 1
        nota[(c["origen"], "primero")] += uno in valen
        union = set().union(*(set(x["respuestas"]) for x in cinco)) if cinco else set()
        nota[(c["origen"], "entre cinco")] += any(v <= union for v in valen)
        nota[(c["origen"], "de la plantilla")] += sum(x["origen"] == "plantilla" for x in cinco)
    print("LOS VECINOS, sin modelo y sin la charla que se mide")
    for o in ("48", "58"):
        n = nota[(o, "casos")]
        print(f"  las {o}: el primero acierta {nota[(o, 'primero')]} de {n} · lo que vale esta entre los cinco "
              f"{nota[(o, 'entre cinco')]} de {n} · de la plantilla {nota[(o, 'de la plantilla')]} de {n * CINCO}")


if __name__ == "__main__":
    if "--llenar" in ARGS:
        llenar()
    if "--muestra" in ARGS:
        muestra(int(ARGS[ARGS.index("--muestra") + 1]))
    if "--vecinos" in ARGS:
        vecinos()
