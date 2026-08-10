"""
LOS INVARIANTES — lo que tiene que valer en CUALQUIER conversacion.

POR QUE EXISTE (Martin, 10-ago-2026). "En cada prueba en real aparecen nuevos
errores" — y es cierto, y no era indisciplina. Es una propiedad del metodo: un
test con respuesta esperada solo encuentra el error que alguien ANTICIPO. Los
tres numeros del repo miden el aparato contra casos escritos a mano, y el
cliente real no saca sus preguntas de esa lista.

LAS TRES CEGUERAS QUE SE VIERON EL 10-AGO, cada una con su prueba:

  1. CEGUERA DE ESCENARIOS. Las reglas nuevas del componedor se dispararon
     CERO veces en los 176 turnos de las 13 charlas grabadas, y en la charla
     REAL de Martin cortaron 500 caracteres por turno. Ninguna charla grabada
     tenia un cliente confirmando en varios turnos sin cambiar nada, que es lo
     que hace un cliente de verdad.
  2. CEGUERA DE COSTURAS. El error de plata -cobrarle $225.000 a un cliente
     que debia $131.625- vivia ENTRE dos modulos: la calculadora repartia bien
     y el cobro leia el total. Los dos modulos tenian test y los dos estaban en
     verde. Ningun test cruzaba la costura, y el mapa la daba por cubierta
     porque cuenta funciones tocadas, no datos que cruzan.
  3. CEGUERA DE ANTICIPACION. La alucinacion de los "8000 DPI" paso con el
     tablero en verde porque la guarda la contaba como verificada sin haber
     verificado nada.

LA VUELTA DE TUERCA, y es todo el diseño: **estas reglas no saben cual es la
respuesta correcta**. No comparan contra un texto esperado. Afirman propiedades
que tienen que valer SIEMPRE — que la cuenta cierre, que lo cobrado sea lo
facturado, que nada se diga dos veces— y por eso se pueden correr sobre una
conversacion que nadie escribio: una charla grabada, una charla simulada, o la
charla REAL que Martin tuvo hace diez minutos.

Ese es el punto: **convierte cualquier conversacion en un test, sin que nadie
escriba la respuesta esperada.** Es lo que faltaba.

EL NUCLEO ES PURO A PROPOSITO. Ninguna funcion de aca importa `app.*`. Reciben
texto y datos sueltos y devuelven violaciones. El adaptador que sabe de Verifika
-de donde sale el catalogo, de donde salen las conversaciones- vive afuera, en
`produccion.py`. Martin pregunto si esto podria ser un producto aparte: si algun
dia lo es, esto se MUDA, no se reescribe. Hoy no se saca, porque un sistema de
invariantes sin un sistema real al que enchufarse no vale nada.

USO:
    from banco_pruebas.invariantes import revisar
    fallas = revisar(mensaje, anterior=mensaje_anterior)
    # -> [{'regla': 'la_cuenta_cierra', 'detalle': 'subtotal ...'}]
"""
import re
import unicodedata

# ── EL FORMATO DE LA CUENTA, que lo escribe el CODIGO y es estable ──────────
# "- 2x Mouse Genius DX-110 Negro: $8.500 c/u = $17.000"
_RE_ITEM = re.compile(
    r"^\s*-\s*(?P<cant>\d+)\s*x\s+(?P<nombre>.+?):\s*\$(?P<unit>[\d\.]+)\s*"
    r"c/u\s*=\s*\$(?P<sub>[\d\.]+)\s*$", re.MULTILINE)
_RE_SUBTOTAL = re.compile(r"^\s*subtotal\s*:\s*\$([\d\.]+)\s*$",
                          re.IGNORECASE | re.MULTILINE)
_RE_TOTAL = re.compile(r"^\s*total\s*:\s*\$([\d\.]+)\s*$",
                       re.IGNORECASE | re.MULTILINE)
_RE_TOTAL_FINAL = re.compile(r"^\s*total\s+final\s*:\s*\$([\d\.]+)\s*$",
                             re.IGNORECASE | re.MULTILINE)
# "- transferencia (65%): $146.250 - 10% descuento = $131.625"
_RE_SPLIT = re.compile(
    r"^\s*-\s*(?P<medio>transferencia|mercado ?pago)\s*\(\s*(?P<pct>[\d.,]+)\s*%\s*\)"
    r"\s*:\s*(?P<montos>.*\S)\s*$", re.IGNORECASE | re.MULTILINE)
