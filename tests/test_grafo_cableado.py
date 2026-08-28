"""
EL BARRIDO DEL CABLEADO — generado del grafo, no escrito a mano.

POR QUE EXISTE (Martin, 12-ago-2026). "Si tenemos que hacer el arreglo manual
de todas las posibles causas y errores, seria una actividad casi interminable".
Y es cierto mientras el trabajo crezca con la cantidad de BUGS. Este archivo lo
hace crecer con la cantidad de NODOS, que es un numero que elegimos nosotros y
hoy son treinta y uno.

EL CAMBIO DE PALANCA, dicho en una linea: en vez de escribir un test por
defecto encontrado, se escribe un CONTRATO por propiedad y se cobra en todos
los nodos que lo declaran. Cuatro contratos por dieciseis engranajes son
sesenta y cuatro comprobaciones, y ninguna la escribio nadie a mano.

LOS CUATRO CONTRATOS, y los cuatro se comprueban sin saber cual era la
respuesta correcta —esa es la unica forma de correrlos sobre entradas
generadas—:

  NO_ENMUDECE       entra un mensaje con contenido, sale un mensaje con
                    contenido. Un bot mudo no vende.
  NO_INVENTA_PLATA  todo importe que sale ya estaba en lo que entro, o en un
                    bloque sellado que ese nodo tiene declarado que repone.
  IDEMPOTENTE       aplicarlo dos veces da lo mismo que una. Es el contrato que
                    protege del ORDEN, que es donde vivieron los dos errores de
                    plata del 10 y del 12 de agosto.
  NO_LEVANTA        ninguna entrada lo hace explotar.

EL CORPUS TAMBIEN SE GENERA. Los mensajes no son casos escritos: salen de la
cuenta real —la calculadora sobre el catalogo real— y de mutaciones que imitan
lo que el modelo escribe de mas: markdown, JSON filtrado, etiquetas de la
atadura, titulos huerfanos, renglones calcados, plata sin respaldo.

EL CANDADO ESTA PRIMERO A PROPOSITO. Un grafo que no coincide con el codigo es
peor que no tener grafo, porque se lee como si fuera cierto. `test_el_grafo_no_
puede_mentir` compara la tabla contra el codigo real de `procesar_venta`.
"""
import inspect
import re

import pytest

from app.verifika import grafo as G

TIENDA = "verifika_prod"


# ── 1. EL CANDADO: el grafo no puede mentir ────────────────────────────────

def test_cada_nodo_declara_una_funcion_que_existe_de_verdad():
    """La diferencia entre un grafo y una lista de nombres lindos. Cada nodo
    dice "modulo:funcion" y acá se importa y se busca el simbolo."""
    faltan = []
    for n in G.NODOS:
        modulo, _, funcion = n.funcion.partition(":")
        try:
            mod = __import__(modulo, fromlist=["x"])
        except ImportError as e:
            faltan.append(f"{n.id}: no importa {modulo} ({e})")
            continue
        if not hasattr(mod, funcion):
            faltan.append(f"{n.id}: {modulo} no tiene {funcion}")
    assert not faltan, "el grafo declara funciones que no existen: " + "; ".join(faltan)


