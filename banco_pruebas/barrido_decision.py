"""
EL BARRIDO DE LA DECISION Y LA REPOSICION — la mitad del turno que amortigua.

POR QUE EXISTE (Martin, 14-ago-2026, y la pregunta es suya, textual): *"dado
que faltan de realizar el barrido en otras areas, el experimento sin dicho
barrido seria algo que tal vez cometa los mismos errores que el sistema
complejo actual"*.

LO QUE FALTABA, MEDIDO Y NO OPINADO. El turno tiene treinta y tres nodos
declarados en `app/verifika/grafo.py`. Hasta hoy los contratos mecanicos los
tenian los DIECIOCHO que transforman texto, y los quince restantes ninguno. Esa
mitad sin medir no es cualquiera: es la que ATAJA lo que el modelo no hizo -el
item declarado que nadie busco, la condicion que no se aplico, la cuenta que
perdio un rubro-. O sea que la red que amortigua los errores del modelo era
justamente la que nadie estaba midiendo, y cualquier experimento sobre el
decisor se iba a medir contra un colchon de espesor desconocido.

NO ES QUE NO SE PUDIERAN BARRER. De los quince, uno solo es el modelo -el
decisor- y otro es el modelo escribiendo -el redactor-. Los demas son funciones
deterministas que reciben el estado del turno y devuelven el estado del turno:
se corren offline, sin credenciales y sin gastar un peso. Estaban sin contrato
porque nadie se los escribio, no porque no se pudiera.

QUE BARRE, y la lista NO esta escrita aca: sale de `grafo.barribles_de_datos()`,
o sea de los nodos que declaran contrato y saben correrse solos. Un nodo nuevo
entra al barrido por existir. Y el que no tiene contrato tiene que declarar POR
QUE, que es el otro candado: `grafo.sin_contrato()` no puede tener un motivo
vacio.

LOS CINCO CONTRATOS, y dos de ellos son defectos ABIERTOS hoy en PENDIENTE:

  NO_LEVANTA              ninguna entrada lo hace explotar.
  IDEMPOTENTE             aplicarlo dos veces da lo mismo que una.
  NO_INVENTA_ID           ningun product_id sale si no entro o no existe en el
                          catalogo real. Es la regla cero, un piso mas arriba.
  NO_PIERDE_EVIDENCIA     la herramienta que entro sigue estando a la salida.
                          Lo que se pierde aca deja al redactor sin el dato y
                          el bot termina negando lo que el catalogo si tiene.
  NO_AGREGA_LO_NO_PEDIDO  ningun item entra a la cuenta si el cliente no lo
                          pidio. Es el auricular del 12-ago.
  NO_RECLAMA_LO_RESUELTO  lo ya atendido no se vuelve a reclamar. Cada reclamo
                          imposible quema una ronda entera del turno.

COMO SE GENERAN LAS ENTRADAS, y es lo que lo hace un barrido y no una lista de
ejemplos: los estados de turno se ARMAN, no se escriben. Se sortean productos
del catalogo REAL de la fuente, se corren las herramientas de verdad para tener
resultados de verdad, y se rompe el estado de una manera distinta por clase.
Las clases no son adorno: cada una es el disparador de una reposicion. Un
barrido que solo genera turnos donde todo vino bien no ejercita ni una sola
pieza de esta mitad, que es exactamente lo que pasaba.

CORRE OFFLINE Y GRATIS: doble local de Firestore con el catalogo y la FAQ
reales, cero llamadas al modelo, cero credenciales.
"""
import random
import re
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

TIENDA = "verifika_prod"
SEMILLA = 14

# Las clases de estado de turno. Cada una existe porque DISPARA algo: si el
# barrido solo generara turnos completos, las seis reposiciones no correrian
# nunca y el numero diria 100% sobre codigo que no se ejecuto.
CLASES = ("completo", "sin_buscar", "condicion_suelta", "sin_cuenta",
          "reparto_suelto", "supuesto_callado", "multibloque", "vacio",
          "torcido")

_RE_ID = re.compile(r"\b[A-Z]{2,5}\d{2,}\b")


# ── LA FUENTE: productos REALES, sorteados ──────────────────────────────────
def _catalogo() -> list:
    """El catalogo real de la fuente. Es el mismo que ve produccion, por la
    misma puerta que usa el turno."""
    from app.storage.firestore_client import get_all_products
    return list(get_all_products(TIENDA) or [])


