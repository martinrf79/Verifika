"""LA FUENTE, SIN INTERMEDIARIOS — lo que el codigo pone delante del modelo."""
import unicodedata

from app.logger import get_logger
from app.core.calculadora import _money as _plata

log = get_logger(__name__)


def _norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


def temas_consultables(tienda_id: str) -> list[str]:
    """EL ENUM UNICO de temas: la FAQ y la base de conocimiento en UNA lista."""
    from app.storage.firestore_client import get_all_faq
    from app.core.guia_venta_prosa import temas as temas_criterio
    faq = get_all_faq(tienda_id=tienda_id) or {}
    # Los temas de criterio incluyen los que solo tienen MOVIDA -queja, despedida, postergacion-: sin ellos en
    # el enum el modelo no puede pedir lo unico que la fuente escribio para esas situaciones.
    return sorted(set(faq.keys()) | set(temas_criterio()))


# LA VALVULA DE ESCAPE DEL ENUM, y es la regla 10.0 aplicada a un tema: el "no" es un resultado de primera
# clase, no un error.
SIN_TEMA = "la_casa_no_lo_tiene_escrito"


# ── LA CERTIFICACION DE TEMAS: la regla cero, aplicada a un tema ────────────
_SIN_SEÑA = frozenset(("que", "como", "cual", "cuando", "donde", "para", "por",
             "con", "sin", "del", "los", "las", "una", "uno", "mas",
             "muy", "hay", "eso", "esa", "ese", "esto", "tiene",
             "tienen", "puedo", "quiero", "hacen", "hace", "son",
             "esta", "estan", "pero", "y", "o", "el", "la", "de",
             "otro", "otra", "otros", "otras", "todo", "toda", "todos",
             "cada", "algo", "alguno", "mismo", "misma", "aca", "alla",
             "ahi", "sobre", "tambien", "entonces", "ahora", "cosa",
             "cosas", "otro/a", "algun", "alguna"))


def _fichas(texto) -> set:
    """Las palabras con las que se compara un tema, por RAIZ CORTA y sin las que no distinguen nada."""
    fuera = set()
    for w in _norm(texto).replace("_", " ").replace("/", " ").split():
        w = "".join(c for c in w if c.isalnum())
        # SE DESCARTA POR LA PALABRA ENTERA Y NO POR LA RAIZ, y se probo al reves: con la raiz, "estafa" cae
        # en "esta" —que es una muletilla— y la fuente pierde dos señas de `desconfianza_online` sin que nadie
        # lo note.
        if len(w) < 3 or w in _SIN_SEÑA:
            continue
        fuera.add(w[:4] if len(w) >= 5 else w)
    return fuera


def _senas_por_tema(tienda_id: str) -> dict:
    """{tema: [conjuntos de fichas]}. La seña de cada tema sale de la fuente que
    lo define: keywords si es de la FAQ, disparadores si es de la base."""
    from app.core.guia_venta_prosa import disparadores_de
    from app.storage.firestore_client import get_all_faq
    faq = get_all_faq(tienda_id=tienda_id) or {}
    fuera = {}
    for tema in temas_consultables(tienda_id):
        señas = [_fichas(tema)]
        for k in ((faq.get(tema, {}).get("keywords") or [])
                  + disparadores_de(tema)):
            f = _fichas(k)
            if f:
                señas.append(f)
        fuera[tema] = señas
    return fuera


