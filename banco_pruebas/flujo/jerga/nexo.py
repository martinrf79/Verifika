"""EL NEXO: DE CADA TRAMO DEL CLIENTE A SU CONCEPTO, Y DEL CONCEPTO A DONDE ESTA EL DATO EN LA FUENTE (27-nov-2026).

Entra un tramo literal, el pedazo que separo Luna. Sale un veredicto, como la regla 7.0 del repo:
  claro     un concepto por clase, sin discusion: el codigo lo usa directo.
  ambiguo   la tabla marca el tramo como trampa, o dos conceptos de la misma clase empatan: los candidatos van a
            Luna para que elija, o se repregunta. La tabla nunca elige sola entre dos.
  vago      el cliente pide algo que la ficha no trae, "que se la banque": se dice que no hay ese dato.
  nada      la tabla no lo conoce: va al respaldo, embeddings o Luna. Nunca se inventa.

Cada concepto lleva su destino, el dato 2:
  condicion    rubro, atributo, preferencia, plataforma, color, origen u orden: la condicion que el codigo ejecuta
               sobre la fuente, de `conceptos.json`.
  columna      un campo que el cliente pregunta: la columna de productos.csv o specs_por_modelo.csv.
  faq          un tema de la tienda: el tema de faq.json.
  no_vende     lo que la tienda no tiene, con la alternativa real si hay.
La tabla general da intencion, relleno, negacion, cantidad, plata y demas, y si enlaza a la tienda, el destino de ese
concepto.

Busca en tres pasos, del mas seguro al menos: la expresion exacta, las expresiones contenidas en el tramo, palabra
entera, de la mas larga a la mas corta, y el tipeo, por parecido de letras. Lo que encuentra por tipeo nunca sale
claro si hay otro candidato cerca.

    python3 nexo.py "che tenes auris sin cable que no salga un huevo"
"""
import difflib, json, os, sys
from collections import defaultdict

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import tabla as T  # noqa: E402

nrm = T.nrm
UMBRAL_TIPEO = 0.86   # parecido minimo para tomar un tipeo; por debajo, "baratp" contra "barato" ya pasa con 0,92


def singular(p):
    if len(p) > 4 and p.endswith("es") and p[-3] not in "aeiou":
        return p[:-2]
    if len(p) > 3 and p.endswith("s"):
        return p[:-1]
    return p


def forma(s):
    return " ".join(singular(p) for p in nrm(s).split())


# Palabras sin contenido: solas no son una expresion, y no cuentan para saber cuanto del tramo se entendio.
VACIAS = set("""a al algo alguna alguno ante con cosa cosita de del donde e el ella en entre es esa ese eso esta este
esto hace hay la las le lo los me mi mis muy ni o para pero por que quiero se si sin su sus te tenes tu un una uno unos
unas va van y ya yo""".split())


NIEGAN = {"no", "ni", "tampoco", "nada", "nunca", "evitar", "menos"}
OPUESTO = {"orden:mas_barato": "orden:mas_caro", "orden:mas_caro": "orden:mas_barato",
           "orden:mas_liviano": "orden:mas_pesado", "orden:mas_pesado": "orden:mas_liviano"}


def negar(x, pal_tramo):
    """Si una palabra que niega queda antes de la expresion y no es parte de ella, el concepto va negado; un orden
    con opuesto se da vuelta: "que no sea caro" es el mas barato."""
    exp = x["expresion"].split()
    try:
        i = next(k for k in range(len(pal_tramo)) if pal_tramo[k:k + len(exp)] == exp)
    except StopIteration:
        return x
    if not (set(pal_tramo[:i]) & NIEGAN) or set(exp) & NIEGAN or x["modo"] == "negado":
        return x
    if x["concepto"] in OPUESTO:
        return dict(x, concepto=OPUESTO[x["concepto"]], via=x["via"] + "+negado")
    return dict(x, modo="negado")


