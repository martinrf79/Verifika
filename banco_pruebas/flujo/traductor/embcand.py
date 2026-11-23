import sys,os,json,math,time,urllib.request,urllib.error
sys.dont_write_bytecode=True
T=os.path.dirname(os.path.abspath(__file__))
S="/home/user/Verifika/banco_pruebas/flujo"
sys.path[:0]=["/home/user/Verifika",S,S+"/bancos",T]
os.chdir("/home/user/Verifika"); sys.argv=["x"]
import jev_filas as JF
from muestra import M
F=JF._fuente(); AC=json.load(open(T+"/aceptables.json"))
URL="https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent"
def clave(paga):
    return os.environ["GEMINI_API_KEY_PROD"].split()[0] if paga else os.environ["GEMINI_API_KEY"].split()[0]
def embed(t):
    """devuelve (vector normalizado, segundos del intento bueno, n429, usó_paga)"""
    paga=False; n429=0; k=0
    while True:
        body=json.dumps({"model":"models/gemini-embedding-001","content":{"parts":[{"text":t}]},"taskType":"RETRIEVAL_QUERY"}).encode()
        t0=time.time()
        try:
            r=json.load(urllib.request.urlopen(urllib.request.Request(URL,data=body,headers={"x-goog-api-key":clave(paga),"Content-Type":"application/json"}),timeout=60))
            dt=time.time()-t0; x=r["embedding"]["values"]; n=math.sqrt(sum(v*v for v in x)) or 1
            return [v/n for v in x],dt,n429,paga
        except urllib.error.HTTPError as e:
            if e.code==429:
                n429+=1; k+=1
                if k>2:
                    if os.environ.get("MARTIN_AUTORIZO_LA_PAGA")=="2026-11-23": paga=True; k=0
                    else: raise SystemExit("429 sin ceder y sin autorizacion de la paga")
                time.sleep(8*k)
            else: raise
out=[]; prev={}
if os.path.exists(T+"/cand.json"): prev={r["i"]:r for r in json.load(open(T+"/cand.json"))}
ids=[int(a) for a in sys.argv[1:]] if len(sys.argv)>1 else range(len(M))
for i in range(len(M)):
    if i in prev: out.append(prev[i]); continue
    q,dt,n429,paga=embed(M[i][2]); t0=time.time()
    s=sorted(((sum(a*b for a,b in zip(q,v)),k) for k,v in F.prod),key=lambda z:-z[0])[:15]
    t1=time.time()-t0
    top=[list(k) for _,k in s]; ac=[tuple(a) for a in AC[i]]
    out.append({"i":i,"top":top,"sim":[round(x,4) for x,_ in s],"ac_en_15":[j for j,k in enumerate(top) if tuple(k) in ac],"n_ac":len(ac),"seg_emb":round(dt,3),"seg_top":round(t1,3),"n429":n429,"paga":paga})
    json.dump(out,open(T+"/cand.json","w"),ensure_ascii=False)
    tok=len(M[i][2])//4+1
    open(T+"/gastos.jsonl","a").write(json.dumps({"que":"embedding "+M[i][1],"clave":"paga" if paga else "gratis","tokens":tok,"usd_nominal":round(tok*0.15/1e6,7)})+"\n")
con=[r for r in out if r["n_ac"]];print("N",len(out),"con aceptables",len(con),"alguno en 15:",sum(1 for r in con if r["ac_en_15"]))
print([(M[r["i"]][1]) for r in con if not r["ac_en_15"]])
