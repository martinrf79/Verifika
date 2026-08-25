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
    # LA OFERTA NO ANCLA, y no es un olvido. Su evidencia no es un texto que se
    # pueda buscar en el mensaje —que el producto este NOMBRADO no prueba que se
    # haya ofrecido nada, y anclarlo ahi lo daria por ofrecido apenas el bot lo
    # mencione, que es el verde falso que este modulo entero evita—. Su prueba
    # es que una herramienta lo certifico, y eso la pone en
    # `_PRUEBA_POR_CONSTRUCCION`, igual que el precio.
    if tipo == "oferta":
        return []
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
                if valor in (None, "", []):
                    continue
                fuera.append(str(valor))
                # UN PRECIO SE ESCRIBE CON PUNTO Y LA FICHA LO GUARDA PELADO
                # (FICHA 09). `precio_ars: 12000` anclaba contra "12000" y el
                # mensaje dice "$12.000", asi que el punto salia OMITIDO
                # habiendo sido contestado en la misma oracion. Medido en las
                # charlas grabadas: dos de las cuatro omisiones de atributo
                # eran esto, y la puerta las hubiera frenado sin motivo. Se
                # agregan las DOS formas, nunca se reemplaza una por la otra.
                if str(valor).isdigit():
                    fuera.append(f"{int(valor):,}".replace(",", "."))

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


# ── EL PUNTO DE OFERTA: LO QUE EL BOT TIENE QUE PROPONER (FICHA 15) ──────────
#
# EL HUECO, Y ES EL UNICO DEL MODULO QUE NO NACE DEL CLIENTE. Los diez tipos de
# arriba representan lo que el cliente PREGUNTO: se abren de lo declarado y se
# cierran cuando la respuesta llego al texto. Nada representa lo que el bot
# tiene que PROPONER. Por eso un turno puede contestar la ficha tecnica perfecta
# y no ofrecer cargar el producto: cumplio la cobertura entera y no habia nada
# que lo obligara a avanzar. Medido sobre las charlas grabadas: 26 turnos rojos
# en avance, TODOS con el carrito en cero de punta a punta, y tres charlas
# enteras sin un solo pedido.
#
# LO ABRE EL CODIGO, NUNCA EL MODELO, y es la regla 0 de siempre. El punto nace
# de dos hechos que el codigo tiene: un producto CERTIFICADO -el que devolvio
# una herramienta- y un estado -que el pedido todavia no lo tenga-. Si lo
# abriera el modelo, el turno que no quiere vender se lo saltea, que es
# exactamente el turno que esto viene a cazar.
#
# Y NO PUEDE VOLVERSE INSISTENCIA, que es la unica forma en que este punto
# empeora el bot. Los frenos son tres y los tres son del codigo:
#
#   1. LA AMBIGUEDAD MANDA. Si alguna herramienta del turno volvio ambigua, el
#      turno esta OBLIGADO a repreguntar, y dos preguntas en el mismo mensaje es
#      pedirle al cliente que administre una agenda. La oferta ni se abre: cede
#      y queda para el turno siguiente.
#   2. LA OFERTA NO ES UNA PREGUNTA. "Te lo cargo al pedido y te paso el total"
#      propone sin preguntar nada. Por eso el detector NO mira el signo de
#      pregunta, y por eso la instruccion de redaccion pide la frase, no el
#      interrogatorio.
#   3. NO CORRESPONDE, con motivo tipado y cerrado.
#
# EL TERCERO ES EL QUE MAS IMPORTA: "el cliente ya dijo que no lo quiere". La
# memoria negativa vive en `descartados` —el campo del documento de la
# conversacion, que guarda NOMBRES porque el cliente descarta "los auriculares",
# no un id— y llega hasta aca porque `hub_venta` se la pasa a la cobertura. Sin
# ella el bot vuelve a ofrecer lo que el cliente rechazo, que es la insistencia
# en su forma mas cara: la unica que el cliente lee como que no lo escucharon.
#
# UN MODELO CONCRETO RECHAZADO NO TAPA A SU FAMILIA. Si lo descartado trae un
# numero de modelo —"Mouse Logitech M170"— se exige ESE numero para callar la
# oferta; sin numero —"los auriculares"— alcanza con la identidad corta que ya
# usa el resto del modulo. Al reves, rechazar el M170 apagaria la oferta de
# cualquier otro mouse Logitech, y dejar de ofrecer alternativas despues de un
# "ese no" es perder la venta justo donde recien empieza.

