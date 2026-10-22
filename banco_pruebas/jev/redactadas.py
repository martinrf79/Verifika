"""Preguntas bien redactadas de todo tipo, con lo correcto escrito ANTES de correr: rubros, reglas, productos, specs."""
import json, os, sys, collections
from concurrent.futures import ThreadPoolExecutor
D = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, D)
import bateria as B
from fuente import K
# (texto, rubros, reglas aceptables por pedido —cada tupla es una regla pedida, vale cualquiera de la tupla—, productos, specs)
CASOS = [
 ("Buenas tardes. ¿Qué mouse inalámbricos tienen por debajo de los 50.000 pesos?", {"mouse"}, [], [], {"conexion"}),
 ("Necesito un monitor de 27 pulgadas con 144 Hz para jugar. ¿Qué opciones tienen?", {"monitor"}, [], [], {"hz"}),
 ("¿Tienen stock del Logitech G502 Hero en color negro?", {"mouse"}, [("stock_disponibilidad",)], ["Logitech G502 Hero"], set()),
 ("¿Cuánto cuesta el envío a Mendoza capital y cuántos días demora?", set(), [("costo_envio", "envios"), ("plazo_envio", "envios")], [], set()),
 ("¿Puedo pagar en cuotas sin interés con tarjeta de crédito?", set(), [("cuotas",)], [], set()),
 ("¿Emiten factura A? Compro para mi empresa.", set(), [("factura", "datos_fiscales")], [], set()),
 ("¿La memoria Kingston Fury Beast DDR4 de 16GB es compatible con la motherboard Asus Prime B550M-A?", {"memoria ram", "motherboard"}, [], ["Kingston Fury Beast DDR4 3200 16GB", "Asus Prime B550M-A"], set()),
 ("¿Qué diferencia hay entre un teclado mecánico y uno de membrana?", {"teclado"}, [("teclado_mecanico_membrana",)], [], {"switch_teclado"}),
 ("Quiero armar una PC para jugar: necesito un procesador Ryzen 5, una placa de video RTX 4060 y 16GB de RAM. ¿Qué me recomiendan?", {"procesador", "placa de video", "memoria ram"}, [], [], set()),
 ("¿Los auriculares JBL Tune 510BT tienen micrófono y cuánto dura la batería?", {"auriculares"}, [], ["JBL Tune 510BT"], {"bateria"}),
 ("Si el producto llega fallado, ¿cómo hago para devolverlo?", set(), [("defectuoso", "devoluciones", "garantia_como_usar")], [], set()),
 ("¿Tienen local para retirar en persona?", set(), [("retiro_local", "ubicacion")], [], set()),
 ("Busco una notebook liviana para la facultad, con buena batería y que no pase el millón de pesos.", {"notebook"}, [], [], {"bateria"}),
 ("¿Hacen descuento por pago con transferencia bancaria?", set(), [("descuento_transferencia",)], [], set()),
 ("Quiero dos teclados Redragon Kumara K552 y un mouse Logitech G203, enviados a Córdoba. ¿Cuánto sería el total?", {"teclado", "mouse"}, [], ["Redragon Kumara K552", "Logitech G203 Lightsync"], set()),
 ("¿Qué garantía tiene la placa de video Asus Dual RTX 4060?", {"placa de video"}, [("garantia",)], ["Asus Dual RTX 4060"], {"garantia"}),
 ("¿Venden al por mayor? Tengo un comercio y necesitaría unas 20 unidades.", set(), [("mayoristas",)], [], set()),
 ("¿El parlante JBL Flip 6 es resistente al agua?", {"parlante"}, [], ["JBL Flip 6"], {"resistencia_agua"}),
 ("Necesito una silla ergonómica para trabajar muchas horas sentado.", {"silla gamer"}, [], [], set()),
 ("¿Cuál es la webcam más económica que tienen?", {"webcam"}, [], [], set()),
 ("¿Los productos son originales y nuevos, o también venden usados?", set(), [("marcas_originales", "usados")], [], set()),
 ("¿Qué router me conviene para una casa de dos plantas donde no llega bien el wifi?", {"router"}, [], [], {"wifi"}),
 ("¿Tienen SSD NVMe de 1TB? ¿Cuál es el más rápido?", {"ssd"}, [], [], {"almacenamiento"}),
 ("¿Puedo cancelar un pedido que ya pagué?", set(), [("cancelacion_pedido", "reembolso")], [], set()),
 ("¿Cómo hago el seguimiento de mi envío?", set(), [("seguimiento_pedido",)], [], set()),
 ("¿La tablet Samsung Galaxy Tab A9 tiene lector de tarjetas de memoria?", {"tablet"}, [], ["Samsung Galaxy Tab A9"], {"lector_tarjetas"}),
 ("Busco una impresora multifunción con sistema continuo para la oficina.", {"impresora"}, [], [], set()),
 ("¿El cargador Anker Nano II de 65W sirve para cargar una notebook?", {"cargador"}, [], ["Anker Nano II 65W"], {"potencia"}),
 ("¿Qué fuente de alimentación necesito para una RTX 4070 Super?", {"fuente", "placa de video"}, [], ["Asus Dual RTX 4070 Super"], {"potencia"}),
 ("¿Aceptan dólares o criptomonedas como forma de pago?", set(), [("monedas_aceptadas", "formas_pago")], [], set()),
 ("Quisiera un micrófono para hacer streaming y un par de auriculares con buen sonido. ¿Qué me recomiendan?", {"microfono", "auriculares"}, [], [], set()),
 ("¿Envían a Uruguay?", set(), [("envio_exterior",)], [], set()),
 ("¿El gabinete Corsair 4000D Airflow tiene iluminación RGB?", {"gabinete"}, [], ["Corsair 4000D Airflow"], {"retroiluminacion"}),
 ("Necesito un disco externo portátil de 2TB para hacer copias de seguridad.", {"almacenamiento externo"}, [], [], {"almacenamiento"}),
 ("¿En qué horario atienden por WhatsApp?", set(), [("horarios",)], [], set()),
 ("¿Puedo hablar con una persona del equipo de ventas?", set(), [("contacto_humano", "formas_contacto")], [], set()),
 ("¿El cooler DeepCool AK620 entra en un gabinete Cooler Master MasterBox Q300L?", {"cooler", "gabinete"}, [], ["DeepCool AK620", "Cooler Master MasterBox Q300L"], set()),
 ("¿Qué procesador Intel me recomiendan para edición de video, y qué motherboard es compatible?", {"procesador", "motherboard"}, [], [], {"procesador"}),
 ("¿Pueden envolverlo para regalo? Es un cumpleaños.", set(), [("envoltorio_regalo",)], [], set()),
 ("¿Cuándo vuelven a tener stock de la RTX 4080 Super?", {"placa de video"}, [("reposicion_stock", "stock_disponibilidad")], ["Asus TUF RTX 4080 Super"], set()),
]
VACIA = "LIBRETA: vacia, es el primer mensaje."
def ids(nm):
    r = K.identificar(nm, "", "verifika_prod")
    if r["veredicto"] == "exists": return {str(v["id"]) for v in r["variantes"]}
    if r["veredicto"] == "ambiguous": return {str(o["id"]) for o in r["opciones"]}
    raise SystemExit(f"no identifica {nm}")
