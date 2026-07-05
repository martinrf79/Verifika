"""
JUEZ DE INVARIANTES — chequeo determinista de cada respuesta del banco.

La tanda de charlas no depende de que un humano LEA cada salida: el juez
aplica los MISMOS detectores del camino vivo (verificador_stock, guardia de
promesas, ancla de precio del verificador) contra el catalogo completo del
doble, mas invariantes de salida (marcador sin estampar, narracion interna).
Si una respuesta viola un invariante, la tanda falla sola.

No trae casos hardcodeados: son invariantes, no ejemplos. Conservador como
los verificadores que reusa: ancla unica o no acusa.
"""
import re

from app.core import verificador_stock as VS
from app.core import guardia_promesas as GP

# Monto en pesos con separador de miles argentino, o entero pelado tras $.
_RE_MONTO = re.compile(r"\$\s?(\d{1,3}(?:\.\d{3})+|\d+)")

# La cifra viene de una CUENTA (total, envio, descuento, cuota): no es el precio
# de lista del producto nombrado y el ancla de precio no la juzga (los totales
# los verifica el pipeline con el proof de la calculadora, no este juez).
_RE_CONTEXTO_CUENTA = re.compile(
    r"(?:total|subtotal|env[ií]o|descuento|cuotas?|se[ñn]a|c/u|por\s+los?\s+\d)",
    re.IGNORECASE)

# Narracion interna del solver filtrada al cliente ("el sistema me tiro un
# detalle", "me pide mas precision"): el cliente nunca tiene que ver la cocina.
_RE_NARRACION = re.compile(
    r"(?:el\s+sistema\s+(?:me|tom[oó]|tir[oó]|dice|marc[oó])|"
    r"la\s+herramienta\s+me|me\s+tir[oó]\s+un\s+detalle|"
    r"ah[ií]\s+me\s+pide|la\s+tool\b)",
    re.IGNORECASE)


def _catalogo_evidencia(tienda_id: str = "verifika_prod") -> list[dict]:
    from app.storage.firestore_client import get_all_products
    return [{"tipo": "producto", **p}
            for p in get_all_products(tienda_id=tienda_id)]


def _tarifas_envio_conocidas(tienda_id: str) -> set[int]:
    """Todos los montos de envio que la tienda puede cobrar (config por
    provincia, tarifas_envio de la tienda, valores de la FAQ costo_envio). Una
    cifra igual a una tarifa es plausiblemente un envio del pedido aunque no
    diga la palabra 'envio' cerca ('Mouse a Cordoba: $7.500'): no se acusa
    como precio de lista pisado."""
    montos: set[int] = set()
    try:
        from app.config import get_settings
        montos |= {int(v) for v in
                   get_settings().ENVIO_INTERIOR_POR_PROVINCIA.values()}
    except Exception:
        pass
    try:
        from app.storage.firestore_client import get_config
        provincias = (get_config("tarifas_envio", tienda_id=tienda_id)
                      or {}).get("provincias") or {}
        montos |= {int(v) for v in provincias.values()
                   if isinstance(v, (int, float))}
    except Exception:
        pass
    try:
        from app.storage.firestore_client import get_all_faq
        valores = ((get_all_faq(tienda_id=tienda_id) or {})
                   .get("costo_envio") or {}).get("valores") or []
        for v in valores:
            for k in ("monto", "monto_min", "monto_max"):
                if isinstance(v.get(k), (int, float)):
                    montos.add(int(v[k]))
    except Exception:
        pass
    return montos


def juzgar(respuesta: str, tienda_id: str = "verifika_prod") -> list[str]:
    """Lista de violaciones de invariantes en la respuesta ([] = limpia)."""
    problemas: list[str] = []
    if not respuesta:
        return ["respuesta vacia"]
    ev = _catalogo_evidencia(tienda_id)

    # 1. Disponibilidad contradicha contra el stock real del catalogo.
    for d in VS.detectar_stock_contradicho(respuesta, ev):
        problemas.append(
            f"stock {d['clase']}: {d['nombre']} tiene stock real {d['stock']}")
    for c in VS.corregir_unidades_stock(respuesta, ev)["correcciones"]:
        problemas.append(
            f"cifra de stock {c['de']} distinta del real {c['a']} ({c['id']})")

    # 2. Promesas prohibidas (dia de entrega, retiro en local, servicio no
    #    ofrecido): el mismo detector de la guardia.
    for clase in GP.detectar(respuesta):
        problemas.append(f"promesa prohibida en la salida: {clase}")

    # 3. Marcador interno sin estampar.
    if "[[" in respuesta or "]]" in respuesta:
        problemas.append("marcador interno sin estampar en la salida")

    # 4. Precio de lista contradicho: cifra $ anclada por NOMBRE COMPLETO a UN
    #    producto que no es su precio real ni una cuenta declarada. El nombre
    #    completo es el ancla porque el estampado siempre lo imprime entero;
    #    contra el catalogo completo el ancla por tokens empata entre hermanos.
    tarifas = _tarifas_envio_conocidas(tienda_id)
    for m in _RE_MONTO.finditer(respuesta):
        ventana_previa = respuesta[max(0, m.start() - 30):m.start()]
        if _RE_CONTEXTO_CUENTA.search(ventana_previa):
            continue
        ventana = respuesta[max(0, m.start() - 110):m.start()].lower()
        nombrados = [p for p in ev
                     if (p.get("nombre") or "").strip()
                     and str(p["nombre"]).lower() in ventana
                     and isinstance(p.get("precio_ars"), (int, float))]
        if len(nombrados) != 1:
            continue
        n = int(m.group(1).replace(".", ""))
        if n in tarifas:
            continue
        pr = int(nombrados[0]["precio_ars"])
        if pr != n and (pr == 0 or n % pr != 0):
            problemas.append(
                f"precio ${n} de {nombrados[0]['nombre']} no coincide con el "
                f"catalogo (${pr})")

    # 5. Narracion interna filtrada al cliente.
    if _RE_NARRACION.search(respuesta):
        problemas.append("narracion interna filtrada al cliente")

    return problemas
