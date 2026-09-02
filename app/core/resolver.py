"""
EL RESOLVER — el nexo. El modelo declara; el codigo resuelve contra la fuente.

NACE EN LA FICHA 34. Hasta aca el hub tenia DOS opiniones sobre el mismo
pedido: derivaba las busquedas de lo declarado y despues le pedia una segunda
lectura al reconciliador y a la reposicion. El 57% de los turnos no coincidian
y toda esa maquinaria existia para tapar la distancia. Si las busquedas, la
cuenta y el contrato salen de lo DECLARADO, no hay nada que reconciliar.

Una funcion, este contrato:

    resolver(declarado, memoria, tienda_id, trace_id) -> dict

Devuelve {"llamadas", "contrato", "bloque"}. No llama a pedido.reconciliar ni
a reposicion.completar. La cuenta se arma si el declarado pide precio, o hay
items con cantidad, o hay destinos: sale del declarado, no de un reclamo.

`_derivar_las_busquedas` se MUDO de hub_venta, no se copio. Las piezas de
cuenta que el piso necesita —armar, reparto, supuesto, un bloque— se
MUDARON aca en la FICHA 36, no se copiaron. El hub y la salida las piden
a este modulo. `reposicion.py` sale de `app/` en el mismo commit.
"""
import re

from app.core import herramientas as H
from app.core import indice_turno as IT
from app.core import pedido as P
from app.logger import get_logger

log = get_logger(__name__)


# Tope de busquedas que el codigo deriva de UNA declaracion. El modelo ya no
# elige herramienta, asi que el tope no defiende de un modelo desbocado sino de
# una declaracion enorme -veinte items, quince temas-: cada llamada derivada es
# una consulta a la fuente y un pedazo de JSON que despues viaja al redactor.
# Si se corta, se dice: cortar en silencio es peor que el problema que evita.
_MAX_DERIVADAS = 14
# Los estados con los que una busqueda vuelve SIN el producto. Se nombran todos,
# y el que manda es `no_vendemos`: es el que sale cuando lo que pidio el cliente
# no es de ningun rubro de la casa.
_NO_LO_TENEMOS = ("no_vendemos", "no_encontrado", "sin_resultados",
                  "no_se_pudo", "error")


def _id_para(que: str, llamadas: list, memoria: list, laxo: bool = True):
    """EL PRODUCTO DEL QUE HABLA EL CLIENTE, resuelto por el codigo.

    EL ORDEN ES MEMORIA PRIMERO, y es la trampa 5 de la FICHA 06 escrita como
    codigo. Un turno puede necesitar un producto que el cliente NO describio:
    "y ese cuanto pesa", "el otro sirve para la ps5". Eso no lo resuelve la
    declaracion, lo resuelve el estado. Si al derivar se pierde el anclaje a lo
    ya mostrado, la memoria larga se rompe, y la memoria es la prioridad 3 del
    objetivo.

    DOS PREDICADOS Y NO UNO, y es la misma leccion que ya tenia anotada
    `_producto_para`. `_cubierto` es LAXO a proposito -le alcanza UNA raiz- y
    con eso "Mouse Genius DX-110 Negro" pegaba en el Logitech que estaba en la
    memoria, porque los dos son un mouse: el cliente pregunta por uno y el bot
    le contesta la ficha de otro, que es alucinar con la cara de tener el dato.
    Asi que primero se busca ESTRICTO -todas las raices de lo que dijo el
    cliente en ese producto- y el laxo queda para cuando el turno ya trajo
    candidatos. `laxo=False` es "resolvelo solo si es claramente el mismo".

    Y NO CERTIFICA NADA NUEVO: elige entre productos que YA salieron de la
    fuente -el carrito, lo mostrado, lo que trajo este mismo turno-. La regla
    cero sigue entera: el id no lo dice el modelo, lo dice el codigo."""
    vistos = list(memoria or [])
    for l in (llamadas or []):
        r = l.get("resultado") or {}
        vistos = list(r.get("productos") or []) + (
            [r["producto"]] if isinstance(r.get("producto"), dict) else []) + vistos
    if not vistos:
        return ""
    raices = P._stems(que)
    if not raices:
        # "ese", "el otro": no hay ninguna raiz con que buscar, asi que lo que
        # el cliente nombro es el ULTIMO producto que vio. Elegir cualquier
        # otro seria inventar; no elegir nada deja la pregunta sin contestar.
        return str(vistos[0].get("id") or "")

    def _texto(prod):
        return H._norm(prod.get("categoria")) + " " + H._norm(prod.get("nombre"))

    exacto = next((p for p in vistos
                   if all(r in _texto(p) for r in raices)), None)
    if exacto or not laxo:
        return str((exacto or {}).get("id") or "")
    prod = _producto_para(que, vistos, set())
    return str((prod or {}).get("id") or "")


