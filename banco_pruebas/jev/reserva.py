"""LA RESERVA: 24 mensajes nuevos, escritos ANTES de correr, con lo que piden. Las condiciones son campo=valor del indice
(None si basta el campo); cada una se controla contra los datos: tiene que existir y no la puede cumplir todo el rubro."""
import json, os, sys
D = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, D)
RESERVA = [
 ("R01", "buenas! busco un teclado que se ilumine de colores y un mouse sin cables, lo mas economico posible. hacen factura A?",
  [("teclado", "retroiluminacion", "si"), ("mouse", "conexion", "inalambrico")], ["factura"], []),
 ("R02", "necesito un parlante para la pileta que aguante si se moja y que se conecte al celu",
  [("parlante", "resistencia_agua", "si"), ("parlante", "bluetooth", "si")], [], []),
 ("R03", "quiero una notebook que se desbloquee con el dedo y que la pantalla sea de 90 hz. cuotas sin interes tienen?",
  [("notebook", "lector_huella", "si"), ("notebook", "hz", "90hz")], ["cuotas"], []),
 ("R04", "para mi viejo que es medio anti china: unos auriculares y un mouse de marca yanqui, nada chino",
  [("auriculares", "pais_marca", "estados unidos"), ("mouse", "pais_marca", "estados unidos")], [], []),
 ("R05", "un monitor para jugar que refresque rapido, 165 o mas, y con panel ips. cuanto sale el envio a Salta?",
  [("monitor", "hz", None), ("monitor", "panel", "ips")], ["costo_envio", "envios"], []),
 ("R06", "memoria ram de 32 gigas y un ssd de 2 teras para la pc, lo mas barato que tengas",
  [("memoria ram", "ram", "32gb"), ("ssd", "almacenamiento", "2tb")], [], []),
 ("R07", "busco teclado sin cables que se conecte a la tablet por bluetooth, tengo un gato que tira todo jaja",
  [("teclado", "conexion", "inalambrico"), ("teclado", "bluetooth", "si")], [], []),
 ("R08", "tienen el JBL Flip 6? y si no hay, algun otro parlante con bluetooth",
  [("parlante", "bluetooth", "si")], [], ["JBL Flip 6"]),
 ("R09", "una impresora que imprima desde el celular por wifi y que tenga pantallita tactil",
  [("impresora", "wifi", None), ("impresora", "tactil", "si")], [], []),
 ("R10", "un ssd para la play 5 de 1 tera, el mas barato",
  [("ssd", "anda_con", "ps5"), ("ssd", "almacenamiento", "1tb")], [], []),
 ("R11", "cargador que sirva para iphone y para la notebook, y unos auriculares blancos",
  [("cargador", "anda_con", None), ("auriculares", "color", "blanco")], [], []),
 ("R12", "un router para casa grande que no sea tp-link porfa",
  [("router", "marca", None)], [], []),
 ("R13", "una tablet con lector de tarjetas para la nena que estudia, y que no sea muy cara. hacen envios a jujuy?",
  [("tablet", "lector_tarjetas", "si")], ["envios", "costo_envio"], []),
 ("R14", "mouse con luces rgb que ande con mac",
  [("mouse", "retroiluminacion", "si"), ("mouse", "anda_con", None)], [], []),
 ("R15", "armando el setup: monitor ultrawide, teclado con luz y auris negros. pago mitad transferencia mitad tarjeta",
  [("monitor", "resolucion", "ultrawide 2560x1080"), ("teclado", "retroiluminacion", "si"), ("auriculares", "color", "negro")], [], []),
 ("R16", "fuente de 750 para la pc y un gabinete blanco con lucecitas",
  [("fuente", "potencia", "750w de potencia"), ("gabinete", "color", "blanco"), ("gabinete", "retroiluminacion", "si")], [], []),
 ("R17", "placa de video con 16 de memoria, la mas barata que tengan. tiene garantia oficial?",
  [("placa de video", "memoria_video", None)], ["garantia"], []),
 ("R18", "motherboard para ryzen 7000 que tenga 4 ranuras de memoria",
  [("motherboard", "procesador", "socket am5, para ryzen 7000 y 8000"), ("motherboard", "ram", None)], [], []),
 ("R19", "notebook con pantalla oled y el teclado iluminado para usar de noche",
  [("notebook", "panel", "oled"), ("notebook", "retroiluminacion", "si")], [], []),
 ("R20", "un microfono que ande en la mac y una webcam que ande en linux",
  [("microfono", "anda_con", None), ("webcam", "anda_con", None)], [], []),
 ("R21", "disco externo de 4 teras plateado",
  [("almacenamiento externo", "almacenamiento", "4tb"), ("almacenamiento externo", "color", "plata")], [], []),
 ("R22", "teclado y mouse de marca suiza, los dos sin cable",
  [("teclado", "pais_marca", "suiza"), ("mouse", "pais_marca", "suiza"), ("teclado", "conexion", "inalambrico"), ("mouse", "conexion", "inalambrico")], [], []),
 ("R23", "parlante rojo con bluetooth, y si no hay rojo uno azul. se puede retirar en persona?",
  [("parlante", "color", "rojo"), ("parlante", "bluetooth", "si")], ["retiro_local", "ubicacion"], []),
 ("R24", "notebook con thunderbolt y teclado retroiluminado, y que tenga lector de tarjetas sd",
  [("notebook", "thunderbolt", "si"), ("notebook", "retroiluminacion", "si"), ("notebook", "lector_tarjetas", "si")], [], []),
]
def validar():
    import indice_jev as I
    from fuente import PS, K
    malos = []
    for rid, tx, conds, temas, prods in RESERVA:
        for r, c, v in conds:
            vs = I.valores(r)
            if c not in vs: malos.append((rid, r, c, "campo no esta en el indice")); continue
            if v is None: continue
            if v not in vs[c]: malos.append((rid, r, c, v, "valor no esta")); continue
            n = len(I.productos_con(r, c, v)); tot = len([p for p in PS if p["categoria"] == r and K.con_stock(p)])
            if not 0 < n < tot: malos.append((rid, r, c, v, f"cumplen {n} de {tot}"))
        for p in prods:
            if K.identificar(p, "", "verifika_prod")["veredicto"] != "exists": malos.append((rid, p, "producto no identificado"))
    return malos