# Los extras entre el subtotal y el total: envio, descuento, sena.
_RE_EXTRA = re.compile(
    r"^\s*(?!subtotal|total)(?P<etiqueta>[^:\n]{2,40}?)\s*:\s*"
    r"(?P<signo>-?)\s*\$?(?P<monto>[\d\.]+)\s*(?P<cola>\(pago parcial\))?\s*$",
    re.IGNORECASE | re.MULTILINE)
_RE_PLATA = re.compile(r"\$\s*([\d\.]+)")
_RE_REPARTO = re.compile(r"^\s*-\s*A\s+(?P<destino>[^:]+):\s*(?P<carga>.+?)\s*$",
                         re.MULTILINE)
_RE_ETIQUETA_ATADURA = re.compile(r"</?d(\s|>)", re.IGNORECASE)


def _n(s) -> str:
    s = unicodedata.normalize("NFKD", re.sub(r"\s+", " ", str(s or "")).strip().lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def _plata(s) -> int:
    return int(str(s).replace(".", ""))


def _falla(regla, detalle):
    return {"regla": regla, "detalle": detalle}


# ── LOS INVARIANTES ─────────────────────────────────────────────────────────
def cuenta_cierra(mensaje: str) -> list:
    """La aritmetica de la cuenta, que es la unica plata que el cliente ve.

    Tres cosas, y las tres son sumas que no admiten opinion:
      - cada renglon: cantidad x precio unitario = subtotal del renglon;
      - los renglones suman el Subtotal;
      - las partes del pago dividido suman el Total final.

    NO se verifica "subtotal + extras = total" con los extras leidos del texto:
    un descuento porcentual y una seña se escriben en el mismo formato y
    restan o no segun el concepto, y adivinarlo desde el texto seria inventar
    una segunda cuenta. La cuenta la hace la calculadora; aca se controla lo
    que se puede controlar sin volver a calcularla."""
    fallas = []
    items = list(_RE_ITEM.finditer(mensaje or ""))
    for m in items:
        cant, unit, sub = int(m["cant"]), _plata(m["unit"]), _plata(m["sub"])
        if cant * unit != sub:
            fallas.append(_falla(
                "renglon_no_multiplica",
                f"{m['nombre'].strip()}: {cant} x ${unit:,} deberia dar "
                f"${cant * unit:,} y dice ${sub:,}".replace(",", ".")))
    sub_m = _RE_SUBTOTAL.search(mensaje or "")
    if items and sub_m:
        suma = sum(_plata(m["sub"]) for m in items)
        if suma != _plata(sub_m.group(1)):
            fallas.append(_falla(
                "subtotal_no_suma",
                f"los renglones suman ${suma:,} y el Subtotal dice "
                f"${_plata(sub_m.group(1)):,}".replace(",", ".")))
    partes = partes_del_pago(mensaje)
    tf = _RE_TOTAL_FINAL.search(mensaje or "")
    if partes and tf:
        suma = sum(partes.values())
        if suma != _plata(tf.group(1)):
            fallas.append(_falla(
                "el_pago_dividido_no_suma_el_total",
                f"las partes suman ${suma:,} y el Total final dice "
                f"${_plata(tf.group(1)):,}".replace(",", ".")))
    return fallas


def partes_del_pago(mensaje: str) -> dict:
    """{medio: monto final} del bloque de pago dividido. {} si no hay."""
    out = {}
    for m in _RE_SPLIT.finditer(mensaje or ""):
        plata = _RE_PLATA.findall(m["montos"])
        if plata:
            out[_n(m["medio"])] = _plata(plata[-1])
    return out


def lo_cobrado_es_lo_facturado(mensaje: str) -> list:
    """EL INVARIANTE QUE HABRIA CAZADO EL ERROR DEL 10-AGO EN LA PRIMERA
    CORRIDA, sin que nadie lo anticipara.

    Al cliente le llego un pago dividido 65/35 y, abajo, los datos para
    transferir con **"Monto: $225.000"**: el total ENTERO por transferencia,
    cuando por esa via le tocaban $131.625. Un 71% de mas, y mas que el total
    final. Ningun test lo veia porque cada modulo estaba bien por separado.

    La propiedad es obvia una vez escrita: **si el mensaje dice cuanto hay que
    pagar por una via, ese numero tiene que ser el que la cuenta le asigna a esa
    via.** No hace falta saber cual es la respuesta correcta para exigirla."""
    fallas = []
    partes = partes_del_pago(mensaje)
    m = re.search(r"^\s*monto\s*:\s*\$([\d\.]+)\s*$", mensaje or "",
                  re.IGNORECASE | re.MULTILINE)
    if not m:
        return fallas
    pedido = _plata(m.group(1))
    if partes:
        esperado = next((v for k, v in partes.items() if "mercado" not in k), None)
        if esperado is not None and pedido != esperado:
            fallas.append(_falla(
                "cobra_distinto_de_lo_que_factura",
                f"pide transferir ${pedido:,} y la cuenta le asigna a esa via "
                f"${esperado:,}".replace(",", ".")))
        return fallas
    tf = _RE_TOTAL_FINAL.search(mensaje or "") or _RE_TOTAL.search(mensaje or "")
    if tf and pedido != _plata(tf.group(1)):
        fallas.append(_falla(
            "cobra_distinto_del_total",
            f"pide transferir ${pedido:,} y el total dice "
            f"${_plata(tf.group(1)):,}".replace(",", ".")))
    return fallas


def un_solo_total_por_concepto(mensaje: str) -> list:
    """Dos "Total:" distintos en un mensaje es una contradiccion de plata. Que
    convivan "Total" y "Total final" es correcto -uno es antes del descuento-;
    que haya dos "Total:" con numeros distintos, no."""
    vistos = {_plata(x) for x in _RE_TOTAL.findall(mensaje or "")}
    if len(vistos) > 1:
        return [_falla("dos_totales_distintos",
                       "el mensaje dice " + " y ".join(f"${v:,}".replace(",", ".")
                                                       for v in sorted(vistos)))]
    return []


def el_reparto_cubre_el_pedido(mensaje: str) -> list:
    """Si hay reparto por destino, las unidades repartidas tienen que ser las
    de la cuenta. El 9-ago le llego a Martin un presupuesto de SEIS articulos
    con el reparto de UNO: el componedor se habia comido dos destinos creyendo
    que repetian."""
    items = list(_RE_ITEM.finditer(mensaje or ""))
    filas = list(_RE_REPARTO.finditer(mensaje or ""))
    if not items or not filas:
        return []
    en_cuenta = sum(int(m["cant"]) for m in items)
    repartidas = 0
    for f in filas:
        n = re.findall(r"(\d+)\s*x", f["carga"])
        repartidas += sum(int(x) for x in n) if n else len(
            [p for p in f["carga"].split(",") if p.strip()])
    if repartidas != en_cuenta:
        return [_falla("el_reparto_no_cubre_el_pedido",
                       f"la cuenta tiene {en_cuenta} unidades y el reparto "
                       f"menciona {repartidas}")]
    return []


def nada_se_dice_dos_veces(mensaje: str) -> list:
    """La prioridad 2 de Martin, escrita como propiedad: sin repetir
    informacion ni datos. Un renglon largo calcado dentro del mismo mensaje, o
    el bloque de la cuenta dos veces, es repeticion demostrable."""
    fallas, vistas = [], {}
    for linea in (mensaje or "").splitlines():
        clave = _n(linea)
        if len(clave) < 25:
            continue
        # EL RENGLON DE LA CUENTA QUEDA AFUERA, y no es una excepcion floja: el
        # MISMO producto puede venir partido en dos destinos, y ahi el renglon
        # calcado es plata correcta, no una coletilla. Distinguir un caso del
        # otro por el TEXTO es imposible; por la ARITMETICA es trivial, y de eso
        # ya se ocupa `subtotal_no_suma`, que en el caso legitimo cierra y en el
        # duplicado no. Cada cosa la decide quien puede probarla.
        if _RE_ITEM.match(linea):
            continue
        vistas[clave] = vistas.get(clave, 0) + 1
    repetidas = [k for k, v in vistas.items() if v > 1]
    if repetidas:
        fallas.append(_falla("renglon_repetido_en_el_mensaje",
                             f"{len(repetidas)} renglones calcados, "
                             f"p.ej. '{repetidas[0][:60]}'"))
    if len(_RE_SUBTOTAL.findall(mensaje or "")) > 1:
        fallas.append(_falla("la_cuenta_dos_veces",
                             "el bloque del presupuesto aparece mas de una vez"))
    return fallas


def no_repite_el_mensaje_anterior(mensaje: str, anterior: str) -> list:
    """Lo que el cliente acaba de leer no se le manda de nuevo. Se mide sobre
    el BLOQUE de la cuenta, que es donde se vio: en la charla del 10-ago la
    cuenta salio calcada dos turnos seguidos, 550 caracteres cada vez, el 45% y
    el 49% del mensaje."""
    if not (anterior or "").strip():
        return []
    def bloque(t):
        return _n(" ".join(l for l in (t or "").splitlines()
                           if _RE_ITEM.match(l) or _RE_SUBTOTAL.match(l)
                           or _RE_TOTAL.match(l) or _RE_TOTAL_FINAL.match(l)
                           or _RE_SPLIT.match(l) or _RE_REPARTO.match(l)))
    a, b = bloque(mensaje), bloque(anterior)
    if a and a == b and len(a) > 200:
        return [_falla("reestampa_la_cuenta_sin_cambios",
                       f"{len(a)} caracteres de cuenta identicos al turno anterior")]
    return []


def sin_etiquetas_ni_marcas_internas(mensaje: str) -> list:
    """Nada de la maquinaria puede llegarle al cliente. Las etiquetas de la
    atadura de prosa son lo unico que el sistema le pide al modelo que escriba
    y que NUNCA puede salir: si se fugan, el cliente lee `<d MOU0023>`."""
    if _RE_ETIQUETA_ATADURA.search(mensaje or ""):
        return [_falla("etiqueta_interna_fugada",
                       "el mensaje lleva una etiqueta <d ...> de la atadura")]
    return []


def sin_encabezado_sin_nada_abajo(mensaje: str) -> list:
    """Un titulo que promete una lista y no muestra ninguna. Le paso a Martin
    el 10-ago: "Reparto de los envios:" y abajo, nada."""
    lineas = (mensaje or "").splitlines()
    for i, l in enumerate(lineas):
        if not re.match(r"^\s*[^\n]{3,60}:\s*$", l):
            continue
        sig = next((x for x in lineas[i + 1:] if x.strip()), "")
        if not sig or re.match(r"^\s*[^\n]{3,60}:\s*$", sig):
            return [_falla("encabezado_huerfano",
                           f"'{l.strip()}' no tiene nada abajo")]
    return []


def productos_del_catalogo(mensaje: str, vocabulario: set) -> list:
    """Todo producto que se cotiza tiene que existir en el catalogo. El
    `vocabulario` es el conjunto de nombres reales; si no se pasa, no se
    controla -el nucleo no sabe de donde sale el catalogo, eso es del
    adaptador-."""
    if not vocabulario:
        return []
    conocidos = {_n(v) for v in vocabulario}
    fallas = []
    for m in _RE_ITEM.finditer(mensaje or ""):
        nombre = _n(m["nombre"])
        if not any(nombre in c or c in nombre for c in conocidos):
            fallas.append(_falla("producto_cotizado_que_no_existe",
                                 f"'{m['nombre'].strip()}' no esta en el catalogo"))
    return fallas


# ── LA PUERTA ───────────────────────────────────────────────────────────────
TODOS = (
    "cuenta_cierra",
    "lo_cobrado_es_lo_facturado",
    "un_solo_total_por_concepto",
    "el_reparto_cubre_el_pedido",
    "nada_se_dice_dos_veces",
    "no_repite_el_mensaje_anterior",
    "sin_etiquetas_ni_marcas_internas",
    "sin_encabezado_sin_nada_abajo",
    "productos_del_catalogo",
)


def revisar(mensaje: str, anterior: str = "", vocabulario: set = None) -> list:
    """Todas las propiedades sobre UN mensaje. Devuelve la lista de
    violaciones; vacia es que paso.

    NO decide si la respuesta es la correcta -eso no se puede sin saber la
    pregunta-. Decide si el mensaje se contradice a si mismo, contradice a la
    cuenta, repite lo ya dicho o deja escapar algo interno. Todas cosas que
    NINGUNA respuesta correcta hace."""
    fallas = []
    fallas += cuenta_cierra(mensaje)
    fallas += lo_cobrado_es_lo_facturado(mensaje)
    fallas += un_solo_total_por_concepto(mensaje)
    fallas += el_reparto_cubre_el_pedido(mensaje)
    fallas += nada_se_dice_dos_veces(mensaje)
    fallas += no_repite_el_mensaje_anterior(mensaje, anterior)
    fallas += sin_etiquetas_ni_marcas_internas(mensaje)
    fallas += sin_encabezado_sin_nada_abajo(mensaje)
    fallas += productos_del_catalogo(mensaje, vocabulario or set())
    return fallas


def revisar_charla(mensajes: list, vocabulario: set = None) -> list:
    """Los invariantes sobre una conversacion entera. `mensajes` es la lista de
    respuestas del bot en orden. Devuelve las violaciones con el turno."""
    fallas, anterior = [], ""
    for i, m in enumerate(mensajes, 1):
        for f in revisar(m, anterior=anterior, vocabulario=vocabulario):
            fallas.append({**f, "turno": i})
        anterior = m
    return fallas
