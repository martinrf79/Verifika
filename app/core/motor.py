"""
EL MOTOR — la UNICA puerta por la que el modelo busca en la fuente.

QUE CAMBIA, y es lo unico que cambia. Hasta hoy el codigo ADIVINABA que fichas
ponerle delante al modelo: leia el mensaje crudo, sacaba palabras, y con eso
elegia cinco productos. El modelo recibia el resultado de una busqueda que
nunca pidio. Ahora la pide el.

POR QUE. El codigo no razona, asi que no puede elegir. Medido el 11-sep sobre
las funciones que adivinan: "que no sea de marca china" resolvia a
`origen no_contiene marc` —la raiz de "marca", que esta en los 880 origenes—,
o sea CERO productos y el bot contestando que no hay nada. No es un bug de esa
funcion: es que traducir una frase a un campo es razonar, y eso lo hace el
modelo o no lo hace nadie.

LA FORMA DE LA BUSQUEDA ES CONSULTA ESTRUCTURADA, y se descarto el resto:

  - PALABRA CLAVE SOLA no alcanza, y esta medido arriba.
  - EMBEDDINGS quedan afuera por la regla 10.4: una cita tiene que poder
    mapearse a un id. Un vecino cercano no se puede verificar mecanicamente, y
    lo que no se verifica no sale al cliente.
  - CONSULTA ESTRUCTURADA es el idioma nativo del modelo: campos y valores, que
    es lo que ya escribe. El codigo la EJECUTA, determinista de punta a punta.

El texto libre no se pierde: entra como UN campo mas de la consulta y lo resuelve
la relevancia, que ya existe y ya pesa por rareza. Es un criterio, no el
mecanismo.

UNA SOLA PUERTA Y UN SOLO NOMBRE. No son tres motores. Son tres MAPAS
—producto, envio, politicas— y un motor, porque el mecanismo de buscar es el
mismo en los tres. Si aparece un segundo motor, es la complejidad volviendo.

LO QUE ESTE MODULO NO HACE, a proposito:
  - No razona. No mira el mensaje del cliente: mira la consulta que el modelo
    escribio.
  - No inventa identidad. Devuelve un veredicto y ante `ambiguo` no elige.
  - No escribe un numero de plata. Devuelve la ficha con el precio ya escrito,
    igual que `fuente._ficha_corta`, y quien lo pone en el texto es `numeros`.

Y CASI TODO ESTO YA ESTABA. `aplicar`, `ordenar`, `rankear_por_cercania` y
`relevancia` viven en `filtros_catalogo` y estan medidas: la grilla entera del
barrido, 687 casos, da cero fallas. El motor las ENSAMBLA y les pone una puerta
con contrato. No es una capa nueva encima; es la puerta que faltaba.
"""
from app.logger import get_logger

log = get_logger(__name__)

NOMBRE = "buscar"

# Tope duro de filas por consulta. El modelo puede pedir menos, nunca mas: una
# busqueda que devuelve cuarenta fichas inunda el prompt y ademas no sirve, que
# es la leccion del catalogo entero que no entra.
TOPE_FILAS = 8
FILAS_POR_DEFECTO = 5

# Cuantas consultas entran en una llamada. Un pedido multiple —"dos auriculares,
# dos mouse y dos memorias"— es UNA llamada con tres consultas, no tres turnos.
TOPE_CONSULTAS = 6

# Hasta cuantos empatados siguen siendo UNA COSA con variantes -el mismo teclado
# en negro, blanco, gris y azul- y no un termino generico. Pasados estos, que el
# cliente haya nombrado una sola cosa y empaten veinte quiere decir que la
# nombro ancho, y ahi mostrar la lista es mejor que repreguntar.
TOPE_AMBIGUO = 4

# Cuantas politicas de la casa vuelven en una llamada. El mismo tope que ya
# usaba `fuente`, y por el mismo motivo: ante un tema ambiguo se sirven TODOS
# los candidatos en vez de elegir, y tres alcanza para eso.
TOPE_TEMAS = 3


class _Cond:
    """La condicion como la espera `filtros_catalogo.aplicar`, que lee por
    atributo. El modelo manda JSON, o sea diccionarios; esto es el unico
    adaptador y vive aca para que `aplicar` no tenga que saber de dos formas."""

    __slots__ = ("campo", "operador", "valor")

    def __init__(self, d: dict):
        self.campo = str((d or {}).get("campo") or "")
        self.operador = str((d or {}).get("operador") or "")
        self.valor = (d or {}).get("valor", "")


