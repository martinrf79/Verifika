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
            "cuantos": {"type": "integer",
                        "description": f"Filas, hasta {TOPE_FILAS}."},
        },
    }
    return {
        "type": "function",
        "function": {
            "name": NOMBRE,
            "description": (
                "Busca en el catalogo de la tienda. Llamala ANTES de hablar de "
                "un producto: es el unico lugar del que salen las fichas y los "
                "precios. Podes mandar varias consultas juntas si el cliente "
                "pidio varias cosas, y podes volver a llamarla si lo que salio "
                "no sirve."),
            "parameters": {
                "type": "object",
                "properties": {
                    "consultas": {"type": "array", "items": consulta,
                                  "description": f"Hasta {TOPE_CONSULTAS}."}},
                "required": ["consultas"]},
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
    from app.core.filtros_catalogo import (aplicar, ordenar,
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
    if conds and not quedan:
        quedan, empatados, incumple = rankear_por_cercania(
            universo, conds, tienda_id)
        veredicto = "no_existe"
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
        # contestar. Por eso la marca es que el modelo haya pedido UNA fila.
        if tope == 1 and len(quedan) > 1:
            mejor = puntos[id(quedan[0])]
            empatados = sum(1 for p in quedan if puntos[id(p)] == mejor)
            if empatados > 1 and mejor > 0:
                veredicto = "ambiguo"
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

    return {"veredicto": veredicto,
            "cuantos_habia": cumplieron if conds else de_cuantos,
            "de_cuantos_se_miro": de_cuantos,
            "filas": [_ficha_corta(p) for p in quedan[:tope]],
            "no_aplicado": no_aplicado,
            "sin_dato": r.get("sin_dato", 0),
            "empatados": empatados,
            "motivo": "; ".join(notas)}


def buscar(consultas: list, tienda_id: str, trace_id: str = "") -> dict:
    """LA PUERTA. Varias consultas en una llamada, un resultado por consulta.

    No lanza: un error de busqueda deja al bot sin fichas, nunca mudo.
    """
    from app.storage.firestore_client import get_all_products
    try:
        catalogo = get_all_products(tienda_id=tienda_id) or []
    except Exception as e:  # noqa: BLE001 — sin catalogo se contesta sin fichas
        log.warning("motor_catalogo_error", trace_id=trace_id,
                    error=f"{type(e).__name__}: {e}")
        catalogo = []
    if not catalogo:
        return {"resultados": [], "motivo": "no se pudo leer el catalogo"}

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
             filas=[len(f["filas"]) for f in fuera])
    return {"resultados": fuera}


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
