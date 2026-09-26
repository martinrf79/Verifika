"""DESMENUZAR — partir y traducir, con y sin tablero (26-sep-2026).

Mide SOLO el primer paso: el modelo parte el mensaje en piezas y traduce cada
una. Sin herramientas, sin buscador, sin redactar. Dos notas separadas:

  partir    las piezas correctas: tipo, lo que nombra, y de cual depende
  traducir  cada pieza cae en el rubro o el tema de la casa que corresponde

Tres formas de traducir, y es lo que se decide:

  A  de cabeza   el modelo traduce a palabras comunes ("aparato con teclas" es
                 teclado). El CODIGO ubica esas palabras en el indice de la
                 fuente: los tags de los productos por rubro y las palabras
                 clave de la FAQ. El indice crece con el catalogo; el prompt no.
  B  tablero     el modelo recibe el esquema de la tienda —rubros, campos,
                 temas, equipos— y traduce directo a esos nombres. Una llamada.
  C  dos vueltas A primero; despues el codigo le devuelve al modelo los tres
                 mejores candidatos del indice por pieza y el modelo elige.

Las piezas correctas estan escritas a mano abajo, antes de correr.

  python3 -m banco_pruebas.desmenuzar                  A, B y C, cinco repeticiones
  python3 -m banco_pruebas.desmenuzar --informe
  opciones: --formas A,B,C  --reps 5  --hilos 8
"""
import csv
import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

from banco_pruebas.sonda_modelo import _json, _n

D = "data/clientes/verifika_prod/"
SALIDA = "banco_pruebas/desmenuzar_corridas.jsonl"
PRODUCTOS = list(csv.DictReader(open(D + "productos.csv", encoding="utf-8")))
FAQ = json.load(open(D + "faq.json", encoding="utf-8"))
RUBROS = sorted({p["categoria"] for p in PRODUCTOS})
TEMAS = [f["tema"] for f in FAQ]
TIPOS = ["producto", "buscar", "envio", "politica", "compatibilidad", "cuenta", "comprar",
         "explicar", "verificar", "repreguntar", "charla"]
CAMPOS = ["precio_ars", "stock", "marca", "color", "conexion", "bluetooth", "bateria", "ram", "almacenamiento",
          "procesador", "peso_gramos", "pais_fabricacion", "pais_marca", "garantia_meses", "switch_teclado",
          "retroiluminacion", "resolucion", "hz", "panel", "potencia", "memoria_video", "formato", "wifi"]
EQUIPOS = ["PC con Windows", "Mac", "PC con Linux", "Android", "iPhone o iPad", "PlayStation 5", "PlayStation 4",
           "Xbox", "Nintendo Switch", "Smart TV", "PC de escritorio", "notebook"]


# ══ LOS CASOS: las 58 y diez de jerga ══════════════════════════════════════
# pieza: tipos aceptados | claves que tiene que nombrar ("a|b" cualquiera) |
#        rubro o tema correcto de la tienda | dep: depende de otra pieza |
#        cond: palabras de la condicion traducida | opc: puede faltar

def p(tipos, *claves, rubro=None, tema=None, dep=False, cond=None, opc=False):
    return {"tipos": tipos.split("|"), "claves": list(claves), "rubro": rubro,
            "tema": tema.split("|") if tema else None, "dep": dep, "cond": cond, "opc": opc}