# LAS QUE CERTIFICAN UN PRODUCTO PARA OFRECERLO. `armar_presupuesto` no esta a
# proposito: lo que pasa por ahi YA es el pedido, asi que no hay nada que
# ofrecer. `cotizar_envio` y `consultar_temas` no traen producto.
_CERTIFICAN_PRODUCTO = ("buscar_productos", "ficha_producto",
                        "comparar_productos")

# LOS TRES MOTIVOS, Y NINGUNO MAS. Cerrado a proposito: un motivo libre
# convierte `NO_CORRESPONDE` en un cajon donde cae todo lo que no se ofrecio, y
# el punto deja de medir.
MOTIVOS_NO_CORRESPONDE = ("rechazado", "ya_en_el_pedido", "cerrando")

# PROPONER EL PASO SIGUIENTE. Formas literales y contadas, igual que el resto
# del modulo: una lista larga de sinonimos convierte cualquier cortesia en una
# oferta y el numero deja de decir nada. Se escriben las formas, no la raiz
# pelada, porque `carg` tambien esta en "cargador" y "sum" en "sumado".
_RE_ACCION = re.compile(
    r"\b(cargo|cargar|cargarlo|cargarla|cargamos|cargas|"
    r"sumo|sumar|sumarlo|sumarla|sumamos|sumas|"
    r"agrego|agregar|agregarlo|agregarla|agregamos|agregas|"
    r"reservo|reservar|reservarlo|reservarla|reservamos|reservas|reserva|"
    r"aparto|apartar|apartarlo|apartamos|"
    r"cotizo|cotizar|cotizarlo|cotizamos|cotizacion|"
    r"preparo|preparar|prepararlo|preparamos|"
    r"avanzo|avanzar|avanzamos|avanzas|"
    r"coordino|coordinar|coordinamos)\b")

# SOBRE QUE CAE LA ACCION. Sin esto "coordinamos por mail" o "avanzamos con la
# consulta" contarian como oferta: la accion tiene que caer sobre el producto, y
# el modelo lo nombra o lo pronominaliza —"te lo cargo"—.
_RE_PRONOMBRE = re.compile(r"\b(lo|la|los|las|te lo|te la)\b")

# EL TURNO QUE YA ESTA CERRANDO. Pedirle el nombre, la direccion o la forma de
# pago ES el paso siguiente: sumarle una oferta encima seria el interrogatorio
# que la ficha prohibe.
_RE_CERRANDO = re.compile(
    r"(a nombre de quien|tu nombre|como te llamas|a que direccion|"
    r"a que domicilio|forma de pago|formas de pago|medio de pago|"
    r"como lo abonas|como abonas|link de pago|pedido confirmado)")


def _oraciones(texto: str) -> list:
    """Las oraciones del mensaje. ACA EL SIGNO DE PREGUNTA CORTA, al reves que
    `_RE_CORTE`: si no cortara, la accion de una oracion le daria el verde a la
    siguiente y "¿Te lo reservo? ¿A que direccion?" seria una sola cosa."""
    return [p for p in re.split(r"[.\n;!?]+", texto or "") if p.strip()]


def _productos_certificados(llamadas: list) -> list:
    """Los productos que una herramienta trajo en ESTE turno, con su id y su
    nombre, sin repetir y en el orden en que llegaron."""
    fuera: list = []
    for l in (llamadas or []):
        if l.get("herramienta") not in _CERTIFICAN_PRODUCTO:
            continue
        for f in _fichas_de(l.get("resultado") or {}):
            nombre = str(f.get("nombre") or "").strip()
            if not nombre:
                continue
            pid = str(f.get("id") or "").upper()
            if not any(p["nombre"] == nombre for p in fuera):
                fuera.append({"id": pid, "nombre": nombre})
    return fuera


