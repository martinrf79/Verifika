"""EL CONTRATO DEL FLUJO NUEVO: LAS LINEAS, LOS NEXOS DE CADA UNA, EL FILTRO Y LA RESPUESTA DEL CODIGO.

Pasado de `banco_pruebas/flujo/flujo_nuevo.py` el 17-nov-2026, orden de Martin, tal cual: el banco importa de aca. Cada
linea de la llamada 0 va a sus nexos: producto, nombrado, condicion, tema y destino. Cada nexo devuelve un `Resultado`
con sus candidatos, lo elegido y su veredicto; el filtro deja solo lo que esta en la fuente, y `redactar` arma la
respuesta con las filas reales de la tienda. `memoria` son los ids mostrados.
"""
import dataclasses

from . import condicion as NC
from . import nombrado as NN
from . import rubro as NR
from . import tema as NT


# ══ EL CONTRATO ══════════════════════════════════════════════════════════════
@dataclasses.dataclass
class Resultado:
    """Lo que entrega un nexo por una linea. Los datos salen de la fuente tal cual."""
    nexo: str                 # destino, producto, nombrado, tema, condicion
    candidatos: list          # ids de la fuente, en orden
    elegido: object = None    # un id, o ninguno
    veredicto: str = "repreguntar"   # coincide, no hay, repreguntar
    datos: object = None      # filas, tarifa o texto de la FAQ


@dataclasses.dataclass
class Linea:
    fragmento: str
    busqueda: str
    destino: str
    nexos: list = dataclasses.field(default_factory=list)


def pendiente(nexo):
    return Resultado(nexo=nexo, candidatos=[], veredicto="repreguntar", datos="pendiente: el nexo no existe todavia")


class Indice(NR.Nexo):
    """El indice de la tienda con los puntajes de este flujo."""

    def __init__(self, tid, producto, tema, condicion=None, jev_condicion=None):
        """Los puntajes de cada nexo: `producto` y `tema` de la primera busqueda, `condicion` de la segunda, y lo que
        eligio Jev en las partes dudosas de la condicion. En produccion los arma `vectores`; en el banco, lo grabado."""
        super().__init__(tid, producto)
        self.marcas = {NR.n(k[1]) for k in self.modelos}
        self.temas = NT.Nexo(tid, tema)
        self.nombres = NN.Nexo(self)
        self.condicion = NC.Nexo(tid, condicion, jev_condicion)


# ══ PASOS 2 Y 4, EL RUTEO Y LOS NEXOS ════════════════════════════════════════
def ruteo(linea, idx):
    nexos = []
    if linea.busqueda:
        nexos.append("producto")
        palabras = NR.n(linea.busqueda).split()
        # El nombrado decide solo si corre: sus palabras de identidad, `nexo_nombrado`.
        nexos.append("nombrado")
        if len([w for w in palabras[1:] if w not in idx.marcas]) >= 1:
            nexos.append("condicion")
    if linea.fragmento:
        nexos.append("tema")
    if linea.destino:
        nexos.append("destino")
    return nexos


def nexo_producto(linea, idx, jev_producto=None):
    p = idx.producto({"busqueda": linea.busqueda, "fragmento": linea.fragmento})
    if p.get("dudoso") and jev_producto:
        # Lo dudoso lo confirma Jev, `nexo_rubro`: uno de los cinco candidatos, o no hay.
        v = jev_producto(linea.busqueda)
        elegido = next((f for f in p["candidatos"] if f["id"] == v), None)
        p = dict(p, elegido=elegido, no_hay=elegido is None)
    ids = [f["id"] for f in p["candidatos"]]
    if p["elegido"]:
        mismos = [f for f in p["candidatos"] if f["rubro"] == p["elegido"]["rubro"]][:3]
        return Resultado("producto", ids, p["elegido"]["id"], "coincide", mismos)
    return Resultado("producto", ids, None, "no hay", [p["cercano"]] if p["cercano"] else [])


def nexo_tema(linea, idx, jev):
    """El nexo de tema, `nexo_tema`: tres temas por los alias, el codigo elige por palabra y Jev confirma lo dudoso."""
    r = idx.temas.tema(linea.fragmento)
    if not r["elegido"]:
        return Resultado("tema", r["candidatos"], None, "ningun tema", None)
    v = jev(linea.fragmento)
    if v not in r["candidatos"]:
        return Resultado("tema", r["candidatos"], None, "ningun tema", None)
    return Resultado("tema", r["candidatos"], v, "coincide", idx.temas.texto(v))