PROD = "producto|buscar"
CASOS = [
    ("C01", [], "tenes el G305?", [p(PROD, "g305", rubro="mouse")]),
    ("C02", [], "que parlantes tenes?", [p("buscar", "parlante", rubro="parlante")]),
    ("C03", [], "cuantos dpi tiene el G502 Hero?", [p(PROD, "g502", rubro="mouse")]),
    ("C04", [], "el K120, que es inalambrico, cuanto sale?",
     [p(PROD, "k120", rubro="teclado"), p("verificar|producto", "inalambric")]),
    ("C05", [], "busco una notebook con 16 GB de RAM", [p("buscar", "16", rubro="notebook", cond="16")]),
    ("C06", [], "quiero un mouse inalambrico, preferentemente Logitech",
     [p("buscar", "logitech", rubro="mouse", cond="inalambric|conexion")]),
    ("C07", [], "un mouse que no sea Genius", [p("buscar", "genius", rubro="mouse")]),
    ("C08", [], "una tablet, lo menos china posible",
     [p("buscar", "chin", rubro="tablet", cond="chin|pais|origen")]),
    ("C09", [], "cual es el monitor mas barato?", [p("buscar", "monitor", rubro="monitor", cond="barat|precio|econom")]),
    ("C10", [], "cuanto sale el envio a Posadas?", [p("envio", "posadas")]),
    ("C11", [], "hacen factura A?", [p("politica", "factura", tema="factura|datos_fiscales")]),
    ("C12", [], "tienen 50 por ciento off en todo, no?",
     [p("verificar|politica", "50", tema="promociones|descuento_transferencia")]),
    ("C13", [], "soy revendedor, tienen precio mayorista?",
     [p("politica", "mayorista|revend", tema="mayoristas")]),
    ("C14", [], "que conviene, DDR4 o DDR5?", [p("explicar", "ddr")]),
    ("C15", [], "me llevo dos G305 negros", [p("comprar", "g305")]),
    ("C16", [], "me llevo el K120 negro, pago 70 por ciento transferencia y 30 por ciento Mercado Pago",
     [p("comprar|producto", "k120"), p("cuenta|politica", "70")]),
    ("C17", [], "cuanto sale el G305 y que teclados mecanicos tenes?",
     [p(PROD, "g305", rubro="mouse"), p("buscar", "mecanic", rubro="teclado")]),
    ("C18", [], "tenes auriculares JBL y cuanto sale mandarlos a Cordoba?",
     [p(PROD, "jbl", rubro="auriculares"), p("envio", "cordoba|córdoba")]),
    ("C19", [], "el G203 tiene stock? y hacen factura A?",
     [p(PROD, "g203", rubro="mouse"), p("politica", "factura", tema="factura|datos_fiscales")]),
    ("C20", [], "sumame dos K120 negros y un G203 negro", [p("cuenta", "k120", "g203")]),
    ("C21", ["cliente: quiero un G305 negro y un K120 negro",
             "bot: el G305 negro sale $80.500 y el K120 negro $14.500"],
     "sumame todo y pago 70 por ciento transferencia y 30 por ciento Mercado Pago",
     [p("cuenta", "g305", "k120"), p("cuenta|politica", "70", opc=True)]),
    ("C22", [], "el G305 sirve para jugar? cuanto sale?",
     [p(PROD, "g305", rubro="mouse"), p("explicar|producto", "jug|gaming|gamer", opc=True)]),
    ("C23", [], "quiero el G305 en blanco y un K120",
     [p("comprar|producto|buscar", "g305", "blanco", rubro="mouse"), p("comprar|producto|buscar", "k120", rubro="teclado")]),
    ("C24", [], "teclado y mouse, los dos lo mas baratos posible",
     [p("buscar", "teclado", rubro="teclado", cond="barat|precio|econom"),
      p("buscar", "mouse", rubro="mouse", cond="barat|precio|econom")]),
    ("C25", [], "dos G305 negros y tres K120 blancos, cuanto es?", [p("cuenta", "g305", "k120")]),
    ("C26", [], "mandame un G203 a Rosario y otro a Mendoza, cuanto sale cada envio?",
     [p("envio", "rosario"), p("envio", "mendoza")]),
    ("C27", ["cliente: mostrame mouse Logitech",
             "bot: tengo el G203 a $37.500, el G502 Hero a $70.000 y el M170 a $12.000"],
     "de esos, cual es el mas barato?", [p("buscar|producto", "barat|m170|precio", rubro="mouse")]),
    ("C28", [], "si no hay G502 Hero en negro, pasame el G305",
     [p(PROD, "g502", rubro="mouse"), p("producto|comprar|buscar", "g305", dep=True)]),
    ("C29", [], "si el G305 anda con Mac, me lo llevo",
     [p("compatibilidad", "g305", "mac"), p("comprar", "g305", dep=True)]),
    ("C30", [], "tengo una PC de escritorio con placa DDR5. si la Kingston Fury Beast DDR4 16GB no le sirve, que otra memoria hay?",
     [p("compatibilidad", "ddr4|fury|kingston"), p("buscar", "ddr5", rubro="memoria ram", dep=True)]),
    ("C31", [], "sumame un MX Master 3S negro y dos G305 negros, si pasa de 300 mil saca el MX",
     [p("cuenta", "mx", "g305", "300")]),
    ("C32", [], "entre el G305 y el G203, dame el que sea inalambrico",
     [p("producto|buscar|compatibilidad", "inalambric"), p("comprar", "g305|g203|inalambric", dep=True)]),
    ("C33", [], "quiero un teclado Redragon, ah no, mejor Logitech", [p("buscar", "logitech", rubro="teclado")]),
    ("C34", ["cliente: cuanto sale mandar un G203 a Rosario?", "bot: a Rosario el envio sale $7.000"],
     "me equivoque, era para Cordoba, no Rosario", [p("envio", "cordoba|córdoba")]),
    ("C35", ["cliente: busco un mouse gamer Logitech", "bot: tengo el G203, el G502 Hero y el G Pro"],
     "ya no importa la marca, pasame otras opciones", [p("buscar", "gamer|gaming", rubro="mouse")]),
    ("C36", [], "el G305 anda con mi Mac?", [p("compatibilidad", "g305", "mac")]),
    ("C37", [], "tengo una notebook, que memoria ram le sirve?",
     [p("compatibilidad|buscar", "notebook", rubro="memoria ram")]),
    ("C38", ["cliente: cuanto sale la Kingston Fury Beast DDR4 16GB?", "bot: sale $41.000"],
     "le sirve a mi pc?", [p("repreguntar", "pc|placa|motherboard|equipo|modelo"),
                           p("compatibilidad", "fury|ddr4|kingston", opc=True)]),
    ("C39", [], "el G203 es inalambrico, no? lo quiero para viajar",
     [p("verificar|producto", "g203", "inalambric", rubro="mouse")]),
    ("C40", [], "me dijeron que el envio es gratis a todo el pais, no?",
     [p("verificar|politica", "gratis", tema="costo_envio|envios")]),
    ("C41", [], "soy jubilado, tienen descuento?",
     [p("politica", "descuento|jubil", tema="promociones|descuento_transferencia")]),
    ("C42", [], "quiero una notebook con 64 GB de RAM por menos de 200 mil",
     [p("buscar", "64", rubro="notebook", cond="200")]),
    ("C43", ["cliente: cuanto sale el K120?", "bot: sale $14.500"], "y ese es inalambrico?",
     [p(PROD + "|verificar", "k120", "inalambric", rubro="teclado")]),
    ("C44", ["cliente: cuanto salen el G305 y el G203?", "bot: el G305 sale $80.500 y el G203 $37.500"],
     "el G305 no me convence, el otro tiene stock?", [p(PROD, "g203", rubro="mouse")]),
    ("C45", ["cliente: busco un mouse Logitech con cable", "bot: tengo el G203 y el G502 Hero"], "y en blanco?",
     [p("buscar", "blanco", "logitech", rubro="mouse")]),
    ("C46", ["cliente: busco un teclado que no sea Redragon", "bot: tengo el K120 y el Keychron K2"],
     "y alguno mecanico?", [p("buscar", "mecanic", "redragon", rubro="teclado")]),
    ("C47", ["cliente: hola, soy de Posadas, Misiones", "bot: hola! en que te ayudo?"],
     "cuanto me sale el G203 negro con envio?",
     [p("producto|cuenta|buscar", "g203"), p("envio|cuenta", "posadas")]),
    ("C48", ["cliente: me llevo un G305 negro", "bot: dale, el G305 negro sale $80.500"],
     "mandamelo a Rosario, cuanto seria en total?",
     [p("envio", "rosario"), p("cuenta", "g305|total")]),
    ("C49", ["cliente: cuanto sale el teclado Logitech K120 negro?", "bot: sale $14.500",
             "cliente: y auriculares JBL tenes?", "bot: tengo el JBL Tune 510BT a $78.000",
             "cliente: tenes webcams?", "bot: tengo la Logitech C920 y la C270"],
     "el teclado logi ese del principio, tiene stock?", [p(PROD, "k120", rubro="teclado")]),
    ("C50", ["cliente: estoy entre el G203 y el G305", "bot: el G203 sale $37.500 y el G305 $80.500",
             "cliente: me llevo uno", "bot: cual de los dos, el G203 o el G305?"],
     "el primero", [p("comprar", "g203")]),
    ("C51", [], "cuanto sale el G305 negro? y mandame ese a Cordoba",
     [p(PROD, "g305", rubro="mouse"), p("envio", "cordoba|córdoba")]),
    ("C52", ["cliente: que tenes en mouse Logitech, teclados Logitech y auriculares JBL?",
             "bot: el G203 a $37.500, el K120 a $14.500 y los JBL Tune 510BT a $78.000"],
     "y ese cuanto?", [p("repreguntar", "cual|ese|cuál")]),
    ("C53", ["cliente: cuanto sale el G502 Hero?", "bot: el G502 Hero sale $70.000, en negro y en blanco"],
     "del que me dijiste, si no hay en negro dame el blanco",
     [p(PROD, "g502", "negro", rubro="mouse"), p("comprar|producto", "blanco", dep=True)]),
    ("C54", [], "tengo una fuente de 550 watts, cual es la placa de video mas potente que aguante?",
     [p("buscar|compatibilidad", "550", rubro="placa de video")]),
    ("C55", ["cliente: cuanto salen el G305 negro y el G203 negro?", "bot: el G305 $80.500 y el G203 $37.500",
             "cliente: me gusta el G305", "bot: el G305 negro es inalambrico y sale $80.500"],
     "ah no, el otro, y ese me lo llevo", [p("comprar", "g203")]),
    ("C56", [], "tienen 50 off, no? entonces si el K120 negro sale menos de 10 mil llevo dos",
     [p("verificar|politica", "50", tema="promociones|descuento_transferencia"),
      p(PROD + "|cuenta", "k120", rubro="teclado"), p("comprar", "k120|dos", dep=True)]),
    ("C57", [], "cual es la capital de Francia?", [p("charla|explicar", "francia|capital")]),
    ("C58", [], "jaja buenisimo gracias crack, che y el G305 tiene garantia?",
     [p(PROD + "|politica", "g305", "garant")]),
    # ── JERGA: la traduccion pura ──
    ("J01", [], "necesito un aparato rectangular con teclas y dada la crisis dame uno acorde",
     [p("buscar", "tecl", rubro="teclado", cond="barat|econom|precio")]),
    ("J02", [], "algo para escuchar musica sin cables en el colectivo",
     [p("buscar", "auric|inalambr|bluetooth", rubro="auriculares")]),
    ("J03", [], "una compu portatil para la facu que no sea un fierro",
     [p("buscar", "notebook|portatil", rubro="notebook")]),
    ("J04", [], "la pantalla para la pc, algo grandecito", [p("buscar", "monitor|pantalla", rubro="monitor")]),
    ("J05", [], "un disco externo de 2 teras", [p("buscar", "2", rubro="almacenamiento externo")]),
    ("J06", [], "algo para hacer videollamadas con buena imagen", [p("buscar", "camara|webcam", rubro="webcam")]),
    ("J07", [], "el bicho ese para que ande el wifi en toda la casa", [p("buscar", "router|wifi", rubro="router")]),
    ("J08", [], "una silla para viciar horas sin que me duela la espalda", [p("buscar", "silla", rubro="silla gamer")]),
    ("J09", [], "la placa para meterle a la pc y jugar al fifa", [p("buscar", "placa|video|gpu", rubro="placa de video")]),
    ("J10", [], "si lo compro y viene fallado que hago?", [p("politica", "fall|defect|garant", tema="defectuoso|garantia|garantia_como_usar|devoluciones|cambios")]),
]


