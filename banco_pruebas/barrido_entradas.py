"""
EL BARRIDO DE ENTRADAS — todo lo que el modelo puede mandarle a una herramienta.

POR QUE EXISTE (Martin, 12-ago-2026, y es su bronca mas justa): "cada prueba en
real es un nuevo arreglo parche... siempre se me dice que el barrido esta a
medias. Esta hecho totalmente o no esta hecho".

QUE FALTABA, MEDIDO Y NO OPINADO. El barrido que habia -`test_barrido_codigo`-
entra por `calculate_total`, que es una funcion INTERNA de la calculadora, y se
saltea `armar_presupuesto`, que es la herramienta que el modelo llama de verdad:
la que valida los argumentos, arma los destinos y escribe el reparto. Es la
misma clase de error que este repo ya pago y tiene escrita como su leccion mas
cara -un banco que llama por dentro da verde mientras el cliente recibe
cualquier cosa-, un piso mas abajo. Por eso el destino "Cordoba capital y
Concordia" era INVISIBLE para el: se procesa en `armar_presupuesto`.

Y su generador declara, textual, que "toda entrada del barrido es legitima":
productos con stock, extras reales, destinos cotizados. O sea que barre el caso
en que todo viene bien. Los cinco defectos que Martin encontro en real el 12-ago
venian TODOS de una entrada torcida.

LO QUE HACE ESTE MODULO. Genera las entradas de las NUEVE herramientas, campo
por campo, en tres clases:

  VALIDO   lo que el modelo manda cuando entendio bien: un id del catalogo, una
           categoria real, una localidad de la tabla, dos partes de pago que
           suman cien.
  BORDE    el limite legitimo: una sola unidad, un solo destino, el 100 en una
           sola parte, la lista de un elemento, el maximo de resultados.
  TORCIDO  lo que el modelo manda cuando NO entendio, y es de donde salieron
           todos los errores reales: un id que no existe, cantidad cero o
           negativa, un destino que son dos lugares pegados, porcentajes que no
           suman, una categoria inventada, una lista vacia.

COMO SE MIDE LA COBERTURA, y por que no se puede mentir: los campos NO estan
escritos a mano en ninguna lista. Se leen de los moldes Pydantic de
`app/core/herramientas.py`, que son los mismos que ve el modelo. Si alguien
agrega un campo a una herramienta, aparece solo en la cuenta y queda sin cubrir
hasta que se le escriban sus valores. Es el mismo candado que `INVENTARIO_FUENTE`
tiene sobre el catalogo: el numero sale de la fuente, no de una declaracion.

CORRE OFFLINE Y GRATIS: doble local de Firestore con el catalogo y la FAQ
reales, cero llamadas al modelo, cero credenciales.
"""
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

TIENDA = "verifika_prod"

VALIDO, BORDE, TORCIDO = "valido", "borde", "torcido"
CLASES = (VALIDO, BORDE, TORCIDO)


# ── LA SUPERFICIE, LEIDA DEL CODIGO ─────────────────────────────────────────
def herramientas() -> dict:
    """{nombre: modelo Pydantic} de todo lo que el modelo puede llamar. Sale de
    la tabla de despacho viva, no de una lista aparte que se desactualiza."""
    from app.core import herramientas as H
    return {n: H._MOLDES[n] for n in sorted(H._CUERPOS) if n in H._MOLDES}


def _anidados(modelo, vistos=None) -> dict:
    """Los moldes que cuelgan de otro molde: `ItemPedido` dentro de
    `ArmarPresupuesto`, `Filtro` dentro de `BuscarProductos`. Sus campos son
    parte de la superficie igual que los de arriba —el destino de cada item vive
    ahi, y ahi vivio el defecto del 12-ago— asi que cuentan para la cobertura."""
    from pydantic import BaseModel
    import typing
    vistos = vistos if vistos is not None else {}
    for campo in modelo.model_fields.values():
        for t in (typing.get_args(campo.annotation) or (campo.annotation,)):
            for t2 in (typing.get_args(t) or (t,)):
                if (isinstance(t2, type) and issubclass(t2, BaseModel)
                        and t2.__name__ not in vistos):
                    vistos[t2.__name__] = t2
                    _anidados(t2, vistos)
    return vistos


