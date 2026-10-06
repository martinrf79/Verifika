"""CAMINO A CON NEXOS: indice fijo + nexos (frases genericas) + memoria como ESTADO escrito por el codigo.

El modelo no ve el catalogo ni la charla larga. Ve:
  INDICE   lo que la tienda tiene, como mapa: rubros con sinonimos, marcas por rubro, politicas.
  NEXOS    frases genericas del cliente y lo que significan en lineas.
  ESTADO   lo que el codigo sabe de la charla: filtros vivos, productos nombrados con id, ultimo listado,
           pedido vigente con destinos, presupuestos dados.
  y los dos ultimos intercambios literales.
Pide en lineas; el codigo resuelve, edita el pedido, suma; el modelo redacta.
"""
import json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import lineas as L
from lineas import n, plata, P, RUBROS, MARCAS
from necesita import llamar

FAMILIAS = {"perifericos": "mouse, teclado, auriculares, webcam, microfono, parlante",
            "componentes": "procesador, motherboard, memoria ram, placa de video, fuente, gabinete, cooler, ssd",
            "audio": "auriculares, parlante, microfono", "almacenamiento": "ssd, almacenamiento externo",
            "computadora / compu / laptop": "notebook", "pantalla": "monitor", "camara": "webcam",
            "disco / pendrive / disco externo": "almacenamiento externo", "silla": "silla gamer"}
NO_VENDE = {"celular / telefono / smartphone": "tablet", "smartwatch / reloj": "nada parecido",
            "consola / playstation / xbox": "nada parecido", "televisor / tv": "monitor"}


def indice():
    marcas = {}
    for p in P:
        marcas.setdefault(p["categoria"], set()).add(p["marca"])
    r = ["RUBROS QUE VENDE LA TIENDA, con sus marcas:"]
    r += [f"- {c}: {', '.join(sorted(m))}" for c, m in sorted(marcas.items())]
    r.append("PALABRAS DEL CLIENTE QUE NO SON UN RUBRO: " + "; ".join(f"{k} = {v}" for k, v in FAMILIAS.items()))
    r.append("NO SE VENDE, y lo mas parecido que si: " + "; ".join(f"{k} -> {v}" for k, v in NO_VENDE.items()))
    import json as _j
    temas = [t["tema"] for t in _j.load(open(L.C + "faq.json"))]
    r.append("POLITICAS (temas): " + ", ".join(temas))
    r.append("DATOS DE CADA PRODUCTO que se pueden pedir o filtrar: precio, stock, marca, color, conexion (inalambrico o "
             "cable), peso, origen de la marca y pais de fabricacion")
    return "\n".join(r)


NEXOS = """NEXOS: lo que dice el cliente y como se pide.
- "lo mas barato", "economico", "por la crisis", "que no sea caro", "ajustado" -> criterio: mas barato
- "lo mejor", "buena calidad", "confio en vos", "premium" -> criterio: buena calidad
- "el mas caro / el mas barato que vendes / de la tienda" -> buscar en: toda la tienda
- "los N mas baratos de X" -> buscar X, N articulos, mas barato. "dos mouse" sin criterio -> buscar mouse 2
- "anotalo", "sumame", "me lo llevo", "quiero N de esos" -> agregar al pedido
- "sacalo", "ese no", "dejame solo X" -> sacar del pedido lo que no queda
- "mejor N", "que sean N" -> cambiar cantidad. "mandalo a X", "el de A mandalo a B" -> cambiar destino
- "cambialo por el de 2tb", "que sea blanco" -> cambiar <id P> variante 2tb / variante blanco (el codigo busca la variante)
- "dame el X", "quiero X" cuando el cliente esta armando un pedido -> agregar
- "va a X", "uno a A y otro a B", "lo demas a C", "los que faltan" -> agregar con destino; "lo demas" es lo pedido que
  todavia no tiene destino: calculalo vos y escribilo concreto. Las cantidades por destino tienen que sumar lo pedido.
- "ese", "ese mismo" -> el ultimo producto nombrado. "el otro" -> del ultimo listado o comparacion, el que NO eligio.
  "el primero", "el segundo" -> por posicion en el ULTIMO LISTADO. Siempre escribi el id P concreto.
- "que no sea X", "sin X" -> condicion en la busqueda; el codigo la guarda como FILTRO VIVO y la aplica a las busquedas
  siguientes, de cualquier rubro, hasta que el cliente la cambie ("ya no importa la marca" -> olvidar).
- "algo parecido" a algo que no se vende -> buscar el rubro mas parecido que si se vende (ver NO SE VENDE)
- "si pasa X, hace Y", "si hay, dame tal", "dame el que cumpla X" -> pedi lo necesario para saber X y agrega una linea
  decidir; el sistema te devuelve los datos y ahi escribis las lineas finales.
- "cuanto sale el envio a X", "cuanto sale cada envio" -> envio, una linea por destino
- "anda con", "le sirve a", "entra en", "es compatible con", "sirve para mi" -> compatibilidad <producto> | <equipo del cliente>
- "el de Posadas", "lo de Rosario" -> en cambiar, escribi "destino Posadas" en lugar del id: se mueve todo lo de ese destino
- "cuanto es todo", "total", "recalculame", "item por item" -> cuenta. "pago 70 transferencia 30 mercado pago" -> pago
- "me habias dicho otro precio" -> mira PRESUPUESTOS DADOS en el ESTADO y pedi la cuenta para comparar
- "lo menos chino", "que no sea chino", "fabricado en", "de que pais" -> condicion: origen no chino (el codigo dice lo que
  figura de origen; casi todo se fabrica en Asia)
- "el precio no importa", "no importa el precio" -> criterio nada: NO es "buena calidad" ni "mas caro"
- "si llevo varios me haces precio", "descuento por cantidad", "precio mayorista", "mejorame el precio" -> politica mayoristas
  y politica promociones; nunca inventes una rebaja
- "quiero hablar con alguien", "una persona", "no me entendes" dos veces -> humano
- un dato del cliente que falta y no se puede deducir -> preguntar"""

