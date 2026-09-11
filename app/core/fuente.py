"""LA FUENTE, SIN INTERMEDIARIOS — lo que el codigo pone delante del modelo.

El 11-sep-2026 se apago la arquitectura de moldes, mesa y dos llamadas. Lo que
queda es esto: ANTES de hablarle al modelo, el codigo busca en la fuente y le
pone delante lo poco que hace falta para contestar. El modelo no elige
herramientas, no declara campos y no nombra ids: lee fichas y politicas que ya
vienen certificadas.

Dos puertas, y ninguna mas:

  fichas_relevantes(mensaje)   los productos del catalogo que el mensaje nombra
  politicas_relevantes(mensaje) los temas de la casa que el mensaje pisa

La certificacion de temas viene TAL CUAL de la herramienta vieja, porque es una
de las diez deterministas que quedan prendidas y su logica esta medida: tres
veredictos, y ante `ambiguous` no se elige, se sirven todos. Lo que se borro es
lo que la envolvia.

NADA DE ESTO ESCRIBE UN NUMERO DE PLATA. Los precios salen de la ficha como
dato, y quien los pone en el texto es `app/core/numeros.py`.
"""
import re
import unicodedata

from app.logger import get_logger

log = get_logger(__name__)


def _norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


def temas_consultables(tienda_id: str) -> list[str]:
    """EL ENUM UNICO de temas: la FAQ y la base de conocimiento en UNA lista.

    Hasta el 4-ago eran dos enums en dos herramientas -`consultar_politica` con
    los cincuenta temas de la FAQ y `consultar_criterio` con los ciento seis de
    la base-, y VEINTISIETE nombres estaban en las dos. Para esos veintisiete el
    modelo tenia que adivinar cual de las dos mitades de la casa guardaba la
    respuesta, y cada mitad devolvia solo la suya: `descuento_transferencia` por
    politica trae el diez por ciento real, y por criterio trae una prosa sin un
    solo digito que literalmente dice que el numero lo trae la otra. Medido con
    el modelo vivo el 4-ago: ante "esta caro, me haces precio si llevo dos? y
    con transferencia cuanto queda" pidio el criterio, o sea la mitad que NO
    puede tener el porcentaje.

    Eso no era un error del modelo: era pedirle que aprendiera nuestro
    archivero. Un tema es un tema; de que archivo sale es asunto del codigo."""
    from app.storage.firestore_client import get_all_faq
    from app.core.guia_venta_prosa import temas as temas_criterio
    faq = get_all_faq(tienda_id=tienda_id) or {}
    # Los temas de criterio incluyen los que solo tienen MOVIDA -queja,
    # despedida, postergacion-: sin ellos en el enum el modelo no puede pedir
    # lo unico que la fuente escribio para esas situaciones.
    return sorted(set(faq.keys()) | set(temas_criterio()))