# ══ EL INDICE DE LA FUENTE: lo que traduce el codigo en A ═════════════════

def _tokens(t):
    return {w for w in re.findall(r"[a-z0-9]+", _n(t)) if len(w) > 2}


INDICE_RUBROS = {}
for pr in PRODUCTOS:
    INDICE_RUBROS.setdefault(pr["categoria"], set()).update(_tokens(pr["categoria"] + " " + pr["tags"]))
INDICE_TEMAS = {f["tema"]: _tokens(f["tema"].replace("_", " ") + " " + " ".join(f.get("keywords") or []))
                for f in FAQ}


def candidatos(texto, indice, n=3):
    q = _tokens(texto)
    q |= {w[:5] for w in q if len(w) > 5}
    puntos = []
    for clave, bolsa in indice.items():
        raices = bolsa | {w[:5] for w in bolsa if len(w) > 5}
        s = len(q & raices)
        if s:
            puntos.append((s, clave))
    return [c for _, c in sorted(puntos, key=lambda x: (-x[0], x[1]))[:n]]


# ══ LOS PROMPTS ═════════════════════════════════════════════════════════════

BASE = f"""Sos el interprete de una tienda online de tecnologia de Argentina. NO le contestas al cliente: partis su ultimo mensaje en piezas para que el codigo las resuelva.
REGLAS:
1. Una pieza por cada cosa que pide, pregunta o afirma; y una por producto o por destino si pide lo mismo de varios. El saludo y el agradecimiento no son piezas, salvo que sea todo el mensaje.
2. tipo es uno de: {", ".join(TIPOS)}. verificar es cuando el cliente da algo por cierto. repreguntar es cuando falta un dato del cliente o no se sabe a que se refiere.
3. texto: lo que dijo el cliente, copiado.
4. pregunta: la pieza escrita como una pregunta clara para el codigo, con las referencias resueltas: "ese", "el otro", "el primero", "todo" se reemplazan por el producto de la charla.
5. condiciones: lo que pide que cumpla, traducido: "acorde a la crisis" es barato, "sin cables" es inalambrico.
6. depende_de: los numeros de las piezas cuyo resultado hace falta para saber si esta se hace.
7. Nunca inventes un dato de la tienda: sin precios, sin stock."""