def _ya_en_el_pedido(llamadas: list, memoria: list | None) -> set:
    """Los productos que el pedido YA tiene, por id y por nombre normalizado.

    SON DOS FUENTES Y HACEN FALTA LAS DOS. La cuenta de ESTE turno —lo que
    `armar_presupuesto` acaba de armar— es la que cubre el caso en que el
    cliente pide cargarlo y el turno lo carga: el carrito de entrada todavia no
    lo tenia, y ofrecerselo de nuevo seria preguntarle si quiere lo que acaba de
    pedir. Y el carrito de la charla, que llega adentro de `memoria`.

    EL CARRITO SE RECONOCE POR `cantidad`, y no es una adivinanza: `memoria` es
    el carrito vigente mas lo ya mostrado, y un item del carrito es el unico que
    lleva cuantas unidades son. Un producto del catalogo nunca trae ese campo.
    Si algun dia lo trajera, la oferta se abriria de menos, que es el lado por
    el que este punto tiene que fallar: de mas es insistencia."""
    fuera: set = set()

    def _anotar(pid, nombre):
        if pid:
            fuera.add(str(pid).upper())
        if nombre:
            fuera.add(_n(nombre))

    for l in (llamadas or []):
        if l.get("herramienta") != "armar_presupuesto":
            continue
        for d in ((l.get("resultado") or {}).get("detalle") or []):
            if isinstance(d, dict):
                _anotar(d.get("id"), d.get("nombre"))
    for p in (memoria or []):
        if isinstance(p, dict) and p.get("cantidad"):
            _anotar(p.get("id"), p.get("nombre"))
    return fuera


def _rechazado(nombre: str, descartados: list | None) -> bool:
    """¿El cliente ya dijo que NO a este producto?

    `descartados` son NOMBRES, no ids: el cliente descarta "los auriculares", y
    asi los guarda `hub_venta`. Por eso se compara por identidad corta y no por
    igualdad, que no daria nunca.

    EL MODELO CON NUMERO SE EXIGE ENTERO, y ahi esta toda la diferencia entre
    respetar un "no" y perder la venta. "Mouse Logitech M170" y "Mouse Logitech
    G203" comparten dos palabras: con la identidad corta sola, rechazar el M170
    apagaria la oferta de cualquier mouse Logitech, y despues de un "ese no" es
    justo cuando hay que ofrecer la alternativa."""
    for d in (descartados or []):
        d = str(d or "").strip()
        if not d:
            continue
        modelos = [w for w in _palabras(d) if any(c.isdigit() for c in w)]
        if modelos:
            if all(_aparece(m, nombre) for m in modelos):
                return True
            continue
        if _ancla_en(d, nombre):
            return True
    return False


def _hay_ambiguedad(llamadas: list) -> bool:
    """¿El turno esta obligado a repreguntar? Es el mismo vocabulario que ya usa
    `_evidencia`: los estados que `herramientas.py` escribe y el veredicto de
    identidad. Si alguno dice ambiguo, la oferta cede."""
    for l in (llamadas or []):
        r = l.get("resultado")
        if not isinstance(r, dict):
            continue
        if str(r.get("estado") or "") in _EVIDENCIA_AMBIGUA:
            return True
        if str(r.get("veredicto") or "") == "ambiguous":
            return True
    return False