def _derivar_las_busquedas(llamadas: list, declarado: dict, memoria: list,
                           tienda_id: str, trace_id: str) -> list:
    """LA PUERTA UNICA (FICHA 06, 23-ago-2026). El modelo DECLARA; el codigo
    deriva de esa declaracion todo lo que hay que ir a buscar.

    POR QUE. Hasta hoy el modelo veia nueve herramientas y ELEGIA, y en el 57%
    de los turnos declaraba una cosa y buscaba otra. Toda la maquinaria del
    reconciliador y de las reposiciones existe para tapar esa distancia. Si las
    busquedas se derivan de la declaracion, la distancia no puede existir: el
    reconciliador queda en CERO faltantes POR CONSTRUCCION, y ese —no los
    tests— es el chequeo de aceptacion de esta unidad.

    POR QUE CORRE ANTES DEL RECONCILIADOR y no en la etapa de reposicion. Una
    reposicion arregla lo que el reconciliador ya reclamo; esto hace que no haya
    nada que reclamar. Puesto despues, el reconciliador veria una declaracion
    sin ninguna busqueda al lado y reclamaria los items enteros, todos los
    turnos: el numero de aceptacion diria 100% de faltantes con el sistema
    andando perfecto.

    NO ES EL CODIGO ELIGIENDO POR EL CLIENTE. Busca lo que el modelo MISMO
    declaro que el cliente pidio, con las palabras del cliente. Traer un dato no
    es elegir por nadie.
    """
    if not declarado:
        return llamadas
    from app.core import filtros_catalogo as FC
    from app.core.filtros_catalogo import categorias_nombradas

    fuera = list(llamadas)
    hechas: list = []
    cortadas: list = []

    def _agregar(nombre: str, args: dict):
        """Corre una herramienta interna, UNA sola vez por argumento. Devuelve
        el resultado, sea el nuevo o el que ya estaba: quien decide en base al
        estado -si la busqueda no encontro nada- tiene que ver lo mismo la
        segunda vez que pasa por aca."""
        for l in fuera:
            if l.get("herramienta") == nombre and (l.get("pedido") or {}) == args:
                return l.get("resultado") or {}
        if len(hechas) >= _MAX_DERIVADAS:
            cortadas.append(nombre)
            return {}
        if nombre == "consultar_productos" and (
                (args or {}).get("proyeccion") or "lista") == "lista":
            r = _buscar_certificando(args, tienda_id)
        else:
            r = H.ejecutar(nombre, args, tienda_id)
            try:
                from app.core.estado_venta import certificar_ids_de_resultado
                certificar_ids_de_resultado(r)
            except Exception:  # noqa: BLE001 — certificar no tumba un turno
                pass
        fuera.append({"herramienta": nombre, "pedido": args, "resultado": r})
        hechas.append((nombre, (r or {}).get("estado")))
        return r

    # ── 1. LAS CONDICIONES, resueltas una vez para todas las busquedas ──
    # `resolver_exclusion` no interpreta la frase: mira en que campo del
    # catalogo esa palabra aparece como VALOR, que es un hecho.
    # `resolver_orden` es su gemela para el extremo -"el mas barato"-, que
    # hasta hoy viajaba en `buscar_productos.ordenar_por` y lo elegia el modelo.
    # TRES PUERTAS Y UNA SOLA POR CONDICION, en este orden. El EXTREMO primero
    # -"el mas barato" es un orden, no un filtro, y filtrar por "barato" no
    # existe-; despues la EXCLUSION, que sabe dar vuelta la negacion; y al final
    # la INCLUSION, que se lleva lo que queda. Ninguna interpreta la frase: las
    # dos de filtro miran en que campo del catalogo esa palabra aparece como
    # VALOR, que es un hecho, y la del orden sale del nombre del campo.
    filtros: list = []
    sueltas: list = []
    # LOS EXTREMOS SE JUNTAN TODOS, NO SE QUEDA EL PRIMERO (2-sep-2026).
    # Era `orden = orden or extremo`: UNA variable para el turno entero, asi que
    # el primer extremo se llevaba todas las busquedas. "cual es el mas caro de
    # toda la tienda, y cual el mas barato" salia con direccion min las dos
    # veces, y el mas caro no lo miraba nadie. ELEGIR ES INVENTAR, que es la
    # regla cero aplicada al orden: si el turno declaro dos extremos opuestos y
    # ninguno es mas suyo que el otro, no se elige uno, se contestan los dos.
    # Caso de oro C2-S04, y ficha 47.
    extremos: list = []
    for r in (declarado.get("restricciones") or []):
        r = str(r)
        extremo = FC.resolver_orden(r, tienda_id)
        if extremo:
            if extremo not in extremos:
                extremos.append(extremo)
            continue
        cond = (FC.resolver_exclusion(r, tienda_id)
                or FC.resolver_inclusion(r, tienda_id))
        if cond:
            if cond not in filtros:
                filtros.append(cond)
            continue
        # LO QUE NO ENTRA EN NINGUN CAMPO VIAJA EN LA DESCRIPCION, y sin esto
        # se perdia entero. "que ande para jugar", "para trabajar": el uso no
        # es una columna del catalogo -`uso_recomendado` es prosa y ahi pega
        # cualquier palabra-, asi que no hay filtro posible. Antes de la puerta
        # unica esto no se perdia porque el modelo lo metia en la descripcion
        # de la busqueda: escribia "mouse inalambrico gamer barato". El
        # ordenador por parecido lo usa igual, que es exactamente para lo que
        # esta.
        #
        # SOLO SI NO TRAE NEGACION, y es la unica linea que importa de esta
        # regla. Meter "sin partes chinas" en el texto de relevancia sube a los
        # chinos, o sea aplica la condicion AL REVES: es peor que perderla. Una
        # negacion que no se pudo estructurar se deja afuera y el punto queda
        # abierto, que es honesto.
        if not FC.tiene_negacion(r):
            sueltas.append(r)

    # UN SOLO extremo sigue mandando sobre todo el turno, igual que antes: es el
    # caso normal -"la notebook mas barata"- y ahi no hay nada que elegir. DOS O
    # MAS no gobiernan ninguna busqueda de item: cada uno se contesta con la suya
    # abajo, y el item que traiga su propio extremo en el texto lo usa igual
    # porque `_buscar` lo lee de `que` antes que de `orden`.
    orden = extremos[0] if len(extremos) == 1 else None

    def _buscar(que: str, categoria: str = ""):
        args: dict = {"descripcion": " ".join([que] + sueltas), "cuantos": 3}
        cat = categoria or next(iter(categorias_nombradas(que, tienda_id)), "")
        if cat:
            args["categoria"] = cat
        if filtros:
            args["filtros"] = list(filtros)
        # EL EXTREMO PUEDE VENIR EN EL ITEM Y NO EN LA CONDICION. "la notebook
        # mas barata que tengas" es UNA frase: el modelo la declara entera en
        # `que` y no tiene por que partirla en dos campos.
        #
        # Y EL DEL ITEM MANDA SOBRE EL DEL TURNO, que es la correccion del
        # 2-sep-2026. `orden` es UNA sola variable para el turno entero y se
        # guarda con `orden or extremo`, o sea que el PRIMER extremo se quedaba
        # con todas las busquedas. En "que notebook es la mas barata y cual la
        # mas cara" ganaba "barata" y las dos busquedas salieron con direccion
        # min: las dos devolvieron NOT0019, que es la mas barata de 171, y la
        # mas cara -NOT0162, cuatro veces mas cara- nunca se miro. Medido en el
        # turno `95175a7f` de WhatsApp.
        #
        # El extremo del item es MAS ESPECIFICO que el del turno: nombra a que
        # busqueda pertenece. Cuando el item no trae ninguno se usa el del
        # turno, igual que antes.
        #
        # LO QUE SIGUE ABIERTO: dos extremos declarados como condiciones
        # SUELTAS, sin que ningun item los nombre, siguen colapsando en el
        # primero. Ahi no hay a que busqueda atarlos y elegir uno seria
        # inventar; se deja como estaba.
        o = FC.resolver_orden(que, tienda_id) or orden
        if o:
            args["ordenar_por"] = o["campo"]
            args["direccion"] = o["direccion"]
        args["proyeccion"] = "lista"
        return _agregar("consultar_productos", args)

    # ── 2. CADA ITEM: una busqueda con las palabras del cliente ─────────
    for it in (declarado.get("items") or []):
        que = str((it or {}).get("que") or "").strip()
        if que:
            _buscar(que, str((it or {}).get("categoria") or "").strip())

    # ── 2-bis. EL EXTREMO QUE NINGUN ITEM RECLAMA SE BUSCA SOLO ─────────
    # "cual es el mas caro de toda la tienda" no nombra ningun rubro, asi que no
    # abre item, y hasta hoy no derivaba NADA: los filtros se calculaban y no los
    # consumia nadie, porque `_buscar` solo se invoca desde items, stock y
    # atributos. El extremo sobre la tienda entera es una pregunta legitima y
    # tiene respuesta exacta en la fuente: se busca sin descripcion y sin
    # categoria, ordenado, y alcanza con el primero.
    #
    # Con UN solo extremo esto NO corre si algun item ya se lo llevo: en ese caso
    # `orden` viajo en la busqueda del item y volver a preguntar por el extremo
    # de toda la tienda seria contestar otra cosa.
    #
    # VA POR EL AGREGADO, NO POR LA LISTA, y esa es la parte que faltaba: una
    # busqueda de lista sin descripcion y sin categoria vuelve `no_encontrado`
    # con `buscado: ""`, porque la lista esta pensada para lo que el cliente
    # DESCRIBE. El camino exacto ya existia en la herramienta y no lo llamaba
    # nadie: `proyeccion: catalogo` con `operacion` devuelve el producto entero
    # con su valor y sobre cuantos se midio -778-, que es una respuesta
    # determinista y no un ranking por parecido.
    #
    # SOLO CUANDO EL TURNO NO DECLARO NINGUN ITEM, y esto se acoto midiendo: la
    # primera version corria siempre que hubiera dos extremos distintos y rompio
    # el caso C2-E06, donde "que sea barato" y "que no sean tan caros" son dos
    # ablandadores DE SUS ITEMS -un mouse y unos auriculares- y no dos preguntas
    # sobre la tienda entera. Sin items no hay a que atarlos y la unica lectura
    # posible es la tienda entera; con items, el extremo es del item y el caso de
    # dos extremos sueltos con items sigue abierto, que es la ficha 47.
    _hay_items = any(str((it or {}).get("que") or "").strip()
                     for it in (declarado.get("items") or []))
    for ext in ([] if _hay_items else extremos):
        campo, direccion = ext["campo"], ext["direccion"]
        if campo == "precio_ars":
            op = "mas_caro" if direccion == "max" else "mas_barato"
            args = {"proyeccion": "catalogo", "operacion": op}
        else:
            op = "el_mayor" if direccion == "max" else "el_menor"
            args = {"proyeccion": "catalogo", "operacion": op, "campo": campo}
        _agregar("consultar_productos", args)

    # ── 3. STOCK: lo mismo, y si no aparece se mira el CATALOGO ENTERO ──
    # Es la obligacion que llevaba `consultar_catalogo` en su descripcion:
    # antes de decir "no tenemos nada de eso" hay que haber mirado los 880. Sin
    # este segundo paso el bot niega el stock sin haber mirado uno solo, que es
    # la peor forma de alucinar porque suena a respuesta normal.
    sin_hallar = False
    for q in (declarado.get("stock") or []):
        q = str(q or "").strip()
        if not q:
            continue
        r = _buscar(q)
        # `no_vendemos` ES EL ESTADO QUE IMPORTA, y casi se me escapa: es el que
        # devuelve la busqueda cuando lo que pidio el cliente no es de ningun
        # rubro nuestro -"celulares samsung", "una play 5"-, o sea EL caso por el
        # que existe este segundo paso. `no_encontrado` es el otro lado: el rubro
        # existe y el producto puntual no.
        if str((r or {}).get("estado") or "") in _NO_LO_TENEMOS:
            sin_hallar = True
    if sin_hallar:
        _agregar("consultar_productos",
                 {"proyeccion": "catalogo",
                  "operacion": "valores", "campo": "categoria"})

    # ── 4. ATRIBUTOS: la ficha del producto que el cliente nombro ───────
    # LA REGLA CERO MANDA ACA TAMBIEN. Si la busqueda vuelve `ambiguo` —varios
    # modelos se llaman parecido— el codigo NO elige uno para traer su ficha:
    # dejaria pasar como dato de la fuente el atributo de un producto que el
    # cliente no nombro. El resultado ambiguo ya viaja al redactor con sus
    # candidatos y su instruccion de repreguntar, que es lo que corresponde.
    ambiguos: list = []

    def _resolver(que: str) -> str:
        pid = _id_para(que, fuera, memoria, laxo=False)
        if pid:
            return pid
        r = _buscar(que)
        if str((r or {}).get("estado") or "") == "ambiguo":
            ambiguos.append(que)
            return ""
        return _id_para(que, fuera, memoria)

    for a in (declarado.get("atributos") or []):
        de = str((a or {}).get("de") or "").strip()
        if not de:
            continue
        pid = _resolver(de)
        if pid:
            _agregar("consultar_productos",
                     {"proyeccion": "ficha", "product_id": pid})

    # ── 5. COMPATIBILIDAD: los dos lados, certificados ─────────────────
    for c in (declarado.get("compatibilidad") or []):
        que = str((c or {}).get("que") or "").strip()
        para = str((c or {}).get("para") or "").strip()
        if not que:
            continue
        pid = _resolver(que)
        if not pid:
            continue
        args = {"proyeccion": "compatibilidad", "product_id": pid}
        # EL OTRO LADO SOLO SI YA ES UN PRODUCTO CONOCIDO. "mi notebook" puede
        # ser una que le mostramos, y ahi el cruce ficha contra ficha es mucho
        # mas preciso; "jugar" no es un producto y no resuelve a ninguno. No se
        # sale a buscarlo: buscar "jugar" traeria cualquier cosa y el cruce
        # saldria contra un producto que el cliente nunca nombro.
        otro = _id_para(para, fuera, memoria) if para else ""
        if otro and otro != pid:
            args["contra_product_id"] = otro
        elif para:
            args["equipo"] = para
        _agregar("consultar_productos", args)

    # ── 6. TEMAS: lo que el modelo nombro libre, CERTIFICADO ────────────
    cert = H.certificar_temas(declarado.get("temas") or [], tienda_id)
    if cert["temas"]:
        _agregar("consultar_temas", {"temas": cert["temas"]})
    if declarado.get("temas"):
        # EL TEMA CERTIFICADO VUELVE A LA DECLARACION, y sin esto la cobertura
        # se rompia en silencio. `indice_turno` abre un punto de politica por
        # cada tema declarado y despues busca su evidencia comparando ese nombre
        # contra el `tema` que devolvio `consultar_temas`. Si el punto se abre
        # con "envio al exterior" y la herramienta contesta `envio_exterior`,
        # los dos nombran lo mismo y no se encuentran nunca: el punto sale sin
        # contestar aunque este contestado. Es la misma clase de defecto que el
        # anclaje por identidad vino a arreglar el 12-ago.
        #
        # EL QUE NO RESOLVIO SE QUEDA CON LAS PALABRAS DEL CLIENTE, a proposito.
        # Sacarlo cerraria el punto y la pregunta desapareceria del indice: el
        # cliente pregunto algo, nadie lo contesto, y el numero de omision no lo
        # veria. Se queda abierto, sale como punto sin contestar, y el redactor
        # recibe la obligacion de decirlo honesto.
        declarado["temas"] = cert["temas"] + cert["sin_resolver"]

    # ── 7. DESTINOS: un envio cotizado por cada localidad nombrada ──────
    for d in (declarado.get("destinos") or []):
        d = str(d or "").strip()
        if d:
            _agregar("cotizar", {"localidad": d})

    if cortadas:
        log.warning("busquedas_derivadas_recortadas", trace_id=trace_id,
                    tope=_MAX_DERIVADAS, descartadas=cortadas[:6])
    log.info("busquedas_derivadas", trace_id=trace_id, hechas=hechas,
             filtros=[f.get("campo") for f in filtros], sueltas=sueltas[:3],
             orden=(orden or {}).get("campo"),
             sin_identificar=ambiguos[:3],
             temas_sin_resolver=cert["sin_resolver"][:3],
             temas_ambiguos=[a[0] for a in cert["ambiguos"]][:3])
    return fuera



