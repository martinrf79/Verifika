"""
LA REPOSICION — UNA SOLA PUERTA, y el orden de dependencia escrito adentro.

QUE CAMBIO ACA (FICHA 11, 24-ago-2026). La etapa de reposicion eran SEIS
funciones sueltas en `hub_venta`, cada una con su `G.paso_datos` en
`procesar_venta`, y ninguna sabia de las otras. El orden entre ellas —que es lo
unico que las hace correctas— vivia repartido en comentarios del hub, que es
exactamente donde vivio el defecto que la FICHA 10 saco de la salida.

NO SE BORRO NI UNA REPOSICION. Las seis siguen corriendo, con las mismas
pruebas y en el mismo orden; lo que se corto son las CINCO COSTURAS. Cada pieza
sigue pasando por `G.paso_datos` adentro de la puerta, asi que se sigue
midiendo cual intervino y `peso_reposicion.py` ve el mismo detalle.

QUE ES ESTA ETAPA, DICHO EN UNA LINEA. Lo que el modelo declaro y no aplico, lo
aplica el codigo, sin gastar una vuelta al modelo. No es cortesia ni prolijidad:
es la prioridad uno. Un turno donde el cliente pidio tres cosas y el modelo
busco una sale MUDO sobre las otras dos, y un turno que pidio precio y no armo
la cuenta sale sin un peso. Las dos cosas ya pasaron y estan medidas.

EL ORDEN ES EL DE LA DEPENDENCIA Y NO SE PUEDE REORDENAR POR ACCIDENTE:

  1. BUSQUEDA    que el producto EXISTA. Si no hay sobre que trabajar, las
                 cinco de abajo no tienen material y el turno sale mudo.
  2. CONDICION   el filtro que el cliente puso y el plan no aplico, sobre lo
                 que la busqueda ya trajo.
  3. CUENTA      la plata, calculada por la calculadora sobre ids
                 certificados. Necesita 1 y 2: sin producto no hay que
                 cotizar, y con el filtro sin aplicar se cotiza otra cosa.
  4. REPARTO     el split de pago, que se aplica SOBRE la cuenta de 3.
  5. SUPUESTO    lo que se asumio para calcular, declarado sobre la cuenta que
                 ya tiene el reparto adentro. Va despues de 4 a proposito.
  6. UN BLOQUE   varias cuentas parciales del mismo turno se funden en una, y
                 eso solo se puede hacer al final, cuando ya estan todas.

LA MEMORIA ENTRA POR UNA SOLA PUERTA Y CON UNA SOLA CONDICION, la de la FICHA
04: se abre cuando el reconciliador RECLAMO la cuenta —`falta_la_cuenta`— o
cuando el turno no certifico nada. La condicion vivia suelta en `procesar_venta`
y era la mitad del total perdido del 21-ago; aca esta al lado de la unica pieza
que la usa.
"""
import re

from app.core import herramientas as H
from app.core import pedido as P
from app.logger import get_logger

log = get_logger(__name__)


def _pieza(nombre: str, funcion, llamadas, *args, **kwargs):
    """Corre UNA pieza adentro de la puerta y deja su veredicto.

    ES `G.paso_datos` Y NO OTRA COSA, por el mismo motivo que `salida._pieza`
    es `G.paso`: juntar seis nodos en uno no puede costar lo que esos seis
    nodos daban, que es saber CUAL intervino. El veredicto se sigue midiendo
    pieza por pieza —comparando la huella del estado, no preguntandole a la
    pieza—, asi que la ficha del turno y `peso_reposicion.py` siguen viendo el
    detalle de las seis.

    LA DIFERENCIA CON LA SALIDA, y es deliberada: `G.paso_datos` RE-LEVANTA.
    Una guardia de salida que se cae devuelve el texto tal como entro, porque
    dejar mudo al bot es peor que no podar; una reposicion que se cae dejaria
    al turno con la cuenta a medio armar, y eso es plata mal contada. El
    comportamiento es el mismo que tenian las seis sueltas."""
    from app.verifika import grafo as G
    return G.paso_datos(nombre, funcion, llamadas, *args, **kwargs)


