"""
VERIFICADOR DE SERVICIOS — segunda linea determinista de la anti alucinacion.

El verificador de plata (verificador.py) cuida las CIFRAS: que ningun numero de
dinero salga de la cabeza del modelo. Pero con datos reales aparecio otra clase de
alucinacion que NO toca plata: el bot promete SERVICIOS o capacidades que la tienda
no ofrece. Empaque para regalo, instalacion a domicilio, entrega en mano, retiro en
local cuando la tienda es solo online, garantia extendida, servicio tecnico. Eso
erosiona la confianza igual que un precio inventado, y el verificador de plata no
lo ve porque solo mira dinero.

Esta pieza es codigo puro, igual de determinista que el verificador de plata:

- Tiene un catalogo curado de SERVICIOS riesgosos, los que el modelo tiende a
  inventar, cada uno con sus frases gatillo.
- Arma el universo de lo que la tienda SI ofrece desde su evidencia real: el texto
  de la FAQ y los campos de producto. Misma fuente de verdad que el resto.
- Si la respuesta AFIRMA un servicio riesgoso y ese servicio no aparece respaldado
  en ninguna parte de la evidencia de la tienda, es una promesa inventada y se
  marca.
- Si el servicio esta negado ("no hacemos envoltorio para regalo") no se marca: el
  bot esta declinando bien, que es lo correcto.

No llama a ningun modelo. Es exacto, instantaneo y no entra en loop. A proposito
cubre solo servicios concretos y comprometedores; los elogios vagos como "atencion
personalizada" se dejan pasar para no bloquear de mas. Ante la duda prefiere NO
marcar (un falso bloqueo rompe la conversacion; una promesa inventada se ataja
ademas por prompt).
"""
import re
import unicodedata
from typing import Optional

from app.logger import get_logger

log = get_logger(__name__)

# La negacion se busca por CLAUSULA, no por ventana de caracteres. Una ventana
# fija se queda corta con negaciones naturales largas ("No tenemos servicio de
# instalacion a domicilio") y bloquea respuestas honestas. Partimos el texto en
# clausulas por puntuacion fuerte (sin contar la coma) y, dentro de la clausula
# donde aparece el servicio, si hay una negacion ANTES, no se marca. Asi
# "no tenemos servicio de X" o "no ofrecemos X" no marcan, y "no hay drama, te lo
# damos" tampoco se cuela como negado en serio porque el caso comun es declinar.
_CLAUSE_SPLIT = re.compile(r"[.;:!?\n]+")
_NEG_RE = re.compile(r"\b(no|sin|tampoco|nunca|jamas)\b")

# Catalogo de servicios riesgosos. Por cada uno:
#   gatillos: frases que, dichas en la RESPUESTA, significan que el bot lo promete.
#   respaldo: substrings que, presentes en la EVIDENCIA de la tienda, prueban que
#             la tienda de verdad lo ofrece. Si falta, se usan los gatillos.
# Todo en minuscula y sin acentos (se normaliza igual antes de comparar).
_SERVICIOS = {
    "empaque_regalo": {
        "gatillos": [
            "envoltorio para regalo", "envoltorio de regalo",
            "empaque para regalo", "empaque de regalo",
            "envuelto para regalo", "envolver para regalo",
            "envolvemos para regalo", "te lo envolvemos",
            "papel de regalo", "envoltura de regalo",
            "lo envolvemos para regalo",
        ],
        # "empaque"/"regalo" sueltos respaldan de mas (la FAQ dice "empaque
        # original" en devoluciones). El respaldo tiene que ser el concepto regalo.
        "respaldo": ["para regalo", "envoltorio", "papel de regalo",
                     "envolvemos para regalo", "envoltura"],
    },
    "instalacion": {
        # OJO: nada de "instalacion" suelto. La palabra aparece inocente en fichas
        # ("cables para su instalacion") y en garantia ("danos por instalacion"),
        # y disparaba o respaldaba de mas. Solo frases de OFRECER el servicio.
        "gatillos": [
            "instalacion a domicilio", "servicio de instalacion",
            "te lo instalamos", "lo instalamos", "instalacion incluida",
            "instalamos en tu", "vamos a instalar", "instalacion gratuita",
            "instalarte", "podemos instalar", "te instalo", "instalar a domicilio",
            "te lo instalo",
        ],
        "respaldo": ["instalamos", "servicio de instalacion",
                     "instalacion a domicilio", "instalacion incluida"],
    },
    "entrega_en_mano": {
        "gatillos": [
            "entrega en mano", "entregar en mano", "entrego en mano",
            "entrega personal", "te lo llevo en mano",
            "te lo entrego personalmente", "entrega personalizada",
            "te lo acerco", "te lo llevo personalmente",
        ],
        "respaldo": ["entrega en mano", "entregar en mano", "entrega personal",
                     "en mano"],
    },
    "retiro_local": {
        "gatillos": [
            "retiro en local", "retiro en el local", "retiras en el local",
            "podes retirarlo", "pasar a buscarlo", "pasas a buscar",
            "retiro en tienda", "retiro en sucursal", "venir a buscarlo",
            "retirarlo en persona", "lo retiras en", "pasa a retirarlo",
        ],
        # A proposito NO incluye "local fisico" ni "sucursal" sueltos: una tienda
        # online los menciona para NEGARLOS ("no tenemos local fisico") y eso
        # respaldaria de mas. Solo respalda si la FAQ ofrece retiro de verdad.
        "respaldo": ["retiro en", "pasar a buscar", "pasa a retirar",
                     "podes retirar", "showroom", "retiralo en"],
    },
    "armado": {
        "gatillos": [
            "te lo mando armado", "te lo mandamos armado", "viene armado",
            "lo armamos", "te lo armamos", "armado y listo", "ya viene armado",
            "te lo ensamblamos", "lo ensamblamos", "viene ensamblado",
            # Servicio de armado de PC, lo que el modelo invento en datos reales:
            "armamos la pc", "armemos la pc", "te armamos la pc",
            "armamos tu pc", "armado de pc", "armado y test", "armado y testeo",
            "instalacion de windows", "armado completo",
        ],
        # "armamos"/"armado" sueltos respaldan de mas: la FAQ dice "armamos el
        # contacto" y "armamos cotizacion", otro sentido. Respaldo solo armado de
        # producto.
        "respaldo": ["te lo armamos", "lo armamos", "entregamos armado",
                     "armado incluido", "servicio de armado", "viene armado",
                     "ensamblado", "lo ensamblamos"],
    },
    "servicio_tecnico": {
        "gatillos": [
            "servicio tecnico", "lo reparamos", "reparamos tu",
            "taller de reparacion", "servicio de reparacion",
            "reparacion a domicilio",
        ],
        "respaldo": ["servicio tecnico", "reparamos", "reparacion", "taller"],
    },
    "garantia_extendida": {
        "gatillos": [
            "garantia extendida", "garantia de por vida", "garantia ampliada",
            "extension de garantia", "garantia de por", "ampliacion de garantia",
        ],
        "respaldo": ["garantia extendida", "garantia ampliada",
                     "extension de garantia", "de por vida"],
    },
    "prueba_previa": {
        "gatillos": [
            "probarlo antes de comprar", "prueba antes de comprar",
            "test antes de comprar", "lo probas antes", "periodo de prueba",
            "prueba sin cargo", "lo probas en tu casa",
        ],
        "respaldo": ["prueba antes", "probarlo antes", "periodo de prueba",
                     "prueba sin cargo"],
    },
}