# ── LA CERTIFICACION DE TEMAS: la regla cero, aplicada a un tema ────────────
#
# POR QUE EL ENUM SALIO (FICHA 06, 23-ago-2026). Los 129 temas pesaban 2.299
# bytes, el bloque mas caro de todo el esquema, y viajaban en CADA llamada al
# decisor. Sacarlo NO es aflojar la atadura: el modelo nombra el tema con LAS
# PALABRAS DEL CLIENTE y el codigo lo certifica contra las señas que la fuente
# ya tiene escritas -las keywords de la FAQ y los disparadores de la base-.
#
# ES LA REGLA CERO DE `CLAUDE.md` UN NIVEL MAS ARRIBA: la identidad la decide
# una funcion determinista con tres veredictos de primera clase, `exists`,
# `ambiguous` y `not_found`, y `not_found` no es un error, es un resultado.
#
# QUE PASA CON `ambiguous`, Y ES LO UNICO QUE SE APARTA DE LA FICHA. La ficha
# pedia REPREGUNTAR. Repreguntar aca seria preguntarle al CLIENTE cual de dos
# nombres de nuestro archivero quiso decir -"¿garantia o garantia_como_usar?"-,
# que es exactamente la falla que este repo ya diagnostico y arreglo el 4-ago
# al unificar los dos enums: "eso no era un error del modelo, era pedirle que
# aprendiera nuestro archivero". El cliente no lo sabe y no tiene por que.
#
# Asi que ante `ambiguous` NO SE ELIGE -que es la parte que importa de la regla
# cero- y se sirven TODOS los candidatos: el modelo recibe las dos politicas
# enteras, con sus numeros reales, y contesta la que le preguntaron. No hay
# invento posible: las dos vienen de la fuente. Y queda logueado.
# LAS PALABRAS QUE NO NOMBRAN NINGUN TEMA. Van los pronombres y los
# cuantificadores, no solo los articulos, y eso lo pidio un caso medido: la
# fuente guarda 'otro a' como disparador de `multidestino`, asi que "afirma otro
# precio" resolvia a multidestino por la palabra "otro". Un pronombre esta en
# cualquier frase y por lo tanto no distingue nada; dejarlo adentro convierte al
# tema que lo tenga de seña en el comodin que se lleva media casa.
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
    """Las palabras con las que se compara un tema, por RAIZ CORTA y sin las que
    no distinguen nada.

    LA RAIZ ES LA MISMA QUE USA `indice_turno._aparece` -de cinco letras para
    arriba alcanza el prefijo de cuatro- y es la misma por el mismo motivo: lo
    que el cliente dice y lo que la fuente escribio nunca coinciden en la
    conjugacion. "lo pienso" contra "lo piensa", "envio" contra "envios",
    "cancelar" contra "cancelacion". Un cortador de plurales no alcanza: pierde
    el verbo, que es como se dice la mitad de las situaciones de venta."""
    fuera = set()
    for w in _norm(texto).replace("_", " ").replace("/", " ").split():
        w = "".join(c for c in w if c.isalnum())
        # SE DESCARTA POR LA PALABRA ENTERA Y NO POR LA RAIZ, y se probo al
        # reves: con la raiz, "estafa" cae en "esta" —que es una muletilla— y
        # la fuente pierde dos señas de `desconfianza_online` sin que nadie lo
        # note. La lista de abajo lleva por eso las variantes escritas, que es
        # barato y no tiene efectos de borde.
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
    """{veredicto, temas}. `exists` con UN tema, `ambiguous` con los que
    empatan, `not_found` con la lista vacia. Nunca elige entre empatados."""
    pedido = _fichas(nombre)
    if not pedido:
        return {"veredicto": "not_found", "temas": [], "nombre": nombre}
    registro = _senas_por_tema(tienda_id)
    # EL NOMBRE DEL TEMA NO TIENE ATAJO, y sacarselo arreglo cuatro choques que
    # estaban ABIERTOS en PENDIENTE. Con atajo, "cuotas" resolvia a `cuotas` y
    # `cuotas_financiacion` no se servia nunca, aunque reclama esa misma palabra:
    # el nombre de nuestro archivero le ganaba a la fuente. El nombre ya viaja
    # como una seña mas en `_senas_por_tema`, asi que empata con la otra y el
    # veredicto sale `ambiguous`, que es lo que de verdad es.
    # LA PALABRA PROPIA, que es la unica que puede desempatar sola. Es la misma
    # idea que la guia vieja usaba para elegir que seña imprimir: una palabra
    # que reclaman veinte temas -"pedido", "envio", "compra"- no dice nada; una
    # que reclaman uno o dos -"queja", "cancelar", "factura"- lo nombra.
    reclaman: dict = {}
    for tema, señas in registro.items():
        for f in señas:
            for w in f:
                reclaman.setdefault(w, set()).add(tema)
    propias = {w for w, t in reclaman.items() if len(t) <= 3}
    puntajes = {}
    for tema, señas in registro.items():
        # DOS NIVELES, Y EL DE ARRIBA APLASTA AL DE ABAJO. Una seña que entra
        # ENTERA es que el cliente dijo esa frase; una palabra propia suelta es
        # apenas un indicio. Multiplicar por diez el primero hace que el indicio
        # nunca le gane a la frase, sin tener que ordenar por dos claves.
        #
        # Y EL PUNTAJE ES EL DE LA SEÑA MAS LARGA, no la suma: sumar premia al
        # tema que tiene muchas señas cortas, que es justo el generico -`envios`-
        # contra el especifico -`plazo_envio`-. La regla de la fuente es que gana
        # el mas especifico, y especifico es la seña que cubre MAS de lo que dijo
        # el cliente con una sola frase.
        mejor = 0
        for f in señas:
            comun = f & pedido
            if not comun:
                continue
            if f <= pedido:
                mejor = max(mejor, 10 * len(f))
            else:
                # EL INDICIO SOLO CUENTA CON PALABRA PROPIA. Sin este filtro
                # "cancelar la compra" pegaria en los treinta temas que nombran
                # "compra" y todo saldria ambiguo, que es no certificar nada.
                mejor = max(mejor, len(comun & propias))
        if mejor:
            puntajes[tema] = mejor
    if not puntajes:
        return {"veredicto": "not_found", "temas": [], "nombre": nombre}
    tope = max(puntajes.values())
    empatan = sorted(t for t, v in puntajes.items() if v == tope)
    # NO HAY DESEMPATE, Y SE PROBO UNO. Preferir al tema cuyo NOMBRE entero cabe
    # en lo que dijo el cliente arregla un caso feo -"compatibilidad" empata con
    # media casa porque la raiz "comp" es tambien comprar y comparar- y ROMPE
    # siete: con ese desempate "cuotas" vuelve a ganarle a `cuotas_financiacion`
    # y "regalo" a `envoltorio_regalo`, que son justo los choques que estaban
    # ABIERTOS en PENDIENTE desde el 12-ago. Medido: 0 choques ciegos sin el
    # desempate, 7 con el. Entre servir un tema de mas y no servir el que el
    # cliente pregunto, gana servir de mas: la fuente no miente, la ausencia si.
    if len(empatan) == 1:
        return {"veredicto": "exists", "temas": empatan, "nombre": nombre}
    return {"veredicto": "ambiguous", "temas": empatan[:3], "nombre": nombre}


