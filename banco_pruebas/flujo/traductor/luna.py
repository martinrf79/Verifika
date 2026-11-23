import sys,os,json,time,re,unicodedata,hashlib
sys.dont_write_bytecode=True
T=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,T)
from muestra import M
from catalogo import MOD,C
CAND=json.load(open(T+"/cand.json"))
OMIT={"id","nombre","categoria","precio_ars","stock","descripcion_rica","garantia_detalle"}
def fila(k):
    rows=MOD[tuple(k)]; p=rows[0]; c=C[tuple(k)]
    pr=sorted(int(r["precio_ars"]) for r in rows); st=sum(int(r["stock"]) for r in rows)
    d={"nombre":p["nombre"].rsplit(" ",1)[0] if len(rows)>1 and all(r["color"] for r in rows) else p["nombre"],"rubro":p["categoria"],
       "precio":str(pr[0]) if pr[0]==pr[-1] else f"{pr[0]} a {pr[-1]}","stock":str(st)}
    for f,v in p.items():
        if f in OMIT or not v: continue
        d[f]=", ".join(dict.fromkeys(r[f] for r in rows)) if f=="color" else v
    for f in ("plataformas","conecta_por","requiere","provee"):
        if c[f]: d[f]=c[f].replace("|",", ")
    return d
def texto_fila(n,d): return f"{n}. "+" | ".join(f"{f}: {v}" for f,v in d.items())
SIS=("Sos el traductor de pedidos de una tienda de tecnologia. Recibis la frase de un cliente y 15 filas de productos candidatos, numeradas del 1 al 15, "
"con los campos que tiene cada una. Tu trabajo, en dos pasos.\n"
"Paso 1: pasar el pedido a requisitos concretos, usando lo que sabes del mundo (por ejemplo que nombre usa el cliente para una consola o una marca, o cuanto es una cifra dicha en jerga). "
"Cada requisito lleva la cita: las palabras exactas del cliente de las que sale, copiadas tal cual de la frase. Tipos: producto (que cosa quiere, o el modelo si lo nombra), atributo (una caracteristica pedida, como inalambrico, con cable, marca, color, capacidad), "
"compat (con que equipo o sistema tiene que andar), precio (un tope o minimo de plata; en la cita va la cifra tal cual la dijo), preferencia (algo que prefiere pero no exige). "
"Un requisito por cosa; no inventes requisitos que el cliente no dijo.\n"
"Paso 2: para cada candidato y cada requisito, el veredicto: cumple, no o sin_dato. Cumple o no solo si lo ves en un campo de esa fila, y en ese caso decis en `campo` el nombre exacto del campo donde lo viste (el nombre que aparece antes de los dos puntos en la fila). "
"Si la fila no trae el dato, sin_dato y campo vacio. No supongas lo que la fila no dice. Los requisitos de tipo precio no los evaluas: no pongas veredictos para ellos.\n"
"Responde solo el JSON.")
SCH={"type":"json_schema","json_schema":{"name":"t","strict":True,"schema":{"type":"object","properties":{
 "requisitos":{"type":"array","items":{"type":"object","properties":{"id":{"type":"string"},"cita":{"type":"string"},"tipo":{"type":"string","enum":["producto","atributo","compat","precio","preferencia"]}},"required":["id","cita","tipo"],"additionalProperties":False}},
 "veredictos":{"type":"array","items":{"type":"object","properties":{"cand":{"type":"integer"},"req":{"type":"string"},"v":{"type":"string","enum":["cumple","no","sin_dato"]},"campo":{"type":"string"}},"required":["cand","req","v","campo"],"additionalProperties":False}}},
 "required":["requisitos","veredictos"],"additionalProperties":False}}}
def prompt(i):
    c=CAND[i]; filas=[fila(k) for k in c["top"]]
    return f'FRASE DEL CLIENTE: {M[i][2]}\n\nCANDIDATOS:\n'+"\n".join(texto_fila(n+1,d) for n,d in enumerate(filas)),filas
def llamar(i):
    from openai import OpenAI
    cli=OpenAI(api_key=os.environ["OPENAI_API_KEY"].split()[0],timeout=180,max_retries=2)
    u,_=prompt(i); t0=time.time()
    for k in range(6):
        try:
            r=cli.chat.completions.create(model=os.environ.get("FLUJO_MODELO","gpt-6-luna"),messages=[{"role":"system","content":SIS},{"role":"user","content":u}],response_format=SCH,reasoning_effort="low");break
        except Exception as e:
            if "429" in str(e): time.sleep(20*(k+1)); continue
            return {"i":i,"err":str(e)[:200]}
    else: return {"i":i,"err":"429"}
    dt=time.time()-t0
    return {"i":i,"raw":r.choices[0].message.content,"seg":round(dt,2),"pt":r.usage.prompt_tokens,"ct":r.usage.completion_tokens,"usd":(r.usage.prompt_tokens*0.10+r.usage.completion_tokens*0.50)/1e6}
if __name__=="__main__":
    ids=[int(x) for x in sys.argv[1:]] or range(len(M))
    hechos={json.loads(l)["i"] for l in open(T+"/resultados.jsonl")} if os.path.exists(T+"/resultados.jsonl") else set()
    gasto=sum(json.loads(l).get("usd",0) for l in open(T+"/resultados.jsonl")) if hechos else 0
    for i in ids:
        if i in hechos: continue
        if gasto>=0.095: print("TOPE de costo, paro");break
        r=llamar(i); gasto+=r.get("usd",0)
        open(T+"/resultados.jsonl","a").write(json.dumps(r,ensure_ascii=False)+"\n")
        print(i,r.get("err") or (r["seg"],r["pt"],r["ct"],round(gasto,4)),flush=True)
