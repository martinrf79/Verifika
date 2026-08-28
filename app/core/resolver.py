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
cuenta que el piso necesita —armar, reparto, supuesto, un bloque— siguen
viviendo en reposicion.py porque salida.py todavia las llama (eso es la
FICHA 35). Este modulo las invoca; no reinterpreta el pedido.
"""
from app.core import herramientas as H
from app.core import indice_turno as IT
from app.core import pedido as P
from app.core import reposicion as R
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
    prod = R._producto_para(que, vistos, set())
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
    from app.core.guia_pedido import categorias_nombradas

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
        if nombre == "buscar_productos":
            r = R._buscar_certificando(args, tienda_id)
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
    orden = None
    for r in (declarado.get("restricciones") or []):
        r = str(r)
        extremo = FC.resolver_orden(r, tienda_id)
        if extremo:
            orden = orden or extremo
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
        o = orden or FC.resolver_orden(que, tienda_id)
        if o:
            args["ordenar_por"] = o["campo"]
            args["direccion"] = o["direccion"]
        return _agregar("buscar_productos", args)

    # ── 2. CADA ITEM: una busqueda con las palabras del cliente ─────────
    for it in (declarado.get("items") or []):
        que = str((it or {}).get("que") or "").strip()
        if que:
            _buscar(que, str((it or {}).get("categoria") or "").strip())

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
        _agregar("consultar_catalogo",
                 {"operacion": "valores", "campo": "categoria"})

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
            _agregar("ficha_producto", {"product_id": pid})

    # ── 5. COMPATIBILIDAD: los dos lados, certificados ─────────────────
    for c in (declarado.get("compatibilidad") or []):
        que = str((c or {}).get("que") or "").strip()
        para = str((c or {}).get("para") or "").strip()
        if not que:
            continue
        pid = _resolver(que)
        if not pid:
            continue
        args = {"product_id": pid}
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
        _agregar("ver_compatibilidad", args)

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
            _agregar("cotizar_envio", {"localidad": d})

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
           if l.get("herramienta") == "armar_presupuesto"])


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
    llamadas = G.paso_datos("cuenta_repuesta", R._cuenta_con_lo_declarado,
                            llamadas, decl, tienda_id, trace_id,
                            memoria=con_memoria)
    llamadas = G.paso_datos("reparto_repuesto", R._reparto_de_pago_declarado,
                            llamadas, decl, tienda_id, trace_id)
    llamadas = G.paso_datos("supuesto_de_pago", R._supuesto_de_pago,
                            llamadas, decl, tienda_id, trace_id)
    return G.paso_datos("bloques_a_uno", R._bloques_a_uno, llamadas, trace_id)


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
            "bloque": R._bloque_presupuesto(llamadas)}