def _hace_falta_cuenta(declarado: dict) -> bool:
    """La cuenta se arma desde lo DECLARADO, no desde un reclamo.

    Decision 8: no es un parche de salida. Pide precio, o hay items con
    cantidad, o hay destinos: cualquiera de las tres abre el punto precio.
    """
    if not declarado:
        return False
    if declarado.get("pide_precio"):
        return True
    if declarado.get("destinos"):
        return True
    for it in (declarado.get("items") or []):
        if not isinstance(it, dict):
            continue
        try:
            if int(it.get("cantidad") or 0) > 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


def _material_del_turno(llamadas: list) -> str:
    return " ".join(
        [str((l.get("resultado") or {}).get("bloque") or "") for l in llamadas]
        + [str(l.get("pedido") or "") for l in llamadas
           if l.get("herramienta") in ("cotizar", "armar_presupuesto")])


def _aplicar_la_cuenta(llamadas: list, declarado: dict, memoria: list,
                       tienda_id: str, trace_id: str) -> list:
    """Aplica lo declarado a la plata. No es una segunda opinion: es el
    punto precio en el lugar que le toca.

    Corre siempre las cuatro piezas de cuenta —crear o reparar, reparto,
    supuesto, un bloque— porque el piso mide el reparto y el supuesto, no
    solo el total. La MEMORIA se abre cuando el declarado pide cuenta o
    cuando el turno no certifico nada: es la condicion de la FICHA 04
    escrita sin el reclamo del reconciliador.
    """
    from app.verifika import grafo as G
    decl = dict(declarado or {})
    if _hace_falta_cuenta(decl) and not decl.get("pide_precio"):
        decl = {**decl, "pide_precio": True}
    certifico_algo = any((l.get("resultado") or {}).get("productos")
                         or (l.get("resultado") or {}).get("producto")
                         for l in llamadas)
    con_memoria = (memoria if (_hace_falta_cuenta(decl) or not certifico_algo)
                   else None)
    llamadas = G.paso_datos("cuenta_repuesta", _cuenta_con_lo_declarado,
                            llamadas, decl, tienda_id, trace_id,
                            memoria=con_memoria)
    llamadas = G.paso_datos("reparto_repuesto", _reparto_de_pago_declarado,
                            llamadas, decl, tienda_id, trace_id)
    llamadas = G.paso_datos("supuesto_de_pago", _supuesto_de_pago,
                            llamadas, decl, tienda_id, trace_id)
    return G.paso_datos("bloques_a_uno", _bloques_a_uno, llamadas, trace_id)


# ── COMPLETAR LO DECLARADO DESDE EL MENSAJE ────────────────────────────────
#
# DESPUES de registrar_pedido y ANTES de buscar y cotizar. El modelo declara;
# el codigo lee el mensaje, completa item→ciudad y el articulo que falte
# (el teclado nombrado solo en el envio) y recien ahi deriva. La respuesta
# cambia cuando la cuenta sale con tres envios y siete productos, no cuando
# el modelo razona mejor.
#
# El parser es el de guia_pedido que la FICHA 36 saco de app/. No se
# reenchufa el modulo: se copia lo que el vivo necesita para cerrar el
# reparto. app/ no importa archivo/.

_RE_DESTINOS_MSG = re.compile(
    r"\b(?:van?|vaya|iran?|env[ií]os?|mandar?|mandal[oa]s?|envial[oa]s?"
    r"|enviad[oa]s?|con\s+env[ií]o)\s+(?:todos?\s+)?(?:junt[oa]s?\s+)?a\s+"
    r"([a-zñ][a-zñ .'-]{2,30}?)"
    r"(?=\s+(?:una?|un|todos?|lo|los|las|el|dime|decime|pasame|pagando|y|e"
    r"|cuanto|dame|es|son|seran?|sera|lleva|va)\b|[,.?!]|$)")
_RE_RESTO_GRUPO = re.compile(
    r"lo demas|el resto|lo restante|lo que queda|que faltan|lo que falta"
    r"|faltantes|los otros")
_RE_DESTINO_PRONOMBRE = re.compile(
    r"^(?:a\s+)?(?:donde|adonde|ahi|alla|alli|casa|mi casa|tu casa|su casa"
    r"|el mismo|la misma|ese lugar|este lugar|la otra|el otro|otra direccion"
    r"|otro destino|la direccion|la misma direccion)\b")
_RE_GRUPO_NOMBRADO = re.compile(
    r"env[ií]os?\s+(?:de|a|para)\s+([a-zñ][a-zñ .'-]{2,30}?)\s+"
    r"(?:es|son|seran?|sera|lleva|va con|va)\s+")
_RE_CORTE_GRUPO = re.compile(
    r"\benv[ií]os?\b|" + _RE_RESTO_GRUPO.pattern
    + r"|\bdime\b|\bdecime\b|\bdame\b|\bpasame\b|\bcuanto\b")


def _es_destino_real(cand: str) -> bool:
    c = (cand or "").strip()
    if not c or _RE_DESTINO_PRONOMBRE.match(c):
        return False
    from app.core.geo_cp import es_lugar_conocido
    return es_lugar_conocido(c)


def _mismo_lugar(a: str, b: str) -> bool:
    pa, pb = set(H._norm(a).split()), set(H._norm(b).split())
    if not pa or not pb:
        return False
    return pa <= pb or pb <= pa


def _hitos_destinos(mensaje: str, conocidos: list | None = None) -> list:
    """[(destino, inicio, fin)] en el orden del mensaje. Primero los que
    el modelo ya nombro, con su grafia; despues los que el regex saca y
    geo confirma. Dedupe por subconjunto de palabras."""
    m = H._norm(mensaje or "")
    hitos: list = []

    def _ya(cand: str) -> bool:
        return any(_mismo_lugar(cand, d) for d, _, _ in hitos)

    for d in (conocidos or []):
        d = str(d or "").strip()
        nd = H._norm(d)
        if not d or not nd:
            continue
        pos = m.find(nd)
        if pos < 0:
            # 'cordoba capital' declarado, el mensaje dice 'cordoba':
            # se busca la palabra mas larga que pegue.
            for n in range(len(nd.split()), 0, -1):
                frag = " ".join(nd.split()[:n])
                pos = m.find(frag)
                if pos >= 0 and len(frag) >= 3:
                    break
            else:
                continue
        if not _ya(d):
            hitos.append((d, pos, pos + max(len(nd), 3)))
    for h in _RE_DESTINOS_MSG.finditer(m):
        cand = h.group(1).strip(" .,-")
        if (len(cand) >= 3 and _es_destino_real(cand) and not _ya(cand)):
            hitos.append((cand, h.start(), h.end()))
    hitos.sort(key=lambda x: x[1])
    return hitos[:4]


