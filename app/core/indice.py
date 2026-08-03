"""
INDICE — el vocabulario UNICO del sistema.

QUE ES. Una sola lista de nombres compartida entre lo que el INTERPRETE puede
declarar y lo que la FUENTE sabe contestar. Cada nombre es una CELDA, y cada
celda trae con que se responde. Nada mas.

POR QUE NACE, medido el 30-jul sobre las 66 charlas grabadas, 282 turnos:

  - El interprete solo podia nombrar las 93 categorias de base_conocimiento.
  - La fuente contesta ademas 50 temas de FAQ, de los cuales **23 NO estaban en
    ese enum**: cuotas, envios, garantia_como_usar, devoluciones,
    marcas_originales, mayoristas y 17 mas.
  - O sea que ante "puedo pagar en cuotas?" el interprete NO TENIA COMO DECIRLO.
    Su schema se lo prohibia. El unico que ruteaba era un regex de palabras
    clave sobre el mensaje crudo.
  - Medido: en 107 de 282 turnos el tema de FAQ lo aportaba ESE regex, no el
    interprete. En 85 pasaba lo mismo con el criterio.

Esa es la causa de los 116 regex repartidos en app/core, y la razon por la que
no se pueden borrar por disciplina: no estaban de mas, estaban TAPANDO un
vocabulario que al interprete le faltaba. Dos listas de nombres para el mismo
eje -93 categorias y 50 temas, con 27 en comun- y el regex haciendo de puente.

Este modulo elimina el puente juntando las dos listas en una. Con el vocabulario
unificado, el interprete puede DECLARAR lo que antes solo el regex adivinaba, y
el regex se queda sin trabajo.

TRES TIPOS DE CELDA, y la distincion no es decorativa:
  - dato    : la respuesta esta escrita en la fuente. La estampa el codigo.
  - calculo : la respuesta es una funcion determinista de la fuente (total,
              envio, reparto). La celda guarda la calculadora, no el valor.
  - criterio: NO hay respuesta guardada ni la va a haber ("me conviene?", "le
              sirve a mi hija?"). La celda guarda el material y el modelo
              redacta. Si se forzara una respuesta enlatada aca, el bot deja de
              vender y suena a maquina.

REGLA DE ESTE ARCHIVO: los resolutores reciben la CELDA y la FUENTE, nunca el
mensaje crudo del cliente. Sin mensaje no hay sobre que correr un regex, asi que
el segundo interprete no puede volver a nacer aca por descuido.
"""
from app.logger import get_logger

log = get_logger(__name__)

# Grupos que se contestan con PROSA. Si el interprete declara una celda de estas
# y el turno no la contesta, el cliente se queda sin respuesta a algo que
# pregunto. Son las que entran como slot REQUERIDO del schema del solver.
GRUPOS_PROSA = {"politica_faq", "objeciones", "comparacion_compatibilidad",
                "asesoramiento", "postventa", "seguridad", "casos_borde",
                "identidad_dato"}

_VOCAB_CACHE: dict = {}

# GEMELOS — la misma pregunta con dos nombres.
#
# El vocabulario junta dos listas que crecieron por separado, asi que hay
# preguntas que quedaron con nombre en las dos: el interprete declara una y la
# respuesta concreta esta guardada bajo la otra. Caso medido: ante "se puede
# pagar en cuotas sin interes?" el interprete declara `cuotas_financiacion`, que
# solo tiene el criterio vago "depende de tu tarjeta", mientras la cantidad REAL
# de cuotas vive en el tema de FAQ `cuotas`. En la corrida viva de 291 turnos eso
# explica los 24 en que el indice quedaba sin material.
#
# Se LINKEAN, no se fusionan: la celda suma el texto del gemelo y no se pierde
# ninguno de los dos. Fusionar borraria una de las dos respuestas.
#
# CADA PAR DE ACA SE VERIFICO LEYENDO LOS DOS TEXTOS, uno por uno. NO se armo por
# solape de palabras: ese metodo proponia cuatro pares que son preguntas
# DISTINTAS, y unirlos habria borrado una respuesta del bot sin que ningun test
# se pusiera en rojo. Quedan anotados abajo para que no se vuelvan a proponer.
#
# RECHAZADOS, y por que:
#   marcas_originales / marcas          -> "son originales?" no es "que marca me
#                                          conviene". Son dos respuestas.
#   stock_disponibilidad / urgencia_honesta -> "hay stock?" no es como transmitir
#                                          urgencia sin mentir. No se tocan.
#   formas_contacto / producto_no_vendido   -> no tienen nada que ver; el solape
#                                          de palabras fue casualidad.
GEMELOS = {
    "cuotas_financiacion": "cuotas",
    "cambios_devoluciones": "devoluciones",
    "mayorista_cantidad": "mayoristas",
    "producto_defectuoso": "defectuoso",
    "asesoramiento_metodo": "asesoramiento",
    "desconfianza_online": "confianza_seguridad",
    "envio_zonas": "envios",
    "teclado": "teclado_mecanico_membrana",
}