# ── EL ESQUEMA QUE VE EL MODELO ─────────────────────────────────────────────
#
# VIAJA COMO HERRAMIENTA DEL PROVEEDOR, NO COMO TEXTO. Es el primero de los
# tres candados de la FICHA 50: el modelo la ve en cada turno, con los nombres
# de campo validados por el enum. Un campo que no esta en el catalogo no se
# puede ni nombrar.
#
# LOS ENUMS SALEN DE LA FUENTE VIVA, igual que siempre. Tienda nueva, catalogo
# nuevo, esquema nuevo, sin tocar una linea de codigo.


def esquema(tienda_id: str) -> dict:
    """La herramienta tal como viaja al modelo, en formato OpenAI-compatible."""
    from app.core.filtros_catalogo import (OPERADORES, SIN_CAMPO,
                                           campos_filtrables, recorrida)
    r = recorrida(tienda_id)
    campos = sorted(campos_filtrables(tienda_id))
    categorias = [c for c, _ in r.get("categorias") or []]
    consulta = {
        "type": "object",
        "properties": {
            "texto": {
                "type": "string",
                "description": "Las palabras del cliente para buscar por "
                               "parecido. Opcional."},
            "categoria": {
                "type": "string", "enum": categorias,
                "description": "El rubro, si el cliente lo nombro."},
            "condiciones": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "campo": {"type": "string",
                                  "enum": campos + [SIN_CAMPO]},
                        "operador": {"type": "string",
                                     "enum": list(OPERADORES)},
                        "valor": {"type": "string"},
                    },
                    "required": ["campo", "operador", "valor"]},
                "description": "Lo que el producto tiene que cumplir. Si el "
                               f"catalogo no tiene campo para eso, usa "
                               f"'{SIN_CAMPO}' y se te dice."},
            "ordenar_por": {
                "type": "object",
                "properties": {
                    "campo": {"type": "string", "enum": campos},
                    "direccion": {"type": "string", "enum": ["min", "max"]}},
                "required": ["campo", "direccion"],
                "description": "Para 'el mas barato', 'el mas liviano'."},
            "ids": {
                "type": "array", "items": {"type": "string"},
                "description": "Ids exactos, para volver a un producto que ya "
                               "le mostraste."},
            "busco": {
                "type": "string", "enum": ["uno", "varios"],
                "description": "'uno' si el cliente nombro UN producto "
                               "puntual; 'varios' si pidio opciones. Con "
                               "'uno', si hay dos que pegan igual se te dice "
                               "y tenes que preguntar cual."},
            "cuantos": {"type": "integer",
                        "description": f"Filas, hasta {TOPE_FILAS}."},
        },
    }
    return {
        "type": "function",
        "function": {
            "name": NOMBRE,
            "description": (
                "Busca en la fuente de la tienda. Llamala ANTES de hablar de un "
                "producto o de una politica de la casa: es el unico lugar del "
                "que salen las fichas, los precios y lo que la casa tiene "
                "escrito. Podes mandar varias consultas juntas si el cliente "
                "pidio varias cosas, pedir politicas con `temas`, las dos cosas "
                "en la misma llamada, y volver a llamarla si lo que salio no "
                "sirve."),
            "parameters": {
                "type": "object",
                "properties": {
                    "consultas": {"type": "array", "items": consulta,
                                  "description": f"Hasta {TOPE_CONSULTAS}."},
                    # EL MAPA 3, Y ES UN CAMPO MAS DE LA MISMA PUERTA. No hay
                    # una herramienta nueva a proposito: el mecanismo de buscar
                    # en la fuente es el mismo, cambia que se busca. Una
                    # herramienta aparte serian dos puertas para lo mismo.
                    #
                    # NO LLEVA ENUM, y va contra la costumbre del resto del
                    # esquema. Los 129 temas pesaban 2.299 bytes en CADA
                    # llamada, y ese enum ya se saco una vez por eso (FICHA 06,
                    # 23-ago). El modelo nombra el tema con LAS PALABRAS DEL
                    # CLIENTE y `fuente.certificar_temas` lo resuelve contra las
                    # señas que la fuente ya tiene escritas: la atadura esta en
                    # el codigo, no en el esquema.
                    "temas": {
                        "type": "array", "items": {"type": "string"},
                        "description": (
                            "Lo que el cliente pregunta sobre la CASA y no "
                            "sobre un producto: garantia, cambios, cuotas, "
                            "facturacion, plazos. Nombra el tema CORTO, en "
                            "POCAS PALABRAS y con las del cliente: 'garantia', "
                            "'cambios', no la frase entera que escribio. Te "
                            "devuelvo lo que la casa tiene escrito, y si no lo "
                            "tiene te lo digo y se lo decis asi. Hasta "
                            f"{TOPE_TEMAS}.")}},
                "required": []},
        },
    }


