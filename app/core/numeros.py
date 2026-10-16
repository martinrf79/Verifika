"""LOS NUMEROS QUE SALEN — ningun monto calculado lo escribe el modelo (FICHA 69, 15-oct-2026).

EL MODELO ESCRIBE EL PRECIO de un producto, copiado del hecho que el codigo
le puso delante. LA CUENTA NO LA ESCRIBE: cada calculo del turno lleva un id y
el redactor pone su marca, `{{cuenta:C1}}`; el codigo la cambia por el bloque
exacto de la calculadora. Los otros huecos siguen: `{{precio}}`,
`{{precio:ID}}`, `{{envio}}`, `{{envio:destino}}` y `{{total}}`.

Tres reglas y ninguna excepcion:

  1. UN HUECO QUE NO RESUELVE NO SE INVENTA: se dice que no se tiene el dato y
     queda el renglon `hueco_sin_dato` en el log.
  2. SOLO VALE LO DE ESTE TURNO. La fuente es lo que devolvieron las
     herramientas ahora y la ficha de la charla, que no trae totales viejos.
     Un presupuesto anterior no es fuente: si el pedido cambio, se recalcula.
  3. UN NUMERO SIN FUENTE NO SALE, Y NO SE LLEVA LA RESPUESTA. Se saca su
     renglon; si el turno tiene un calculo que no quedo escrito, va su bloque.
     Queda `monto_suelto` en el log con el `trace_id`: es una alarma, y en
     produccion tiene que ir a cero.
"""
import re

from app.logger import get_logger

log = get_logger(__name__)

_HUECO = re.compile(r"\{\{\s*(precio|envio|total|cuenta)\s*(?::\s*([^}]*))?\s*\}\}")