def certificar_tema(nombre: str, tienda_id: str) -> dict:
    """{veredicto, temas}. `exists` con UN tema, `ambiguous` con los que empatan, `not_found` con la lista vacia."""
    pedido = _fichas(nombre)
    if not pedido:
        return {"veredicto": "not_found", "temas": [], "nombre": nombre}
    registro = _senas_por_tema(tienda_id)
    # EL NOMBRE DEL TEMA NO TIENE ATAJO, y sacarselo arreglo cuatro choques que estaban ABIERTOS en PENDIENTE.
    reclaman: dict = {}
    for tema, señas in registro.items():
        for f in señas:
            for w in f:
                reclaman.setdefault(w, set()).add(tema)
    propias = {w for w, t in reclaman.items() if len(t) <= 3}
    puntajes = {}
    for tema, señas in registro.items():
        # DOS NIVELES, Y EL DE ARRIBA APLASTA AL DE ABAJO.
        mejor = 0
        for f in señas:
            comun = f & pedido
            if not comun:
                continue
            if f <= pedido:
                mejor = max(mejor, 10 * len(f))
            else:
                # EL INDICIO SOLO CUENTA CON PALABRA PROPIA.
                mejor = max(mejor, len(comun & propias))
        if mejor:
            puntajes[tema] = mejor
    if not puntajes:
        return {"veredicto": "not_found", "temas": [], "nombre": nombre}
    tope = max(puntajes.values())
    empatan = sorted(t for t, v in puntajes.items() if v == tope)
    # NO HAY DESEMPATE, Y SE PROBO UNO. Preferir al tema cuyo NOMBRE entero cabe en lo que dijo el cliente
    # arregla un caso feo -"compatibilidad" empata con media casa porque la raiz "comp" es tambien comprar y
    # comparar- y ROMPE siete: con ese desempate "cuotas" vuelve a ganarle a `cuotas_financiacion` y "regalo"
    # a `envoltorio_regalo`, que son justo los choques que estaban ABIERTOS en PENDIENTE desde el 12-ago.
    if len(empatan) == 1:
        return {"veredicto": "exists", "temas": empatan, "nombre": nombre}
    return {"veredicto": "ambiguous", "temas": empatan[:3], "nombre": nombre}


def certificar_temas(nombres: list, tienda_id: str) -> dict:
    """La puerta unica: lo que el modelo nombro libre, certificado."""
    ciertos: list = []
    ambiguos: list = []
    perdidos: list = []
    for n in (nombres or []):
        if not str(n or "").strip():
            continue
        v = certificar_tema(str(n), tienda_id)
        if v["veredicto"] == "not_found":
            perdidos.append(str(n))
            continue
        if v["veredicto"] == "ambiguous":
            ambiguos.append((str(n), v["temas"]))
        for t in v["temas"]:
            if t not in ciertos:
                ciertos.append(t)
    if ambiguos or perdidos:
        log.info("tema_no_resuelto", ambiguos=ambiguos[:4],
                 sin_resolver=perdidos[:4])
    return {"temas": ciertos, "ambiguos": ambiguos, "sin_resolver": perdidos}


# ── LOS PRODUCTOS QUE EL MENSAJE NOMBRA ─────────────────────────────────────


# LA PROSA DE LA FICHA, y es lo que se PIDE desde el 14-sep.
_SIEMPRE = ("nombre", "modelo", "caracteristicas_extra")


def _campos_prosa() -> tuple:
    from app.core.fuente_producto import CAMPOS_TEXTO
    return tuple(c for c in CAMPOS_TEXTO if c not in _SIEMPRE)


def _ficha_corta(prod: dict, cantidad: int = 1, specs_pedidas=None,
                 detalle: bool = False) -> dict:
    """La ficha que ve el modelo. Corta a proposito: id, nombre, categoria, stock, precio y los campos que la
    fuente declaro para ese rubro."""
    from app.core.fuente_producto import campos_ficha
    precio = prod.get("precio_ars")
    fuera = {
        "id": prod.get("id"),
        "nombre": prod.get("nombre"),
        "categoria": prod.get("categoria"),
        "stock": prod.get("stock"),
        # EL PRECIO VIAJA YA ESCRITO, y es a proposito: el modelo lo COPIA en vez de formatearlo.
        "precio": _plata(precio),
        "precio_ars": precio,
    }
    if cantidad and cantidad > 1:
        # SOLO LA CANTIDAD. El SUBTOTAL lo estampa `motor._con_la_cuenta` llamando a `calculadora`, que es la
        # herramienta de la plata: una multiplicacion suelta escrita aca seria un segundo lugar donde el repo
        # hace cuentas, y por cada cosa que se prende se apaga una.
        fuera["cantidad"] = cantidad
    # ── LA PROSA SE PIDE, LAS SPECS VIAJAN (14-sep-2026) ────────────────
    prosa = _campos_prosa()
    for campo, valor in (campos_ficha(prod) or []):
        if campo in fuera or valor in (None, ""):
            continue
        if not detalle and campo in prosa:
            continue
        fuera[str(campo)] = valor
    # LAS SPECS AL FINAL Y EN SU PROPIA CAJA. Anidadas y no desparramadas entre los campos de arriba: asi el
    # modelo ve de un vistazo que es dato duro de la ficha y que es prosa, y un campo nuevo del catalogo no
    # puede pisar a `id` ni a `precio` por llamarse igual.
    specs = prod.get("specs") or {}
    if isinstance(specs, dict) and specs:
        if specs_pedidas is None:
            elegidas = dict(specs)
        else:
            # El campo que se pidio y la ficha no tiene NO se rellena con nada: que falte es el dato -es la
            # respuesta 2, "no tengo ese dato"- y un vacio inventado ahi seria peor que la ausencia.
            pedidas = {_norm(str(x)) for x in (specs_pedidas or [])}
            elegidas = {k: v for k, v in specs.items() if _norm(str(k)) in pedidas}
        elegidas = {str(k): v for k, v in elegidas.items() if v not in (None, "")}
        if elegidas:
            fuera["specs"] = elegidas
    return fuera


