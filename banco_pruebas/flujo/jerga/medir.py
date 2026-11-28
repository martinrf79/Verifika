"""LA BASE DE JERGA MEDIDA CONTRA LAS ETIQUETAS, CON EL TRAMO PERFECTO (27-nov-2026).

Capa: traduccion de cada tramo a un concepto de la tienda, con la separacion de las etiquetas, FICHA 108. Entra el
pedazo literal etiquetado, sale el veredicto del nexo, y se compara con el concepto de la etiqueta. Siempre de los dos
lados: lo que acierta y lo que rompe, que es tomar un concepto de la tienda donde la etiqueta dice que no hay.

Por tramo:
  bien         claro y con el concepto de la etiqueta; para lo que no pide nada, que no tome ningun concepto
  duda_con     ambiguo o parcial, con el concepto bueno entre los candidatos: lo elige Luna o se repregunta
  no_lo_toma   la tabla no lo conoce, o lo da por vago: va al respaldo, no erra
  error        claro con otro concepto, o ambiguo sin el bueno: lo que hay que mirar
  falsa_alarma lo que no pide nada, o pide algo que no hay, y la tabla le pone un concepto de la tienda
Marca, modelo, cantidad y numeros no son de la tabla: los lee el codigo, y se cuentan aparte.

El examen y las reales no se usaron para escribir la tabla: los agentes no los vieron.

    python3 medir.py [--semillas] [--ver error|falsa_alarma|duda_con|no_lo_toma] [--reales|--examen]
"""
import json, os, sys
from collections import Counter, defaultdict

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import tabla as T  # noqa: E402
import nexo as N  # noqa: E402

PRIMEROS = os.path.join(AQUI, "..", "primeros")
CONCEPTO = {"rubro", "orden", "preferencia", "atributo", "color", "plataforma", "origen"}
DEL_CODIGO = {"marca", "modelo", "cantidad", "numero", "compat"}


def tramos(nombre):
    for m in json.load(open(os.path.join(PRIMEROS, nombre + ".json"))):
        for p in m["pedidos"]:
            for c in p["cas"]:
                yield m["id"], m["texto"], c
        for c in m.get("global", []):
            yield m["id"], m["texto"], c


def juzgar(r, c):
    tipo, valor = c["tipo"], c["valor"]
    ver = r["veredicto"]
    elegidos = [x["concepto"] for x in r.get("conceptos", [])] if ver == "claro" else []
    if tipo in CONCEPTO:
        if ver == "claro" and valor in elegidos:
            return "bien"
        if ver in ("ambiguo", "parcial") and valor in r["candidatos"]:
            return "duda_con"
        if ver in ("nada", "vago", "general", "parcial"):
            return "no_lo_toma"
        return "error"
    if tipo == "fuera":
        if valor == "no_vende":
            if ver == "claro" and any(e.startswith("no_vende:") for e in elegidos):
                return "bien"
            if ver in ("ambiguo", "parcial") and any(e.startswith("no_vende:") for e in r["candidatos"]):
                return "duda_con"
            return "no_lo_toma" if ver in ("nada", "vago", "general", "parcial") else "error"
        # ignorar o sin dato: que no le ponga producto, ni atributo, ni orden
        prod = [e for e in (elegidos or r.get("candidatos", []))
                if T.clase_de(e) in CONCEPTO or e.startswith("no_vende:")]
        if not prod:
            return "bien"
        return "falsa_alarma" if ver == "claro" else "duda_con"
    return None


def medir(nombre, base, ver=None):
    res = defaultdict(Counter)
    aparte = Counter()
    for mid, texto, c in tramos(nombre):
        if c["tipo"] in DEL_CODIGO:
            aparte[c["tipo"]] += 1
            continue
        r = base.resolver(c["palabras"])
        j = juzgar(r, c)
        if j is None:
            aparte[c["tipo"]] += 1
            continue
        clave = c["tipo"] if c["tipo"] != "fuera" else "fuera:" + c["valor"]
        res[clave][j] += 1
        if ver and j == ver:
            print(f"  {mid} [{clave}] '{c['palabras']}' -> {r['veredicto']} {r.get('candidatos')}  | {texto[:70]}")
    return res, aparte