A_SALIDA = """8. rubro: el tipo de producto en palabras comunes (teclado, mouse, auriculares), si la pieza es de un producto. tema: de que asunto de la tienda pregunta en palabras comunes (factura, envio, garantia), si es una politica.
Devolve SOLO JSON: {"piezas": [{"n": 1, "tipo": "...", "texto": "...", "pregunta": "...", "rubro": "...", "tema": "...", "condiciones": ["..."], "depende_de": []}]}"""

B_TABLERO = f"""8. rubro: EXACTAMENTE uno de estos rubros de la tienda, si la pieza es de un producto: {", ".join(RUBROS)}.
9. tema: EXACTAMENTE uno de estos temas de la casa, si es una politica: {", ".join(TEMAS)}.
10. condiciones: escritas como "campo: valor" con estos campos: {", ".join(CAMPOS)}.
11. Equipos que conoce la tienda para compatibilidad: {", ".join(EQUIPOS)}.
Devolve SOLO JSON: {{"piezas": [{{"n": 1, "tipo": "...", "texto": "...", "pregunta": "...", "rubro": "...", "tema": "...", "condiciones": ["..."], "depende_de": []}}]}}"""

C_ELEGIR = """Te doy piezas de un mensaje de un cliente y, para cada una, los candidatos que encontro el buscador de la tienda: rubros y temas. Elegi para cada pieza el rubro y el tema que corresponden, SOLO de sus candidatos, o null si ninguno sirve.
Devolve SOLO JSON: {"piezas": [{"n": 1, "rubro": "..." o null, "tema": "..." o null}]}"""