# SUBE DE 3 A 6 EL 20-sep, y el motivo entero esta en `motor.TOPE_TEMAS`: los campos `temas` y `criterio` del
# tablero se fundieron en uno, asi que un solo tope tiene que cubrir lo que antes cubrian dos de tres.
TOPE_TEMAS = 6

# Cuantas entradas de criterio vuelven en una llamada.
TOPE_CRITERIO = 3


def _texto_del_tema(tema: str, faq: dict, campo: str = "respuesta_curada") -> str:
    """La politica de la casa sobre ese tema, con los numeros ya estampados."""
    from app.core.curadas import estampar_valores
    dato = faq.get(tema) or {}
    texto = dato.get(campo) or ""
    if texto:
        texto = estampar_valores(texto, dato) or ""
    return texto


def _criterio_del_tema(tema: str) -> dict:
    """LO QUE LA CASA TIENE ESCRITO SOBRE ESE TEMA: para que sirve, cual conviene, y la movida con la que se
    conduce la situacion si la fuente la escribio."""
    from app.core.guia_venta_prosa import consultar_guia_venta
    g = consultar_guia_venta(tema) or {}
    if str(g.get("tema") or "") != tema:
        return {}
    fuera = {"tema": tema}
    for clave, campo in (("texto", "texto"), ("objetivo", "objetivo"),
                         ("movida", "movida"), ("cuando_no", "escape")):
        v = str(g.get(campo) or "").strip()
        if v:
            fuera[clave] = v
    return fuera if len(fuera) > 1 else {}


def _de_la_casa(pedidos: list, faq: dict, tienda_id: str, tope: int,
                evento: str, con_base: bool = False) -> dict:
    """EL REPARTO POR AREA: de cada tema certificado, la boca que lo contesta. `con_base` suma la respuesta llana de la
    FAQ, sin la invitacion de venta de la curada, para quien ya tiene el pedido armado."""
    v = certificar_temas(pedidos, tienda_id)
    politicas, criterio, sin_resolver = [], [], list(v["sin_resolver"])
    for tema in v["temas"][:tope]:
        texto = _texto_del_tema(tema, faq)
        if texto:
            politicas.append({"tema": tema, "texto": texto} if not con_base
                             else {"tema": tema, "texto": texto, "base": _texto_del_tema(tema, faq, "respuesta")})
            continue
        c = _criterio_del_tema(tema)
        if c:
            criterio.append(c)
            continue
        sin_resolver.append(tema)
    log.info(evento, pidio=pedidos[:4],
             temas=[p["tema"] for p in politicas],
             criterio=[c["tema"] for c in criterio],
             ambiguos=[a[0] for a in v["ambiguos"]][:3],
             sin_resolver=sin_resolver[:3])
    return {"politicas": politicas, "criterio": criterio,
            "sin_resolver": sin_resolver}