PIDE = """Sos el traductor de una tienda online de tecnologia de Argentina. No le contestas al cliente: escribis lineas de pedido que el codigo resuelve. Usa el INDICE, los NEXOS y el ESTADO de la charla.
Formas, una por linea, casillas separadas por |:
D<n> | buscar | <rubro exacto o "toda la tienda"> | <cuantos articulos> | <mas barato | mas caro | mas liviano | buena calidad | nada> | <condiciones: marca, color, conexion, que no sea tal marca, o nada>
D<n> | producto | <id P del ESTADO, o el nombre del producto con color>
D<n> | rubros
D<n> | politica | <tema de POLITICAS>
D<n> | agregar | <id P, o D<k> para lo que devuelva esa linea> | <cantidad> | <destino o nada>
D<n> | sacar | <id P>
D<n> | cambiar | <id P> | cantidad <N>   o   destino <lugar>   o   variante <color o capacidad>   o   por <id P o D<k>>
D<n> | olvidar | <filtro vivo que el cliente levanto>
D<n> | cuenta
D<n> | pago | <medio porcentaje, medio porcentaje>
D<n> | decidir | <que hay que decidir con los datos: la condicion del cliente>
D<n> | preguntar | <lo que falta y no se puede deducir>
D<n> | humano                     (el cliente pide una persona, o la charla no se puede resolver)
D<n> | nada
D<n> | envio | <destino>            (cuanto cuesta mandar a ese destino)
D<n> | compatibilidad | <id P o nombre del producto> | <el equipo o producto del cliente: notebook, mac, ps5, la placa P2...>
Reglas: D<k> es el PRIMER articulo que devuelva esa linea; D<k>.2 el segundo, D<k>.3 el tercero. Si el cliente quiere dos articulos distintos de una busqueda, agrega D1 y D1.2; si quiere 2 unidades del mismo, agrega D1 con cantidad 2. Un producto que el cliente nombra (G203, K380 negro) se pide con producto, no con buscar. Usa los id P del ESTADO para todo lo ya nombrado. No escribas precios. Solo las lineas."""

REDACTA = ("Sos el vendedor de una tienda online de tecnologia de Argentina. Hablas en espanol argentino, con voseo, claro "
           "y sin repetir. Te paso los DATOS que el sistema consulto para el ultimo mensaje del cliente y el final de la "
           "charla. Contesta usando SOLO esos datos y contesta todo lo que pregunto. No sumes ni calcules: los totales "
           "vienen hechos, copialos con su detalle. Si un dato dice NO SE PUDO, NO_EXISTE, AMBIGUO, FALTA o CONFIRMAR, "
           "decilo con naturalidad y pregunta solo eso. Los DATOS son lo vigente: si contradicen algo que el vendedor dijo "
           "antes, mandan los DATOS y corregilo. No nombres ids ni lineas. Pedi el nombre solo si el cliente dijo que compra.")


_CAMPOS_FICHA = ("conexion", "bluetooth", "ram", "procesador", "almacenamiento", "memoria_video", "potencia", "hz",
                 "resolucion", "panel", "bateria", "camara", "wifi", "formato")


def politica3(c):
    q = set(re.findall(r"[a-z]+", n(" ".join(c)))) - {"de", "la", "el", "los", "las", "y", "por", "con", "a"}
    puntos = []
    for t in L.FAQ:
        kw = set(re.findall(r"[a-z]+", n(" ".join(t["keywords"]) + " " + t["tema"].replace("_", " "))))
        sc = len(q & kw)
        if sc:
            puntos.append((sc, t))
    puntos.sort(key=lambda x: -x[0])
    if not puntos:
        return {"no_se_pudo": f"no hay una politica escrita sobre '{' '.join(c)}'"}
    top = puntos[0][0]
    return {"politicas": [f"{t['tema']}: {t['respuesta']}" for sc, t in puntos if sc * 2 >= top][:3]}