def nexo_nombrado(linea, idx):
    """El nexo nombrado, `nexo_nombrado`: el rubro por embeddings y la identidad por palabra exacta. None si no corre."""
    r = idx.nombres.nombrado(linea)
    if r is None or (r["veredicto"] == "not_found" and r["de_otro_rubro"]):
        return None
    if r["veredicto"] == "exists":
        f = next(x for x in idx.filas if x["id"] == r["producto"]["id"])
        fila = {"id": f["id"], "nombre": f["nombre"], "rubro": f["categoria"], "precio": int(float(f["precio_ars"])),
                "stock": int(f["stock"] or 0)}
        return Resultado("nombrado", [f["id"]], f["id"], "coincide", [fila])
    if r["veredicto"] == "ambiguous":
        filas = [x for x in (idx._fila((r["rubro"], f["marca"], f["modelo"])) for f in idx.filas
                             if f["categoria"] == r["rubro"] and f["modelo"] in r["modelos"]) if x]
        filas = sorted({x["id"]: x for x in filas}.values(), key=lambda x: x["precio"])
        return Resultado("nombrado", [x["id"] for x in filas], None, "ambiguo", filas)
    return Resultado("nombrado", [], None, "no hay", {"palabras": r["palabras"], "rubro": r["rubro"]})


def nexo_condicion(linea, idx, por_id):
    """El nexo de condicion, `nexo_condicion`, sobre el rubro que ya decidieron el de producto y el nombrado. None si no
    corre, o si la busqueda no pide nada mas que el producto."""
    r, _ = NC.rubro_de(linea, por_id)
    if r is None:
        return None
    nx = idx.condicion
    items = nx.condicion(linea.busqueda, r)["items"]
    if not items:
        return None

    def fila(p):
        return {"id": p["id"], "nombre": p["nombre"], "rubro": r, "precio": int(p["precio_ars"]), "stock": int(p["stock"])}
    atados = [it for it in items if it["veredicto"] in ("ata", "orden", "tope")]
    filas = nx.filas(r, atados)
    if any(it["veredicto"] == "no se ata" for it in items):
        # Lo que no se ata se repregunta; si algo si se ato, "144hz" en "monitor 27 pulgadas 144hz", se muestra con eso.
        fs = [fila(p) for p in filas[:3]] if atados and not any(it["veredicto"] == "no hay" for it in items) else []
        return Resultado("condicion", [x["id"] for x in fs], None, "repreguntar",
                         {"rubro": r, "items": items, "filas": fs, "atado": [it["parte"] for it in atados],
                          "partes": [it["parte"] for it in items if it["veredicto"] == "no se ata"]})
    if any(it["veredicto"] == "no hay" for it in items) or not filas:
        # Lo mas cercano: lo que cumple lo demas, sin lo que no hay.
        cerca = [fila(p) for p in filas[:1]]
        return Resultado("condicion", [x["id"] for x in cerca], None, "no hay",
                         {"rubro": r, "items": items, "filas": cerca,
                          "partes": [it["parte"] for it in items if it["veredicto"] == "no hay"] or [linea.busqueda]})
    fs = [fila(p) for p in filas[:3]]
    return Resultado("condicion", [x["id"] for x in fs], fs[0]["id"], "coincide", {"rubro": r, "items": items, "filas": fs})


def nexo_destino(linea):
    from app.core.flujo.normal import lugares
    from app.core.fuente import _cotizar
    lugares_ = [f for f, _ in lugares(linea.destino)]
    if not lugares_:
        return [Resultado("destino", [], None, "repreguntar", {"lugar": linea.destino, "motivo": "no es un lugar conocido"})]
    out = []
    for l in lugares_:
        r = _cotizar(l)
        out.append(Resultado("destino", [l], l if r else None, "coincide" if r else "repreguntar",
                             {"lugar": l, "monto": r.get("monto"), "zona": r.get("zona"), "provincia": r.get("provincia")}
                             if r else {"lugar": l, "motivo": "falta la provincia"}))
    return out


def nexos(linea, idx, jev, jev_producto=None):
    for nexo in ruteo(linea, idx):
        if nexo == "producto":
            linea.nexos.append(nexo_producto(linea, idx, jev_producto))
        elif nexo == "tema":
            linea.nexos.append(nexo_tema(linea, idx, jev))
        elif nexo == "nombrado":
            r = nexo_nombrado(linea, idx)
            if r:
                linea.nexos.append(r)
        elif nexo == "destino":
            linea.nexos.extend(nexo_destino(linea))
        elif nexo == "condicion":
            r = nexo_condicion(linea, idx, {f["id"]: f for f in idx.filas})
            if r:
                linea.nexos.append(r)
        else:
            linea.nexos.append(pendiente(nexo))
    return linea


# ══ PASOS 6 A 8, EL FILTRO, REDACTAR Y LA MEMORIA ════════════════════════════
def filtro(linea, por_id):
    """Lo elegido tiene que estar entre los candidatos y en la fuente; si no, no vale."""
    for r in linea.nexos:
        if r.nexo == "producto" and r.elegido is not None and (r.elegido not in r.candidatos or r.elegido not in por_id):
            r.elegido, r.veredicto = None, "repreguntar"
        if r.nexo == "nombrado" and r.elegido is not None and (r.elegido not in r.candidatos or r.elegido not in por_id):
            r.elegido, r.veredicto = None, "repreguntar"
        if r.nexo == "tema" and r.elegido is not None and r.elegido not in r.candidatos:
            r.elegido, r.veredicto, r.datos = None, "ningun tema", None
        if r.nexo == "condicion" and any(x not in por_id for x in r.candidatos):
            r.elegido, r.veredicto = None, "repreguntar"
    return linea