# ── OPERATIVAS — el texto que emite el CODIGO, no el modelo ─────────────────
#
# Son las respuestas que dispara una decision del flujo y no una pregunta del
# cliente: el pedido ya tomado, el handoff a una persona, el "no" al cierre.
# Hasta hoy vivian como constantes sueltas adentro de `leads.py` y salian al
# cliente sin pasar por ninguna puerta, asi que NADA en el sistema sabia que se
# habian dicho. Medido el 31-jul en los guiones 28 y 52: la misma frase salio
# textual en dos turnos seguidos y ninguna de las podas la vio, porque se pega
# DESPUES del render.
#
# Entran al indice como celdas de tipo `dato`, grupo `operativa`. Con id se las
# puede registrar, y registrado se sabe si ya se dijeron.
#
# NO entran al `vocabulario()`: el interprete no las declara nunca. No son temas
# que el cliente pregunta, son salidas que el flujo decide. Meterlas en su enum
# seria darle al modelo la posibilidad de disparar un handoff.
#
# El TEXTO de cada una vive en la fuente (`base_conocimiento.json`, bloque
# `mensajes`): son mensajes de marca que salen tal cual al cliente, y desde el
# 3-ago toda la prosa esta en un solo archivo. Lo que queda aca es CUALES son
# las operativas, que es cableado, no texto. El segundo argumento es la red por
# si el archivo faltara.
def _msj(clave: str, defecto: str) -> str:
    from app.core.guia_venta_prosa import mensaje
    return mensaje(clave, defecto)


OPERATIVAS = {
    "pedido_ya_tomado": _msj(
        "pedido_ya_tomado",
        "Tu pedido ya quedó tomado. Una persona del equipo te contacta a la "
        "brevedad para coordinar el pago y el envío. ¿Te ayudo con algo más?"),
    "no_interesado": _msj(
        "no_interesado",
        "Perfecto, sin problema. Cuando quieras retomar, acá estoy. "
        "Igual le paso el dato a una persona del equipo por si te puede dar "
        "una mano."),
    "handoff_humano": _msj(
        "handoff_humano",
        "Buenisimo, gracias por la decision. En un momento te contacta "
        "una persona del equipo para coordinar tu compra. Para que pueda "
        "hablarte directo, pasame por favor tu nombre y un telefono "
        "donde ubicarte."),
}


# ── CALCULOS — la celda guarda la FUNCION, no el valor ──────────────────────
#
# El tipo `calculo` estaba declarado arriba desde que nacio el indice y NO existia
# en el codigo: `celda()` solo sabia devolver dato o criterio. Por eso el costo de
# envio, que es una cuenta contra la tarifa de la fuente, viajaba como si fuera
# una politica escrita, y su texto generico -"depende de tu localidad"- se pegaba
# ENCIMA del numero que la calculadora acababa de estampar.
#
# Cada celda de calculo trae dos cosas:
#   `calculadora` : que funcion la resuelve. Es documentacion ejecutable de donde
#                   sale el numero; el que la corre sigue siendo el renderizador.
#   `marca`       : como se reconoce que ese valor YA esta en el mensaje. Sin
#                   esto no se puede saber si la celda quedo contestada, porque
#                   el fragmento de calculo no viaja rotulado con su nombre.
#
# La `marca` vivia hasta hoy como una tabla aparte adentro de `generador_v2`. Dos
# listas de lo mismo escritas a mano ya se cobraron un error hoy -el criterio del
# banco marcaba y la poda del codigo no podaba, porque estaban escritos por
# separado-. Una sola definicion, aca.
CALCULOS = {
    "costo_envio": {
        "calculadora": "tools.cotizar_envio",
        # "Envio: $6.000" / "el envio te sale $6.000"
        "marca": r"env[ií]o[^.\n]{0,20}\$\s?\d"},
    "plazo_envio": {
        "calculadora": "tools.cotizar_envio",
        # "2 a 3 dias habiles", tal cual sale de la tarifa
        "marca": r"\d+\s*(?:a\s*\d+\s*)?d[ií]as?\s+h[aá]biles"},
    "total": {
        "calculadora": "tools.calculate_total",
        # "Total: $26.500", el renglon que sella la cuenta
        "marca": r"total\s*:\s*\$\s?\d"},
}