def punto_de_oferta(llamadas: list, memoria: list | None = None,
                    texto: str = "",
                    descartados: list | None = None) -> dict | None:
    """EL PUNTO SINTETICO `oferta`, o None si en este turno no hay nada que
    ofrecer. Lo abre el codigo con dos hechos suyos y ninguna opinion del
    modelo: hay un producto certificado y el pedido no lo tiene.

    Sale con `candidatos` —los productos que se pueden ofrecer— y con
    `no_corresponde` cuando el turno tiene motivo para no ofrecer nada."""
    traidos = _productos_certificados(llamadas)
    if not traidos:
        return None
    # LA AMBIGUEDAD MANDA Y NO DEJA RASTRO: el punto no se abre. Marcarlo
    # `NO_CORRESPONDE` seria decir que se decidio no ofrecer, y lo que pasa es
    # otra cosa —la oferta queda para el turno siguiente—.
    if _hay_ambiguedad(llamadas):
        return None
    en_pedido = _ya_en_el_pedido(llamadas, memoria)
    fuera_del_pedido = [p for p in traidos
                        if p["id"] not in en_pedido
                        and _n(p["nombre"]) not in en_pedido]
    libres = [p for p in fuera_del_pedido
              if not _rechazado(p["nombre"], descartados)]
    # LOS TRES MOTIVOS, EN ESTE ORDEN Y NO EN OTRO. Primero lo que el pedido ya
    # tiene, que es el mas fuerte —ofrecerlo seria preguntarle si quiere lo que
    # acaba de pedir—; despues el "no" del cliente, que manda sobre cualquier
    # cosa que el bot quiera proponer; y al final el cierre, que es el unico que
    # depende del texto de este turno.
    motivo = ""
    if not fuera_del_pedido:
        motivo, libres = "ya_en_el_pedido", traidos
    elif not libres:
        motivo, libres = "rechazado", fuera_del_pedido
    elif _RE_CERRANDO.search(_n(texto or "")):
        motivo = "cerrando"
    nombres = [p["nombre"] for p in libres][:8]
    return {"id": "oferta:1", "tipo": "oferta", "termino": nombres[0],
            "texto": f"proponerle el paso siguiente sobre {nombres[0]}",
            "candidatos": nombres,
            **({"no_corresponde": motivo} if motivo else {})}


def _ofrecio_el_paso(punto: dict, texto: str) -> bool:
    """¿El texto propone el paso siguiente sobre ESE producto?

    LAS DOS MITADES EN LA MISMA ORACION, y esa atadura es todo lo que separa
    esto de un colador. La accion sola deja pasar "coordinamos por mail"; el
    producto solo deja pasar la ficha tecnica que no ofrece nada. Y no se pide
    signo de pregunta a proposito: "Te lo cargo al pedido y te paso el total"
    ofrece sin preguntar, que es justo la forma que no gasta la unica
    repregunta del turno."""
    nombres = punto.get("candidatos") or []
    for pedazo in _oraciones(texto):
        if not _RE_ACCION.search(_n(pedazo)):
            continue
        if _RE_PRONOMBRE.search(_n(pedazo)):
            return True
        if any(_ancla_en(nombre, pedazo) for nombre in nombres):
            return True
    return False


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

    # ── LA OFERTA (FICHA 15) ────────────────────────────────────────────
    # NO SE CONTESTA: SE PROPONE. Es el unico punto que no mira si algo del
    # cliente llego al texto, sino si el bot puso sobre la mesa el paso
    # siguiente. Con motivo para no ofrecer, `atendido` es False y el punto
    # termina igual: por `NO_CORRESPONDE`, no por el texto.
    if tipo == "oferta":
        if punto.get("no_corresponde"):
            return False
        return _ofrecio_el_paso(punto, texto or "")

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

