"""LA TABLA DE PUNTOS — lo que ve la segunda llamada.

Hasta hoy a la llamada dos le viajaban dos cosas: `json.dumps(llamadas)`, el
volcado crudo de las herramientas, y una instruccion en prosa al final del prompt
—"tu mensaje NO le contesta esto, agregalo"—. Y despues, cuando el texto volvia,
`salida._punto_omitido_repuesto` intentaba reponer con cirugia de strings el
punto que habia faltado.

O sea: el codigo YA sabia, punto por punto, que pregunto el cliente y que
material tenia para cada uno —lo calculaba `indice_turno.puntos` en cada turno— y
le mandaba al modelo un volcado sin esa estructura mas un reto. El modelo tenia
que aparear pregunta y evidencia solo. Eso es el cableado.

Este modulo arma la tabla. Una fila por punto, con tres cosas:

    pregunto   lo que el cliente pidio, con sus palabras
    estado     con_material | sin_material | sellado | pregunta
    material   SOLO los campos que esa pregunta necesita

QUE NO HACE: no llama al modelo, no escribe prosa, no decide que contestar, no
poda texto. Arma la mesa y se corre.

LOS CUATRO ESTADOS, y el cuarto se gano su lugar:

    con_material   hay con que contestar. El modelo redacta.
    sin_material   se pregunto y no hay dato. El modelo lo dice honesto o
                   pregunta. NO se completa de memoria.
    sellado        lo escribio el codigo y se pega tal cual: la cuenta.
    pregunta       una contradiccion declarada. No es falta de material: es que
                   resolverla seria elegir por el cliente. Sale como pregunta
                   siempre, aunque hubiera con que contestarla.

POR QUE EL MATERIAL VA PROYECTADO. Medido el 2-sep sobre el catalogo real: cinco
categorias pesan 17.061 caracteres mandando todos los campos de todos los
productos, y ahi `specs` es el 26,8% —18 claves por producto de las cuales el
cliente pregunto una— y `descripcion` el 13,4%, sin aportar UNA SOLA palabra que
no este en otro campo. Proyectado a lo que pide la pregunta, el mismo turno pesa
3.830 y entran los 12 productos enteros, contra 8 de 12 con el recorte.

Y hay un segundo efecto, que es el que importa para la prioridad uno: si el
cliente pregunta los DPI y la ficha no tiene DPI, el material sale VACIO en vez
de salir con los otros diecisiete campos. El modelo no tiene de donde sacar un
numero parecido. La alucinacion no se caza despues: no tiene con que nacer.

`puntos` se mudo ACA desde `indice_turno` el 3-sep-2026, cuando ese modulo se
apago. Vino entera y tal cual, con su docstring: es la unica pieza de las 1.738
lineas del indice que era comportamiento y no medicion. No usa nada mas de su
modulo viejo.
"""
import json
import re
import unicodedata

from app.logger import get_logger

log = get_logger(__name__)

# El tope existe como red, no como plan: con la proyeccion bien hecha un turno
# normal pesa la quinta parte. Si esto se toca, algo se esta mandando de mas.
TOPE = 14000

# Los campos de un producto que contesta una pregunta de COMPRA: cual es, cuanto
# sale, si lo hay. Nada mas. El resto se agrega solo cuando la pregunta lo pide.
_DE_COMPRA = ("id", "nombre", "precio", "stock")

# Las palabras con las que se PREGUNTA, que no nombran ningun campo. Sin esto,
# "que garantia tiene" pegaria en cualquier clave que contenga "tiene".
_VACIAS = frozenset({
    "que", "cual", "cuales", "cuanto", "cuanta", "cuantos", "cuantas", "como",
    "donde", "tiene", "tienen", "trae", "traen", "viene", "vienen", "con",
    "sin", "para", "por", "del", "las", "los", "una", "uno", "sus", "este",
    "esta", "estos", "estas", "ese", "esa", "esos", "esas", "and", "the"})


def _norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


def _palabras(s) -> set:
    return {w for w in re.split(r"[^a-z0-9]+", _norm(s)) if len(w) >= 3}


def _pega(termino: str, texto: str) -> bool:
    """El termino del punto contra el pedido de una herramienta. Alcanza con que
    comparta una palabra de tres letras o mas: el punto ya existe porque el
    cliente lo pidio, asi que esto solo elige CUAL llamada lo contesta, no si
    hay que contestarlo."""
    a, b = _palabras(termino), _palabras(texto)
    return bool(a and b and (a & b))


