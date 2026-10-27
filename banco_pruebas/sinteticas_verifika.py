"""LAS SINTETICAS DE VERIFIKA — 200 mensajes complejos de primer mensaje, armados por el codigo (27-oct-2026, FICHA 82).

Pedido de Martin del 27-oct: mas ejemplos complejos de Verifika, que quedan para otras pruebas. Un generador con semilla
fija arma cada mensaje juntando piezas: compras con reparto a destinos, compras con condicion, rubros dichos por su uso,
modelos nombrados, preguntas de la tienda, pago dividido y tope del total. Lo correcto sale de la misma estructura con
que se arma el mensaje, antes de correr ningun modelo. Los mensajes quedan en `sinteticas_verifika.json`.

La vara es la de `sinteticas_separar.calificar`: cada linea esperada en una linea distinta del modelo, con su cosa, su
cantidad, su destino y su "si"; cada pregunta en alguna linea; el pago y el tope en algun lado.

    python3 banco_pruebas/sinteticas_verifika.py --armar     los 200 mensajes, sin modelo
    python3 banco_pruebas/sinteticas_verifika.py [--ver]      la consigna de las lineas, con la clave gratis
"""
import json
import os
import random
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
ARCHIVO = os.path.join(AQUI, "sinteticas_verifika.json")

# rubro: (como lo nombra un cliente, como lo cuenta por su uso, expresion que lo encuentra)
RUBROS = {
    "mouse": ("mouse", "algo para mover el cursor", r"mouse|cursor|raton"),
    "teclado": ("teclados", "algo para escribir", r"teclado|escribir|tipear"),
    "auriculares": ("auriculares", "algo para escuchar sin molestar a nadie", r"auricular|escuchar|headset"),
    "monitor": ("monitores", "una pantalla para la compu", r"monitor|pantalla"),
    "webcam": ("webcams", "algo para que me vean en las videollamadas", r"webcam|camara|videollamada|vean"),
    "parlante": ("parlantes", "algo para escuchar musica en la casa", r"parlante|musica"),
    "memoria ram": ("memorias", "mas memoria para la PC", r"memoria|ram"),
    "ssd": ("discos SSD", "algo para que la compu arranque rapido", r"ssd|disco|arranque"),
    "router": ("routers", "algo para que llegue el wifi a toda la casa", r"router|wifi"),
    "silla gamer": ("sillas gamer", "una silla para estar horas jugando", r"silla"),
    "microfono": ("microfonos", "algo para que me escuchen bien en el stream", r"microfono|escuchen|stream"),
    "impresora": ("impresoras", "algo para imprimir los trabajos del cole", r"impresora|imprimir"),
    "cargador": ("cargadores", "algo para cargar el celular rapido", r"cargador|cargar"),
    "tablet": ("tablets", "algo para que los chicos miren dibujitos", r"tablet|dibujito"),
}
MODELOS = [("G203", "mouse", ["negro", "blanco"]), ("G502 Hero", "mouse", ["negro", "blanco"]),
           ("K380", "teclado", ["negro", "blanco"]), ("Cloud II", "auriculares", ["negro", "blanco"]),
           ("C920", "webcam", ["negro"]), ("QuadCast S", "microfono", ["negro", "blanco"]),
           ("Archer C6", "router", ["negro", "blanco"]), ("EcoTank L3250", "impresora", ["negro", "blanco"]),
           ("Galaxy Tab A9", "tablet", ["gris", "azul"]), ("Z313", "parlante", ["negro", "azul"]),
           ("Coeus", "silla gamer", ["negro", "negro y rojo"]), ("Fury Beast 16GB", "memoria ram", ["negro", "blanco"])]
LUGARES = ["Rosario", "Mendoza", "Cordoba", "Salta", "Neuquen", "Posadas", "Concordia", "Bahia Blanca", "Tucuman",
           "Mar del Plata", "Parana", "Santa Fe", "La Plata", "Corrientes", "San Juan", "Ushuaia", "Rio Cuarto", "Tandil"]
PREGUNTAS = [("hacen factura A?", r"factura"), ("cuantas cuotas sin interes tienen?", r"cuota"),
             ("que garantia tienen?", r"garantia"), ("aceptan Mercado Pago?", r"mercado"),
             ("tienen local para retirar?", r"local|retir"), ("hacen precio por cantidad?", r"cantidad|mayorist"),
             ("los productos son originales?", r"original"), ("tienen descuento pagando por transferencia?",
                                                              r"descuento|transferencia")]