def tabla_md(res):
    cols = ["bien", "duda_con", "no_lo_toma", "error", "falsa_alarma"]
    tot = Counter()
    print("| clase | tramos | " + " | ".join(cols) + " |")
    print("|---|---|" + "---|" * len(cols))
    for k in sorted(res, key=lambda k: -sum(res[k].values())):
        n = sum(res[k].values())
        tot.update(res[k])
        print(f"| {k} | {n} | " + " | ".join(str(res[k][c]) for c in cols) + " |")
    n = sum(tot.values())
    print(f"| total | {n} | " + " | ".join(str(tot[c]) for c in cols) + " |")



def medir_vectores(nombres=("reales", "examen"), k=5, ver=False):
    """Etapa 1 paso 2: sobre los tramos que el codigo NO da por claros y piden un concepto de la tienda, si el
    concepto de la etiqueta esta entre los k candidatos de los embeddings. Mide solo la busqueda, con el tramo
    perfecto. Con contexto: el nombre del rubro etiquetado en el mismo pedido, como si lo diera otra fila."""
    import vectores as V
    base, ix = N.base(), V.Indice()
    nombre = {k_: v["nombre"] for k_, v in T.ENCARGO["conceptos"].items()}
    for n in nombres:
        r = {m: Counter() for m in ("sin contexto", "con contexto")}
        total = 0
        for m in json.load(open(os.path.join(PRIMEROS, n + ".json"))):
            for p in m["pedidos"]:
                rub = [c["valor"] for c in p["cas"] if c["tipo"] == "rubro" and isinstance(c["valor"], str)]
                for c in p["cas"]:
                    if c["tipo"] not in CONCEPTO and not (c["tipo"] == "fuera" and c["valor"] == "no_vende"):
                        continue
                    if base.resolver(c["palabras"])["veredicto"] == "claro":
                        continue
                    total += 1
                    buenos = c["valor"] if isinstance(c["valor"], list) else [c["valor"]]
                    ctx = nombre.get(rub[0], "") if rub and c["tipo"] != "rubro" else ""
                    for modo in r:
                        cs = [x["concepto"] for x in ix.candidatos(c["palabras"], k, contexto=ctx if modo == "con contexto" else "")]
                        bien = (lambda x: x.startswith("no_vende:")) if c["tipo"] == "fuera" else (lambda x: x in buenos)
                        ok = any(bien(x) for x in cs)
                        r[modo]["esta" if ok else "no_esta"] += 1
                        r[modo]["primero"] += bool(cs and bien(cs[0]))
                        if ver and not ok and modo == "con contexto":
                            print(f"   {m['id']} {c['palabras']!r} {c['valor']} ctx={ctx!r} -> {cs}")
        print(f"\n## {n}: {total} tramos que el codigo no da por claros")
        for modo, v in r.items():
            print(f"  {modo:13} el bueno entre los {k}: {v['esta']}, primero: {v['primero']}, no esta: {v['no_esta']}")


if __name__ == "__main__":
    a = sys.argv[1:]
    ver = a[a.index("--ver") + 1] if "--ver" in a else None
    nombres = ["reales"] if "--reales" in a else ["examen"] if "--examen" in a else ["reales", "examen"]
    if "--vectores" in a:
        medir_vectores(nombres, ver=bool(ver))
        sys.exit()
    if "--semillas" in a:
        t, g, tr, v, _ = T.armar(solo_semillas=True)
        for x in t + g + tr + v:
            x.setdefault("nrm", T.nrm(x["expresion"]))
        base = N.Base((t, g, tr, v))
        print("SOLO SEMILLAS: alias.json, la base de reglas y no_vendidas")
    else:
        base = N.base()
    for n in nombres:
        print(f"\n## {n}")
        res, aparte = medir(n, base, ver)
        tabla_md(res)
        print("aparte, del codigo:", dict(aparte))