def redactar(lineas):
    def plata(x):
        return "$" + f"{int(x):,}".replace(",", ".")
    partes, temas = [], []
    for l in lineas:
        # Si el nombrado corrio, su respuesta reemplaza a la del producto generico de la misma linea; si corrio la condicion,
        # la suya reemplaza a las dos.
        nombro = any(r.nexo == "nombrado" for r in l.nexos)
        condiciono = any(r.nexo == "condicion" for r in l.nexos)
        for r in l.nexos:
            if (r.nexo == "producto" and (nombro or condiciono)) or (r.nexo == "nombrado" and condiciono):
                continue
            if r.nexo == "condicion" and r.veredicto == "coincide":
                # Solo lo que se ato: repetir la busqueda entera afirmaria lo que no se ato.
                dicho = ", ".join(it["parte"] for it in r.datos["items"])
                partes.append(f"En {r.datos['rubro']}, {dicho}, tengo: " + "; ".join(
                    f"{f['nombre']} a {plata(f['precio'])}, quedan {f['stock']}" for f in r.datos["filas"]) + ".")
            elif r.nexo == "condicion" and r.veredicto == "no hay":
                c = r.datos["filas"][0] if r.datos["filas"] else None
                partes.append(f"{r.datos['rubro'].capitalize()} {', '.join(r.datos['partes'])} no hay."
                              + (f" Lo mas cercano: {c['nombre']} a {plata(c['precio'])}." if c else ""))
            elif r.nexo == "condicion" and r.datos["filas"]:
                partes.append(f"De {', '.join(r.datos['partes'])} la ficha de {r.datos['rubro']} no dice nada. Con "
                              f"{', '.join(r.datos['atado'])} tengo: " + "; ".join(
                                  f"{f['nombre']} a {plata(f['precio'])}" for f in r.datos["filas"])
                              + ". Te sirve alguno, o contame que buscas?")
            elif r.nexo == "condicion":
                partes.append(f"De {', '.join(r.datos['partes'])} la ficha de {r.datos['rubro']} no dice nada: "
                              f"te muestro los que hay, o contame que buscas.")
            if r.nexo == "nombrado" and r.veredicto == "coincide":
                f = r.datos[0]
                partes.append(f"{f['nombre']} a {plata(f['precio'])}, quedan {f['stock']}.")
            elif r.nexo == "nombrado" and r.veredicto == "ambiguo":
                partes.append(f"Por {l.busqueda} tengo: " + "; ".join(
                    f"{f['nombre']} a {plata(f['precio'])}" for f in r.datos[:5])
                    + (f"; y {len(r.datos) - 5} mas" if len(r.datos) > 5 else "") + ". Cual te interesa?")
            elif r.nexo == "nombrado":
                partes.append(f"{l.busqueda.capitalize()} no lo tengo.")
            elif r.nexo == "producto" and r.veredicto == "coincide":
                partes.append(f"Por {l.busqueda} tengo: " + "; ".join(
                    f"{f['nombre']} a {plata(f['precio'])}, quedan {f['stock']}" for f in r.datos) + ".")
            elif r.nexo == "producto":
                c = r.datos[0] if r.datos else None
                partes.append(f"{l.busqueda.capitalize()} no hay." + (f" Lo mas cercano: {c['nombre']} a {plata(c['precio'])}."
                                                                      if c else ""))
            elif r.nexo == "destino" and r.veredicto == "coincide":
                partes.append(f"El envio a {r.datos['lugar']} sale {plata(r.datos['monto'])}.")
            elif r.nexo == "destino" and r.datos.get("motivo") == "falta la provincia":
                partes.append(f"Para el envio a {r.datos['lugar']} necesito la provincia.")
            elif r.nexo == "tema" and r.veredicto == "coincide" and r.elegido not in temas:
                temas.append(r.elegido)
                partes.append(r.datos)
    return "\n".join(partes)


def memoria(lineas):
    return [x for l in lineas for r in l.nexos if r.nexo in ("producto", "nombrado", "condicion")
            and r.veredicto in ("coincide", "ambiguo") for x in [f["id"] for f in (r.datos["filas"] if r.nexo == "condicion"
                                                                                     else r.datos)]]


def flujo(lineas, idx, por_id, jev, jev_producto=None):
    """Los pasos 2 a 8 sobre las lineas de la llamada 0. `jev(fragmento)` y `jev_producto(busqueda)` dan el veredicto de
    lo dudoso del tema y del producto."""
    lineas = [filtro(nexos(l, idx, jev, jev_producto), por_id) for l in lineas]
    return lineas, redactar(lineas), memoria(lineas)

