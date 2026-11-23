import csv,re,unicodedata,sys
sys.dont_write_bytecode=True
from catalogo import MOD,C,D
S={(s["categoria"],s["marca"],s["modelo"]):s for s in csv.DictReader(open(D+"specs_por_modelo.csv",encoding="utf-8"))}
def nrm(s):
    s="".join(c for c in unicodedata.normalize("NFD",(s or "").lower()) if unicodedata.category(c)!="Mn")
    return re.sub(r"[^a-z0-9.]+"," ",s).strip()
PLAT={"pc_escritorio":"pc","notebook":"pc","windows":"pc","linux":"pc","macos":"mac","ps4":"ps4","ps5":"ps5","xbox":"xbox","nintendo_switch":"switch","ios":"ios","android":"android"}
def gb(t):
    m=re.findall(r"(\d+)\s*(TB|GB)",t or "")
    if not m: return None
    n,u=m[-1]; return int(n)*(1000 if u=="TB" else 1)
def columnas(k):
    rows=MOD[k]; p=rows[0]; c=C[k]; cat=k[0]; con=[x for x in c["conecta_por"].split("|") if x]
    o={"rubro":cat,"marca":k[1],"modelo":k[2]}
    o["inalambrico"]=None if not con else ("bluetooth" in con or "receptor_usb" in con)
    cx=set()
    if "bluetooth" in con: cx.add("bluetooth")
    if {"receptor_usb","puerto_usb_a","puerto_usb_c"}&set(con): cx.add("usb")
    if "jack_35" in con: cx.add("3.5mm")
    if {"puerto_usb_a","puerto_usb_c","jack_35"}&set(con): cx.add("cable")
    o["conexion"]=sorted(cx) if con else None
    pl=[x for x in c["plataformas"].split("|") if x]
    o["compatible_con"]=sorted({PLAT[x] for x in pl if x in PLAT}) if pl else None
    pr=[int(r["precio_ars"]) for r in rows]; o["precio"]=min(pr)
    cols=sorted({nrm(r["color"]) for r in rows if r["color"]}); o["color"]=cols or None
    cap=None
    if cat in("ssd","memoria ram","almacenamiento externo"): cap=gb(k[2])
    elif cat=="tablet": cap=gb(p["caracteristicas_extra"].split(",")[0])
    o["capacidad_gb"]=cap
    s=S.get(k); r=None
    if s and s["retroiluminacion"]:
        t=s["retroiluminacion"].lower()
        if "rgb" in t: r=True
        elif t.startswith("no") or "blanc" in t: r=False
    elif not s or not s["retroiluminacion"]:
        if re.search(r"rgb|lightsync",(k[2]+p["tags"]+p["descripcion"]+p["caracteristicas_extra"]).lower()): r=True
    o["rgb"]=r
    m=re.search(r"Fabricado en ([^.]*)",p["origen"])
    if m:
        t=re.sub(r"\s+segun linea","",m.group(1)); o["pais"]=sorted({nrm(x) for x in re.split(r",| o ",t) if x.strip()})
    else: o["pais"]=None
    return o
COL={k:columnas(k) for k in MOD}
if __name__=="__main__":
    import collections
    for f in ["inalambrico","conexion","compatible_con","color","capacidad_gb","rgb","pais"]:
        print(f,"nulos",sum(v[f] is None for v in COL.values()),"de",len(COL))
