"""
RESPONDEDOR SIMPLE — paso 3 del camino mínimo de pruebas.

El camino de prueba es deliberadamente corto: comprender (LLM) -> resolver
(codigo) -> responder simple (codigo). Este modulo es el tercer paso: toma el
objeto de comprension YA resuelto por resolver_aspectos y arma una respuesta
directa, de plantilla, que cierra en la herramienta determinista. SIN LLM
redactor, SIN verificador, SIN compuerta: eso es la capa pesada que estas pruebas
dejan afuera a proposito para medir pregunta + interpretacion + respuesta rapida.

Cada respuesta dice si CIERRA el aspecto (el dato quedo resuelto) o si abre una
PREGUNTA (hace falta que el cliente desambigue o complete). La pregunta de
ambiguedad es la que tapa el cajon equivocado: nace de los candidatos reales que
detecto el codigo, no de una adivinanza.

Por ahora cubre LOCALIDAD (el unico aspecto con resolvedor). Crece con el mismo
patron cuando entren producto y pago. Funcion pura, testeable offline.
"""
from typing import Optional

from app.core.resolver_aspectos import resolver_aspectos

# Etiquetas legibles para la respuesta. El slug interno es para el codigo; al
# cliente se le habla en castellano normal.
_PROV_LABEL = {
    "buenos_aires": "Buenos Aires", "caba": "Capital Federal",
    "cordoba": "Cordoba", "santa fe": "Santa Fe", "mendoza": "Mendoza",
    "salta": "Salta", "tucuman": "Tucuman", "misiones": "Misiones",
    "corrientes": "Corrientes", "entre rios": "Entre Rios",
    "catamarca": "Catamarca", "jujuy": "Jujuy",
    "tierra del fuego": "Tierra del Fuego",
}
_ZONA_LABEL = {"caba": "Capital", "gba": "Gran Buenos Aires", "interior": "interior"}


def _prov(slug: str) -> str:
    return _PROV_LABEL.get(slug, str(slug or "").replace("_", " ").title())


def responder_localidad(res: dict) -> Optional[dict]:
    """Respuesta simple para el aspecto localidad ya resuelto."""
    estado = res.get("estado")
    if estado == "ambiguo":
        termino = str(res.get("termino", "")).title()
        ops = ", ".join(_prov(p) for p in res.get("candidatos", []))
        return {"tipo": "confirmar_localidad", "cierra": False,
                "texto": (f"{termino} hay en varias provincias. "
                          f"Para cotizarte bien el envio, decime cual es la tuya: "
                          f"{ops}.")}
    if estado == "resuelto":
        zona = _ZONA_LABEL.get(res.get("zona"), res.get("zona"))
        return {"tipo": "localidad_ok", "cierra": True,
                "texto": f"Listo, el envio va a zona {zona}."}
    if estado == "pedir_dato":
        return {"tipo": "pedir_cp", "cierra": False,
                "texto": ("No me cae esa localidad. Pasame el codigo postal y "
                          "te cotizo el envio.")}
    return None


def responder_simple(comprension: dict) -> Optional[dict]:
    """Camino minimo: resuelve los aspectos y arma la respuesta del primero que
    tenga dato. Devuelve {tipo, texto, cierra} o None si no hay nada que
    responder por esta via simple (el caso cae al flujo normal)."""
    comprension = resolver_aspectos(comprension or {})
    res_loc = (comprension.get("envio") or {}).get("resolucion") or {}
    if res_loc.get("estado") and res_loc["estado"] != "sin_dato":
        return responder_localidad(res_loc)
    return None