def test_el_grafo_no_puede_mentir_sobre_el_orden_del_turno():
    """EL CANDADO QUE HACE QUE ESTO SEA VERDAD Y NO DOCUMENTACION.

    Los nodos de salida se declaran en un orden, y el turno los corre en un
    orden. Tienen que ser el mismo. Si alguien mueve una guardia de lugar en
    `procesar_venta` y no toca el grafo, esto se pone rojo en el push: el orden
    de las guardias NO es un detalle, es donde vivieron los dos errores de
    plata de esta semana."""
    from app.core.hub_venta import procesar_venta

    codigo = inspect.getsource(procesar_venta)
    posiciones = {}
    for n in G.nodos_de("salida"):
        m = re.search(rf'G\.paso\(\s*["\']{re.escape(n.id)}["\']', codigo)
        if m:
            posiciones[n.id] = m.start()
    declarados = [n.id for n in G.nodos_de("salida") if n.id in posiciones]
    reales = sorted(posiciones, key=posiciones.get)
    assert declarados == reales, (
        f"el orden declarado no es el real.\ndeclarado: {declarados}\n"
        f"real:      {reales}")
    # EL PISO SE DERIVA DEL GRAFO, NO ES UN NUMERO (24-ago-2026, FICHA 10).
    # Decia `>= 14` y era el conteo de nodos del dia que se escribio. Un piso
    # escrito a mano envejece de las dos maneras: si los nodos bajan a
    # proposito hay que aflojarlo -y aflojar un umbral es indistinguible de
    # borrar la vara-, y si suben deja de exigir nada. Lo que el candado quiere
    # decir es "TODOS los declarados estan cableados", y eso se escribe con
    # `len(nodos_de(salida))`: mas estricto que cualquier numero, y no envejece.
    declarables = [n for n in G.nodos_de("salida") if n.aplicar]
    assert len(posiciones) == len(declarables), (
        f"{len(posiciones)} de {len(declarables)} engranajes de salida pasan "
        "por el grafo: alguno se cableo por afuera y no deja veredicto")


def test_ningun_engranaje_de_salida_se_cablea_por_afuera_del_grafo():
    """LA OTRA MITAD DEL CANDADO, y es la que evita que el grafo envejezca. No
    alcanza con que lo declarado exista: hay que exigir que lo que EXISTE este
    declarado. Cada linea de `procesar_venta` que reasigna el texto tiene que
    pasar por `G.paso`, salvo las cuatro excepciones de abajo, que no son
    engranajes: son el texto que entra, el respaldo cuando no hubo modelo y la
    limpieza de ids internos."""
    import ast
    import textwrap

    from app.core.hub_venta import procesar_venta

    codigo = textwrap.dedent(inspect.getsource(procesar_venta))
    arbol = ast.parse(codigo)
    # Lo que SI puede escribir el texto sin ser una guardia: el redactor y el
    # cierre, que son nodos declarados del grafo pero producen el texto en vez
    # de transformarlo; el texto directo del decisor cuando el turno no usa
    # herramientas; los dos respaldos de cuando no hubo modelo; y la limpieza
    # de ids internos, que es una expresion regular sin logica propia.
    permitidas = ("G.paso", "_redactar", "_cerrar", "texto_directo",
                  "VERIFIKA_FALLBACK_MESSAGE", "_prosa", "_RE_ID_INTERNO")
    sueltas = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Assign):
            continue
        destinos = []
        for t in nodo.targets:
            destinos += ([e.id for e in t.elts if isinstance(e, ast.Name)]
                         if isinstance(t, ast.Tuple) else
                         [t.id] if isinstance(t, ast.Name) else [])
        if "texto" not in destinos:
            continue
        fuente = ast.get_source_segment(codigo, nodo.value) or ""
        if any(p in fuente for p in permitidas):
            continue
        sueltas.append(fuente.replace("\n", " ")[:90])
    assert not sueltas, (
        "engranajes que tocan el texto sin pasar por el grafo, o sea sin "
        "veredicto: " + " | ".join(sueltas))


def test_todo_nodo_de_salida_declara_al_menos_un_contrato():
    """Un nodo de salida sin contrato es un nodo que el barrido no puede
    controlar. Se permite solo cuando no transforma texto por si mismo —el
    cierre, que es una corrutina y arma el cobro—, y eso queda a la vista."""
    # LA EXCEPCION SE CIERRA (24-ago-2026, FICHA 10). Era `== ["cierre"]`: el
    # unico nodo de salida sin contrato mecanico era el que graba el lead y
    # arma el cobro. Con la salida en cuatro puertas el cierre deja de ser una
    # guardia -no verifica nada del texto- y baja a la etapa que le
    # corresponde, asi que la lista queda VACIA y la excepcion desaparece en
    # vez de heredarse. Cerrar lo permitido, no ampliarlo.
    sin_contrato = [n.id for n in G.nodos_de("salida") if not n.contratos]
    assert sin_contrato == [], (
        f"nodos de salida sin contrato: {sin_contrato}")