def _grupos_del_mensaje(mensaje: str, cats_pedido: list,
                        tienda_id: str, destinos: list | None = None) -> list:
    """[(destino, [(n, cat)])] cuando el cliente dijo QUE va a cada ciudad.
    [] si no cierra. Entiende items pegados antes del destino, grupos
    nombrados despues, y el resto ('los otros van a Posadas')."""
    from app.core import filtros_catalogo as FC
    try:
        totales = {cat: int(n) for n, cat in (cats_pedido or [])}
    except (TypeError, ValueError):
        return []
    if not totales:
        return []
    m = H._norm(mensaje or "")
    hitos = _hitos_destinos(mensaje, destinos)
    if len(hitos) < 2:
        return []
    asignado: dict = {}
    limites = sorted(h[1] for h in hitos)
    for g in _RE_GRUPO_NOMBRADO.finditer(m):
        ref = set(g.group(1).strip(" .,-").split())
        duenos = [d for d, _, _ in hitos
                  if ref <= set(H._norm(d).split())
                  or set(H._norm(d).split()) <= ref]
        if len(duenos) != 1:
            continue
        fin = min([l for l in limites if l > g.end()] + [len(m)])
        seg = m[g.end():fin]
        corte = _RE_CORTE_GRUPO.search(seg)
        if corte:
            seg = seg[:corte.start()]
        items = FC.cantidades_por_categoria(seg, tienda_id)
        if not items or duenos[0] in asignado:
            if duenos[0] in asignado:
                return []
            continue
        asignado[duenos[0]] = items
    resto_destino = None
    prev_fin = 0
    for destino, ini, fin in hitos:
        segmento = m[prev_fin:ini]
        prev_fin = fin
        ventana = segmento[-70:]
        if len(segmento) > 70 and " " in ventana:
            ventana = ventana[ventana.find(" ") + 1:]
        if _RE_RESTO_GRUPO.search(ventana):
            if resto_destino:
                return []
            resto_destino = destino
            continue
        if destino in asignado:
            continue
        items = FC.cantidades_por_categoria(ventana, tienda_id)
        if items:
            asignado[destino] = items
    restantes = dict(totales)
    for items in asignado.values():
        for n, cat in items:
            restantes[cat] = restantes.get(cat, 0) - int(n)
    if any(n < 0 for n in restantes.values()):
        return []
    sobrante = {c: n for c, n in restantes.items() if n > 0}
    sin_grupo = [d for d, _, _ in hitos if d not in asignado
                 and d != resto_destino]
    if resto_destino is None and len(sin_grupo) == 1 and sobrante \
            and _RE_RESTO_GRUPO.search(m):
        resto_destino = sin_grupo[0]
        sin_grupo = []
    grupos = [(d, items) for d, items in asignado.items()]
    if resto_destino:
        if not sobrante:
            return []
        grupos.append((resto_destino,
                       [(n, c) for c, n in sorted(sobrante.items())]))
    elif sobrante or sin_grupo:
        return []
    orden = {d: i for i, (d, _, _) in enumerate(hitos)}
    grupos.sort(key=lambda g: orden.get(g[0], 99))
    return grupos


def _completar_el_declarado(declarado: dict, tienda_id: str) -> dict:
    """Lee el mensaje, completa item→ciudad y el articulo que falte.

    No interpreta: pega cantidades y destinos que el cliente YA escribio.
    Si el reparto no cierra, deja lo que pudo (el articulo de mas) y no
    inventa destinos. Todo-o-nada en el detalle de que va a donde.
    """
    if not isinstance(declarado, dict):
        return declarado or {}
    from app.core.estado_venta import get_current_estado
    from app.core import filtros_catalogo as FC
    mensaje = str((get_current_estado() or {}).get("mensaje_del_turno") or "")
    if not mensaje.strip():
        return declarado
    fuera = dict(declarado)
    items = [dict(i) for i in (fuera.get("items") or []) if isinstance(i, dict)]
    destinos = [str(d).strip() for d in (fuera.get("destinos") or [])
                if str(d or "").strip()]
    cats = FC.cantidades_por_categoria(mensaje, tienda_id)
    # EL ARTICULO QUE FALTA: nombrado en el envio y no en el pedido
    # (el teclado a Concordia). Se suma, no se pregunta: la cuenta tiene
    # que salir con las unidades que el cliente mando a algún lado.
    cubiertos = " ".join(H._norm((i.get("categoria") or "") + " "
                                 + (i.get("que") or "")) for i in items)
    for n, cat in cats:
        if P._cubierto(cat, cubiertos):
            continue
        items.append({"que": cat, "cantidad": max(1, int(n)),
                      "categoria": cat})
        cubiertos += " " + H._norm(cat)
        log.info("articulo_faltante_completado", rubro=cat, cantidad=n)
    hitos = _hitos_destinos(mensaje, destinos)
    if hitos and not destinos:
        destinos = [d for d, _, _ in hitos]
    if hitos:
        extra = [d for d, _, _ in hitos
                 if not any(_mismo_lugar(d, x) for x in destinos)]
        destinos = destinos + extra
    if destinos:
        fuera["destinos"] = destinos
    cats_pedido = cats or [
        (max(1, int(i.get("cantidad") or 1)),
         str(i.get("categoria") or i.get("que") or "").strip())
        for i in items if str(i.get("categoria") or i.get("que") or "").strip()]
    grupos = _grupos_del_mensaje(mensaje, cats_pedido, tienda_id, destinos)
    if grupos:
        nuevos = []
        for dest, pares in grupos:
            canon = next((d for d in destinos if _mismo_lugar(d, dest)), dest)
            for n, cat in pares:
                nuevos.append({"que": cat, "cantidad": max(1, int(n)),
                               "categoria": cat, "destino": canon})
        items = nuevos
        if not destinos:
            fuera["destinos"] = [d for d, _ in grupos]
        log.info("reparto_completado_del_mensaje",
                 destinos=len(grupos),
                 unidades=sum(i["cantidad"] for i in items))
        # EL CODIGO NO CIERRA UNA CONTRADICCION. ACA VIVIA EL FILTRO QUE LA
        # BORRABA, y se va entero (31-ago-2026).
        #
        # Decia "la contradiccion del teclado dejo de serlo: ya esta en el
        # pedido", y descartaba toda contradiccion cuyo texto nombrara una
        # categoria que hubiera quedado en el carrito. La regla estaba dada
        # vuelta: que el teclado este en el carrito es JUSTAMENTE lo que la
        # hace una contradiccion, porque el cliente nunca pidio comprarlo; que
        # el codigo lo haya metido no es el cliente contestando.
        #
        # MEDIDO EN VIVO, turno 2dde2ad0 del 31-ago, la charla real de Martin.
        # El decisor detecto DOS contradicciones -el teclado que no estaba en
        # la lista, y la distribucion que no coincide con lo pedido-, este
        # filtro las borro a las dos porque las dos nombran categorias del
        # carrito, e `indice_turno` ya ni vio el campo: en el log, `campos` no
        # trae `contradicciones`. El cliente pidio seis articulos y se fue con
        # siete y un teclado de $12.000 que nunca pidio, sin que nadie le
        # preguntara nada.
        #
        # Y LA MAQUINARIA DE ABAJO YA ESTABA BIEN Y COMPLETA. `indice_turno`
        # convierte cada contradiccion en un punto, `_cubierto` le exige el
        # signo de pregunta, y el estado sale AMBIGUO si el turno pregunto o
        # CONFLICTO si no: ahi esta escrito que una contradiccion "no puede
        # terminar RESUELTA por el codigo". Este filtro contradecia esa regla
        # tres archivos mas alla. Sacarlo no agrega una pieza: reconecta la que
        # ya estaba.
        #
        # La contradiccion se cierra de UNA sola manera: el turno la pregunta y
        # el cliente contesta. El item SI se queda en la cuenta -un detalle no
        # tira una venta, y el cliente tiene que ver el presupuesto-, pero sale
        # con la pregunta al lado.
    fuera["items"] = items
    return fuera


def resolver(declarado, memoria, tienda_id, trace_id, llamadas=None,
             descartados=None, diferida=None) -> dict:
    """Interpreto → resuelvo → redactar. Una sola opinion sobre el pedido.

    `llamadas` es lo que ya trajo el turno (registrar_pedido y lo que el
    modelo hubiera pedido). `descartados` y `diferida` viajan al contrato
    porque el indice los necesita para no reabrir lo rechazado. Los tres
    son del camino vivo; el contrato de la ficha son los cuatro primeros.
    """
    from app.verifika import grafo as G
    llamadas = list(llamadas or [])
    declarado = declarado or {}
    # Completa item→ciudad y el articulo que falte LEYENDO el mensaje,
    # y recien ahi busca y cotiza. Pisa el dict del hub: si el redactor
    # sigue viendo la contradiccion, pregunta aunque la cuenta ya cierre.
    completo = _completar_el_declarado(declarado, tienda_id)
    if completo is not declarado:
        declarado.clear()
        declarado.update(completo)
    for l in llamadas:
        if l.get("herramienta") == "registrar_pedido":
            res = dict(l.get("resultado") or {})
            res["pedido"] = declarado
            l["resultado"] = res
    llamadas = G.paso_datos("busquedas_derivadas", _derivar_las_busquedas,
                            llamadas, declarado, memoria or [], tienda_id,
                            trace_id)
    llamadas = _aplicar_la_cuenta(llamadas, declarado, memoria or [],
                                  tienda_id, trace_id)
    contrato = IT.cobertura(declarado, _material_del_turno(llamadas),
                            trace_id, llamadas=llamadas,
                            memoria=memoria or [],
                            descartados=descartados or [],
                            diferida=diferida or [])
    return {"llamadas": llamadas, "contrato": contrato,
            "bloque": _bloque_presupuesto(llamadas)}


# ── PIEZAS MUDADAS DE reposicion.py (FICHA 36) ──


def _es_presupuesto(l: dict) -> bool:
    """Cuenta armada, con el nombre nuevo o el grabado."""
    n = l.get("herramienta")
    if n == "armar_presupuesto":
        return True
    if n != "cotizar":
        return False
    ped = l.get("pedido") or {}
    res = l.get("resultado") or {}
    return bool(ped.get("items") or res.get("bloque") or res.get("presentacion"))


def _es_lista(l: dict) -> bool:
    """Busqueda de productos, con el nombre nuevo o el grabado."""
    n = l.get("herramienta")
    if n == "buscar_productos":
        return True
    if n != "consultar_productos":
        return False
    return ((l.get("pedido") or {}).get("proyeccion") or "lista") == "lista"