def _ids_del_catalogo() -> set:
    return {str(p.get("id") or p.get("product_id") or "")
            for p in _catalogo()} - {""}


def _muestra(n: int, semilla: int) -> list:
    """n productos del catalogo real, sorteados con semilla fija: el barrido
    tiene que dar el mismo numero dos veces seguidas o no sirve de vara."""
    cat = _catalogo()
    return random.Random(semilla).sample(cat, min(n, len(cat)))


# ── LOS ESTADOS DE TURNO, ARMADOS ───────────────────────────────────────────
def _buscar(prod: dict) -> dict:
    """Una llamada de busqueda REAL, con el resultado que devuelve la
    herramienta viva. No se simula el resultado: se lo pide."""
    from app.core import herramientas as H
    args = {"descripcion": str(prod.get("nombre") or "")[:60], "cuantos": 3}
    return {"herramienta": "buscar_productos", "pedido": args,
            "resultado": H.ejecutar("buscar_productos", args, TIENDA)}


def _buscar_sin_cumplir(prod: dict) -> dict:
    """Una busqueda que NO encuentra lo pedido del todo y por eso devuelve
    BLOQUE.

    Es la unica forma de llegar a `bloques_a_uno`, que exige dos rubros con
    bloque: cuando todo se encuentra no hay bloque que unir. Se pide un precio
    imposible sobre una categoria real, que es una condicion que ningun
    producto de la fuente cumple sin tener que inventar nada."""
    from app.core import herramientas as H
    args = {"descripcion": str(prod.get("nombre") or "")[:40],
            "categoria": str(prod.get("categoria") or ""),
            "filtros": [{"campo": "precio_ars", "operador": "menor",
                         "valor": "1"}],
            "cuantos": 3}
    return {"herramienta": "buscar_productos", "pedido": args,
            "resultado": H.ejecutar("buscar_productos", args, TIENDA)}


def _de_rubros_distintos(n: int, semilla: int) -> list:
    """n productos de n categorias DISTINTAS. `bloques_a_uno` agrupa por rubro
    y se queda con uno por rubro, asi que con tres productos de la misma
    categoria no se dispara nunca."""
    cat = _catalogo()
    rnd = random.Random(semilla)
    por_cat: dict = {}
    for p in rnd.sample(cat, len(cat)):
        c = str(p.get("categoria") or "")
        if c and c not in por_cat:
            por_cat[c] = p
        if len(por_cat) >= n:
            break
    return list(por_cat.values())


def _presupuesto(prods: list, destinos: list | None = None,
                 pago: list | None = None) -> dict:
    from app.core import herramientas as H
    args = {"items": [{"product_id": str(p.get("id")), "cantidad": 1}
                      for p in prods]}
    if destinos:
        args["destinos"] = list(destinos)
    if pago:
        args["pago"] = list(pago)
    return {"herramienta": "armar_presupuesto", "pedido": args,
            "resultado": H.ejecutar("armar_presupuesto", args, TIENDA)}


def _declarado(prods: list, **extra) -> dict:
    """Lo que el modelo DECLARO que entendio, con la forma del molde real."""
    d = {"items": [{"que": str(p.get("nombre") or "").split()[0].lower(),
                    "cantidad": 1} for p in prods],
         "pide_precio": True}
    d.update(extra)
    return d