def _producto_de_compra(p: dict, extra=()) -> dict:
    """Un producto con lo que hace falta para venderlo, mas los campos que la
    pregunta del turno pidio expresamente."""
    out = {}
    for k in _DE_COMPRA:
        v = p.get(k)
        if k == "precio" and v is None:
            v = p.get("precio_ars")
        if v not in (None, "", [], {}):
            out[k] = v
    for k in extra:
        v = _valor_del_campo(p, k)
        if v not in (None, "", [], {}):
            out[k] = v
    return out


def _valor_del_campo(p: dict, campo: str):
    """El valor de un campo de la ficha, mirando primero arriba y despues en
    `specs`. Devuelve None si la ficha NO LO TIENE, y ese None es la respuesta:
    lo que la fuente no dice, no viaja."""
    if not campo:
        return None
    if campo in p:
        return p[campo]
    specs = p.get("specs") or {}
    if campo in specs:
        return specs[campo]
    # EL CLIENTE NO ESCRIBE EL NOMBRE DE LA COLUMNA, y el prefijo solo no
    # alcanza: medido, "lector de huella digital" contra `lector_huella` y
    # "cancelacion de ruido activa" contra `cancelacion_ruido` no comparten
    # prefijo y la ficha se daba por vacia teniendo el dato. Se cruza por
    # PALABRAS: gana la clave que comparta mas palabras de cuatro letras o mas
    # con lo que se pregunto, y hace falta al menos una. `peso` no alcanza
    # `precio` porque no comparten ninguna.
    # TRES LETRAS, NO CUATRO, y por los nombres de campo mas comunes de este
    # rubro: `ram`, `dpi`, `usb`, `ssd`, `hz`. Con cuatro, "cuanta ram tiene" se
    # quedaba sin una sola palabra util y la ficha se daba por vacia. Lo que
    # saca el ruido no es el largo, son las palabras de pregunta.
    pedidas = _palabras(campo) - _VACIAS
    if not pedidas:
        return None
    mejor, cuantas, largo = None, 0, 0
    for origen in (p, specs):
        for k, v in origen.items():
            comunes = len(pedidas & (_palabras(k) - _VACIAS))
            # A igualdad de palabras gana la clave mas CORTA: entre
            # `garantia_meses` y `garantia_detalle` la que contesta "cuanta
            # garantia" es la del numero, que es la regla que el repo ya aplica
            # en `resolver_orden` cuando dos campos empatan por nombre.
            if comunes > cuantas or (comunes == cuantas and comunes
                                     and len(str(k)) < largo):
                mejor, cuantas, largo = v, comunes, len(str(k))
    return mejor