def _buscar_certificando(args: dict, tienda_id: str):
    """La busqueda que hace EL CODIGO, con sus ids certificados.

    EL AGUJERO QUE CIERRA (FICHA 04, 21-ago-2026), y es la mitad que faltaba de
    un arreglo que ya se habia hecho. `_ejecutar_en_paralelo` certifica lo que
    devuelven las herramientas que pidio EL MODELO, y su comentario nombra el
    turno 6 de `80_charla_real_12ago` como el caso que lo motivo. Pero las
    reposiciones buscan por su cuenta —el modelo declaro un rubro y no lo
    busco, asi que lo busca el codigo— y esos resultados no pasaban por ahi.

    CONSECUENCIA MEDIDA, en ese mismo turno 6: el carrito tiene microfonos, el
    cliente pide auriculares, mouse y memorias, el CODIGO los busca y los
    encuentra, el mensaje se los MUESTRA con nombre y precio... y despues
    `calculate_total` rechaza los tres ids por "no certificados" y el turno
    cierra sin un solo total. El log lo decia con todas las letras:
    `id_no_certificado sueltos=['AUR0019', 'MOU0023', 'RAM0001']`.

    NO AFLOJA LA REGLA CERO, y conviene decir por que. La regla es que la
    IDENTIDAD la decide el codigo y nunca el modelo. Estos ids salen del
    catalogo, por la misma herramienta, en el mismo turno, y los pidio el
    codigo: son MAS certificados que los del modelo, no menos. Lo que la regla
    frena es el id inferido de memoria, y eso sigue frenado igual.

    Se certifica en el hilo del turno, sincronico, que es donde vive la
    contextvar: la misma trampa que ya tenia anotada `_ejecutar_en_paralelo`."""
    r = H.ejecutar("consultar_productos", args, tienda_id)
    try:
        from app.core.estado_venta import certificar_ids_de_resultado
        certificar_ids_de_resultado(r)
    except Exception:  # noqa: BLE001 — certificar no puede tumbar un turno
        pass
    return r



def _producto_para(que: str, vistos: list, del_carrito: set):
    """EL PRODUCTO QUE UNA CATEGORIA YA TENIA RESUELTO NO SE VUELVE A ELEGIR.

    LA FALLA, y estaba abierta en PENDIENTE con dos sintomas que parecian
    distintos y son el mismo: "los auriculares pasaron de Negro a Blanco sin
    que el cliente lo pidiera" y "2 mouse salio Genius y Logitech juntos".
    Casetes `80` turno 7 y `81` turno 2.

    LA CAUSA, reproducida antes de tocar nada. La reposicion elegia el PRIMER
    producto de `vistos` que cubriera el rubro, y `vistos` trae primero lo que
    buscO ESTE turno y despues lo que ya estaba en el carrito. Entonces, con un
    mouse Negro ya cotizado, si el turno vuelve a buscar "mouse" y la busqueda
    devuelve el Blanco primero, la cuenta sale con el Blanco. El cliente no
    pidio cambiar nada: pidio agregar un teclado.

    LA REGLA QUE LO ARREGLA, y es una sola: si el producto que YA estaba en el
    carrito sigue satisfaciendo lo que el cliente nombro, gana el del carrito.
    Si no lo satisface -el carrito tiene el Negro y el cliente ahora dice
    "mouse blanco"- entonces el cliente SI esta pidiendo otro, y gana la
    busqueda del turno.

    DOS PREDICADOS Y NO UNO, y esto lo encontre probando el otro lado antes de
    darlo por bueno. `_cubierto` es LAXO a proposito -le alcanza UNA raiz- y
    esta bien que lo sea, porque su trabajo es decir si el item fue atendido y
    ahi conviene no acusar faltantes falsos. Pero para decidir si el del
    carrito sigue siendo el que el cliente nombro, esa laxitud lo rompe: con el
    Negro en el carrito, "mouse blanco" tambien daba cubierto por la raiz
    "mouse" y el cliente no podia cambiar de color nunca mas. Un arreglo que
    congela el carrito es peor que el defecto.

    Asi que el carrito gana solo con el predicado ESTRICTO -todas las raices de
    lo que dijo el cliente tienen que estar en ese producto-, y la busqueda del
    turno sigue eligiendo con el laxo de siempre. Si el carrito no tiene nada
    de ese rubro, el comportamiento es identico al de antes, linea por linea.
    """
    def _texto(p):
        return H._norm(p.get("categoria")) + " " + H._norm(p.get("nombre"))

    raices = P._stems(que)

    def _es_el_mismo(p):
        """Estricto: todo lo que el cliente nombro esta en este producto."""
        return bool(raices) and all(s in _texto(p) for s in raices)

    return (next((p for p in vistos
                  if str(p.get("id") or "").upper() in del_carrito
                  and _es_el_mismo(p)), None)
            or next((p for p in vistos if P._cubierto(que, _texto(p))), None))