def ficha(p, corta=False):
    s = L.SPECS.get((p["marca"], p["modelo"])) or {}
    datos = [f"{k} {s[k]}" for k in _CAMPOS_FICHA if s.get(k)]
    if corta:
        return "; ".join(datos[:3])
    colores = [f"{q['color']} ({'stock ' + str(q['stock']) if q['stock'] > 0 else 'sin stock'})" for q in P
               if q["marca"] == p["marca"] and q["modelo"] == p["modelo"] and q["color"]]
    extra = ["colores: " + ", ".join(colores) if len(colores) > 1 else "",
             f"garantia {p['garantia_meses']} meses" if p.get("garantia_meses") else "",
             p.get("caracteristicas_extra") or "", f"uso {p['uso_recomendado']}" if p.get("uso_recomendado") else "",
             p.get("origen") or "", (p.get("descripcion") or "")[:160]]
    return "; ".join(x for x in datos + extra if x)


def filtro_numeros(cond, filas_base):
    """'64 gb', 'ddr5', '1tb', '550w': las palabras con numeros filtran por nombre, descripcion y ficha."""
    t = re.sub(r"(\d+)\s+(gb|tb|w|hz|mhz)\b", r"\1\2", n(cond))
    toks = [w for w in re.findall(r"[a-z0-9]+", t) if re.search(r"\d", w) and re.search(r"[a-z]", w)]
    if not toks:
        return None, []
    def texto_de(p):
        sp = L.SPECS.get((p["marca"], p["modelo"])) or {}
        return re.sub(r"(\d+)\s+(gb|tb|w|hz|mhz)\b", r"\1\2", n(p["nombre"] + " " + p["descripcion"] + " " + " ".join(sp.values())))
    return [p for p in filas_base if all(w in texto_de(p) for w in toks)], toks