def superficie() -> dict:
    """{'herramienta.campo': None} de TODOS los campos que el modelo puede
    llenar, incluidos los de los moldes anidados. Es el denominador de la
    cobertura y se calcula leyendo los moldes."""
    fuera = {}
    for nombre, modelo in herramientas().items():
        for campo in modelo.model_fields:
            fuera[f"{nombre}.{campo}"] = None
        for sub_nombre, sub in _anidados(modelo).items():
            for campo in sub.model_fields:
                fuera[f"{nombre}.{sub_nombre}.{campo}"] = None
    return fuera


# ── LOS VALORES, POR CAMPO Y POR CLASE ──────────────────────────────────────
def _muestra(tienda_id: str = TIENDA) -> dict:
    """Datos REALES para los valores validos: ids, categorias y temas que
    existen. Un valido inventado probaria otra cosa."""
    from app.storage.firestore_client import get_all_products
    from app.core.guia_venta_prosa import GUIA_VENTA
    prods = [p for p in get_all_products(tienda_id=tienda_id)
             if int(p.get("stock") or 0) > 0]
    por_cat: dict = {}
    for p in prods:
        por_cat.setdefault(str(p.get("categoria") or ""), []).append(p)
    cats = sorted(c for c in por_cat if c)
    # Los temas REALES de la guia, que es la fuente. Un tema inventado como
    # "valido" probaria el camino del tema que no existe, no el del que si.
    temas = sorted(t for t in (GUIA_VENTA or {}) if isinstance(t, str))
    return {"productos": prods, "por_categoria": por_cat, "categorias": cats,
            "temas": temas[:6]}


def _opciones(nombre_herramienta: str, campo: str) -> list:
    """Los valores que el MOLDE permite, cuando el campo es un enum. Salen del
    `Literal` del schema, que es el mismo que ve el modelo.

    POR QUE SE LEEN Y NO SE ESCRIBEN. La primera version de este barrido tenia
    'listar_categorias' escrito a mano como valor valido de `operacion`, y no
    existe: el molde acepta 'contar', 'mas_barato' y otras cinco. O sea que seis
    casos "validos" probaban el rechazo del molde y no la herramienta, y la
    cobertura los contaba como cubiertos. Un generador que se equivoca en el
    valido mide cualquier cosa."""
    import typing
    modelo = herramientas().get(nombre_herramienta)
    if modelo is None:
        return []
    info = modelo.model_fields.get(campo)
    if info is None:
        for sub in _anidados(modelo).values():
            info = sub.model_fields.get(campo)
            if info is not None:
                break
    if info is None:
        return []
    for t in (typing.get_args(info.annotation) or (info.annotation,)):
        opts = typing.get_args(t)
        if opts and all(isinstance(o, str) for o in opts):
            return list(opts)
    return []


# Un id que respeta la FORMA del catalogo y no existe: el peor caso, porque
# pasa cualquier validacion de formato. "ZZZ9999" no es un typo, es lo que el
# modelo inventa cuando cree recordar un producto.
_ID_FANTASMA = "ZZZ9999"
# El destino con dos lugares pegados: el defecto real del 12-ago a las 18:05.
_DESTINO_DOBLE = "Cordoba capital y Concordia"
_LUGAR_FANTASMA = "Ciudad Inventada del Norte"


