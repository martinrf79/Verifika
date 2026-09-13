"""LA FUENTE, SIN INTERMEDIARIOS — lo que el codigo pone delante del modelo.

El 11-sep-2026 se apago la arquitectura de moldes, mesa y dos llamadas. Lo que
queda es esto: ANTES de hablarle al modelo, el codigo busca en la fuente y le
pone delante lo poco que hace falta para contestar. El modelo no elige
herramientas, no declara campos y no nombra ids: lee fichas y politicas que ya
vienen certificadas.

Dos puertas, y ninguna mas:

  fichas_relevantes(mensaje)   los productos del catalogo que el mensaje nombra
  politicas_de(nombres)          los temas de la casa que el MODELO nombro

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
# siendo quien dice si un producto EXISTE.
#
# LAS FICHAS YA NO SALEN DE ACA (11-sep-2026). `fichas_relevantes` adivinaba
# cuales ponerle delante al modelo leyendo el mensaje crudo; ahora las busca el
# modelo con `motor.buscar`, que es la FICHA 50. Lo que queda en este modulo es
# lo que NINGUNA busqueda puede contestar: el inventario del catalogo entero y
# las politicas de la casa, que se certifican y no se buscan. `_ficha_corta`
# sigue aca porque es la forma de la ficha, y la usa el motor.


def _norm_cat(c) -> str:
    return _norm(str(c or ""))


def _plata(n) -> str:
    """El precio como se escribe, no como se guarda. Vacio si no hay precio:
    una ficha sin precio no puede inventar uno."""
    try:
        return "$" + f"{int(round(float(n))):,}".replace(",", ".")
    except (TypeError, ValueError):
        return ""


def _ficha_corta(prod: dict, cantidad: int = 1, specs_pedidas=None) -> dict:
    """La ficha que ve el modelo. Corta a proposito: id, nombre, categoria,
    stock, precio y los campos que la fuente declaro para ese rubro.

    LAS SPECS VIAJAN SOLO LAS QUE SE PIDEN, Y ESE ES EL PRECIO (13-sep-2026).
    Medido antes de elegir: el mapa entero suma entre 1.476 y 3.225 caracteres
    por consulta —la ficha crece entre un 32 y un 57 por ciento— y cinco
    notebooks con todas las specs dan 8.837, que NO ENTRAN en el recorte de
    8.000 con que `respuesta` le pasa el retorno al modelo. O sea que mandarlas
    siempre no era caro: era romper el JSON a la mitad. Por eso `specs_pedidas`
    filtra, y sale el mapa entero solo cuando el modelo declaro `busco: uno`,
    que es el caso donde el cliente pregunta por UN producto y quiere detalle.

    LO QUE VIAJA, VIAJA DE LA FUENTE (13-sep-2026). Las tres capas
    —`specs_preguntables`, `specs_por_categoria`, `specs_por_modelo`— se
    calculan enteras en el camino vivo: `firestore_client` llama a
    `fuente_producto.enriquecer` en cada refresco del catalogo y cada producto
    queda con su mapa `specs` en memoria. **Lo que faltaba no era el calculo,
    era mostrarlo:** esta funcion solo pasaba `campos_ficha`, que es prosa
    —nombre, descripcion, caracteristicas—, asi que una pregunta puntual
    —"¿tiene bluetooth?", "¿es resistente al agua?"— se contestaba leyendo
    prosa o no se contestaba, teniendo el dato estructurado a un campo de
    distancia. El mapa ya viene en la forma que el modelo necesita: campo y
    respuesta corta en castellano.

    LA CANTIDAD ES EL CALCULO DE ESTA BOCA. Cada boca trae el suyo: envio
    deriva la tarifa del destino, y catalogo multiplica por cuantos pidio el
    cliente. "Dos teclados de esos" vuelve con `subtotal` ya hecho, escrito
    igual que el precio para que el modelo lo COPIE en vez de multiplicar de
    cabeza. Lo que NO se hace aca es el total del pedido: eso cruza bocas
    —precios, envio y el descuento que es politica— y vive en el retorno.
    """
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
    if cantidad and cantidad > 1:
        fuera["cantidad"] = cantidad
        try:
            fuera["subtotal"] = _plata(float(precio) * cantidad)
            fuera["subtotal_ars"] = int(round(float(precio) * cantidad))
        except (TypeError, ValueError):
            pass
    for campo, valor in (campos_ficha(prod) or []):
        if campo in fuera or valor in (None, ""):
            continue
        fuera[str(campo)] = valor
    # LAS SPECS AL FINAL Y EN SU PROPIA CAJA. Anidadas y no desparramadas entre
    # los campos de arriba: asi el modelo ve de un vistazo que es dato duro de
    # la ficha y que es prosa, y un campo nuevo del catalogo no puede pisar a
    # `id` ni a `precio` por llamarse igual.
    specs = prod.get("specs") or {}
    if isinstance(specs, dict) and specs:
        if specs_pedidas is None:
            elegidas = dict(specs)
        else:
            # El campo que se pidio y la ficha no tiene NO se rellena con nada:
            # que falte es el dato -es la respuesta 2, "no tengo ese dato"- y
            # un vacio inventado ahi seria peor que la ausencia.
            pedidas = {_norm(str(x)) for x in (specs_pedidas or [])}
            elegidas = {k: v for k, v in specs.items() if _norm(str(k)) in pedidas}
        elegidas = {str(k): v for k, v in elegidas.items() if v not in (None, "")}
        if elegidas:
            fuera["specs"] = elegidas
    return fuera


TOPE_TEMAS = 3


def _texto_del_tema(tema: str, faq: dict) -> str:
    """La politica de la casa sobre ese tema, con los numeros ya estampados.

    Los numeros -una tarifa, un plazo, un porcentaje- los pone `curadas`, que
    devuelve None si un hueco no resuelve: una politica a medias no se sirve.
    Sin curada cae a la prosa de la casa del MISMO tema.
    """
    from app.core.curadas import estampar_valores
    dato = faq.get(tema) or {}
    texto = dato.get("respuesta_curada") or ""
    if texto:
        texto = estampar_valores(texto, dato) or ""
    if not texto:
        from app.core.guia_venta_prosa import consultar_guia_venta
        g = consultar_guia_venta(tema) or {}
        texto = " ".join(str(g.get(k) or "") for k in
                         ("texto", "objetivo", "movida")).strip()
    return texto


def politicas_de(nombres: list, tienda_id: str, tope: int = TOPE_TEMAS) -> dict:
    """LO QUE EL MODELO NOMBRO, CERTIFICADO. Es el mapa 3 de la FICHA 50.

    QUE REEMPLAZA: a `politicas_relevantes`, borrada el 12-sep. Ahi el CODIGO
    adivinaba el tema leyendo el mensaje CRUDO entero con raices de cuatro
    letras, asi que un mensaje largo pegaba con cualquier cosa. Medido en vivo el 12-sep 01:37: "quiero un mouse que no sea
    de fabricacion china" sirvio las politicas `fabricacion` y `mouse`, veredicto
    ambiguo, ninguna de las dos al caso. Y a las 00:58 un pedido de precios de
    seis productos trajo `concepto_imposible` y `costo_envio`, y con esas dos
    delante el modelo encasillo el turno como `politica_sin_cubrir`.

    Es la MISMA leccion que la FICHA 50 ya aplico a los productos: el codigo no
    razona, asi que no puede elegir de que habla el cliente. El modelo nombra el
    tema con las palabras del cliente y `certificar_temas` lo resuelve contra
    las señas que la fuente ya tiene escritas. Los tres veredictos no cambian, y
    ante `ambiguous` se sirven todos los candidatos: no se elige.

    Devuelve {politicas: [{tema, texto}], sin_resolver: [...]}. `sin_resolver`
    NO es un error: es un tema que la casa no tiene escrito, y el modelo tiene
    que decirlo en vez de inventarlo.
    """
    from app.storage.firestore_client import get_all_faq
    pedidos = [str(n).strip() for n in (nombres or []) if str(n or "").strip()]
    if not pedidos:
        return {"politicas": [], "sin_resolver": []}
    try:
        faq = get_all_faq(tienda_id=tienda_id) or {}
    except Exception as e:  # noqa: BLE001 — sin FAQ no se inventa una politica
        log.warning("fuente_faq_error", error=f"{type(e).__name__}: {e}")
        return {"politicas": [], "sin_resolver": pedidos}
    v = certificar_temas(pedidos, tienda_id)
    fuera = []
    for tema in v["temas"][:tope]:
        texto = _texto_del_tema(tema, faq)
        if texto:
            fuera.append({"tema": tema, "texto": texto})
    log.info("fuente_politicas", pidio=pedidos[:4],
             temas=[f["tema"] for f in fuera],
             ambiguos=[a[0] for a in v["ambiguos"]][:3],
             sin_resolver=v["sin_resolver"][:3])
    return {"politicas": fuera, "sin_resolver": v["sin_resolver"]}


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


def inventario(tienda_id: str) -> dict:
    """{productos, categorias: [(nombre, cuantos)], precio_min, precio_max}.

    LA CUENTA NO SE HACE ACA. Sale de `filtros_catalogo.recorrida`, que recorre
    el catalogo UNA vez y de esa misma pasada saca tambien el registro de
    campos. Hasta el 11-sep habia dos recorridas de los mismos 880 productos y
    dos caches del mismo dato, y a este no lo vaciaba nadie: subir un catalogo
    nuevo por `/admin/upload-catalog` dejaba al bot diciendo el numero de
    productos del anterior hasta que el proceso se reiniciara.

    Vacio cuando el catalogo no se pudo leer, y `texto_inventario` lo omite.
    """
    from app.core.filtros_catalogo import recorrida
    r = recorrida(tienda_id)
    if not r.get("productos"):
        return {}
    return {k: r[k] for k in
            ("productos", "categorias", "precio_min", "precio_max")}


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


# ── EL ENVIO: EL MAPA 2 DE LA FICHA 50, Y LA TARIFA YA COTIZADA ────────────
#
# QUE ESTABA ROTO, Y ES LO QUE ARREGLA ESTO (11-sep-2026). El motor de envio
# —`calculadora.cotizar_envio`, con la tarifa exacta de las 24 provincias, la
# zona resuelta por CPA oficial y el umbral de envio gratis— estaba ENTERO y
# DESENCHUFADO. La unica herramienta del modelo es `buscar`, que mira el
# catalogo, asi que al envio no llegaba por ahi; y el unico puente que quedaba
# era el hueco `{{envio}}`, que el molde del tipo `envio_costo` ni siquiera
# nombraba —decia `{{costo_envio}}`, que el codigo no llena—.
#
# Resultado medido en el codigo: la respuesta de envio salia de la politica
# `costo_envio`, o sea el RANGO publicado de 5.000 a 12.000, teniendo la tarifa
# exacta de la provincia a una llamada de distancia. Dos caminos para el mismo
# numero y ganaba el flojo, que es exactamente la regla 2 del proyecto.
#
# COMO ENTRA AHORA. Igual que el inventario: el codigo lo resuelve ANTES y se
# lo pone delante. El envio no necesita razonar —el destino sale del CPA o del
# nombre del lugar, determinista— asi que no es una herramienta mas: seria una
# vuelta mas al modelo, y cada vuelta vuelve a pagar el prompt entero.
#
# EL DESTINO SE BUSCA EN DOS LADOS Y ESE ES EL SEGUNDO ARREGLO: el mensaje de
# este turno, y si no, la localidad que la charla ya tiene. Hasta hoy se miraba
# solo el mensaje, asi que un cliente que dio el codigo postal tres turnos
# antes no cotizaba nunca.
#
# EL UMBRAL DE ENVIO GRATIS NO SE APLICA ACA, y es a proposito: depende del
# PEDIDO, y el pedido no vive en este camino. Viaja como dato para que el
# modelo lo diga —"a partir de tanto es gratis"— y lo aplica la calculadora
# cuando el cierre arma la orden de verdad. Lo que se borro es la cuenta que
# sumaba TODAS las fichas que devolvio la busqueda: mostrar cinco notebooks
# regalaba el envio.


def _cotizar(texto: str) -> dict:
    """La tarifa de ese texto, o {} si no clasifica.

    SE LE PASA EL TEXTO CRUDO Y NO UN LUGAR YA RESUELTO, y es el segundo
    arreglo del dia. `geo_cp.resolver` es mas estricto que el clasificador de
    zona: "mandamelo a CP 5121" y "envio a rosario" no los resolvia, y los dos
    clasifican perfecto por `clasificar_zona`. Quien sabe de destinos es el
    motor de envio, asi que se le pregunta a el y no a una pieza de al lado.
    """
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
    """COMO SE LE NOMBRA AL CLIENTE: la palabra que EL uso, si la dijo.

    ES UNA REGLA DE VENTA ANTES QUE UNA DE CODIGO (12-sep-2026). El cliente
    escribe "Posadas" y el bot le contestaba "misiones", porque el destino se
    nombraba con la provincia que la tabla resolvio. La provincia es un
    artefacto NUESTRO —asi esta armada la tarifa— y al cliente no le importa:
    el pidio a Posadas. Nombrarle otra cosa lo obliga a verificar que no nos
    equivocamos, que es exactamente lo que un vendedor no hace.

    Y PESA MAS PORQUE ESTO ES UN MOTOR MULTI-TIENDA: la division en provincias
    es de la tabla argentina. La palabra del cliente viaja en cualquier pais.

    Sin esa palabra —el destino viene de la charla, no de este mensaje— cae a
    la provincia y despues a la zona, que es como venia funcionando. NUNCA el
    codigo postal: con el CP puesto ahi, el cliente que escribio "Cordoba
    capital" leia "el envio a 5000".
    """
    dicho = str(r.get("dicho") or "").strip()
    if dicho:
        return dicho
    return _destino_estable(r)


def _destino_estable(r: dict) -> str:
    """COMO SE GUARDA para el turno siguiente: la provincia, o la zona.

    VA APARTE DE COMO SE NOMBRA, y son dos necesidades distintas que hasta hoy
    compartian una funcion. Lo que se guarda tiene que volver a clasificar solo
    dentro de tres turnos, y una localidad ambigua —"Los Condores"— no lo hace;
    la provincia si. Lo que se MUESTRA tiene que ser la palabra del cliente.
    Mezclarlas obligaba a elegir cual de las dos se rompe.
    """
    prov = str(r.get("provincia") or "").replace("_", " ").strip()
    if prov:
        return prov
    zona = str(r.get("zona") or "").strip()
    return {"caba": "CABA", "gba": "GBA"}.get(zona, zona)


def _plazo_de(zona: str, faq: dict) -> str:
    """El plazo de esa zona, de la FAQ `plazo_envio`. Vacio si la tienda no lo
    tiene cargado: un plazo inventado es una promesa que no podemos cumplir."""
    valores = {str(v.get("concepto") or ""): v.get("monto")
               for v in ((faq.get("plazo_envio") or {}).get("valores") or [])}
    clave = "caba" if str(zona or "") in ("caba", "gba") else "interior"
    mn, mx = valores.get(f"dias_{clave}_min"), valores.get(f"dias_{clave}_max")
    if not (isinstance(mn, (int, float)) and isinstance(mx, (int, float))):
        return ""
    return f"Llega en {int(mn)} a {int(mx)} dias habiles desde el pago."


def _umbral_de(faq: dict) -> int:
    """El umbral de envio gratis. Sale de la MISMA funcion que lo aplica en la
    calculadora, para que el numero que el bot publica y el que el codigo cobra
    no puedan divergir nunca."""
    from app.core.calculadora import _umbral_envio_gratis
    return _umbral_envio_gratis((faq.get("costo_envio") or {}).get("valores"))


def _tabla_interior(tienda_id: str) -> dict:
    """La tarifa por provincia, con el mismo orden de precedencia que usa la
    calculadora: Firestore pisa al default del codigo. Si el mapa leyera solo
    el default, una tienda con tabla propia publicaria un rango que sus propias
    cotizaciones no cumplen.
    """
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
    """Las zonas que la tienda cotiza, con su tarifa. Es el mapa 2: no dice a
    cuanto sale ESTE envio, dice que se puede cotizar y con que dato."""
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


# Cuantos destinos se cotizan en un turno. Cuatro alcanza para el pedido
# partido que motivo esto -tres destinos- y le deja uno de margen; mas que eso
# no es un pedido, es un texto que nombra lugares de paso.
TOPE_DESTINOS = 4


def _cotizar_cada_uno(mensaje: str) -> list[dict]:
    """Un resultado de cotizacion por cada lugar que el mensaje nombra, en el
    orden en que el cliente los dijo y sin repetir destino.

    LOS LUGARES LOS DA `geo_cp`, contra su tabla de 16.164 localidades. Este
    modulo no parte prosa: pregunta donde hay un lugar y cotiza cada uno.

    UN LUGAR QUE NO COTIZA NO ENTRA Y NO ROMPE NADA: si una localidad es
    ambigua, ese destino simplemente no esta, y el turno sigue con los que si
    resolvieron. Devolver una tarifa adivinada seria peor que faltar una.
    """
    from app.core.geo_cp import lugares_en_texto
    try:
        lugares = lugares_en_texto(mensaje)
    except Exception as e:  # noqa: BLE001 — sin lugares se sigue por el camino de uno
        log.warning("envio_lugares_error", error=f"{type(e).__name__}: {e}")
        return []
    fuera, vistos = [], set()
    for lugar in lugares[:TOPE_DESTINOS]:
        r = _cotizar(lugar)
        if not r:
            continue
        # SE REPITE POR LO QUE EL CLIENTE DIJO, no por la provincia. "Posadas y
        # Obera" son DOS envios aunque compartan tarifa: colapsarlos en
        # "misiones" le contesta uno donde pidio dos.
        if lugar in vistos:
            continue
        vistos.add(lugar)
        r = dict(r)
        r["dicho"] = lugar
        fuera.append(r)
    return fuera


def _bloque_de_varios(rs: list, gratis: str, faq: dict) -> dict:
    """El bloque cuando el cliente nombro MAS DE UN destino.

    CADA DESTINO LLEVA SU PROPIO HUECO, `{{envio:<destino>}}`, y ese es el
    punto entero: con un solo `{{envio}}` el codigo no puede saber a cual de
    las tarifas se refiere cada renglon, asi que escribiria la misma dos veces.
    El hueco con referencia ya existia en `numeros` para el precio y no lo
    usaba nadie para el envio.

    `destino` y `monto` sueltos siguen saliendo, y son los del PRIMERO: es lo
    que `respuesta` guarda como la localidad de la charla y lo que resuelve un
    `{{envio}}` sin referencia. Un camino solo, con la lista al lado.
    """
    filas, destinos, plazos = [], [], []
    for r in rs:
        monto, zona = int(r.get("monto") or 0), str(r.get("zona") or "")
        visible = _destino_legible(r)
        destinos.append({"destino": visible, "monto": monto, "zona": zona})
        plazos.append(_plazo_de(zona, faq))
        filas.append(f"- {visible}: {_plata(monto)}, escribi "
                     f"{{{{envio:{visible}}}}} donde vaya ese costo.")
    # EL PLAZO QUE ES EL MISMO SE DICE UNA VEZ. Tres destinos del interior
    # comparten "llega en 4 a 7 dias" y repetirlo por renglon es exactamente lo
    # que el objetivo 2 no tolera: el bloque se mide en repeticion. Cuando los
    # plazos difieren, cada fila se lleva el suyo y no hay linea comun.
    unicos = {p for p in plazos if p}
    comun = unicos.pop() if len(unicos) == 1 else ""
    if not comun:
        filas = [f + (f" {p}" if p else "") for f, p in zip(filas, plazos)]
    log.info("envio_cotizado_varios", destinos=[d["destino"] for d in destinos],
             montos=[d["monto"] for d in destinos])
    cola = " ".join(x for x in (comun, gratis.strip()) if x)
    return {
        "texto": ("EL CLIENTE NOMBRO VARIOS DESTINOS y el codigo YA COTIZO CADA "
                  "UNO, tarifa exacta:\n" + "\n".join(filas)
                  + (f"\n{cola}" if cola else "")
                  + "\nCada hueco trae la tarifa de SU destino: no copies un "
                  "monto a mano ni uses el mismo para todos."),
        "destino": destinos[0]["destino"], "monto": destinos[0]["monto"],
        "zona": destinos[0]["zona"], "destino_estable": _destino_estable(rs[0]),
        "destinos": destinos}


SIN_ENVIO = {"texto": "", "destino": "", "monto": None, "zona": "",
             "destino_estable": "", "destinos": []}


def texto_envio(mensaje: str, localidad_previa: str, tienda_id: str) -> dict:
    """{texto, destino, monto, zona}, y NUNCA lanza: un bloque de envio que se
    rompe no puede dejar al cliente sin turno. Sin bloque el bot contesta lo
    demas igual, y el hueco del envio dice que no se tiene el dato."""
    try:
        return _texto_envio(mensaje, localidad_previa, tienda_id)
    except Exception as e:  # noqa: BLE001 — el envio nunca tumba el turno
        log.warning("envio_bloque_error", error=f"{type(e).__name__}: {str(e)[:150]}")
        return dict(SIN_ENVIO)


def _texto_envio(mensaje: str, localidad_previa: str, tienda_id: str) -> dict:
    """El bloque de envio que viaja al modelo.

    Con destino: la tarifa EXACTA ya cotizada, y el monto sale aparte para que
    `numeros` lo escriba en el hueco. Sin destino: el mapa de lo que la tienda
    cotiza y que dato hace falta para dar el numero exacto.
    """
    from app.storage.firestore_client import get_all_faq
    try:
        faq = get_all_faq(tienda_id=tienda_id) or {}
    except Exception as e:  # noqa: BLE001 — sin FAQ se contesta sin envio
        log.warning("envio_faq_error", error=f"{type(e).__name__}: {e}")
        return dict(SIN_ENVIO)

    umbral = _umbral_de(faq)
    gratis = (f" El envio es GRATIS si la compra supera {_plata(umbral)}."
              if umbral else "")

    # VARIOS DESTINOS EN UN MENSAJE, y es el arreglo del 12-sep. Medido en
    # vivo 01:37: "uno a Cordoba capital y otro a Posadas" cotizaba UNA sola
    # vez y el cliente leia una tarifa donde habia pedido dos. Los lugares los
    # segmenta `geo_cp`, contra su tabla, no una lista de frases.
    varios = _cotizar_cada_uno(mensaje)
    if len(varios) > 1:
        return _bloque_de_varios(varios, gratis, faq)

    # EL MENSAJE DE HOY MANDA SOBRE LA CHARLA: un cliente que corrige la
    # direccion corrige la tarifa.
    r = varios[0] if varios else _cotizar(mensaje)
    de_donde = "mensaje"
    if not r:
        r = _cotizar(localidad_previa)
        de_donde = "charla"
    if not r and localidad_previa and str(mensaje or "").strip():
        # LA LOCALIDAD AMBIGUA MAS LA PROVINCIA DE LA CHARLA (12-sep-2026).
        #
        # El caso es real y tiene fecha: "Los Condores" no resuelve solo -hay
        # varios en el pais- y el cliente ya habia dicho Cordoba dos turnos
        # antes. Cotizar cada texto por separado falla en los dos; juntos
        # resuelven, porque la tabla desambigua una localidad con la provincia
        # en el mismo texto.
        #
        # ESTA CAPACIDAD YA EXISTIA Y ESTABA MUERTA. Vivia en `cotizar_envio`,
        # que la buscaba en `estado_venta.get_current_estado()`, y nadie llama
        # `set_current_estado` en el camino vivo: ese diccionario es `{}`
        # SIEMPRE, asi que la rama no corrio una sola vez desde el apagon. El
        # unico que la ejercitaba era un test que seteaba el estado a mano, o
        # sea una vara midiendo un mundo que no existe.
        #
        # Aca si vive, porque la provincia sale de `ultima_localidad`, que el
        # turno escribe de verdad en cada charla.
        r = _cotizar(f"{mensaje}, {localidad_previa}")
        de_donde = "mensaje+charla"

    if r:
        monto, zona = int(r.get("monto") or 0), str(r.get("zona") or "")
        visible = _destino_legible(r)
        plazo = _plazo_de(zona, faq)
        log.info("envio_cotizado", destino=visible, zona=zona, monto=monto,
                 de_donde=de_donde)
        return {
            "texto": (f"EL ENVIO A {visible.upper()} YA ESTA COTIZADO por el "
                      f"codigo: {_plata(monto)}, tarifa exacta de ese destino. "
                      f"{plazo}{gratis} Escribi {{{{envio}}}} donde vaya ese "
                      f"costo y el codigo lo pone; no lo copies a mano ni lo "
                      f"redondees."),
            "destino": visible, "monto": monto, "zona": zona,
            "destino_estable": _destino_estable(r),
            "destinos": [{"destino": visible, "monto": monto, "zona": zona}]}

    tarifas = _tarifas(faq, tienda_id)
    cuerpo = f"ENVIOS: la tienda cotiza {tarifas}." if tarifas else \
        "ENVIOS: la tienda cotiza por zona."
    return {"texto": (cuerpo + gratis + " Para dar la tarifa EXACTA hace falta "
                      "la PROVINCIA o el CODIGO POSTAL. Si el cliente no lo "
                      "dijo, pediselo: no des un monto sin ese dato."),
            "destino": "", "monto": None, "zona": "",
            "destino_estable": "", "destinos": []}
