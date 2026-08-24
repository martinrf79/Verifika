"""
EL INDICE DEL TURNO: el nexo entre lo que se INTERPRETO y lo que se RESPONDIO.

POR QUE EXISTE (Martin, 9-ago-2026, y lo venia pidiendo hace sesiones).

El sistema tiene dos mitades bien hechas y NADA que las ate:

  - La INTERPRETACION -`registrar_pedido`, el interprete de hoy- entiende bien.
    Medido el 8-ago: 100 sobre 100 en las cinco redacciones, 15 de 15 corridas,
    y la lista de "lo que no entiende" quedo VACIA.
  - La RESPUESTA -la redaccion final, el solver de hoy- se cae igual.

El reconciliador que ya existe compara lo declarado contra las LLAMADAS: sabe si
buscaste el rubro, si aplicaste la condicion, si armaste la cuenta. **Nadie mira
si el punto llego al TEXTO.** Un punto puede estar perfectamente ejecutado y no
salir dicho, y eso es exactamente lo que se mide fallando:
`cada_unidad_con_destino` falla entre 9 y 12 de cada 15 corridas. El cliente dice
a donde va cada cosa, el sistema lo entiende, lo guarda, y el mensaje no lo dice.

QUE HACE ESTE MODULO, y es una sola idea. Cada cosa que el cliente pidio se
convierte en un PUNTO con id estable. Despues se marca, punto por punto, si esa
cosa aparece en la respuesta. El resultado es una lista chica y legible:

    item:1   2 auriculares          -> atendido
    item:2   2 mouse                -> atendido
    destino:2 Concordia             -> FALTA
    pago:1   reparto 70/30          -> atendido

LO QUE NO HACE, y es a proposito. No inventa contenido, no reescribe prosa y no
decide por el cliente. Marca. Lo que se hace con un punto que falta lo decide
quien lo consume: hoy, decirselo al redactor con el punto concreto en la mano en
vez de una instruccion generica.

POR QUE CONTRA EL TEXTO Y NO CONTRA EL ESTADO. Es la regla de tau-bench que ya
usa `objetivo.py`: se juzga por lo observado, no por lo que el agente cuenta que
hizo. El cliente no lee el estado interno: lee el mensaje.
"""
import re
import unicodedata

from app.logger import get_logger

log = get_logger(__name__)