def _base(clase: str, semilla: int) -> dict:
    """El estado del turno de una clase. Devuelve el ctx que comen los nodos."""
    ctx = {"tienda_id": TIENDA, "trace_id": f"barrido-{clase}-{semilla}",
           "llamadas": [], "declarado": {}, "rec": {}, "memoria": [],
           "history": [], "estado": {}, "texto": "", "pedidos": [],
           "ya_resuelto": ""}
    prods = _muestra(3, semilla)

    if clase == "vacio":
        # El turno donde el modelo no llamo a nada. Ninguna reposicion tiene de
        # donde agarrarse y ninguna puede romper: es el piso de NO_LEVANTA.
        ctx["declarado"] = _declarado(prods[:1])
        ctx["pedidos"] = []
        return ctx

    if clase == "torcido":
        # Lo que llega cuando una herramienta se cayo o devolvio cualquier
        # cosa. Nada de esto es inventado: `_ejecutar_en_paralelo` fabrica el
        # {"estado": "error"} cuando una tool levanta.
        ctx["declarado"] = _declarado(prods[:2])
        ctx["llamadas"] = [
            {"herramienta": "buscar_productos", "pedido": {}, "resultado": None},
            {"herramienta": "armar_presupuesto", "pedido": {"items": []},
             "resultado": {"estado": "error"}},
            {"herramienta": "no_existe", "pedido": {"x": 1}, "resultado": {}},
            {"herramienta": "buscar_productos"},
        ]
        ctx["pedidos"] = [{"nombre": "buscar_productos", "args": {}},
                          {"nombre": "no_existe", "args": {}},
                          {"nombre": "ficha_producto",
                           "args": {"product_id": "NOEXISTE999"}}]
        return ctx

    if clase == "completo":
        # Todo vino bien: se declaro, se busco y se calculo.
        ctx["declarado"] = _declarado(prods)
        ctx["llamadas"] = [_buscar(p) for p in prods]
        ctx["llamadas"].append(_presupuesto(prods, destinos=["cordoba capital"]))
        ctx["pedidos"] = [{"nombre": "buscar_productos",
                           "args": {"descripcion": str(prods[0].get("nombre")),
                                    "cuantos": 2}}]
        return ctx

    if clase == "sin_buscar":
        # EL DEFECTO DEL 9-AGO: el modelo declara tres rubros y busca dos.
        ctx["declarado"] = _declarado(prods)
        ctx["llamadas"] = [_buscar(p) for p in prods[:1]]
        ctx["pedidos"] = [{"nombre": "buscar_productos",
                           "args": {"descripcion": str(prods[1].get("nombre"))}}]
        return ctx

    if clase == "condicion_suelta":
        # La condicion que el cliente puso y ninguna busqueda aplico.
        ctx["declarado"] = _declarado(prods[:2],
                                      restricciones=["que no sea de china"])
        ctx["llamadas"] = [_buscar(p) for p in prods[:2]]
        ctx["pedidos"] = [{"nombre": "buscar_productos",
                           "args": {"descripcion": str(prods[0].get("nombre"))}}]
        return ctx

    if clase == "sin_cuenta":
        # EL DEFECTO DEL 5-AGO, los $69.000: se pide precio, se busca todo y la
        # cuenta no se arma.
        ctx["declarado"] = _declarado(prods, pide_precio=True,
                                      destinos=["rosario"])
        ctx["llamadas"] = [_buscar(p) for p in prods]
        ctx["pedidos"] = [{"nombre": "armar_presupuesto",
                           "args": {"items": [{"product_id": str(prods[0].get("id")),
                                               "cantidad": 2}]}}]
        return ctx

    if clase == "reparto_suelto":
        # EL DEFECTO DEL 6-AGO, los $17.500: el reparto declarado y la cuenta
        # armada sin el. El reparto va SIN medio a proposito: con el medio
        # dicho no hay nada que asumir y el codigo no toca nada, que es lo
        # correcto. El caso que rompio en produccion es este.
        ctx["declarado"] = _declarado(
            prods[:2], reparto_pago=[{"porcentaje": 70}, {"porcentaje": 30}])
        ctx["llamadas"] = [_buscar(p) for p in prods[:2]]
        ctx["llamadas"].append(_presupuesto(prods[:2]))
        ctx["pedidos"] = [{"nombre": "armar_presupuesto",
                           "args": {"items": [{"product_id": str(prods[0].get("id")),
                                               "cantidad": 1}]}}]
        return ctx

    if clase == "supuesto_callado":
        # EL DEFECTO DE LOS DOS DIAS SEGUIDOS: el reparto SI se aplico, pero el
        # cliente nunca dijo que medio lleva cada parte y la cuenta no lo
        # declara. El 5-ago salio al reves que el 6, y como la transferencia
        # tiene descuento, ese silencio le cambia al cliente lo que paga.
        ctx["declarado"] = _declarado(
            prods[:2], reparto_pago=[{"porcentaje": 70}, {"porcentaje": 30}])
        ctx["llamadas"] = [_buscar(p) for p in prods[:2]]
        ctx["llamadas"].append(_presupuesto(
            prods[:2], pago=[{"medio": "transferencia", "porcentaje": 70},
                             {"medio": "mercado pago", "porcentaje": 30}]))
        ctx["pedidos"] = []
        return ctx

    if clase == "multibloque":
        # EL DEFECTO DEL 6-AGO, la mitad del mensaje: un bloque por rubro. Los
        # productos son de rubros DISTINTOS y las busquedas no encuentran del
        # todo, que son las dos condiciones para que haya bloques que unir.
        rubros = _de_rubros_distintos(3, semilla)
        ctx["declarado"] = _declarado(rubros)
        ctx["llamadas"] = [_buscar_sin_cumplir(p) for p in rubros]
        ctx["pedidos"] = []
        return ctx

    raise ValueError(f"clase desconocida: {clase}")