if __name__ == "__main__" and len(sys.argv) == 1:
    print(validar() or "las 24 validas contra los datos")

def correr():
    """Primera vuelta v4 de Gemini y Jev con la calibracion: rubros >= .5 o top2, reglas top3, campos top3, productos top5."""
    import vuelta1 as V
    from fuente import K
    from banco_pruebas import libro_paga
    OUT = os.path.join(D, "reserva_resp.jsonl"); hechos = {json.loads(l)["id"] for l in open(OUT)} if os.path.exists(OUT) else set()
    g0 = libro_paga.hoy(); LIB = "LIBRETA: vacia, es el primer mensaje."
    for rid, tx, conds, temas, prods in RESERVA:
        if rid in hechos: continue
        if libro_paga.hoy() - g0 > 0.05: print("TOPE"); break
        sal = V.primera("v4", tx, LIB); rs = [r for r in sal.get("renglones") or [] if isinstance(r, dict)]
        perdido = V.A.sin_citar(tx, {"preguntas": [{"cita": r.get("cita", "")} for r in rs]})
        inv = [V.invento(r.get("limpio", ""), tx, LIB) for r in rs]
        sel = [V.jev1(r.get("limpio", ""), LIB) for r in rs]
        rub = set().union(*[set(s["rubros"]) for s in sel]); tem = set().union(*[set(s["temas"]) for s in sel])
        rub_oro = {r for r, _, _ in conds} | {K.identificar(p, "", "verifika_prod")["producto"]["categoria"] for p in prods}
        campos, pids = set(), set()
        for r in rub_oro & rub:
            for i, s in enumerate(sel):
                if r in s["rubros"]:
                    x = V.jev2(rs[i].get("limpio", ""), r, LIB); campos |= {(r, c) for c in x["campos"]}; pids |= set(x["prods"])
        c_oro = {(r, c) for r, c, _ in conds}
        p_oro = [{str(v["id"]) for v in K.identificar(p, "", "verifika_prod")["variantes"]} for p in prods]
        x = {"id": rid, "texto": tx, "renglones": rs, "perdido": perdido, "invento": [i for i in inv if i[0] or i[1]],
             "rubros": [sorted(rub_oro & rub), sorted(rub_oro)], "rub_mas": sorted(rub - rub_oro),
             "temas": [sorted(set(temas) & tem), temas], "campos": [sorted(map(list, c_oro & campos)), sorted(map(list, c_oro))],
             "prods": [sum(bool(g & pids) for g in p_oro), len(p_oro)]}
        with open(OUT, "a") as o: o.write(json.dumps(x, ensure_ascii=False) + "\n")
        print(f"{rid}: rubros {len(x['rubros'][0])}/{len(x['rubros'][1])} campos {len(x['campos'][0])}/{len(x['campos'][1])} reglas {'ok' if not temas or x['temas'][0] else 'FALTA'} prods {x['prods']} perdido {perdido} invento {x['invento']}", flush=True)
    print(f"paga: {libro_paga.hoy() - g0:.4f} USD")
if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "correr":
    correr()