def certificar_temas(nombres: list, tienda_id: str) -> dict:
    """La puerta unica: lo que el modelo nombro libre, certificado. Se loguea
    CADA vez que un tema no resuelve, que es la unica forma de que un agujero
    de la fuente se vea en el log y no lo pague el cliente."""
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
#
# El certificador de identidad -`pedido_helpers.certificar_producto`- sigue
# siendo quien dice si un producto EXISTE. Esto es el paso de antes: acotar los
# 880 del catalogo a los pocos que el mensaje puede estar nombrando, para que el
# prompt no lleve el catalogo entero ni lleve nada.

TOPE_FICHAS = 5


def _norm_cat(c) -> str:
    return _norm(str(c or ""))


def _plata(n) -> str:
    """El precio como se escribe, no como se guarda. Vacio si no hay precio:
    una ficha sin precio no puede inventar uno."""
    try:
        return "$" + f"{int(round(float(n))):,}".replace(",", ".")
    except (TypeError, ValueError):
        return ""


def _ficha_corta(prod: dict) -> dict:
    """La ficha que ve el modelo. Corta a proposito: id, nombre, categoria,
    stock, precio y los campos que la fuente declaro para ese rubro."""
    from app.core.fuente_producto import campos_ficha
    precio = prod.get("precio_ars")
    fuera = {
        "id": prod.get("id"),
        "nombre": prod.get("nombre"),
        "categoria": prod.get("categoria"),
        "stock": prod.get("stock"),
        # EL PRECIO VIAJA YA ESCRITO, y es a proposito: el modelo lo COPIA en
        # vez de formatearlo. Un numero pelado invita a redondearlo, a pasarlo
        # a miles o a sumarle el envio de memoria; una cadena se copia igual.
        # El numero crudo queda al lado para el codigo, que es quien suma.
        "precio": _plata(precio),
        "precio_ars": precio,
    }
    for campo, valor in (campos_ficha(prod) or []):
        if campo in fuera or valor in (None, ""):
            continue
        fuera[str(campo)] = valor
    return fuera