def criterio_de(nombres: list, tienda_id: str,
                tope: int = TOPE_CRITERIO) -> dict:
    """LA BOCA CRITERIO, CERTIFICADA. Es el componente 15 de la FICHA 52 y lo unico que le faltaba era el cable."""
    from app.storage.firestore_client import get_all_faq
    pedidos = [str(n).strip() for n in (nombres or []) if str(n or "").strip()]
    if not pedidos:
        return {"politicas": [], "criterio": [], "sin_resolver": []}
    try:
        faq = get_all_faq(tienda_id=tienda_id) or {}
    except Exception as e:  # noqa: BLE001 — sin FAQ se sirve el criterio solo
        log.warning("fuente_faq_error", error=f"{type(e).__name__}: {e}")
        faq = {}
    return _de_la_casa(pedidos, faq, tienda_id, tope, "fuente_criterio")


def politicas_de(nombres: list, tienda_id: str, tope: int = TOPE_TEMAS, con_base: bool = False) -> dict:
    """LO QUE EL MODELO NOMBRO, CERTIFICADO. Es el mapa 3 de la FICHA 50."""
    from app.storage.firestore_client import get_all_faq
    pedidos = [str(n).strip() for n in (nombres or []) if str(n or "").strip()]
    if not pedidos:
        return {"politicas": [], "criterio": [], "sin_resolver": []}
    try:
        faq = get_all_faq(tienda_id=tienda_id) or {}
    except Exception as e:  # noqa: BLE001 — sin FAQ no se inventa una politica
        log.warning("fuente_faq_error", error=f"{type(e).__name__}: {e}")
        return {"politicas": [], "criterio": [], "sin_resolver": pedidos}
    return _de_la_casa(pedidos, faq, tienda_id, tope, "fuente_politicas", con_base)


# ── EL INVENTARIO: LO QUE EL MODELO TIENE QUE SABER SIEMPRE ────────────────


def inventario(tienda_id: str) -> dict:
    """{productos, categorias: [(nombre, cuantos)], precio_min, precio_max}."""
    from app.core.filtros_catalogo import recorrida
    r = recorrida(tienda_id)
    if not r.get("productos"):
        return {}
    return {k: r[k] for k in
            ("productos", "categorias", "precio_min", "precio_max")}


# ── EL ENVIO: EL MAPA 2 DE LA FICHA 50, Y LA TARIFA YA COTIZADA ────────────


def _cotizar(texto: str) -> dict:
    """La tarifa de ese texto, o {} si no clasifica."""
    from app.core.calculadora import cotizar_envio
    if not str(texto or "").strip():
        return {}
    try:
        r = cotizar_envio(localidad=texto) or {}
    except Exception as e:  # noqa: BLE001 — sin tarifa no se inventa una
        log.warning("envio_cotizar_error", error=f"{type(e).__name__}: {e}")
        return {}
    return r if r.get("ok") else {}


def _destino_legible(r: dict) -> str:
    """COMO SE LE NOMBRA AL CLIENTE: la palabra que EL uso, si la dijo."""
    dicho = str(r.get("dicho") or "").strip()
    if dicho:
        return dicho
    return _destino_estable(r)


def _destino_estable(r: dict) -> str:
    """COMO SE GUARDA para el turno siguiente: la provincia, o la zona."""
    prov = str(r.get("provincia") or "").replace("_", " ").strip()
    if prov:
        return prov
    zona = str(r.get("zona") or "").strip()
    return {"caba": "CABA", "gba": "GBA"}.get(zona, zona)


def _plazo_de(zona: str, faq: dict) -> str:
    """El plazo de esa zona, de la FAQ `plazo_envio`."""
    valores = {str(v.get("concepto") or ""): v.get("monto")
               for v in ((faq.get("plazo_envio") or {}).get("valores") or [])}
    clave = "caba" if str(zona or "") in ("caba", "gba") else "interior"
    mn, mx = valores.get(f"dias_{clave}_min"), valores.get(f"dias_{clave}_max")
    if not (isinstance(mn, (int, float)) and isinstance(mx, (int, float))):
        return ""
    return f"Llega en {int(mn)} a {int(mx)} dias habiles desde el pago."


def _umbral_de(faq: dict) -> int:
    """El umbral de envio gratis. Sale de la MISMA funcion que lo aplica en la calculadora, para que el numero
    que el bot publica y el que el codigo cobra no puedan divergir nunca."""
    from app.core.calculadora import _umbral_envio_gratis
    return _umbral_envio_gratis((faq.get("costo_envio") or {}).get("valores"))