def estados() -> list:
    """Los estados de turno del barrido: cada clase por cada sorteo. Son
    entradas GENERADAS, no escritas, que es la unica forma de encontrar el
    defecto que nadie anticipo."""
    fuera = []
    for clase in CLASES:
        for k in range(3):
            fuera.append((clase, _base(clase, SEMILLA + k * 17)))
    return fuera


# ── LOS CONTRATOS, comprobados sin saber cual era la respuesta correcta ─────
_CLAVES_DE_ID = ("id", "product_id", "contra_product_id")


def _ids_de(obj) -> set:
    """Todo product_id que aparece en cualquier rincon de una estructura.

    Se leen las CLAVES de id, no se busca el patron en el texto libre, y la
    diferencia no es cosmetica: la primera version barria con una expresion
    regular y marcaba `CV550` como id inventado cuando era el MODELO de una
    webcam escrito adentro de su nombre. Un contrato que da falsos positivos se
    desactiva a la semana; es preferible medir menos y que cada rojo sea real."""
    vistos = set()
    pila = [obj]
    while pila:
        x = pila.pop()
        if isinstance(x, dict):
            for k, v in x.items():
                if k in _CLAVES_DE_ID and isinstance(v, str) and v.strip():
                    vistos.add(v.strip())
                else:
                    pila.append(v)
        elif isinstance(x, (list, tuple)):
            pila.extend(x)
    return vistos


def _herramientas_de(llamadas) -> set:
    return {str(l.get("herramienta") or "") for l in (llamadas or [])
            if isinstance(l, dict)} - {""}


def _items_cotizados(llamadas) -> set:
    """Los ids que entraron a una cuenta. Es lo que el cliente termina
    pagando, asi que es donde NO_AGREGA_LO_NO_PEDIDO se mide."""
    fuera = set()
    for l in (llamadas or []):
        if not isinstance(l, dict) or l.get("herramienta") != "armar_presupuesto":
            continue
        for it in ((l.get("pedido") or {}).get("items") or []):
            if isinstance(it, dict) and it.get("product_id"):
                fuera.add(str(it["product_id"]))
    return fuera


def _cubierto_por_evidencia(que: str, ctx: dict) -> bool:
    """El item esta atendido si alguna busqueda del turno trajo algo que lo
    nombra, o si ya se resolvio antes. Se mide contra la EVIDENCIA, no
    reimplementando al reconciliador: si el barrido copiara su logica, los dos
    se equivocarian juntos y el contrato no valdria nada."""
    palabra = str(que or "").strip().lower()
    if not palabra:
        return False
    if palabra in str(ctx.get("ya_resuelto") or "").lower():
        return True
    for l in (ctx.get("llamadas") or []):
        if not isinstance(l, dict):
            continue
        r = l.get("resultado")
        if not isinstance(r, dict) or r.get("estado") in ("error", "no_encontrado"):
            continue
        for p in (r.get("productos") or []):
            if palabra in str((p or {}).get("nombre") or "").lower():
                return True
    return False


