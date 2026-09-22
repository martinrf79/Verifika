"""EL TURNO, EN UNA SOLA LLAMADA. Desde el 11-sep-2026 este es el camino vivo.

QUE REEMPLAZA. A `turno.py` y a las ocho etapas: moldes, decisor con
herramientas, resolver, mesa, redactor, obligaciones. Todo eso esta apagado en
`archivo/apagado_11sep/`. No conviven: hay un solo camino.

EL FLUJO, entero:

  1. FUENTE   el codigo pone lo que NINGUNA busqueda puede contestar: el
              inventario -dos renglones sobre el catalogo entero- y el ENVIO ya
              cotizado, que sale del codigo postal y no se razona.
  2. MODELO   ve la voz de la casa, la memoria, el tablero y el motor. Los
              VEINTE TIPOS los ve recien en la vuelta de contestar.
              BUSCA EL, productos Y politicas de la casa por la MISMA puerta:
              escribe la consulta, el codigo la ejecuta y certifica, y con lo
              que volvio contesta. El precio lo copia de la ficha que trajo; el
              envio y la suma van como hueco, porque no los sabe.
  3. NUMEROS  el codigo escribe el envio que ya cotizo y el total, y tira
              abajo la respuesta si quedo una sola cifra que la fuente no
              tiene. La procedencia se mide contra TODO lo que viajo.
  4. CIERRE   si el cliente decidio comprar, se toma el pedido y se manda el
              link de pago. `leads` y `cierre` no se tocaron.
  5. MEMORIA  se guarda la charla, igual que siempre.

POR QUE UNA SOLA LLAMADA. Tres llamadas por turno daban entre 4,4 y 5,8
segundos medidos y se comian la cuota diaria de a tres. Una sola con los veinte
moldes adentro pesa menos que la primera de las tres que habia.

DE DONDE SACA EL MODELO LA RESPUESTA, que es la pregunta que define todo esto:
de las fichas Y las politicas que EL pidio con `motor.buscar` y que el codigo
certifico, y de ningun otro lado. Por eso la ficha viaja con el precio ya
escrito, y por eso la guarda de procedencia mira exactamente esas fichas.

POR QUE EL MODELO BUSCA Y NO EL CODIGO. El codigo no razona, asi que no puede
traducir "un rectangulo con teclas" a `teclado` ni "acorde a la crisis" a un
orden por precio. Cuando lo intento -`resolver_inclusion` y sus hermanas,
cortando raices de cuatro letras- dio lo que tenia que dar: "que no sea de
marca china" resolvia a `origen no_contiene marc`, la raiz de "marca", que esta
en los 880 origenes. Cero productos, y el bot diciendo que no hay nada.

LO QUE EL MODELO NO PUEDE HACER, y lo garantiza el codigo, no el prompt:
escribir un numero que la fuente no tenga -precio, plazo o spec, da igual-,
calcular un envio o una suma, afirmar que existe un producto que no esta en las
fichas, e inventar una politica de la casa.
"""
import json
import time

from app.config import get_settings
from app.core import bocas as BC
from app.core import numeros as N
from app.core import tipos as TP
from app.core.llm_reintento import llamar_con_reintento
from app.logger import get_logger
from app.storage.firestore_client import get_conversation, save_conversation

log = get_logger(__name__)
settings = get_settings()


# ── EL PROMPT ───────────────────────────────────────────────────────────────
#
# Corto a proposito. Cada regla de aca tiene ademas su candado en codigo: el
# prompt pide, el codigo obliga. Los veinte moldes viven aparte, en
# `_COMO_SUENA`, porque viajan solo en la vuelta de contestar.
#
# LA PLATA SE DICE UNA VEZ SOLA, y esa forma es el arreglo del 15-sep. La
# version anterior enumeraba casos -el precio es el UNICO numero que podes
# escribir, y seis renglones despues el total de la cuenta se copia igual que
# un precio- y despues amenazaba con tirar la respuesta abajo si la cifra no
# salia de una ficha o de los dos huecos. El total no es ninguna de esas dos
# cosas: el prompt le decia al modelo que escribir el total mataba la
# respuesta. Una enumeracion de casos se desincroniza sola cada vez que se
# enchufa una boca nueva; una regla de procedencia, no.
#
# EL PARRAFO DE `busco` NO SE MUDA AL ESQUEMA, y hay medicion: el 12-sep, con
# `busco` viviendo SOLO en la descripcion de la herramienta, 0 de 9 consultas
# lo declararon y la ambiguedad no se podia disparar nunca. Vara en
# `tests/test_turno_nuevo.py`. ESTA NOTA ES PARA EL QUE EDITA, y hasta el
# 16-sep vivia ADENTRO del prompt: el modelo la leia en cada vuelta —tres por
# turno— con una fecha, un numero de medicion y la ruta de un test adentro.
# Nada de eso lo ayuda a contestar. Lo que le habla al modelo va en el string;
# lo que nos habla a nosotros, aca.
_MOLDE_REGLAS = """Sos el vendedor. Contestas UN mensaje de WhatsApp.

Un campo que la fuente no tiene se dice, y NO cancela el resto: precios, envio
y cuenta salen igual con las fichas que volvieron. Si el mensaje mezcla varias
preguntas, se contestan TODAS y el tipo es `multipregunta`.

__LA_PLATA__

TODA consulta lleva `busco`, y no es opcional: `uno` si el cliente nombro un
producto puntual -"el K120", "esa notebook", "el teclado que me mostraste"-, y
`varios` si pidio opciones, un rubro o un extremo. Con `uno`, si hay dos que le
pegan igual te aviso y ahi le preguntas cual: elegir por el es inventar.

Traduci vos lo que el cliente dijo. "Un rectangulo con teclas" es la categoria
`teclado`. "Algo acorde a la crisis" es ordenar por precio de menor a mayor.
Eso es tu trabajo, no el del codigo.

SOLO EXISTE LO QUE LA BUSQUEDA DEVOLVIO. Si un producto no aparecio, no lo
vendemos y se lo decis. Si un dato no esta en la ficha, no lo tenemos y se lo
decis.

Y ADEMAS DE NO MENTIR, VENDES. Son cinco y salieron de charlas reales:
1. No repitas lo que ya dijiste en tu mensaje anterior.
2. Nombra el destino con la palabra del cliente: "Posadas", no "misiones".
3. No vuelvas a ofrecer lo que el cliente ya rechazo.
4. UNA sola pregunta por mensaje.
5. Con el precio ya mostrado y el cliente decidido, ofrece el cierre.

Contestas con dos cosas: el `tipo` de pregunta que es, y el `texto` que lee el
cliente. El formato lo obliga el codigo, no vos.
"""


# EL PROMPT ARMADO. El unico hueco es la plata, y sale de `bocas`: la lista de
# numeros que el modelo puede copiar es la lista de bocas que devuelven uno, no
# una enumeracion escrita a mano. El 14-sep se enchufo la cuenta y el prompt
# siguio diciendo que el precio era el unico numero de plata, o sea que le
# decia al modelo que escribir el total mataba la respuesta. Derivada, la boca
# nueva entra al prompt el mismo dia que entra al motor.
#
# SE ARMA CON `replace` Y NO CON `format` a proposito: el prompt tiene llaves
# dobles de verdad -{{envio}} y {{total}} son los huecos que llena el codigo- y
# `format` se las comeria.
_REGLAS = _MOLDE_REGLAS.replace("__LA_PLATA__", BC.para_la_plata())


# ── COMO SUENA LA RESPUESTA — los veinte moldes ─────────────────────────────
#
# VIAJA SOLO EN LA VUELTA DE CONTESTAR (15-sep-2026, decision de Martin en la
# FICHA 54). Pesan 1.036 tokens y se pagaban en las tres vueltas; en la vuelta
# de buscar no se decide como suena la respuesta, asi que ahi no pertenecen.
#
# Y NO ES SOLO COSTO: INDUCEN. El modelo elige un tipo y despues declara los
# campos que ese tipo le sugiere, en vez de mirar que boca contesta lo que le
# preguntaron. Al pedido con reparto 70/30 le puso `identidad_ambigua`.
#
# LA SIMETRIA YA EXISTIA DEL OTRO LADO: el tablero -que es el indice de lo que
# se puede pedir- desaparece en la vuelta de contestar, porque ahi ya no hay
# nada que pedir. Los moldes son lo mismo al reves.
#
# EL ESQUEMA DE RESPUESTA SE QUEDA EN LAS TRES, y es otra cosa: el esquema
# OBLIGA el formato y los moldes enseñan la prosa. Sin esquema el modelo
# contestaba en markdown y el tipo salia vacio -medido el 12-sep-.
_COMO_SUENA = """COMO SUENA LA RESPUESTA. Abajo tenes VEINTE TIPOS de pregunta
con el molde de cada uno. Eligi el que corresponde al mensaje del cliente y
contestale con ESE molde, escrito con tus palabras, corto y natural. Si el
mensaje mezcla dos tipos, contesta los dos en el mismo mensaje; si mezcla mas
de uno, el tipo es `multipregunta`.

Lo que en el molde va entre signos de menor y mayor -<producto>, <stock>,
<opciones>- NO se copia: ahi va la palabra real, sacada de la ficha que tenes
abajo. Las llaves dobles son las tres unicas que el codigo llena.

LOS VEINTE TIPOS:
"""


# COMO SE LEE LO QUE VOLVIO. Viaja PEGADO al retorno y no en las reglas, y ese
# es el punto: en la primera vuelta no hay retorno que leer, asi que en el
# prompt se pagaba una vez de gusto en cada turno. Naciendo con el retorno, no
# hay turno que lo pague sin usarlo.
#
# Y YA NO SE ESCRIBE ACA (16-sep-2026, FICHA 55 §4.2). Los renglones salen de
# `bocas`, que es la MISMA lista de la que sale el indice del tablero y la
# regla de la plata de abajo. Eran dos textos sobre lo mismo con dos
# redacciones distintas, y ya se pago dos veces: el encabezado tardo tres dias
# en enterarse de que habia cinco bocas, y el envio cotizado no salia en la
# respuesta porque que hacer con la tarifa estaba escrito en el tablero, que
# no viaja en la vuelta de contestar.
_COMO_SE_LEE = BC.para_el_retorno()