class Base:
    def __init__(self, filas=None):
        tienda, general, trampas, vagas = filas or T.cargar()
        self.idx = defaultdict(list)          # forma -> filas
        for x in tienda:
            if forma(x["expresion"]) not in VACIAS:
                self.idx[forma(x["expresion"])].append(("tienda", x["concepto"], x.get("modo", "")))
        for x in general:
            if forma(x["expresion"]) not in VACIAS:
                self.idx[forma(x["expresion"])].append(("general", x["valor"], x.get("enlace")))
        self.trampa = {forma(x["expresion"]): x for x in trampas}
        self.vaga = {forma(x["expresion"]): x for x in vagas}
        self.formas = list(self.idx)
        self.largo = max((len(f.split()) for f in self.formas), default=1)
        self.conceptos = json.load(open(os.path.join(AQUI, "..", "conceptos", "conceptos.json")))

    def destino(self, cid):
        E = T.ENCARGO
        if not cid:
            return None
        if cid.startswith("no_vende:"):
            return {"tipo": "no_vende", "alternativa": E["no_vende"].get(cid, {}).get("alternativa")}
        if cid in E["campos"]:
            col = E["campos"][cid]["columna_ficha"]
            return {"tipo": "columna", "columna": col} if col else {"tipo": "sin_columna"}
        if cid in E["temas"]:
            return {"tipo": "faq", "tema": cid.split(":", 1)[1]}
        if cid in self.conceptos:
            return {"tipo": "condicion", "cond": self.conceptos[cid]["cond"]}
        return None

    def hits(self, tramo):
        f = forma(tramo)
        pal = f.split()
        out = []
        if f in self.idx:
            out += [(f, "exacta", 1.0, h) for h in self.idx[f]]
            return out, [f]
        # contenidas, palabra entera, la mas larga primero, sin pisar palabras ya tomadas
        tomadas, vistas = set(), []
        for n in range(min(self.largo, len(pal)), 0, -1):
            for i in range(len(pal) - n + 1):
                if tomadas & set(range(i, i + n)):
                    continue
                g = " ".join(pal[i:i + n])
                if g in self.idx:
                    out += [(g, "contenida", 0.95, h) for h in self.idx[g]]
                    tomadas |= set(range(i, i + n))
                    vistas.append(g)
        # tipeo: lo que quedo suelto, palabra por palabra y de a dos, contra las formas de igual largo
        resto = [i for i in range(len(pal)) if i not in tomadas]
        for i in resto:
            for n in (2, 1):
                if n == 2 and (i + 1 not in resto):
                    continue
                g = " ".join(pal[i:i + n])
                if len(g) < 4:
                    continue
                cerca = difflib.get_close_matches(g, [x for x in self.formas if len(x.split()) == n], 3, UMBRAL_TIPEO)
                for c in cerca:
                    r = difflib.SequenceMatcher(None, g, c).ratio()
                    out += [(c, "tipeo", round(0.9 * r, 3), h) for h in self.idx[c]]
                    vistas.append(c)
                if cerca:
                    break
        return out, vistas

    def resolver(self, tramo):
        f = forma(tramo)
        hits, vistas = self.hits(tramo)
        # Trampa sobre el tramo entero o sobre una expresion que encontro. Solo vuelve dudoso el tramo si reclaman dos
        # conceptos de la tienda o mas: "placa" es video o mother. Si es un concepto contra nada, "barato" orden o
        # relleno, el tramo ya llego como parte del pedido, separado por Luna: sigue el concepto y queda el aviso.
        avisos = []
        for g in [f] + vistas:
            if g in self.trampa:
                t = self.trampa[g]
                reales = [c for c in t["puede_ser"] if T.valido_tienda(c)]
                if len(reales) >= 2:
                    return {"tramo": tramo, "veredicto": "ambiguo", "candidatos": reales,
                            "por": f"trampa: {t['expresion']}", "destinos": {c: self.destino(c) for c in reales},
                            "general": []}
                avisos.append(t)
        tienda = [(g, via, p, h) for g, via, p, h in hits if h[0] == "tienda"]
        gen = [{"valor": h[1], "enlace": h[2], "via": via, "expresion": g} for g, via, p, h in hits if h[0] == "general"]
        if not tienda:
            for g in [f] + vistas:
                if g in self.vaga:
                    v = self.vaga[g]
                    return {"tramo": tramo, "veredicto": "vago", "candidatos": [v["concepto_cercano"]] if v[
                        "concepto_cercano"] else [], "por": v["nota"], "destinos": {}, "general": gen}
        # el enlace de la general cuenta como concepto de la tienda, con la misma via
        for x in gen:
            if x["enlace"]:
                tienda.append((x["expresion"], x["via"], 0.94 if x["via"] != "tipeo" else 0.8,
                               ("tienda", x["enlace"], "")))
        if not tienda:
            return {"tramo": tramo, "veredicto": "general" if gen else "nada", "candidatos": [], "destinos": {},
                    "general": gen}
        por_clase = defaultdict(dict)
        for g, via, p, (_t, cid, modo) in tienda:
            if cid.startswith("no_vende:"):
                cid = "no_vende:" + forma(cid.split(":", 1)[1]).replace(" ", "_")
            c = T.clase_de(cid) if not cid.startswith("no_vende:") else "no_vende"
            prev = por_clase[c].get(cid)
            if not prev or p > prev["puntaje"]:
                por_clase[c][cid] = {"concepto": cid, "modo": modo, "via": via, "puntaje": p, "expresion": g}
        for c in por_clase:
            por_clase[c] = {v["concepto"]: v for v in (negar(x, f.split()) for x in por_clase[c].values())}
        llenas = [p for p in f.split() if p not in VACIAS]
        cubiertas = {p for g, *_ in tienda for p in g.split()} | {p for x in gen for p in x["expresion"].split()}
        cobertura = sum(1 for p in llenas if p in cubiertas) / max(1, len(llenas))
        elegidos, dudosos = [], []
        for c, cands in por_clase.items():
            orden = sorted(cands.values(), key=lambda x: -x["puntaje"])
            if len(orden) == 1 or orden[0]["puntaje"] - orden[1]["puntaje"] >= 0.04:
                elegidos.append(orden[0])
            else:
                dudosos += orden
        ver = "ambiguo" if dudosos else "claro"
        if ver == "claro" and cobertura < 0.5:
            # una descripcion larga donde la tabla entendio una palabra suelta: va al respaldo con los candidatos
            ver, dudosos = "parcial", elegidos
        cands = [x["concepto"] for x in (dudosos or elegidos)]
        return {"tramo": tramo, "veredicto": ver, "conceptos": elegidos, "cobertura": round(cobertura, 2), "candidatos": cands,
                "destinos": {x["concepto"]: self.destino(x["concepto"]) for x in elegidos + dudosos}, "general": gen,
                "avisos": [a["expresion"] + ": " + "/".join(a["puede_ser"]) for a in avisos]}


_BASE = None


def base():
    global _BASE
    if _BASE is None:
        _BASE = Base()
    return _BASE


if __name__ == "__main__":
    for t in sys.argv[1:]:
        print(json.dumps(base().resolver(t), ensure_ascii=False, indent=1))