def puntos(declarado: dict) -> list:
    """Lo interpretado, desarmado en puntos con id estable.

    El id es `campo:n` y `tipo` ES el campo de `registrar_pedido`. Sin apodo.
    El orden es el del molde, que es el del mensaje. Estable dentro del turno.
    """
    fuera: list = []
    if not declarado:
        return fuera

    for i, it in enumerate((declarado.get("items") or []), 1):
        que = str(it.get("que") or "").strip()
        if not que:
            continue
        cant = it.get("cantidad") or 1
        fuera.append({"id": f"items:{i}", "tipo": "items", "termino": que,
                      "texto": f"{cant} {que}"})

    for i, r in enumerate((declarado.get("restricciones") or []), 1):
        r = str(r or "").strip()
        if r:
            fuera.append({"id": f"restricciones:{i}", "tipo": "restricciones",
                          "termino": r, "texto": r})

    for i, d in enumerate((declarado.get("destinos") or []), 1):
        d = str(d or "").strip()
        if d:
            fuera.append({"id": f"destinos:{i}", "tipo": "destinos",
                          "termino": d, "texto": f"envio a {d}"})

    for i, c in enumerate((declarado.get("contradicciones") or []), 1):
        c = str(c or "").strip()
        if c:
            fuera.append({"id": f"contradicciones:{i}", "tipo": "contradicciones",
                          "termino": c, "texto": c})

    if declarado.get("reparto_pago"):
        pcts = [str(int(float(p.get("porcentaje") or 0)))
                for p in declarado["reparto_pago"]
                if p.get("porcentaje")]
        if pcts:
            fuera.append({"id": "reparto_pago:1", "tipo": "reparto_pago",
                          "termino": " ".join(pcts),
                          "texto": f"reparto del pago {'/'.join(pcts)}"})

    if declarado.get("pide_precio"):
        fuera.append({"id": "pide_precio:1", "tipo": "pide_precio",
                      "termino": "",
                      "texto": "el precio de lo que pidio"})

    # ── LAS CUATRO FAMILIAS INFORMATIVAS (FICHA 02, 21-ago-2026) ────────
    #
    # LAS SEIS DE ARRIBA SALEN TODAS DE `registrar_pedido`, o sea que el
    # sistema solo sabia abrir puntos sobre la parte TRANSACCIONAL: que
    # comprar, adonde va, como se paga. Si el cliente preguntaba cuantos Hz
    # tiene el monitor NO SE ABRIA NINGUN PUNTO, y entonces no quedaba nada
    # sin contestar —porque nunca se declaro que hubiera algo que contestar—.
    # El contrato de cobertura era ciego exactamente en las preguntas
    # informativas, que son la mitad de una conversacion de venta y son donde
    # mas se alucina.
    #
    # POR ESO EL 13% DE PUNTOS SIN CONTESTAR ES UN PISO Y NO EL NUMERO REAL.
    # El real es peor y no se puede medir hasta que existan las diez.
    #
    # EL PUNTO SALE DE LO DECLARADO, NUNCA DE LO BUSCADO. Es tentador abrir un
    # punto de `politica` porque se llamo a `consultar_temas`, y es circular:
    # si el punto existe porque se busco, entonces una pregunta que NADIE
    # busco no abre punto, y la omision —que es justo lo que queremos cazar—
    # se vuelve invisible. El punto nace de lo que el cliente pidio.
    #
    # Las cuatro informativas viven en el molde desde la FICHA 06. El tipo
    # es el campo. No se abre un punto porque se busco: se abre porque se
    # declaro.

    for i, a in enumerate((declarado.get("atributos") or []), 1):
        de = str((a or {}).get("de") or "").strip()
        campo = str((a or {}).get("campo") or "").strip()
        # UN ATRIBUTO SIN CAMPO NO ES UN PUNTO. "el monitor" no se puede
        # contestar; "los Hz del monitor" si. Un punto que no se contesta con
        # un dato concreto infla el denominador y hace BAJAR el porcentaje de
        # omision sin que nada haya mejorado, que es peor que no medirlo.
        if not de or not campo:
            continue
        fuera.append({"id": f"atributos:{i}", "tipo": "atributos",
                      "termino": de, "campo": campo,
                      "texto": f"{campo} de {de}"})

    for i, q in enumerate((declarado.get("stock") or []), 1):
        q = str(q or "").strip()
        if q:
            fuera.append({"id": f"stock:{i}", "tipo": "stock", "termino": q,
                          "texto": f"si hay stock de {q}"})

    for i, c in enumerate((declarado.get("compatibilidad") or []), 1):
        que = str((c or {}).get("que") or "").strip()
        para = str((c or {}).get("para") or "").strip()
        if not que or not para:
            continue
        fuera.append({"id": f"compatibilidad:{i}", "tipo": "compatibilidad",
                      "termino": f"{que} {para}", "que": que, "para": para,
                      "texto": f"si {que} sirve para {para}"})

    for i, t in enumerate((declarado.get("temas") or []), 1):
        t = str(t or "").strip()
        if t:
            # El tema viene con guion bajo -`costo_envio`, `garantia`- y el
            # matcher parte por espacios: sin esto `costo_envio` seria una sola
            # palabra que no aparece jamas en un mensaje escrito por nadie.
            fuera.append({"id": f"temas:{i}", "tipo": "temas",
                          "termino": t.replace("_", " "), "tema": t,
                          "texto": f"la politica de {t.replace('_', ' ')}"})

    return fuera


# ══════════════════════════════════════════════════════════════════════════
# EL INDICE DE LO QUE TRAJO EL TURNO
# ══════════════════════════════════════════════════════════════════════════

def _clasificar(llamadas: list) -> dict:
    """Las llamadas del turno agrupadas por lo que saben contestar. Una sola
    pasada, sin interpretar nada: se mira el pedido, que lo escribio el codigo."""
    idx = {"listas": [], "fichas": {}, "compat": [], "temas": {},
           "envios": {}, "agregados": []}
    for l in (llamadas or []):
        ped = (l.get("pedido") or {})
        res = (l.get("resultado") or {})
        nom = l.get("herramienta")
        if nom == "consultar_temas":
            for t in (res.get("temas") or []):
                if t.get("tema"):
                    idx["temas"][_norm(t["tema"])] = t
            continue
        if nom == "cotizar":
            if ped.get("localidad"):
                idx["envios"][_norm(ped["localidad"])] = res
            continue
        if nom != "consultar_productos":
            continue
        proy = ped.get("proyeccion")
        if proy == "ficha":
            p = res.get("producto") or {}
            if p.get("id"):
                idx["fichas"][p["id"]] = res
        elif proy == "compatibilidad":
            idx["compat"].append(res)
        elif proy == "catalogo":
            idx["agregados"].append({"pedido": ped, "resultado": res})
        else:
            idx["listas"].append({"pedido": ped, "resultado": res})
    return idx