def test_todo_contrato_declarado_existe_y_todo_nodo_barrible_se_barre():
    """Que no se declare un contrato con un nombre que nadie comprueba.

    Los contratos son DOS familias y las dos valen: los de texto, que cumplen
    los nodos de salida, y los de datos, que cumple la mitad que decide. Un
    nombre que no este en ninguna de las dos es un contrato que nadie comprueba
    y que igual figura como cumplido, que es peor que no tenerlo."""
    universo = set(G.TODOS_LOS_CONTRATOS) | set(G.CONTRATOS_DE_DATOS)
    for n in G.NODOS:
        for c in n.contratos:
            assert c in universo, f"{n.id} declara '{c}', que no existe"
    # MISMO CAMBIO QUE EL PISO DEL CANDADO, y por el mismo motivo: lo que hay
    # que exigir es que NINGUN nodo de salida que transforma texto se quede
    # afuera del barrido, no que sean catorce. Un nodo con `aplicar` y sin
    # contratos es un nodo que el barrido no controla, y eso es lo que esto
    # tiene que poner rojo.
    fuera = [n.id for n in G.nodos_de("salida")
             if n.aplicar and not n.contratos]
    assert not fuera, f"nodos de salida que el barrido no controla: {fuera}"
    assert len(G.barribles()) >= 4, (
        f"solo {len(G.barribles())} nodos son barribles: el barrido se apago")
    # LA MITAD QUE DECIDE, CON LA MISMA CURA QUE LA DE ARRIBA (FICHA 11).
    #
    # DECIA `>= 10` Y ERA EL CONTEO DEL DIA QUE SE ESCRIBIO. Hoy hay ONCE nodos
    # de datos barribles y seis son la etapa de reposicion. La FICHA 11 los
    # funde en UNA puerta, asi que el numero pasa a 11 - 6 + 1 = 6 sin que se
    # apague una sola comprobacion: las seis piezas siguen corriendo adentro,
    # con sus mismos contratos, y el barrido las ejercita a traves de la puerta.
    #
    # LAS DOS MANERAS EN QUE UN PISO ESCRITO A MANO ENVEJECE, y este las tiene
    # las dos: con seis se pondria rojo sin que nada se haya apagado, y bajarlo
    # a `>= 6` seria un umbral movido para que pase el trabajo que lo movio, o
    # sea indistinguible de aflojar la vara. Es el mismo defecto que la FICHA 10
    # curo en el piso de al lado dos lineas mas arriba, y se cura igual: lo que
    # el candado quiere decir es "NINGUN nodo que mueve datos queda afuera del
    # barrido", y eso se escribe derivandolo del grafo.
    #
    # Y ES MAS ESTRICTO QUE EL NUMERO, no menos: `>= 10` dejaba entrar un nodo
    # nuevo sin contratos mientras hubiera diez viejos que si los tuvieran.
    # Esto lo pone rojo el dia que aparece.
    fuera_datos = [n.id for n in G.NODOS
                   if n.aplicar_datos and not n.contratos]
    assert not fuera_datos, (
        f"nodos de datos que el barrido no controla: {fuera_datos}")
    assert G.barribles_de_datos(), (
        "ningun nodo de datos es barrible: se apago el barrido de la mitad "
        "que decide")


# ── 2. EL CORPUS GENERADO ──────────────────────────────────────────────────

@pytest.fixture(scope="module")
def contextos(contexto, contexto_sin_cuenta):
    """LOS DOS REGIMENES DEL TURNO, y hay que barrer los dos.

    Un turno con cuenta y un turno SIN cuenta que devuelve un hallazgo son
    caminos distintos del mismo cableado: la mitad de las guardias se comporta
    al reves en cada uno. Barrer solo el primero deja al nodo del hallazgo
    pasando en falso, porque con una cuenta puesta ese nodo se calla por
    diseño. Esta es la ceguera de escenarios escrita como fixture."""
    return (contexto, contexto_sin_cuenta)