def completar(llamadas: list, declarado: dict, rec: dict, tienda_id: str,
              trace_id: str, memoria: list | None = None) -> list:
    """LA PUERTA — lo que el modelo declaro y no aplico, aplicado por el codigo.

    Entra la lista de llamadas del turno y sale la misma lista completada. No
    inventa un producto, no decide una identidad y no llama al modelo: cada
    pieza busca en la fuente o le pide una cuenta a la calculadora.

    EL ORDEN DE LAS SEIS ESTA EN EL DOCSTRING DEL MODULO y es el de la
    dependencia. Antes estaba repartido en cinco comentarios del hub, o sea que
    para saber por que el supuesto va despues del reparto habia que leer
    `procesar_venta` entera."""
    llamadas = _pieza("busqueda_repuesta", _busqueda_de_lo_declarado,
                      llamadas, declarado, rec, tienda_id, trace_id)
    llamadas = _pieza("condicion_repuesta", _condicion_faltante_aplicada,
                      llamadas, rec, tienda_id, trace_id)
    # ── LA UNICA CONDICION DE LA ETAPA, y es la de la FICHA 04 ───────────
    #
    # EL DEFECTO QUE CURO, vivo en produccion desde el 17-ago y tapado por el
    # corpus: `_certifico_algo` apagaba la memoria ENTERA cuando el turno
    # certificaba cualquier cosa. El cliente decia "agrega un teclado" al
    # presupuesto de seis articulos, el turno certificaba TECLADOS, y por eso
    # mismo se le negaba el carrito donde vivian los otros seis: la cuenta no
    # se armaba y el mensaje salia sin un solo total.
    #
    # LA CONDICION ES EL RECLAMO, NO LA CERTIFICACION, y esa distincion es la
    # que la hace segura. No se repone "porque hay productos" —eso seria el
    # codigo decidiendo por el cliente, y ademas alarga el mensaje—: se repone
    # cuando el reconciliador dice que el cliente PIDIO precio y la cuenta no
    # esta. `_cuenta_con_lo_declarado` pone los productos del turno ADELANTE de
    # los de la memoria, asi que abrirle la memoria no le cambia la eleccion
    # cuando el turno si trajo lo que hacia falta.
    #
    # Y NO SUBE LAS LLAMADAS AL MODELO: la cuenta la arma la calculadora, que
    # cuesta cero tokens. `llamadas_max: 2` sigue defendiendolo.
    certifico_algo = any((l.get("resultado") or {}).get("productos")
                         or (l.get("resultado") or {}).get("producto")
                         for l in llamadas)
    con_memoria = (memoria if (bool(rec.get("falta_la_cuenta"))
                               or not certifico_algo) else None)
    llamadas = _pieza("cuenta_repuesta", _cuenta_con_lo_declarado,
                      llamadas, declarado, tienda_id, trace_id,
                      memoria=con_memoria)
    llamadas = _pieza("reparto_repuesto", _reparto_de_pago_declarado,
                      llamadas, declarado, tienda_id, trace_id)
    llamadas = _pieza("supuesto_de_pago", _supuesto_de_pago,
                      llamadas, declarado, tienda_id, trace_id)
    return _pieza("bloques_a_uno", _bloques_a_uno, llamadas, trace_id)


# ── LA BUSQUEDA QUE HACE EL CODIGO ──────────────────────────────────────────

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
    r = H.ejecutar("buscar_productos", args, tienda_id)
    try:
        from app.core.estado_venta import certificar_ids_de_resultado
        certificar_ids_de_resultado(r)
    except Exception:  # noqa: BLE001 — certificar no puede tumbar un turno
        pass
    return r


# ── LAS SEIS PIEZAS, en el orden en que las corre `completar` ──────────────