# ── LA BUSQUEDA ─────────────────────────────────────────────────────────────


def _universo(catalogo: list, categoria: str, tienda_id: str) -> tuple:
    """El catalogo acotado al rubro que pidio el modelo. Si el rubro no existe
    se dice y se busca en todo: acotar a la nada devolveria cero en silencio."""
    from app.core.filtros_catalogo import _norm
    cat = _norm(categoria)
    if not cat:
        return catalogo, ""
    dentro = [p for p in catalogo if _norm(p.get("categoria")) == cat]
    if dentro:
        return dentro, ""
    return catalogo, f"la categoria '{categoria}' no existe en el catalogo"


def _por_ids(catalogo: list, ids: list) -> list:
    pedidos = [str(i).strip() for i in (ids or []) if str(i).strip()]
    if not pedidos:
        return []
    porid = {str(p.get("id")): p for p in catalogo}
    return [porid[i] for i in pedidos if i in porid]


def _una(consulta: dict, catalogo: list, tienda_id: str) -> dict:
    """UNA consulta del modelo contra el catalogo. Devuelve el resultado
    ENTERO: lo que trajo, cuantos habia, que no se pudo aplicar y por que.

    NUNCA VUELVE VACIA SIN MOTIVO ESCRITO. Es la regla de Martin del 2-ago y la
    razon por la que este contrato es mas grande que "una lista de productos":
    un cero sin explicacion hace que el modelo le diga al cliente que no hay,
    cuando lo que pasa es que la fuente no tiene el dato.
    """
    from app.core.fuente import _ficha_corta
    from app.core.filtros_catalogo import (aplicar, dato_que_falla, ordenar,
                                           orden_tiene_sentido,
                                           pesos_por_rareza,
                                           rankear_por_cercania, relevancia)
    c = consulta or {}
    texto = str(c.get("texto") or "").strip()
    tope = c.get("cuantos")
    try:
        tope = int(tope)
    except (TypeError, ValueError):
        tope = FILAS_POR_DEFECTO
    tope = max(1, min(TOPE_FILAS, tope))

    no_aplicado, notas = [], []

    # 1. POR ID PRIMERO. Es como resuelve la memoria —"el que me mostraste
    #    antes"— y no necesita ni parecido ni condiciones.
    if c.get("ids"):
        filas = _por_ids(catalogo, c["ids"])
        faltan = [str(i) for i in c["ids"] if str(i) not in
                  {str(p.get("id")) for p in filas}]
        return {"veredicto": "existe" if filas else "no_existe",
                "cuantos_habia": len(filas),
                "filas": [_ficha_corta(p) for p in filas[:tope]],
                "no_aplicado": ([{"campo": "ids", "motivo":
                                  f"no existen estos ids: {', '.join(faltan)}"}]
                                if faltan else []),
                "sin_dato": 0, "empatados": 0,
                "motivo": "" if filas else "ninguno de esos ids esta en el catalogo"}

    universo, aviso = _universo(catalogo, str(c.get("categoria") or ""),
                                tienda_id)
    if aviso:
        no_aplicado.append({"campo": "categoria", "motivo": aviso})
    de_cuantos = len(universo)

    # 2. LAS CONDICIONES. `aplicar` ya informa el tercer balde —los que no
    #    tienen el dato— y los filtros que no se pudieron aplicar con su motivo.
    conds = [_Cond(x) for x in (c.get("condiciones") or [])]
    r = aplicar(universo, conds, tienda_id) if conds else {
        "productos": universo, "aplicados": [], "descartados": [], "sin_dato": 0}
    no_aplicado.extend(r["descartados"])
    quedan = r["productos"]
    cumplieron = len(quedan)
    empatados = 0
    veredicto = "existe"

    # 3. EL RESCATE. Si ninguna cumple todo, se trae lo mas parecido y se dice
    #    cual condicion falla. Devolver vacio seria decirle al cliente que no
    #    existe lo que si existe con una condicion menos.
    rescate = False
    if conds and not quedan:
        quedan, empatados, incumple = rankear_por_cercania(
            universo, conds, tienda_id)
        veredicto = "no_existe"
        rescate = True
        notas.append(f"ninguno cumple todo; esto es lo mas parecido, "
                     f"incumple {incumple} de {len(conds)}")
        if empatados > 1:
            notas.append(f"{empatados} estan igual de lejos y se desempato "
                         f"por precio")

    # 4. EL ORDEN. Solo si ordenar por ese campo ordena por ALGO: sobre valores
    #    que son etiquetas —"China", "Negro"— el orden es alfabetico y no
    #    contesta ninguna pregunta que un cliente pueda hacer.
    orden = c.get("ordenar_por") or {}
    campo_orden = str(orden.get("campo") or "")
    if campo_orden:
        if quedan and orden_tiene_sentido(quedan, campo_orden, tienda_id):
            quedan = ordenar(quedan, campo_orden,
                             str(orden.get("direccion") or "min"), tienda_id)
        else:
            no_aplicado.append({
                "campo": campo_orden,
                "motivo": "ordenar por ese campo no ordena por nada: sus "
                          "valores son etiquetas, no magnitudes"})
    elif texto and quedan:
        raras = pesos_por_rareza(quedan, texto)
        puntos = {id(p): relevancia(p, texto, raras) for p in quedan}
        quedan = sorted(quedan, key=lambda p: (-puntos[id(p)],
                                               p.get("precio_ars") or 0))
        # AMBIGUO ES DE IDENTIDAD, Y SOLO DE IDENTIDAD.
        #
        # Es la regla 10.0: ante `ambiguous` el modelo esta OBLIGADO a
        # preguntar, no a elegir. Eso vale cuando el cliente nombro UNA cosa y
        # el catalogo tiene dos que le pegan igual —el mismo teclado en negro y
        # en blanco—: elegir ahi es inventar identidad.
        #
        # NO vale para un empate cualquiera. Que 171 notebooks esten igual de
        # lejos de un precio imposible no es una ambiguedad: es que la
        # condicion no se puede cumplir, y eso es `no_existe` con el rescate al
        # lado. Confundir los dos haria que el bot repregunte donde tiene que
        # contestar.
        #
        # LA MARCA LA DECLARA EL MODELO, Y ANTES ERA EL TOPE DE FILAS. Hasta el
        # 11-sep la condicion era `cuantos == 1`, o sea que se leia la
        # INTENCION del cliente desde una perilla de paginado. Dos agujeros
        # medidos: el modelo que pedia cinco filas de un producto puntual no
        # recibia la ambiguedad NUNCA —y ahi es donde elegir es inventar—, y
        # cualquier consulta con `cuantos: 1` la recibia aunque el cliente
        # hubiera pedido "el mas barato". Si el cliente nombro una cosa o pidio
        # opciones es IDIOMA, y el idioma lo lee el modelo: ahora lo declara en
        # `busco` y el codigo certifica el empate, que es lo unico que el
        # codigo puede saber.
        #
        # EL EMPATE DEL RESCATE NO SE PISA. `empatados` puede venir cargado de
        # arriba -"52 estan igual de lejos"- y eso es informacion del cliente:
        # solo se lo reemplaza cuando de verdad hay una ambiguedad de
        # identidad, nunca con un cero de paso.
        if str(c.get("busco") or "") == "uno" and len(quedan) > 1:
            mejor = puntos[id(quedan[0])]
            iguales = sum(1 for p in quedan if puntos[id(p)] == mejor)
            if 1 < iguales <= TOPE_AMBIGUO and mejor > 0:
                veredicto = "ambiguo"
                empatados = iguales
                notas.append(f"hay {empatados} que pegan igual con lo que "
                             f"pidio: no elijas, pregunta cual")
                # SE SIRVEN TODOS LOS CANDIDATOS, no el primero. Decirle al
                # modelo que hay dos y mostrarle uno es pedirle que pregunte
                # por algo que no puede ver. Es la misma linea que ya tiene
                # `certificar_temas` ante un tema ambiguo.
                quedan = quedan[:empatados]
                tope = min(TOPE_FILAS, max(tope, empatados))

    if not quedan:
        veredicto = "no_existe"
        notas.append("el catalogo no tiene nada de eso")

    # LA FILA DEL RESCATE DICE POR QUE NO CUMPLE, Y ES EL DATO REAL.
    #
    # Medido el 11-sep sobre el catalogo vivo: "un mouse que no sea de
    # fabricacion china" devuelve `no_existe` -los 52 lo son- con tres mouse al
    # lado como lo mas parecido, y esas tres fichas viajan MUDAS: el campo por
    # el que se filtro no esta en la ficha corta, porque `campos_ficha` trae los
    # del rubro. O sea que el modelo recibe tres mouse sin un solo dato que lo
    # contradiga y un motivo en prosa a un renglon de distancia. Ofrecer lo que
    # el cliente acaba de excluir esta a un paso.
    #
    # Con esto cada fila del rescate lleva `no_cumple` con el VALOR de la ficha
    # —"origen: Marca Genius de Taiwan. Fabricado en China."—, asi el modelo
    # puede decir la verdad entera: no tengo ninguno sin eso, y estos son los
    # que hay. Y el cliente decide, que es lo que no puede hacer si no lo ve.
    #
    # `dato_que_falla` ya estaba escrita para esto, con su caso y su fecha, y no
    # la llamaba nadie: quedo suelta cuando se apago el bloque que la usaba.
    filas = []
    for p in quedan[:tope]:
        f = _ficha_corta(p)
        if rescate:
            motivo_fila = dato_que_falla(p, conds, tienda_id)
            if motivo_fila:
                f["no_cumple"] = motivo_fila
        filas.append(f)

    return {"veredicto": veredicto,
            "cuantos_habia": cumplieron if conds else de_cuantos,
            "de_cuantos_se_miro": de_cuantos,
            "filas": filas,
            "no_aplicado": no_aplicado,
            "sin_dato": r.get("sin_dato", 0),
            "empatados": empatados,
            "motivo": "; ".join(notas)}


