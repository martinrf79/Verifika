"""Segunda tanda: datos tecnicos, compatibilidad y memoria implicita. Cada llamada se anota con sus tokens en gasto_jev.jsonl."""
import json, os, re, sys, csv, collections, datetime
D = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, D)
import fuente as F
from fuente import PS, FAQ, K, n, REPO
from sondas import crit, rank, NOM, STOCK, RUBROS, linea_rica
GASTO = os.path.join(D, "gasto_jev.jsonl")
def llamar(body, etiqueta):
    r = F.llamar(body)
    with open(GASTO, "a") as f:
        f.write(json.dumps({"cuando": datetime.datetime.utcnow().isoformat(), "prueba": etiqueta, "tokens": r["usage"]["input_tokens"],
                            "usd": round(r["usage"]["input_tokens"] * 0.042 / 1e6, 5)}) + "\n")
    return r
def jev(qs, state, etiqueta, lote=40):
    out, items = {}, list(qs.items())
    for i in range(0, len(items), lote):
        out.update(llamar({"state": state, "model": "jev-latest", "questions": dict(items[i:i + lote])}, etiqueta)["answers"])
    return out
COMPAT = {(r["marca"], r["modelo"]): r for r in csv.DictReader(open(os.path.join(REPO, "data/clientes/verifika_prod/compatibilidad.csv")))}
def hoja(rubro):
    """La hoja rica de un rubro: lo que Jev lee despues de elegir el rubro."""
    out = []
    for p in PS:
        if p["categoria"] != rubro: continue
        c = COMPAT.get((p.get("marca"), p.get("modelo")))
        out.append(linea_rica(p) + (f" | anda con: {c['plataformas'].replace('|', ', ')}; conecta por {c['conecta_por']}" if c else ""))
    return f"CATALOGO DE {rubro.upper()} CON DATOS:\n" + "\n".join(out)

SI = lambda v: n(v).startswith("si")
SPECS = {"bluetooth": (SI, "con bluetooth", "que se conecte al celular sin cable"),
         "retroiluminacion": (SI, "con retroiluminacion", "que tenga lucecitas de colores"),
         "resistencia_agua": (SI, "resistente al agua", "que aguante si le cae agua"),
         "tactil": (SI, "con pantalla tactil", "que pueda tocar la pantalla con el dedo"),
         "lector_huella": (SI, "con lector de huella", "que se desbloquee con el dedo"),
         "thunderbolt": (SI, "con puerto Thunderbolt", "con el puerto rapido de Intel para monitores"),
         "ram_ampliable": (SI, "con RAM ampliable", "que despues le pueda agregar mas memoria"),
         "lector_tarjetas": (SI, "con lector de tarjetas", "donde pueda meter la tarjetita de la camara"),
         "conexion": (lambda v: "inalambr" in n(v), "inalambrico", "sin cables")}
def s6b_specs():
    casos = []
    for r in RUBROS:
        del_r = [p for p in STOCK if p["categoria"] == r]
        for sid, (f, formal, vaga) in SPECS.items():
            b = {str(p["id"]) for p in del_r if (p.get("specs") or {}).get(sid) and f((p.get("specs") or {})[sid])}
            con_dato = [p for p in del_r if (p.get("specs") or {}).get(sid)]
            if 0 < len(b) < len(con_dato):
                for forma, t in (("formal", f"busco {r} {formal}"), ("vaga", f"quiero {r} {vaga}")): casos.append((r, t, b, forma))
    c = collections.Counter(); mal = []
    for r in sorted({x[0] for x in casos}):
        sub = [(i, x) for i, x in enumerate(casos) if x[0] == r]
        a = jev({f"q{i}": {"type": "choice", "criteria": crit(r, True), "instructions": f"El cliente pide: «{t}». Que producto de la hoja cumple lo que pide?"} for i, (_, t, _, _) in sub}, hoja(r), "s6b_specs")
        for i, (_, t, b, forma) in sub:
            k = min(5, len(b)); c[forma + "#"] += 1; c[forma] += a[f"q{i}"]["choice"] in b
            c[forma + "k"] += sum(x in b for x in rank(a[f"q{i}"])[:k]); c[forma + "kp"] += k
            if a[f"q{i}"]["choice"] not in b: mal.append((t, NOM[a[f"q{i}"]["choice"]]))
    return "specs por rubro: " + "; ".join(f"{fo} top1 {c[fo]}/{c[fo+'#']}, primeros k {c[fo+'k']}/{c[fo+'kp']}" for fo in ("formal", "vaga")), mal[:8]