# De que modulo sale cada calculadora. Un solo lugar donde el nombre de la celda
# se convierte en la funcion que la resuelve. Hasta hoy el indice la NOMBRABA en
# un string y cada consumidor la importaba por su cuenta, o sea que la relacion
# celda-funcion no vivia en ningun lado: estaba repartida entre el que nombraba y
# el que importaba, que es la misma forma de los dos errores de ayer.
_MODULOS = {"tools": "app.core.tools",
            "fuente_producto": "app.core.fuente_producto",
            "compatibilidad": "app.core.compatibilidad"}


def resolver(nombre: str):
    """La FUNCION que resuelve una celda de calculo. None si la celda no es de
    calculo o si su modulo no carga.

    El indice no ejecuta: devuelve CON QUE se ejecuta. Quien la corre sigue
    siendo el renderizador, que es el unico que tiene los items, el destino y el
    estado del turno. Esa division es a proposito: si el indice ejecutara,
    necesitaria el contexto del turno y volveria a ser un segundo orquestador."""
    c = CALCULOS.get(str(nombre or ""))
    if not c:
        return None
    mod, _, fn = str(c.get("calculadora") or "").partition(".")
    ruta = _MODULOS.get(mod)
    if not ruta or not fn:
        return None
    try:
        import importlib
        return getattr(importlib.import_module(ruta), fn, None)
    except Exception as e:
        log.warning("indice_resolver_error", celda=nombre, error=str(e)[:120])
        return None


# ── POR PRODUCTO — el otro eje de la fuente ─────────────────────────────────
#
# La FAQ, el criterio y las operativas se resuelven con el nombre solo. La ficha
# y la compatibilidad NO: necesitan ademas de que producto se habla. Es el mismo
# indice pero con un argumento mas, y por eso la celda lo declara en vez de que
# cada consumidor lo sepa de memoria.
#
# Los ids de spec ya los declara el interprete en `specs_preguntadas`, atados a
# esta misma fuente. Lo que faltaba era que el indice supiera que existen y con
# que se contestan: hasta hoy `fuente_producto` y `compatibilidad` las servian
# cada una por su lado y ninguna dejaba rastro de haber contestado.
_RESOLUTORES_PRODUCTO = {
    "spec": "fuente_producto.extraer_specs",
    "compatibilidad": "compatibilidad.bloque_ficha",
}


def resolver_producto(nombre: str):
    """La FUNCION que resuelve una celda por producto. Mismo contrato que
    `resolver` para las de calculo: devuelve con que se resuelve, no el valor,
    porque el producto lo tiene el renderizador y no el indice."""
    c = celda_producto(nombre)
    if not c:
        return None
    mod, _, fn = str(c.get("resolutor") or "").partition(".")
    ruta = _MODULOS.get(mod)
    if not ruta or not fn:
        return None
    try:
        import importlib
        return getattr(importlib.import_module(ruta), fn, None)
    except Exception as e:
        log.warning("indice_resolver_producto_error", celda=nombre,
                    error=str(e)[:120])
        return None


def _specs_ids() -> set:
    try:
        from app.core.fuente_producto import specs_config
        return {str(s["id"]) for s in (specs_config() or []) if s.get("id")}
    except Exception as e:
        log.warning("indice_specs_error", error=str(e)[:120])
        return set()


def celda_producto(nombre: str) -> dict | None:
    """La celda de un eje que se contesta CON un producto adelante. None si el
    nombre no es uno de esos.

    Devuelve el resolutor, no el valor: el indice dice de donde sale el dato, no
    lo va a buscar. Igual que en `calculo`, quien lo corre sigue siendo el
    renderizador, que es el unico que tiene el producto del turno."""
    cid = str(nombre or "").strip()
    if not cid:
        return None
    if cid == "compatibilidad":
        return {"nombre": cid, "tipo": "dato", "grupo": "producto",
                "necesita": "producto",
                "resolutor": _RESOLUTORES_PRODUCTO["compatibilidad"]}
    if cid in _specs_ids():
        return {"nombre": cid, "tipo": "dato", "grupo": "producto",
                "necesita": "producto",
                "resolutor": _RESOLUTORES_PRODUCTO["spec"]}
    return None


