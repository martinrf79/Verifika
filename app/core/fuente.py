"""LA FUENTE, SIN INTERMEDIARIOS — lo que el codigo pone delante del modelo.

El 11-sep-2026 se apago la arquitectura de moldes, mesa y dos llamadas. Lo que
queda es esto: ANTES de hablarle al modelo, el codigo busca en la fuente y le
pone delante lo poco que hace falta para contestar. El modelo no elige
herramientas, no declara campos y no nombra ids: lee fichas y politicas que ya
vienen certificadas.

Las areas que se CERTIFICAN en vez de buscarse, y las dos entran con lo que el
MODELO nombro, ninguna con el mensaje crudo:

  politicas_de(nombres)   la FAQ: garantia, cambios, cuotas, plazos
  criterio_de(nombres)    el criterio de la casa: para que sirve, cual conviene

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


# LO QUE EL CLIENTE PIDE Y LO QUE ES CONDUCTA. El `pilar` de cada entrada de
# `base_conocimiento.json` ya parte la base en cinco, y dos de esos cinco no
# son preguntas de un cliente: `conversacion` es el saludo, el cierre y la
# despedida, y `seguridad` es el jailbreak, la autoridad falsa y la amenaza.
# Las usa el CODIGO por dentro; nadie las pregunta por WhatsApp.
#
# NO ES UNA LISTA ESCRITA A MANO, y por eso se nombran los dos pilares y no
# los treinta ids: una entrada nueva con pilar `criterio` entra sola al enum,
# y una de conducta se queda afuera sola. Es la misma regla de la leyenda.
_PILARES_DE_CONDUCTA = ("conversacion", "seguridad")

# LA VALVULA DE ESCAPE DEL ENUM, y es la regla 10.0 aplicada a un tema: el "no"
# es un resultado de primera clase, no un error. Con el enum cerrado, un tema
# de la casa que la fuente no tiene escrito dejaria de poder nombrarse, y el
# modelo elegiria el mas parecido —que es exactamente la alucinacion que el
# enum viene a cerrar—. Con esto puede decir que le preguntaron algo que la
# lista no cubre, y vuelve por `temas_sin_resolver` como cualquier otro.
SIN_TEMA = "la_casa_no_lo_tiene_escrito"


def temas_del_tablero(tienda_id: str) -> list[str]:
    """EL ENUM DE TEMAS TAL COMO VIAJA, y es `temas_consultables` sin conducta.

    POR QUE VUELVE EL ENUM QUE LA FICHA 06 SACO EL 23-ago. Entonces eran 129
    nombres y 2.299 bytes en CADA llamada, el bloque mas caro del esquema, y
    salio por peso. Lo que cambio es la cuenta, medida el 20-sep: sacandole los
    dos pilares de conducta quedan 99 nombres y 1.670 bytes, y la leyenda
    acaba de devolver 1.087 caracteres al bajar su techo. Ahora se paga.

    Y LO QUE COMPRA ES UN CANDADO DURO donde habia una atadura blanda. Sin
    enum el modelo escribe las palabras del cliente y se entera DESPUES, por
    `certificar_temas`, si la casa tenia eso escrito. Con enum, un tema que la
    fuente no tiene no se puede ni nombrar, que es la misma regla con la que el
    esquema cierra los nombres de campo del catalogo.
    """
    from app.core.guia_venta_prosa import meta_categoria
    from app.core.guia_venta_prosa import temas as temas_criterio
    from app.storage.firestore_client import get_all_faq
    try:
        faq = get_all_faq(tienda_id=tienda_id) or {}
    except Exception as e:  # noqa: BLE001 — sin FAQ queda el criterio solo
        log.warning("fuente_faq_error", error=f"{type(e).__name__}: {e}")
        faq = {}
    de_la_base = [t for t in temas_criterio()
                  if (meta_categoria(t).get("pilar") or "")
                  not in _PILARES_DE_CONDUCTA]
    return sorted(set(faq.keys()) | set(de_la_base))


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


# LA PROSA DE LA FICHA, y es lo que se PIDE desde el 14-sep. Son los cinco
# campos que `fuente_producto.CAMPOS_TEXTO` trae y que no son ni identidad ni
# dato duro: los parrafos con los que el modelo redacta.
#
# NO SE ESCRIBEN DOS VECES: salen de CAMPOS_TEXTO sacandole los tres que SIEMPRE
# viajan -el nombre y el modelo son identidad, `caracteristicas_extra` es la
# spec compacta de fabrica-, asi que un campo de texto nuevo en el catalogo cae
# del lado de la prosa solo, sin tocar esta lista.
_SIEMPRE = ("nombre", "modelo", "caracteristicas_extra")


def _campos_prosa() -> tuple:
    from app.core.fuente_producto import CAMPOS_TEXTO
    return tuple(c for c in CAMPOS_TEXTO if c not in _SIEMPRE)


def _ficha_corta(prod: dict, cantidad: int = 1, specs_pedidas=None,
                 detalle: bool = False) -> dict:
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

    LA CANTIDAD ES EL CALCULO DE ESTA BOCA, y la hace `calculadora`. Cada boca
    trae el suyo: envio deriva la tarifa del destino, catalogo multiplica por
    cuantos pidio el cliente. Esta funcion solo ANOTA la cantidad; quien pone
    el subtotal es `motor._con_la_cuenta`, que llama a la herramienta de la
    plata. Lo que NO se hace en esta boca es el total del pedido: eso cruza
    bocas —precios, envio y el descuento que es politica— y vive en el retorno.
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
        # SOLO LA CANTIDAD. El SUBTOTAL lo estampa `motor._con_la_cuenta`
        # llamando a `calculadora`, que es la herramienta de la plata: una
        # multiplicacion suelta escrita aca seria un segundo lugar donde el
        # repo hace cuentas, y por cada cosa que se prende se apaga una.
        fuera["cantidad"] = cantidad
    # ── LA PROSA SE PIDE, LAS SPECS VIAJAN (14-sep-2026) ────────────────
    #
    # ES EL REVES DE LO QUE SE HIZO EL 13-sep, y el motivo es que lo que se
    # midio entonces estaba medido con la prosa adentro. MEDIDO AHORA sobre el
    # catalogo vivo, cinco fichas por rubro:
    #
    #     rubro          prosa   specs completas    neto
    #     teclado        2.850            1.446   -1.404
    #     notebook       3.581            3.170     -411
    #     mouse          2.798            1.421   -1.377
    #     silla gamer    3.198              400   -2.798
    #
    # La prosa era el 60 al 63 por ciento del retorno entero en TODA lista, y
    # las specs completas son mas baratas que ella en los cuatro rubros. O sea
    # que el intercambio no se paga: devuelve. Y ocho notebooks con prosa daban
    # 8.932 caracteres, que NO ENTRAN en el recorte de 8.000.
    #
    # QUIEN DECIDE ES `busco`, que el modelo YA declara, asi que esto no cuesta
    # un campo nuevo en el tablero. Con `uno` el cliente pregunta por UN
    # producto y quiere detalle: viaja todo. Con `varios` pidio opciones, y
    # cinco parrafos de "ideal para" son la REPETICION que el objetivo 2 no
    # tolera. Para que sirve y cual conviene tienen boca propia desde el
    # 13-sep: es `criterio`, y esta es la razon por la que la prosa ya no
    # tiene que viajar en cada lista para contestarlo.
    prosa = _campos_prosa()
    for campo, valor in (campos_ficha(prod) or []):
        if campo in fuera or valor in (None, ""):
            continue
        if not detalle and campo in prosa:
            continue
        fuera[str(campo)] = valor
    # LAS SPECS AL FINAL Y EN SU PROPIA CAJA. Anidadas y no desparramadas entre
    # los campos de arriba: asi el modelo ve de un vistazo que es dato duro de
    # la ficha y que es prosa, y un campo nuevo del catalogo no puede pisar a
    # `id` ni a `precio` por llamarse igual.
    # LAS SPECS VIAJAN ENTERAS, SIEMPRE. Ya no hay que pedirlas: el campo
    # `specs` de la consulta se borro el 14-sep porque dejo de significar algo.
    # El motivo por el que se filtraban -que cinco notebooks con todo no
    # entraban en el recorte de 8.000- era de la prosa, no de ellas: sacada la
    # prosa, entran holgadas y son el dato que contesta "¿tiene bluetooth?" sin
    # leer un parrafo. `specs_pedidas` queda por si alguna tienda necesita
    # recortar; el camino vivo no la usa.
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


# SUBE DE 3 A 6 EL 20-sep, y el motivo entero esta en `motor.TOPE_TEMAS`: los
# campos `temas` y `criterio` del tablero se fundieron en uno, asi que un solo
# tope tiene que cubrir lo que antes cubrian dos de tres.
TOPE_TEMAS = 6

# Cuantas entradas de criterio vuelven en una llamada. El mismo tope que las
# politicas y por el mismo motivo: ante un tema ambiguo se sirven todos los
# candidatos en vez de elegir, y tres alcanza para eso.
TOPE_CRITERIO = 3


def _texto_del_tema(tema: str, faq: dict) -> str:
    """La politica de la casa sobre ese tema, con los numeros ya estampados.

    Los numeros -una tarifa, un plazo, un porcentaje- los pone `curadas`, que
    devuelve None si un hueco no resuelve: una politica a medias no se sirve.

    SOLO DE LA FAQ, Y ESO CAMBIO EL 13-sep-2026. Cuando la FAQ no tenia el
    tema, esta funcion caia al criterio de `base_conocimiento.json` y lo servia
    como POLITICA: era el ramal de criterio entrando por el cable equivocado.
    Medido sobre la tienda viva, "para que sirve un mouse gamer" pedido como
    tema devolvia el criterio de `mouse` bajo el encabezado "POLITICAS DE LA
    CASA que tocan este mensaje", y encima se comia una de las tres ranuras que
    tienen las politicas de verdad. El criterio ahora tiene boca propia y
    vuelve en su propia caja; el tema que la FAQ no contesta no se pierde, lo
    manda ahi `_de_la_casa`.
    """
    from app.core.curadas import estampar_valores
    dato = faq.get(tema) or {}
    texto = dato.get("respuesta_curada") or ""
    if texto:
        texto = estampar_valores(texto, dato) or ""
    return texto


def _criterio_del_tema(tema: str) -> dict:
    """LO QUE LA CASA TIENE ESCRITO SOBRE ESE TEMA: para que sirve, cual
    conviene, y la movida con la que se conduce la situacion si la fuente la
    escribio. `{}` si `categorias` no dice nada de eso.

    EL MATCH TOLERANTE DE `consultar_guia_venta` NO DECIDE ACA, y por eso se
    verifica que devolvio EL tema que se le pidio. Se le entra con un tema ya
    CERTIFICADO por `certificar_tema` —tres veredictos, y ante `ambiguous` no
    elige—, asi que esta funcion solo LEE la fuente. Sin ese chequeo, un nombre
    que no existe volveria con el criterio del tema mas parecido y el modelo no
    tendria como saber que le contestaron otra cosa.

    NO TRAE NUMEROS, Y NO ES UNA PRECAUCION DE ESTA FUNCION: es el invariante
    de `guia_venta_prosa`, que descarta el campo entero si tiene un digito. Por
    eso esta es la unica boca sin CALCULO adentro —la FICHA 52 le pide uno a
    cada una—: no hay nada que calcular sobre prosa sin cifras, y la cuenta de
    la pregunta que la acompaña -"¿cual conviene?"- la trae la boca CATALOGO
    con el precio de cada ficha.
    """
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
                evento: str) -> dict:
    """EL REPARTO POR AREA: de cada tema certificado, la boca que lo contesta.

    LA BOCA LA ELIGE EL CODIGO, NO EL MODELO, y esa es la leccion del 4-ago
    escrita en `temas_consultables`: "un tema es un tema; de que archivo sale es
    asunto del codigo". El modelo nombra con las palabras del cliente y puede
    nombrarlo por el campo que no corresponde —"¿me hacés precio?" es criterio
    de venta Y politica de descuento a la vez—; lo que no puede pasar es que un
    tema que la casa TIENE escrito vuelva vacio porque entro por el campo de al
    lado. Por eso las dos cajas salen siempre y cada tema cae en la suya.

    EL ORDEN DE LAS DOS AREAS NO ES ARBITRARIO: primero la FAQ, que es la que
    trae los numeros ya estampados por `curadas`, y el criterio despues, que es
    prosa sin un solo digito. Un tema que las dos tienen escrito se contesta con
    el que puede traer la cifra.

    Lo que ninguna de las dos tiene escrito va a `sin_resolver`, junto con lo
    que no certifico: los dos dicen que le falta a la fuente.
    """
    v = certificar_temas(pedidos, tienda_id)
    politicas, criterio, sin_resolver = [], [], list(v["sin_resolver"])
    for tema in v["temas"][:tope]:
        texto = _texto_del_tema(tema, faq)
        if texto:
            politicas.append({"tema": tema, "texto": texto})
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
    """LA BOCA CRITERIO, CERTIFICADA. Es el componente 15 de la FICHA 52 y lo
    unico que le faltaba era el cable.

    QUE AREA ES. Las entradas de `categorias` en `base_conocimiento.json`: para
    que sirve cada cosa, cual conviene segun el uso, que diferencia hay entre
    dos, que significa gama baja aca, y la movida con la que se conduce una
    objecion o una queja. Estan escritas y del turno no las alcanzaba NADIE: el
    archivo lo lee `guia_venta_prosa`, y de las cuatro cosas que trae, el turno
    usa una sola, la VOZ. O sea que el criterio de la casa quedaba adentro del
    mismo archivo que si viaja en cada turno.

    QUE PASABA SIN ESTE CABLE, y son dos cosas medidas. El tablero le decia al
    modelo, con todas las letras, que para que sirve un producto y cual conviene
    TODAVIA NO SE PIDEN por la puerta: asi que a "¿me sirve para jugar?" —el
    pedido 5 de los catorce de la FICHA 52— contestaba de memoria. Y por el
    otro lado el criterio SI se colaba, disfrazado: pedido como `temas`, la
    prosa de `mouse` volvia rotulada "POLITICAS DE LA CASA".

    MISMA PUERTA Y MISMO MECANISMO QUE `politicas_de`, y por eso las dos son la
    misma funcion con otro nombre: la certificacion es `certificar_temas` y el
    reparto por area es `_de_la_casa`. Lo que las distingue no es el codigo, es
    que cada una NOMBRA una boca en el tablero, y una boca que el tablero no
    nombra no existe para el modelo. Una funcion de certificacion nueva seria un
    segundo criterio de identidad para lo mismo.

    Devuelve {criterio: [{tema, texto, objetivo, movida, cuando_no}],
    politicas: [...], sin_resolver: [...]}. `sin_resolver` NO es un error: es lo
    que el cliente pregunto y la casa no tiene escrito, y es el renglon que dice
    QUE ENTRADA agregarle a `base_conocimiento.json`.
    """
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

    Devuelve {politicas: [{tema, texto}], criterio: [...], sin_resolver: [...]}.
    `sin_resolver` NO es un error: es un tema que la casa no tiene escrito, y el
    modelo tiene que decirlo en vez de inventarlo. La caja de `criterio` sale de
    aca porque el reparto por area lo hace el codigo: un tema que la FAQ no
    contesta y el criterio si, vuelve como criterio y no como una politica que la
    casa nunca escribio. El motivo entero esta en `_de_la_casa`.
    """
    from app.storage.firestore_client import get_all_faq
    pedidos = [str(n).strip() for n in (nombres or []) if str(n or "").strip()]
    if not pedidos:
        return {"politicas": [], "criterio": [], "sin_resolver": []}
    try:
        faq = get_all_faq(tienda_id=tienda_id) or {}
    except Exception as e:  # noqa: BLE001 — sin FAQ no se inventa una politica
        log.warning("fuente_faq_error", error=f"{type(e).__name__}: {e}")
        return {"politicas": [], "criterio": [], "sin_resolver": pedidos}
    return _de_la_casa(pedidos, faq, tienda_id, tope, "fuente_politicas")


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