ESTADOS_TERMINALES = ("RESUELTO", "AMBIGUO", "NO_SE_SABE", "CONFLICTO",
                      # LOS DOS DE LA OFERTA (FICHA 15). Son suyos y de ningun
                      # otro tipo: un punto del cliente no se "ofrece", y la
                      # oferta no se "resuelve" ni se "sabe".
                      "OFRECIDO", "NO_CORRESPONDE")

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

    # LA OFERTA TERMINA EN LOS SUYOS Y EN NINGUN OTRO (FICHA 15). No puede
    # terminar `NO_SE_SABE` —el producto lo trajo una herramienta, o sea que se
    # sabe— ni `AMBIGUO` —con ambigüedad el punto no se abre—. O el turno
    # propuso el paso siguiente, o tenia motivo para no proponerlo, o se fue sin
    # ofrecer: eso ultimo es la casilla vacia, y es lo que la puerta frena.
    if tipo == "oferta":
        if llego:
            return "OFRECIDO"
        return "NO_CORRESPONDE" if punto.get("no_corresponde") else ""

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
              memoria: list | None = None,
              descartados: list | None = None) -> dict:
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
    # EL PUNTO DE OFERTA VA CON LOS DEL CLIENTE (FICHA 15) Y SE ABRE ACA, que es
    # el unico lugar del modulo donde estan juntos lo que trajeron las
    # herramientas y lo que el pedido ya tiene. `puntos()` sigue siendo lo
    # declarado y nada mas: la oferta no la declara nadie, la abre el codigo.
    _oferta = punto_de_oferta(llamadas or [], memoria, texto or "",
                              descartados)
    if _oferta:
        ps = ps + [_oferta]
    if not ps:
        return {"puntos": [], "faltan": []}
    marcados = []
    for p in ps:
        anclas = anclajes(p, llamadas or [], memoria)
        ok = _cubierto(p, texto or "")
        por_ancla = ""
        # LA OFERTA NO PASA POR EL ANCLAJE: se contesta proponiendo, y el
        # anclaje mira si algo esta DICHO. Sin esta guarda el punto se daria por
        # ofrecido con solo nombrar el producto.
        if not ok and p.get("tipo") != "oferta":
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


# ── LA PUERTA: LA COBERTURA DEJA DE SER UN LOG (FICHA 09, 24-ago-2026) ───────
#
# HASTA ACA EL MODULO MIRABA Y ESCRIBIA EN EL LOG. La ficha 08 le puso a cada
# punto su estado terminal; el que queda con la casilla VACIA es la omision, y
# esta funcion es la que decide que hacer con ella. Es el contrato de
# `DECISIONES.md` #3 escrito como codigo: el turno no sale como esta si un
# punto quedo sin estado.
#
# LA PUERTA SOLO FRENA LO QUE PUEDE PROBAR, y esa es toda la idea. Un punto
# frena cuando pasan LAS DOS COSAS:
#
#   1. quedo SIN ESTADO -no se dijo, no se pregunto, y no se dijo que no se
#      sabia-, y
#   2. el codigo TENIA con que contestarlo: hay anclaje, o sea evidencia
#      certificada de este turno o de la memoria.
#
# Sin la segunda mitad la puerta seria un adivino. Un punto sin evidencia no
# demuestra una omision: demuestra que el sistema no lo busco, que es otra
# falla y se arregla en otro lado. Frenarlo seria frenar al turno por algo que
# el codigo nunca supo, y eso vende menos que la omision que se quiere evitar.
#
# POR QUE LA POLITICA NO FRENA, y esta medido. Un tema de la FAQ se contesta
# con PROSA y el anclaje de una politica son sus numeros -"6 meses", "3000
# ars"-. En las charlas grabadas el turno contesta la politica del envio con el
# numero REAL de la cotizacion -$7.000- en vez del numero generico de la FAQ, y
# el punto salia sin estado habiendo sido contestado bien. Y el nombre del tema
# es vocabulario de nuestro archivero -`desconfianza_online`,
# `concepto_imposible`-: no aparece jamas en un mensaje escrito para un
# cliente. De las 38 omisiones medidas, 20 son de politica y casi todas son
# esto. Una politica se sirve entera y el modelo la escribe con sus palabras:
# no hay forma MECANICA de probar que se omitio, y la regla tecnica 4 dice que
# lo que no se puede mapear mecanicamente se descarta.
#
# STOCK Y COMPATIBILIDAD TAMPOCO FRENAN, por la razon de siempre: no anclan a
# proposito -el nombre del producto no contesta "¿hay?" ni "¿me sirve?"- asi
# que nunca tienen con que probar la omision.
#
# LO QUE LA PUERTA NO HACE, Y NO ES UN OLVIDO: no le niega el mensaje al
# cliente. `DECISIONES.md` #14 -un punto sin resolver bloquea su renglon, NUNCA
# el turno- y #16 -un punto en NO SE SABE jamas frena el cierre-. Frenar la
# salida entera por un destino sin decir seria cambiar una omision por un
# silencio, que es peor: un detalle nunca tira una venta. Lo que la puerta hace
# es RECHAZAR EL TEXTO COMO ESTA: quien la consume repone el renglon que falta
# con material sellado, y lo que no se puede reponer sale marcado en el turno
# en vez de perderse.