def _campos_que_pidio_el_turno(declarado: dict, puntos: list) -> list:
    """Los campos del catalogo que este turno tiene que poder justificar: el que
    se pregunto como atributo, y el que ordena o filtra una restriccion. Sin
    esto el modelo dice "es la mas barata" sin tener el precio de las otras, o
    "tiene 24 meses" sin que la garantia haya viajado."""
    campos = []
    for p in puntos:
        c = p.get("campo")
        if c and c not in campos:
            campos.append(c)
    return campos


# ══════════════════════════════════════════════════════════════════════════
# LA TABLA
# ══════════════════════════════════════════════════════════════════════════

def _candidatos_ambiguos(termino: str, idx: dict, campos: list):
    """Los candidatos de una busqueda que volvio `ambiguo`, o None si no hubo.

    `ambiguous` no es un error ni una falta de material: es el unico veredicto
    ante el cual el codigo tiene PROHIBIDO elegir. Devolver los candidatos es lo
    que convierte esa prohibicion en una pregunta que se puede escribir.
    """
    for l in idx["listas"]:
        ped, res = l["pedido"], l["resultado"]
        texto_ped = f"{ped.get('descripcion','')} {ped.get('categoria','')}"
        if not _pega(termino, texto_ped):
            continue
        if res.get("estado") != "ambiguo":
            continue
        prods = [x for x in (res.get("productos") or []) if isinstance(x, dict)]
        return [{"cual_de_estos": [_producto_de_compra(x, campos)
                                   for x in prods]}]
    return None