def _esquema_respuesta() -> dict:
    """EL FORMATO NO SE PIDE: SE OBLIGA (12-sep-2026).

    Hasta hoy el JSON se pedia por prompt y nada mas, asi que el modelo
    contestaba en prosa cuando se le daba la gana y `_parsear` caia al texto
    pelado con el tipo VACIO. Medido contra el proveedor vivo: la MISMA
    pregunta, con esquema devuelve `{"tipo": "saludo", "texto": "hola"}` y sin
    esquema devuelve `**Tipo:** saludo` en markdown. No es que el modelo se
    olvide: es que nadie se lo estaba obligando.

    En vivo eso salia como `tipo_vacio` en tres de cada cuatro turnos, y un
    tipo vacio no es cosmetico: de el sale la señal del cierre en `_senal`, asi
    que un `intencion_compra` que no se encasilla es una venta que no se toma.

    EL ENUM ES EL CANDADO. Los veinte tipos viajan como valores permitidos, de
    la misma fuente que el prompt: un tipo inventado deja de ser posible en vez
    de tolerarse. Es la regla cero aplicada al formulario de la respuesta.

    CONVIVE CON EL MOTOR, y se midio antes de escribirlo: cuando el modelo
    llama a `buscar`, el contenido viene vacio y el esquema no estorba; cuando
    contesta, sale el JSON. Por eso viaja en TODAS las vueltas y no solo en la
    ultima.
    """
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "respuesta_al_cliente",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "tipo": {"type": "string", "enum": list(TP.ORDEN)},
                    "texto": {"type": "string"},
                },
                "required": ["tipo", "texto"],
            },
        },
    }


def _voz(negocio: str) -> str:
    """QUIEN HABLA. Es lo unico anclado al principio y no se movio: la identidad
    de la casa tiene que estar antes que todo, incluso antes de la pregunta."""
    from app.core.guia_venta_prosa import identidad
    return identidad(negocio) or ""


def _moldes() -> str:
    """LOS VEINTE MOLDES, y viajan SOLO en la vuelta de contestar.

    El motivo entero esta arriba de `_COMO_SUENA`: en la vuelta de buscar no se
    decide como suena la respuesta, y tener los veinte delante induce al modelo
    a elegir un tipo primero y a pedir despues los campos que ese tipo sugiere.
    """
    return _COMO_SUENA + TP.bloque_para_el_prompt()


def _aparato() -> str:
    """EL APARATO ENTERO: las reglas y los veinte moldes. Es lo que ve el
    modelo en la vuelta de CONTESTAR; en las de buscar viaja solo `_REGLAS`.

    Va DESPUES de la pregunta.

    POR QUE SE PARTIO EN DOS (12-sep-2026). Hasta hoy la voz y el aparato eran
    un solo bloque de sistema, asi que el modelo leia dos mil y pico de tokens
    de instrucciones y moldes ANTES de saber que le habian preguntado. Elegir
    entre veinte tipos sin tener la pregunta delante es elegir a ciegas: lo que
    queda fresco es el ultimo molde leido, no el que corresponde.

    Medido lo que pasaba: `tipo_vacio` en la mitad de los turnos, y el 12-sep
    00:58 un pedido de precios de seis productos encasillado como
    `politica_sin_cubrir` —el molde de "eso no lo tengo escrito"— teniendo
    quince fichas en la mano.

    Ahora el orden es: quien habla, QUE LE PREGUNTARON, como se contesta.
    """
    return _REGLAS + _moldes()


def _memoria_texto(conv: dict) -> str:
    """Lo que el modelo tiene que recordar de la charla, en pocas lineas.

    LA MEMORIA NO SE APAGO Y NO SE APAGA. Es el objetivo 3 del proyecto: una
    referencia lejana tiene que resolver. Lo que se apago es la maquinaria que
    la rodeaba, no lo que el sistema recuerda.
    """
    partes = []
    resumen = (conv.get("summary") or "").strip()
    if resumen:
        partes.append("De lo que ya hablaron: " + resumen)
    vistos = conv.get("productos_vistos") or []
    ultimo = max((int(p.get("turno") or 0) for p in vistos), default=0)
    recien = [p for p in vistos if ultimo and int(p.get("turno") or 0) == ultimo]
    if recien:
        # "EL SEGUNDO", "EL MAS BARATO DE ESOS", "ESE". Es lo que nombro tu
        # ultimo mensaje, numerado en el orden en que el cliente lo leyo, que
        # es el unico orden al que el cliente se puede referir.
        #
        # UN MODELO EN DOS COLORES ES UN RENGLON, porque asi lo lee el cliente:
        # "el G203 en negro o blanco" es UNA opcion. Numerados por separado,
        # "el segundo" caia en el G203 blanco y no en el G502 —medido en la
        # tanda de charlas del 22-sep, CH2—.
        grupos: list = []
        for p in recien:
            clave = p.get("grupo") or p.get("modelo") or p.get("id")
            if grupos and grupos[-1][0] == clave:
                grupos[-1][1].append(p)
            elif any(g[0] == clave for g in grupos):
                next(g for g in grupos if g[0] == clave)[1].append(p)
            else:
                grupos.append((clave, [p]))
        partes.append(
            "LO QUE NOMBRASTE EN TU ULTIMO MENSAJE, en el orden en que el "
            "cliente lo leyo. 'El segundo' es el 2; 'ese', 'lo', 'el mismo' "
            "o 'esos' es esto, y 'de esos' se elige ENTRE ESTOS, no en el "
            "catalogo:\n"
            + "\n".join(
                f"{n}. " + " / ".join(
                    f"{p.get('id')}: {p.get('nombre')}"
                    + (f", {p['precio']}" if p.get("precio") else "")
                    for p in ps)
                for n, (_c, ps) in enumerate(grupos[:8], 1)))
        vistos = [p for p in vistos if p not in recien]
    if vistos:
        # CON ID Y CON PRECIO, y las dos cosas por un caso medido.
        #
        # EL 12-SEP A LAS 00:06 y a las 00:08 el bot le contesto DOS VECES
        # seguidas "no tengo esa informacion confirmada" a un cliente que estaba
        # armando un presupuesto. Lo que paso adentro: el modelo escribio los
        # precios de lo que ya habia mostrado SACANDOLOS DE SU CABEZA -algunos
        # acertados, otros sumados a mano- y la guarda de procedencia tiro la
        # respuesta entera, con razon.
        #
        # No podia hacer otra cosa: este bloque le mandaba los NOMBRES pelados.
        # Sin el precio no tenia de donde copiarlo; sin el id no podia ni volver
        # a buscarlo, aunque `buscar` acepta ids y su descripcion dice, textual,
        # "para volver a un producto que ya le mostraste". La capacidad estaba
        # escrita y el modelo no tenia con que usarla.
        #
        # El precio aca ES fuente -viaja en el prompt, igual que el inventario-
        # asi que copiarlo de aca ya no es inventar.
        partes.append(
            "Productos que le mostraste ANTES, con su id y su precio, del "
            "mas viejo al mas reciente"
            + ("" if recien else
               "; si dice 'ese' o 'el que me dijiste', es el ultimo")
            + ":\n"
            + "\n".join(
                f"- {p.get('id')}: {p.get('nombre')}"
                + (f", {p['precio']}" if p.get("precio") else "")
                for p in vistos[-8:]))
    # EL ULTIMO PRESUPUESTO, Y ES FUENTE COMO EL PRECIO DE ARRIBA (15-sep-2026).
    #
    # MEDIDO EN WHATSAPP ESE MISMO DIA, cuatro turnos sobre UN pedido: el total
    # salio 207.500, despues 284.000 y despues 395.000, y el cuarto turno no
    # llego al cliente porque el modelo escribio $250.000 y la guarda tiro la
    # respuesta entera. Ninguna de las tres cuentas estaba mal sumada: cada
    # turno ELIGIO productos y cantidades distintas, porque lo unico que
    # sobrevivia al turno eran los nombres de lo mostrado.
    #
    # Con el presupuesto delante el modelo no rearma el carrito: lo copia. Y al
    # viajar en el prompt es FUENTE, asi que copiar ese total ya no es inventar
    # y la guarda de procedencia deja de matar la respuesta.
    #
    # LA REGLA DE FRESCURA VA PEGADA AL DATO, que es donde se usa: si el pedido
    # cambio, se pide la cuenta de nuevo. Corregir un total a mano es la unica
    # forma de que vuelva a aparecer una cifra sin procedencia.
    presu = (conv.get("ultimo_presupuesto") or "").strip()
    if presu:
        partes.append(
            "EL ULTIMO PRESUPUESTO que ya le pasaste. Estos numeros son "
            "fuente: copialos tal cual. Si el pedido cambio, pedi la cuenta de "
            "nuevo por el motor en vez de corregirlos a mano:\n" + presu[:700])
    carrito = conv.get("carrito_vigente") or []
    if carrito:
        # CON ID Y CON CANTIDAD, por lo mismo que los productos vistos: sin el
        # id el modelo no puede volver a pedir la cuenta de lo mismo, y sin la
        # cantidad la vuelve a elegir -medido: el cliente pidio dos de cada uno
        # y el turno siguiente cotizo uno-.
        partes.append("EN EL PEDIDO, tal como se conto: " + " · ".join(
            f"{p.get('cantidad') or 1}x {p.get('id')} {p.get('nombre') or ''}".strip()
            for p in carrito[:8]))
    # LO QUE EXCLUYO O PREFIRIO, y el codigo lo repone solo en la busqueda
    # del mismo rubro. Se le dice al modelo para que no ofrezca de palabra lo
    # que el motor ya saco.
    vig = (conv.get("preferencias_cliente") or {}).get("vigentes") or []
    renglones_vig = [f"{x.get('categoria')}: {x.get('campo')} "
                     f"{x.get('operador')} {x.get('valor')}"
                     for x in vig if isinstance(x, dict)]
    if renglones_vig:
        partes.append("LO QUE EL CLIENTE YA EXCLUYO O PREFIRIO, y sigue "
                      "valiendo si refina la busqueda: "
                      + " · ".join(renglones_vig[:6]))
    descartados = [str(x) for x in (conv.get("descartados") or [])]
    if descartados:
        partes.append("Ya dijo que NO a: " + ", ".join(descartados[:6]))
    loc = (conv.get("ultima_localidad") or "").strip()
    if loc:
        partes.append("Envia a: " + loc)
    datos = conv.get("datos_cliente_parciales") or {}
    if datos.get("nombre"):
        partes.append("Se llama: " + str(datos["nombre"]))
    return "\n".join(partes)



def _vigentes_que_siguen(vigentes: dict | None, mensaje: str) -> dict:
    """Lo que el cliente excluyo o prefirio en turnos anteriores, que sigue
    valiendo en este (22-sep-2026).

    MEDIDO EN LA TANDA DE CHARLAS, CH21: "auriculares que no sean redragon",
    y al turno siguiente "y algo mas barato?" busco auriculares SIN la
    exclusion. Entre vueltas de un turno el cotejo ya la reponia; entre turnos
    se perdia, porque la memoria no guardaba con que criterio se busco.

    ENTRE TURNOS EL CLIENTE HABLO, y por eso la regla es mas estricta que entre
    vueltas: una exclusion se arrastra SOLO si el mensaje nuevo no vuelve a
    nombrar ese valor. Si dice "ahora si, mostrame redragon", manda lo que el
    modelo declare en este turno. Son las mismas `REPONIBLES` del cotejo:
    excluir o graduar, nunca un filtro positivo que pueda vaciar la busqueda.
    """
    from app.core import cotejo as CO
    m = CO.norm(mensaje)
    fuera: dict = {}
    for x in (vigentes or []):
        if not isinstance(x, dict) or not x.get("categoria"):
            continue
        if CO.norm(x.get("operador")) not in CO.REPONIBLES:
            continue
        if CO.norm(x.get("valor")) in m:
            continue
        cond = {k: x.get(k) for k in ("campo", "operador", "valor")}
        fuera.setdefault(CO.norm(x["categoria"]), {})[CO.firma(cond)] = cond
    return fuera