# UNA CIFRA GRANDE: con signo pesos, con puntos de mil, o cuatro digitos para
# arriba. No es solo plata a proposito: `3200 MHz` tambien cae, porque la regla
# es de donde sale el numero. Lo corto -"24 meses", "16GB"- no entra.
# EL PISO ES CUATRO DIGITOS: con tres, "100% original" se llevaba la respuesta;
# el precio mas barato tiene cuatro, y un monto de tres cae por el signo pesos.
# El borde es por DIGITO y no `\b`: con `\b`, "2560x1440" no era ningun numero.
_CIFRA = re.compile(r"\$\s?\d[\d.]*"
                    r"|(?<!\d)\d{1,3}(?:\.\d{3})+(?!\d)"
                    r"|(?<!\d)\d{4,}(?!\d)")

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
           envios: dict | None = None, cuenta: dict | None = None,
           calculos: dict | None = None) -> tuple:
    """(texto con los numeros puestos, informe). El informe dice que huecos se
    llenaron, cuales quedaron sin dato, que montos se sacaron y que bloques
    puso el codigo.

    `fuente_texto` es lo que vio el modelo EN ESTE TURNO: lo que devolvieron
    las herramientas y la ficha de la charla. No la charla escrita: ahi estan
    los presupuestos viejos, y copiar uno es como salio Posadas con el envio
    que ya no se cobraba (15-oct, K21 en WhatsApp).

    `envio_monto` es la tarifa cuando volvio UNA sola del motor; con varias el
    hueco pelado no elige. `envios` es {destino: tarifa} y resuelve
    `{{envio:cordoba}}`. `cuenta` es el ultimo total calculado: llena
    `{{total}}`, con `total_final_ars` si hay reparto de pago.

    `calculos` es {id: {"detalle": bloque, "vuelve": lo que devolvio}}, cada
    calculo del turno con el id que vio el redactor. `{{cuenta:C1}}` pone el
    bloque; un calculo sin marca y sin su total escrito va al final.
    """
    informe = {"llenos": [], "sin_dato": [], "montos": [], "inventada": [], "bloques": []}
    calculos = calculos or {}

    def _pone(m):
        clase, ref = m.group(1), (m.group(2) or "").strip()
        if clase == "cuenta":
            if ref in calculos:
                informe["bloques"].append(ref)
                return f"\x00C:{ref}\x00"
            informe["sin_dato"].append(f"cuenta:{ref}")
            return SIN_DATO
        if clase == "precio":
            f = _precio_de(fichas, ref)
            if not f:
                informe["sin_dato"].append("precio" + (f":{ref}" if ref else ""))
                return SIN_DATO
            monto = int(f["precio_ars"])
        elif clase == "envio":
            # Con varios destinos, el que nombra el hueco; con uno, el unico.
            monto = _envio_de(envios, ref) if ref else envio_monto
            if monto is None:
                informe["sin_dato"].append("envio" + (f":{ref}" if ref else ""))
                return SIN_DATO
        else:
            # El total va en la segunda pasada, con los precios ya puestos.
            return "\x00TOTAL\x00"
        informe["llenos"].append(clase)
        informe["montos"].append(int(monto))
        return _money(monto)

    salida = _HUECO.sub(_pone, texto or "")

    # EL HUECO QUE EL MODELO COPIO DEL MOLDE —`{{producto}}`— no viaja crudo.
    crudos = re.findall(r"\{\{[^}]*\}\}", salida)
    if crudos:
        informe["crudos"] = crudos
        log.warning("hueco_crudo", trace_id=trace_id, huecos=crudos[:5])
        salida = re.sub(r"\s*\{\{[^}]*\}\}", " " + SIN_DATO, salida)

    # ── LA GUARDA: UN NUMERO SIN FUENTE SE SACA, CON SU RENGLON ─────────
    #
    # La regla es de PROCEDENCIA, no de tema: `1000 dpi` y `3200 MHz` son de la
    # ficha y pasan; un monto que no esta en nada de lo que vio el modelo en
    # este turno no pudo salir de la fuente. Antes tiraba la respuesta entera y
    # el cliente leia el aviso de demanda por un renglon; ahora se va el renglon
    # y lo demas sale.
    import json as _json
    permitidos = {str(m) for m in informe["montos"]}
    permitidos |= _digitos(_json.dumps([fichas or [], envios or {}, cuenta or {}, envio_monto],
                                       ensure_ascii=False, default=str))
    permitidos |= _digitos(fuente_texto or "")
    for c in calculos.values():
        permitidos |= _digitos(_json.dumps(c.get("vuelve") or {}, ensure_ascii=False, default=str))
    renglones = []
    for renglon in salida.split("\n"):
        # Se va la ORACION que lo lleva: un parrafo de WhatsApp es un renglon.
        oraciones = []
        for o in re.split(r"(?<=[.!?])\s+", renglon):
            malos = [b.strip() for b in _CIFRA.findall(o) if re.sub(r"\D", "", b) not in permitidos]
            informe["inventada"] += malos
            if not malos:
                oraciones.append(o)
        if oraciones or not renglon.strip():
            renglones.append(" ".join(oraciones))
    salida = "\n".join(renglones)
    informe["bloques"] = [c for c in informe["bloques"] if f"\x00C:{c}\x00" in salida]

    # ── LOS BLOQUES DE LA CALCULADORA, tal cual ─────────────────────────
    # Un renglon corto que solo repite plata de un bloque marcado —"$7.500"
    # despues del presupuesto— se va: el bloque ya la dice.
    def plata(r):
        return {re.sub(r"\D", "", m) for m in re.findall(r"\$\s?\d[\d.]*", r)}
    marcados = _digitos(_json.dumps([calculos[c].get("vuelve") for c in informe["bloques"]], default=str))
    salida = "\n".join(r for r in salida.split("\n")
                        if not (plata(r) and plata(r) <= marcados and len(r.split()) <= 8))
    for cid in informe["bloques"]:
        salida = salida.replace(f"\x00C:{cid}\x00", "\n" + str(calculos[cid].get("detalle") or SIN_DATO) + "\n")
    # SIN MARCA Y SIN SU TOTAL ESCRITO, el bloque va al final; se van los
    # renglones del modelo que solo repetian montos de esos bloques.
    faltan = [cid for cid, c in calculos.items() if cid not in informe["bloques"] and not (
        str(int((c.get("vuelve") or {}).get("total_final_ars") or (c.get("vuelve") or {}).get("total_ars") or 0))
        in _digitos(salida))]
    if faltan:
        suyos = _digitos(_json.dumps([calculos[c].get("vuelve") for c in faltan], ensure_ascii=False, default=str))
        salida = "\n".join(r for r in salida.split("\n") if not (plata(r) and plata(r) <= suyos))
        salida = salida.rstrip() + "\n\n" + "\n\n".join(str(calculos[c].get("detalle") or "") for c in faltan)
        informe["bloques"] += faltan

    # ── EL TOTAL, RECIEN AHORA ──────────────────────────────────────────
    # El calculado gana: la suma del texto no conoce el descuento ni el
    # reparto. Sin cuenta, suma lo que quedo escrito antes del hueco, que ya
    # paso por la guarda.
    if "\x00TOTAL\x00" in salida:
        _calc = (cuenta or {}).get("total_final_ars")
        if _calc is None:
            _calc = (cuenta or {}).get("total_ars")
        if _calc is None:
            partes = [int(re.sub(r"\D", "", m)) for m in
                      re.findall(r"\$\s?\d[\d.]*", salida.split("\x00TOTAL\x00")[0])]
            _calc = sum(partes) if partes else None
        if _calc is not None:
            informe["llenos"].append("total")
            informe["montos"].append(int(_calc))
            salida = salida.replace("\x00TOTAL\x00", _money(_calc))
        else:
            informe["sin_dato"].append("total")
            salida = salida.replace("\x00TOTAL\x00", SIN_DATO)

    salida = re.sub(r"\n{3,}", "\n\n", salida).strip()
    if not salida:
        salida = SIN_DATO.capitalize() + "."
    if informe["sin_dato"]:
        log.warning("hueco_sin_dato", trace_id=trace_id, huecos=informe["sin_dato"])
    if informe["inventada"]:
        log.warning("monto_suelto", trace_id=trace_id, montos=informe["inventada"][:5])
    if calculos:
        log.info("montos_del_codigo", trace_id=trace_id, bloques=informe["bloques"],
                 calculos={k: (v.get("vuelve") or {}).get("total_final_ars") or (v.get("vuelve") or {}).get("total_ars")
                           for k, v in calculos.items()})
    return salida, informe