def _cuenta_con_lo_declarado(llamadas: list, declarado: dict, tienda_id: str,
                             trace_id: str, memoria: list | None = None) -> list:
    """EL RUBRO QUE EL CLIENTE PIDIO Y LA CUENTA PERDIO, lo repone el CODIGO.

    LA FALLA, medida en produccion el 5-ago con el mensaje real de Martin. Pidio
    "dos auriculares, dos mouse y dos memorias". El modelo declaro los TRES
    rubros, busco los TRES, y despues llamo a `armar_presupuesto` con DOS: las
    memorias se cayeron en el camino. El cliente recibio un total de $181.000
    que le faltaban $69.000 de mercaderia que habia pedido. El reconciliador no
    lo vio porque su regla 5 chequea que la cuenta EXISTA, no que lo declarado
    este ADENTRO de la cuenta.

    POR QUE LO ARREGLA EL CODIGO Y NO OTRA RONDA. Devolverselo al modelo cuesta
    una vuelta entera -entre 3 y 8 segundos- y no garantiza nada: medido el
    5-ago, ante una correccion del reconciliador el modelo pidio CERO
    herramientas 3 de 3 veces. Rehacer la cuenta cuesta CERO tokens y
    milisegundos, y es la misma herramienta con un item mas.

    NO ES EL CODIGO DECIDIENDO POR EL CLIENTE. Se repone solo lo que el modelo
    MISMO declaro que el cliente pidio, y solo con un producto que ESTE MISMO
    TURNO ya certifico y le mostro. El producto elegido es el primero que se le
    mostro, que es el orden que ya calculo el codigo. Y no queda escondido: el
    renglon sale en la cuenta con su nombre y su precio, que es como el cliente
    lo ve.
    """
    if not declarado:
        return llamadas
    idx = next((i for i, l in enumerate(llamadas)
                if _es_presupuesto(l)
                and (l.get("resultado") or {}).get("estado") == "ok"), None)
    if idx is None and not declarado.get("pide_precio"):
        return llamadas

    # Los productos que ESTE turno certifico, por categoria y por nombre, en el
    # orden en que se los mostro al cliente.
    vistos: list = []
    for l in llamadas:
        r = l.get("resultado") or {}
        # EL MISMO `producto` DE DOS FORMAS (ver `pedido._universo_de_busquedas`):
        # `ver_compatibilidad` lo devuelve como nombre pelado. Aca se juntan
        # fichas CERTIFICADAS, o sea con id, y un nombre suelto no lo es: se
        # descarta con el `isinstance`, que es el mismo guardia que ya usan
        # `atadura_prosa`, `salida`, `estado_venta` y `hub_venta`. Sin el, esto
        # explotaba igual que `pedido`; no se vio antes solo porque el turno se
        # caia unas lineas mas arriba.
        for p in (r.get("productos") or []) + [r.get("producto")]:
            if not isinstance(p, dict):
                continue
            if p.get("id") and p not in vistos:
                vistos.append(p)
    # LA CHARLA TAMBIEN CERTIFICA, no solo el turno. Esta funcion decia "el
    # turno -o la charla-" desde que nacio y miraba unicamente el turno, y esa
    # distancia entre la intencion y el codigo costo un caso real: el cliente
    # pide el precio de DOS unidades de la notebook que venia mirando, el turno
    # no llama a ninguna herramienta porque no hace falta -el producto ya esta
    # certificado y en el carrito-, `vistos` sale vacio y la reparacion se
    # apaga. Al cliente le llego una frase de venta sin un solo numero.
    #
    # NO AFLOJA LA REGLA CERO: lo que entra son ids que YA fueron certificados
    # cuando entraron al carrito o se mostraron, que son los mismos que
    # `calculate_total` acepta. Van DESPUES de los del turno, asi que si este
    # turno mostro algo, ese gana.
    ya = {str(p.get("id") or "").upper() for p in vistos}
    # LOS DEL CARRITO, aparte, porque son los que tienen PRIORIDAD cuando el
    # rubro ya estaba resuelto. Ver `_producto_para`.
    del_carrito = set()
    for p in (memoria or []):
        pid = str((p or {}).get("id") or "").upper()
        if not pid or not p.get("nombre"):
            continue
        del_carrito.add(pid)
        if pid not in ya:
            ya.add(pid)
            vistos.append({"id": pid, "nombre": p["nombre"],
                           "categoria": str(p.get("categoria") or "")})
    if not vistos:
        return llamadas
    por_id = {p["id"]: p for p in vistos}

    # ── LA CUENTA QUE NO EXISTE, y es la falla que mas puntos cuesta ────────
    #
    # MEDIDO EL 7-AGO EN VIVO, 15 corridas de la pregunta de Martin en cinco
    # redacciones: CUATRO terminaron sin ninguna cuenta. El cliente pidio precio
    # de seis productos y no recibio un solo numero. Son exactamente las
    # corridas de 10 y 12 puntos sobre 100, o sea el PEOR CASO, que es el que
    # decide si esto se puede vender.
    #
    # La reparacion de abajo existia desde el 6-ago pero exigia que YA hubiera
    # una cuenta a la cual reponerle el rubro que falto. Cuando el modelo no
    # llama a `armar_presupuesto` ni una vez, no habia nada que reparar y el
    # turno salia sin numeros.
    #
    # Es el mismo principio que ya se aplico dos veces con resultado: la
    # compuerta determinista que arregla la LLAMADA en vez de pedirle al modelo
    # otra ronda. Aca la compuerta no completa una cuenta: la crea, con los
    # productos que el turno -o la charla- ya certifico, y solo cuando el modelo
    # mismo declaro que el cliente pidio precio. Si no hay ningun producto
    # certificado para lo declarado, no inventa nada y el turno sigue sin cuenta,
    # que es el comportamiento honesto.
    if idx is None:
        nuevos = []
        for it in (declarado.get("items") or []):
            que = H._norm(it.get("que"))
            cand = _producto_para(que, vistos, del_carrito)
            if not cand:
                continue
            fila = {"product_id": cand["id"],
                    "cantidad": max(1, int(it.get("cantidad") or 1))}
            if it.get("destino"):
                fila["destino"] = it["destino"]
            nuevos.append(fila)
        if not nuevos:
            return llamadas
        args = {"items": nuevos}
        if declarado.get("destinos"):
            args["destinos"] = list(declarado["destinos"])
        # EL REPARTO DE PAGO VIAJA CON LA CUENTA, y sin esto se perdia justo en
        # el turno donde mas importa. Charla real del 12-ago, 18:05: el cliente
        # dice "anula el teclado, y va 70 mercado pago", la llamada del modelo
        # se cae por un id no certificado, esta reposicion rehace la cuenta
        # SIN pago, y el mensaje sale con el total y sin una palabra del
        # reparto que el cliente acababa de cambiar. El dato estaba declarado
        # en el mismo turno; lo unico que faltaba era pasarlo.
        pago = [{"medio": p.get("medio") or "", "porcentaje": p.get("porcentaje")}
                for p in (declarado.get("reparto_pago") or [])
                if isinstance(p, dict) and p.get("porcentaje")]
        if pago:
            args["pago"] = pago
        r = H.ejecutar("cotizar", args, tienda_id)
        if (r or {}).get("estado") != "ok":
            log.warning("cuenta_no_se_pudo_crear", trace_id=trace_id)
            return llamadas
        log.info("cuenta_creada_por_codigo", trace_id=trace_id,
                 items=len(nuevos))
        return llamadas + [{"herramienta": "cotizar", "pedido": args,
                            "resultado": r}]

    args = dict(llamadas[idx].get("pedido") or {})
    items = [dict(i) for i in (args.get("items") or [])]
    ya = " ".join(
        H._norm(por_id.get(str(i.get("product_id")), {}).get("categoria"))
        + " " + H._norm(por_id.get(str(i.get("product_id")), {}).get("nombre"))
        for i in items)
    sumados = []

    # ── UN RUBRO PEDIDO UNA VEZ, UN SOLO PRODUCTO ──────────────────────────
    #
    # EL DEFECTO, de la charla real: el cliente pide "2 mouse" y la cuenta sale
    # con un Genius y un Logitech. **El cliente no pidio dos modelos distintos:
    # la variedad la invento el sistema, y se la cobra.** Es mandarle algo que
    # no pidio en la parte que se paga, o sea la prioridad uno.
    #
    # POR QUE SE UNIFICA Y NO SE PREGUNTA. Preguntar seria lo correcto si la
    # ambiguedad fuera del cliente, y no lo es: el cliente nombro un rubro, una
    # vez, con una cantidad. El que se contradijo fue el sistema. Preguntar
    # quema un turno y no vende.
    #
    # LAS TRES ATADURAS QUE LO HACEN SEGURO:
    #   1. Solo cuando el cliente nombro ese rubro UNA sola vez. Si declaro dos
    #      items del mismo rubro, esta pidiendo dos cosas distintas y no se
    #      toca.
    #   2. Se unifica DENTRO de cada destino. El mismo producto a dos ciudades
    #      repite con razon, y juntarlos romperia el reparto de envios.
    #   3. El producto que queda lo elige `_producto_para`, o sea el mismo que
    #      ya venia resuelto en el carrito si sigue sirviendo. No se elige uno
    #      nuevo: se vuelve al que el cliente ya tenia.
    #
    # Y LA PLATA NO SE REESCRIBE: se cambia el ITEM y la cuenta la vuelve a
    # calcular `armar_presupuesto` unas lineas mas abajo, con los precios de la
    # fuente. El codigo nunca estampa un total que no calculo la calculadora.
    for it in (declarado.get("items") or []):
        que = H._norm(it.get("que"))
        if not que:
            continue
        if sum(1 for x in (declarado.get("items") or [])
               if H._norm(x.get("que")) == que) != 1:
            continue
        elegido = _producto_para(que, vistos, del_carrito)
        if not elegido:
            continue
        # SE AGRUPA POR CATEGORIA, NO POR `_cubierto`. Lo encontro el barrido de
        # la decision con el contrato de idempotencia, y era grave: `_cubierto`
        # es LAXO -le alcanza una raiz- asi que dos rubros DISTINTOS caian en el
        # mismo grupo y se unificaban en uno. O sea que el arreglo contra
        # cobrarle al cliente algo que no pidio se comia mercaderia que SI habia
        # pedido, que es peor. La categoria es un dato de la ficha, no una
        # coincidencia de palabras.
        cat = H._norm(elegido.get("categoria"))
        mismos = [i for i in items
                  if cat and H._norm(por_id.get(str(i.get("product_id")), {})
                                     .get("categoria")) == cat]
        if len({str(i.get("product_id")) for i in mismos}) < 2:
            continue
        por_destino: dict = {}
        for i in mismos:
            d = str(i.get("destino") or "")
            por_destino.setdefault(d, []).append(i)
        for d, grupo in por_destino.items():
            if len({str(i.get("product_id")) for i in grupo}) < 2:
                continue
            total = sum(max(1, int(i.get("cantidad") or 1)) for i in grupo)
            for i in grupo[1:]:
                items.remove(i)
            grupo[0]["product_id"] = elegido["id"]
            grupo[0]["cantidad"] = total
            sumados.append(f"unificado a {total}x {elegido.get('nombre')}")
            log.info("rubro_unificado_a_un_producto", trace_id=trace_id,
                     rubro=que, destino=d or "unico",
                     quedaba=elegido["id"], era=len(grupo))

    for it in (declarado.get("items") or []):
        que = H._norm(it.get("que"))
        if not que:
            continue
        # ── LA CANTIDAD TAMBIEN CUENTA, no solo el rubro ────────────────────
        # Medido en produccion el 6-ago, mismo mensaje: el cliente pidio DOS
        # auriculares y la cuenta salio con "1x Auriculares HyperX: $70.000".
        # La regla de reponer el rubro que falta no lo veia, porque el rubro
        # estaba: lo que faltaba era una unidad. Es plata igual, la mitad de
        # ese renglon.
        #
        # Se suma por RUBRO y no por renglon: el mismo producto puede venir
        # partido en dos renglones con destinos distintos, y eso esta bien.
        if P._cubierto(que, ya):
            pedidas = max(1, int(it.get("cantidad") or 1))
            iguales = [i for i in items
                       if P._cubierto(que, H._norm(
                           por_id.get(str(i.get("product_id")), {})
                           .get("categoria")) + " " + H._norm(
                           por_id.get(str(i.get("product_id")), {})
                           .get("nombre")))]
            tiene = sum(max(1, int(i.get("cantidad") or 1)) for i in iguales)
            if iguales and tiene < pedidas:
                # Se completa sobre el PRIMER renglon de ese rubro, que es el
                # que el modelo eligio: no se elige otro producto ni se abre uno
                # nuevo, solo se lleva la cantidad a la que el cliente pidio.
                iguales[0]["cantidad"] = (max(1, int(iguales[0].get("cantidad")
                                                     or 1)) + pedidas - tiene)
                sumados.append(f"+{pedidas - tiene}x "
                               f"{por_id.get(str(iguales[0]['product_id']), {}).get('nombre')}")
            continue
        # El primero que se le mostro de ese rubro. Si no se le mostro ninguno,
        # no se inventa: eso es un faltante de verdad y lo cuenta el redactor.
        cand = _producto_para(que, vistos, del_carrito)
        if not cand:
            continue
        # EL DESTINO VIAJA CON EL ITEM. Sin esto el renglon repuesto entra
        # huerfano y el reparto de envios sigue sin cerrar, o sea que se arregla
        # la plata y se rompe el envio. Medido el 6-ago en produccion: la cuenta
        # cobro tres envios y no pudo decir que iba a donde.
        nuevo = {"product_id": cand["id"],
                 "cantidad": max(1, int(it.get("cantidad") or 1))}
        if it.get("destino"):
            nuevo["destino"] = it["destino"]
        items.append(nuevo)
        sumados.append(f"{it.get('cantidad') or 1}x {cand.get('nombre')}")
    if not sumados:
        return llamadas

    args["items"] = items
    r = H.ejecutar("cotizar", args, tienda_id)
    if (r or {}).get("estado") != "ok":
        log.warning("cuenta_no_se_pudo_completar", trace_id=trace_id,
                    faltaban=sumados)
        return llamadas
    log.info("cuenta_completada_por_codigo", trace_id=trace_id,
             sumados=sumados)
    fuera = list(llamadas)
    fuera[idx] = {"herramienta": "cotizar", "pedido": args,
                  "resultado": r}
    return fuera



