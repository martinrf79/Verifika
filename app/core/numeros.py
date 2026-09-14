"""LOS DOS NUMEROS QUE EXISTEN — el precio de un producto y el costo de un envio.

EL MODELO ESCRIBE EL PRECIO, copiado de la ficha que el codigo le puso
delante. Lo que NO puede escribir es un numero que la fuente no tenga, y eso lo
decide este modulo, no el prompt.

Los dos numeros que ninguna ficha tiene van como hueco y los pone el codigo:

    {{envio}}       la tarifa del destino, ya cotizada por el motor
    {{total}}       la suma, que el modelo no puede hacer de cabeza

(y siguen andando `{{precio}}` y `{{precio:ID}}`, por si el modelo no tiene el
numero a mano)

Dos reglas y ninguna excepcion:

  1. UN HUECO QUE NO RESUELVE NO SE INVENTA. Se dice que no se tiene el dato y
     queda el renglon `hueco_sin_dato` en el log. Es la misma regla de la FAQ
     curada: una respuesta a medias es mejor que una inventada.
  2. UN NUMERO QUE NO ESTA EN LA FUENTE NO SALE, y se lleva puesta la
     respuesta entera. No importa si es un precio, un plazo o una spec: si el
     modelo lo escribio y la fuente no lo tiene, lo invento. El codigo siempre
     puede invalidar lo que dijo el modelo.
"""
import re

from app.logger import get_logger

log = get_logger(__name__)

_HUECO = re.compile(r"\{\{\s*(precio|envio|total)\s*(?::\s*([^}]*))?\s*\}\}")

# UNA CIFRA GRANDE: con signo pesos, con puntos de mil, o cuatro digitos para
# arriba. No es solo plata a proposito: `1920x1080` y `3200 MHz` tambien caen
# aca, y esta bien que caigan. La regla no es "de donde sale la plata" sino
# "de donde sale el numero", y la respuesta es siempre la misma: de la fuente.
# Lo corto -"24 meses", "2 unidades", "16GB"- no entra: no hay nada que
# inventar en un numero que el cliente puede verificar de un vistazo.
#
# EL PISO DEL NUMERO PELADO ES CUATRO DIGITOS, y se probo en tres. Con tres,
# "100% original" y "en 3 a 5 dias, zona 100" se llevaban puesta la respuesta
# entera por un numero que no es un dato. Con cuatro no se pierde nada que
# importe: el precio mas barato del catalogo tiene cuatro digitos, y un monto
# de tres escrito como plata igual cae por el signo pesos o por los puntos.
# El borde se mira por DIGITO y no por palabra: con `\b`, "2560x1440" no era
# dos numeros sino ninguno, porque entre el 0 y la x no hay borde de palabra.
# Una resolucion inventada pasaba entera.
_CIFRA = re.compile(r"\$\s?\d[\d.]*"
                    r"|(?<!\d)\d{1,3}(?:\.\d{3})+(?!\d)"
                    r"|(?<!\d)\d{4,}(?!\d)")
_PLATA = _CIFRA  # nombre viejo, por si algo lo importa

SIN_DATO = "ese dato no lo tengo a mano"


def _money(n) -> str:
    return "$" + f"{int(round(float(n))):,}".replace(",", ".")


def _digitos(texto: str) -> set:
    """Todas las corridas de tres digitos o mas que hay en un texto. Es como se
    compara: sin puntos, sin signo y sin unidad, asi `$8.500`, `8500` y `8.500`
    son el mismo numero."""
    return {m for m in re.findall(r"\d{3,}", re.sub(r"[.,]", "", texto or ""))}


def _precio_de(fichas: list, referencia: str):
    """El precio de la ficha que el modelo nombro. None si no se puede saber
    cual es: con dos fichas y sin referencia, elegir seria adivinar."""
    con_precio = [f for f in (fichas or []) if f.get("precio_ars")]
    ref = (referencia or "").strip().lower()
    if ref:
        for f in con_precio:
            if ref == str(f.get("id") or "").lower():
                return f
        for f in con_precio:
            if ref in str(f.get("nombre") or "").lower():
                return f
        return None
    return con_precio[0] if len(con_precio) == 1 else None


# EL ENVIO NO SE COTIZA ACA, y es el arreglo del 11-sep con el destino que le
# puso el 13-sep. Lo resuelve la boca de envio, que hoy pide el modelo por el
# motor, y el monto llega hecho. Lo que habia era una SEGUNDA resolucion de
# destino que ademas armaba el subtotal del umbral de envio gratis sumando
# TODAS las fichas que devolvio la busqueda: mostrar cinco notebooks regalaba
# el envio. Un dato, un lugar.