def _n(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def _raiz(palabra: str) -> str:
    """La palabra sin su plural naive. "memorias" y "memoria" son el mismo
    punto, y "auriculares" tiene que encontrarse en "Auriculares Redragon"."""
    p = _n(palabra).strip()
    for cola in ("es", "s"):
        if len(p) > 4 and p.endswith(cola):
            return p[:-len(cola)]
    return p


def _aparece(termino: str, texto: str) -> bool:
    """¿El termino esta en el texto?

    SE COMPARA POR RAIZ CORTA Y DESDE EL ARRANQUE DE PALABRA, y las dos cosas
    tienen su motivo medido. El cliente dijo "partes CHINAS" y el bot escribio
    "de origen CHINO": con la palabra entera el punto figuraba sin atender
    cuando estaba dicho, y un indice que marca en falso es peor que no tener
    indice, porque manda a agregar algo que ya esta. Y el ancla `\\b` al
    arranque evita que "mouse" se de por dicho porque el texto nombre otra cosa
    que lo contenga en el medio."""
    t = _n(texto)
    partes = []
    for w in _n(termino).split():
        if len(w) < 3:
            continue
        r = _raiz(w)
        # De 5 letras para arriba alcanza el prefijo: chin(as|o|a), memoria(s),
        # auricular(es). Mas corto que eso se busca entero, para no pegarle a
        # cualquier palabra.
        partes.append(r[:4] if len(r) >= 5 else r)
    if not partes:
        return False
    return all(re.search(rf"\b{re.escape(p)}", t) for p in partes)


# ── LOS PUNTOS: cada cosa que el cliente pidio, con su id ────────────────────
def puntos(declarado: dict) -> list:
    """Lo interpretado, desarmado en puntos con id estable.

    El id es `tipo:n` y se arma del ORDEN en que el modelo declaro, que es el
    orden del mensaje del cliente. Estable dentro del turno, que es lo que hace
    falta para atar interpretacion con respuesta.
    """
    fuera: list = []
    if not declarado:
        return fuera

    for i, it in enumerate((declarado.get("items") or []), 1):
        que = str(it.get("que") or "").strip()
        if not que:
            continue
        cant = it.get("cantidad") or 1
        fuera.append({"id": f"item:{i}", "tipo": "item", "termino": que,
                      "texto": f"{cant} {que}"})

    for i, r in enumerate((declarado.get("restricciones") or []), 1):
        r = str(r or "").strip()
        if r:
            fuera.append({"id": f"condicion:{i}", "tipo": "condicion",
                          "termino": r, "texto": r})

    for i, d in enumerate((declarado.get("destinos") or []), 1):
        d = str(d or "").strip()
        if d:
            fuera.append({"id": f"destino:{i}", "tipo": "destino",
                          "termino": d, "texto": f"envio a {d}"})

    for i, c in enumerate((declarado.get("contradicciones") or []), 1):
        c = str(c or "").strip()
        if c:
            fuera.append({"id": f"duda:{i}", "tipo": "duda", "termino": c,
                          "texto": c})

    if declarado.get("reparto_pago"):
        pcts = [str(int(float(p.get("porcentaje") or 0)))
                for p in declarado["reparto_pago"]
                if p.get("porcentaje")]
        if pcts:
            fuera.append({"id": "pago:1", "tipo": "pago",
                          "termino": " ".join(pcts),
                          "texto": f"reparto del pago {'/'.join(pcts)}"})

    if declarado.get("pide_precio"):
        fuera.append({"id": "precio:1", "tipo": "precio", "termino": "",
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
    # AVISO PARA LA SESION QUE LEA EL NUMERO, y es la trampa de esta unidad:
    # hoy `registrar_pedido` NO tiene los campos `atributos`, `stock`,
    # `compatibilidad` ni `temas`, asi que en una charla real estas cuatro
    # familias NO SE ABREN TODAVIA. Agregarlos al molde cambia el esquema que
    # ve el modelo y es otra unidad, con otro riesgo. **Un numero bajo de
    # puntos nuevos en el corpus grabado no quiere decir que la omision bajo:
    # quiere decir que todavia no se puede medir.**

    for i, a in enumerate((declarado.get("atributos") or []), 1):
        de = str((a or {}).get("de") or "").strip()
        campo = str((a or {}).get("campo") or "").strip()
        # UN ATRIBUTO SIN CAMPO NO ES UN PUNTO. "el monitor" no se puede
        # contestar; "los Hz del monitor" si. Un punto que no se contesta con
        # un dato concreto infla el denominador y hace BAJAR el porcentaje de
        # omision sin que nada haya mejorado, que es peor que no medirlo.
        if not de or not campo:
            continue
        fuera.append({"id": f"atributo:{i}", "tipo": "atributo",
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
            fuera.append({"id": f"politica:{i}", "tipo": "politica",
                          "termino": t.replace("_", " "), "tema": t,
                          "texto": f"la politica de {t.replace('_', ' ')}"})

    return fuera


# ── LOS ANCLAJES: la EVIDENCIA con que ese punto se contesta ────────────────
#
# EL DEFECTO QUE ESTO CIERRA, medido el 12-ago sobre las charlas grabadas. El
# indice decia que 65 de 515 puntos no llegaban al texto, y al leerlos uno por
# uno la MAYORIA eran falsas alarmas suyas: el cliente pidio "para jugar" y el
# bot escribio "gaming"; pidio "barato" y el bot escribio "la mas economica";
# pidio "celulares Samsung" y el bot contesto "de Samsung tenemos 38 modelos".
# Los tres estaban contestados y los tres figuraban sin atender.
#
# LA CAUSA ES DE FONDO, no un umbral mal puesto: el vinculo entre lo
# interpretado y lo respondido se estaba RECONSTRUYENDO al final comparando las
# PALABRAS DEL CLIENTE contra la prosa del modelo, y esas dos nunca coinciden
# porque el modelo escribe con sus palabras. Comparar por parecido de texto
# falla en las dos direcciones: acusa lo que esta dicho con otro sinonimo, y
# deja pasar lo que se dijo de un producto equivocado.
#
# LA SOLUCION ES ATAR POR IDENTIDAD, Y LA IDENTIDAD LA TIENE EL CODIGO. Cada
# punto se contesta con lo que trajo una herramienta, y eso el sistema lo sabe
# con nombre y apellido: el producto certificado que devolvio la busqueda, la
# localidad que cotizo el envio, el total que calculo la calculadora. Esos son
# los ANCLAJES. "Gaming" no se parece a "jugar", pero "Logitech M170" es
# exactamente el producto que la busqueda del punto uno devolvio, y si esta en
# el mensaje, el punto uno esta contestado. No hay sinonimo que rompa eso.
#
# POR QUE NO SE LE PIDE LA MARCA AL MODELO. Era el otro camino: que el modelo
# escriba `<p item:1>` alrededor de lo que contesta cada punto, como ya escribe
# `<d ID>` para la atadura. Funciona igual de bien y cuesta mucho mas: cambia el
# CONTRATO con el modelo, o sea que obliga a regrabar los diez casetes con la
# clave paga cada vez. La evidencia ya esta del lado del codigo; pedirsela al
# modelo seria pagar por un dato que ya tenemos.
#
# ES MONOTONO A PROPOSITO: el anclaje solo puede sacar una alarma, nunca
# agregar una. Un punto que hoy figura atendido va a seguir figurando atendido.

# Palabras que no anclan nada porque estan en cualquier mensaje.
_VACIAS = {"que", "las", "los", "una", "unas", "unos", "con", "sin", "para",
           "por", "del", "mas", "muy", "todo", "todos", "quiero", "necesito",
           "cantidad", "posible", "posibles", "tenga", "tengan", "sea", "sean"}

# Las herramientas que traen material con el que se contesta un punto.
_TRAEN = ("buscar_productos", "ficha_producto", "comparar_productos",
          "armar_presupuesto", "cotizar_envio", "consultar_temas")


def _palabras(texto: str) -> list:
    return [w for w in _n(texto).replace("/", " ").split()
            if len(w) >= 3 and w not in _VACIAS]


def _ancla_en(ancla: str, texto: str) -> bool:
    """¿El anclaje esta dicho en el mensaje?

    NO se exige el nombre completo, y tiene su motivo medido: la busqueda
    devuelve "Mouse Logitech M170 Negro" y el bot escribe "el Logitech M170 es
    la opcion mas economica". Exigir las cuatro palabras dejaria el punto sin
    atender teniendolo contestado, que es justo el defecto que esto viene a
    arreglar. Se pide lo que identifica: dos palabras del anclaje, o UNA sola
    si lleva numero adentro -"M170", "DX-110", "245"- porque un modelo con
    numero no aparece en un mensaje por casualidad."""
    ws = _palabras(ancla)
    if not ws:
        return False
    presentes = [w for w in ws if _aparece(w, texto)]
    if any(any(c.isdigit() for c in w) for w in presentes):
        return True
    # UNA SOLA PALABRA ALCANZA SI ES LARGA, y lo decidio un caso medido: el
    # cliente pregunto por celulares Samsung e iPhone, el codigo busco
    # "samsung", y el bot contesto "de Samsung tenemos 38 modelos, de iPhone no
    # trabajamos ninguna linea" —una respuesta correcta que no nombra un solo
    # producto—. Con el minimo de dos palabras ese anclaje no contaba nunca y el
    # punto figuraba sin atender. De cinco letras para arriba una palabra ya
    # identifica; abajo de eso se siguen pidiendo dos.
    if len(presentes) == 1 and len(presentes[0]) >= 5:
        return True
    return len(presentes) >= 2


def _fichas_de(resultado: dict) -> list:
    """Todos los productos que devolvio una herramienta, vengan por la puerta
    que vengan.

    LAS TRES PUERTAS, y la tercera es la que faltaba: `productos` cuando la
    busqueda encontro, `producto` cuando es una ficha sola, y
    `hay_en_la_categoria` cuando el modelo EXACTO no existe y se muestran los
    de esa linea. Ese tercer caso es una respuesta correcta y frecuente —"ese
    SSD de 7000 MB/s no lo tenemos, pero si estos"— y el indice no la veia
    porque miraba solo la primera puerta. El mismo dato con otro nombre de
    campo: plomeria, no logica."""
    r = resultado or {}
    fichas = list(r.get("productos") or []) + list(r.get("hay_en_la_categoria") or [])
    if r.get("producto"):
        fichas.append(r["producto"])
    return [f for f in fichas if isinstance(f, dict)]


def _atiende(punto: dict, llamada: dict) -> bool:
    """¿Esta llamada fue por ESTE punto? Se compara lo que el cliente pidio
    contra lo que el codigo BUSCO -categoria y descripcion, que son campos
    estructurados-, no contra la prosa. Alcanza con que compartan una palabra
    con peso: el rubro es lo que las une, y el resto son adjetivos que cada uno
    dice a su manera."""
    ped = llamada.get("pedido") or {}
    universo = " ".join(str(ped.get(k) or "") for k in
                        ("categoria", "descripcion", "localidad", "que"))
    del_punto = set(_palabras(punto.get("termino") or ""))
    return bool(del_punto & set(_palabras(universo)))


def anclajes(punto: dict, llamadas: list, memoria: list | None = None) -> list:
    """La EVIDENCIA de un punto: los textos concretos con los que el sistema
    puede haberlo contestado. Vacio si ninguna herramienta lo atendio, y ahi el
    punto se sigue midiendo como antes.

    `memoria` son el carrito vigente y los productos ya mostrados. LA EVIDENCIA
    DE UN PUNTO NO SIEMPRE ESTA EN ESTE TURNO, y el caso que lo mostro es una
    negociacion: el cliente pide dos unidades de la notebook que venia mirando,
    el turno no llama a ninguna herramienta porque no hace falta, y el punto
    quedaba sin evidencia aunque el bot lo contestara nombrando el equipo. Solo
    ancla el producto de la memoria que el punto NOMBRA: sin esa atadura,
    cualquier producto visto contestaria cualquier punto."""
    tipo = punto.get("tipo")
    fuera: list = []
    del_punto = set(_palabras(punto.get("termino") or ""))
    for p in (memoria or []):
        nombre = str((p or {}).get("nombre") or "")
        if nombre and del_punto & set(_palabras(nombre)):
            fuera.append(nombre)
    if not llamadas:
        return [a for a in dict.fromkeys(fuera) if a.strip()]
    for l in llamadas:
        # `ver_compatibilidad` entra SOLO para su propio tipo, y no se suma a
        # `_TRAEN`: sumarla ahi le daria evidencia nueva a `item` y a
        # `condicion`, que es un cambio de comportamiento en puntos que ya se
        # miden hoy. El anclaje solo puede SACAR una alarma, nunca agregarla,
        # asi que ampliar la fuente de evidencia de un tipo viejo mueve
        # numeros que esta unidad no tiene que mover.
        _herr = l.get("herramienta")
        if _herr not in _TRAEN and not (tipo == "compatibilidad"
                                        and _herr == "ver_compatibilidad"):
            continue
        r = l.get("resultado") or {}
        ped = l.get("pedido") or {}
        # UNA CONDICION NO COMPARTE PALABRA CON SU BUSQUEDA, y no puede. El
        # cliente dice "para jugar" y el codigo busca "gamer": esa TRADUCCION es
        # exactamente el trabajo del interprete. Atarla exigiendo una palabra en
        # comun deja afuera el unico caso que importa, asi que una condicion se
        # ancla contra cualquier busqueda del turno que haya traido productos:
        # la condicion se aplica sobre esa busqueda, no sobre otra.
        fichas = _fichas_de(r)
        propio = (_atiende(punto, l) if tipo != "condicion" else bool(fichas))

        if tipo in ("item", "condicion") and propio:
            for p in fichas:
                if p.get("nombre"):
                    fuera.append(str(p["nombre"]))
            # LO QUE EL CODIGO BUSCO tambien ancla, y cubre el caso en que la
            # respuesta correcta no nombra ningun producto: "de Samsung tenemos
            # 38 modelos, de iPhone no trabajamos ninguna linea" contesta el
            # punto sin listar uno solo, y "los discos HDD no llegan a 7000
            # MB/s" lo contesta negando. Los dos estaban marcados sin atender.
            fuera.append(str(ped.get("descripcion") or ""))
            fuera.append(str(ped.get("categoria") or ""))
            if tipo == "condicion":
                for f in (ped.get("filtros") or []):
                    if isinstance(f, dict) and f.get("valor"):
                        fuera.append(str(f["valor"]))
                for c in (r.get("condiciones_aplicadas") or []):
                    fuera.append(str(c))

        if tipo == "destino" and propio:
            ped = l.get("pedido") or {}
            fuera.append(str(ped.get("localidad") or ""))
            if r.get("localidad"):
                fuera.append(str(r["localidad"]))

        if tipo == "item" and l.get("herramienta") == "armar_presupuesto":
            # La cuenta contesta el item nombrandolo en su renglon.
            for d in (r.get("detalle") or []):
                if d.get("nombre"):
                    fuera.append(str(d["nombre"]))

        if tipo == "precio":
            # El precio se contesta con un numero, y el numero puede venir del
            # total de la cuenta o de los precios de lo que se mostro. La ficha
            # ya lo trae escrito -"$28.500"- porque al modelo se le pide que lo
            # copie tal cual; se toman las dos formas.
            if r.get("total_ars"):
                fuera.append(f"{int(r['total_ars']):,}".replace(",", "."))
            # SIN EL SIGNO PESOS: el anclaje se busca con un limite de palabra
            # adelante, y `\b` no existe entre un espacio y un "$" —los dos son
            # no-palabra—, asi que "$28.500" no encontraba "$28.500" ni en su
            # propio texto. El numero pelado si ancla.
            for p in fichas[:8]:
                if p.get("precio"):
                    fuera.append(str(p["precio"]).lstrip("$ "))
                elif p.get("precio_ars"):
                    fuera.append(f"{int(p['precio_ars']):,}".replace(",", "."))

        # ── ATRIBUTO: el anclaje es EL VALOR, no el nombre del campo ────
        # Es el mismo razonamiento que el resto del modulo: el codigo TIENE
        # el dato -la ficha del producto certificado dice `hz: "75Hz"`-, asi
        # que no hace falta adivinar si el modelo uso la palabra "hz". Si el
        # valor esta en el mensaje, el atributo esta contestado, y ningun
        # sinonimo rompe eso. Solo ancla la ficha que el punto NOMBRA.
        if tipo == "atributo" and propio:
            campo = str(punto.get("campo") or "").strip()
            for f in fichas:
                if not (del_punto & set(_palabras(str(f.get("nombre") or "")))):
                    continue
                specs = f.get("specs") if isinstance(f.get("specs"), dict) else {}
                valor = specs.get(campo, f.get(campo))
                if valor not in (None, "", []):
                    fuera.append(str(valor))

        # ── POLITICA: el anclaje son los NUMEROS de la politica ─────────
        # NO el texto de la FAQ entero: son cuarenta palabras, el modelo lo
        # reescribe con las suyas, y `_ancla_en` se conforma con dos palabras
        # presentes —o sea que un parrafo largo anclaria contra casi
        # cualquier mensaje y el punto saldria contestado siempre—. Los
        # numeros con su unidad -"6 meses"- son lo unico que identifica.
        if tipo == "politica" and _herr == "consultar_temas":
            for t in (r.get("temas") or []):
                if str(t.get("tema") or "") != str(punto.get("tema") or ""):
                    continue
                for v in (t.get("valores") or []):
                    if v.get("monto") in (None, ""):
                        continue
                    unidad = str(v.get("unidad") or "").strip()
                    fuera.append(f"{v['monto']} {unidad}".strip())

        # STOCK Y COMPATIBILIDAD NO ANCLAN, y es una decision, no un olvido.
        # Su unica evidencia posible seria el nombre del producto, y nombrar
        # el producto NO contesta ni "¿hay?" ni "¿me sirve?": anclar ahi los
        # daria por contestados apenas el bot mencione el equipo. Se miden
        # contra el texto, que es donde de verdad se ven.

    return [a for a in dict.fromkeys(fuera) if a.strip()]


# ── LA COBERTURA: que punto llego al texto y cual no ─────────────────────────
_RE_TOTAL = re.compile(r"(?im)^\s*total(?:\s+final)?\s*:")
_RE_PREGUNTA = re.compile(r"\?")

# CONTESTAR SI HAY O NO HAY. Estan las dos caras a proposito: "no nos queda"
# contesta el punto igual de bien que "tenemos 7", y un vocabulario que solo
# mire la cara buena marcaria sin atender una respuesta correcta.
_RE_DISPONIBILIDAD = re.compile(
    r"\b(stock|disponible|disponibles|agotad|tenemos|tengo|hay|queda|quedan|"
    r"reponer|repone|entrega inmediata|sin unidades)")

# EL VEREDICTO DE COMPATIBILIDAD, tambien en las dos caras, mas la tercera que
# es la unica honesta cuando la ficha no lo dice: que no se puede confirmar.
_RE_VEREDICTO = re.compile(
    r"\b(compatible|incompatible|sirve|no sirve|funciona|anda|calza|encaja|"
    r"soporta|admite|no puedo confirmar|no figura|sin dato)")


def _dice(palabra, texto: str) -> bool:
    """¿El texto nombra este campo? Sin el minimo de tres letras de
    `_aparece`, porque los campos son cortos —`hz`, `ram`, `w`, `gb`— y ese
    minimo los descarta a todos: `_aparece("hz", ...)` da False SIEMPRE.

    Se ancla al arranque de palabra igual que `_aparece`, asi que `hz` no se
    da por dicho porque el texto diga otra cosa que lo contenga en el medio."""
    w = _raiz(str(palabra or "").strip())
    if not w:
        return False
    return bool(re.search(rf"\b{re.escape(w)}", _n(texto)))


def _cubierto(punto: dict, texto: str) -> bool:
    """UN CRITERIO POR TIPO, y todos miran el texto que lee el cliente.

    No es una sola regla porque los puntos no se contestan igual: un rubro se
    contesta nombrandolo, un destino nombrando la localidad, una duda
    PREGUNTANDO, y el precio con un total. Meter todo en una regla sola es lo
    que hace que una guardia muerda a su vecina.
    """
    tipo = punto.get("tipo")
    termino = punto.get("termino") or ""

    if tipo in ("item", "destino"):
        return _aparece(termino, texto)

    if tipo == "condicion":
        # De la condicion importa la palabra que la hace unica -"chinas",
        # "blanco", "logitech"-, no el relleno con que se dijo. Si alguna de
        # esas palabras esta en el texto, la condicion se nombro.
        vacias = {"que", "las", "los", "una", "unas", "unos", "con", "sin",
                  "menos", "menor", "minima", "minimo", "cantidad", "partes",
                  "posible", "posibles", "componentes", "sean", "sea", "tenga",
                  "tengan", "para", "por", "del", "mas", "muy", "todo", "todos",
                  "quiero", "necesito", "divide", "dividir", "presupuesto"}
        claves = [w for w in _n(termino).split()
                  if len(w) >= 4 and w not in vacias]
        return any(_aparece(w, texto) for w in claves) if claves else True

    if tipo == "duda":
        # Una duda se atiende PREGUNTANDO. Que el texto nombre el objeto de la
        # duda y tenga una pregunta: sin el signo, la nombro al pasar.
        claves = [w for w in _n(termino).split() if len(w) >= 5][:6]
        nombrada = any(_aparece(w, texto) for w in claves) if claves else False
        return bool(nombrada and _RE_PREGUNTA.search(texto or ""))

    if tipo == "pago":
        return all(p in _n(texto) for p in (termino or "").split())

    if tipo == "precio":
        return bool(_RE_TOTAL.search(texto or ""))

    # ── LAS CUATRO INFORMATIVAS (FICHA 02) ──────────────────────────────
    #
    # NINGUNA SE CONTESTA NOMBRANDO EL OBJETO, y por eso ninguna alcanza con
    # `_aparece`: decir "el monitor Samsung" no contesta cuantos Hz tiene, ni
    # si hay stock, ni si sirve para la notebook. **Las tres exigen el objeto
    # NOMBRADO mas la RESPUESTA dicha**, igual que `duda` exige el signo de
    # pregunta. Sin esa segunda mitad, el punto se daria por contestado
    # apenas el bot mencione el producto, que es exactamente la clase de
    # verde falso que el modulo entero viene a evitar.
    #
    # Y OJO CON EL DEFAULT DE ABAJO: `return True`. Una familia nueva que no
    # se escriba aca queda marcada como SIEMPRE contestada y su omision se
    # vuelve invisible en silencio. Por eso las cuatro se escriben, aunque
    # todavia no puedan abrirse en una charla real.

    if tipo == "atributo":
        # El campo se pide aparte y sin el minimo de tres letras: `hz`, `ram`
        # y `w` son campos reales, y `_aparece` descarta las palabras cortas.
        return bool(_aparece(termino, texto) and _dice(punto.get("campo"), texto))

    if tipo == "stock":
        return bool(_aparece(termino, texto)
                    and _RE_DISPONIBILIDAD.search(_n(texto)))

    if tipo == "compatibilidad":
        return bool(_aparece(punto.get("que") or "", texto)
                    and _aparece(punto.get("para") or "", texto)
                    and _RE_VEREDICTO.search(_n(texto)))

    if tipo == "politica":
        return _aparece(termino, texto)

    return True


# ── EL ESTADO TERMINAL DEL PUNTO (FICHA 08, 24-ago-2026) ─────────────────────
#
# HASTA ACA EL MODULO SOLO SABIA DECIR SI O NO: `atendido`. Y "no atendido"
# mete cuatro cosas distintas en la misma bolsa: el bot se lo olvido, el bot
# pregunto cual de los tres era, la fuente no tiene el dato, y el cliente se
# contradijo. Las cuatro se leen igual en el log y **tres de las cuatro no son
# un defecto.** Mientras sean indistinguibles la cobertura no puede ser puerta:
# frenar el turno por "no atendido" frenaria tambien al bot que hizo bien las
# cosas —pregunto, o dijo honestamente que no sabe—, y eso es peor que la
# omision que se quiere evitar.
#
# LOS CUATRO ESTADOS SON LOS DE `DECISIONES.md` #3, y son TERMINALES: el punto
# termino el turno ahi y no espera nada mas de este turno.
#
#   RESUELTO     llego al texto que lee el cliente.
#   AMBIGUO      no se podia cerrar sin elegir por el cliente, y el turno
#                PREGUNTA. Es el unico final que le pide algo al cliente.
#   NO_SE_SABE   no hay con que contestarlo. `DECISIONES.md` #16: jamas frena
#                el cierre, y "no se sabe" nunca se dice como un "no".
#   CONFLICTO    lo que el cliente pidio no cierra y el turno NO lo pregunto.
#
# Y EL QUINTO CASO, QUE A PROPOSITO NO ES UN ESTADO: cadena vacia. El punto
# tenia con que contestarse y no salio dicho. **Eso es la OMISION**, y es lo
# unico que la puerta de la ficha 09 va a frenar. Si la omision fuera un estado
# terminal mas, un turno que se olvida algo estaria tan "terminado" como uno
# que lo contesta, y la puerta no tendria de que agarrarse.
#
# NO SE LE PREGUNTA NADA AL MODELO PARA ESTO. Es la misma regla que los
# anclajes: la evidencia ya esta del lado del codigo —el estado que devolvio
# cada herramienta, y el texto final— asi que pedirsela al modelo seria pagar
# por un dato que ya tenemos, y ademas cambiar el contrato obliga a regrabar
# los casetes con la clave paga.

ESTADOS_TERMINALES = ("RESUELTO", "AMBIGUO", "NO_SE_SABE", "CONFLICTO")

# LO QUE DEVOLVIERON LAS HERRAMIENTAS. No es un vocabulario nuevo: son los
# `estado` que `herramientas.py` ya escribe, y los tres veredictos de identidad.
_EVIDENCIA_AMBIGUA = {"ambiguo", "depende_de_la_variante"}
_EVIDENCIA_SIN_DATO = {"no_encontrado", "no_vendemos", "sin_dato_en_la_fuente",
                       "sin_resultados", "sin_tema", "campo_desconocido",
                       "equipo_desconocido", "no_se_pudo"}

# EL BOT DICIENDO QUE NO SABE. Cortas y literales a proposito: una lista larga
# de sinonimos convierte cualquier negativa en NO_SE_SABE y tapa omisiones.
_RE_NO_SE = re.compile(
    r"(no (lo |la |los |las )?(tengo|tenemos|figura|aparece|dice|se|sabria|"
    r"puedo confirmar|trabajamos|vendemos|manejamos)|"
    r"no (tengo|tenemos|hay) (ese |esa |el |la )?(dato|informacion)|"
    r"sin dato|no me consta|no esta escrito)")

# Los cortes de oracion. El signo de apertura `¿` no corta: abre.
_RE_CORTE = re.compile(r"[.\n;!]+")


def _nombrado(punto: dict, texto: str) -> bool:
    """¿El texto NOMBRA este punto? Es la mitad barata de `_cubierto`, sin la
    respuesta dicha. Sirve para saber de que habla una pregunta o un "no lo
    tengo"."""
    tipo = punto.get("tipo")
    if tipo == "compatibilidad":
        return _aparece(punto.get("que") or "", texto)
    if tipo == "precio":
        # El precio no se NOMBRA, se contesta con un numero. Preguntar "¿te
        # paso el total?" no es contestar el precio ni tampoco preguntarlo.
        return False
    claves = [w for w in _n(punto.get("termino") or "").split()
              if len(w) >= 4 and w not in _VACIAS]
    return any(_aparece(w, texto) for w in claves) if claves else False


def _en_la_misma_oracion(punto: dict, patron, texto: str) -> bool:
    """¿El patron y el punto caen en la MISMA oracion?

    Es la atadura que hace que esto no sea un colador. Sin ella, un "¿Te lo
    despacho hoy?" de cortesia al final del mensaje dejaria en AMBIGUO a todo
    lo que el bot se olvido de contestar, y la omision —que es justo lo que se
    busca— se escaparia escondida detras de una pregunta amable."""
    for pedazo in _RE_CORTE.split(texto or ""):
        if patron.search(_n(pedazo)) and _nombrado(punto, pedazo):
            return True
    return False


def _evidencia(punto: dict, llamadas: list) -> str:
    """Que dice de este punto lo que trajeron las herramientas: `AMBIGUO`,
    `NO_SE_SABE`, o vacio si no dicen nada. No mira el texto del modelo: mira
    lo que el codigo sabe, que es lo unico que no se puede alucinar."""
    tipo = punto.get("tipo")
    fuera = ""
    for l in (llamadas or []):
        r = l.get("resultado")
        if not isinstance(r, dict):
            continue

        if tipo == "politica":
            # EL ESTADO DE UNA POLITICA ES POR TEMA. Una sola llamada trae
            # hasta seis temas, y que cinco esten escritos no dice nada del
            # sexto: `consultar_temas` devuelve `estado` adentro de cada uno.
            if l.get("herramienta") != "consultar_temas":
                continue
            if str(r.get("estado") or "") in _EVIDENCIA_SIN_DATO:
                fuera = "NO_SE_SABE"
            for t in (r.get("temas") or []):
                if not isinstance(t, dict):
                    continue
                if str(t.get("tema") or "") != str(punto.get("tema") or ""):
                    continue
                if str(t.get("estado") or "") in _EVIDENCIA_SIN_DATO:
                    fuera = "NO_SE_SABE"
            continue

        if not _atiende(punto, l):
            continue
        estado = str(r.get("estado") or "")
        veredicto = str(r.get("veredicto") or "")
        # PREGUNTAR LE GANA A NO SABER, y se corta aca mismo. Si una busqueda
        # del punto volvio ambigua, el final correcto es la repregunta aunque
        # otra llamada del mismo turno no haya encontrado nada.
        if estado in _EVIDENCIA_AMBIGUA or veredicto == "ambiguous":
            return "AMBIGUO"
        if estado in _EVIDENCIA_SIN_DATO or veredicto == "not_found":
            fuera = "NO_SE_SABE"
    return fuera


def estado_terminal(punto: dict, texto: str, llamadas: list | None = None,
                    atendido: bool | None = None) -> str:
    """En que termino este punto: uno de `ESTADOS_TERMINALES`, o CADENA VACIA
    si no termino en ninguno —y eso es la omision, que es lo que se frena—.

    `atendido` se pasa cuando ya se calculo, que es lo que hace `cobertura`.
    Es el mismo dato que `_cubierto`, pero calculado tambien con los ANCLAJES,
    o sea con la evidencia que el texto solo no alcanza a ver. Sin el
    parametro, un punto contestado por su producto certificado volveria a
    figurar sin contestar, que es el defecto que los anclajes cerraron."""
    llego = _cubierto(punto, texto or "") if atendido is None else bool(atendido)
    tipo = punto.get("tipo")

    # LA CONTRADICCION DECLARADA ES SU PROPIA FAMILIA, y no puede terminar
    # RESUELTA por el codigo: nace de algo que no cierra sin elegir por el
    # cliente. O el turno la PREGUNTA —y queda AMBIGUA, esperando al cliente—
    # o no la pregunta y el conflicto sigue abierto. `_cubierto` de una `duda`
    # ya exige el signo de pregunta, asi que aca "llego" significa "pregunto".
    if tipo == "duda":
        return "AMBIGUO" if llego else "CONFLICTO"

    if llego:
        return "RESUELTO"

    por_evidencia = _evidencia(punto, llamadas or [])
    if por_evidencia == "AMBIGUO":
        return "AMBIGUO"
    if _en_la_misma_oracion(punto, _RE_PREGUNTA, texto or ""):
        return "AMBIGUO"
    if por_evidencia:
        return por_evidencia
    if _en_la_misma_oracion(punto, _RE_NO_SE, texto or ""):
        return "NO_SE_SABE"
    return ""


def cobertura(declarado: dict, texto: str, trace_id: str = "",
              llamadas: list | None = None,
              memoria: list | None = None) -> dict:
    """El indice del turno: cada punto interpretado, con su estado en la
    respuesta. Devuelve `{puntos, faltan}` y lo deja en el log, que es donde se
    puede leer despues sin adivinar.

    CADA PUNTO SALE CON DOS COSAS, y son distintas: `atendido`, que es si llego
    al texto, y `estado`, que es COMO termino —`ESTADOS_TERMINALES`, o vacio si
    no termino en ninguno—. Un punto puede no estar atendido y haber terminado
    bien igual: el turno pregunto por el, o no habia con que contestarlo. Lo
    que queda con `estado` vacio es la omision, y nada mas que la omision.

    `llamadas` son las herramientas del turno, y con ellas el punto se mide
    contra su EVIDENCIA -el producto que la busqueda devolvio, la localidad que
    el envio cotizo, el total que la calculadora armo- y no solo contra las
    palabras del cliente. Sin ellas se mide como antes: el anclaje es una
    mejora que no puede empeorar el resultado, nunca una dependencia."""
    ps = puntos(declarado)
    if not ps:
        return {"puntos": [], "faltan": []}
    marcados = []
    for p in ps:
        anclas = anclajes(p, llamadas or [], memoria)
        ok = _cubierto(p, texto or "")
        por_ancla = ""
        if not ok:
            por_ancla = next((a for a in anclas if _ancla_en(a, texto or "")), "")
            ok = bool(por_ancla)
        # NINGUN PUNTO SALE SIN LA CASILLA `estado` (FICHA 08). Puede salir
        # con la casilla VACIA —eso es la omision— pero nunca sin ella: un
        # punto sin la clave seria un punto que nadie miro, y la puerta de la
        # ficha 09 no podria distinguirlo de uno que termino bien.
        estado = estado_terminal(p, texto or "", llamadas or [], atendido=ok)
        marcados.append({**p, "atendido": ok, "estado": estado,
                         "anclajes": anclas,
                         **({"por_ancla": por_ancla} if por_ancla else {})})
    faltan = [p for p in marcados if not p["atendido"]]
    sin_estado = [p for p in marcados if not p["estado"]]
    log.info("indice_turno", trace_id=trace_id,
             total=len(marcados), sin_atender=len(faltan),
             sin_estado=len(sin_estado),
             detalle=[f"{p['id']}={'ok' if p['atendido'] else 'FALTA'}"
                      for p in marcados],
             estados=[f"{p['id']}={p['estado'] or 'SIN_ESTADO'}"
                      for p in marcados],
             por_evidencia=[f"{p['id']}<-{p['por_ancla'][:30]}"
                            for p in marcados if p.get("por_ancla")][:5],
             faltan=[p["texto"][:60] for p in faltan][:5])
    return {"puntos": marcados, "faltan": faltan}


def instruccion(faltan: list) -> str:
    """Los puntos sin atender, convertidos en una obligacion CONCRETA para la
    redaccion.

    POR QUE ASI Y NO CON UNA INSTRUCCION GENERICA. Ya esta medido dos veces en
    este repo que "te falto algo, fijate" no mueve al modelo: ante una
    correccion generica pidio cero herramientas 3 de 3 veces. Un punto con su
    texto -"no dijiste que va a Concordia"- es una cosa sola y verificable, que
    es lo unico que se le puede pedir a un redactor.
    """
    if not faltan:
        return ""
    lineas = ["Tu mensaje NO le contesta esto, que el cliente sí pidió. "
              "Agregalo, sin repetir lo que ya escribiste:"]
    for p in faltan:
        lineas.append(f"- {p['texto']}")
    return "\n".join(lineas)
