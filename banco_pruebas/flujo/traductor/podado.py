import sys,os,json,time,collections,statistics as st
sys.dont_write_bytecode=True
T=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,T)
from muestra import M
import luna, run, decidir_verif as DV
SAQUE={"stock","descripcion","dimensiones","garantia_meses","contenido_caja","tags","material","caracteristicas_extra"}
def fila(n,k):
    d=luna.fila(k); return f"{n}. "+" | ".join(f"{f}: {str(v)[:50]}" for f,v in d.items() if f not in SAQUE)
SIS=("Tienda de tecnologia. Recibis la frase de un cliente y filas de productos numeradas. "
"Pasa el pedido a requisitos usando lo que sabes del mundo (nombres de consolas, jerga de plata, etc.), cada uno con la cita: palabras exactas del cliente. "
"Tipos: producto, atributo, compat, precio, preferencia (lo que prefiere sin exigir). "
"Despues decidi que filas cumplen TODOS los requisitos que no son precio ni preferencia, mirando solo lo que dicen las filas; no supongas datos que la fila no trae. "
"sirven: numeros de filas que cumplen. dudosas: filas que cumplirian pero a las que les falta un dato, con el nombre del campo o dato que falta. "
"Si ninguna fila es lo que pide, sirven y dudosas vacias. Responde solo el JSON.")
SCH={"type":"json_schema","json_schema":{"name":"p","strict":True,"schema":{"type":"object","properties":{
 "requisitos":{"type":"array","items":{"type":"object","properties":{"cita":{"type":"string"},"tipo":{"type":"string","enum":["producto","atributo","compat","precio","preferencia"]}},"required":["cita","tipo"],"additionalProperties":False}},
 "sirven":{"type":"array","items":{"type":"integer"}},
 "dudosas":{"type":"array","items":{"type":"object","properties":{"fila":{"type":"integer"},"falta":{"type":"string"}},"required":["fila","falta"],"additionalProperties":False}}},
 "required":["requisitos","sirven","dudosas"],"additionalProperties":False}}}
def precio_ok(k,lim):
    import catalogo; p=min(int(r["precio_ars"]) for r in catalogo.MOD[tuple(k)])
    return all((p<=n if d=="max" else p>=n) for d,n in lim)
def una(i):
    c=json.load(open(T+"/cand.json"))[i]; top=c["top"]
    usr=f"FRASE: {M[i][2]}\nFILAS:\n"+"\n".join(fila(n+1,k) for n,k in enumerate(top))
    raw,dt,n429,paga,ti,to=run.llamar(SIS,usr,SCH,f"podado {M[i][1]}")
    if raw is None: return {"i":i,"err":1}
    j=json.loads(raw); fr=M[i][2]
    lim=[t for t in (DV.tope(q["cita"],fr) for q in j["requisitos"] if q["tipo"]=="precio" and DV.norm(q["cita"]).strip() in DV.norm(fr)) if t]
    sirven=[top[n-1] for n in j["sirven"] if 1<=n<=len(top)]
    sirven=[k for k in sirven if precio_ok(k,lim)]
    if sirven: dec="ofrece"
    elif j["dudosas"]: dec="repregunta"
    else: dec="no_hay"
    return {"i":i,"dec":dec,"of":sirven,"seg":round(dt+c["seg_emb"]+c["seg_top"],2),"llm":round(dt,2),"tin":ti,"tout":to,"paga":paga,"j":j}
if __name__=="__main__":
    out=T+"/podado.jsonl"; hechos={json.loads(l)["i"] for l in open(out)} if os.path.exists(out) else set()
    ids=[int(x) for x in sys.argv[1:]] or range(len(M))
    for i in ids:
        if i in hechos: continue
        r=una(i); open(out,"a").write(json.dumps(r,ensure_ascii=False)+"\n"); print(M[i][1],r.get("dec"),r.get("llm"),r.get("tin"),r.get("tout"),flush=True)