def valores(campo: str, m: dict) -> dict:
    """{clase: valor} para un campo, nombrado 'herramienta.campo' o
    'herramienta.Molde.campo'. Devuelve {} si el campo no tiene valores
    escritos: eso lo cuenta la cobertura como hueco, que es el punto."""
    prods = m["productos"]
    cat = m["categorias"][0] if m["categorias"] else "mouse"
    p1 = prods[0]["id"] if prods else "MOU0001"
    p2 = prods[1]["id"] if len(prods) > 1 else p1
    hoja = campo.rsplit(".", 1)[-1]
    herramienta = campo.split(".", 1)[0]

    # ── Identidad de producto ───────────────────────────────────────────
    if hoja in ("product_id", "contra_product_id"):
        return {VALIDO: p1, BORDE: p1.lower(), TORCIDO: _ID_FANTASMA}
    # ── Cantidades y topes ──────────────────────────────────────────────
    if hoja == "cantidad":
        return {VALIDO: 2, BORDE: 1, TORCIDO: 0}
    if hoja == "cuantos":
        return {VALIDO: 3, BORDE: 1, TORCIDO: 0}
    if hoja == "porcentaje":
        return {VALIDO: 70, BORDE: 100, TORCIDO: 0}
    # ── Lugares ─────────────────────────────────────────────────────────
    if hoja in ("localidad", "destino"):
        return {VALIDO: "Cordoba capital", BORDE: "caba",
                TORCIDO: _DESTINO_DOBLE}
    if hoja == "destinos":
        return {VALIDO: ["Cordoba capital", "Rosario"], BORDE: ["caba"],
                TORCIDO: [_DESTINO_DOBLE, _LUGAR_FANTASMA]}
    # ── Rubros y texto del cliente ──────────────────────────────────────
    if hoja == "categoria":
        return {VALIDO: cat, BORDE: cat.upper(), TORCIDO: "cohetes espaciales"}
    if hoja in ("descripcion", "que"):
        return {VALIDO: cat, BORDE: "x", TORCIDO: "asdkjh qwe zzz"}
    if hoja in ("equipo", "para"):
        return {VALIDO: "play 5", BORDE: "pc", TORCIDO: "nave espacial"}
    # ── Las cuatro familias informativas (FICHA 06) ─────────────────────
    if hoja == "de":
        return {VALIDO: cat, BORDE: "ese", TORCIDO: "asdkjh qwe zzz"}
    if hoja == "stock":
        return {VALIDO: [cat], BORDE: [], TORCIDO: ["cohetes espaciales"]}
    if hoja == "atributos":
        return {VALIDO: [{"de": cat, "campo": "pais_fabricacion"}],
                BORDE: [{"de": cat, "campo": "precio_ars"}],
                TORCIDO: [{"de": "", "campo": "campo_que_no_existe"}]}
    if hoja == "compatibilidad":
        return {VALIDO: [{"que": cat, "para": "play 5"}],
                BORDE: [{"que": cat, "para": "pc"}],
                TORCIDO: [{"que": "", "para": ""}]}
    if hoja == "temas":
        return {VALIDO: (m["temas"][:2] or ["envios"]), BORDE: ["envios"],
                TORCIDO: ["tema_que_no_existe"]}
    if hoja in ("restricciones", "contradicciones"):
        return {VALIDO: ["sin china en el pais donde se fabrica"],
                BORDE: [], TORCIDO: ["" ]}
    if hoja == "motivo":
        # Del molde: `motivo` es un enum cerrado, asi que el valido y el borde
        # son sus dos opciones y el torcido es cualquier otra cosa.
        mo = _opciones(herramienta, "motivo") or ["decide_comprar"]
        return {VALIDO: mo[0], BORDE: mo[-1], TORCIDO: "x" * 400}
    if hoja == "pide_precio":
        return {VALIDO: True, BORDE: False, TORCIDO: True}
    # ── Filtros y orden ─────────────────────────────────────────────────
    if hoja == "operador":
        op = _opciones(herramienta, "operador") or ["contiene", "no_contiene"]
        return {VALIDO: op[0], BORDE: op[-1], TORCIDO: "explota"}
    if hoja == "valor":
        return {VALIDO: "china", BORDE: "0", TORCIDO: "-1"}
    if hoja == "campo":
        return {VALIDO: "pais_fabricacion", BORDE: "precio_ars",
                TORCIDO: "campo_que_no_existe"}
    if hoja == "ordenar_por":
        return {VALIDO: "precio_ars", BORDE: "stock",
                TORCIDO: "campo_que_no_existe"}
    if hoja == "direccion":
        d = _opciones(herramienta, "direccion") or ["min", "max"]
        return {VALIDO: d[0], BORDE: d[-1], TORCIDO: "diagonal"}
    if hoja == "operacion":
        o = _opciones(herramienta, "operacion") or ["contar"]
        return {VALIDO: o[0], BORDE: o[-1],
                TORCIDO: "operacion_que_no_existe"}
    # ── Listas de moldes anidados ───────────────────────────────────────
    if hoja == "items":
        if herramienta == "registrar_pedido":
            return {VALIDO: [{"que": cat, "cantidad": 2}],
                    BORDE: [{"que": cat, "cantidad": 1}],
                    TORCIDO: []}
        return {VALIDO: [{"product_id": p1, "cantidad": 2}],
                BORDE: [{"product_id": p1, "cantidad": 1}],
                TORCIDO: [{"product_id": _ID_FANTASMA, "cantidad": 2}]}
    if hoja in ("pago", "reparto_pago"):
        return {VALIDO: [{"medio": "transferencia", "porcentaje": 70},
                         {"medio": "mercado pago", "porcentaje": 30}],
                BORDE: [{"medio": "transferencia", "porcentaje": 100}],
                # No suman 100: el reparto que le cambia al cliente lo que paga.
                TORCIDO: [{"medio": "transferencia", "porcentaje": 70},
                          {"medio": "mercado pago", "porcentaje": 70}]}
    if hoja == "filtros":
        return {VALIDO: [{"campo": "pais_fabricacion",
                          "operador": "no_contiene", "valor": "china"}],
                BORDE: [],
                TORCIDO: [{"campo": "campo_que_no_existe",
                           "operador": "explota", "valor": "-1"}]}
    if hoja == "medio":
        return {VALIDO: "transferencia", BORDE: "", TORCIDO: "bitcoin"}
    return {}