def _material_del_punto(p: dict, idx: dict, campos: list) -> list:
    """El material de UN punto. Devuelve lista vacia cuando no hay: eso no es un
    error, es el dato que hace que el bot pregunte en vez de inventar."""
    tipo, termino = p.get("tipo"), str(p.get("termino") or "")

    if tipo in ("items", "stock", "restricciones"):
        # LAS LISTAS PRIMERO Y LOS AGREGADOS DE ULTIMA. Un agregado no lleva
        # descripcion —"que vendes" se contesta con los 22 rubros, no con tres
        # productos— asi que no puede competir por palabras con la busqueda que
        # el punto nombro. Entra cuando ninguna lista contesto: ahi es lo unico
        # que hay y contesta de verdad.
        for l in idx["listas"] + idx["agregados"]:
            ped, res = l["pedido"], l["resultado"]
            texto_ped = f"{ped.get('descripcion','')} {ped.get('categoria','')}"
            es_agregado = bool(ped.get("operacion"))
            es_del_punto = (_pega(termino, texto_ped)
                            or (es_agregado and tipo in ("items", "stock"))
                            or (tipo == "restricciones"
                                and (ped.get("ordenar_por") or ped.get("operacion")
                                     or ped.get("filtros"))))
            if not es_del_punto:
                continue
            uno = res.get("producto")
            prods = [uno] if isinstance(uno, dict) else (res.get("productos") or [])
            prods = [x for x in prods if isinstance(x, dict)]
            if prods:
                return [_producto_de_compra(x, campos) for x in prods]
            # EL "NO HAY" TAMBIEN ES MATERIAL, y esta es la parte que hace que
            # el bot conteste bien lo que no tiene. Una busqueda que volvio
            # vacia no deja al punto sin nada: deja el hecho de que no hay, y
            # los rubros que si vendemos, que es exactamente con lo que se
            # escribe un no honesto con salida. Sin esto el turno decia
            # `sin_material` y el modelo se quedaba sin con que contestar
            # justo en el caso donde mas facil es inventar.
            if res.get("estado") in ("no_encontrado", "sin_dato_en_la_fuente",
                                     "no_vendemos"):
                out = {"no_hay": res.get("buscado") or termino}
                cats = res.get("categorias_que_vendemos")
                if cats:
                    out["si_vendemos"] = cats
                # `no_vendemos` es el no honesto CON SALIDA que ya arma la
                # herramienta: dice cual es el rubro real de lo que pidieron y
                # con que se lo puede reemplazar. Viaja entero: es justo lo que
                # convierte un "no tenemos" seco en una venta posible.
                if res.get("rubro_real"):
                    out["rubro_real"] = res["rubro_real"]
                alt = res.get("alternativa")
                if alt:
                    out["alternativa"] = (
                        [_producto_de_compra(x, campos) for x in alt
                         if isinstance(x, dict)] if isinstance(alt, list)
                        else alt)
                if res.get("bloque"):
                    out["hecho"] = res["bloque"]
                return [out]
            if res.get("estado") == "ninguno_cumple_del_todo":
                out = {"ninguno_cumple": termino}
                if res.get("bloque"):
                    out["hecho"] = res["bloque"]
                cerca = [x for x in (res.get("productos")
                                     or res.get("candidatos") or [])
                         if isinstance(x, dict)]
                if cerca:
                    out["lo_mas_cerca"] = [_producto_de_compra(x, campos)
                                           for x in cerca]
                return [out]
            # UN AGREGADO contesta con `valores`, no con productos: "que
            # vendes" se contesta con los 22 rubros y cuantos hay de cada uno.
            if res.get("valores"):
                return [{"campo": res.get("campo"),
                         "cuantos_distintos": res.get("cuantos_distintos"),
                         "valores": res["valores"]}]
            if res.get("valor") is not None:
                return [{"campo": res.get("campo"), "valor": res["valor"]}]
        return []

    if tipo == "atributos":
        campo = str(p.get("campo") or "")
        # IDENTIDAD AMBIGUA: NO SE ELIGE, SE PREGUNTA, y esto es la regla cero
        # hecha estructura en vez de instruccion. `resolver` ya aborta la ficha
        # cuando el producto vuelve `ambiguo`, asi que sin esto el punto llegaba
        # vacio y el modelo no tenia con que preguntar bien. Ahora llega con los
        # candidatos y la pregunta se escribe sola: "cual de estas dos".
        amb = _candidatos_ambiguos(termino, idx, campos)
        if amb is not None:
            return amb
        for res in idx["fichas"].values():
            prod = res.get("producto")
            if not isinstance(prod, dict):
                continue
            if not _pega(termino, f"{prod.get('nombre','')} {prod.get('id','')}"):
                continue
            valor = _valor_del_campo(prod, campo)
            if valor in (None, "", [], {}):
                # LA FICHA NO LO TIENE. Sale vacio a proposito: mandar los otros
                # diecisiete campos es darle al modelo de donde sacar un numero
                # parecido, que es exactamente el caso C4-01 de los casos de oro.
                return []
            return [{"id": prod.get("id"), "nombre": prod.get("nombre"),
                     campo: valor}]
        return []

    if tipo == "compatibilidad":
        for res in idx["compat"]:
            # `producto` no siempre viene como ficha: segun el veredicto puede
            # llegar como el nombre pelado. Se normaliza aca y no se asume.
            prod = res.get("producto")
            prod = prod if isinstance(prod, dict) else {"nombre": str(prod or "")}
            if not _pega(str(p.get("que") or ""),
                         f"{prod.get('nombre','')} {prod.get('id','')}"):
                continue
            if res.get("estado") in ("equipo_desconocido", "no_encontrado"):
                return []
            return [{"id": prod.get("id"), "nombre": prod.get("nombre"),
                     "veredicto": res.get("estado"),
                     "porque": res.get("motivo") or res.get("detalle") or ""}]
        return []

    if tipo == "temas":
        t = idx["temas"].get(_norm(p.get("tema") or termino))
        if not t or t.get("estado") != "encontrado":
            return []
        return [{k: t[k] for k in ("tema", "politica", "valores", "criterio")
                 if t.get(k) not in (None, "", [], {})}]

    if tipo == "destinos":
        e = idx["envios"].get(_norm(termino))
        if not e or not e.get("ok"):
            return []
        return [{"localidad": termino, "costo": e.get("costo"),
                 "zona": e.get("zona")}]

    return []