class Sesion:
    def __init__(self):
        self.prods = {}       # id P -> producto
        self.por_nombre = {}  # nombre -> id P
        self.ultimo = []      # ids del ultimo listado
        self.filtros = []     # marcas excluidas vivas
        self.pedido = []      # [{"p": id, "q": int, "destino": str}]
        self.presupuestos = []
        self.chat = []        # [(cliente, vendedor)]
        self.turno = 0

    def pid(self, p):
        if p["nombre"] not in self.por_nombre:
            k = f"P{len(self.prods) + 1}"
            self.prods[k] = p
            self.por_nombre[p["nombre"]] = k
        return self.por_nombre[p["nombre"]]

    def estado(self):
        r = ["ESTADO DE LA CHARLA (lo escribe el sistema):"]
        r.append("FILTROS VIVOS: " + (", ".join("que no sea " + m for m in self.filtros) or "ninguno"))
        if self.prods:
            r.append("PRODUCTOS NOMBRADOS EN LA CHARLA:")
            for k, p in list(self.prods.items())[-25:]:
                r.append(f"  {k} {p['nombre']} {plata(p['precio'])}")
        if self.ultimo:
            r.append("ULTIMO LISTADO, en orden: " + ", ".join(f"{i}. {k}" for i, k in enumerate(self.ultimo, 1)))
        if self.pedido:
            r.append("PEDIDO VIGENTE:")
            for it in self.pedido:
                r.append(f"  {it['p']} {self.prods[it['p']]['nombre']} x{it['q']} -> {it['destino'] or 'sin destino'}")
        else:
            r.append("PEDIDO VIGENTE: vacio")
        if self.presupuestos:
            r.append("PRESUPUESTOS DADOS: " + " | ".join(self.presupuestos[-3:]))
        return "\n".join(r)

    def ultimos(self):
        out = []
        for c, v in self.chat[-2:]:
            out += [f"CLIENTE: {c}", f"VENDEDOR: {v[:900]}"]
        return "\n".join(out)

    # ── resolver lineas ──
    def id_con_variante(self, x):
        """'P2 blanco', 'P1 en negro': el producto del ESTADO en ese color o capacidad. Sin variante, el mismo."""
        m = re.fullmatch(r"(P\d+)\s*(?:,|en|de)?\s*(.*)", (x or "").strip())
        if not m or m.group(1) not in self.prods:
            return None
        p = self.prods[m.group(1)]
        resto = n(m.group(2))
        if not resto or n(p["color"]) in resto:
            return p
        return self.variante(p, resto) or p

    def ref(self, x, hechos, usados):
        x = x.strip()
        if re.match(r"P\d+\b", x):
            return self.id_con_variante(x)
        m = re.fullmatch(r"(D\d+)(?:\.(\d+))?", x)
        if m:
            filas = (hechos.get(m.group(1)) or {}).get("filas") or []
            if not filas or (hechos.get(m.group(1)) or {}).get("ambiguo"):
                return None
            i = int(m.group(2) or 1) - 1
            return filas[i] if i < len(filas) else None
        h = L.producto([x])
        return (h.get("filas") or [None])[0] if not h.get("ambiguo") and not h.get("no_existe") else None

    @staticmethod
    def renumerar(lineas):
        mapa, out = {}, []
        for i, l in enumerate(lineas, 1):
            c = [re.sub(r"\b(D\d+)\b", lambda m: mapa.get(m.group(1), m.group(1)), x) for x in l["c"]]
            nuevo = f"D{i}"
            if l["tipo"] in ("buscar", "producto") or l["id"] not in mapa:  # una referencia apunta a datos
                mapa[l["id"]] = nuevo
            out.append({"id": nuevo, "tipo": l["tipo"], "c": c})
        return out

    def variante(self, p, texto):
        """El mismo modelo en otro color o capacidad: 'blanco', 'de 2tb'."""
        t = n(texto)
        base = set(re.findall(r"[a-z]+", n(p["modelo"])))
        cands = [q for q in P if q["categoria"] == p["categoria"] and q["marca"] == p["marca"] and q is not p
                 and base & set(re.findall(r"[a-z]+", n(q["modelo"])))]
        pal = [w for w in re.findall(r"[a-z0-9]+", t) if w not in ("variante", "que", "sea", "el", "la", "de", "por", "en")]
        mismo = [q for q in cands if q["modelo"] == p["modelo"]]  # el mismo modelo en otro color va primero
        mejor = sorted(cands, key=lambda q: (-sum(w in n(q["nombre"]) for w in pal), q not in mismo))
        if mejor and sum(w in n(mejor[0]["nombre"]) for w in pal) > 0:
            return mejor[0]
        return None

    @staticmethod
    def identificar(texto, rubro=None):
        """El producto que nombra el texto: todas sus palabras de modelo estan, y gana el que tiene menos de mas."""
        q = set(re.findall(r"[a-z0-9]+", n(texto)))
        cands = []
        for p in P:
            if rubro and p["categoria"] != rubro:
                continue
            mod = set(re.findall(r"[a-z0-9]+", n(p["modelo"])))
            dig = {w for w in mod if re.search(r"\d", w)}
            alfa = mod - dig
            ok = (dig and dig <= q | {"gb", "tb"} and len(alfa & q) >= len(alfa) // 2) or (not dig and alfa and alfa <= q)
            if ok:
                extra = len(set(re.findall(r"[a-z0-9]+", n(p["nombre"]))) - q)
                cands.append((extra, -len(mod), p))
        if not cands:
            return None
        cands.sort(key=lambda x: (x[0], x[1]))
        mejor = cands[0][2]
        # si el color no se dijo, cualquier color del mismo modelo; se prefiere con stock
        mismos = [p for e, _, p in cands if p["marca"] == mejor["marca"] and p["modelo"] == mejor["modelo"]]
        con_color = [p for p in mismos if n(p["color"]) and n(p["color"]) in n(texto)]
        elegidos = con_color or sorted(mismos, key=lambda p: -p["stock"])
        return elegidos[0]

    def buscar_con_modelo(self, c):
        """Si las condiciones nombran un modelo (Stinger 2, K380, 980 1TB), es ese producto."""
        rub = L.rubro_en(c[0]) if c else None
        p = self.identificar(" ".join(c[2:4]) if len(c) > 3 else "", rub) if len(c) > 3 else None
        if p:
            return {"filas": [p]}
        h = L.buscar(c)
        cond = n(c[3] if len(c) > 3 else "")
        rub = h.get("alcance") if h.get("alcance") != "toda la tienda" else None
        if rub or L.rubro_en(c[0] if c else ""):
            rub = rub or L.rubro_en(c[0])
            base = [p for p in P if p["categoria"] == rub and p["stock"] > 0]
            filtradas, toks = filtro_numeros(cond, base)
            if toks:
                if not filtradas:
                    return {"no_existe": f"no hay {rub} con {' '.join(toks)} con stock"}
                campo, signo, _ = L.criterio(c[2] if len(c) > 2 else "")
                if campo:
                    filtradas = sorted(filtradas, key=lambda p: signo * p[campo])
                cant = int(re.sub(r"\D", "", c[1]) or 1) if len(c) > 1 else 1
                return {"filas": filtradas[:max(cant, 6) if not campo else cant], "filtros": ["con " + " ".join(toks)]}
        if re.search(r"[a-z]*\d+[a-z0-9]*", cond) or len(cond.split()) >= 2:
            pr = L.producto([f"{c[0]} {cond}"])
            if pr.get("filas") and not pr.get("ambiguo") and not pr.get("no_existe"):
                mod = set(re.findall(r"[a-z0-9]+", n(pr["filas"][0]["modelo"])))
                if mod and len(mod & set(re.findall(r"[a-z0-9]+", cond))) >= max(1, len(mod) - 1):
                    return {"filas": pr["filas"][:1], "aviso": pr.get("aviso")}
        return h

    def resolver(self, lineas):
        hechos, usados, avisos = {}, {}, []
        listado = []
        for l in lineas:
            t, c = l["tipo"], l["c"]
            if t == "buscar":
                c = c + [""] * (4 - len(c))
                cond = c[3]
                h = self.buscar_con_modelo(c)
                nuevas = [m for m in MARCAS if re.search(r"(no sea|sin|excepto|ni)\s+(?:\w+\s+){0,3}?" + n(m) + r"\b", n(cond))]
                for m in nuevas:
                    if m not in self.filtros:
                        self.filtros.append(m)
                vivos = [m for m in self.filtros if m not in nuevas and not re.search(n(m), n(cond))]
                if vivos and h.get("filas") is not None:  # el filtro vivo lo aplica el codigo
                    c2 = list(c)
                    c2[3] = (cond + " que no sea " + " ni ".join(self.filtros)).strip()
                    h = L.buscar(c2)
                    h.setdefault("filtros", []).append("se mantuvo lo que pidio antes: que no sea " + ", ".join(self.filtros))
                hechos[l["id"]] = h
            elif t == "producto":
                x = (c[0] if c else "").strip()
                if self.id_con_variante(x):
                    hechos[l["id"]] = {"filas": [self.id_con_variante(x)], "ficha": True}
                else:
                    p = self.identificar(x)
                    hechos[l["id"]] = dict({"filas": [p]} if p else L.producto(c), ficha=True)
            elif t == "rubros":
                hechos[l["id"]] = {"rubros": RUBROS}
            elif t == "politica":
                hechos[l["id"]] = politica3(c)
            elif t == "olvidar":
                antes = list(self.filtros)
                self.filtros = [m for m in self.filtros if n(m) not in n(" ".join(c))] if c and c[0] else []
                if self.filtros == antes and any(w in n(" ".join(c)) for w in ("marca", "todo", "filtro")):
                    self.filtros = []
                hechos[l["id"]] = {"aviso": "filtros levantados: " + ", ".join(m for m in antes if m not in self.filtros)}
            elif t == "preguntar":
                hechos[l["id"]] = {"preguntar": " ".join(c)}
            elif t == "humano":
                hechos[l["id"]] = dict(L.politica(["contacto humano persona vendedor"]),
                                       aviso="PASAR A UNA PERSONA: deci que un vendedor de la tienda sigue la charla")
                self.humano = True
            elif t == "compatibilidad":
                p = self.ref(c[0] if c else "", hechos, usados)
                from app.core import agente as A
                from app.core.contexto_turno import get_current_tienda
                hechos[l["id"]] = {"aviso": "compatibilidad: " + json.dumps(A.h_compatibilidad(
                    get_current_tienda() or "verifika_prod", producto=(p or {}).get("nombre") or (c[0] if c else ""),
                    con=c[1] if len(c) > 1 else ""), ensure_ascii=False, default=str)}
            elif t == "envio":
                tarifa = L.costo_envio(c[0] if c else "")
                hechos[l["id"]] = ({"aviso": f"envio a {c[0]}: {plata(tarifa)}; gratis si lo de ese envio supera $250.000; "
                                    "plazo 4 a 7 dias habiles"} if tarifa is not None
                                   else {"no_se_pudo": f"no se reconoce el destino '{c[0] if c else ''}'"})
            for f in (hechos.get(l["id"]) or {}).get("filas") or []:
                listado.append(self.pid(f))
        # operaciones sobre el pedido, en orden
        for l in lineas:
            t, c = l["tipo"], l["c"] + ["", "", ""]
            if t == "agregar":
                p = self.ref(c[0], hechos, usados)
                if not p:
                    avisos.append(f"NO SE PUDO agregar '{c[0]}': no se sabe que producto es")
                    continue
                q = int(re.sub(r"\D", "", c[1]) or 1)
                dest = "" if n(c[2]) in ("", "nada", "-") else c[2]
                k = self.pid(p)
                igual = next((it for it in self.pedido if it["p"] == k and it["destino"] == dest), None)
                if igual:
                    igual["q"] += q
                else:
                    self.pedido.append({"p": k, "q": q, "destino": dest})
            elif t == "sacar":
                p = self.ref(c[0], hechos, usados)
                k = self.por_nombre.get(p["nombre"]) if p else None
                if k:
                    self.pedido = [it for it in self.pedido if it["p"] != k]
                else:
                    avisos.append(f"NO SE PUDO sacar '{c[0]}'")
            elif t == "cambiar":
                p = self.ref(c[0], hechos, usados)
                k = self.por_nombre.get(p["nombre"]) if p else None
                arg = " ".join(c[1:]).strip()
                if not arg and n(c[0]).startswith("destino "):  # "cambiar | destino Cordoba": todo va ahi
                    arg, c[0], p, k = c[0], "todo", None, None
                its = [it for it in self.pedido if it["p"] == k] if k else []
                viejo = re.sub(r"^destino\s+", "", n(c[0]))
                if n(arg).startswith("destino"):
                    nuevo_dest = n(arg.split(None, 1)[1]) if len(arg.split(None, 1)) > 1 else ""
                    # el destino viejo nombrado en el mensaje o en la linea: se mueve solo lo de ahi
                    viejos = {n(it["destino"]) for it in self.pedido if it["destino"] and n(it["destino"]) != nuevo_dest
                              and (n(it["destino"]) in n(self.mensaje) or n(it["destino"]) == viejo)}
                    if viejos:
                        base = its or self.pedido
                        its = [it for it in base if n(it["destino"]) in viejos] or \
                              [it for it in self.pedido if n(it["destino"]) in viejos]
                if not its:
                    # "el de Posadas": cambiar por destino
                    its = [it for it in self.pedido if viejo and viejo in n(it["destino"])]
                if not its and n(arg).startswith("destino"):
                    its = [it for it in self.pedido if not it["destino"]] or (self.pedido if len(
                        {it["destino"] for it in self.pedido}) == 1 else [])
                if not its:
                    avisos.append(f"NO SE PUDO cambiar '{c[0]}': no esta en el pedido")
                    continue
                m = re.match(r"cantidad\s+(\d+)", n(arg))
                if m:
                    its[0]["q"] = int(m.group(1))
                    for it in its[1:]:
                        self.pedido.remove(it)
                elif n(arg).startswith("destino"):
                    for it in its:
                        it["destino"] = arg.split(None, 1)[1] if len(arg.split(None, 1)) > 1 else ""
                elif n(arg).startswith("variante"):
                    for it in its:
                        v = self.variante(self.prods[it["p"]], arg)
                        if v:
                            it["p"] = self.pid(v)
                        else:
                            avisos.append(f"NO SE PUDO: no hay {self.prods[it['p']]['nombre']} en la variante '{arg}'")
                elif n(arg).startswith("por"):
                    nuevo = self.ref(arg.split(None, 1)[1] if len(arg.split(None, 1)) > 1 else "", hechos, usados)
                    if nuevo:
                        for it in its:
                            it["p"] = self.pid(nuevo)
                    else:
                        avisos.append(f"NO SE PUDO cambiar por '{arg}'")
        compra = re.search(r"\b(dame|me llevo|quiero|sumame|agregame|anotame|anotalo|sumalo|agregalo)\b(?! (el |la )?(precio|info|dato))",
                           n(self.mensaje))
        if compra and not any(l["tipo"] in ("agregar", "sacar", "cambiar", "preguntar") for l in lineas):
            prods = [l for l in lineas if l["tipo"] == "producto" and (hechos.get(l["id"]) or {}).get("filas")
                     and not hechos[l["id"]].get("ambiguo")]
            if len(prods) == 1 and self.pedido is not None and (self.pedido or self.turno > 1):
                p = hechos[prods[0]["id"]]["filas"][0]
                self.pedido.append({"p": self.pid(p), "q": 1, "destino": ""})
                lineas.append({"id": "DY", "tipo": "agregar", "c": [prods[0]["id"], "1", ""]})
        # D. "el envio va a X": lo que no tiene destino va ahi
        envios = [l["c"][0] for l in lineas if l["tipo"] == "envio" and l["c"]]
        sin = [it for it in self.pedido if not it["destino"]]
        if len(envios) == 1 and sin and not any(it["destino"] for it in self.pedido) \
                and re.search(r"\b(va|van|mandalo|mandalos|mandamelo|envio|envialo|a)\b", n(self.mensaje)) \
                and L.costo_envio(envios[0]) is not None:
            for it in sin:
                it["destino"] = envios[0]
            lineas.append({"id": "DZ", "tipo": "cambiar", "c": ["todo", "destino " + envios[0]]})
        if listado:
            self.ultimo = list(dict.fromkeys(listado))
        cambio = any(l["tipo"] in ("agregar", "sacar", "cambiar") for l in lineas)
        if cambio and not any(l["tipo"] == "cuenta" for l in lineas):
            lineas.append({"id": "DX", "tipo": "cuenta", "c": []})
        for l in lineas:
            if l["tipo"] == "cuenta":
                hechos[l["id"]] = self.cuenta()
            if l["tipo"] == "pago":
                hechos[l["id"]] = self.pago(" ".join(l["c"]))
        return hechos, avisos

    def cuenta(self):
        if not self.pedido:
            return {"no_se_pudo": "el pedido esta vacio: no hay nada que sumar"}
        bloques = {}
        for it in self.pedido:
            bloques.setdefault(it["destino"], []).append(it)
        out, total = [], 0
        for dest, its in bloques.items():
            sub = sum(self.prods[i["p"]]["precio"] * i["q"] for i in its)
            env, txt_env = 0, ""
            if dest:
                tarifa = L.costo_envio(dest)
                if tarifa is None:
                    txt_env = f"envio a '{dest}': NO SE PUDO, destino no reconocido"
                else:
                    env = 0 if sub > 250000 else tarifa
                    txt_env = f"envio a {dest} {plata(env)}" + (" (gratis, supera $250.000)" if env == 0 else "")
            renglones = [f"{i['q']}x {self.prods[i['p']]['nombre']} {plata(self.prods[i['p']]['precio'])} c/u = "
                         f"{plata(self.prods[i['p']]['precio'] * i['q'])}" for i in its]
            out.append({"destino": dest or "sin destino", "renglones": renglones, "subtotal": sub, "envio": txt_env,
                        "total": sub + env})
            total += sub + env
        self.total = total
        self.presupuestos.append(f"turno {self.turno}: total {plata(total)}")
        return {"bloques": out, "total_general": total}

    def pago(self, txt):
        tot = getattr(self, "total", None)
        if tot is None:
            c = self.cuenta()
            if "total_general" not in c:
                return c
            tot = c["total_general"]
        partes = []
        pares = re.findall(r"([a-zA-Z ]+?)\s*(\d+)\s*%?", txt)
        if not pares or not any(m.strip() for m, _ in pares):
            medios = re.findall(r"transferencia|mercado ?pago|tarjeta|efectivo", n(self.mensaje))
            pcts = re.findall(r"(\d+)\s*(?:%|por ?ciento)", n(txt) + " " + n(self.mensaje))
            pares = list(zip(medios, pcts))
        if not pares:  # "70, 30" sin medio: el reparto del presupuesto, sin descuento
            pares = [(f"parte {i}", x) for i, x in enumerate(re.findall(r"\d+", txt), 1)]
        for medio, pct in pares:
            monto = round(tot * int(pct) / 100)
            s = f"{medio.strip()} {pct}%: {plata(monto)}"
            if "transfer" in n(medio):
                s += f" (con el 10% de descuento por transferencia: {plata(round(monto * 0.9))})"
            partes.append(s)
        return {"reparto": partes, "sobre": plata(tot)}

    def texto(self, lineas, hechos, avisos):
        out = []
        for l in lineas:
            h = hechos.get(l["id"])
            if not h:
                continue
            cab = f"{l['tipo']} {' | '.join(l['c'])}:"
            if "bloques" in h:
                r = ["CUENTA DEL PEDIDO VIGENTE:"]
                for b in h["bloques"]:
                    r.append(f"  {b['destino'].upper()}:")
                    r += ["    " + x for x in b["renglones"]]
                    r.append(f"    subtotal {plata(b['subtotal'])}" + (f"; {b['envio']}" if b["envio"] else "")
                             + f"; total {plata(b['total'])}")
                r.append(f"  TOTAL GENERAL {plata(h['total_general'])}. Pagando por transferencia, 10% de descuento.")
                out.append("\n".join(r))
            elif "reparto" in h:
                out.append(f"REPARTO DEL PAGO sobre {h['sobre']}: " + "; ".join(h["reparto"]))
            else:
                r = [cab]
                for k in ("no_existe", "ambiguo", "no_se_pudo", "aviso", "preguntar"):
                    if h.get(k):
                        r.append(f"  {k.upper()}: {h[k]}")
                if h.get("filtros"):
                    r.append("  filtros: " + "; ".join(h["filtros"]))
                for p in h.get("filas", []):
                    f = ficha(p, corta=not h.get("ficha"))
                    r.append(f"  - {p['nombre']} — {plata(p['precio'])} — stock {p['stock']}" + (f" — {f}" if f else ""))
                if h.get("rubros"):
                    r.append("  rubros: " + ", ".join(h["rubros"]))
                for x in h.get("politicas", []):
                    r.append("  " + x)
                out.append("\n".join(r))
        out += avisos
        return "\n\n".join(out)

    def turno_de(self, m, mensaje):
        self.mensaje = mensaje
        self.turno += 1
        base = [{"role": "system", "content": PIDE + "\n\n" + INDICE + "\n\n" + NEXOS},
                {"role": "user", "content": self.estado() + "\n\nULTIMOS MENSAJES:\n" + (self.ultimos() or "(ninguno)")
                 + f"\n\nMENSAJE DEL CLIENTE: {mensaje}"}]
        crudo = llamar(m, base, temp=0.0)
        lineas, malas = L.parsear(crudo)
        lineas = self.renumerar(lineas)
        foto = json.dumps([self.pedido, self.filtros, self.ultimo])
        hechos, avisos = self.resolver(lineas)
        rondas = 1
        # LA RED: lo agregado este turno contra los numeros del mensaje
        problema = self.red(mensaje, lineas)
        decidir = [l for l in lineas if l["tipo"] == "decidir"]
        if problema or decidir or malas:
            pedido_extra = []
            if problema:
                pedido_extra.append("El sistema encontro esto: " + problema)
            if malas:
                pedido_extra.append("Estas lineas no tienen la forma pedida: " + " / ".join(malas))
            if decidir:
                pedido_extra.append("Estos son los datos que pediste para decidir:\n" + self.texto(lineas, hechos, avisos))
            primera = (lineas, hechos)
            if problema or malas:  # error de reparto: se reescribe todo desde antes del turno
                self.pedido, self.filtros, self.ultimo = json.loads(foto)
            else:  # decidir: la segunda vuelta continua lo de la primera
                pedido_extra.append("ESTADO DESPUES DE TUS LINEAS:\n" + self.estado())
            crudo2 = llamar(m, base + [{"role": "assistant", "content": crudo},
                                       {"role": "user", "content": "\n".join(pedido_extra)
                                        + ("\nEscribi de nuevo TODAS las lineas finales, ya decididas, sin linea decidir." if (problema or malas) else
                                           "\nEscribi SOLO las lineas que faltan para cumplir lo que decidiste (sacar, cambiar, "
                                           "agregar, cuenta), sobre el pedido como esta ahora. Sin linea decidir.")}], temp=0.0)
            lineas, malas = L.parsear(crudo2)
            lineas = self.renumerar(lineas)
            hechos, avisos = self.resolver(lineas)
            crudo = crudo + "\n--- segunda vuelta ---\n" + crudo2
            rondas = 2
            p2 = self.red(mensaje, lineas)
            if p2:
                avisos.append("CONFIRMAR ANTES DE CALCULAR: " + p2 + ". Deci que entendiste y pregunta si esta bien.")
        datos = self.texto(lineas, hechos, avisos)
        if rondas == 2 and decidir:
            l1, h1 = primera
            previos = [l for l in l1 if l["tipo"] in ("buscar", "producto", "politica", "envio")]
            datos = self.texto(previos, h1, []) + "\n\n" + datos
        resp = llamar(m, [{"role": "system", "content": REDACTA},
                          {"role": "user", "content": "DATOS:\n" + (datos or "(ninguno)") + "\n\nFINAL DE LA CHARLA:\n"
                           + (self.ultimos() or "(empieza)") + f"\nCLIENTE: {mensaje}"}], temp=0.2)
        self.chat.append((mensaje, resp))
        return {"lineas": crudo, "datos": datos, "respuesta": resp, "rondas": rondas}

    def red(self, mensaje, lineas):
        nombrados = {n(x.split(None, 1)[1]) if n(x).startswith("destino ") else n(x)
                     for l in lineas if l["tipo"] in ("agregar", "cambiar")
                     for x in (l["c"][2:3] if l["tipo"] == "agregar" else l["c"][1:2]) if x and n(x) not in ("nada", "-")}
        nombrados = {d for d in nombrados if d and not d.startswith(("cantidad", "variante", "por "))}
        en_pedido = {n(it["destino"]) for it in self.pedido if it["destino"]}
        faltan = [d for d in nombrados if d not in en_pedido]
        if faltan:
            return "nombraste los destinos " + ", ".join(faltan) + " pero el pedido no tiene nada para ahi: " \
                   "agrega cada unidad con su destino, una linea por destino"
        agregados = {}
        for l in lineas:
            if l["tipo"] == "agregar":
                c = l["c"] + ["", ""]
                q = int(re.sub(r"\D", "", c[1]) or 1)
                agregados[len(agregados)] = q
        if not agregados:
            return ""
        por_rubro = {}
        for it in self.pedido:
            r = self.prods[it["p"]]["categoria"]
            por_rubro[r] = por_rubro.get(r, 0) + it["q"]
        dichos = L.pedidos_del_cliente(mensaje)
        malos = [f"el cliente pidio {q} de {r} y el pedido tiene {por_rubro.get(r, 0)}" for r, q in dichos.items()
                 if por_rubro.get(r, 0) != q]
        return "; ".join(malos)


INDICE = indice()
L.TIPOS = ("humano", "envio", "compatibilidad", "buscar", "producto", "rubros", "politica", "agregar", "sacar", "cambiar", "olvidar", "cuenta", "pago",
           "decidir", "preguntar", "nada")