# QUE CELDA CONTESTA CADA CAMPO DE LA FICHA. La ficha estampa el dato del
# producto desde la fuente; esta tabla dice QUE PREGUNTA quedo contestada con
# eso, para que el turno no vuelva a pegar la prosa generica de esa misma
# pregunta abajo. Vive aca y no en el renderizador porque es conocimiento de la
# fuente -que responde que-, no de como se arma el texto.
# Conservador a proposito: solo los campos donde la ficha contesta LA MISMA
# pregunta. `garantia` queda afuera: la ficha dice cuantos meses, y la politica
# agrega como se gestiona, que es otra cosa y suma.
CELDA_DE_CAMPO_FICHA = {
    "caracteristicas": "especificaciones",
    "specs": "especificaciones",
    "medidas": "especificaciones",
    "contenido_caja": "contenido_caja",
    "material": "material_composicion",
    "procedencia": "origen_procedencia",
    "compatibilidad": "compatibilidad",
}


def celda_de_campo(campo: str) -> str:
    """La celda que queda contestada cuando la ficha estampa este campo."""
    return CELDA_DE_CAMPO_FICHA.get(str(campo or "").strip(), "")


def inventario(tienda_id=None) -> dict:
    """QUE SABE CONTESTAR EL SISTEMA, contado por fuente. Es el mapa de la fuente
    unica: si una fuente deja de cargar, se ve el cero acá en vez de descubrirlo
    seis semanas despues por una respuesta vacia.

    Nace de la falla que costo mas cara del proyecto: los 23 temas de FAQ que el
    interprete no podia nombrar estuvieron tapados por un regex durante meses
    porque nadie tenia el numero de cuantos temas sabia contestar cada fuente."""
    from app.core.guia_venta_prosa import categorias_conocimiento
    try:
        faq = len(_faq_dict(tienda_id))
    except Exception:
        faq = 0
    return {"vocabulario": len(vocabulario(tienda_id)),
            "faq": faq,
            "criterio": len(list(categorias_conocimiento())),
            "operativas": len(OPERATIVAS),
            "calculos": len(CALCULOS),
            "specs": len(_specs_ids())}


def marcas_de_calculo() -> dict:
    """{celda: patron} de las celdas de calculo. El renderizador pregunta esto
    para saber si el codigo ya contesto la celda con el numero real, y en ese
    caso no pegar la prosa generica encima."""
    return {n: c["marca"] for n, c in CALCULOS.items() if c.get("marca")}


def texto_operativo(nombre: str) -> str:
    """El texto de una celda operativa. Un solo lugar donde vive."""
    return OPERATIVAS.get(str(nombre or ""), "")


def registrar(meta: dict, nombre: str) -> None:
    """Anota que ESTA celda contesto en este turno.

    Es el registro que no existia: hasta hoy cada fuente entraba por su puerta y
    no dejaba rastro, asi que preguntas como "¿esto ya se dijo?" o "¿se contesto
    todo lo que pregunto?" habia que responderlas comparando TEXTO, una por una y
    con un parche distinto cada vez. Con el id anotado se responden una sola vez
    y valen para toda la fuente."""
    if not isinstance(meta, dict) or not nombre:
        return
    usadas = meta.setdefault("celdas_usadas", [])
    if nombre not in usadas:
        usadas.append(str(nombre))


def usadas(meta: dict) -> list:
    """Las celdas que contestaron en este turno, en orden."""
    return list((meta or {}).get("celdas_usadas") or [])


def _faq_dict(tienda_id):
    from app.storage.firestore_client import get_all_faq
    return get_all_faq(tienda_id=tienda_id) or {}


def vocabulario(tienda_id=None) -> list[str]:
    """LA lista de nombres del sistema: las categorias de base_conocimiento mas
    los temas de FAQ que no figuran entre ellas. Es el enum de `categorias` del
    interprete y la clave de este indice: una sola lista, no dos."""
    if tienda_id in _VOCAB_CACHE:
        return list(_VOCAB_CACHE[tienda_id])
    from app.core.guia_venta_prosa import categorias_conocimiento
    nombres = list(categorias_conocimiento())
    try:
        for t in _faq_dict(tienda_id):
            if t not in nombres:
                nombres.append(str(t))
    except Exception as e:
        # Sin FAQ el sistema sigue con las categorias: no se cae un turno por
        # esto. Y NO se cachea el resultado incompleto -si la primera consulta
        # cae antes de que Firestore este disponible, cachear dejaria al
        # interprete mudo sobre los 23 temas por el resto del proceso.
        log.warning("indice_vocabulario_sin_faq", error=str(e)[:120])
        return nombres
    _VOCAB_CACHE[tienda_id] = nombres
    return list(nombres)