def tabla(declarado: dict, llamadas: list, bloque: str = "",
          puntos_del_turno: list | None = None) -> dict:
    """LA MESA QUE VE LA SEGUNDA LLAMADA.

    Devuelve `{"puntos": [...], "bloque": str}`. El bloque de la cuenta viaja
    UNA sola vez, aparte: es lo unico que el modelo no redacta.

    No mira el texto de nadie —todavia no hay texto— y no vuelve a interpretar
    el mensaje: solo aparea lo declarado con lo que trajeron las herramientas.
    """
    if puntos_del_turno is None:
        puntos_del_turno = puntos(declarado or {})

    idx = _clasificar(llamadas)
    campos = _campos_que_pidio_el_turno(declarado or {}, puntos_del_turno)
    hay_cuenta = bool(re.search(r"(?i)total(?:\s+final)?\s*:", bloque or ""))

    filas = []
    for p in puntos_del_turno:
        tipo = p.get("tipo")
        fila = {"id": p.get("id"), "pregunto": p.get("texto")}

        if tipo == "contradicciones":
            # NUNCA se da por cubierta, aunque el turno tenga con que. Resolverla
            # es elegir por el cliente, que es la regla cero.
            fila["estado"] = "pregunta"
            fila["material"] = []
        elif tipo in ("pide_precio", "reparto_pago"):
            fila["estado"] = "sellado" if hay_cuenta else "sin_material"
            fila["material"] = []
        else:
            mat = _material_del_punto(p, idx, campos)
            if mat and any("cual_de_estos" in m for m in mat
                           if isinstance(m, dict)):
                # La identidad no se eligio, y por eso mismo hay que preguntar.
                fila["estado"] = "pregunta"
            else:
                fila["estado"] = "con_material" if mat else "sin_material"
            fila["material"] = mat
        filas.append(fila)

    out = {"puntos": filas}
    if bloque:
        out["bloque"] = bloque

    faltan = sum(1 for f in filas if f["estado"] == "sin_material")
    log.info("tabla_armada", puntos=len(filas), sin_material=faltan,
             sellado=sum(1 for f in filas if f["estado"] == "sellado"))
    return out


# ══════════════════════════════════════════════════════════════════════════
# EL ARMADO — la vuelta: el modelo devuelve la tabla llena y el codigo la pega
# ══════════════════════════════════════════════════════════════════════════
#
# LA PREGUNTA QUE ESTO CONTESTA, Y ES LA BUENA: ¿puede el codigo armar un
# mensaje sin que quede descolgado? Si el codigo ESCRIBIERA prosa, no. Por eso
# no escribe ni una palabra.
#
# El reparto es este, y es todo el diseño:
#
#   el MODELO escribe TODA la prosa —la apertura, el texto de cada punto y la
#   pregunta final— y la escribe viendo la tabla ENTERA de una sola vez. No son
#   respuestas sueltas cosidas despues: es un solo acto de escritura sobre un
#   material ordenado, igual que hoy, con la diferencia de que ve que contesta.
#
#   el CODIGO hace tres cosas y ninguna es redactar: ordena las casillas en el
#   orden en que el cliente pregunto, pega el bloque de la cuenta tal cual donde
#   va, y si una casilla quedo vacia escribe la pregunta por eso.
#
# La coherencia sale de que el que escribe ve todo. Lo que el codigo aporta es
# lo unico que la prosa no puede garantizar: que no falte nada y que la plata no
# se retipee.

ESQUEMA_RESPUESTA = {
    "type": "object",
    "properties": {
        "apertura": {
            "type": "string",
            "description": "Una frase corta para arrancar, o vacio si el "
                           "mensaje entra directo. No repitas lo que pregunto."},
        "puntos": {
            "type": "array",
            "description": "Uno por CADA fila de la tabla, con su mismo id y "
                           "en el mismo orden. Ninguno se saltea.",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "texto": {
                        "type": "string",
                        "description": "Lo que le decis al cliente sobre ESE "
                                       "punto, con el material de esa fila y "
                                       "nada mas. Si la fila dice sin_material, "
                                       "decilo honesto y no lo completes. Si "
                                       "dice sellado, dejalo vacio: la cuenta "
                                       "la pega el codigo. Sin precios: los "
                                       "numeros de plata salen del bloque."},
                },
                "required": ["id", "texto"],
            },
        },
        "pregunta_final": {
            "type": "string",
            "description": "UNA sola pregunta, al final, o vacio. Si alguna "
                           "fila dice pregunta, esta es por eso."},
    },
    "required": ["puntos"],
}



