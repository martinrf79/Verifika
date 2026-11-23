import sys,os,json,collections,random
sys.dont_write_bytecode=True
T=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,T)
from muestra import M
from columnas import COL,nrm
CAND=json.load(open(T+"/cand.json")); AC=json.load(open(T+"/aceptables.json"))
def evaluar(col,q):
    """lista de (filtro, 'cumple'|'no'|'sin_dato')"""
    out=[]
    def add(f,v): out.append((f,v))
    if q.get("rubro"): add("rubro","cumple" if col["rubro"]==q["rubro"] else "no")
    if q.get("marca"): add("marca","cumple" if any(nrm(m)==nrm(col["marca"]) for m in q["marca"]) else "no")
    if q.get("modelo"): add("modelo","cumple" if any(nrm(m) and nrm(m) in nrm(col["modelo"]) for m in q["modelo"]) else "no")
    if q.get("inalambrico") is not None:
        v=col["inalambrico"]; add("inalambrico","sin_dato" if v is None else "cumple" if v==q["inalambrico"] else "no")
    if q.get("conexion"):
        v=col["conexion"]; add("conexion","sin_dato" if v is None else "cumple" if q["conexion"] in v else "no")
    if q.get("compatible_con"):
        v=col["compatible_con"]; add("compatible_con","sin_dato" if v is None else "cumple" if set(q["compatible_con"])<=set(v) else "no")
    if q.get("precio_max") is not None: add("precio_max","cumple" if col["precio"]<=q["precio_max"] else "no")
    if q.get("precio_min") is not None: add("precio_min","cumple" if col["precio"]>=q["precio_min"] else "no")
    if q.get("color"):
        v=col["color"]; add("color","sin_dato" if v is None else "cumple" if any(nrm(q["color"]) in c for c in v) else "no")
    if q.get("capacidad_gb") is not None:
        v=col["capacidad_gb"]; add("capacidad_gb","sin_dato" if v is None else "cumple" if v==q["capacidad_gb"] else "no")
    if q.get("rgb") is not None:
        v=col["rgb"]; add("rgb","sin_dato" if v is None else "cumple" if v==q["rgb"] else "no")
    if q.get("excluir_pais"):
        v=col["pais"]; p=nrm(q["excluir_pais"])
        add("excluir_pais","sin_dato" if v is None else "no" if v==[p] else "sin_dato" if p in v else "cumple")
    return out
def decidir(i,q):
    top=[tuple(k) for k in CAND[i]["top"]]
    otros=(q.get("otros_requisitos") or "").strip()
    filtros=[k for k in q if k not in("otros_requisitos","orden") and q[k] not in(None,[],"")]
    if otros: return {"dec":"repregunta","causa":"otros_requisitos","of":[]}
    if not filtros: return {"dec":"repregunta","causa":"nada_extraido","of":[]}
    viv=[]
    for k in top:
        ev=evaluar(COL[k],q)
        if any(v=="no" for _,v in ev): continue
        viv.append((k,[f for f,v in ev if v=="sin_dato"]))
    if q.get("orden")=="mas_barato": viv.sort(key=lambda x:COL[x[0]]["precio"])
    elif q.get("orden")=="mas_caro": viv.sort(key=lambda x:-COL[x[0]]["precio"])
    if not viv: return {"dec":"no_hay","causa":"","of":[]}
    mej=viv[:5]
    sd=sorted({f for _,fs in mej for f in fs})
    if sd: return {"dec":"repregunta","causa":"columna_nula","sin_dato":sd,"of":[]}
    return {"dec":"ofrece","causa":"","of":[k for k,_ in mej]}
def corregir(i,x):
    ac={tuple(a) for a in AC[i]}; en15=[tuple(k) for k in CAND[i]["top"] if tuple(k) in ac]
    if ac and not en15: return "falla_busqueda"
    if x["dec"] in("repregunta","error"): return "repregunta"
    if x["dec"]=="no_hay": return "acierta" if not ac else "erra"
    return "acierta" if x["of"] and all(k in ac for k in x["of"]) else "erra"
def base(i):
    ac={tuple(a) for a in AC[i]}; return "acierta" if tuple(CAND[i]["top"][0]) in ac else "erra"
def correr():
    RES={}
    for l in open(T+"/resultados.jsonl"):
        r=json.loads(l); RES[r["i"]]=r
    out=[]
    for i in range(len(M)):
        r=RES.get(i)
        if not r or "raw" not in r: x={"dec":"error","causa":"api","of":[]}; q=None
        else: q=json.loads(r["raw"]); x=decidir(i,q)
        out.append({"i":i,"id":M[i][1],"frase":M[i][2],"dudosa":M[i][4],"dec":x["dec"],"causa":x["causa"],"sin_dato":x.get("sin_dato"),
          "of":[k[2] for k in x["of"]],"c":corregir(i,x),"base":base(i),"n_ac":len(AC[i]),"q":{k:v for k,v in (q or {}).items() if v not in(None,[])}})
    json.dump(out,open(T+"/decisiones.json","w"),ensure_ascii=False,indent=0)
    return out,RES
def cuenta(out,f,lab):
    s=[o for o in out if f(o)]; n=len(s); cc=collections.Counter(o["c"] for o in s)
    return f"{lab} N={n} "+" ".join(f"{k}={v}({round(100*v/n)}%)" for k,v in sorted(cc.items()))
def prev(d,lab):
    o=json.load(open(d+"/decisiones.json"))
    for f,l in [(lambda o:True,"todas"),(lambda o:not o["dudosa"],"sin dudosas")]: print(lab,cuenta(o,f,l))
if __name__=="__main__":
    out,RES=correr()
    for f,l in [(lambda o:True,"todas"),(lambda o:not o["dudosa"],"sin dudosas"),(lambda o:o["c"]!="falla_busqueda","sin falla de busqueda")]: print("canonico",cuenta(out,f,l))
    print("repregunta por causa",collections.Counter(o["causa"] for o in out if o["dec"]=="repregunta"))
    rs=[r for r in RES.values() if "seg" in r]
    import statistics as st
    print("seg mediana",st.median(r["seg"] for r in rs),"max",max(r["seg"] for r in rs),"tin medio",round(st.mean(r["tin"] for r in rs)),"tout medio",round(st.mean(r["tout"] for r in rs)),"n429",sum(r.get("n429",0) for r in RES.values()),"espera429",sum(r.get("esp429",0) for r in RES.values()),"errores",sum("err" in r for r in RES.values()))