# LOS TIPOS QUE PUEDEN FRENAR: los que el codigo certifica. Un `item` se
# certifica con el producto que devolvio la busqueda, un `destino` con la
# localidad que cotizo el envio, un `atributo` con el valor de la ficha, un
# `precio` con el total de la calculadora, un `pago` con el reparto declarado.
# Los tres que faltan -politica, stock, compatibilidad- no tienen prueba
# mecanica, y arriba esta escrito por que.
TIPOS_QUE_FRENAN = ("item", "condicion", "destino", "atributo", "precio", "pago")

# LA OFERTA NO FRENA, Y ES LO CONTRARIO DE UN OLVIDO (FICHA 15, corregida el
# 25-ago). Los seis de arriba frenan porque el texto se puede ARREGLAR: falta un
# dato que el codigo tiene y la guardia lo repone con material sellado. Una
# oferta que falta no se puede reponer —es prosa de venta, y ninguna guardia de
# este repo escribe prosa—, asi que "no puede salir" no abriria ninguna puerta:
# dejaria el turno marcado como rechazado sin nada que hacer con el.
#
# Y EL DAÑO SERIA AL REVES DEL QUE SE BUSCA. Un turno mudo pierde la venta
# ENTERA; retenerlo o tratarlo como texto rechazado la pierde igual y ademas
# deja al cliente sin respuesta. `DECISIONES.md` #14 y #16 ya lo dicen para los
# puntos del cliente y vale doble para este: un detalle nunca tira una venta, y
# una oferta que no se hizo es exactamente un detalle comparado con el silencio.
#
# EL TURNO SALE Y QUEDA REGISTRADO, que es lo unico que hace falta: sale en
# `sin_ofrecer`, lo loguea la puerta de salida y lo cuenta la vara de venta. Un
# numero a la vista es lo que permite perseguirlo; un turno frenado, no.
TIPOS_SIN_OFERTA = ("oferta",)

# EL PRECIO ES LA EXCEPCION, Y LA FUERZA UN CASO REAL. Su evidencia no es un
# texto que se pueda buscar en el mensaje: es la CUENTA, y la cuenta la arma la
# calculadora con ids certificados. El caso: el cliente pregunta cuanto sale
# llevar dos unidades de la notebook que venia mirando, el turno no llama a
# ninguna herramienta porque el producto ya esta certificado en el carrito, y
# el punto no tiene un solo anclaje. Exigirle uno seria dejar salir justo el
# turno que nacio para frenar. Se pregunta de la unica forma honesta: se le
# pide la cuenta a la calculadora, y si no la puede armar no se pega nada.
_PRUEBA_POR_CONSTRUCCION = ("precio",)