def _mensaje(caso):
    _, ctx, msg, _ = caso
    charla = "\n".join(ctx) if ctx else "(sin charla previa)"
    return f"CHARLA PREVIA:\n{charla}\n\nULTIMO MENSAJE DEL CLIENTE: {msg}"


# ══ LA NOTA ═════════════════════════════════════════════════════════════════

def _txt(pz):
    return _n(" ".join(str(pz.get(k) or "") for k in ("texto", "pregunta", "rubro", "tema"))
              + " " + " ".join(map(str, pz.get("condiciones") or [])))


def _tiene(clave, t):
    return any(_n(o) in t for o in clave.split("|"))


def nota(caso, piezas, con_tipo=False):
    """Devuelve (partir_ok, traducir_ok o None, detalle). Partir mira el CONTENIDO
    —que nombra, a que apunta, de que depende—; con_tipo exige ademas la etiqueta."""
    esperadas = caso[3]
    libres = list(range(len(piezas)))
    fallas, trad_fallas, trad_total, pareo = [], [], 0, {}
    for i, e in enumerate(esperadas):
        hit = next((j for j in libres if (not con_tipo or str(piezas[j].get("tipo")) in e["tipos"])
                    and all(_tiene(c, _txt(piezas[j])) for c in e["claves"])), None)
        if hit is None:
            if not e["opc"]:
                fallas.append(f"falta {e['tipos'][0]}({','.join(e['claves'])})")
            continue
        libres.remove(hit)
        pareo[i] = hit
        pz = piezas[hit]
        if e["dep"] and not pz.get("depende_de"):
            fallas.append(f"{e['claves'][0]} sin dependencia")
        if e["rubro"]:
            trad_total += 1
            if _n(pz.get("rubro_final")) != _n(e["rubro"]):
                trad_fallas.append(f"rubro {pz.get('rubro_final')} por {e['rubro']}")
        if e["tema"]:
            trad_total += 1
            if _n(pz.get("tema_final")) not in [_n(x) for x in e["tema"]]:
                trad_fallas.append(f"tema {pz.get('tema_final')} por {e['tema'][0]}")
        if e["cond"] and not _tiene(e["cond"], _n(" ".join(map(str, pz.get("condiciones") or []))
                                                      + " " + str(pz.get("pregunta")))):
            trad_fallas.append(f"condicion sin {e['cond']}")
            trad_total += 1
    sobran = len(libres)
    partir = not fallas and sobran <= 1
    if sobran > 1:
        fallas.append(f"sobran {sobran}")
    trad = None if not trad_total else not trad_fallas
    return partir, trad, "; ".join(fallas + trad_fallas)