def celda(nombre: str, tienda_id=None) -> dict | None:
    """Que sabe contestar la fuente sobre este nombre. None si no sabe nada, que
    es un resultado valido: el turno lo responde honesto sin inventar.

    Un nombre puede traer las DOS cosas -la politica escrita y el criterio de
    venta-; los 27 que estan en las dos listas son justamente esos. Se devuelven
    ambas y el solver usa la que le sirve, igual que hoy."""
    cid = str(nombre or "").strip()
    if not cid:
        return None
    if cid in OPERATIVAS:
        return {"nombre": cid, "tipo": "dato", "grupo": "operativa",
                "faq_tema": "", "texto_faq": OPERATIVAS[cid],
                "texto_faq_crudo": OPERATIVAS[cid], "texto_criterio": ""}
    from app.core.guia_venta_prosa import meta_categoria, texto_de
    from app.core.curadas import estampar_valores
    texto_faq, texto_faq_crudo, faq_tema = "", "", ""
    try:
        faq = _faq_dict(tienda_id)
        # el nombre propio, y si no tiene politica escrita, la de su GEMELO: la
        # misma pregunta guardada con el otro nombre.
        gem = GEMELOS.get(cid, "")
        d = faq.get(cid) or faq.get(gem, {}) or {}
        crudo = str(d.get("respuesta_curada") or d.get("respuesta") or "").strip()
        if crudo:
            faq_tema = cid if faq.get(cid) else gem
            # CRUDO = con los huecos {{concepto}} intactos. Es lo que ve el
            # SOLVER: asi redacta la politica en su voz pero el NUMERO no lo
            # escribe el, lo estampa el codigo desde la fuente al renderizar.
            # Mismo mecanismo que los precios, que el modelo tampoco escribe.
            texto_faq_crudo = crudo
            texto_faq = estampar_valores(crudo, d) or crudo
    except Exception as e:
        log.warning("indice_celda_faq_error", nombre=cid, error=str(e)[:120])
    texto_criterio = texto_de(cid) or ""
    if not texto_faq and not texto_criterio and cid not in CALCULOS:
        # Sin texto Y sin calculadora, la fuente no sabe nada de este nombre.
        # La excepcion de CALCULOS no es un detalle: `total` es una celda de
        # calculo PURA -no tiene politica escrita ni criterio de venta, la
        # respuesta es la cuenta- y este corte la devolvia None, o sea que el
        # indice declaraba tres calculos y solo podia entregar dos. El
        # inventario de /health decia 3. La fuente unica tiene que devolver lo
        # que dice que tiene.
        return None
    meta = meta_categoria(cid)
    # los temas que vienen SOLO de la FAQ no estan en base_conocimiento, asi que
    # no tienen grupo. Son politica de la tienda por definicion.
    grupo = meta.get("grupo") or ("politica_faq" if texto_faq else "")
    # una celda de CALCULO igual conserva su texto: la politica escrita sigue
    # siendo la respuesta valida cuando la cuenta no se puede hacer -sin destino
    # no hay tarifa-. Lo que cambia es que el que la consume sabe que hay una
    # funcion que manda por encima del texto.
    if cid in CALCULOS:
        return {"nombre": cid, "tipo": "calculo", "grupo": grupo,
                "calculadora": CALCULOS[cid]["calculadora"],
                "marca": CALCULOS[cid].get("marca", ""),
                "faq_tema": faq_tema, "texto_faq": texto_faq,
                "texto_faq_crudo": texto_faq_crudo,
                "texto_criterio": texto_criterio}
    return {"nombre": cid,
            "tipo": "dato" if texto_faq else "criterio",
            "grupo": grupo,
            "faq_tema": faq_tema,
            "texto_faq": texto_faq,
            "texto_faq_crudo": texto_faq_crudo,
            "texto_criterio": texto_criterio}


def celdas(nombres, tienda_id=None) -> list[dict]:
    """Las celdas de los nombres que declaro el interprete, sin repetir y en el
    orden en que las declaro."""
    out, vistos = [], set()
    for n in (nombres or []):
        cid = str(n or "").strip()
        if not cid or cid in vistos:
            continue
        vistos.add(cid)
        c = celda(cid, tienda_id)
        if c:
            out.append(c)
    return out


def obligatorias(celdas_turno, tope: int = 5) -> list[str]:
    """Las celdas que el turno DEBE contestar: las de prosa con material. Son los
    slots requeridos del schema del solver, asi que saltearlas es imposible a
    nivel API, no algo que se mida despues."""
    return [c["nombre"] for c in (celdas_turno or [])
            if c.get("grupo") in GRUPOS_PROSA][:tope]


def menu(celdas_turno, campo: str) -> str:
    """El material de las celdas para el prompt, una linea por celda con su id
    entre corchetes. `campo` es texto_faq o texto_criterio."""
    return "\n".join(f"  [{c['nombre']}] {c[campo]}"
                     for c in (celdas_turno or []) if c.get(campo))
