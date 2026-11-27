"""DONDE SE PIERDE CADA DATO DEL MENSAJE (27-nov-2026). Plan 7 de `lab/plan.md`.

Por cada casillero de la etiqueta, con sus palabras literales, la primera etapa de la cadena del banco donde ya no esta:
  luna    las palabras no estan en lo que Luna escribio: perdida de la traduccion
  pedido  Luna lo tiene, pero no queda en ningun pedido de `condicion.pedidos`
  uso     esta en un pedido pero ninguna funcion lo usa
  llega   lo usa alguna funcion
  sin consumidor  ninguna funcion de esta cadena lo lee: la cantidad
En el examen, ademas, el dato 2 de cada pedido y lo global de `examen/tramos.py`.
Sin modelo y sin gasto: lee lo que Luna separo, grabado. No cambia la cadena.

    python3 primeros/perdidas.py [--examen|--reales] [--ver]
"""
import collections, os, re, sys

AQUI = os.path.dirname(os.path.abspath(__file__))
VER = "--ver" in sys.argv
FICHA = "--ficha" in sys.argv
sys.path[:0] = [AQUI]
sys.dont_write_bytecode = True
import condicion as K  # noqa: E402
import ficha as FI  # noqa: E402

C, nrm = K.C, K.nrm
VACIAS = set("de del la el los las un una uno unos unas que y o a en con para por me mi se lo le al es sea su".split())
CONDICION = {"numero", "color", "atributo", "preferencia", "orden", "plataforma", "compat", "dato"}


def palabras(t):
    return [w for w in re.findall(r"[a-z0-9]+", nrm(t)) if w not in VACIAS]


def esta(p, texto):
    """Las palabras de contenido de `p` estan en `texto`: todas, o dos de cada tres si son tres o mas."""
    ws = palabras(p)
    if not ws:
        return True
    t = " ".join(palabras(texto))
    junto = t.replace(" ", "")
    hay = sum(1 for w in ws if re.search(r"\b" + re.escape(w), t) or w in junto)
    return hay == len(ws) or (len(ws) >= 3 and hay * 3 >= len(ws) * 2)


def texto_pedido(f):
    return " | ".join([f["consulta"], f.get("nombre") or ""] + [p for p, _ in f["partes"]]
                      + [d.get("texto") or "" for d in f["atadas"]] + list(f["sin_dato"]))


def usado(c, peds):
    """True si llega a la funcion que le toca; "dicho" si queda dicho sin dato o no reconocido; falso si no."""
    t, p = c["tipo"], c["palabras"]
    dicho = any(esta(p, s) for f in peds for s in list(f["sin_dato"]) + list(f.get("no_reconocido", [])))
    if t == "rubro":
        r = nrm(str(c["valor"]).split(":", 1)[-1]).replace("_", " ")
        return any(f["rubro"] and (nrm(f["rubro"]) == r or nrm(f["rubro"]).rstrip("s") == r.rstrip("s")) for f in peds)
    if t in ("marca", "modelo"):
        # Llega si va al nombre de existe, o si la condicion lo ato como marca o modelo para filtrar.
        return any(esta(p, f.get("nombre") or "") for f in peds) or any(
            d["tipo"] in ("marca", "modelo") and (esta(p, d.get("texto") or "") or esta(d.get("texto") or "x y z", p))
            for f in peds for d in f["atadas"])
    if t in CONDICION:
        if any(esta(p, d.get("texto") or "") or esta(d.get("texto") or "x y z", p) for f in peds for d in f["atadas"]):
            return True
        return "dicho" if dicho else False
    if t == "fuera":
        if c["valor"] == "ignorar":
            return True
        # Lo que la tienda no vende llega si queda dicho, o si va en el nombre a existe y existe dice que no hay.
        return dicho or any(f.get("nombre") and esta(p, f["nombre"]) and FI.EX.existe(f["nombre"])[0] == "no_hay"
                            for f in peds)
    return None