def _vigentes_para_guardar(condiciones: dict) -> list:
    """El estado del turno como lista plana, que es lo que se guarda: una
    clave armada con la condicion no es un nombre de campo seguro."""
    from app.core import cotejo as CO
    return [dict(categoria=cat, **{k: x.get(k) for k in
                                   ("campo", "operador", "valor")})
            for cat, conds in (condiciones or {}).items()
            for x in conds.values()
            if isinstance(x, dict)
            and CO.norm(x.get("operador")) in CO.REPONIBLES][:12]


def _lo_ultimo_nombrado(vistos: list | None, tienda_id: str) -> list:
    """[(id, categoria)] de lo que nombro la ultima respuesta, para que el
    cotejo resuelva "de esos". La categoria sale de la fuente y no de la
    memoria: la memoria guarda lo que se dijo, la fuente dice que es."""
    from app.storage.firestore_client import get_product_by_id
    vistos = vistos or []
    ultimo = max((int(p.get("turno") or 0) for p in vistos), default=0)
    fuera = []
    for p in vistos:
        if not ultimo or int(p.get("turno") or 0) != ultimo:
            continue
        try:
            prod = get_product_by_id(str(p.get("id")),
                                     tienda_id=tienda_id) or {}
        except Exception:  # noqa: BLE001 — sin producto no hay rubro
            prod = {}
        fuera.append((str(p.get("id")), str(prod.get("categoria") or "")))
    return fuera


def _nombrados(texto: str, fichas: list, tienda_id: str) -> list:
    """Las fichas que la respuesta NOMBRA, en el orden en que las nombra.

    SE APAREA POR MODELO, que es la palabra que distingue un producto en una
    respuesta —"el K120", "el G203"—, y no por el nombre entero, que el modelo
    casi nunca copia tal cual. Un modelo de menos de tres letras no se busca:
    aparear por parecido es la enfermedad que el MAPA_CABLEADO tiene numerada.
    El mismo modelo en dos colores queda en el lugar donde se nombro, con el
    color que la respuesta dice primero.
    """
    import re
    from app.storage.firestore_client import get_product_by_id
    t = _norm_simple(texto)
    hallados = []
    for f in fichas or []:
        try:
            prod = get_product_by_id(str(f.get("id")), tienda_id=tienda_id) or {}
        except Exception:  # noqa: BLE001 — sin producto no se aparea
            prod = {}
        apariciones = sorted({m.start() for k in _claves_modelo(prod.get("modelo"))
                              for m in re.finditer(re.escape(k), t)})
        if not apariciones:
            continue
        # SI EL MODELO SE NOMBRA UNA VEZ, sus colores son UN renglon: "el G203
        # en negro o blanco". SI SE NOMBRA POR COLOR -"1. G203 negro, 2. G203
        # blanco"- cada color es su renglon, y la posicion es la de la
        # aparicion que sigue su color. Manda lo que el cliente leyo.
        color = _norm_simple(prod.get("color"))
        i = apariciones[0]
        if len(apariciones) > 1 and color:
            i = next((a for a in apariciones
                      if color in t[a:a + 60].split(",")[0]), i)
        j = t.find(color, i) if color else -1
        grupo = (str(prod.get("modelo") or "") if len(apariciones) == 1
                 else str(f.get("id")))
        hallados.append((i, j if j >= 0 else 10 ** 6,
                         dict(f, modelo=str(prod.get("modelo") or ""),
                              grupo=grupo)))
    hallados.sort(key=lambda x: (x[0], x[1]))
    visto, fuera = set(), []
    for _i, _j, f in hallados:
        if str(f.get("id")) not in visto:
            visto.add(str(f.get("id")))
            fuera.append(f)
    return fuera


def _claves_modelo(modelo) -> list:
    """Como se nombra un modelo en una respuesta: entero -"G Pro X
    Superlight"- o por la parte que lleva numeros -"G203" de "G203
    Lightsync"-, que es la que usan el cliente y el bot. Una palabra sin
    numeros no alcanza: "Pro" o "Core" estan en veinte modelos."""
    import re
    m = _norm_simple(modelo)
    claves = [m] if len(m) >= 3 else []
    claves += [w for w in re.split(r"\s+", m)
               if len(w) >= 3 and any(c.isdigit() for c in w)
               and any(c.isalpha() for c in w) and w != m]
    return claves