def _base(nombre: str, m: dict) -> dict:
    """Los argumentos VALIDOS minimos de una herramienta: el punto de partida
    sobre el que se cambia UN campo por vez. Cambiar todo junto no permitiria
    saber cual valor rompio."""
    modelo = herramientas()[nombre]
    args = {}
    for campo in modelo.model_fields:
        v = valores(f"{nombre}.{campo}", m)
        if v:
            args[campo] = v[VALIDO]
    # LA BASE LLEVA TODOS LOS CAMPOS QUE TIENEN VALOR, y no solo los
    # obligatorios. Con los opcionales afuera, la lista anidada donde vive el
    # campo -los `filtros` de una busqueda, el `reparto_pago` de un pedido- no
    # existia en la base y sus campos quedaban sin barrer: 24 celdas de 126, el
    # 19%, invisibles. Es exactamente la forma de "a medias" que hay que
    # terminar.
    return args


def casos(m: dict | None = None) -> list:
    """Todos los casos del barrido: {herramienta, campo, clase, args}.

    UNO A LA VEZ, a proposito: se parte de los argumentos validos y se cambia
    UN campo por su valor de esa clase. Asi, cuando una propiedad se rompe, el
    caso dice exactamente que campo y con que valor, y el arreglo no se busca a
    ciegas. Los campos anidados se cambian adentro del primer elemento de su
    lista."""
    m = m or _muestra()
    fuera = []
    for nombre, modelo in herramientas().items():
        base = _base(nombre, m)
        # El caso BASE, todo valido: la herramienta tiene que contestar bien.
        fuera.append({"herramienta": nombre, "campo": "(base)",
                      "clase": VALIDO, "args": dict(base)})
        for campo in modelo.model_fields:
            vals = valores(f"{nombre}.{campo}", m)
            for clase, v in vals.items():
                args = dict(base)
                args[campo] = v
                fuera.append({"herramienta": nombre, "campo": campo,
                              "clase": clase, "args": args})
        # Los anidados: se cambia el campo adentro del primer elemento.
        for sub_nombre, sub in _anidados(modelo).items():
            lista = next((c for c in modelo.model_fields
                          if isinstance(base.get(c), list) and base.get(c)
                          and isinstance(base[c][0], dict)
                          and set(sub.model_fields) & set(base[c][0])), None)
            if not lista:
                continue
            for campo in sub.model_fields:
                vals = valores(f"{nombre}.{sub_nombre}.{campo}", m)
                for clase, v in vals.items():
                    args = dict(base)
                    fila = dict(base[lista][0])
                    fila[campo] = v
                    args[lista] = [fila] + [dict(x) for x in base[lista][1:]]
                    fuera.append({"herramienta": nombre,
                                  "campo": f"{sub_nombre}.{campo}",
                                  "clase": clase, "args": args})
    return fuera