PAGOS = [("pago 70 por transferencia y 30 con Mercado Pago", [70, 30]), ("la mitad con debito y la mitad en efectivo",
                                                                        [50, 50]),
         ("pago 60 con tarjeta y 40 por transferencia", [60, 40]), ("dividimos el pago 80 y 20", [80, 20])]
NUM = {1: "un", 2: "dos", 3: "tres", 4: "cuatro", 5: "cinco", 6: "seis"}
SOLO = {**NUM, 1: "uno"}  # el numero sin sustantivo: "uno de cada uno", "me llevo uno"


def L(cosa, cant=None, dest=None, si=False):  # noqa: N802
    return {"cosa": cosa, "cant": cant, "dest": dest, "si": si}


def _rx_lugar(lu: str) -> str:
    return lu.lower().split()[0]


def reparto(r: random.Random) -> tuple:
    """Dos o tres rubros, cada uno con cantidad, repartidos a dos o tres destinos."""
    rubros = r.sample(list(RUBROS), r.choice([2, 2, 3]))
    lugares = r.sample(LUGARES, r.choice([2, 2, 3]))
    por_uso = r.random() < 0.4
    if len(lugares) == 2 and r.random() < 0.5:
        # "uno de cada uno a A y el resto a B"
        tot = r.choice([2, 3, 4])
        partes = [(lu, 1 if i == 0 else tot - 1) for i, lu in enumerate(lugares)]
        cosas = ", ".join(f"{NUM[tot]} {RUBROS[x][0]}" if not (por_uso and i == 0) else f"{NUM[tot]} de {RUBROS[x][1]}"
                          for i, x in enumerate(rubros))
        msg = f"necesito {cosas}. Uno de cada uno a {lugares[0]} y el resto a {lugares[1]}."
    else:
        partes = [(lu, r.choice([1, 2])) for lu in lugares]
        tot = sum(k for _, k in partes)
        cosas = " y ".join(f"{NUM.get(tot, tot)} {RUBROS[x][0]}" for x in rubros)
        repartos = ", ".join(f"{SOLO[k]} de cada uno a {lu}" for lu, k in partes)
        msg = f"quiero {cosas}: {repartos}."
    lineas = [L(RUBROS[x][2], k, _rx_lugar(lu)) for lu, k in partes for x in rubros]
    return msg, lineas


def condicion(r: random.Random) -> tuple:
    """Pregunta por un modelo en un color; si hay, lleva tantos; si no, otro modelo o color."""
    m, rub, colores = r.choice(MODELOS)
    color = r.choice(colores)
    k = r.choice([1, 2, 3])
    otro = r.choice([x for x in MODELOS if x[1] == rub and x[0] != m] or [None])
    alterno = f"el {otro[0]}" if otro else f"en otro color"
    msg = r.choice([f"tenes el {m} en {color}? si hay, anotame {SOLO[k]}; si no, {alterno}.",
                    f"si el {m} viene en {color} me llevo {SOLO[k]}, y si no, {alterno}."])
    rx = m.lower().split()[0]
    lineas = [L(rx), L(rx, k, si=True), L((otro[0].lower().split()[0] if otro else rx), None, si=True)]
    if msg.startswith("si el"):
        lineas = lineas[1:]
    return msg, lineas


def modelos(r: random.Random) -> tuple:
    """Dos modelos nombrados, cada uno con cantidad, a un destino o a dos."""
    a, b = r.sample(MODELOS, 2)
    ka, kb = r.choice([1, 2]), r.choice([1, 2, 3])
    if r.random() < 0.5:
        lu = r.choice(LUGARES)
        msg = f"mandame {NUM[ka]} {a[0]} y {NUM[kb]} {b[0]} a {lu}."
        lineas = [L(a[0].lower().split()[0], ka, _rx_lugar(lu)), L(b[0].lower().split()[0], kb, _rx_lugar(lu))]
    else:
        la, lb = r.sample(LUGARES, 2)
        msg = f"un pedido: {NUM[ka]} {a[0]} a {la} y {NUM[kb]} {b[0]} a {lb}."
        lineas = [L(a[0].lower().split()[0], ka, _rx_lugar(la)), L(b[0].lower().split()[0], kb, _rx_lugar(lb))]
    return msg, lineas


def ver(r: random.Random) -> tuple:
    """Pedir ver opciones de un rubro dicho por su uso, con una condicion de precio."""
    x = r.choice(list(RUBROS))
    tope = r.choice([50, 80, 120, 200])
    msg = r.choice([f"busco {RUBROS[x][1]}, que no pase de {tope} mil.",
                    f"mostrame {RUBROS[x][0]} de menos de {tope} mil, los mas baratos."])
    return msg, [L(RUBROS[x][2])]