def buscar(consultas: list, tienda_id: str, trace_id: str = "",
           temas: list | None = None, temas_apagados=()) -> dict:
    """LA PUERTA. Productos y politicas de la casa, en una sola llamada.

    `temas_apagados` son los que OTRO bloque ya contesta mejor, y hoy es uno
    solo: el costo del envio, que `fuente.texto_envio` ya cotizo exacto para
    ese destino mientras la politica publica apenas el RANGO. Dos caminos para
    el mismo numero y ganaba el flojo; por cada cosa que se prende se apaga una.

    No lanza: un error de busqueda deja al bot sin fichas, nunca mudo.
    """
    from app.core.fuente import politicas_de
    fuera_temas, sin_resolver = [], []
    if temas:
        try:
            r = politicas_de(list(temas)[:TOPE_TEMAS], tienda_id)
            apagados = {str(t) for t in (temas_apagados or ())}
            fuera_temas = [p for p in r["politicas"]
                           if p["tema"] not in apagados]
            sin_resolver = r["sin_resolver"]
        except Exception as e:  # noqa: BLE001 — sin politica no se inventa una
            log.warning("motor_temas_error", trace_id=trace_id,
                        error=f"{type(e).__name__}: {str(e)[:120]}")

    if not consultas:
        # SOLO POLITICAS ES UNA LLAMADA VALIDA. "¿Cual es la politica de
        # garantia?" no necesita tocar el catalogo, y obligar a inventar una
        # consulta vacia para preguntarlo seria pedirle al modelo que aprenda
        # nuestra plomeria.
        return {"resultados": [], "politicas": fuera_temas,
                "temas_sin_resolver": sin_resolver}

    from app.storage.firestore_client import get_all_products
    try:
        catalogo = get_all_products(tienda_id=tienda_id) or []
    except Exception as e:  # noqa: BLE001 — sin catalogo se contesta sin fichas
        log.warning("motor_catalogo_error", trace_id=trace_id,
                    error=f"{type(e).__name__}: {e}")
        catalogo = []
    if not catalogo:
        return {"resultados": [], "politicas": fuera_temas,
                "temas_sin_resolver": sin_resolver,
                "motivo": "no se pudo leer el catalogo"}

    fuera = []
    for c in (consultas or [])[:TOPE_CONSULTAS]:
        try:
            fuera.append(_una(c, catalogo, tienda_id))
        except Exception as e:  # noqa: BLE001 — una consulta rota no tumba el resto
            log.warning("motor_consulta_error", trace_id=trace_id,
                        error=f"{type(e).__name__}: {str(e)[:120]}")
            fuera.append({"veredicto": "no_existe", "filas": [],
                          "cuantos_habia": 0, "no_aplicado": [], "sin_dato": 0,
                          "empatados": 0,
                          "motivo": "esa consulta no se pudo ejecutar"})
    log.info("motor_buscar", trace_id=trace_id, consultas=len(fuera),
             veredictos=[f["veredicto"] for f in fuera],
             filas=[len(f["filas"]) for f in fuera],
             temas=[p["tema"] for p in fuera_temas])
    return {"resultados": fuera, "politicas": fuera_temas,
            "temas_sin_resolver": sin_resolver}


def fichas_de(resultado: dict) -> list[dict]:
    """Las fichas de todas las consultas, sin repetir. Es lo que la guarda de
    procedencia necesita: un numero que no este en estas fichas no sale al
    cliente, y da igual en cual de las consultas aparecio."""
    fuera, vistos = [], set()
    for r in (resultado or {}).get("resultados") or []:
        for f in r.get("filas") or []:
            i = str(f.get("id"))
            if i not in vistos:
                vistos.add(i)
                fuera.append(f)
    return fuera