# Cuantos destinos se cotizan en una llamada. Cuatro alcanza para el pedido
# partido que motivo esto -tres destinos- y le deja uno de margen; mas que eso
# no es un pedido, es un texto que nombra lugares de paso.
TOPE_DESTINOS = 4


# ── LA BOCA DE ENVIO: SE PIDE, YA NO SE EMPUJA (13-sep-2026) ────────────────
#
# QUE CAMBIA. Hasta hoy el codigo leia el mensaje crudo, buscaba lugares con
# `geo_cp`, cotizaba y le ponia el bloque delante al modelo EN CADA TURNO,
# hubiera preguntado o no. Andaba, y por eso duro: el destino es determinista y
# no hay nada que razonar en un codigo postal.
#
# POR QUE SE CAMBIA IGUAL. Era el ultimo dato que llegaba por un SEGUNDO
# camino, y eso se pago dos veces medido: la politica del rango competia con la
# tarifa exacta -hubo que apagarla a mano- y en los 19 turnos del 13-sep el
# unico que pidio envio fue de los que NO llamaron al motor, porque ya lo tenia
# servido. La decision de Martin en la FICHA 52 es una sola: todo lo que se
# contesta con un dato entra por el motor.
#
# QUE SIGUE SIENDO DEL CODIGO, y es la mitad que importa: clasificar el texto a
# provincia y zona, y sacar la tarifa de la tabla. El modelo NOMBRA el destino
# con las palabras del cliente; el numero no lo toca nadie mas que la fuente.
#
# EL UMBRAL DE ENVIO GRATIS NO SE APLICA ACA, y es a proposito: depende del
# PEDIDO, que no vive en este camino. Viaja como dato para que el modelo lo
# diga y lo aplica la calculadora cuando el cierre arma la orden.