PLAT = {"macos": ("que ande con Mac", "para mi MacBook"), "ps5": ("compatible con PS5", "para la play 5"), "ios": ("que ande con iPhone o iPad", "para el iPad de mi hija"),
        "android": ("compatible con Android", "para mi celu Samsung"), "smart_tv": ("que ande con un Smart TV", "para enchufar a la tele"),
        "nintendo_switch": ("compatible con Nintendo Switch", "para la Switch"), "xbox": ("compatible con Xbox", "para la Xbox de mi hermano")}
def s9_compat():
    casos = []
    for r in RUBROS:
        del_r = [p for p in STOCK if p["categoria"] == r]
        con = [(p, COMPAT.get((p.get("marca"), p.get("modelo")))) for p in del_r]
        con = [(p, c) for p, c in con if c]
        for pl, (formal, vaga) in PLAT.items():
            b = {str(p["id"]) for p, c in con if pl in c["plataformas"].split("|")}
            if 0 < len(b) < len(con):
                for forma, t in (("formal", f"busco {r} {formal}"), ("vaga", f"necesito {r} {vaga}")): casos.append((r, t, b, forma))
    c = collections.Counter(); mal = []
    for r in sorted({x[0] for x in casos}):
        sub = [(i, x) for i, x in enumerate(casos) if x[0] == r]
        a = jev({f"q{i}": {"type": "choice", "criteria": crit(r, True), "instructions": f"El cliente pide: «{t}». Que producto de la hoja anda con lo que dice?"} for i, (_, t, _, _) in sub}, hoja(r), "s9_compat")
        for i, (_, t, b, forma) in sub:
            k = min(5, len(b)); c[forma + "#"] += 1; c[forma] += a[f"q{i}"]["choice"] in b
            c[forma + "k"] += sum(x in b for x in rank(a[f"q{i}"])[:k]); c[forma + "kp"] += k
            if a[f"q{i}"]["choice"] not in b: mal.append((t, NOM[a[f"q{i}"]["choice"]]))
    return "compatibilidad por rubro: " + "; ".join(f"{fo} top1 {c[fo]}/{c[fo+'#']}, primeros k {c[fo+'k']}/{c[fo+'kp']}" for fo in ("formal", "vaga")), mal[:8]

NOMBRE = {"fuente": "fuente de alimentacion para PC", "parlante": "parlante o altavoz", "silla gamer": "silla gamer o de escritorio"}
def s10_memoria():
    """Rubros que el mensaje no nombra y salen de la charla: con la libreta sola y con la charla entera."""
    from app.core.flujo import marcador
    from app.core.flujo.agenda import preguntas
    T = [json.loads(l) for l in open(os.path.join(D, "turnos.jsonl"))]
    hist = collections.defaultdict(list)
    for t in T: hist[t["charla"]].append(t["mensaje"])
    casos = []
    for t in T:
        rub = {p["rubro"] for p in preguntas(t["agenda"]) if p["accion"] == "buscar" and p.get("rubro") in RUBROS}
        nombrados = {r for r in RUBROS if f'el rubro {r}' in marcador.tabla(t["mensaje"], "verifika_prod")}
        ocultos = rub - nombrados
        if ocultos and t["turno"] > 0: casos.append((t, ocultos))
    c = collections.Counter(); det = []
    for t, oc in casos:
        antes = "\n".join(f"CLIENTE: {m}" for m in hist[t["charla"]][:t["turno"]])
        for modo, st in (("libreta", t["libreta"]), ("charla", f"LA CHARLA:\n{antes}\n\n{t['libreta']}")):
            st += f"\n\nULTIMO MENSAJE DEL CLIENTE: {t['mensaje']}"
            a = jev({f"r_{r}": {"type": "noul", "instructions": f"Lo que pide el ULTIMO MENSAJE, leido con la charla, incluye productos del rubro {NOMBRE.get(r, r)}?"} for r in RUBROS}, st, "s10_memoria")
            got = {r for r in RUBROS if a[f"r_{r}"]["noul"] >= .5}
            c[modo + "#"] += len(oc); c[modo] += len(oc & got); c[modo + "mas"] += len(got - oc)
            det.append((modo, t["charla"], t["turno"], t["mensaje"][:60], sorted(oc), sorted(got)))
    return f"memoria, rubros no nombrados en {len(casos)} turnos: " + "; ".join(f"{m} {c[m]}/{c[m+'#']} de mas {c[m+'mas']}" for m in ("libreta", "charla")), det

if __name__ == "__main__":
    for s in sys.argv[1:]:
        res, mal = globals()[s](); print(res); [print("   ", m) for m in mal]
    g = [json.loads(l) for l in open(GASTO)]
    print(f"GASTO anotado: {sum(x['tokens'] for x in g)/1e6:.2f} M tokens, {sum(x['usd'] for x in g):.3f} USD en {len(g)} llamadas")