def fichas_relevantes(mensaje: str, tienda_id: str,
                      tope: int = TOPE_FICHAS) -> list[dict]:
    """Las fichas del catalogo que el mensaje nombra, de mas a menos relevante.

    La relevancia la calcula `filtros_catalogo.relevancia`, que ya pesa por
    rareza: una palabra que esta en los 880 no distingue nada y una que esta en
    dos los nombra. Si nada pasa el piso, vuelve vacio: que el modelo no tenga
    ninguna ficha delante es un resultado valido y es lo que le hace decir que
    no lo tenemos.
    """
    from app.core.filtros_catalogo import (categorias_nombradas, ordenar,
                                           orden_tiene_sentido,
                                           pesos_por_rareza, relevancia,
                                           resolver_orden)
    from app.storage.firestore_client import get_all_products
    txt = (mensaje or "").strip()
    if not txt:
        return []
    try:
        catalogo = get_all_products(tienda_id=tienda_id) or []
    except Exception as e:  # noqa: BLE001 — sin catalogo se contesta sin fichas
        log.warning("fuente_catalogo_error", error=f"{type(e).__name__}: {e}")
        return []
    if not catalogo:
        return []
    # ── EL EXTREMO NO SE BUSCA POR PARECIDO, SE ORDENA ──────────────────
    #
    # MEDIDO EL 11-SEP: a "cual es el producto mas caro que tienes" la
    # relevancia devolvio cinco memorias RAM cualquiera, porque ninguna palabra
    # del mensaje nombra un producto. "Mas caro" no es un parecido: es un
    # ORDEN, y el orden lo hace el codigo sobre el campo de la fuente.
    #
    # `resolver_orden` solo devuelve algo si el cliente puso el superlativo, y
    # el campo sale de `campos_filtrables`, o sea de la fuente viva. Si el
    # cliente nombro un rubro, el orden se acota a ese rubro; si no, va sobre
    # el catalogo entero, que es lo que la pregunta pide.
    orden = resolver_orden(txt, tienda_id)
    if orden and orden.get("campo"):
        universo = catalogo
        rubros = [_norm_cat(c) for c in categorias_nombradas(txt, tienda_id)]
        if rubros:
            universo = [p for p in catalogo
                        if _norm_cat(p.get("categoria")) in rubros]
        if universo and orden_tiene_sentido(universo, orden["campo"], tienda_id):
            fuera = [_ficha_corta(p) for p in ordenar(
                universo, orden["campo"], orden.get("direccion") or "min",
                tienda_id)[:tope]]
            log.info("fuente_fichas_por_orden", campo=orden["campo"],
                     direccion=orden.get("direccion"), de=len(universo),
                     cuantas=len(fuera), ids=[f.get("id") for f in fuera])
            return fuera

    raras = pesos_por_rareza(catalogo, txt)
    puntuados = []
    for p in catalogo:
        r = relevancia(p, txt, raras)
        if r > 0:
            puntuados.append((r, p))
    if not puntuados:
        return []
    puntuados.sort(key=lambda x: (-x[0], str(x[1].get("nombre") or "")))
    fuera = [_ficha_corta(p) for _, p in puntuados[:tope]]
    log.info("fuente_fichas", cuantas=len(fuera), de=len(puntuados),
             ids=[f.get("id") for f in fuera])
    return fuera


# ── LAS POLITICAS QUE EL MENSAJE PISA ───────────────────────────────────────

TOPE_TEMAS = 3