def _reparto_de_pago_declarado(llamadas: list, declarado: dict, tienda_id: str,
                               trace_id: str) -> list:
    """EL REPARTO QUE EL CLIENTE PIDIO Y LA CUENTA NO LLEVA: lo aplica el CODIGO.

    LA FALLA, medida en produccion el 6-ago sobre el mensaje real de Martin.
    Cerro con "divide el presupuesto en setenta treinta". El modelo lo declaro
    bien como restriccion, el reconciliador lo reclamo TRES rondas seguidas, y
    `armar_presupuesto` salio con `pago=None` las tres veces. Al cliente le
    llego la cuenta sin una palabra del reparto que habia pedido.

    Y no es solo que falte un renglon: la parte que va por transferencia lleva
    10% de descuento. Sobre ese mismo total, el reparto declarado da $232.500 en
    vez de $250.000. **El silencio le costo $17.500 al cliente**, en un turno
    donde el precio era lo unico que el habia dicho que no le importaba.

    POR QUE LO ARREGLA EL CODIGO Y NO OTRA RONDA. Es la misma cuenta que ya se
    hizo para el rubro perdido: devolverselo al modelo cuesta entre 3 y 8
    segundos y no garantiza nada -esta medido, 3 de 3 rondas sin resultado-,
    mientras que rehacer la cuenta cuesta CERO tokens y milisegundos. Ademas el
    reclamo era IMPOSIBLE de resolver por busqueda, que es lo que lo hacia
    eterno; eso se corto en `reconciliar`, regla 3.

    NO ELIGE POR EL CLIENTE. El reparto es del cliente: 70 y 30 los dijo el. Lo
    unico que el codigo asume es CUAL medio lleva cada parte, porque el cliente
    no lo dijo, y lo asume siempre para el mismo lado -la parte grande por
    transferencia, que es la que tiene descuento, o sea la que le conviene al
    cliente- en vez de que el modelo elija distinto cada vez, que es lo que
    hacia. Y no queda escondido: `_supuesto_de_pago`, que corre justo despues,
    escribe el supuesto adentro de la cuenta para que el cliente lo de vuelta en
    una linea si va al reves.
    """
    idx = next((i for i, l in enumerate(llamadas)
                if _es_presupuesto(l)
                and (l.get("resultado") or {}).get("estado") == "ok"), None)
    if idx is None:
        return llamadas
    args = dict(llamadas[idx].get("pedido") or {})
    # EL CAMPO TIPADO PRIMERO, la lectura de castellano como red.
    amb = (P.reparto_declarado(declarado)
           or P.reparto_ambiguo((declarado or {}).get("restricciones")))
    if not amb:
        return llamadas
    _, mayor, menor = amb
    puesto = list(args.get("pago") or [])
    if puesto:
        # ── LA COMPUERTA: EL REPARTO NO SE DEJA DEL LADO QUE LE CUESTA MAS ───
        #
        # Medido en vivo el 7-ago, y es la unica falla de estado que sobrevivio
        # a todo lo demas: el modelo SI mando el reparto, pero puso el 70 en
        # Mercado Pago, que es el medio SIN descuento. Sobre esa cuenta son
        # $9.140 de mas para el cliente. El turno anterior lo habia puesto al
        # reves. O sea: el modelo tira una moneda, en silencio, y la moneda
        # decide lo que el cliente paga.
        #
        # NO SE LE ESTA CORRIGIENDO UNA DECISION AL CLIENTE: el cliente NUNCA
        # dijo que medio lleva cada parte -por eso el reparto es `ambiguo`-. Lo
        # unico que se reemplaza es el volado del modelo por una eleccion
        # deterministica y siempre para el mismo lado, el que le conviene al
        # cliente. Y se declara: `_supuesto_de_pago` corre despues y lo escribe
        # en la cuenta para que lo de vuelta en una linea.
        #
        # Es el patron de "Reason Less, Verify More": una compuerta determinista
        # que mira la llamada propuesta ANTES de ejecutarla y la corrige con una
        # razon, en vez de escribirle otra instruccion al prompt.
        grande = max(puesto, key=lambda x: float(x.get("porcentaje") or 0))
        if "transferencia" in H._norm(grande.get("medio")):
            return llamadas                      # ya esta del lado que conviene
        # DOS SITUACIONES DISTINTAS, DOS AVISOS DISTINTOS (31-ago-2026).
        #
        # La correccion de abajo es la misma para las dos y esta bien que lo
        # sea; lo que no puede ser el mismo es el DIAGNOSTICO. Hasta hoy este
        # aviso decia `reparto_de_pago_al_reves` -o sea "el modelo eligio el
        # medio que le cuesta mas al cliente"- tambien cuando el modelo no
        # habia elegido NINGUN medio. Medido en el turno 2dde2ad0 del 31-ago:
        # `tenia=[['', 70], ['', 30]]`, dos medios vacios, y el log dijo "al
        # reves". No estaba al reves: no estaba.
        #
        # POR QUE IMPORTA UNA PALABRA EN UN LOG. Porque los logs son el unico
        # instrumento con el que se mira produccion desde afuera, y un aviso que
        # nombra mal lo que vio manda a buscar el defecto al lugar equivocado.
        # Es la misma enfermedad que `logger.py` ya documenta por el otro lado.
        # Ademas los dos casos se arreglan distinto si algun dia hay que
        # arreglarlos: el volado del modelo se corrige acá, y el campo vacio se
        # corrige en el contrato de `registrar_pedido`.
        sin_medio = not any(H._norm(p.get("medio")) for p in puesto)
        log.warning(
            "reparto_de_pago_sin_medio" if sin_medio
            else "reparto_de_pago_al_reves",
            trace_id=trace_id,
            tenia=[(p.get("medio"), p.get("porcentaje")) for p in puesto])
    args["pago"] = [{"medio": "transferencia", "porcentaje": mayor},
                    {"medio": "mercado pago", "porcentaje": menor}]
    r = H.ejecutar("cotizar", args, tienda_id)
    if (r or {}).get("estado") != "ok":
        log.warning("reparto_de_pago_no_se_pudo", trace_id=trace_id,
                    pedido=amb[0])
        return llamadas
    log.info("reparto_de_pago_por_codigo", trace_id=trace_id, pedido=amb[0],
             aplicado=f"transferencia {mayor}%, mercado pago {menor}%")
    fuera = list(llamadas)
    fuera[idx] = {"herramienta": "cotizar", "pedido": args,
                  "resultado": r}
    return fuera



def _supuesto_de_pago(llamadas: list, declarado: dict, tienda_id: str,
                      trace_id: str) -> list:
    """EL REPARTO DE PAGO QUE EL CLIENTE NO ASIGNO A NINGUN MEDIO.

    LA FALLA, medida en produccion sobre el mismo mensaje dos dias seguidos.
    "Divide el presupuesto en setenta treinta" no dice QUE medio lleva el 70 ni
    cual el 30. El modelo eligio, en silencio, y eligio DISTINTO cada vez: el
    5-ago puso Mercado Pago 70 y transferencia 30; el 6-ago al reves. Como la
    transferencia tiene 10% de descuento, ese silencio le cambia al cliente lo
    que paga.

    ES LA REGLA CERO APLICADA AL PAGO: ante lo ambiguo el sistema no elige por
    el cliente. Pero tampoco frena la venta preguntando y dejandolo sin numero:
    aplica el reparto, y DECLARA el supuesto en la cuenta, que es la parte que
    el modelo no puede reescribir. El cliente ve lo que se asumio y lo corrige
    en una linea.

    El hecho lo mira sobre lo DECLARADO, no sobre el mensaje crudo: si una
    restriccion trae dos porcentajes y no nombra ningun medio de pago, el que
    despues aparece en la cuenta lo puso el modelo, no el cliente.

    FICHA 43: la linea se ESCRIBE solo si la familia `reparto_pago` se abrio.
    Aplicar el split es la cuenta; decir el supuesto es hablar. Si el cliente
    no abrio esa familia, el codigo no la nombra.
    """
    from app.core.familias import abiertas
    if "reparto_pago" not in abiertas(declarado):
        return llamadas
    idx = next((i for i, l in enumerate(llamadas)
                if _es_presupuesto(l)
                and (l.get("resultado") or {}).get("bloque")), None)
    if idx is None:
        return llamadas
    partes = ((llamadas[idx].get("pedido") or {}).get("pago") or [])
    if len(partes) < 2:
        return llamadas
    amb = (P.reparto_declarado(declarado)
           or P.reparto_ambiguo((declarado or {}).get("restricciones")))
    if not amb:
        return llamadas
    ambigua = amb[0]
    dicho = ", ".join(f"{p.get('medio')} {int(float(p.get('porcentaje') or 0))}%"
                      for p in partes)
    from app.core import huecos
    huecos.anotar(tienda_id, "supuesto", "medio_de_pago", ambigua)
    log.info("supuesto_de_pago_declarado", trace_id=trace_id, pedido=ambigua,
             asumido=dicho)
    fuera = list(llamadas)
    res = dict(llamadas[idx]["resultado"])
    # EL SUPUESTO, EN UNA LINEA Y PEGADO A LA POSDATA DE ARRIBA. La version
    # anterior repetia el reparto DOS veces mas -"Dijiste 70/30" y "lo arme con
    # transferencia 70%, mercado pago 30%"- cuando el bloque de Pago dividido,
    # tres renglones mas arriba, ya lo dice con los montos. Tres veces el mismo
    # numero en el mismo mensaje.
    #
    # Lo que la regla cero EXIGE que se diga sigue dicho: que el medio de cada
    # parte lo asumio el sistema, cual asumio, y que se da vuelta en una linea.
    # Y va con UN solo salto, no dos, para que quede una posdata sola en vez de
    # dos bloques seguidos pidiendo lo mismo.
    mayor = max(partes, key=lambda p: float(p.get("porcentaje") or 0))
    linea = (f"El {int(float(mayor.get('porcentaje') or 0))}% "
             f"lo puse por {mayor.get('medio')}, que es la que tiene "
             f"descuento: si va al revés, decime y lo doy vuelta.")
    # EL SUPUESTO SE DICE UNA VEZ. Lo encontro el barrido de la decision con el
    # contrato de idempotencia: si el turno pasa dos veces por aca, el cliente
    # leia la misma aclaracion dos veces adentro de la misma cuenta. Es
    # exactamente la repeticion que la prioridad dos no tolera.
    if linea in str(res.get("bloque") or ""):
        return llamadas
    res["bloque"] = res["bloque"] + "\n" + linea
    fuera[idx] = {**llamadas[idx], "resultado": res}
    return fuera