@pytest.fixture(scope="module")
def contexto_sin_cuenta(contexto):
    """El turno que NO cotizo y encontro algo parecido: el regimen del
    hallazgo. El bloque lo genera la herramienta real con un filtro que ningun
    producto cumple, no una copia escrita a mano."""
    from app.core import herramientas as H

    a = H.BuscarProductos(
        categoria="mouse", descripcion="mouse inalambrico",
        filtros=[{"campo": "precio_ars", "operador": "menor", "valor": "1"}])
    r = H.buscar_productos(a, TIENDA)
    assert r.get("bloque"), "la herramienta no devolvio hallazgo"
    ctx = dict(contexto)
    ctx["bloque"] = ""
    ctx["hallazgo"] = r["bloque"]
    ctx["llamadas"] = [{"herramienta": "buscar_productos",
                        "pedido": {"categoria": "mouse",
                                   "descripcion": "mouse inalambrico"},
                        "resultado": r}]
    ctx["corpus"] = [
        "Ninguno cumple del todo con lo que pediste.\n\n" + r["bloque"],
        "**Mira lo que encontre:**\n" + r["bloque"],
        "No tengo exactamente eso.",
    ]
    return ctx


@pytest.fixture(scope="module")
def contexto(firestore_doble):
    """El contexto de un turno real: una cuenta de verdad, calculada por la
    calculadora sobre el catalogo real, con sus llamadas como las arma el hub.

    Se genera, no se escribe: si mañana cambia el formato de la cuenta, el
    corpus cambia solo."""
    from app.core.contexto_turno import set_current_tienda
    from app.core import estado_venta
    from app.core.calculadora import calculate_total
    from app.storage.firestore_client import get_all_products

    set_current_tienda(TIENDA)
    prods = [p for p in get_all_products(tienda_id=TIENDA)
             if p.get("stock", 0) >= 3 and p.get("precio_ars")]
    prods.sort(key=lambda p: p["precio_ars"])
    dos = [prods[10], prods[len(prods) // 2]]
    estado_venta._envio_localidades.set([])
    estado_venta.set_envio_localidad("Cordoba, provincia de Cordoba")
    r = calculate_total(
        items=[{"product_id": p["id"], "cantidad": c}
               for c, p in zip((1, 2), dos)],
        items_extra=[{"faq_tema": "costo_envio", "concepto": "envio_caba_gba"}])
    assert r["ok"], r
    bloque = r["presentacion"]
    llamadas = [{"herramienta": "armar_presupuesto", "pedido": {},
                 "resultado": {"estado": "ok", "bloque": bloque,
                               "total_ars": r["total_ars"]}}]
    for p in dos:
        llamadas.append({
            "herramienta": "buscar_productos",
            "pedido": {"categoria": p.get("categoria", ""),
                       "descripcion": p.get("nombre", "")},
            "resultado": {"estado": "ok", "productos": [p]}})
    return {
        "llamadas": llamadas,
        "bloque": bloque,
        "tienda_id": TIENDA,
        "trace_id": "barrido-grafo",
        "previo": "",
        "vistos": dos,
        "negocio": "Verifika",
        "mensaje": "cuanto sale todo junto?",
        "anterior": "",
        "vocabulario": {p["nombre"] for p in prods},
        "productos": dos,
    }


def _corpus(ctx):
    """Los mensajes con los que se barre cada nodo. Uno sano, y despues las
    formas en que el modelo lo ensucia, que son las que las guardias existen
    para limpiar."""
    if ctx.get("corpus"):
        return ctx["corpus"]
    bloque = ctx["bloque"]
    nombre = ctx["productos"][0]["nombre"]
    return [
        # el turno sano, tal como el codigo lo arma
        f"Perfecto, te armo la cuenta.\n\n{bloque}\n\n¿Te lo mando a Cordoba?",
        # prosa sola, sin cuenta
        "Tenemos ese modelo en stock. ¿Querés que te arme el presupuesto?",
        # markdown, que WhatsApp no renderiza
        f"**Te paso el detalle:**\n\n{bloque}\n\n*Avisame*",
        # JSON de herramienta filtrado
        '{"herramienta": "buscar_productos", "args": {}}\n'
        f"Encontre esto:\n{bloque}",
        # etiqueta de la atadura fugada
        f"El <d MOU0023>{nombre}</d> esta disponible.\n{bloque}",
        # titulo que promete una lista y no muestra ninguna
        f"{bloque}\n\nReparto de los envios:\n\n¿Confirmamos?",
        # el mismo renglon largo, calcado
        "Te confirmo que el envio a Cordoba capital sale $7.500.\n"
        "Te confirmo que el envio a Cordoba capital sale $7.500.\n" + bloque,
        # plata sin respaldo en ninguna herramienta
        f"{bloque}\n\nY te hago un descuento especial de $99.999.",
        # la cuenta escrita dos veces
        f"{bloque}\n\n{bloque}",
        # narracion interna
        "El sistema me indica que hay varios modelos distintos, "
        f"asi que te paso lo que encontre.\n{bloque}",
        # anuncio sin nada abajo
        "Te paso el presupuesto por los dos productos:",
        # mensaje minimo
        "Hola",
    ]


# ── 3. EL BARRIDO DE CONTRATOS, generado del grafo ─────────────────────────

@pytest.fixture(scope="module")
def barrido_de_contratos(contextos):
    """Corre CADA nodo barrible sobre CADA mensaje del corpus, en los DOS
    regimenes del turno, y junta las violaciones de contrato. La lista de nodos
    no esta escrita acá: sale del grafo, asi que un engranaje nuevo entra al
    barrido por existir."""
    from app.verifika.invariantes import _importes

    fallas = []
    corridas = 0
    for ctx in contextos:
        corpus = _corpus(ctx)
        for nodo in G.barribles():
            permitidos = []
            for fuente in nodo.repone:
                permitidos += _importes(ctx.get(fuente) or "")
            for texto in corpus:
                corridas += 1
                try:
                    salida = nodo.aplicar(texto, ctx)
                except Exception as e:  # noqa: BLE001
                    if G.NO_LEVANTA in nodo.contratos:
                        fallas.append((nodo.id, G.NO_LEVANTA,
                                       f"{type(e).__name__}: {str(e)[:60]}",
                                       texto[:60]))
                    continue
                if G.NO_ENMUDECE in nodo.contratos:
                    if (texto or "").strip() and not (salida or "").strip():
                        fallas.append((nodo.id, G.NO_ENMUDECE,
                                       "dejo el turno mudo", texto[:60]))
                if G.NO_INVENTA_PLATA in nodo.contratos:
                    entraron = _importes(texto) + permitidos
                    nuevos = [x for x in _importes(salida) if x not in entraron]
                    if nuevos:
                        fallas.append((nodo.id, G.NO_INVENTA_PLATA,
                                       f"aparecio {nuevos[:3]}", texto[:60]))
                if G.IDEMPOTENTE in nodo.contratos:
                    try:
                        otra = nodo.aplicar(salida, ctx)
                    except Exception:  # noqa: BLE001 — ya se conto arriba
                        otra = salida
                    if otra != salida:
                        fallas.append((nodo.id, G.IDEMPOTENTE,
                                       f"{len(salida)} -> {len(otra)} en la "
                                       "segunda pasada", texto[:60]))
    return {"corridas": corridas, "fallas": fallas}


def test_el_barrido_del_grafo_recorre_todos_los_nodos(barrido_de_contratos,
                                                      contextos):
    """Que no se apague solo. Sin esto, un grafo vacio daria todos los
    contratos en verde, que es la trampa del tablero que este repo ya pago."""
    # LA CUENTA, ESCRITA (24-ago-2026, FICHA 10). Este numero era `>= 150`, que
    # era el conteo de nodos del dia que se escribio por el corpus de ese dia:
    # con dieciocho nodos de salida el barrido corria 234 veces y 150 era
    # holgura. Con cuatro puertas corre 60, asi que el 150 se pondria rojo sin
    # que nada se haya apagado, y bajarlo a otro numero repetiria el defecto.
    # Se escribe la CUENTA: nodos barribles por el corpus REAL de cada uno de
    # los dos regimenes -que no tienen el mismo largo, el del hallazgo trae
    # tres mensajes y el de la cuenta doce-. Asi exige el barrido entero y no
    # hay que tocarlo cuando cambian los nodos ni cuando crece el corpus.
    esperadas = len(G.barribles()) * sum(len(_corpus(c)) for c in contextos)
    assert barrido_de_contratos["corridas"] == esperadas, (
        f"el barrido corrio {barrido_de_contratos['corridas']} veces y "
        f"tenian que ser {esperadas}")


def test_ningun_engranaje_deja_mudo_al_bot(barrido_de_contratos):
    """El contrato mas caro de romper: un mensaje que entra con contenido no
    puede salir vacio. Le paso a Martin en real y el cliente leyo el texto de
    respaldo."""
    malas = [f for f in barrido_de_contratos["fallas"] if f[1] == G.NO_ENMUDECE]
    assert not malas, f"{len(malas)} nodos enmudecen: {malas[:3]}"


def test_ningun_engranaje_inventa_un_peso(barrido_de_contratos):
    """Todo importe que sale ya estaba en lo que entro, o en el bloque sellado
    que ese nodo declara que repone. La cuenta la hace la calculadora y nadie
    mas: ninguna guardia de salida puede crear un numero de plata."""
    malas = [f for f in barrido_de_contratos["fallas"]
             if f[1] == G.NO_INVENTA_PLATA]
    assert not malas, f"{len(malas)} nodos inventan plata: {malas[:3]}"


def test_ningun_engranaje_explota_con_una_entrada_del_corpus(barrido_de_contratos):
    """Una guardia que levanta deja el turno sin respuesta, que es peor que el
    defecto que venia a arreglar."""
    malas = [f for f in barrido_de_contratos["fallas"] if f[1] == G.NO_LEVANTA]
    assert not malas, f"{len(malas)} nodos levantan: {malas[:3]}"


def test_los_engranajes_son_idempotentes(barrido_de_contratos):
    """EL CONTRATO QUE PROTEGE DEL ORDEN, que es donde vivieron los dos errores
    de plata de esta semana. Un nodo idempotente no se puede romper porque otro
    corra antes, porque el turno lo pase dos veces o porque un reintento lo
    repita."""
    malas = [f for f in barrido_de_contratos["fallas"] if f[1] == G.IDEMPOTENTE]
    assert not malas, f"{len(malas)} nodos no son idempotentes: {malas[:3]}"


# ── 4. EL VEREDICTO POR ENGRANAJE ──────────────────────────────────────────

def test_el_veredicto_se_mide_comparando_y_no_se_le_pregunta_al_nodo():
    """La regla que lo hace confiable: "intervino" es que el texto cambio, no
    lo que el nodo diga de si mismo. Un nodo no puede mentir sobre esto."""
    G.abrir_turno()
    G.paso("sin_markdown", lambda t: t.replace("**", ""), "**hola** grande")
    G.paso("sin_json", lambda t: t, "no me toca nadie")
    v = G.veredicto_del_turno()
    assert v["engranajes"] == 2
    assert v["intervinieron"] == ["sin_markdown"]


def test_una_guardia_que_explota_no_tumba_el_turno_y_queda_marcada():
    """NO_ENMUDECE aplicado en vivo, no solo en el barrido: si un engranaje
    levanta, el texto sigue de largo tal como entro y el que fallo queda con
    nombre y apellido en el log del turno."""
    def rota(t):
        raise ValueError("me rompi")

    G.abrir_turno()
    salida = G.paso("sin_markdown", rota, "el mensaje del cliente")
    assert salida == "el mensaje del cliente"
    v = G.veredicto_del_turno()
    assert v["intervinieron"] == ["sin_markdown"]
    assert "levanto:ValueError" in v["detalle"][0]


def test_una_guardia_que_enmudece_se_descarta_sola():
    """Si una guardia devuelve vacio sobre un mensaje que tenia contenido, se
    descarta la pasada y se manda el texto anterior. El bot no queda mudo
    aunque un engranaje se rompa."""
    G.abrir_turno()
    salida = G.paso("componedor", lambda t, **k: "", "un mensaje con contenido")
    assert salida == "un mensaje con contenido"
    assert "enmudecio" in G.veredicto_del_turno()["detalle"][0]
