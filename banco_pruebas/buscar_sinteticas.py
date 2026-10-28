"""LA BUSQUEDA COMPLETA — frases variadas de rubro, tema y producto, de la separacion a la busqueda (28-oct-2026).

FICHA 83, pedido de Martin del 28-oct: probar los embeddings de forma mas completa que con las 14 frases repetidas de las
sinteticas. Frases escritas a mano, sin mirar `alias.json`, cada una con lo que busca:

  rubro     cada rubro de la tienda dicho de seis formas: por su uso, por el problema que resuelve, por como se ve, con
            un apodo, para quien es, y mal escrito.
  tema      las reglas de la tienda dichas como las pregunta un cliente, dos por tema.
  producto  modelos de la tienda dichos por apodo, a medias o mal escritos.

El camino es el del bot: el modelo separa cada frase con la consigna de las lineas, y el codigo busca por embeddings en
UN solo indice con todo lo de la tienda —rubros con sus alias, temas con sus palabras de la FAQ, y productos por marca y
modelo—, porque el codigo no sabe de antemano que tipo de cosa es. Tres busquedas: con las palabras del cliente, con la
"cosa" que escribio el modelo, y con las dos sumadas.

    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/buscar_sinteticas.py [--ver]
"""
RUBRO = {
    "mouse": ["algo para mover la flechita en la pantalla", "se me rompio el que uso con la mano derecha para hacer clic",
              "uno chiquito con ruedita para la notebook", "el bicho ese con cable que va al lado del teclado",
              "uno para mi viejo que no se maneja con el touchpad", "un maus inalanbrico"],
    "teclado": ["algo para tipear comodo los trabajos de la facu", "se me borraron las letras del que tengo",
                "uno con las teclitas que se iluminan", "uno de esos que hacen clic clic al escribir",
                "para mi hija que escribe mucho en la tablet", "un teklado mecanico"],
    "auriculares": ["algo para escuchar musica en el colectivo", "mis vecinos se quejan del ruido cuando juego de noche",
                    "unos que se ponen arriba de la cabeza con almohadillas", "unos que cancelen el ruido para viajar",
                    "para mi hijo que juega online y habla con los amigos", "unos auricualres gamer"],
    "monitor": ["una pantalla mas grande para trabajar con dos ventanas", "la que tengo se ve borrosa y me cansa la vista",
                "una pantalla curva para el escritorio", "una pantalla de 144 para jugar fluido",
                "para la oficina de mi papa que usa planillas", "un monitror de 27"],
    "webcam": ["algo para que me vean en las reuniones del trabajo", "la camarita de la notebook se ve horrible",
               "una camarita que se engancha arriba de la pantalla", "algo para hacer streaming mostrando la cara",
               "para mi abuela que quiere hacer videollamadas con los nietos", "una camara web full jd"],
    "parlante": ["algo para poner musica fuerte en el asado", "la compu suena muy bajito",
                 "una cajita de sonido que se conecta por bluetooth", "algo para escuchar musica en el living",
                 "para la pileta, que aguante el agua", "un parlnte portatil"],
    "memoria ram": ["algo para que la compu no se tilde con muchas pestanas", "la PC se queda colgada cuando abro varios programas",
                    "unos peinecitos que van en la placa", "8 gigas mas para la compu",
                    "para la notebook de mi hijo que va lenta", "memorias dd4 de 16"],
    "ssd": ["algo para que la compu prenda en segundos", "la compu tarda mil años en arrancar",
            "un disquito solido para cambiar el viejo", "un nvme para la placa",
            "para la notebook vieja que todavia tiene disco mecanico", "un dico ssd de 1 tera"],
    "router": ["algo para que llegue internet a toda la casa", "el wifi no llega a mi pieza",
               "una cajita con antenas para el internet", "un mesh para dos pisos",
               "para la oficina donde se conectan veinte personas", "un ruter wifi 6"],
    "silla gamer": ["algo comodo para sentarme muchas horas frente a la compu", "me duele la espalda de la silla de cocina",
                    "una silla con apoya cabeza y almohadones", "una de esas sillas de gamer con colores",
                    "para mi hijo que se pasa la tarde jugando", "una sila gamer reclinable"],
    "microfono": ["algo para grabar podcast", "en las llamadas no me escuchan bien",
                  "uno de esos que se ponen en un brazo sobre el escritorio", "algo para cantar y grabarme",
                  "para mi hija que hace streams", "un microfno usb"],
    "impresora": ["algo para sacar en papel los trabajos del cole", "estoy harto de ir a imprimir al kiosco",
                  "una de esas con tanque de tinta que se recarga", "una multifuncion que escanee",
                  "para la oficina, que imprima mucho y barato", "una inpresora wifi"],
    "cargador": ["algo para que el celular cargue rapido", "el celu tarda horas en cargarse",
                 "un enchufe con puerto usb c", "uno de 65 watts para la notebook y el celu",
                 "para mi mama que perdio el del telefono", "un cargdor tipo c"],
    "tablet": ["algo para que los chicos vean dibujitos en el auto", "el celular es muy chico para leer",
               "una pantalla tactil grande sin teclado", "algo para estudiar con pdf y tomar notas",
               "para mi abuelo que quiere ver el futbol en la cama", "una tablet android barata"],
    "notebook": ["una compu que pueda llevar a la facu", "mi pc de escritorio no la puedo mover",
                 "una portatil liviana", "una laptop para programar",
                 "para mi hija que empieza la secundaria", "una notbuk con 16 de ram"],
    "placa de video": ["algo para que los juegos anden en ultra", "los juegos me van a 20 cuadros",
                       "una grafica con tres ventiladores", "una rtx para renderizar",
                       "para la PC gamer que estoy armando", "una placa de vido nvidia"],
    "procesador": ["el cerebro de la compu", "la compu se queda corta para editar video",
                   "un chip para el socket am4", "un ryzen o un intel para armar la pc",
                   "para la PC de diseño de mi hermano", "un procesdor de 8 nucleos"],
    "motherboard": ["la placa donde va todo conectado", "se me quemo la placa principal",
                    "una placa madre con wifi", "una mother para ryzen",
                    "para armar la PC desde cero", "una motherbord b550"],
    "fuente": ["lo que le da energia a la PC", "la compu se apaga sola cuando juego",
               "una de 650 watts certificada", "una modular para que no queden cables",
               "para la placa de video nueva que pide mas potencia", "una funte de 750"],
    "gabinete": ["la caja donde va la PC", "la PC no tiene donde ir",
                 "una caja con vidrio para ver las luces", "una torre con buena ventilacion",
                 "para armar la PC del nene", "un gabiente blanco"],
    "cooler": ["algo para que la PC no levante temperatura", "el procesador llega a 90 grados",
               "un disipador de torre", "una refrigeracion liquida",
               "para la PC que esta al lado de la ventana en verano", "un culer para el cpu"],
    "almacenamiento externo": ["algo para guardar las fotos de las vacaciones", "se me lleno la compu y no quiero borrar nada",
                               "un disco que se enchufa por usb", "algo para hacer backup del trabajo",
                               "para mi papa que tiene todas las fotos en el celu", "un disco exterrno de 2 teras"],
}
TEMA = {
    "ubicacion": ["donde quedan ustedes?", "tienen negocio para ir a ver?"],
    "horarios": ["hasta que hora atienden?", "abren los sabados?"],
    "formas_pago": ["como se puede pagar?", "aceptan tarjeta de credito?"],
    "cuotas": ["se puede pagar en cuotas?", "cuantas cuotas sin interes hay?"],
    "costo_envio": ["cuanto sale el envio?", "el envio lo cobran aparte?"],
    "plazo_envio": ["cuanto tarda en llegar?", "si compro hoy cuando lo tengo?"],
    "garantia": ["que garantia tienen los productos?", "si se rompe a los dos meses que hago?"],
    "devoluciones": ["puedo devolver si no me gusta?", "tienen devolucion?"],
    "factura": ["hacen factura A?", "me dan factura para la empresa?"],
    "descuento_transferencia": ["hay descuento pagando por transferencia?", "si pago con transferencia sale menos?"],
    "contacto_humano": ["puedo hablar con una persona?", "me pasas con alguien de ventas?"],
    "mayoristas": ["hacen precio por cantidad?", "venden al por mayor?"],
    "marcas_originales": ["los productos son originales?", "no son truchos, no?"],
    "usados": ["venden cosas usadas?", "tienen reacondicionados?"],
    "defectuoso": ["me llego roto, que hago?", "vino fallado de fabrica"],
    "envio_urgente": ["lo pueden mandar hoy mismo?", "tienen envio express?"],
    "envoltorio_regalo": ["me lo envuelven para regalo?", "es para regalar, lo mandan lindo?"],
    "contenido_caja": ["que trae la caja?", "viene con cable?"],
    "seguimiento_pedido": ["donde esta mi pedido?", "me pasas el numero de seguimiento?"],
    "cancelacion_pedido": ["puedo cancelar la compra?", "me arrepenti, se puede anular?"],
    "envio_exterior": ["mandan a Uruguay?", "hacen envios fuera del pais?"],
    "pago_contra_entrega": ["puedo pagar cuando me llega?", "pago al recibir?"],
    "retiro_local": ["lo puedo pasar a buscar?", "se puede retirar en persona?"],
    "promociones": ["tienen alguna promo?", "hay ofertas esta semana?"],
}
PRODUCTO = {
    "G203": ["el g 203", "el g203 de logi"], "G502 Hero": ["el g502", "el logitech g 502 hero"],
    "MX Master 3S": ["el mx master", "el master 3"], "DeathAdder V3": ["el deathadder", "el death adder de razer"],
    "Cobra M711": ["el redragon cobra", "el m711"], "K380": ["el k 380", "el k380 de logitech"],
    "Kumara K552": ["el kumara", "el k552"], "BlackWidow V4": ["el black widow", "el blackwidow de razer"],
    "Cloud II": ["los cloud 2", "los hyperx cloud dos"], "WH-1000XM5": ["los sony xm5", "los 1000xm5"],
    "Tune 510BT": ["los jbl tune 510", "los tune 510 bt"], "Kraken V3": ["los kraken", "los razer kraken v3"],
    "C920": ["la c920", "la logitech c 920"], "QuadCast S": ["el quadcast", "el hyperx quad cast"],
    "Yeti": ["el blue yeti", "el yeti"], "Go 3": ["el jbl go 3", "el go3"], "Flip 6": ["el flip 6", "el jbl flip"],
    "Archer C6": ["el archer c6", "el tp link c6"], "EcoTank L3250": ["la epson l3250", "la ecotank 3250"],
    "Galaxy Tab A9": ["la tab a9", "la galaxy tab a 9"], "Redmi Pad SE": ["la redmi pad", "la xiaomi pad se"],
    "Odyssey G5": ["el odyssey g5", "el samsung g5"], "RTX 4060": ["la 4060", "la rtx 4060 de asus"],
    "Ryzen 5 5600": ["el ryzen 5600", "el r5 5600"], "Fury Beast DDR4": ["la fury beast ddr4", "la kingston fury"],
    "980 PRO": ["el samsung 980 pro", "el 980pro"], "Coeus": ["la coeus", "la redragon coeus"],
    "Hyper 212": ["el hyper 212", "el cooler master 212"], "H5 Flow": ["el h5 flow", "el nzxt h5"],
}