def _bloque_presupuesto(llamadas: list) -> str:
    for l in llamadas:
        r = l.get("resultado") or {}
        if _es_presupuesto(l) and r.get("bloque"):
            return str(r["bloque"])
    return ""



def _bloques_a_uno(llamadas: list, trace_id: str) -> list:
    """TRES RUBROS, UN SOLO BLOQUE. El recorte mas grande del mensaje, y no lo
    hace el modelo: lo hace el codigo, que es quien lo escribe.

    LA MEDICION, sobre el turno real del 6-ago: la respuesta salio en 2.977
    caracteres y 3 mensajes de WhatsApp. De esos, 1.476 -la MITAD- eran tres
    bloques calcados, uno por rubro, cada uno con su cabecera, su linea de
    empate y la MISMA cola "donde si se cumple del todo: almacenamiento externo,
    procesador", repetida textual tres veces.

    No es culpa del modelo: cada busqueda devuelve su bloque y la instruccion le
    dice que lo pegue tal cual, asi que pego tres. La solucion no es pedirle que
    resuma -eso es rogarle a la prosa- sino entregarle UNO.

    Se arma de los DATOS, no pegando textos: rubro, dos productos con su precio
    y el dato que falla, el empate en una linea y la cola una sola vez.
    """
    candidatos = [i for i, l in enumerate(llamadas)
                  if _es_lista(l)
                  and (l.get("resultado") or {}).get("bloque")
                  and (l.get("resultado") or {}).get("productos")]
    # UN RUBRO, UNA VEZ. Cuando el turno da varias vueltas, el modelo vuelve a
    # buscar la misma categoria y se acumulan los resultados: medido en el
    # guion 76, ocho busquedas para tres rubros. Se queda la ULTIMA de cada
    # rubro, que es la mas afinada, y se descartan las anteriores.
    por_rubro: dict = {}
    for i in candidatos:
        r = llamadas[i]["resultado"]
        cat = H._norm(r.get("categoria")
                      or (r.get("productos") or [{}])[0].get("categoria"))
        por_rubro[cat] = i
    idx = sorted(por_rubro.values())
    if len(idx) < 2:
        return llamadas

    # ── CON LA CUENTA SOBRE LA MESA, LA VIDRIERA NO VA ──────────────────────
    #
    # ES EL RECORTE MAS GRANDE QUE QUEDABA, y Martin lo viene marcando desde el
    # 7-ago: "el bloque de hallazgo pegado ENTERO cuando ya hay cuenta". Medido
    # sobre su mensaje del 9-ago: el bloque son 640 caracteres de 1.731, MAS
    # que la cuenta, y lista productos que NO son los que se cotizan -mostraba
    # el Zeus X Blanco y cobraba el Negro, mostraba el Logitech y cobraba el
    # Genius-. O sea que los 640 no solo sobran: confunden.
    #
    # POR QUE ESTE CORTE SI Y EL DEL 9-AGO NO. Ese dia se probo borrar el grupo
    # entero y la nota cayo de 89 a 77, porque con los renglones se iba el
    # HECHO -"pais de fabricacion: china"-, que es el unico criterio que el
    # cliente puso. La leccion quedo escrita: borrar solo es seguro cuando lo
    # borrado esta demostrablemente repetido. Aca no se borra el hecho: se
    # CONSERVA, en una linea por rubro, y lo que se va son los renglones de
    # producto, que si estan repetidos -el producto que el cliente compra esta
    # en la cuenta, con su nombre y su precio, tres renglones mas abajo-.
    #
    # Y EL HECHO QUE SOBREVIVE ES EL DEL PRODUCTO COTIZADO, no el del primero
    # de la lista. Con eso se cierra de raiz la vidriera que contradecia a la
    # factura, que estaba abierta desde el 9-ago a la mañana.
    ids_cotizados, hay_cuenta = set(), False
    for l in llamadas:
        if _es_presupuesto(l) and (l.get("resultado") or {}).get("bloque"):
            hay_cuenta = True
            for it in ((l.get("pedido") or {}).get("items") or []):
                ids_cotizados.add(str(it.get("product_id") or "").upper())

    if hay_cuenta:
        cortas = []
        for i in idx:
            r = llamadas[i]["resultado"]
            cat = r.get("categoria") or (r["productos"][0].get("categoria") or "")
            prods = r.get("productos") or []
            elegida = next((f for f in prods
                            if str(f.get("id") or "").upper() in ids_cotizados),
                           prods[0] if prods else {})
            hecho = str(elegida.get("por_que") or "").strip()
            if hecho:
                cortas.append(f"{str(cat).capitalize()}: {hecho}")
        if cortas:
            fuera = list(llamadas)
            for n, i in enumerate(candidatos):
                r = dict(llamadas[i]["resultado"])
                r["bloque"] = "\n".join(cortas) if i == idx[0] else ""
                r["instruccion"] = (
                    "Pegá el bloque TAL CUAL, sin cambiar un renglón: es el "
                    "origen de cada rubro y es el criterio que el cliente puso. "
                    "NO listes productos: los que compra ya están en la cuenta "
                    "con su nombre y su precio. PROHIBIDO afirmar nada sobre el "
                    "catálogo entero." if i == idx[0] else
                    "Ya está dicho en el bloque de arriba: no lo repitas.")
                fuera[i] = {**llamadas[i], "resultado": r}
            log.info("bloques_a_uno_con_cuenta", trace_id=trace_id,
                     rubros=len(cortas), largo=len("\n".join(cortas)))
            return fuera

    lineas, hubo_empate = [], False
    for i in idx:
        r = llamadas[i]["resultado"]
        cat = r.get("categoria") or (r["productos"][0].get("categoria") or "")
        fichas = (r.get("productos") or [])[:2]
        # ── EL DATO QUE FALLA VA EN LA CABECERA CUANDO ES EL MISMO ──────────
        # Medido sobre el turno del 6-ago: los seis renglones terminaban en
        # "— país de fabricación: china", el mismo texto seis veces. Es un
        # hecho del RUBRO, no de cada producto, y repetirlo por renglon no
        # agrega un dato: agrega 190 caracteres y hace que la respuesta se lea
        # como una excusa repetida en vez de un hallazgo.
        motivos = {f.get("por_que") for f in fichas if f.get("por_que")}
        comun = motivos.pop() if len(motivos) == 1 else ""
        # EL EMPATE, POR RUBRO Y SIN LA FRASE QUE CONTRADICE AL CLIENTE. Antes
        # se sumaban los tres y salia "hay varios igual de cerca -160 en total-:
        # ninguno está mejor que otro, te muestro los más baratos". Ese 160 no
        # significa nada -son tres universos distintos sumados- y "te muestro
        # los más baratos" le contesta con el precio a un cliente que acababa de
        # decir que el precio no era lo importante. El numero por rubro SI es un
        # hecho: dice cuanto surtido hay atras.
        n = int(r.get("empatados_igual_de_cerca") or 0)
        cabeza = str(cat).capitalize()
        detalle = []
        if n > len(fichas):
            detalle.append(f"{n} igual de cerca")
            hubo_empate = True
        if comun:
            detalle.append(comun)
        lineas.append(cabeza + (f" ({', '.join(detalle)})" if detalle else "")
                      + ":")
        for f in fichas:
            renglon = f"- {f.get('nombre')}"
            if f.get("precio"):
                renglon += f": {f['precio']}"
            if f.get("por_que") and not comun:
                renglon += f" — {f['por_que']}"
            lineas.append(renglon)

    partes = ["Lo que más se acerca a lo que pediste:", "\n".join(lineas)]
    if hubo_empate:
        partes.append("Dentro de cada rubro la ficha no los distingue entre "
                      "sí, así que te muestro dos de cada uno y te paso el "
                      "resto si querés comparar.")
    # `donde_si_se_cumple` NO ENTRA EN UN PEDIDO DE VARIOS RUBROS. Sirve para
    # "tenés algo sin China?", que es una pregunta sobre el catalogo. Acá el
    # cliente pidió auriculares, mouse y memorias: contestarle "donde sí se
    # cumple es en almacenamiento externo y procesador" no le resuelve nada,
    # le cambia el pedido, y ocupa un renglón en un mensaje que ya sobra.
    unico = "\n\n".join(partes)

    fuera = list(llamadas)
    for n, i in enumerate(candidatos):
        r = dict(llamadas[i]["resultado"])
        if i == idx[0]:
            r["bloque"] = unico
            r["instruccion"] = (
                "Pegá el bloque TAL CUAL, sin cambiar un renglón: ya trae los "
                "rubros juntos. Escribí vos lo de antes y lo de después, corto. "
                "NO repitas los productos afuera del bloque y PROHIBIDO afirmar "
                "nada sobre el catálogo entero.")
        else:
            # El resto se queda SIN bloque: si no, el modelo pega los tres.
            r.pop("bloque", None)
            r["instruccion"] = ("Estos productos ya están en el bloque del "
                                "primer resultado. NO los vuelvas a listar.")
        fuera[i] = {**llamadas[i], "resultado": r}
    log.info("bloques_fusionados", trace_id=trace_id, rubros=len(idx),
             largo=len(unico))
    return fuera