def _normaliza(t) -> str:
    """A minuscula y sin acentos, para comparar parejo."""
    t = unicodedata.normalize("NFKD", str(t or ""))
    t = t.encode("ascii", "ignore").decode("ascii")
    return t.lower()


def _afirmado_en(texto_norm: str, frase_norm: str) -> bool:
    """True si la frase aparece como palabra(s) completa(s) en el texto, SIN una
    negacion pegada justo antes. El limite de palabra evita que "armado" matchee
    dentro de "desarmado" o "armamos" dentro de "desarmamos", justo lo que dicen
    los clientes ("viene desarmado en la caja"). Recorre todas las apariciones:
    alcanza con que una este afirmada."""
    patron = re.compile(r"(?<!\w)" + re.escape(frase_norm) + r"(?!\w)")
    for clausula in _CLAUSE_SPLIT.split(texto_norm):
        for m in patron.finditer(clausula):
            if not _NEG_RE.search(clausula[:m.start()]):
                return True
    return False


def _corpus_tienda(evidence: list[dict]) -> str:
    """Junta todo lo que la tienda dice ofrecer: el texto de la FAQ (y sus
    keywords/valores si vienen) y los campos descriptivos de los productos.
    De aca sale si un servicio esta respaldado o es inventado."""
    partes: list[str] = []
    for item in evidence or []:
        tipo = item.get("tipo")
        if tipo == "faq":
            partes.append(str(item.get("respuesta", "")))
            partes.append(str(item.get("tema", "")))
            for k in item.get("keywords", []) or []:
                partes.append(str(k))
            for v in item.get("valores", []) or []:
                partes.append(str(v.get("concepto", "")))
                partes.append(str(v.get("condicion", "")))
        elif tipo == "producto":
            for k in ("nombre", "categoria", "descripcion", "uso_recomendado",
                      "caracteristicas_extra", "material"):
                partes.append(str(item.get(k, "")))
    return _normaliza(" ".join(partes))


def verificar_servicios(respuesta: str,
                        evidence: list[dict],
                        trace_id: Optional[str] = None) -> dict:
    """
    Marca servicios que la respuesta promete y la tienda no ofrece. Devuelve:
        {
          "ok": bool,                       # True si no hay servicio inventado
          "accion": "responder"|"bloquear",
          "servicios_inventados": [...],    # nombres canonicos
          "total_servicios_detectados": int # cuantos servicios riesgosos afirmo
        }
    """
    resp = _normaliza(respuesta)
    corpus = _corpus_tienda(evidence)

    inventados: list[str] = []
    detectados = 0
    for nombre, cfg in _SERVICIOS.items():
        gatillos = [_normaliza(g) for g in cfg["gatillos"]]
        if not any(_afirmado_en(resp, g) for g in gatillos):
            continue
        detectados += 1
        respaldo = [_normaliza(r) for r in cfg.get("respaldo") or cfg["gatillos"]]
        if any(_afirmado_en(corpus, r) for r in respaldo):
            continue
        inventados.append(nombre)

    ok = len(inventados) == 0
    accion = "responder" if ok else "bloquear"

    log.info("verificador_servicios", trace_id=trace_id, accion=accion,
             detectados=detectados, inventados=inventados)

    return {
        "ok": ok,
        "accion": accion,
        "servicios_inventados": inventados,
        "total_servicios_detectados": detectados,
    }