# ── LAS TRES QUE EL ESQUEMA NO PUEDE GARANTIZAR ────────────────────────────
#
# El esquema fija la FORMA: cuantas casillas hay, que cada una tenga su id, que
# haya una sola pregunta. Lo que NO puede fijar es el contenido de la prosa
# adentro de cada casilla, y ahi todavia entran tres cosas. Son tres, no
# cuarenta y seis, y son totales: no dependen de reconocer una redaccion.
#
#   1. UN NUMERO DE PLATA que no esta en el bloque sellado ni en el material.
#      La instruccion dice que no escriba precios; esto lo hace cierto.
#   2. UN ID INTERNO. `MOU0023` no es una alucinacion pero le rompe la charla
#      al cliente, y ademas es la forma de que una afirmacion se cuelgue de un
#      id que el turno nunca trajo.
#   3. UN PEDAZO DE JSON. El volcado interno filtrado.
#
# Se corta la ORACION, no el mensaje: podar de mas deja al bot mudo, y un turno
# mudo es peor que un turno feo. Si la poda se lleva todo, se deja el texto.

_RE_PLATA = re.compile(r"\$\s*[\d][\d.,]*")
_RE_ID_INTERNO = re.compile(r"\b[A-Z]{2,4}\d{3,5}\b")
_RE_JSON = re.compile(r'["\{\[]\s*"[a-z_]+"\s*:|"estado"\s*:|\{\s*"')


def _numeros_del_texto(t: str) -> set:
    return {re.sub(r"[.,]", "", m.group(0).replace("$", "").strip())
            for m in _RE_PLATA.finditer(t or "")}


def _limpiar(texto: str, mesa: dict, trace_id: str = "") -> str:
    """La casilla del modelo, sin lo que no puede escribir."""
    texto = (texto or "").strip()
    if not texto:
        return ""
    respaldo = _numeros_del_texto(mesa.get("bloque") or "")
    respaldo |= _numeros_del_texto(
        json.dumps(mesa.get("puntos") or [], ensure_ascii=False, default=str))
    fuera = []
    for oracion in re.split(r"(?<=[.!?])\s+", texto):
        motivo = ""
        sueltos = _numeros_del_texto(oracion) - respaldo
        if sueltos:
            motivo = f"plata_sin_respaldo:{sorted(sueltos)[:3]}"
        elif _RE_ID_INTERNO.search(oracion):
            motivo = "id_interno"
        elif _RE_JSON.search(oracion):
            motivo = "json_filtrado"
        if motivo:
            log.warning("casilla_podada", trace_id=trace_id, motivo=motivo,
                        oracion=oracion[:120])
            continue
        fuera.append(oracion)
    limpio = " ".join(fuera).strip()
    if not limpio:
        # LA CASILLA SE VA ENTERA, Y ESTA BIEN. La valvula del sistema viejo
        # -"si podar se lleva todo, no se poda"- existia porque ahi se podaba el
        # MENSAJE: cortarlo entero dejaba al bot mudo. Aca se poda UNA casilla y
        # el mensaje sigue teniendo las otras, el bloque sellado y la pregunta,
        # asi que vaciarla no enmudece a nadie. Mantener la valvula en este
        # nivel era peor que no tenerla: una casilla de una sola oracion con un
        # precio inventado pasaba intacta, que es justo el caso que esto ataja.
        # La valvula sigue existiendo, una sola vez, al final de `armar`.
        log.error("casilla_podada_entera", trace_id=trace_id,
                  texto=texto[:160])
    return limpio