def violaciones(nodo, antes: dict, despues: dict, catalogo: set) -> list:
    """Los contratos del nodo, comprobados sobre el estado antes y despues.
    Devuelve la lista de los que se rompieron, con el detalle."""
    from app.verifika import grafo as G
    rotos = []

    if G.NO_INVENTA_ID in nodo.contratos:
        nuevos = _ids_de(despues) - _ids_de(antes)
        inventados = sorted(nuevos - catalogo)
        if inventados:
            rotos.append((G.NO_INVENTA_ID,
                          f"ids que no existen en el catalogo: {inventados[:4]}"))

    if G.NO_PIERDE_EVIDENCIA in nodo.contratos:
        perdidas = _herramientas_de(antes.get("llamadas")) - \
            _herramientas_de(despues.get("llamadas"))
        if perdidas:
            rotos.append((G.NO_PIERDE_EVIDENCIA,
                          f"herramientas que desaparecieron: {sorted(perdidas)}"))

    if G.NO_AGREGA_LO_NO_PEDIDO in nodo.contratos:
        # Un id puede entrar a la cuenta solo si el turno lo trajo: estaba en
        # otra llamada, en el carrito o en lo ya mostrado. Un id que aparece en
        # la cuenta sin haber estado en ningun lado es el auricular del 12-ago.
        sumados = _items_cotizados(despues.get("llamadas")) - \
            _items_cotizados(antes.get("llamadas"))
        respaldo = _ids_de(antes) | _ids_de(despues.get("memoria")) | \
            _ids_de(despues.get("estado"))
        sin_respaldo = sorted(sumados - respaldo)
        if sin_respaldo:
            rotos.append((G.NO_AGREGA_LO_NO_PEDIDO,
                          f"entraron a la cuenta sin pedirse: {sin_respaldo[:4]}"))

    if G.NO_RECLAMA_LO_RESUELTO in nodo.contratos:
        faltantes = " ".join((despues.get("rec") or {}).get("faltantes") or [])
        for it in ((antes.get("declarado") or {}).get("items") or []):
            que = str((it or {}).get("que") or "")
            if que and _cubierto_por_evidencia(que, antes) and \
                    f"'{que}'" in faltantes:
                rotos.append((G.NO_RECLAMA_LO_RESUELTO,
                              f"reclama '{que}', que ya estaba atendido"))
    return rotos


_SALIDA_DE = {"reconciliador": "rec", "indice_turno": "indice",
              "memoria_texto": "memoria_texto"}


def _clave_de_salida(nodo, ctx: dict):
    """Lo que ESTE nodo produjo, para poder compararlo consigo mismo en la
    prueba de idempotencia sin mirar el resto del estado, que otros nodos
    tocan."""
    return repr(ctx.get(_SALIDA_DE.get(nodo.id, "llamadas")))


def _intervino(nodo, antes: dict, despues: dict) -> bool:
    """Si el nodo hizo algo. Se MIDE, no se le pregunta, igual que el veredicto
    del turno vivo.

    El reconciliador es la excepcion y tiene motivo: no transforma el estado,
    lo DICTAMINA. Su `rec` se calcula igual entre en el turno o no, asi que
    compararlo antes y despues siempre da igual y lo dejaba figurando como
    codigo no ejercitado. Para el, intervenir es haber reclamado algo."""
    if nodo.id == "reconciliador":
        rec = despues.get("rec") or {}
        return bool(rec.get("faltantes") or rec.get("preguntar")
                    or rec.get("sin_buscar"))
    return _clave_de_salida(nodo, despues) != _clave_de_salida(nodo, antes)