def casos() -> list:
    out = [{"tipo": "rubro", "oro": r, "frase": f} for r, fs in RUBRO.items() for f in fs]
    out += [{"tipo": "tema", "oro": t, "frase": f} for t, fs in TEMA.items() for f in fs]
    out += [{"tipo": "producto", "oro": p, "frase": f} for p, fs in PRODUCTO.items() for f in fs]
    return out


def main() -> None:
    import asyncio
    import collections
    import json
    import os
    import re
    import sys
    import numpy as np
    aqui = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, aqui)
    import candidatos82 as C82
    import momento0 as M
    from app.core import agente
    from app.core.flujo import catalogo as K
    from vara_dato import n
    tid = M.P.TID
    cs = casos()
    # 1. La separacion, con la consigna de las lineas: de cada frase sale una linea con su "cosa".
    j = lambda e: json.dumps(e, ensure_ascii=False)  # noqa: E731
    consigna = M.LINEAS.format(contar="", temas=", ".join(M.F._temas_de(tid)), ej1=j(M.EJ1), ej2=j(M.EJ2))
    sem = asyncio.Semaphore(4)

    async def uno(frase):
        async with sem:
            try:
                return M.interprete._json(await M.interprete._pedir(
                    [{"role": "system", "content": consigna}, {"role": "user", "content": f"MENSAJE DEL CLIENTE: {frase}"}],
                    "buscar", M._formato_lineas(False)))
            except Exception as e:  # noqa: BLE001
                return {"error": f"{type(e).__name__}: {str(e)[:100]}"}

    async def todas():
        return await asyncio.gather(*[uno(c["frase"]) for c in cs])
    salidas = asyncio.run(todas())
    for c, s in zip(cs, salidas):
        ls = s.get("lineas") or []
        c["cosa"] = " ".join(str(x.get("cosa") or "") for x in ls).strip() or "-"
        c["texto"] = " ".join(str(x.get("texto") or "") for x in ls).strip() or c["frase"]
    # 2. El indice de la tienda, uno solo: rubros con sus alias, temas con sus palabras, productos por marca y modelo.
    alias = agente._alias(tid).get("rubros") or {}
    base = [(r, ("rubro", r)) for r in M.F._rubros(tid)] + [(f, ("rubro", r)) for r, fs in alias.items() for f in fs]
    faq = json.load(open(os.path.join(os.path.dirname(aqui), "data", "clientes", tid, "faq.json"), encoding="utf-8"))
    base += [(f"{t['tema'].replace('_', ' ')}: {', '.join(t.get('keywords') or [])}", ("tema", t["tema"])) for t in faq]
    vistos = {}
    for p in K.productos(tid):
        vistos.setdefault(f"{p.get('marca')} {p.get('modelo')}", ("producto", f"{p.get('marca')} {p.get('modelo')}"))
    base += list(vistos.items())
    textos = [b for b, _ in base] + [c["frase"] for c in cs] + [c["cosa"] for c in cs]
    E = dict(zip(dict.fromkeys(textos), C82.embeddings(list(dict.fromkeys(textos)))))
    mb = np.stack([E[b] for b, _ in base])
    claves = sorted(set(k for _, k in base))
    idx = collections.defaultdict(list)
    for i, (_, k) in enumerate(base):
        idx[k].append(i)

    def puntaje(q):
        s = mb @ E[q]
        return {k: max(s[i] for i in ii) for k, ii in idx.items()}

    def bien(k, c):
        if k[0] != c["tipo"]:
            return False
        if c["tipo"] == "producto":
            return n(c["oro"]) in n(k[1])
        return k[1] == c["oro"]

    cuenta = collections.Counter()
    total = collections.Counter(c["tipo"] for c in cs)
    malos = []
    for c in cs:
        a, b = puntaje(c["frase"]), puntaje(c["cosa"])
        for nombre, p in (("cliente", a), ("cosa", b), ("las dos", {k: a[k] + b[k] for k in claves})):
            orden = sorted(claves, key=lambda k: -p[k])
            cuenta[(c["tipo"], nombre, 1)] += bien(orden[0], c)
            cuenta[(c["tipo"], nombre, 3)] += any(bien(k, c) for k in orden[:3])
            if nombre == "las dos" and not bien(orden[0], c):
                malos.append(f"  {c['tipo']:8} {c['oro']:22} {c['frase'][:50]!r:52} cosa {c['cosa'][:22]!r:24} → {orden[0][1]}")
    print(f"\nLA BUSQUEDA COMPLETA · {len(cs)} frases: {dict(total)} · indice de {len(base)} entradas · "
          f"{sum('error' in s for s in salidas)} sin separar")
    for tipo in ("rubro", "tema", "producto"):
        print(f"  {tipo}")
        for nombre in ("cliente", "cosa", "las dos"):
            print(f"    {nombre:8} primero {cuenta[(tipo, nombre, 1)]:3} de {total[tipo]} · entre los tres "
                  f"{cuenta[(tipo, nombre, 3)]:3}")
    if "--ver" in sys.argv:
        print("\n".join(malos))
    with open(os.path.join(aqui, "buscar_sinteticas_corrida.jsonl"), "w", encoding="utf-8") as fh:
        for c in cs:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