def armar(respuesta: dict, mesa: dict, trace_id: str = "") -> str:
    """El mensaje al cliente, armado desde la tabla llena.

    `respuesta` es lo que devolvio el modelo con el esquema de arriba. `mesa` es
    lo que devolvio `tabla()`. El orden manda la mesa, no la respuesta: si el
    modelo devolvio los puntos en otro orden, se reordenan; si se salteo uno,
    se ve.
    """
    dicho = {str(p.get("id")): str(p.get("texto") or "").strip()
             for p in (respuesta.get("puntos") or []) if isinstance(p, dict)}
    partes = []
    ap = str(respuesta.get("apertura") or "").strip()
    if ap:
        partes.append(ap)

    sin_contestar = []
    hay_cuenta = False
    for fila in mesa.get("puntos") or []:
        pid, estado = fila.get("id"), fila.get("estado")
        if estado == "sellado":
            # LA CUENTA VA AL FINAL, no en el lugar que le toca por el molde.
            # Medido leyendo la muestra: el orden del molde la dejaba en el
            # medio, entre el envio y la garantia, y el mensaje quedaba partido
            # al medio por un bloque de numeros. Un presupuesto se lee al final,
            # justo antes de la pregunta que cierra, que es como lo manda
            # cualquier vendedor. Es lo unico que se saca del orden del cliente.
            hay_cuenta = True
            continue
        texto = _limpiar(dicho.get(pid, ""), mesa, trace_id)
        if texto:
            partes.append(texto)
        elif estado in ("sin_material", "pregunta"):
            sin_contestar.append(fila)
        else:
            # EL MODELO SE SALTEO UN PUNTO QUE SI TENIA CON QUE CONTESTAR, y eso
            # NO se tapa con una pregunta al cliente: preguntarle por algo que
            # el sistema sabia contestar es peor que no decirlo, porque lo hace
            # trabajar a el y ademas suena descolgado. Es un defecto del turno y
            # se mide como tal; el mensaje sale sin ese punto.
            log.warning("punto_con_material_sin_texto", punto=pid,
                        pregunto=fila.get("pregunto"))

    if hay_cuenta and mesa.get("bloque"):
        # Entera y sin retipear: si el modelo escribio algo en la casilla
        # sellada, se descarto arriba y nunca llego hasta aca.
        partes.append(mesa["bloque"].strip())

    pregunta = str(respuesta.get("pregunta_final") or "").strip()
    if not pregunta and sin_contestar:
        # EL CODIGO NO REDACTA, PERO NO DEJA UN HUECO MUDO. Si el modelo no
        # pregunto por lo que quedo sin contestar, la escribe el codigo. Y la
        # escribe SEGUN EL TIPO, no pegando el renglon crudo: pegado quedaba
        # "Una cosa para no equivocarme: que no sea caro, me lo confirmas?",
        # que es exactamente el riesgo de que el codigo arme prosa. Una sola
        # pregunta, la del primer punto que quedo abierto.
        pregunta = _pregunta_del_codigo(sin_contestar[0])
    if pregunta:
        partes.append(pregunta)

    mensaje = "\n\n".join(x for x in partes if x)
    # LA VALVULA, UNA SOLA VEZ Y AL FINAL. Si de todo el turno no quedo nada que
    # decir, el que llama cae al mensaje de demanda: es preferible a mandar un
    # texto vacio, y el error de arriba ya dejo la marca de por que paso.
    if not mensaje.strip():
        log.error("turno_sin_nada_que_decir", trace_id=trace_id,
                  puntos=len(mesa.get("puntos") or []))
    return mensaje


def _pregunta_del_codigo(fila: dict) -> str:
    """La unica prosa que el codigo escribe, y son cuatro moldes fijos.

    No es redaccion: es la forma minima de no dejar mudo un punto que el cliente
    pidio. Si el modelo pregunto por su cuenta, esto no corre nunca.
    """
    tipo = str(fila.get("id") or "").split(":")[0]
    que = str(fila.get("pregunto") or "").strip()
    # El texto del punto se arma pegando campo y producto —"garantia de el
    # mouse"— y eso leido en voz alta suena mal. Dos contracciones y listo: no
    # es redaccion, es no escribir mal el castellano.
    que = re.sub(r"(?i)\bde el\b", "del", que)
    que = re.sub(r"(?i)\ba el\b", "al", que)
    if tipo == "contradicciones":
        # El molde ya pide que la contradiccion se declare "como la duda
        # concreta que le harias", asi que viaja tal cual. Pero el signo no se
        # da por sentado: si el modelo la declaro como afirmacion, sale igual
        # como pregunta, porque preguntar es lo unico que se puede hacer con
        # una contradiccion.
        que = que.rstrip(".")
        return f"Antes de seguir, una duda: {que}" + ("" if que.endswith("?") else "?")
    if tipo == "restricciones":
        return (f"De la condicion que me pusiste, {que}, no tengo con que "
                f"confirmartelo. Me das un detalle mas y lo miro bien?")
    if tipo == "atributos":
        # NEUTRO EN GENERO A PROPOSITO. "Garantia del mouse no LO tengo" no
        # concuerda, y el codigo no puede saber el genero del campo que
        # pregunto el cliente. Se dice "el dato", que sirve para cualquiera:
        # es la forma de que el codigo escriba lo minimo sin escribir mal.
        return (f"De {que} no tengo el dato confirmado en la ficha. "
                f"Queres que lo consulte y te aviso?")
    if tipo == "stock":
        # El texto del punto ya arranca con "si hay stock de": pegarle "Sobre"
        # adelante da "Sobre si hay stock de". Se usa el termino pelado.
        cosa = que[len("si hay stock de "):] if que.startswith("si hay stock de ") else que
        return (f"De {cosa} no llegue a confirmarte el stock. "
                f"Me decis la marca o el modelo y lo busco?")
    return f"Sobre {que} no tengo el dato confirmado. Me lo precisas un poco?"
