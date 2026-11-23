import sys,os,json,re,unicodedata,random,collections
sys.dont_write_bytecode=True
T=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,T)
from muestra import M
import luna
CAND=json.load(open(T+"/cand.json")); AC=json.load(open(T+"/aceptables.json"))
RES={}
def norm(s):
    s="".join(c for c in unicodedata.normalize("NFD",s.lower()) if unicodedata.category(c)!="Mn")
    return " "+re.sub(r"[^a-z0-9$]+"," ",s).strip()+" "
UN={"luca":1000,"lucas":1000,"luquita":1000,"luquitas":1000,"mil":1000,"k":1000,"palo":10**6,"palos":10**6,"millon":10**6,"millones":10**6}
def tope(cita,frase):
    m=re.search(r"(\d[\d.,]*)\s*([a-z]+)?",norm(cita).replace("$"," "))
    if not m: return None
    n=m.group(1).replace(".","").replace(",","."); 
    try: n=float(n)
    except: return None
    mult=UN.get((m.group(2) or ""),1)
    if mult==1 and n<1000: return None
    antes=norm(frase); p=antes.find(norm(cita).strip()); ctx=antes[max(0,p-40):p]+" "+norm(cita)
    d="min" if re.search(r"\b(mas de|desde|minimo|arriba|mayor)\b",ctx) else "max"
    return d,n*mult
def decidir(i):
    frase=M[i][2]; r=RES[i]
    if "raw" not in r: return {"dec":"error"}
    d=json.loads(r["raw"]); top=CAND[i]["top"]; fnorm=norm(frase)
    reqs={};desc=[]
    for q in d["requisitos"]:
        c=norm(q["cita"])
        if c.strip() and c in fnorm: reqs[q["id"]]=q
        else: desc.append(q["id"])
    filas=luna.prompt(i)[1]
    ver={}
    for v in d["veredictos"]:
        ver[(v["cand"],v["req"])]=v
    duros=[];pref=[]
    for rid,q in reqs.items():
        if q["tipo"]=="preferencia": pref.append(rid)
        elif q["tipo"]=="precio":
            t=tope(q["cita"],frase)
            if t: q["_t"]=t; duros.append(rid)
            else: pref.append(rid)
        else: duros.append(rid)
    est=[]
    for n,k in enumerate(top):
        campos=set(filas[n]); s="pasa"; npref=0
        for rid in duros:
            q=reqs[rid]
            if q["tipo"]=="precio":
                pr=int(luna.fila(k)["precio"].split()[0]); dr,t=q["_t"]; v="cumple" if (pr<=t if dr=="max" else pr>=t) else "no"
            else:
                x=ver.get((n+1,rid)); v=x["v"] if x else "sin_dato"
                if v!="sin_dato" and (x["campo"].strip().lower() not in campos): v="sin_dato"
            if v=="no": s="desc";break
            if v=="sin_dato": s="dudoso"
        for rid in pref:
            x=ver.get((n+1,rid))
            if x and x["v"]=="cumple" and x["campo"].strip().lower() in campos: npref+=1
        est.append((s,npref))
    if not duros: return {"dec":"repregunta","motivo":"sin requisitos duros","reqs":list(reqs.values()),"desc":desc}
    vivos=sorted([n for n,(s,_) in enumerate(est) if s!="desc"],key=lambda n:(-est[n][1],n))
    if not vivos: dec,of="no_hay",[]
    else:
        mej=vivos[:5]
        if any(est[n][0]=="dudoso" for n in mej): dec,of="repregunta",[]
        else: dec,of="ofrece",[tuple(top[n]) for n in mej]
    return {"dec":dec,"of":of,"est":est,"desc":desc,"reqs":list(reqs.values())}
def corregir(i,x):
    ac={tuple(a) for a in AC[i]}; en15=[tuple(k) for k in CAND[i]["top"] if tuple(k) in ac]
    if ac and not en15: return "falla_busqueda"
    if x["dec"]=="repregunta" or x["dec"]=="error": return "repregunta"
    if x["dec"]=="no_hay": return "acierta" if not ac else "erra"
    return "acierta" if x["of"] and all(k in ac for k in x["of"]) else "erra"
def base(i):
    ac={tuple(a) for a in AC[i]}; return "acierta" if tuple(CAND[i]["top"][0]) in ac else "erra"
if __name__=="__main__":
    out=[]
    for i in range(len(M)):
        x=decidir(i); c=corregir(i,x); b=base(i)
        out.append({"i":i,"id":M[i][1],"frase":M[i][2],"dudosa":M[i][4],"dec":x["dec"],"of":[k[2] for k in x.get("of",[])],"c":c,"base":b,"n_ac":len(AC[i]),"reqs":x.get("reqs"),"desc":x.get("desc")})
    json.dump(out,open(T+"/decisiones.json","w"),ensure_ascii=False,indent=0)
    def cuenta(f,lab):
        s=[o for o in out if f(o)]; n=len(s); cc=collections.Counter(o["c"] for o in s)
        print(lab,"N",n,{k:(v,round(100*v/n,1)) for k,v in cc.items()}, "base top1:",collections.Counter(o["base"] for o in s))
    cuenta(lambda o:True,"todas")
    cuenta(lambda o:o["c"]!="falla_busqueda","sin falla de busqueda")
    cuenta(lambda o:not o["dudosa"],"sin dudosas")
    cuenta(lambda o:o["dudosa"],"solo dudosas")
    cuenta(lambda o:o["n_ac"]==0,"no hay (vacias)")
    cuenta(lambda o:o["n_ac"]>0,"con aceptables")
    rs=[json.loads(l) for l in open(T+"/resultados.jsonl")]
    print("errores api",sum("err" in r for r in rs),"seg medio",round(sum(r["seg"] for r in rs if "seg" in r)/len(rs),2),"usd",round(sum(r.get("usd",0) for r in rs),4))
    print("citas descartadas",sum(len(o["desc"] or []) for o in out))