def _tabla_interior(tienda_id: str) -> dict:
    """La tarifa por provincia, con el mismo orden de precedencia que usa la calculadora: Firestore pisa al
    default del codigo."""
    from app.config import get_settings as _gs
    from app.storage.firestore_client import get_config
    try:
        propia = (get_config("tarifas_envio", tienda_id=tienda_id) or {}).get(
            "provincias") or {}
    except Exception as e:  # noqa: BLE001 — sin tabla propia, el default
        log.warning("envio_tarifas_error", error=f"{type(e).__name__}: {e}")
        propia = {}
    return {**(_gs().ENVIO_INTERIOR_POR_PROVINCIA or {}), **propia}


def _tarifas(faq: dict, tienda_id: str) -> str:
    """Las zonas que la tienda cotiza, con su tarifa."""
    partes = []
    valores = (faq.get("costo_envio") or {}).get("valores") or []
    metro = next((v for v in valores if any(
        k in str(v.get("concepto") or "").lower()
        for k in ("caba", "gba", "metropol", "amba"))), None)
    if metro and isinstance(metro.get("monto"), (int, float)):
        partes.append(f"a CABA y GBA {_plata(metro['monto'])}")
    montos = [int(m) for m in _tabla_interior(tienda_id).values() if m]
    if montos:
        partes.append(f"al interior segun la provincia, de {_plata(min(montos))} "
                      f"a {_plata(max(montos))}")
    return "; ".join(partes)


# Cuantos destinos se cotizan en una llamada.
TOPE_DESTINOS = 4


# ── LA BOCA DE ENVIO: SE PIDE, YA NO SE EMPUJA (13-sep-2026) ────────────────


def _fila_de(r: dict, nombre: str, faq: dict) -> dict:
    """La fila que ve el modelo: el destino con SU palabra, la tarifa ya escrita, el plazo y el hueco que tiene
    que copiar."""
    monto, zona = int(r.get("monto") or 0), str(r.get("zona") or "")
    visible = _destino_legible({**r, "dicho": nombre})
    return {"destino": visible,
            "costo": _plata(monto),
            "monto_ars": monto,
            "zona": zona,
            "plazo": _plazo_de(zona, faq),
            "escribi": f"{{{{envio:{visible}}}}}"}


def cotizar_destinos(nombres, tienda_id: str,
                     localidad_previa: str = "") -> dict:
    """{filas, gratis_desde, zonas} para los destinos que nombro el modelo."""
    from app.storage.firestore_client import get_all_faq
    try:
        faq = get_all_faq(tienda_id=tienda_id) or {}
    except Exception as e:  # noqa: BLE001 — sin FAQ no hay plazo ni umbral
        log.warning("envio_faq_error", error=f"{type(e).__name__}: {e}")
        faq = {}
    filas, alguno_sin_dato = [], False
    for nombre in [str(n or "").strip() for n in (nombres or [])][:TOPE_DESTINOS]:
        if not nombre:
            continue
        r = _cotizar(nombre)
        if not r and localidad_previa:
            r = _cotizar(f"{nombre}, {localidad_previa}")
        if not r:
            alguno_sin_dato = True
            filas.append({"destino": nombre, "sin_dato":
                          "no puedo clasificar ese lugar: pedile la PROVINCIA "
                          "o el CODIGO POSTAL y volve a preguntarme"})
            continue
        filas.append(_fila_de(r, nombre, faq))
    if not filas:
        return {}
    fuera: dict = {"filas": filas}
    # EL PLAZO QUE ES EL MISMO SE DICE UNA VEZ.
    plazos = {f.get("plazo") for f in filas if f.get("plazo")}
    if len(plazos) == 1 and not any(f.get("sin_dato") for f in filas):
        fuera["plazo"] = plazos.pop()
        for f in filas:
            f.pop("plazo", None)
    umbral = _umbral_de(faq)
    if umbral:
        fuera["gratis_desde"] = _plata(umbral)
    if alguno_sin_dato:
        tarifas = _tarifas(faq, tienda_id)
        if tarifas:
            fuera["zonas"] = f"la tienda cotiza {tarifas}"
    log.info("envio_cotizado", destinos=[f["destino"] for f in filas],
             montos=[f.get("monto_ars") for f in filas])
    return fuera