if __name__ == "__main__":
    for i, (tx, *_rest) in enumerate(CASOS):
        B.T[("RED", i)] = {"libreta": VACIA, "agenda": {}}; B.TEXTOS[("RED", i, "redactada")] = tx
    oro_p = [[ids(n) for n in c[3]] for c in CASOS]
    with ThreadPoolExecutor(6) as ex:
        R = list(ex.map(B.uno, [("RED", i, "redactada", 0) for i in range(len(CASOS))]))
    json.dump(R, open(os.path.join(D, "redactadas_resp.json"), "w"), ensure_ascii=False)
    c = collections.Counter()
    for r, (tx, rub, reglas, prods, specs), op in zip(R, CASOS, oro_p):
        pred_r = {k for k, v in r["pr"].items() if v >= .5}; t3 = sorted(r["pf"], key=lambda k: -r["pf"][k])[:3]
        pred_s = {k for k, v in r["ps"].items() if v >= .5}; rank = [x for v in r["rank"].values() for x in v[:5]]
        f = [f"rubro {x}" for x in rub - pred_r] + [f"regla {g[0]} (Jev {t3})" for g in reglas if not set(g) & set(t3)] \
            + [f"producto {n}" for n, g in zip(prods, op) if not g & set(rank)] + [f"spec {s}" for s in specs - pred_s]
        c.update(rub=len(rub), rub_ok=len(rub & pred_r), rub_mas=len(pred_r - rub), reg=len(reglas), reg_ok=sum(bool(set(g) & set(t3)) for g in reglas),
                 prod=len(prods), prod_ok=sum(bool(g & set(rank)) for g in op), sp=len(specs), sp_ok=len(specs & pred_s), sp_mas=len(pred_s - specs))
        if f: print(f"  FALLA «{tx[:80]}»: {'; '.join(f)}")
    print(f"\n{len(CASOS)} redactadas | rubros {c['rub_ok']}/{c['rub']} de mas {c['rub_mas']} | reglas en top3 {c['reg_ok']}/{c['reg']} | "
          f"producto nombrado en top5 {c['prod_ok']}/{c['prod']} | specs {c['sp_ok']}/{c['sp']} de mas {c['sp_mas']}")
