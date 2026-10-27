"""LAS FORMAS DE PREGUNTA — cuantas combinaciones de rasgos hay en el examen y en la plantilla (27-oct-2026, FICHA 82).

Pedido de Martin: contar todas las formas antes de sumar reglas. Cada turno se describe por ocho rasgos sacados de su
vara: cuantas cosas, que acciones, destinos, si reparte, si hay condicion, si algo vale para todo, si senala la libreta
y si hay charla. Sin modelo.

    python3 banco_pruebas/formas_de_pregunta.py
"""
import sys,json,collections
sys.argv=['x']; sys.path.insert(0,'/home/user/Verifika/banco_pruebas'); sys.path.insert(0,'/home/user/Verifika')
import embeddings_primera as EP
P,V=EP.P,EP.V
from app.core.flujo import interprete
FUERA={"de_si","nada"}
ACC={"lleva":"llevar","cambia":"cambiar","saca":"cambiar","opciones":"ver"}
def rasgos(vara, libreta):
    cs=[c for c in vara["cosas"] if c["acto"] not in FUERA]
    acc=sorted({ACC.get(c["acto"],"preguntar") for c in cs})
    dest=[V.n(c["datos"].get("destino") or "") for c in cs if c["datos"].get("destino")]
    porque=collections.defaultdict(set)
    for c in cs:
        if c["datos"].get("destino"): porque[(c["que"] or ["*"])[0]].add(V.n(c["datos"]["destino"]))
    reparte=any(len(v)>1 for v in porque.values())
    n=len(cs)
    r={"cosas":"1" if n<=1 else "2" if n==2 else "3+",
       "acciones":"+".join(acc) or "nada",
       "destinos":"ninguno" if not dest else ("uno" if len(set(dest))==1 else "varios"),
       "reparte":reparte,
       "condicion":any(c["datos"].get("depende") for c in cs) or "si_pasa" in vara["todo"],
       "para_todo":bool({"orden","tope","reparto"} & set(vara["todo"])),
       "senala":any(c["ref"] for c in cs),
       "charla":libreta}
    return r
filas=[]
for f,cid,msg,est,h in P._turnos_sueltos():
    vara,nums=EP._vara_de(f,cid,est)
    filas.append(("examen_"+f,cid,rasgos(vara,'vacia' not in interprete.libreta(est,h,P.TID))))
from banco_pruebas.plantilla_venta import llenar as LL
LL.entorno()
for c in LL.llenar()["casos"]:
    if not c.get("entra"): continue
    ag=c["agenda"] if isinstance(c["agenda"],dict) else {"preguntas":c["agenda"]}
    try: vara=V.vara_58(ag,{})
    except Exception as e: continue
    filas.append(("plantilla",c["id"],rasgos(vara,'vacia' not in (c.get("libreta") or "vacia"))))

for fuente in ("examen","plantilla"):
    fs=[r for s,_,r in filas if s.startswith(fuente)]
    firmas=collections.Counter(json.dumps(r,sort_keys=True) for r in fs)
    print(f"\n{fuente}: {len(fs)} turnos o clases, {len(firmas)} formas distintas (combinaciones de rasgos)")
    for k in fs[0]:
        print(f"   {k:10}", dict(collections.Counter(str(r[k]) for r in fs)))
todas=collections.Counter(json.dumps(r,sort_keys=True) for _,_,r in filas)
ex={json.dumps(r,sort_keys=True) for s,_,r in filas if s.startswith("examen")}
pl={json.dumps(r,sort_keys=True) for s,_,r in filas if s=="plantilla"}
print(f"\nformas del examen que la plantilla no tiene: {len(ex-pl)} de {len(ex)}")