def _busqueda_de_lo_declarado(llamadas: list, declarado: dict, rec: dict,
                              tienda_id: str, trace_id: str) -> list:
    """EL RUBRO QUE EL MODELO DECLARO Y NUNCA BUSCO, lo busca el CODIGO.

    LA FALLA, medida el 9-ago con `objetivo.py --vivo`. La redaccion coloquial
    de la pregunta de Martin daba 6 sobre 100 -y 8 el dia anterior-, siempre el
    mismo numero, mientras las otras cuatro daban 84, 88 y 92. El log de las
    tres corridas, identico:

        ronda 1 -> ['registrar_pedido', 'consultar_temas']
        reconciliador faltan: "El cliente pidio 'auriculares' y no lo
        buscaste. Buscalo." + mouse + memorias ram
        ronda 2 -> []

    El modelo DECLARA bien los tres rubros -entiende perfecto, ya estaba
    medido en 100 sobre 15 de 15- y despues no busca ninguno. El reconciliador
    lo caza, se lo pide, y en la ronda dos el modelo pide CERO herramientas. Sin
    productos no hay cuenta, no hay precio y no hay respuesta: el cliente recibe
    un mensaje de 717 caracteres que no cotiza nada.

    ES EL MISMO HECHO QUE YA ESTABA ESCRITO DOS VECES EN ESTE ARCHIVO: ante una
    correccion del reconciliador el modelo pide CERO herramientas 3 de 3 veces
    -medido el 5-ago para la condicion sin aplicar, y otra vez para el rubro que
    la cuenta perdia-. Las dos veces la salida fue la misma y funciono: que lo
    haga el codigo. Esta es la tercera cara de esa misma moneda, y la mas cara,
    porque las otras dos rompian una parte del turno y esta lo rompe entero.

    NO ES EL CODIGO DECIDIENDO POR EL CLIENTE. Busca lo que el modelo MISMO
    declaro que el cliente pidio, con las palabras del cliente, y le suma la
    exclusion que el cliente puso, resuelta por `resolver_exclusion`, que no
    interpreta la frase: mira en que campo del catalogo esa palabra aparece como
    valor, que es un hecho. Traer un dato no es elegir por nadie; lo que no se
    hace es cotizar solo, y por eso esto corre ANTES de las reposiciones que ya
    estaban: primero existe el producto, y recien despues la cuenta se arma con
    lo declarado, con sus reglas de siempre.

    Y CUESTA CERO TOKENS: es la misma herramienta con los argumentos que el
    reconciliador ya tenia tipados. La ronda vacia que hoy se quema esperando
    que el modelo obedezca, se ahorra.
    """
    faltan = [q for q in (rec or {}).get("sin_buscar") or [] if str(q).strip()]
    if not faltan:
        return llamadas
    from app.core import filtros_catalogo as FC
    from app.core.guia_pedido import categorias_nombradas

    # La exclusion que el cliente puso, una sola vez para todos los rubros.
    filtros: list = []
    for r in (declarado or {}).get("restricciones") or []:
        cond = FC.resolver_exclusion(str(r), tienda_id)
        if cond and cond not in filtros:
            filtros.append(cond)

    fuera = list(llamadas)
    hechas = []
    for que in faltan:
        # LA CATEGORIA VA SI Y SOLO SI ES UNA DE LA TIENDA, y la resuelve
        # `categorias_nombradas` contra la fuente viva. Con la descripcion sola
        # -"auriculares", "memorias ram"- la busqueda vuelve `no_encontrado`:
        # esta pensada para lo que el cliente describe, no para un rubro pelado.
        # El test lo cazo antes de que llegara a produccion.
        args = {"descripcion": que, "cuantos": 3}
        cats = categorias_nombradas(que, tienda_id)
        if cats:
            args["categoria"] = cats[0]
        if filtros:
            args["filtros"] = list(filtros)
        # LA MISMA BUSQUEDA NO SE AGREGA DOS VECES, y no es una optimizacion:
        # lo encontro el barrido de la decision con el contrato de
        # idempotencia. El turno puede pasar por aca en dos rondas seguidas con
        # el MISMO reclamo -que el reconciliador repita un faltante es un
        # defecto conocido y abierto-, y sin esta guarda la segunda vuelta
        # agregaba una llamada calcada: el redactor veia el mismo producto dos
        # veces y lo escribia dos veces. El defecto no se ve aca, se ve en el
        # mensaje del cliente, que es donde nadie lo iba a atribuir a esto.
        if any(l.get("herramienta") == "buscar_productos"
               and (l.get("pedido") or {}) == args for l in fuera):
            continue
        r = _buscar_certificando(args, tienda_id)
        fuera.append({"herramienta": "buscar_productos", "pedido": args,
                      "resultado": r})
        hechas.append((que, (r or {}).get("estado")))
    log.info("busqueda_de_lo_declarado", trace_id=trace_id, hechas=hechas,
             filtros=[f.get("campo") for f in filtros])
    return fuera