def politicas_relevantes(mensaje: str, tienda_id: str,
                         tope: int = TOPE_TEMAS) -> list[dict]:
    """[{tema, texto}] con la politica de la casa ya estampada.

    El tema se certifica con las mismas señas de siempre. Los numeros de la
    politica -una tarifa, un plazo, un porcentaje- los estampa `curadas`, que
    devuelve None si un hueco no resuelve: una politica a medias no se sirve.
    """
    from app.core.curadas import estampar_valores
    from app.storage.firestore_client import get_all_faq
    txt = (mensaje or "").strip()
    if not txt:
        return []
    v = certificar_tema(txt, tienda_id)
    if v["veredicto"] == "not_found":
        log.info("fuente_sin_tema")
        return []
    try:
        faq = get_all_faq(tienda_id=tienda_id) or {}
    except Exception as e:  # noqa: BLE001
        log.warning("fuente_faq_error", error=f"{type(e).__name__}: {e}")
        return []
    fuera = []
    for tema in v["temas"][:tope]:
        dato = faq.get(tema) or {}
        texto = dato.get("respuesta_curada") or ""
        if texto:
            texto = estampar_valores(texto, dato) or ""
        if not texto:
            # Sin curada, la prosa de la casa: criterio y movida del mismo tema.
            from app.core.guia_venta_prosa import consultar_guia_venta
            g = consultar_guia_venta(tema) or {}
            texto = " ".join(str(g.get(k) or "") for k in
                             ("texto", "objetivo", "movida")).strip()
        if texto:
            fuera.append({"tema": tema, "texto": texto})
    log.info("fuente_politicas", veredicto=v["veredicto"],
             temas=[f["tema"] for f in fuera])
    return fuera


# ── EL INVENTARIO: LO QUE EL MODELO TIENE QUE SABER SIEMPRE ────────────────
#
# MEDIDO EN VIVO EL 11-SEP, Y ES LA FALLA QUE MAS DAÑO HIZO DEL CAMINO NUEVO.
# A "¿cuantos productos vendes?" el bot contesto "nuestro catalogo cuenta con 5
# modelos diferentes de memorias RAM". Hay 880 productos en 22 categorias.
#
# No mintio el modelo: mintio el prompt. La etapa uno le mandaba CINCO fichas
# elegidas por relevancia con el encabezado "es todo lo que existe", asi que
# ante una pregunta sobre el catalogo ENTERO -cuantos vendes, que vendes, que
# categorias tenes- contestaba sobre las cinco que le tocaron.
#
# El inventario es la respuesta determinista a esas preguntas, y viaja SIEMPRE:
# son dos renglones y no depende de que la relevancia acierte.

_INVENTARIO: dict = {}


def inventario(tienda_id: str) -> dict:
    """{productos, categorias: [(nombre, cuantos)], precio_min, precio_max}.

    Se arma una vez por tienda y no se vuelve a tocar: el catalogo ya vive
    cacheado en `firestore_client` y esto son cuentas sobre esa lista."""
    if tienda_id in _INVENTARIO:
        return _INVENTARIO[tienda_id]
    try:
        from app.storage.firestore_client import get_all_products
        catalogo = get_all_products(tienda_id=tienda_id) or []
    except Exception as e:  # noqa: BLE001
        log.warning("fuente_inventario_error", error=f"{type(e).__name__}: {e}")
        return {}
    cuenta: dict = {}
    precios = []
    for p in catalogo:
        cat = str(p.get("categoria") or "").strip()
        if cat:
            cuenta[cat] = cuenta.get(cat, 0) + 1
        v = p.get("precio_ars")
        if v:
            try:
                precios.append(int(v))
            except (TypeError, ValueError):
                pass
    out = {
        "productos": len(catalogo),
        "categorias": sorted(cuenta.items(), key=lambda t: (-t[1], t[0])),
        "precio_min": min(precios) if precios else None,
        "precio_max": max(precios) if precios else None,
    }
    _INVENTARIO[tienda_id] = out
    log.info("fuente_inventario", productos=out["productos"],
             categorias=len(out["categorias"]))
    return out


def texto_inventario(tienda_id: str) -> str:
    """El inventario como se lo lee el modelo. Vacio si no se pudo armar."""
    inv = inventario(tienda_id)
    if not inv.get("productos"):
        return ""
    cats = ", ".join(f"{c} ({n})" for c, n in inv["categorias"])
    linea = (f"EL CATALOGO ENTERO son {inv['productos']} productos en "
             f"{len(inv['categorias'])} categorias: {cats}.")
    if inv.get("precio_min") and inv.get("precio_max"):
        linea += (f" Los precios van de {_plata(inv['precio_min'])} a "
                  f"{_plata(inv['precio_max'])}.")
    return linea