def _fila_de(r: dict, nombre: str, faq: dict) -> dict:
    """La fila que ve el modelo: el destino con SU palabra, la tarifa ya
    escrita, el plazo y el hueco que tiene que copiar.

    NO LLEVA LA PROVINCIA. "Posadas" resuelve a misiones y el cliente pidio a
    Posadas: con la provincia delante el modelo la escribe, que es la falla de
    venta que el repo corrigio el 12-sep. Lo que la charla necesita guardar lo
    resuelve `estable_de`, del lado del codigo.
    """
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
    """{filas, gratis_desde, zonas} para los destinos que nombro el modelo.

    NUNCA LANZA Y NUNCA INVENTA: el destino que no clasifica vuelve con
    `sin_dato` y con que dato falta, que es la respuesta 5 de la FICHA 52.

    `localidad_previa` es la provincia que la charla ya tiene, y resuelve la
    localidad AMBIGUA: "Los Condores" no clasifica solo -hay varios en el
    pais- y con "cordoba" al lado si. Cotizar cada texto por separado falla en
    los dos; juntos resuelven, porque la tabla desambigua una localidad con la
    provincia en el mismo texto.
    """
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
    # EL PLAZO QUE ES EL MISMO SE DICE UNA VEZ. Tres destinos del interior
    # comparten "llega en 4 a 7 dias", y repetirlo por renglon es exactamente
    # lo que el objetivo 2 no tolera: se mide en repeticion. Cuando los plazos
    # difieren, cada fila se queda con el suyo y no hay linea comun.
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


def estable_de(nombre: str, localidad_previa: str = "") -> str:
    """COMO SE GUARDA EL DESTINO PARA EL TURNO SIGUIENTE: la provincia, o la
    zona. Va aparte de como se NOMBRA, y son dos necesidades distintas: lo que
    se guarda tiene que volver a clasificar solo dentro de tres turnos, y una
    localidad ambigua no lo hace; la provincia si.

    Vive del lado del codigo a proposito: la provincia no viaja al modelo, para
    que no le conteste "misiones" al que pidio a Posadas.
    """
    r = _cotizar(nombre)
    if not r and localidad_previa:
        r = _cotizar(f"{nombre}, {localidad_previa}")
    return _destino_estable(r) if r else ""