def armar(n: int = 200, semilla: int = 2710) -> list:
    r = random.Random(semilla)
    piezas = [reparto, condicion, modelos, ver]
    casos = []
    for i in range(n):
        k = r.choice([2, 2, 2, 3])
        elegidas = [reparto] + r.sample(piezas[1:], k - 1) if r.random() < 0.4 else r.sample(piezas, min(k, 4))
        textos, lineas, preguntas, pago, tope = [], [], [], [], None
        for f in elegidas:
            t, ls = f(r)
            textos.append(t)
            lineas += ls
        for p, rx in r.sample(PREGUNTAS, r.choice([0, 1, 1, 2])):
            textos.append(p)
            preguntas.append(rx)
        if r.random() < 0.25:
            t, pago = r.choice(PAGOS)
            textos.append(t + ".")
        elif r.random() < 0.15:
            tope = r.choice([300, 500, 800]) * 1000
            textos.append(f"en total no quiero pasar de {tope // 1000} mil.")
        msg = " ".join(x[0].upper() + x[1:] for x in textos)
        casos.append({"id": f"V{i + 1:03d}", "tienda": "verifika", "mensaje": msg, "lineas": lineas,
                      "preguntas": preguntas, "pago": pago, "tope": tope})
    return casos


async def correr() -> None:
    import asyncio
    sys.path.insert(0, AQUI)
    import momento0 as M
    import sinteticas_separar as S
    casos = json.load(open(ARCHIVO, encoding="utf-8"))
    j = lambda e: json.dumps(e, ensure_ascii=False)  # noqa: E731
    consigna = M.LINEAS.format(contar="", temas=", ".join(M.F._temas_de(M.P.TID)), ej1=j(M.EJ1), ej2=j(M.EJ2))
    sem = asyncio.Semaphore(int(os.environ.get("A_LA_VEZ", "2")))

    async def uno(caso):
        async with sem:
            for intento in range(6):
                try:
                    return M.interprete._json(await M.interprete._pedir(
                        [{"role": "system", "content": consigna},
                         {"role": "user", "content": f"MENSAJE DEL CLIENTE: {caso['mensaje']}"}],
                        "sinteticas", M._formato_lineas(False)))
                except Exception as e:  # noqa: BLE001 — la gratis se traba: se espera y se reintenta
                    if intento == 5:
                        return {"error": f"{type(e).__name__}: {str(e)[:100]}"}
                    await asyncio.sleep(20 * (intento + 1))

    salidas = await asyncio.gather(*[uno(c) for c in casos])
    ok = [(c, s, S.calificar(c, s)) for c, s in zip(casos, salidas) if "error" not in s]
    with open(os.path.join(AQUI, "sinteticas_verifika_corrida.jsonl"), "w", encoding="utf-8") as fh:
        for c, s in zip(casos, salidas):
            fh.write(json.dumps({"id": c["id"], "salida": s}, ensure_ascii=False) + "\n")
    print(f"\nLAS SINTETICAS DE VERIFIKA · {len(casos)} mensajes, {len(ok)} con respuesta")
    print(f"  enteros {sum(r['entero'] for _, _, r in ok)} de {len(ok)} · lineas {sum(r['lineas'] for _, _, r in ok)} de "
          f"{sum(len(c['lineas']) for c, _, _ in ok)} · preguntas {sum(r['preguntas'] for _, _, r in ok)} de "
          f"{sum(len(c['preguntas']) for c, _, _ in ok)} · pago {sum(r['pago'] for c, _, r in ok if c['pago'])} de "
          f"{sum(bool(c['pago']) for c, _, _ in ok)} · tope {sum(r['tope'] for c, _, r in ok if c['tope'])} de "
          f"{sum(bool(c['tope']) for c, _, _ in ok)}")
    if "--ver" in sys.argv:
        for c, s, r in ok:
            if not r["entero"]:
                print(f"  {c['id']} {r}\n    {c['mensaje']}\n    {[x.get('texto') for x in s.get('lineas') or []]}"
                      f" · todo {s.get('todo')}")


if __name__ == "__main__":
    if "--armar" in sys.argv:
        casos = armar()
        json.dump(casos, open(ARCHIVO, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"{len(casos)} mensajes · {sum(len(c['lineas']) for c in casos)} lineas · "
              f"{sum(len(c['preguntas']) for c in casos)} preguntas · {sum(bool(c['pago']) for c in casos)} con pago · "
              f"{sum(bool(c['tope']) for c in casos)} con tope")
        for c in casos[:6]:
            print(" ", c["id"], c["mensaje"])
    else:
        import asyncio
        asyncio.run(correr())
