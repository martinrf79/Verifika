import sys,os,json,re
sys.dont_write_bytecode=True
T=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,T)
from muestra import M
import catalogo as K
from columnas import S
def acept(r):
    r=dict(r); sp=r.pop("spec",None); lv=r.pop("liviano",False)
    out=K.acept(r)
    if sp: out={k for k in out if all(re.search(rx,S.get(k,{}).get(f,"") or "") for f,rx in sp)}
    if lv:
        pe={k:min(int(x["peso_gramos"] or 9999) for x in K.MOD[k]) for k in out}
        m=min(pe.values()); out={k for k in out if pe[k]==m}
    return out
if __name__=="__main__":
    AC=[sorted(acept(m[3])) for m in M]
    json.dump(AC,open(T+"/aceptables.json","w"),ensure_ascii=False)
    print(len(M),[ (m[1],len(a)) for m,a in zip(M,AC)])