def _norm_simple(t) -> str:
    import unicodedata
    t = unicodedata.normalize("NFD", str(t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _vistos_al_dia(vistos: list, fichas: list, texto: str, turno: int,
                   tienda_id: str) -> list:
    """La lista de productos vistos despues de este turno.

    LO NOMBRADO VA AL FINAL, EN SU ORDEN Y CON SU TURNO. Si la respuesta no
    nombra ninguna ficha por su modelo —una charla sobre envio, o un nombre que
    no se pudo aparear— se guardan las fichas como antes, para no perder el id:
    olvidar es peor que recordar de mas.
    """
    nombrados = _nombrados(texto, fichas, tienda_id)
    nuevos = nombrados or [f for f in fichas or []
                           if str(f.get("id")) not in
                           {str(p.get("id")) for p in vistos}]
    ids = {str(f.get("id")) for f in nuevos}
    fuera = [p for p in vistos if str(p.get("id")) not in ids]
    for f in nuevos:
        # EL PRECIO SE GUARDA: sin el, el turno siguiente no puede decir
        # cuanto salia lo que ya se mostro.
        fuera.append({"id": f.get("id"), "nombre": f.get("nombre"),
                      "precio": f.get("precio"),
                      "modelo": f.get("modelo") or "",
                      "grupo": f.get("grupo") or f.get("modelo") or "",
                      "turno": turno if nombrados else 0})
    return fuera

def _bloque_fuente(politicas: list, inventario: str = "",
                   envio: str = "") -> str:
    """Lo que el codigo pone delante del modelo SIN que lo pida.

    YA NO HAY FICHAS ACA, y es el cambio de la FICHA 50: las trae el modelo con
    `buscar`. Queda lo que ninguna busqueda puede contestar y por eso viaja
    siempre.

    EL INVENTARIO. Medido el 11-sep: a "¿cuantos productos vendes?" el bot
    contesto "5 modelos de memorias RAM", porque el encabezado le decia "es
    todo lo que existe" arriba de las cinco fichas que la relevancia habia
    traido. Una pregunta sobre el catalogo ENTERO no la contesta ninguna
    busqueda por parecido: son dos renglones y van siempre.

    LAS POLITICAS siguen certificadas por el codigo. Son el mapa 3 y no cambian
    en esta vuelta.

    EL ENVIO SALIO DE ACA EL 13-sep: era el ultimo dato que se empujaba, y
    ahora lo pide el modelo por el motor como todo lo demas. El argumento que
    lo sostenia -que no hay nada que razonar en un codigo postal- sigue siendo
    cierto y no alcanzaba: el precio de tenerlo servido fue que la politica del
    rango compitiera con la tarifa exacta y que el turno que preguntaba por el
    envio fuera justo el que no llamaba al motor.
    """
    partes = []
    if inventario:
        partes.append(inventario)
    if envio:
        partes.append(envio)
    if politicas:
        partes.append("POLITICAS DE LA CASA que tocan este mensaje:\n"
                      + "\n".join(f"- {p['tema']}: {p['texto']}" for p in politicas))
    return "\n\n".join(partes)



def _parsear(crudo: str) -> dict:
    """El JSON del modelo, o el texto pelado si no vino como JSON. Un modelo
    que se olvida del formato no puede dejar mudo al bot."""
    t = (crudo or "").strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t[t.find("{"):] if "{" in t else t
    try:
        d = json.loads(t[t.index("{"):t.rindex("}") + 1])
        if isinstance(d, dict) and (d.get("texto") or "").strip():
            return {"tipo": str(d.get("tipo") or ""), "texto": str(d["texto"])}
    except Exception:  # noqa: BLE001 — abajo esta la salida honesta
        pass
    return {"tipo": "", "texto": (crudo or "").strip()}


# Cuantas veces puede buscar el modelo en un turno. Dos, y el numero tiene
# motivo: una para buscar y otra para corregir si lo que salio no sirve, que es
# la capacidad que la FICHA 50 pide con todas las letras. La tercera no la pide
# nadie y cada vuelta es una llamada al modelo.
VUELTAS_DE_BUSQUEDA = 2


def _informe_en_blanco() -> dict:
    """EL NUMERO DEL MOTOR, un renglon por turno.

    QUE CONTESTA, que es lo que hoy no se puede contestar de ninguna otra
    forma: si el modelo USA el motor o lo esquiva, cuantas vueltas le cuesta
    -y cada vuelta vuelve a pagar el prompt entero-, si lo que vuelve le
    sirve o tiene que buscar de nuevo, y QUE LE FALTA A LA FUENTE, que sale
    solo de `campos`: una condicion que el catalogo no puede cumplir es un
    campo que habria que agregar, y hasta hoy eso se descubria leyendo
    charlas a mano.

    Las cuatro perillas del motor -dos vueltas, ocho filas, seis consultas,
    cinco por defecto- estan puestas a ojo. Este renglon es lo que permite
    moverlas mirando, y por eso va antes que cualquier arreglo de robustez.
    """
    # `campos_tocados` es el estado que la guarda de `guardas_salida` cruza
    # contra la respuesta: los campos que el turno miro de verdad. No es lo
    # mismo que `campos`, que son los que NO se pudieron aplicar.
    # LOS CINCO NUMEROS DEL COTEJO (22-sep-2026). Salen de `app.core.cotejo` y
    # miden lo mismo desde cinco lados: cuanto de lo que el modelo declaro se
    # puede cotejar contra lo que el cliente dijo. `renglones` y
    # `renglones_copia` son la base —sobre un renglon parafraseado no se puede
    # cotejar nada— y los otros tres son lo que el codigo ya corrigio solo.
    return {"campos_tocados": set(), "correcciones": 0,
            "vueltas": 0, "llamadas": 0, "consultas": 0, "repetidas": 0,
            "puntuales": 0, "veredictos": [], "filas": 0, "rescates": 0,
            "vacios": 0, "sin_dato": 0, "campos": [], "fichas": 0,
            "temas": [], "temas_sin_resolver": [], "compat": [],
            "compat_sin_dato": [], "afirma": [], "envios": [],
            "envios_sin_clasificar": [],
            "criterio": [], "criterio_sin_resolver": [],
            "cuentas": 0, "cuentas_sin_total": 0,
            "renglones": 0, "renglones_copia": 0, "renglones_propios": [],
            "rubros_sin_pedir": [], "umbrales_degradados": [],
            "condiciones_repuestas": [], "vueltas_sin_aporte": 0}


def _anotar(informe: dict, consultas: list, pedidas: set, r: dict) -> None:
    """Suma al informe lo que hizo ESTA llamada al motor.

    LA CONSULTA REPETIDA SE CUENTA APARTE, y es el unico numero de aca que no
    se puede sacar del resultado: entre vuelta y vuelta el modelo no ve lo que
    ya pidio, solo lo que volvio, asi que puede gastar la segunda vuelta
    repitiendo la primera. Si eso pasa seguido, el arreglo no es subir el tope
    de vueltas: es decirle que ya lo busco.
    """
    for c in (consultas or []):
        informe["consultas"] += 1
        # LOS CAMPOS QUE ESTA CONSULTA MIRO. Es el estado con el que se juzga
        # despues si la respuesta afirmo sobre algo que el turno nunca tuvo
        # delante: un campo que entro por una condicion o por el orden ya
        # volvio con su dato o con el motivo de por que no.
        for cond in (c or {}).get("condiciones") or []:
            campo = str((cond or {}).get("campo") or "")
            if campo:
                informe["campos_tocados"].add(campo)
        orden = str(((c or {}).get("ordenar_por") or {}).get("campo") or "")
        if orden:
            informe["campos_tocados"].add(orden)
        # CUANTAS VECES DECLARO QUE EL CLIENTE NOMBRO UNA COSA. Sin este numero
        # no hay forma de saber si `busco` se usa: la ambiguedad podria estar
        # muerta -el modelo no lo declara nunca- y el informe se veria igual,
        # con cero ambiguos, que es exactamente como se ve cuando no hubo
        # ninguna. Lo pidio la primera tanda viva con el numero puesto.
        if str((c or {}).get("busco") or "") == "uno":
            informe["puntuales"] += 1
        seña = json.dumps(c, ensure_ascii=False, sort_keys=True, default=str)
        if seña in pedidas:
            informe["repetidas"] += 1
        else:
            pedidas.add(seña)
    # LOS TEMAS QUE EL MODELO PIDIO, Y LOS QUE LA CASA NO TIENE ESCRITOS. El
    # segundo numero es el que dice que le FALTA A LA FAQ, y hasta hoy no
    # existia: con el codigo adivinando el tema, un tema sin resolver era
    # indistinguible de uno que nadie pregunto.
    for a in (r or {}).get("afirma") or []:
        informe["afirma"].append(str(a.get("veredicto") or ""))
    for p in (r or {}).get("politicas") or []:
        informe["temas"].append(str(p.get("tema") or ""))
    for n in (r or {}).get("temas_sin_resolver") or []:
        informe["temas_sin_resolver"].append(str(n))
    # LOS PARES DE COMPATIBILIDAD Y —EL QUE IMPORTA— LOS QUE LA TABLA NO PUDO
    # CONTESTAR. Es el mismo par de numeros que `temas` / `temas_sin_resolver`:
    # el segundo dice QUE FILA FALTA en `compatibilidad.csv`, y sin el un hueco
    # de la tabla es indistinguible de una pregunta que nadie hizo.
    for x in (r or {}).get("compatibilidad") or []:
        v = str((x or {}).get("veredicto") or "")
        informe["compat"].append(v)
        if v == "sin_dato":
            informe["compat_sin_dato"].append(
                f"{(x or {}).get('producto')}|{(x or {}).get('con')}")
    # LOS DESTINOS, Y LOS QUE NO SE PUDIERON CLASIFICAR. El segundo renglon es
    # el que dice que lugar le falta a la tabla de `geo_cp`, o que el cliente
    # escribe de una forma que no reconocemos. Antes no existia: con el codigo
    # adivinando el destino, un lugar que no clasificaba no dejaba rastro.
    for e in ((r or {}).get("envios") or {}).get("filas") or []:
        informe["envios"].append(str(e.get("destino") or ""))
        if e.get("sin_dato"):
            informe["envios_sin_clasificar"].append(str(e.get("destino") or ""))
    # LA BOCA CRITERIO, CON EL MISMO PAR DE NUMEROS QUE LAS OTRAS TRES: lo que
    # se sirvio y lo que la casa no tiene escrito. El segundo es el que dice QUE
    # ENTRADA agregarle a `base_conocimiento.json`, igual que
    # `temas_sin_resolver` con la FAQ y `compat_sin_dato` con la tabla de pares.
    for c in (r or {}).get("criterio") or []:
        informe["criterio"].append(str((c or {}).get("tema") or ""))
    for n in (r or {}).get("criterio_sin_resolver") or []:
        informe["criterio_sin_resolver"].append(str(n))
    # LA CUENTA DEL RETORNO, CON EL MISMO PAR DE NUMEROS QUE LAS BOCAS: la que
    # salio y la que no se pudo hacer. El segundo dice que le falta al pedido
    # para poder darle un total, y sin el un total que no salio es
    # indistinguible de un cliente que no lo pidio.
    _cta = (r or {}).get("cuenta") or {}
    if _cta.get("total_ars") is not None:
        informe["cuentas"] += 1
    elif _cta.get("sin_total"):
        informe["cuentas_sin_total"] += 1
    # EL OTRO LADO, Y SIN EL LA GUARDA SERIA UN GENERADOR DE FALSOS
    # POSITIVOS: un campo tambien le llega al modelo adentro de la ficha, sin
    # que ninguna consulta lo haya nombrado. Hablar de la garantia de un
    # teclado cuya ficha trae `garantia_meses` no es afirmar sin mirar.
    for res in (r or {}).get("resultados") or []:
        for fila in res.get("filas") or []:
            informe["campos_tocados"].update(
                str(k) for k, v in (fila or {}).items()
                if v not in (None, "") and not isinstance(v, dict))
            informe["campos_tocados"].update(
                str(k) for k in (fila or {}).get("specs") or ())
    for res in (r or {}).get("resultados") or []:
        veredicto = str(res.get("veredicto") or "")
        filas = len(res.get("filas") or [])
        informe["veredictos"].append(veredicto)
        informe["filas"] += filas
        informe["sin_dato"] += int(res.get("sin_dato") or 0)
        if not filas:
            informe["vacios"] += 1
        elif veredicto == "no_existe":
            # Trajo lo mas parecido: la condicion no se pudo cumplir entera.
            informe["rescates"] += 1
        for na in res.get("no_aplicado") or []:
            campo = str((na or {}).get("campo") or "")
            if campo:
                informe["campos"].append(campo)


async def _preguntar(voz: str, memoria: str, history: list, mensaje: str,
                     fuente: str, trace_id: str, tienda_id: str,
                     localidad_previa: str = "",
                     vigentes: list | None = None,
                     vistos: list | None = None) -> tuple:
    """La llamada al modelo, con el motor de busqueda en la mano.

    EL ORDEN DE LECTURA, y es lo que cambio el 12-sep. Lo que el modelo lee,
    en este orden y ninguno otro:

      1. LA VOZ     quien habla. Anclado al principio, como siempre.
      2. LA PREGUNTA el mensaje del cliente, PELADO. Antes que el aparato.
      3. EL APARATO  las reglas y los veinte moldes.
      4. LA MEMORIA  lo que ya se hablo.
      5. LA CHARLA   el historial, en orden.
      6. EL TURNO    la fuente, lo que volvio de buscar, y el mensaje otra vez
                     al final, que es donde tiene que estar fresco.

    El mensaje aparece dos veces a proposito y cuesta decenas de tokens: arriba
    para que el modelo sepa que le preguntaron antes de leer como se contesta,
    y abajo para que sea lo ultimo que ve antes de escribir.

    EL MODELO BUSCA Y DESPUES CONTESTA, y esa es la vuelta que agrega la FICHA
    50. Antes el codigo adivinaba que fichas ponerle delante leyendo el mensaje
    crudo; ahora el modelo escribe la consulta y el codigo la ejecuta.

    Devuelve (salida, fichas, envios, cuenta, informe). Las fichas, los envios
    y la cuenta son lo que volvio del motor, y son las TRES procedencias que
    `numeros` necesita: un precio, una tarifa o un total que no este en lo que
    el modelo EFECTIVAMENTE pidio no puede salir al cliente. Los envios son
    {destino: monto}; la cuenta es el total ya calculado por `calculadora`.

    EL INFORME ES EL NUMERO DEL MOTOR, y por eso se arma aca y no adentro de
    `motor.py`: el motor ve UNA llamada, y lo que hay que medir es el TURNO
    -cuantas vueltas costo, si el modelo re-busco, si repitio la misma consulta,
    y que condicion no se pudo aplicar-. Nada de esto se puede reconstruir
    despues desde afuera: si no sale del turno, no existe.
    """
    from app.core import cotejo as CO
    from app.core import guardas_salida as gs
    from app.core import motor as MT
    from app.core.llm_reintento import _cliente, _modelo, _modelo_decisor
    informe = _informe_en_blanco()
    cli = _cliente()
    if cli is None:
        log.warning("respuesta_sin_clave", trace_id=trace_id)
        return {}, [], {}, {}, informe
    msgs = [{"role": "system", "content": voz}] if voz else []
    # LA PREGUNTA, ANTES QUE EL APARATO. Es el cambio del 12-sep y el motivo
    # esta entero en `_aparato`.
    msgs.append({"role": "system",
                 "content": "ESTO ES LO QUE TE PREGUNTO EL CLIENTE Y ES LO QUE "
                            "TENES QUE CONTESTAR:\n" + (mensaje or "")})
    # LAS REGLAS VIAJAN SIEMPRE; LOS MOLDES SOLO EN LA VUELTA DE CONTESTAR, y
    # se enchufan adentro del loop, justo aca, para que el orden de lectura no
    # cambie: voz, pregunta, reglas, MOLDES, memoria, charla, turno.
    corte_moldes = len(msgs)
    msgs.append({"role": "system", "content": _REGLAS})
    if memoria:
        msgs.append({"role": "system", "content": memoria})
    for h in (history or [])[-(settings.HISTORY_LIMIT * 2):]:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            msgs.append({"role": h["role"], "content": str(h["content"])[:900]})

    try:
        herramientas = [MT.esquema(tienda_id)]
    except Exception as e:  # noqa: BLE001 — sin esquema se contesta sin buscar
        log.warning("respuesta_esquema_error", trace_id=trace_id,
                    error=f"{type(e).__name__}: {str(e)[:120]}")
        herramientas = []

    # NO SE LE REENVIA AL MODELO SU PROPIA LLAMADA, y no es una eleccion de
    # estilo. El protocolo de herramientas pide devolver el mensaje `assistant`
    # con sus `tool_calls` y despues el rol `tool`; Gemini ademas exige que ese
    # eco traiga un `thought_signature` suyo, y sin el contesta 400 -medido el
    # 11-sep, seis de seis-. Reenviar campos propios de un proveedor ata el
    # turno a ese proveedor.
    #
    # Lo que se hace en cambio: el resultado de la busqueda se le pone delante
    # como UN BLOQUE MAS de la fuente, que es exactamente lo que es. La vuelta
    # siguiente es una llamada limpia con ese bloque adentro. Funciona igual en
    # cualquier proveedor compatible y no tiene protocolo que mantener.
    fichas: list = []
    # LOS ENVIOS SE ACUMULAN COMO LAS FICHAS, y por el mismo motivo: son la
    # procedencia de la tarifa. Un destino cotizado en la primera vuelta tiene
    # que seguir valiendo en la ultima, que es donde el modelo escribe.
    envios: dict = {}
    # LA CUENTA SE ACUMULA COMO LAS FICHAS Y LOS ENVIOS, y por el mismo motivo:
    # es la tercera procedencia. Un total calculado en la primera vuelta tiene
    # que seguir valiendo en la ultima, que es donde el modelo escribe.
    cuenta: dict = {}
    # EL REPARTO SE ACUMULA, IGUAL QUE LAS FICHAS, LOS ENVIOS Y LA CUENTA, y
    # por el mismo motivo: declarado en una vuelta tiene que seguir valiendo en
    # la que trae la cuenta.
    #
    # MEDIDO EL 20-sep, revision 00555: las tres corridas declararon el reparto
    # y la cuenta en vueltas DISTINTAS, y el total solo salio con descuento en
    # las dos donde el modelo los repitio juntos. Sin esto, acordarse depende
    # de que el modelo se acuerde, y eso es pedirle que haga gratis lo que el
    # codigo garantiza gratis.
    reparto: list = []
    hallazgos: list = []
    # LA CORRECCION VIAJA APARTE DE LOS HALLAZGOS, y no es cosmetica: los
    # hallazgos salen bajo el encabezado "LO QUE DEVOLVIO TU BUSQUEDA", y la
    # correccion no es un retorno de busqueda —es el codigo diciendole que lo
    # que escribio no se sostiene—. Mezclarlas seria la segunda descripcion de
    # dos cosas distintas bajo un mismo titulo.
    correccion = ""
    # LO QUE LA CASA DEVOLVIO, para la guarda de la plata. Viaja pegado a la
    # salida y no en el informe: el informe es el renglon de metricas y tiene
    # candado de que el que escribe y el que lee nombren lo mismo.
    fuente_casa = ""
    pedidas: set = set()
    # LO QUE EL COTEJO NECESITA DE LA FUENTE, LEIDO UNA SOLA VEZ POR TURNO.
    # `cotejo` no lee la fuente a proposito —hay un test que lo exige— asi que
    # los dos enums se los pasa este borde, que ya los tiene para el esquema.
    # Si la recorrida falla, el cotejo sigue midiendo la fidelidad del renglon
    # y se apagan las dos comprobaciones que dependen del catalogo: un turno
    # no se cae porque una comprobacion no pueda correr.
    try:
        from app.core.filtros_catalogo import campos_ordenables, recorrida
        _ordenables = campos_ordenables(tienda_id)
        _categorias = [c for c, _ in recorrida(tienda_id).get(
            "categorias") or []]
    except Exception as e:  # noqa: BLE001
        log.warning("cotejo_sin_fuente", trace_id=trace_id,
                    error=f"{type(e).__name__}: {str(e)[:120]}")
        _ordenables, _categorias = [], []
    # LAS CONDICIONES DECLARADAS EN ESTE TURNO, por categoria. Es estado del
    # turno igual que `pedidas`, y vive aca por el mismo motivo: declarado en
    # una vuelta tiene que seguir valiendo en la ultima, que es donde el
    # modelo escribe.
    condiciones_del_turno: dict = _vigentes_que_siguen(vigentes, mensaje)
    # EL LOOP ES UN `while` DESDE EL 16-sep, y el motivo es uno solo: la
    # correccion de estado puede pedir UNA vuelta mas. `tope` son las vueltas
    # que llevan tablero, o sea en las que se puede buscar; siempre hay una
    # ultima sin tablero, que es la de contestar. Un turno que no se corrige
    # cuesta exactamente lo que costaba.
    tope = VUELTAS_DE_BUSQUEDA
    vuelta = 0
    corregido = False
    while vuelta <= tope:
        informe["vueltas"] += 1
        # LA FUENTE VIAJABA DOS VECES, y era un bug de cableado, no una
        # eleccion (12-sep-2026). `msgs` ya llevaba un turno de usuario con el
        # mensaje Y la fuente enteros, y aca se armaba OTRO igual: el
        # inventario, el bloque de envio y las politicas llegaban duplicados al
        # modelo en cada una de las hasta tres vueltas. Ahora el turno se arma
        # en un solo lugar y `msgs` no lo trae.
        partes = []
        if fuente:
            partes.append(fuente)
        if hallazgos:
            partes.append(_COMO_SE_LEE + "\n".join(hallazgos))
        # LA CORRECCION, PEGADA AL MENSAJE. Va ultima de la fuente y antes del
        # pedido del cliente, que es donde queda fresca: lo que se le esta
        # pidiendo es que reescriba, y eso se lee justo antes de escribir.
        if correccion:
            partes.append(correccion)
        # EL MENSAJE, ULTIMO. Que sea lo ultimo que lee antes de escribir.
        partes.append("Contesta ESTE mensaje del cliente: " + (mensaje or ""))
        # En la ultima vuelta la herramienta ya no viaja: es la vuelta de
        # CONTESTAR. Sin esto el modelo puede quedarse buscando para siempre y
        # el cliente sin respuesta.
        tools = herramientas if (herramientas and vuelta < tope) else None
        # Y ES LA MISMA LINEA LA QUE DECIDE LOS MOLDES, a proposito: donde hay
        # herramienta se busca, y donde no hay, se contesta. Que las dos cosas
        # salgan de la misma condicion hace imposible que se desincronicen.
        cabeza = msgs if tools else (
            msgs[:corte_moldes + 1]
            + [{"role": "system", "content": _moldes()}]
            + msgs[corte_moldes + 1:])
        turno = cabeza + [{"role": "user", "content": "\n\n".join(partes)}]

        # QUE VIAJO, POR VUELTA. Es el primero de los dos renglones que le
        # faltaban a la sonda de produccion (15-sep-2026): desde afuera no
        # habia forma de saber que tenia el modelo delante cuando decidio.
        # No viaja el TEXTO -seria el prompt entero en cada turno- sino su
        # forma: que bloques estaban, cuanto pesaban y en que vuelta.
        log.info("prompt_armado", trace_id=trace_id, vuelta=vuelta + 1,
                 con_tablero=bool(tools), con_moldes=not bool(tools),
                 modelo=(_modelo_decisor() if tools else _modelo()),
                 bloques=len(turno), hallazgos=len(hallazgos),
                 tokens=sum(len(str(m.get("content") or "")) for m in turno) // 4)

        # EL MODELO DE LA VUELTA QUE INTERPRETA (20-sep-2026), Y ES UNA
        # MEDICION, NO UNA MEJORA DECLARADA.
        #
        # `llm_reintento._modelo_decisor` ya existia desde el 2-ago para esto
        # exacto —"se le puede poner uno mas grande SOLO aca, que es donde se
        # decide"— y quedo sin llamar cuando el decisor viejo se apago el
        # 11-sep. Esto lo vuelve a enchufar en el camino vivo; no es una pieza
        # nueva.
        #
        # LA MISMA LINEA QUE DECIDE EL TABLERO decide el modelo, igual que ya
        # decide los moldes: donde hay herramienta se interpreta, y donde no
        # hay, se redacta. Que las tres cosas salgan de la misma condicion hace
        # imposible que se desincronicen.
        #
        # POR QUE SE PRUEBA: medido el 20-sep sobre M1 y M6, cinco turnos, la
        # UNICA casilla que falla en los dos mensajes es la cuenta, y el
        # tablero ya no la mueve —se midio tres veces que el modelo hace el
        # reparto O la cuenta, nunca las dos—. Eso es firma de capacidad. Si
        # esto no mueve el numero, el techo es otro y se revierte: es config
        # operativa y sale con una linea.
        modelo_vuelta = _modelo_decisor() if tools else _modelo()

        def _call(_tools=tools, _msgs=turno, _modelo_v=modelo_vuelta):
            extra = {"tools": _tools, "tool_choice": "auto"} if _tools else {}
            try:
                r = cli.chat.completions.create(
                    model=_modelo_v, messages=_msgs, temperature=0.3,
                    max_tokens=900, response_format=_esquema_respuesta(),
                    **extra)
            except Exception as e:  # noqa: BLE001 — ver el renglon de abajo
                # EL TURNO NO SE CAE POR PROBAR UN MODELO. Un id mal escrito o
                # una cuota agotada del escalon de arriba dejaria al cliente
                # SIN RESPUESTA, y eso no es un costo aceptable para una
                # medicion. Se reintenta una vez con el de siempre y se anota
                # cual fue, para que el log no mienta sobre quien contesto.
                if _modelo_v == _modelo():
                    raise
                log.warning("modelo_decisor_cayo", trace_id=trace_id,
                            modelo=_modelo_v,
                            error=f"{type(e).__name__}: {str(e)[:150]}")
                r = cli.chat.completions.create(
                    model=_modelo(), messages=_msgs, temperature=0.3,
                    max_tokens=900, response_format=_esquema_respuesta(),
                    **extra)
            return r.choices[0].message if r.choices else None

        try:
            msg = await llamar_con_reintento(
                _call, timeout_s=settings.LLM_TIMEOUT_SECONDS,
                trace_id=trace_id)
        except Exception as e:  # noqa: BLE001 — el turno no se rompe por el modelo
            log.warning("respuesta_modelo_error", trace_id=trace_id,
                        error=f"{type(e).__name__}: {str(e)[:150]}")
            informe["fichas"] = len(fichas)
            return {}, fichas, envios, cuenta, informe
        if msg is None:
            informe["fichas"] = len(fichas)
            return {}, fichas, envios, cuenta, informe

        llamadas = list(getattr(msg, "tool_calls", None) or [])
        if not llamadas:
            salida = _parsear(msg.content or "")
            # ── LA CORRECCION DE ESTADO, Y ES LO QUE LA GUARDA HACE AHORA ──
            #
            # Hasta el 16-sep esto miraba y nada mas. Lo que mostro la primera
            # charla real con la guarda puesta es que mirar no alcanzaba: el
            # renglon salio correcto —`pais_fabricacion`, con 19 campos
            # tocados— y el cliente leyo la mentira igual.
            #
            # NO SE TIRA LA RESPUESTA: se le devuelve el dato y se le pide de
            # nuevo. El motivo entero, con el caso, esta en
            # `guardas_salida.correccion_de_estado`.
            #
            # UNA SOLA VEZ POR TURNO. La segunda seria perseguir al modelo
            # hasta que diga lo que queremos.
            if not corregido and informe["correcciones"] < gs.TOPE_CORRECCIONES:
                aviso = gs.correccion_de_estado(
                    salida.get("texto") or "", informe["campos_tocados"],
                    tienda_id, trace_id)
                if aviso:
                    corregido = True
                    informe["correcciones"] += 1
                    correccion = aviso
                    # LA VUELTA QUE VIENE LLEVA TABLERO, y es la unica forma
                    # de que la correccion sirva: se le pide que busque el
                    # campo que no busco, asi que tiene que poder buscar.
                    #
                    # ES `+2` Y NO `+1`, y el test lo cazo: el tablero viaja
                    # mientras `vuelta < tope`, asi que para que la vuelta
                    # `vuelta+1` lo lleve, el tope tiene que quedar en
                    # `vuelta+2`. Con `+1` la correccion viajaba a una vuelta
                    # sin tablero, o sea que se le devolvia el dato y no se le
                    # daba con que buscarlo.
                    #
                    # Y LA DE DESPUES NO LO LLEVA, que es lo que cierra el
                    # turno: si en la vuelta de correccion busca, la siguiente
                    # es la de contestar. Peor caso, cuatro llamadas en vez de
                    # tres, y solo en el turno que se corrige.
                    tope = vuelta + 2
                    vuelta += 1
                    continue
            informe["fichas"] = len(fichas)
            salida["fuente_casa"] = fuente_casa
            salida["vigentes"] = condiciones_del_turno
            return salida, fichas, envios, cuenta, informe

        for c in llamadas:
            informe["llamadas"] += 1
            try:
                args = json.loads(c.function.arguments or "{}")
            except Exception:  # noqa: BLE001 — un JSON roto no tumba el turno
                args = {}
                log.warning("motor_argumentos_rotos", trace_id=trace_id,
                            crudo=str(c.function.arguments)[:200])
            consultas = args.get("consultas") or []
            # LOS DOS OBLIGATORIOS VAN PRIMEROS Y NACEN MUDOS (21-sep-2026).
            # `renglones` es lo que el cliente pidio con SUS palabras y
            # `pedir_total` el si o no del presupuesto. Los dos VIAJAN Y SE
            # LOGUEAN Y NADA MAS: ninguna respuesta cambia por ellos, que es
            # la regla 2 de las seis contra la cascada. La cuenta la sigue
            # haciendo `cuenta.items` cuando hay ids, igual que ayer.
            pidio = {"renglones": args.get("renglones") or [],
                     "pedir_total": bool(args.get("pedir_total")),
                     "consultas": consultas, "temas": args.get("temas") or [],
                     "compatibilidad": args.get("compatibilidad") or [],
                     "afirma": args.get("afirma") or [],
                     "envios": args.get("envios") or [],
                     "criterio": args.get("criterio") or [],
                     "cuenta": args.get("cuenta") or {},
                     "reparto_pago": args.get("reparto_pago") or []}
            # LO QUE EL MODELO ESCRIBIO, TAL CUAL, y es EL renglon que faltaba.
            # `motor_buscar` cuenta cuantas consultas hubo y cuantas filas
            # volvieron; con que PALABRAS se pidio no quedaba en ningun lado.
            # El banco lo ve con un espia y produccion no lo veia, asi que la
            # unica pieza que decide toda la busqueda era la unica invisible.
            #
            # VA ANTES DE BUSCAR a proposito: si el motor se cae, el renglon
            # ya quedo escrito y se puede ver con que lo tumbaron.
            # EL RECORTE SUBE A 2.000 PORQUE ENTRAN DOS CAMPOS MAS, y este
            # renglon es lo UNICO que lee la vara de la interpretacion desde
            # produccion: un pedido cortado a la mitad se lee como un campo
            # que el modelo no declaro. Son caracteres de log, no tokens.
            log.info("motor_pedido", trace_id=trace_id, vuelta=vuelta + 1,
                     pedido=json.dumps(pidio, ensure_ascii=False)[:2000])
            # ── EL COTEJO, DESPUES DE LOGUEAR Y ANTES DE BUSCAR ────────────
            #
            # EL ORDEN ES LO UNICO QUE IMPORTA ACA, y la primera tanda con el
            # modelo real lo cazo el 22-sep. Con el saneo ANTES del log, el
            # `motor_pedido` salia ya corregido: la vara leia una consulta sin
            # el techo inventado y le daba la casilla por buena. M11 paso de
            # fallar 2 de 2 en produccion a dar 3 de 3 en banco sin que el
            # modelo hubiera cambiado nada.
            #
            # UN INSTRUMENTO QUE MIDE LA CORRECCION EN VEZ DEL MODELO ES PEOR
            # QUE NO TENER INSTRUMENTO, porque el numero sube solo y eso es
            # indistinguible de un avance. Es la misma enfermedad que el
            # umbral movido junto con el trabajo que lo hace pasar, que
            # CLAUDE.md llama la unica puerta por la que este metodo se
            # corrompe.
            #
            # ASI QUE EL LOG DICE LO QUE ESCRIBIO EL MODELO y estas dos lineas
            # arreglan lo que le llega al motor. Lo que el codigo corrigio se
            # lee aparte, en los renglones del cotejo de `motor_turno`.
            #
            # LAS DOS VAN ACA Y NO EN EL MOTOR porque el motor no mira el
            # mensaje del cliente, mira la consulta: cotejar lo declarado
            # contra lo dicho es trabajo de este borde, el unico lugar donde
            # estan las dos cosas.
            #
            # SANEAR VA ANTES DE REPONER: asi la memoria del turno solo guarda
            # condiciones ya saneadas y un techo inventado no puede volver a
            # entrar por la puerta de la reposicion.
            informe["umbrales_degradados"] += CO.sanear_umbrales(
                consultas, mensaje, _ordenables, trace_id)
            informe["condiciones_repuestas"] += CO.reponer_condiciones(
                consultas, condiciones_del_turno, trace_id)
            # LA PREGUNTA NO ES PREMISA, Y EL PRODUCTO QUE EL RENGLON NOMBRA
            # SE BUSCA (22-sep-2026). Las dos las midio la tanda de charlas y
            # el motivo entero esta en `cotejo`, secciones 6 y 7.
            CO.afirmas_que_preguntan(args.get("afirma"), mensaje, trace_id)
            _con = dict(args, consultas=consultas)
            CO.rescatar_nombrados(pidio["renglones"], _con, vistos or [],
                                  trace_id)
            consultas = _con["consultas"]
            CO.restringir_a_esos(mensaje, consultas,
                                 _lo_ultimo_nombrado(vistos, tienda_id),
                                 trace_id)
            # ── EL RENGLON ES COPIA, O NO LO ES ───────────────────────────
            #
            # Se mide sobre la PRIMERA llamada del turno y nada mas. La
            # pregunta que contesta es "de entrada, ¿transcribio o tradujo?",
            # y esa se contesta en la primera, igual que las casillas de
            # ausencia de la vara. En la vuelta 2 el modelo ya tiene su propia
            # lista delante, asi que copiarse a si mismo no dice nada nuevo.
            if not informe["renglones"] and pidio["renglones"]:
                copias, propios = CO.fidelidad(pidio["renglones"], mensaje)
                informe["renglones"] = len(pidio["renglones"])
                informe["renglones_copia"] = copias
                informe["renglones_propios"] = propios
                # EL RUBRO NOMBRADO Y NO PEDIDO, que es la omision hecha
                # afirmacion. Sale del cruce de los renglones COPIA contra
                # las categorias que las consultas fueron a buscar, y viaja
                # como aviso: el turno no escribe el texto, le pone el dato
                # delante al modelo para que pregunte por lo que falta.
                faltan = CO.rubros_sin_pedir(
                    pidio["renglones"], mensaje, consultas, _categorias)
                if faltan:
                    informe["rubros_sin_pedir"] = faltan
                    log.info("rubro_sin_pedir", trace_id=trace_id,
                             rubros=faltan[:4])
                    hallazgos.append(
                        "OJO: el cliente nombro " + ", ".join(faltan[:4])
                        + " y no lo buscaste. Si lo quiere en el pedido, "
                        "buscalo; si no estas seguro, preguntaselo.")
            # SE GUARDA ANTES DE BUSCAR, para que la MISMA vuelta que lo
            # declara ya lo use si ademas trae la cuenta.
            if args.get("reparto_pago"):
                reparto = list(args["reparto_pago"])
            # ── LA VUELTA QUE NO AGREGA NADA ──────────────────────────────
            #
            # Si esta llamada repite consultas ya servidas y no trae ninguna
            # otra casilla, no se vuelve a buscar: el retorno de arriba sigue
            # delante del modelo y este es el mismo. No baja la latencia —el
            # motor son 0 ms contra 3.000 del modelo— y lo que da es que el
            # mismo pedido no pueda volver con dos retornos distintos.
            if (CO.todo_repetido(consultas, pedidas)
                    and not any(args.get(k) for k in (
                        "temas", "compatibilidad", "afirma", "envios",
                        "criterio", "cuenta", "reparto_pago"))):
                informe["vueltas_sin_aporte"] += 1
                # SE ANOTA IGUAL, CON EL RETORNO VACIO: la consulta se pidio,
                # asi que tiene que seguir contando en `consultas` y en
                # `repetidas`. Saltear el conteo junto con la busqueda haria
                # que el numero de repetidas bajara justo cuando empezamos a
                # atajarlas, que es un instrumento midiendose a si mismo.
                _anotar(informe, consultas, pedidas, {})
                log.info("vuelta_sin_aporte", trace_id=trace_id,
                         vuelta=vuelta + 1, consultas=len(consultas))
                hallazgos.append(
                    "Eso ya lo buscaste y te lo devolvi mas arriba: usa ese "
                    "resultado. Si te falta algo, pedi OTRA cosa.")
                continue
            r = MT.buscar(consultas, tienda_id, trace_id,
                          temas=args.get("temas"),
                          compat=args.get("compatibilidad"),
                          afirma=args.get("afirma"),
                          envios=args.get("envios"),
                          localidad_previa=localidad_previa,
                          criterio=args.get("criterio"),
                          cuenta=args.get("cuenta"),
                          reparto_pago=reparto)
            _anotar(informe, consultas, pedidas, r)
            for f in MT.fichas_de(r):
                if str(f.get("id")) not in {str(x.get("id")) for x in fichas}:
                    fichas.append(f)
            for e in (r.get("envios") or {}).get("filas") or []:
                if e.get("monto_ars"):
                    envios[str(e["destino"])] = int(e["monto_ars"])
            if (r.get("cuenta") or {}).get("total_ars") is not None:
                cuenta = r["cuenta"]
            # LO QUE LA CASA TIENE ESCRITO TAMBIEN ES FUENTE (22-sep-2026). Es
            # la cuarta vez que este modulo aprende la misma leccion, ahora con
            # las politicas: "¿cuanto sale mandarlo a Rosario?" volvio con la
            # tarifa Y con el envio gratis desde $250.000, el modelo escribio
            # las dos y la guarda tiro la respuesta entera por la segunda.
            # Medido 2 de 2 en la tanda de charlas. Entra SOLO lo que volvio
            # de la fuente, no la consulta: un umbral que el modelo escribio
            # en su pedido no se legitima por haberlo pedido.
            for k in ("politicas", "criterio", "afirma", "compatibilidad",
                      "envios"):
                if r.get(k):
                    fuente_casa += "\n" + json.dumps(
                        r[k], ensure_ascii=False, default=str)
            hallazgos.append(
                # EL RECORTE ERA DE 900 Y CORTABA CONSULTAS ENTERAS. Medido
                # el 13-sep: un pedido abierto -"algo para jugar que no sea muy
                # caro"- mando cinco consultas que dan 959 caracteres, asi que
                # la quinta llegaba partida y el modelo no podia saber que ya
                # la habia pedido. Seis consultas es el tope, y con el tope
                # lleno entran holgadas en 1.400.
                # Y EL RENGLON NO VUELVE EN EL ECO, a proposito. Este
                # presupuesto ya se agrando una vez -de 900 a 1.400- porque
                # cortaba consultas enteras; meter la lista adelante volveria
                # a cortarlas, que es el defecto que se arreglo el 13-sep. El
                # modelo ya tiene sus renglones en su propia llamada.
                "Buscaste: " + json.dumps(
                    {k: v for k, v in pidio.items() if k != "renglones"},
                    ensure_ascii=False)[:1400]
                + "\nVolvio: " + _retorno_que_entra(r, trace_id))
        vuelta += 1
    informe["fichas"] = len(fichas)
    return {}, fichas, envios, cuenta, informe


# Cuanto del retorno le cabe al modelo en una vuelta. El numero es el de
# siempre; lo que cambio el 13-sep es COMO se recorta.
TOPE_RETORNO = 8000


def _retorno_que_entra(r: dict, trace_id: str = "") -> str:
    """El retorno como JSON, recortado SACANDO FILAS y no cortando la cadena.

    HASTA HOY ERA `json.dumps(r)[:8000]`, o sea que un retorno grande le
    llegaba al modelo partido al medio: la cadena queda sin cerrar, no es JSON,
    y la ultima ficha aparece mutilada —un precio a la mitad es un precio
    distinto—. Se destapo el 13-sep midiendo las specs: cinco notebooks con el
    mapa entero dan 8.837 caracteres y el corte caia adentro de una ficha.

    Sacar la ultima fila y DECIRLO es honesto: el modelo sabe que hay mas y
    puede pedir menos o afinar la consulta. Un JSON roto no le deja hacer nada,
    y encima parece completo.
    """
    entero = json.dumps(r, ensure_ascii=False)
    if len(entero) <= TOPE_RETORNO:
        return entero
    podado = json.loads(entero)
    sacadas = 0
    for res in podado.get("resultados") or []:
        while len(json.dumps(podado, ensure_ascii=False)) > TOPE_RETORNO \
                and len(res.get("filas") or []) > 1:
            res["filas"].pop()
            sacadas += 1
    if sacadas:
        podado["recortado"] = (
            f"se sacaron {sacadas} filas para que entre la respuesta; "
            f"pedi menos filas o afina la consulta si necesitas ver mas")
    salida = json.dumps(podado, ensure_ascii=False)
    log.info("retorno_recortado", trace_id=trace_id, filas_sacadas=sacadas,
             largo=len(salida), largo_entero=len(entero))
    # Si ni con una fila por consulta entra, recien ahi se corta la cadena: es
    # el ultimo recurso y queda anotado en el log de arriba.
    return salida[:TOPE_RETORNO]


def _senal(tipo: str, mensaje: str) -> dict:
    """La interpretacion MINIMA que pide el cierre: intencion y confianza.

    LA SEÑAL SALE DE DOS LADOS Y NINGUNO ES UNA HERRAMIENTA. Del TIPO que
    eligio el modelo -`intencion_compra` es literalmente eso-, y de la marca
    determinista sobre el mensaje, que ya existia y no depende de que el modelo
    se acuerde de nada. Con que uno de los dos diga compra, alcanza.
    """
    from app.core.leads import _RE_PIDE_COBRO
    if _RE_PIDE_COBRO.search(mensaje or ""):
        return {"intencion": "decision_compra", "confianza": 1.0,
                "motivo": "pide_datos_de_pago"}
    if str(tipo or "") == "intencion_compra":
        return {"intencion": "decision_compra", "confianza": 1.0,
                "motivo": "tipo_intencion_compra"}
    if str(tipo or "") in ("precio_simple", "precio_multiple", "envio_costo"):
        return {"intencion": "pregunta_especifica", "confianza": 0.9}
    return {"intencion": "exploracion", "confianza": 0.6}


async def _cerrar(conv, user_id, canal, tienda_id, mensaje, texto, trace_id,
                  senal) -> tuple:
    """CIERRE Y COBRO. La misma funcion de siempre: `leads` no se toco.

    El bot que contesta bien y no toma el pedido no sirve para vender, asi que
    esta etapa sobrevivio al apagon entera. Devuelve (texto, datos del cliente,
    si ya se pregunto el cierre).
    """
    from app.core.cierre import extraer_datos_cliente, extraer_determinista
    from app.core.leads import _RE_PIDE_COBRO, procesar_mensaje_para_lead
    datos_previos = conv.get("datos_cliente_parciales") or {}
    datos_turno: dict = {}
    try:
        datos_turno.update(extraer_determinista(mensaje))
        if senal.get("intencion") == "decision_compra":
            for k, v in extraer_datos_cliente(mensaje, trace_id).items():
                if v:
                    datos_turno[k] = v
    except Exception as e:  # noqa: BLE001 — el cierre nunca tumba el turno
        log.warning("respuesta_extractor_error", trace_id=trace_id,
                    error=str(e)[:120])
    datos = {**datos_previos, **datos_turno}
    pide_cobro = bool(_RE_PIDE_COBRO.search(mensaje or ""))
    meta: dict = {}
    if (texto and texto != settings.VERIFIKA_FALLBACK_MESSAGE) or pide_cobro:
        try:
            _, meta = await procesar_mensaje_para_lead(
                user_id, canal, tienda_id, mensaje, texto, trace_id,
                interpretacion=senal,
                presupuesto=conv.get("ultimo_presupuesto") or "",
                datos_turno=datos_turno, datos_previos=datos,
                presupuesto_nuevo=False,
                pregunta_cierre_hecha=bool(conv.get("pregunta_cierre_hecha")))
            rd = (meta.get("respuesta_directa") or "").strip()
            # EL COBRO NO SE ENTREGA DOS VECES: se compara por el DATO -el CBU
            # o el alias-, no por el texto.
            if rd and meta.get("accion") == "cobro_datos":
                try:
                    from app.core.pago import datos_transferencia
                    d = datos_transferencia(tienda_id) or {}
                    clave = str(d.get("cbu") or d.get("alias") or "")
                    if clave and clave in (texto or ""):
                        log.info("respuesta_cobro_ya_entregado", trace_id=trace_id)
                        rd = ""
                except Exception as e:  # noqa: BLE001
                    log.warning("respuesta_cobro_dedup_error", trace_id=trace_id,
                                error=str(e)[:120])
            if rd:
                base = (texto or "").strip()
                if not base or base == settings.VERIFIKA_FALLBACK_MESSAGE:
                    texto = rd
                elif base[:80] and base[:80] in rd:
                    texto = rd
                else:
                    texto = base + "\n\n" + rd
                log.info("respuesta_cierre", trace_id=trace_id,
                         accion=meta.get("accion"))
        except Exception as e:  # noqa: BLE001
            log.warning("respuesta_lead_error", trace_id=trace_id,
                        error=str(e)[:160])
    hecha = meta.get("accion") in ("pregunta_cierre", "pregunta_pendiente_cierre")
    return texto, datos, hecha


async def procesar_turno(user_id: str, raw_message: str, tienda_id: str,
                         canal: str, trace_id: str) -> str:
    """Un turno completo. Devuelve el texto para el cliente.

    Misma firma que el turno viejo: el orchestrator cambia una linea."""
    t0 = time.time()
    etapas: dict = {}
    from app.core import fuente as F
    from app.core import guardas_salida as gs
    from app.core.contexto_turno import set_current_tienda

    set_current_tienda(tienda_id)
    conv = get_conversation(user_id, tienda_id=tienda_id) or {}
    history = conv.get("history", []) or []
    negocio = gs.business_name(tienda_id)

    # ── 1. FUENTE ───────────────────────────────────────────────────────
    t = time.time()
    # LAS POLITICAS YA NO SE ADIVINAN ACA, y es el mapa 3 de la FICHA 50
    # (12-sep-2026). Las pide el modelo por el motor, con el campo `temas`, y
    # las certifica `fuente.politicas_de`. Lo que queda en esta etapa es lo que
    # NINGUNA busqueda puede contestar: el inventario del catalogo entero y el
    # envio, que no se razona porque sale del codigo postal.
    inventario = F.texto_inventario(tienda_id)
    # EL ENVIO YA NO SE EMPUJA ACA, y era el ultimo dato que llegaba por un
    # segundo camino (13-sep-2026). Lo pide el modelo por el motor, con el
    # lugar que nombro el cliente; el codigo sigue clasificando el texto a
    # provincia y sacando la tarifa de la tabla, que es la mitad que le toca.
    # El apagado de la politica del rango se mudo al motor, que es donde ahora
    # se ven las dos cosas.
    bloque = _bloque_fuente([], inventario)
    etapas["fuente"] = int((time.time() - t) * 1000)

    # ── 2. MODELO, QUE AHORA BUSCA EL ──────────────────────────────────
    #
    # LAS FICHAS YA NO LAS ELIGE EL CODIGO. Salen de lo que el modelo busco con
    # el motor. Es el cambio entero de la FICHA 50: el codigo no razona, asi
    # que no puede elegir que ponerle delante, y el catalogo entero no entra.
    t = time.time()
    memoria = _memoria_texto(conv)
    salida, fichas, envios, cuenta, motor = await _preguntar(
        _voz(negocio), memoria, history, raw_message, bloque, trace_id,
        tienda_id, localidad_previa=conv.get("ultima_localidad") or "",
        vigentes=(conv.get("preferencias_cliente") or {}).get("vigentes"),
        vistos=conv.get("productos_vistos") or [])
    etapas["modelo"] = int((time.time() - t) * 1000)
    # EL NUMERO DEL MOTOR, UN RENGLON POR TURNO. Sale SIEMPRE, haya buscado o
    # no: un turno que no busco es un dato, no un hueco en la serie. Lo agrega
    # `banco_pruebas/produccion.py` sobre la ventana que se pida, asi que el
    # numero se lee desde el issue 31 sin entrar a la consola de nadie.
    log.info("motor_turno", trace_id=trace_id,
             vueltas=motor["vueltas"], llamadas=motor["llamadas"],
             consultas=motor["consultas"], repetidas=motor["repetidas"],
             puntuales=motor["puntuales"],
             veredictos=motor["veredictos"][:12], filas=motor["filas"],
             rescates=motor["rescates"], vacios=motor["vacios"],
             sin_dato=motor["sin_dato"], campos=motor["campos"][:8],
             campos_tocados=len(motor["campos_tocados"]),
             correcciones=motor["correcciones"],
             fichas=motor["fichas"], temas=motor["temas"][:6],
             temas_sin_resolver=motor["temas_sin_resolver"][:4],
             compat=motor["compat"][:6],
             compat_sin_dato=motor["compat_sin_dato"][:4],
             # LO QUE EL CLIENTE DIO POR SENTADO, un veredicto por afirmacion.
             # El renglon que importa es cuantas `contradice`: cada una es una
             # premisa falsa que, sin esta boca, el bot le habria repetido al
             # cliente con sus propias palabras.
             afirma=motor["afirma"][:6],
             envios=motor["envios"][:4],
             envios_sin_clasificar=motor["envios_sin_clasificar"][:4],
             criterio=motor["criterio"][:6],
             criterio_sin_resolver=motor["criterio_sin_resolver"][:4],
             cuentas=motor["cuentas"],
             cuentas_sin_total=motor["cuentas_sin_total"],
             # LOS CINCO DEL COTEJO (22-sep-2026). `renglones_copia` sobre
             # `renglones` es el numero que dice si la casilla de
             # transcripcion transcribe; los otros cuatro son lo que el codigo
             # vio y corrigio solo, o sea el trabajo que antes no se hacia.
             renglones=motor["renglones"],
             renglones_copia=motor["renglones_copia"],
             renglones_propios=motor["renglones_propios"][:4],
             rubros_sin_pedir=motor["rubros_sin_pedir"][:4],
             umbrales_degradados=motor["umbrales_degradados"][:4],
             condiciones_repuestas=motor["condiciones_repuestas"][:4],
             vueltas_sin_aporte=motor["vueltas_sin_aporte"])
    if not motor["llamadas"]:
        # EL TERCER CANDADO DE LA FICHA 50: se mide cada turno que contesto sin
        # haber buscado. No se bloquea —la guarda de procedencia ya impide que
        # salga un numero que no vio—, se CUENTA, que es como sabemos si el
        # modelo usa el motor o lo esquiva.
        log.warning("turno_sin_buscar", trace_id=trace_id)

    texto = (salida.get("texto") or "").strip()
    if texto and not (salida.get("tipo") or "").strip():
        # EL TIPO VACIO NO TUMBA EL TURNO PERO SE CUENTA. Medido el 11-sep:
        # tres de seis turnos volvieron sin tipo, o sea que el modelo contesto
        # sin encasillar. El texto igual sale -el parseo tolera texto pelado-,
        # pero sin este renglon no habia forma de saber cuantas veces pasa.
        log.warning("tipo_vacio", trace_id=trace_id, largo=len(texto))
    if not texto:
        from app.core.guia_venta_prosa import mensaje as _prosa
        texto = _prosa("sobrecarga",
                       "Perdón, estoy con mucha demanda en este momento. "
                       "Probá de nuevo en un ratito y te respondo. 🙏")
        log.warning("respuesta_sin_modelo", trace_id=trace_id)
        informe = {}
    else:
        # ── 3. NUMEROS ──────────────────────────────────────────────────
        t = time.time()
        # LA MEMORIA TAMBIEN ES FUENTE, y sin este renglon el arreglo de arriba
        # no sirve de nada: el precio de lo ya mostrado viaja al modelo, el
        # modelo lo copia como se le pide, y la guarda lo llama invento porque
        # solo miraba el bloque. Es LA MISMA leccion que este archivo ya
        # aprendio el 11-sep con el inventario, aplicada al otro bloque que
        # viaja aparte: lo que se le pone delante al modelo es fuente, TODO.
        texto, informe = N.llenar(
            texto, fichas, trace_id,
            fuente_texto=(bloque + "\n" + memoria + "\n"
                          + str(salida.get("fuente_casa") or "")),
            # LA TARIFA SALE DE LO QUE EL MODELO PIDIO POR EL MOTOR. Un
            # `{{envio}}` pelado usa la unica que volvio; con varios destinos
            # cada hueco trae la suya por `{{envio:<destino>}}`, que es lo que
            # evita escribir el mismo monto en los tres renglones.
            envio_monto=(list(envios.values())[0] if len(envios) == 1
                         else None),
            envios=envios,
            # EL TOTAL YA CALCULADO, Y ES EL CAMBIO DEL 14-sep. Hasta hoy
            # `{{total}}` lo resolvia `numeros` sumando las cifras que ya
            # estaban escritas en el mensaje, y esa suma no puede conocer el
            # descuento por transferencia ni el reparto entre medios de pago.
            # Ahora el total lo hace `calculadora` en el retorno, ANTES de
            # redactar: el modelo lo escribe con el numero en la mano, y si
            # igual deja el hueco, el hueco se llena con ESE total y no con
            # una suma distinta.
            cuenta=cuenta)
        etapas["numeros"] = int((time.time() - t) * 1000)
        if informe.get("inventada"):
            # LA RESPUESTA CON PLATA INVENTADA NO SALE. No hay forma honesta de
            # corregirla renglon por renglon: el numero ya contamino la frase.
            texto = settings.VERIFIKA_FALLBACK_MESSAGE
        texto = gs.con_saludo_inicial(gs.sin_saludo_del_modelo(texto), negocio) \
            if not history else gs.sin_saludo_del_modelo(texto)

    # ── 4. CIERRE Y COBRO ───────────────────────────────────────────────
    t = time.time()
    texto, datos_cliente, cierre_hecho = await _cerrar(
        conv, user_id, canal, tienda_id, raw_message, texto, trace_id,
        _senal(salida.get("tipo") or "", raw_message))
    etapas["cierre"] = int((time.time() - t) * 1000)

    # ── 5. MEMORIA ──────────────────────────────────────────────────────
    t = time.time()
    history = history + [{"role": "user", "content": raw_message},
                         {"role": "assistant", "content": texto}]
    resumen = conv.get("summary", "") or ""
    viejos = history[:-(settings.HISTORY_LIMIT * 2)]
    if viejos:
        try:
            from app.core.memoria_larga import actualizar_resumen
            resumen = await actualizar_resumen(resumen, viejos, trace_id)
        except Exception as e:  # noqa: BLE001 — la memoria nunca tumba el turno
            log.warning("respuesta_memoria_error", trace_id=trace_id,
                        error=str(e)[:120])
    history = history[-(settings.HISTORY_LIMIT * 2):]
    # LO QUE SE RECUERDA ES LO QUE EL CLIENTE LEYO, EN EL ORDEN EN QUE LO LEYO
    # (22-sep-2026). Hasta hoy se guardaban TODAS las fichas que volvian de
    # buscar —hasta ocho por consulta— al final de la lista y solo si eran
    # nuevas, y la memoria mostraba las OCHO MAS VIEJAS diciendo "el ultimo es
    # el mas reciente". Pasados ocho productos, "ese" apuntaba al equivocado y
    # "el segundo" no tenia orden de donde salir. Ahora lo nombrado en la
    # respuesta va al final, en su orden, marcado con el turno.
    previos = conv.get("productos_vistos") or []
    vistos = _vistos_al_dia(
        previos, fichas, texto,
        max((int(p.get("turno") or 0) for p in previos), default=0) + 1,
        tienda_id)
    # EL DESTINO DE LA CHARLA LO ESCRIBE QUIEN LO RESOLVIO. Habia una SEGUNDA
    # resolucion aca -otra llamada a `geo`, con otro criterio que el del motor
    # de envio- y guardaba un codigo postal pelado. Ahora se guarda el destino
    # que cotizo de verdad, ya nombrado con la palabra: el turno siguiente lo
    # vuelve a clasificar sin depender de que el cliente lo repita.
    # SE GUARDA LO ESTABLE, SE MUESTRA LO QUE EL CLIENTE DIJO. Son dos cosas
    # distintas y desde el 12-sep tienen campo propio: lo que vuelve a
    # clasificar solo dentro de tres turnos es la provincia, no "Posadas".
    # LO QUE SE GUARDA ES LA PROVINCIA, no la palabra del cliente: dentro de
    # tres turnos tiene que volver a clasificar sola, y "Los Condores" no lo
    # hace. Se resuelve del lado del codigo justamente para que la provincia no
    # viaje al modelo, que es lo que hacia que le contestara "misiones" al que
    # pidio a Posadas.
    previa = conv.get("ultima_localidad") or ""
    primero = next(iter(envios), "")
    localidad = (F.estable_de(primero, previa) or primero or previa) \
        if primero else previa
    # LA CUENTA SOBREVIVE AL TURNO. Los dos campos existian en la memoria desde
    # siempre y no los escribia NADIE: `leads` lee `ultimo_presupuesto` para
    # decidir si puede cerrar, y como venia vacio cortaba siempre por "no
    # cerrar sin precio mostrado". Se escriben solo cuando la cuenta SALIO; una
    # cuenta que no se pudo hacer no pisa la anterior, porque la anterior sigue
    # siendo lo ultimo que el cliente vio.
    presupuesto = None
    carrito = None
    if (cuenta or {}).get("total_ars") is not None:
        presupuesto = str(cuenta.get("detalle") or "")[:900] or None
        carrito = cuenta.get("items") or None
    try:
        save_conversation(user_id, history, resumen, tienda_id=tienda_id,
                          estado_conversacion="en_curso",
                          productos_vistos=vistos[-20:],
                          ultima_localidad=localidad or None,
                          ultimo_presupuesto=presupuesto,
                          carrito_vigente=carrito,
                          datos_cliente_parciales=datos_cliente,
                          pregunta_cierre_hecha=cierre_hecho,
                          # EL CRITERIO QUE SIGUE VALIENDO. Solo se pisa si
                          # el turno paso por el modelo: un turno caido no
                          # borra lo que el cliente excluyo.
                          preferencias_cliente=(
                              {"vigentes": _vigentes_para_guardar(
                                  salida["vigentes"])}
                              if "vigentes" in salida else None))
    except Exception as e:  # noqa: BLE001
        log.warning("respuesta_save_error", trace_id=trace_id, error=str(e)[:150])
    etapas["memoria"] = int((time.time() - t) * 1000)

    log.info("turno_ok", trace_id=trace_id,
             latency_ms=int((time.time() - t0) * 1000), etapas=etapas,
             tipo=salida.get("tipo") or "", largo=len(texto or ""),
             fichas=len(fichas), politicas=len(motor["temas"]),
             envio_destinos=list(envios)[:3],
             envio_montos=list(envios.values())[:3],
             cuenta_total=(cuenta or {}).get("total_ars"),
             cuenta_final=(cuenta or {}).get("total_final_ars"),
             huecos_llenos=len((informe or {}).get("llenos") or []),
             huecos_sin_dato=len((informe or {}).get("sin_dato") or []),
             plata_inventada=len((informe or {}).get("inventada") or []))
    return texto
