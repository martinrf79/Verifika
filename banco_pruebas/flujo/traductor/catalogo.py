import csv,collections,re,sys,os
D=os.path.join(os.path.dirname(os.path.abspath(__file__)),"../../../data/clientes/verifika_prod/")
P=list(csv.DictReader(open(D+"productos.csv",encoding="utf-8")))
C={(c["categoria"],c["marca"],c["modelo"]):c for c in csv.DictReader(open(D+"compatibilidad.csv",encoding="utf-8"))}
MOD=collections.OrderedDict()
for p in P: MOD.setdefault((p["categoria"],p["marca"],p["modelo"]),[]).append(p)
def inal(k):
    c=C[k]["conecta_por"].split("|"); return "bluetooth" in c or "receptor_usb" in c
def acept(r):
    """claves de modelo que cumplen la regla"""
    if r.get("vacio"): return set()
    out=set()
    for k,rows in MOD.items():
        cat,marca,mod=k; p=rows[0]; c=C[k]
        if "rubro" in r and cat not in r["rubro"]: continue
        if r.get("gaming") and not p["uso_recomendado"].startswith("Gaming"): continue
        if "marca" in r and marca not in r["marca"]: continue
        if "no_marca" in r and marca in r["no_marca"]: continue
        if "modelos" in r and not any(m in mod for m in r["modelos"]): continue
        if "modelo_re" in r and not re.search(r["modelo_re"],mod): continue
        if "inal" in r and inal(k)!=r["inal"]: continue
        if "plat" in r and not set(r["plat"])&set(c["plataformas"].split("|")): continue
        if "color" in r and not any(x["color"]==r["color"] for x in rows): continue
        if any(not any(re.search(rx,x[f],re.I) for f in cmp.split("|") for x in rows[:1]) for cmp,rx in [(a,b) for a,b in r.get("texto",[])] for x in [0]): continue
        if "precio_max" in r and min(int(x["precio_ars"]) for x in rows)>r["precio_max"]: continue
        if "precio_min" in r and min(int(x["precio_ars"]) for x in rows)<r["precio_min"]: continue
        out.add(k)
    return out
