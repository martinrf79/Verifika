import sys,os,json,time
sys.dont_write_bytecode=True
T=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,T)
from muestra import M
import extraer, luna, decidir_canon as DC, decidir_verif as DV
from openai import OpenAI
BASE="https://generativelanguage.googleapis.com/v1beta/openai/"; MOD="models/gemini-3.1-flash-lite"
PIN,POUT=0.25,1.50  # USD por millon, tarifa nominal (la gratis cuesta 0)
def cli(paga): return OpenAI(api_key=(os.environ["GEMINI_API_KEY_PROD"] if paga else os.environ["GEMINI_API_KEY"]).split()[0],base_url=BASE,timeout=120,max_retries=0)
def llamar(sis,usr,sch,etq):
    """un intento bueno; 429/503: 2 reintentos con la gratis, luego la paga solo si MARTIN_AUTORIZO_LA_PAGA=2026-11-23"""
    paga=False;k=0;n429=0;n503=0
    while True:
        t0=time.time()
        try:
            r=cli(paga).chat.completions.create(model=MOD,messages=[{"role":"system","content":sis},{"role":"user","content":usr}],response_format=sch,temperature=0,**({"reasoning_effort":os.environ["ESFUERZO"]} if os.environ.get("ESFUERZO") else {}))
            dt=time.time()-t0; u=r.usage
            usd=0 if not paga else (u.prompt_tokens*PIN+u.completion_tokens*POUT)/1e6
            open(T+"/gastos.jsonl","a").write(json.dumps({"que":etq,"clave":"paga" if paga else "gratis","tin":u.prompt_tokens,"tout":u.completion_tokens,"usd_nominal":round((u.prompt_tokens*PIN+u.completion_tokens*POUT)/1e6,6),"usd_real":round(usd,6)})+"\n")
            return r.choices[0].message.content,dt,n429,paga,u.prompt_tokens,u.completion_tokens
        except Exception as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                n503+=1
                if n503>2 and not paga and os.environ.get("MARTIN_AUTORIZO_LA_PAGA")=="2026-11-23": paga=True; continue
                if n503>6: return None,0,n429,paga,0,0
                time.sleep(5); continue
            if "429" in str(e):
                n429+=1;k+=1
                if k>2:
                    if os.environ.get("MARTIN_AUTORIZO_LA_PAGA")=="2026-11-23": paga=True;k=0
                    else: return None,0,n429,paga,0,0
                time.sleep(6*k)
            else: return None,0,n429,paga,0,0
def una(i):
    cand=json.load(open(T+"/cand.json"))[i]
    seg=cand["seg_emb"]+cand["seg_top"]; n429=cand["n429"]; paga=cand["paga"]
    raw,dt,n,p,ti,to=llamar(extraer.SIS,M[i][2],extraer.SCH,f"extractor {M[i][1]}")
    n429+=n; paga|=p
    if raw is None: return {"i":i,"err":"extractor","n429":n429}
    seg+=dt; q=json.loads(raw); x=DC.decidir(i,q); r={"i":i,"q":q,"canon":x["dec"],"causa":x.get("causa"),"tok":[ti,to]}
    if x["dec"]=="ofrece": r.update(dec="ofrece",of=[list(k) for k in x["of"]],rapido=True)
    else:
        u,_=luna.prompt(i)
        raw2,dt2,n,p,ti,to=llamar(luna.SIS,u,luna.SCH,f"verificador {M[i][1]}")
        n429+=n; paga|=p; r["tok"]+= [ti,to]
        if raw2 is None: r.update(dec="error",of=[],rapido=False)
        else:
            seg+=dt2; DV.RES[i]={"raw":raw2}; y=DV.decidir(i)
            r.update(dec=y["dec"],of=[list(k) for k in y.get("of",[])],rapido=False,raw_v=raw2)
    r.update(seg=round(seg,2),n429=n429,paga=paga)
    return r
if __name__=="__main__":
    ids=[int(a) for a in sys.argv[1:]] or range(len(M))
    hechos={json.loads(l)["i"] for l in open(T+"/resultados.jsonl")} if os.path.exists(T+"/resultados.jsonl") else set()
    for i in ids:
        if i in hechos: continue
        r=una(i); open(T+"/resultados.jsonl","a").write(json.dumps(r,ensure_ascii=False)+"\n")
        print(M[i][1],r.get("canon"),r.get("dec"),r.get("seg"),r.get("n429"),r.get("paga"),flush=True)
