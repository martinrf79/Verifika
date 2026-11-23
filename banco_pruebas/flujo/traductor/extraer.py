import sys,os,json,time
sys.dont_write_bytecode=True
T=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,T)
from muestra import M
from catalogo import MOD
RUBROS=sorted({k[0] for k in MOD})
def nul(t,**k): d={"type":t}; d.update(k); return {"anyOf":[d,{"type":"null"}]}
PROP={"rubro":nul("string",enum=RUBROS),"marca":nul("array",items={"type":"string"}),"modelo":nul("array",items={"type":"string"}),
 "inalambrico":nul("boolean"),"conexion":nul("string",enum=["cable","usb","bluetooth","3.5mm"]),
 "compatible_con":nul("array",items={"type":"string","enum":["pc","mac","ps4","ps5","xbox","switch","ios","android"]}),
 "precio_max":nul("integer"),"precio_min":nul("integer"),"color":nul("string"),"capacidad_gb":nul("integer"),"rgb":nul("boolean"),
 "orden":nul("string",enum=["mas_barato","mas_caro"]),"excluir_pais":nul("string"),"otros_requisitos":nul("string")}
SCH={"type":"json_schema","json_schema":{"name":"pedido","strict":True,"schema":{"type":"object","properties":PROP,"required":list(PROP),"additionalProperties":False}}}
SIS=("Sos el traductor de pedidos de una tienda de tecnologia. Recibis la frase de un cliente argentino y la pasas a un esquema fijo, usando lo que sabes del mundo "
"(jerga de precios como lucas o mil, nombres de consolas como la Play, marcas, que es 'inalambrico' o 'sin cable'). Lo que el cliente no dijo va en null; no inventes nada. "
"Campos: rubro (uno de la lista de rubros; null si lo que pide no es ninguno de esos rubros o si no dice que cosa quiere), marca (lista de marcas que pide; si se corrige, la ultima; para 'que no sea X' no se usa marca, va en otros_requisitos), "
"modelo (lista de modelos que nombra, tal cual: M170, G305), inalambrico (true si pide sin cable o inalambrico, false si pide con cable), conexion (cable, usb, bluetooth o 3.5mm, solo si la pide), "
"compatible_con (lista de equipos con los que tiene que andar: pc, mac, ps4, ps5, xbox, switch, ios, android; la Play son ps4 y ps5; el iPad es ios), "
"precio_max y precio_min en pesos como numero entero, color, capacidad_gb en GB (1 tera son 1000), rgb (true si pide luces o iluminacion RGB), orden (mas_barato o mas_caro si pide el mas barato o el mas caro), "
"excluir_pais (el pais de fabricacion que no quiere, en espanol, por ejemplo China para 'lo menos china posible'), "
"otros_requisitos: texto libre con todo lo que pide y no entra en los otros campos (por ejemplo una marca que no quiere, una caracteristica como mecanico o con microfono, lo que pide y no esta entre los rubros, una pregunta que no es un pedido). No van ahi la cantidad que quiere llevar, ni preguntas como cuanto sale o tenes, ni saludos: solo condiciones sobre el producto. null si no queda nada. "
"Rubros de la tienda: "+", ".join(RUBROS)+". Responde solo el JSON.")
def llamar(frase):
    from openai import OpenAI
    cli=OpenAI(api_key=os.environ["GEMINI_API_KEY"],base_url="https://generativelanguage.googleapis.com/v1beta/openai/",timeout=120,max_retries=0)
    esp=0.0; n429=0
    for k in range(8):
        t0=time.time()
        try:
            r=cli.chat.completions.create(model="models/gemini-3.1-flash-lite",messages=[{"role":"system","content":SIS},{"role":"user","content":frase}],response_format=SCH,temperature=0)
            seg=time.time()-t0
            return {"raw":r.choices[0].message.content,"seg":round(seg,2),"tin":r.usage.prompt_tokens,"tout":r.usage.completion_tokens,"esp429":round(esp,1),"n429":n429}
        except Exception as e:
            if "429" in str(e) or "503" in str(e):
                n429+=1; w=min(60,5*2**k); time.sleep(w); esp+=w+(time.time()-t0)
            else: return {"err":str(e)[:300]}
    return {"err":"reintentos agotados","esp429":round(esp,1),"n429":n429}
if __name__=="__main__":
    ids=[int(a) for a in sys.argv[1:]] or range(len(M))
    hechos={json.loads(l)["i"] for l in open(T+"/resultados.jsonl")} if os.path.exists(T+"/resultados.jsonl") else set()
    for i in ids:
        if i in hechos and len(sys.argv)==1: continue
        r=llamar(M[i][2]); r["i"]=i
        open(T+"/resultados.jsonl","a").write(json.dumps(r,ensure_ascii=False)+"\n")
        print(i,r.get("seg"),r.get("tin"),r.get("tout"),r.get("err",""),flush=True)