def _condicion_faltante_aplicada(llamadas: list, rec: dict, tienda_id: str,
                                 trace_id: str) -> list:
    """La condicion que el cliente puso, el modelo declaro y ninguna busqueda
    aplico: la aplica el CODIGO y se rehace la busqueda.

    EL NUMERO QUE LO JUSTIFICA (5-ago, clave paga, nueve corridas). El
    reconciliador cazaba bien la condicion sin aplicar, y en la ronda dos el
    modelo pedia CERO herramientas 3 de 3, con la correccion primera en el
    prompt y con el orden rechazado a la vista. Tres redacciones distintas de la
    instruccion no movieron el numero: desde el punto de vista del modelo ya lo
    habia resuelto. Seguir escribiendo prosa para convencerlo es la rueda que
    hay que cortar.

    El codigo no interpreta la frase: `resolver_exclusion` busca en QUE CAMPO
    del catalogo aparece esa palabra como valor, que es un hecho. Y solo actua
    sobre EXCLUSIONES -hace falta una negacion en las palabras del cliente-,
    porque aplicar una condicion al reves seria peor que no aplicarla.

    Rehacer la busqueda cuesta CERO tokens: es la misma herramienta, corriendo
    con una condicion mas. Y cuando la exclusion no deja nada, la busqueda
    entrega el bloque de hechos que el modelo pega, o sea que el muro deja de
    escribirlo el modelo de su cabeza.
    """
    faltantes = [f for f in (rec or {}).get("faltantes", [])
                 if "condicion" in f.lower()]
    if not faltantes:
        return llamadas
    idx = next((i for i, l in enumerate(llamadas)
                if l.get("herramienta") == "buscar_productos"), None)
    if idx is None:
        return llamadas
    from app.core import filtros_catalogo as FC
    args = dict(llamadas[idx].get("pedido") or {})
    sumadas = []
    for f in faltantes:
        # el texto de la condicion viene entre comillas en el faltante
        m = re.search(r"'([^']+)'", f)
        cond = FC.resolver_exclusion(m.group(1) if m else f, tienda_id)
        if cond and cond not in (args.get("filtros") or []):
            args["filtros"] = list(args.get("filtros") or []) + [cond]
            sumadas.append(cond)
    if not sumadas:
        return llamadas
    # El orden que el modelo pidio puede haber sido su intento de aplicar esta
    # misma condicion; con la condicion puesta de verdad, ya no hace falta.
    args.pop("ordenar_por", None)
    r = _buscar_certificando(args, tienda_id)
    log.info("condicion_faltante_aplicada", trace_id=trace_id,
             condiciones=sumadas, estado=(r or {}).get("estado"))
    fuera = list(llamadas)
    fuera[idx] = {"herramienta": "buscar_productos", "pedido": args,
                  "resultado": r}
    return fuera


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
                if l.get("herramienta") == "armar_presupuesto"
                and (l.get("resultado") or {}).get("estado") == "ok"), None)
    if idx is None and not declarado.get("pide_precio"):
        return llamadas

    # Los productos que ESTE turno certifico, por categoria y por nombre, en el
    # orden en que se los mostro al cliente.
    vistos: list = []
    for l in llamadas:
        r = l.get("resultado") or {}
        for p in (r.get("productos") or []) + ([r["producto"]]
                                               if r.get("producto") else []):
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
        r = H.ejecutar("armar_presupuesto", args, tienda_id)
        if (r or {}).get("estado") != "ok":
            log.warning("cuenta_no_se_pudo_crear", trace_id=trace_id)
            return llamadas
        log.info("cuenta_creada_por_codigo", trace_id=trace_id,
                 items=len(nuevos))
        return llamadas + [{"herramienta": "armar_presupuesto", "pedido": args,
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
    r = H.ejecutar("armar_presupuesto", args, tienda_id)
    if (r or {}).get("estado") != "ok":
        log.warning("cuenta_no_se_pudo_completar", trace_id=trace_id,
                    faltaban=sumados)
        return llamadas
    log.info("cuenta_completada_por_codigo", trace_id=trace_id,
             sumados=sumados)
    fuera = list(llamadas)
    fuera[idx] = {"herramienta": "armar_presupuesto", "pedido": args,
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
                if l.get("herramienta") == "armar_presupuesto"
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
        log.warning("reparto_de_pago_al_reves", trace_id=trace_id,
                    tenia=[(p.get("medio"), p.get("porcentaje"))
                           for p in puesto])
    args["pago"] = [{"medio": "transferencia", "porcentaje": mayor},
                    {"medio": "mercado pago", "porcentaje": menor}]
    r = H.ejecutar("armar_presupuesto", args, tienda_id)
    if (r or {}).get("estado") != "ok":
        log.warning("reparto_de_pago_no_se_pudo", trace_id=trace_id,
                    pedido=amb[0])
        return llamadas
    log.info("reparto_de_pago_por_codigo", trace_id=trace_id, pedido=amb[0],
             aplicado=f"transferencia {mayor}%, mercado pago {menor}%")
    fuera = list(llamadas)
    fuera[idx] = {"herramienta": "armar_presupuesto", "pedido": args,
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
    """
    idx = next((i for i, l in enumerate(llamadas)
                if l.get("herramienta") == "armar_presupuesto"
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
        if l.get("herramienta") == "armar_presupuesto" and r.get("bloque"):
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
                  if l.get("herramienta") == "buscar_productos"
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
        if (l.get("herramienta") == "armar_presupuesto"
                and (l.get("resultado") or {}).get("bloque")):
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