def puede_salir(puntos: list) -> dict:
    """¿El turno puede salir con este texto? El veredicto de la cobertura,
    convertido en puerta.

    Devuelve `{puede, omitidos, sin_prueba, sin_ofrecer, motivo}`:

      puede       False si algun punto quedo sin estado TENIENDO con que
                  contestarse. Es lo unico que frena.
      omitidos    esos puntos, con su id y su texto. Son los que hay que
                  reponer antes de mandar.
      sin_prueba  los que quedaron sin estado y sin evidencia. No frenan, pero
                  se devuelven para que el turno los deje anotados: sin esto
                  desaparecerian, y un numero que desaparece es un numero que
                  nadie arregla.
      sin_ofrecer el turno tenia un producto para proponer y no propuso nada.
                  NUNCA frena: un turno mudo pierde la venta entera, y ninguna
                  guardia puede reponer una oferta porque es prosa. Sale en su
                  propia lista para que quede contado.
      motivo      una linea legible para el log.

    Es PURA: recibe los puntos que ya marco `cobertura` y no vuelve a mirar el
    texto ni las herramientas. Se la puede correr sobre una charla vieja."""
    marcados = [p for p in (puntos or []) if isinstance(p, dict)]
    sin_estado = [p for p in marcados if not (p.get("estado") or "")]
    omitidos = [p for p in sin_estado
                if p.get("tipo") in TIPOS_QUE_FRENAN
                and (p.get("anclajes")
                     or p.get("tipo") in _PRUEBA_POR_CONSTRUCCION)]
    # LA OFERTA SALE ANTES DE MIRAR SI FRENA, porque no frena nunca. Va en su
    # propia lista y no en `sin_prueba`: prueba tiene de sobra —una herramienta
    # certifico el producto—, lo que no tiene es arreglo automatico.
    sin_ofrecer = [p for p in sin_estado
                   if p.get("tipo") in TIPOS_SIN_OFERTA]
    # Por IDENTIDAD y no por igualdad: dos puntos distintos pueden tener el
    # mismo contenido, y `in` sobre diccionarios compara valores.
    _contados = {id(p) for p in omitidos} | {id(p) for p in sin_ofrecer}
    sin_prueba = [p for p in sin_estado if id(p) not in _contados]
    motivo = ""
    if omitidos:
        motivo = "sin decir, teniendo el dato: " + ", ".join(
            f"{p.get('id')}={p.get('texto')}" for p in omitidos[:4])
    return {"puede": not omitidos, "omitidos": omitidos,
            "sin_prueba": sin_prueba, "sin_ofrecer": sin_ofrecer,
            "motivo": motivo}


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
    # LA OFERTA SE PIDE APARTE Y NO COMO UN PUNTO QUE FALTA (FICHA 15). El
    # encabezado de arriba dice "esto el cliente sí lo pidió", y la oferta es lo
    # contrario: es lo que el cliente NO pidió y el bot tiene que proponer.
    # Metida en esa lista, el modelo la leeria como un reclamo del cliente y
    # contestaria en vez de ofrecer.
    del_cliente = [p for p in faltan if p.get("tipo") != "oferta"]
    oferta = next((p for p in faltan if p.get("tipo") == "oferta"
                   and not p.get("no_corresponde")), None)
    lineas = []
    if del_cliente:
        lineas.append("Tu mensaje NO le contesta esto, que el cliente sí pidió. "
                      "Agregalo, sin repetir lo que ya escribiste:")
        for p in del_cliente:
            lineas.append(f"- {p['texto']}")
    if oferta:
        # LA UNICA LINEA DE LA MITAD 2, y es una atadura, no una reescritura del
        # prompt: `_INSTRUCCION_DOS` no se toca. Va SOLO en los turnos que
        # tienen algo concreto que ofrecer, asi que en el resto el prompt pesa
        # exactamente lo que pesaba.
        #
        # "SIN PREGUNTAR DE NUEVO" NO ES CORTESIA: es el candado contra la
        # insistencia. Dos preguntas en el mismo mensaje es pedirle al cliente
        # que administre una agenda, y `una_sola_repregunta` es el numero que
        # esta ficha no puede bajar.
        if lineas:
            lineas.append("")
        lineas.append(
            f"Ya le mostraste {oferta['termino']} y todavía no está en el "
            "pedido: cerrá proponiendo el paso siguiente concreto sobre eso "
            "—cargarlo, cotizarlo o reservarlo—, en una sola frase y sin "
            "sumarle otra pregunta al cliente.")
    return "\n".join(lineas)