# Las herramientas que tocan PLATA. Sobre estas no alcanza con cambiar un campo
# por vez: los errores de plata viven en la INTERACCION de dos campos, y el
# error real del 12-ago -destino compuesto MAS reparto de pago- fue exactamente
# eso. Se barren de a pares, que es lo que la practica llama pairwise y lo que
# caza la enorme mayoria de los defectos de interaccion.
CON_PLATA = ("armar_presupuesto",)


def pares(m: dict | None = None) -> list:
    """Los casos de DOS campos torcidos a la vez sobre las herramientas que
    tocan plata. Complementa a `casos`, que cambia uno por vez.

    POR QUE HACE FALTA. Un campo torcido solo suele caer en un camino de
    rechazo limpio. Dos juntos se cruzan: un destino compuesto con un reparto
    de pago invalido, una cantidad cero con un id fantasma. Ahi es donde una
    guardia tapa a la otra y el resultado sale mal sin que nadie lo vea."""
    import itertools
    m = m or _muestra()
    fuera = []
    for nombre in CON_PLATA:
        modelo = herramientas()[nombre]
        base = _base(nombre, m)
        # Cada dimension: un campo raiz, o un campo de un molde anidado con la
        # lista donde vive.
        dims = []
        for campo in modelo.model_fields:
            if valores(f"{nombre}.{campo}", m):
                dims.append((campo, None))
        for sub_nombre, sub in _anidados(modelo).items():
            lista = next((c for c in modelo.model_fields
                          if isinstance(base.get(c), list) and base.get(c)
                          and isinstance(base[c][0], dict)
                          and set(sub.model_fields) & set(base[c][0])), None)
            if not lista:
                continue
            for campo in sub.model_fields:
                if valores(f"{nombre}.{sub_nombre}.{campo}", m):
                    dims.append((campo, lista))
        for (c1, l1), (c2, l2) in itertools.combinations(dims, 2):
            if l1 and l2 and l1 == l2 and c1 == c2:
                continue
            v1 = valores(f"{nombre}.{c1}", m) or valores(
                f"{nombre}.X.{c1}", m)
            v2 = valores(f"{nombre}.{c2}", m) or valores(
                f"{nombre}.X.{c2}", m)
            for k1 in CLASES:
                for k2 in CLASES:
                    if k1 == VALIDO and k2 == VALIDO:
                        continue
                    args = {k: (list(v) if isinstance(v, list) else v)
                            for k, v in base.items()}
                    for campo, lista, clase, vals in ((c1, l1, k1, v1),
                                                      (c2, l2, k2, v2)):
                        if clase not in vals:
                            continue
                        if lista:
                            fila = dict(args[lista][0])
                            fila[campo] = vals[clase]
                            args[lista] = [fila] + [dict(x)
                                                    for x in args[lista][1:]]
                        else:
                            args[campo] = vals[clase]
                    fuera.append({"herramienta": nombre,
                                  "campo": f"{c1}+{c2}",
                                  "clase": f"{k1}+{k2}", "args": args})
    return fuera


def cobertura(casos_corridos: list) -> dict:
    """El numero, calculado: que celdas campo-por-clase de la superficie
    quedaron ejercitadas y cuales no. `pendientes` es la lista exacta de lo que
    falta, con nombre de herramienta y de campo."""
    total = {f"{c}|{k}" for c in superficie() for k in CLASES}
    hechas = set()
    for c in casos_corridos:
        if c["campo"] == "(base)":
            continue
        hechas.add(f"{c['herramienta']}.{c['campo']}|{c['clase']}")
    faltan = sorted(total - hechas)
    return {"celdas": len(total), "cubiertas": len(total) - len(faltan),
            "pendientes": faltan,
            "porcentaje": round(100 * (len(total) - len(faltan)) / len(total), 1)
            if total else 0.0}