def main():
    ex, luna = C.cargar()
    T = {}
    if C.EXAMEN:
        sys.path.insert(0, os.path.join(AQUI, "..", "examen"))
        from tramos import T
    n = collections.Counter()
    casos = collections.defaultdict(list)
    for e in ex:
        textos = (luna.get(e["id"], {}).get("salida") or {}).get("textos") or []
        lt = " | ".join(re.sub(r"\[[^\]]*\]", " ", t) for t in textos)
        if FICHA:
            peds, tramos = FI.armar(textos)
            n[("tramos", "sin uso")] += sum(1 for tr in tramos if not tr["usos"])
            n[("tramos", "total")] += len(tramos)
        else:
            peds = K.pedidos(textos)
        tp = " || ".join(texto_pedido(f) for f in peds)
        for ip, p in enumerate(e["pedidos"]):
            for c in p["cas"]:
                tipo = c["tipo"]
                if tipo == "cantidad":
                    etapa = "sin consumidor"
                elif not esta(c["palabras"], lt):
                    etapa = "luna"
                elif not esta(c["palabras"], tp):
                    etapa = "pedido"
                else:
                    u = usado(c, peds)
                    etapa = "dicho" if u == "dicho" else ("llega" if u else "uso")
                grupo = "condicion" if tipo in CONDICION else tipo
                n[(grupo, etapa)] += 1
                if etapa in ("pedido", "uso"):
                    casos[(grupo, etapa)].append((e["id"], c["palabras"], e["texto"][:90], textos))
        t = T.get(e["id"])
        if t:
            cadena = set()
            for x in textos:
                cadena |= set(C.dato2(x)[0])
            for _, ds in t["p"]:
                for d in ds:
                    if d in ("ofrecer", "fuera"):
                        continue
                    clase = d.split(":")[0]
                    produce = clase in ("precio", "stock", "campo", "tema")
                    etapa = ("llega" if d in cadena else "uso") if produce else "sin consumidor"
                    n[("dato2 " + clase, etapa)] += 1
                    if etapa == "uso":
                        casos[("dato2 " + clase, etapa)].append((e["id"], d, e["texto"][:90], textos))
            for tramo, tipo, _ in t.get("g", []):
                if tipo in ("destino", "pago", "tope"):
                    etapa = "luna" if not esta(tramo, lt) else "sin consumidor"
                    n[("global " + tipo, etapa)] += 1
    etapas = ["llega", "dicho", "uso", "pedido", "luna", "sin consumidor"]
    if FICHA:
        print(f"ficha: {n[('tramos', 'total')]} tramos, sin ningun uso {n[('tramos', 'sin uso')]}\n")
    grupos = sorted({g for g, _ in n if g != "tramos"})
    print(f"{'':22}" + "".join(f"{x:>16}" for x in etapas))
    for g in grupos:
        print(f"{g:22}" + "".join(f"{n[(g, x)]:>16}" for x in etapas))
    tot = {x: sum(n[(g, x)] for g in grupos) for x in etapas}
    print(f"{'total':22}" + "".join(f"{tot[x]:>16}" for x in etapas))
    luna_ok = tot["llega"] + tot["dicho"] + tot["uso"] + tot["pedido"]
    print(f"\ncon lo que Luna si tenia, {luna_ok}: llega {tot['llega']}, dicho sin dato {tot['dicho']}, "
          f"el codigo lo pierde en el pedido {tot['pedido']}, sin usar {tot['uso']}")
    if VER:
        for k, v in sorted(casos.items()):
            print(f"\n== {k[0]} · {k[1]} · {len(v)}")
            for i, pal, tx, ts in v[:12]:
                print(f"  {i:10} {pal!r:28} {tx}")
                print(f"  {'':10} luna: {' / '.join(ts)[:160]}")


if __name__ == "__main__":
    main()