# ══ LA CORRIDA ══════════════════════════════════════════════════════════════

def _pedir(cli, modelo, sistema, usuario):
    from banco_pruebas.sonda_modelo import _llamar
    r = _llamar(cli, modelo, [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
                0.2, pausa=0)
    return r.choices[0].message.content or "", (r.usage.prompt_tokens if r.usage else 0)


def correr(forma, caso, cli, modelo):
    sistema = BASE + "\n" + (B_TABLERO if forma == "B" else A_SALIDA)
    texto, tok = _pedir(cli, modelo, sistema, _mensaje(caso))
    obj = _json(texto) or {}
    piezas = [x for x in (obj.get("piezas") or []) if isinstance(x, dict)]
    if forma == "B":
        for x in piezas:
            x["rubro_final"], x["tema_final"] = x.get("rubro"), x.get("tema")
    else:
        for x in piezas:  # el codigo ubica las palabras del modelo en el indice
            base = f"{x.get('rubro') or ''} {x.get('pregunta') or ''} {x.get('texto') or ''}"
            x["cand_rubros"] = candidatos(f"{x.get('rubro') or ''} " * 3 + base, INDICE_RUBROS) if x.get("rubro") else []
            x["cand_temas"] = candidatos(f"{x.get('tema') or ''} " * 3 + base, INDICE_TEMAS) if x.get("tema") else []
            x["rubro_final"] = (x["cand_rubros"] or [None])[0]
            x["tema_final"] = (x["cand_temas"] or [None])[0]
        if forma == "C" and any(x["cand_rubros"] or x["cand_temas"] for x in piezas):
            pedido = [{"n": x.get("n"), "pieza": x.get("pregunta"), "rubros_candidatos": x["cand_rubros"],
                       "temas_candidatos": x["cand_temas"]} for x in piezas]
            t2, tok2 = _pedir(cli, modelo, C_ELEGIR, json.dumps(pedido, ensure_ascii=False))
            tok += tok2
            elegidos = {str(e.get("n")): e for e in ((_json(t2) or {}).get("piezas") or []) if isinstance(e, dict)}
            for x in piezas:
                e = elegidos.get(str(x.get("n")), {})
                if x["cand_rubros"]:
                    x["rubro_final"] = e.get("rubro") if e.get("rubro") in x["cand_rubros"] else None
                if x["cand_temas"]:
                    x["tema_final"] = e.get("tema") if e.get("tema") in x["cand_temas"] else None
    partir, trad, det = nota(caso, piezas) if piezas else (False, False, "json roto")
    return {"partir": partir, "traducir": trad, "detalle": det, "tokens": tok, "piezas": piezas}


def informe():
    filas = [json.loads(x) for x in open(SALIDA, encoding="utf-8")]
    por_id = {c[0]: c for c in CASOS}
    for r in filas:  # se recalifica desde lo guardado
        if r["piezas"]:
            r["partir"], r["traducir"], r["detalle"] = nota(por_id[r["id"]], r["piezas"])
            r["con_tipo"] = nota(por_id[r["id"]], r["piezas"], con_tipo=True)[0]
        else:
            r["con_tipo"] = False
    print("\nDESMENUZAR · forma: contenido bien / con la etiqueta de tipo / traducir bien / tokens de entrada")
    for forma in "ABC":
        f = [r for r in filas if r["forma"] == forma]
        if not f:
            continue
        casos = {}
        for r in f:
            casos.setdefault(r["id"], []).append(r)
        part = sum(r["partir"] for r in f)
        tr = [r["traducir"] for r in f if r["traducir"] is not None]
        jerga = [r["traducir"] for r in f if r["id"].startswith("J") and r["traducir"] is not None]
        print(f"  {forma}: contenido {part}/{len(f)} · con tipo {sum(r['con_tipo'] for r in f)}/{len(f)}"
              f" · traducir {sum(tr)}/{len(tr)} · jerga {sum(jerga)}/{len(jerga)}"
              f" · {sum(r['tokens'] for r in f) // len(f)} tokens")
        malos = {cid: v for cid, v in casos.items() if not all(r["partir"] and r["traducir"] is not False for r in v)}
        for cid, v in sorted(malos.items()):
            dets = [r["detalle"] for r in v if r["detalle"]]
            print(f"     {cid} {sum(r['partir'] for r in v)}/{len(v)} partir, "
                  f"{sum(r['traducir'] is not False for r in v)}/{len(v)} traducir · {max(set(dets), key=dets.count)[:90]}")


def main():
    a = sys.argv[1:]

    def opt(nombre, defecto):
        if nombre in a:
            i = a.index(nombre)
            v = a[i + 1]
            del a[i:i + 2]
            return v
        return defecto
    formas, reps, hilos = opt("--formas", "A,B,C").split(","), int(opt("--reps", 5)), int(opt("--hilos", 8))
    if "--informe" in a:
        informe()
        return
    from banco_pruebas.sonda_modelo import _cliente
    cli, modelo = _cliente()
    nombre = modelo.replace(" (paga)", "")
    cola = [(f, c, r) for r in range(1, reps + 1) for f in formas for c in CASOS]
    print(f"{modelo} · {len(cola)} llamadas base · formas {formas} · reps {reps}")
    candado = threading.Lock()

    def uno(t):
        forma, caso, rep = t
        r = correr(forma, caso, cli, nombre)
        with candado, open(SALIDA, "a", encoding="utf-8") as f:
            f.write(json.dumps({"forma": forma, "id": caso[0], "rep": rep, **r}, ensure_ascii=False) + "\n")
    with ThreadPoolExecutor(hilos) as ex:
        for fut in [ex.submit(uno, t) for t in cola]:
            fut.result()
    informe()


if __name__ == "__main__":
    main()