def _envio_de(envios: dict, referencia: str):
    """La tarifa del destino que el modelo nombro en el hueco, o None.

    Se compara NORMALIZADO y por contenido en las dos direcciones: el modelo
    puede escribir `{{envio:Cordoba}}` donde el bloque decia `cordoba`, o
    `{{envio:Cordoba capital}}` donde decia `cordoba`. Lo que no se hace es
    elegir por parecido cuando hay dos candidatos: ahi no se adivina, sale que
    no se tiene el dato, que es la misma regla que gobierna el precio."""
    ref = _norm_destino(referencia)
    if not ref or not envios:
        return None
    exacto = [m for d, m in envios.items() if _norm_destino(d) == ref]
    if len(exacto) == 1:
        return exacto[0]
    parecidos = [m for d, m in envios.items()
                 if ref in _norm_destino(d) or _norm_destino(d) in ref]
    return parecidos[0] if len(parecidos) == 1 else None


def _norm_destino(s) -> str:
    import unicodedata
    t = unicodedata.normalize("NFKD", str(s or "").lower().strip())
    return "".join(c for c in t if not unicodedata.combining(c))


def llenar(texto: str, fichas: list, trace_id: str = "",
           fuente_texto: str = "", envio_monto: int | None = None,
           envios: dict | None = None, cuenta: dict | None = None) -> tuple:
    """(texto con los numeros puestos, informe). El informe dice que huecos se
    llenaron, cuales quedaron sin dato y si hubo plata inventada.

    `fuente_texto` es TODO lo que se le puso delante al modelo, tal cual viajo:
    inventario, politicas y envio. La guarda compara contra eso y no contra una
    lista de piezas, asi una fuente nueva no se olvida de sumarse a la
    procedencia -paso el 11-sep con el inventario y tiro una respuesta
    correcta-.

    `envio_monto` es la tarifa cuando volvio UNA sola del motor. None cuando
    no volvio ninguna o volvieron varias: entonces el hueco pelado dice que no
    se tiene el dato, nunca un numero, porque con dos tarifas delante elegir
    seria adivinar.

    `envios` es {destino: tarifa}, lo que el modelo pidio por la boca de envio,
    y resuelve `{{envio:cordoba}}`. Con un solo destino los dos caminos son el
    mismo: la lista trae uno.

    `cuenta` es el TOTAL que `calculadora` ya calculo en el retorno, antes de
    que el modelo redactara. Hace dos cosas, y las dos son la misma regla de
    procedencia: el modelo PUEDE escribir ese total -y entonces esto es lo que
    impide que la guarda lo llame invento-, y si igual deja el hueco,
    `{{total}}` se llena con ESE total y no con una suma del texto. Con un
    reparto de pago manda `total_final_ars`, que es el unico numero que el
    cliente va a pagar de verdad.
    """
    informe = {"llenos": [], "sin_dato": [], "montos": [], "inventada": []}
    usados: list = []

    def _pone(m):
        clase, ref = m.group(1), (m.group(2) or "")
        if clase == "precio":
            f = _precio_de(fichas, ref)
            if not f:
                informe["sin_dato"].append("precio" + (f":{ref}" if ref else ""))
                return SIN_DATO
            monto = int(f["precio_ars"])
            usados.append(monto)
            informe["llenos"].append("precio")
            informe["montos"].append(monto)
            return _money(monto)
        if clase == "envio":
            # EL HUECO CON DESTINO, `{{envio:cordoba}}` (12-sep-2026). Con
            # varios destinos en un mensaje, un `{{envio}}` pelado no dice a
            # cual de las tarifas se refiere el renglon, asi que el codigo
            # escribia la misma dos veces. El destino que el modelo nombra en
            # el hueco es el que `fuente` ya cotizo y le puso delante.
            monto = _envio_de(envios, ref) if ref else envio_monto
            if monto is None:
                informe["sin_dato"].append("envio" + (f":{ref}" if ref else ""))
                return SIN_DATO
            usados.append(monto)
            informe["llenos"].append("envio")
            informe["montos"].append(monto)
            return _money(monto)
        # El total se resuelve en la SEGUNDA pasada, cuando ya estan puestos
        # los precios y el envio: sumar antes daria la mitad de la cuenta.
        return "\x00TOTAL\x00"

    salida = _HUECO.sub(_pone, texto or "")

    # EL HUECO QUE EL MODELO COPIO DEL MOLDE. `{{producto}}` y los demas no son
    # de plata: ahi tenia que escribir la palabra de la ficha. Si quedo crudo,
    # sale el aviso y el hueco no viaja al cliente con las llaves puestas.
    crudos = re.findall(r"\{\{[^}]*\}\}", salida)
    if crudos:
        informe["crudos"] = crudos
        log.warning("hueco_crudo", trace_id=trace_id, huecos=crudos[:5])
        salida = re.sub(r"\s*\{\{[^}]*\}\}", " " + SIN_DATO, salida)

    # ── LA GUARDA: TODO NUMERO SALE DE LA FUENTE ────────────────────────
    #
    # Desde el 11-sep el modelo SI escribe el precio, copiado de la ficha. Esto
    # es lo que hace que esa licencia no sea un agujero: un numero que no esta
    # en las fichas, ni en las politicas que se le pusieron delante, ni lo puso
    # el codigo, NO PUEDE haber salido de la fuente. Salio de la cabeza del
    # modelo, y la respuesta entera no sale.
    #
    # LA FUENTE SON LAS TRES COSAS QUE VIAJARON, y el inventario es una de
    # ellas. Medido el 11-sep 18:40: a "que producto mas caro tenes" el modelo
    # contesto "$3.100.500", que es el tope que el inventario le habia dicho, y
    # la guarda lo llamo invento porque solo miraba fichas y politicas. Se tiro
    # una respuesta CORRECTA. Lo que se le pone delante al modelo es fuente,
    # todo, o la guarda castiga por hacerle caso al prompt.
    #
    # Y por eso la comparacion es contra el texto ENTERO de la fuente y no solo
    # contra los precios: `1000 dpi` y `3200 MHz` son numeros de la ficha, y
    # una guarda que solo conociera precios los llamaria invento y tiraria una
    # respuesta correcta. La regla es de PROCEDENCIA, no de tema.
    import json as _json
    permitidos = {str(m) for m in informe["montos"]}
    permitidos |= _digitos(_json.dumps(fichas or [], ensure_ascii=False,
                                       default=str))
    permitidos |= _digitos(fuente_texto or "")
    # LA TARIFA DEL MOTOR TAMBIEN ES FUENTE, y hasta hoy no. El 13-sep el
    # envio salio del bloque que viaja siempre y paso a pedirse por el motor:
    # la tarifa vive en `envios`, que el modelo ve en el retorno, y la guarda
    # no la miraba. Medido el 13-sep 22:35, charla 5493547504287: "el que me
    # dijiste recien" —el Genius de $12.000— el modelo copio los $7.500 que
    # el motor acaba de cotizar a Cordoba, huecos_llenos=0, y la guarda tiro
    # la respuesta entera. El cliente leyo el fallback. Copiar la tarifa que
    # volvio no es inventar; inventar sigue cayendo, porque lo que no esta
    # en `envios` no entra aca.
    if envio_monto is not None:
        permitidos |= _digitos(str(int(envio_monto)))
    if envios:
        permitidos |= _digitos(_json.dumps(envios, ensure_ascii=False,
                                           default=str))
    # EL TOTAL CALCULADO TAMBIEN ES FUENTE. Es la misma leccion que este modulo
    # ya aprendio dos veces -con el inventario el 11-sep, con la tarifa del
    # motor el 13-sep-: lo que se le pone delante al modelo es fuente, TODO, o
    # la guarda castiga por hacerle caso. El detalle entra entero porque ahi
    # viven los subtotales y el descuento, que son los renglones que el modelo
    # copia cuando desglosa la cuenta.
    if cuenta:
        permitidos |= _digitos(_json.dumps(cuenta, ensure_ascii=False,
                                           default=str))
    for bruto in _CIFRA.findall(salida):
        limpio = re.sub(r"\D", "", bruto)
        if limpio and limpio not in permitidos:
            informe["inventada"].append(bruto.strip())

    # ── EL TOTAL, RECIEN AHORA ──────────────────────────────────────────
    #
    # Suma TODO monto que quedo escrito en el mensaje, venga del modelo o del
    # codigo: los del modelo ya pasaron por la guarda de arriba, asi que a esta
    # altura no hay una sola cifra sin respaldo en la fuente. Sumar solo lo que
    # puso el codigo daba la mitad de la cuenta -el precio lo escribe el modelo
    # desde la ficha-, que es peor que no dar ninguna.
    if "\x00TOTAL\x00" in salida:
        # EL TOTAL CALCULADO GANA SOBRE LA SUMA DEL TEXTO (14-sep-2026), y no
        # es una preferencia: son dos numeros distintos. La suma del texto no
        # puede conocer el descuento por transferencia ni el reparto entre
        # medios, asi que con un 70/30 daba el total SIN descuento. Con la
        # cuenta hecha, el hueco se llena con lo que el cliente va a pagar.
        _calc = (cuenta or {}).get("total_final_ars")
        if _calc is None:
            _calc = (cuenta or {}).get("total_ars")
        if _calc is not None:
            informe["llenos"].append("total")
            informe["montos"].append(int(_calc))
            salida = salida.replace("\x00TOTAL\x00", _money(_calc))
            partes = []
        else:
            partes = [int(re.sub(r"\D", "", m)) for m in
                      re.findall(r"\$\s?\d[\d.]*",
                                 salida.split("\x00TOTAL\x00")[0])]
        if partes:
            total = sum(partes)
            informe["llenos"].append("total")
            informe["montos"].append(total)
            salida = salida.replace("\x00TOTAL\x00", _money(total))
        elif "\x00TOTAL\x00" in salida:
            informe["sin_dato"].append("total")
            salida = salida.replace("\x00TOTAL\x00", SIN_DATO)

    if informe["sin_dato"]:
        log.warning("hueco_sin_dato", trace_id=trace_id,
                    huecos=informe["sin_dato"])
    if informe["inventada"]:
        log.warning("plata_inventada", trace_id=trace_id,
                    montos=informe["inventada"][:5])
    return salida, informe