# ── LA CORRIDA ──────────────────────────────────────────────────────────────
def barrer() -> dict:
    """Corre cada nodo barrible de datos sobre cada estado generado y comprueba
    sus contratos. Devuelve el numero, las celdas y las violaciones."""
    from app.verifika import grafo as G
    catalogo = _ids_del_catalogo()
    nodos = G.barribles_de_datos()
    casos = estados()

    celdas, cubiertas, intervino, rotos = set(), set(), {}, []
    for nombre_nodo in (n.id for n in nodos):
        for clase in CLASES:
            celdas.add((nombre_nodo, clase))

    for clase, ctx in casos:
        # El reconciliador corre primero de verdad en el turno, y las
        # reposiciones comen lo que el reclama: sin eso, tres de las seis no se
        # disparan nunca y el barrido mediria aire.
        try:
            ctx = G.POR_ID["reconciliador"].aplicar_datos(ctx)
        except Exception:  # noqa: BLE001 — se reporta como violacion abajo
            pass
        for nodo in nodos:
            entrada = dict(ctx)
            try:
                salida = nodo.aplicar_datos(entrada)
            except Exception as e:  # noqa: BLE001
                rotos.append((nodo.id, clase, G.NO_LEVANTA,
                              f"{type(e).__name__}: {str(e)[:120]}"))
                continue
            cubiertas.add((nodo.id, clase))
            if _intervino(nodo, entrada, salida):
                intervino[nodo.id] = intervino.get(nodo.id, 0) + 1
            for c, detalle in violaciones(nodo, entrada, salida, catalogo):
                rotos.append((nodo.id, clase, c, detalle))
            if G.IDEMPOTENTE in nodo.contratos:
                try:
                    otra = nodo.aplicar_datos(dict(salida))
                except Exception as e:  # noqa: BLE001
                    rotos.append((nodo.id, clase, G.NO_LEVANTA,
                                  f"segunda pasada: {type(e).__name__}"))
                    continue
                if _clave_de_salida(nodo, otra) != _clave_de_salida(nodo, salida):
                    rotos.append((nodo.id, clase, G.IDEMPOTENTE,
                                  "la segunda pasada cambia el estado"))

    return {
        "nodos": len(nodos),
        "clases": len(CLASES),
        "casos": len(casos),
        "celdas": len(celdas),
        "cubiertas": len(cubiertas),
        "cobertura": round(100.0 * len(cubiertas) / max(1, len(celdas)), 1),
        "sin_cubrir": sorted(celdas - cubiertas),
        "intervinieron": intervino,
        "nunca_intervino": sorted(n.id for n in nodos if n.id not in intervino),
        "violaciones": rotos,
        "contratos": sorted({c for n in nodos for c in n.contratos}),
    }


def cobertura() -> dict:
    """La forma que pide `inventario_barrido.py`.

    LA COBERTURA CUENTA DOS COSAS Y LAS DOS TIENEN QUE ESTAR, porque con una
    sola el numero miente: que cada nodo se haya CORRIDO en cada clase, y que
    cada nodo haya INTERVENIDO al menos una vez. Un nodo que se corre nueve
    veces y nunca hace nada es codigo que el barrido recorre sin ejercitar, y
    contarlo como cubierto es exactamente la clase de verde vacio que este repo
    ya pago."""
    r = barrer()
    pendientes = [f"{n} x {c}" for n, c in r["sin_cubrir"]]
    pendientes += [f"{n}: nunca intervino" for n in r["nunca_intervino"]]
    return {"porcentaje": r["cobertura"], "pendientes": pendientes,
            "casos": r["casos"], "celdas": r["celdas"],
            "cubiertas": r["cubiertas"], "nodos": r["nodos"],
            "clases": r["clases"], "contratos": r["contratos"],
            "violaciones": r["violaciones"],
            "intervinieron": len(r["intervinieron"])}


def main() -> int:
    from banco_pruebas.sim_firestore import install
    from app.core.contexto_turno import set_current_tienda
    install()
    set_current_tienda(TIENDA)

    r = barrer()
    print("=" * 72)
    print("EL BARRIDO DE LA DECISION Y LA REPOSICION")
    print("=" * 72)
    print(f"  nodos barridos ......... {r['nodos']}")
    print(f"  clases de estado ....... {r['clases']}  ({', '.join(CLASES)})")
    print(f"  estados generados ...... {r['casos']}")
    print(f"  celdas nodo x clase .... {r['cubiertas']}/{r['celdas']} "
          f"= {r['cobertura']}%")
    print(f"  contratos comprobados .. {', '.join(r['contratos'])}")
    print()
    print("  QUIEN INTERVINO, y cuantas veces. Un nodo que nunca interviene es")
    print("  codigo que el barrido recorre sin ejercitar:")
    for nodo, veces in sorted(r["intervinieron"].items(), key=lambda x: -x[1]):
        print(f"    {nodo:22} {veces}")
    if r["nunca_intervino"]:
        print(f"    NUNCA INTERVINO: {', '.join(r['nunca_intervino'])}")
    print()
    if r["violaciones"]:
        print(f"  VIOLACIONES DE CONTRATO: {len(r['violaciones'])}")
        for nodo, clase, contrato, detalle in r["violaciones"][:30]:
            print(f"    {nodo:22} {clase:17} {contrato:24} {detalle}")
    else:
        print("  VIOLACIONES DE CONTRATO: 0")
    if r["sin_cubrir"]:
        print(f"  celdas sin cubrir: {r['sin_cubrir'][:10]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
