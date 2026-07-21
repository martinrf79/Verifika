"""
BANCO DE INTERPRETACION — mide al INTERPRETE directo, caso por caso.

Prioridad 1 de Martin (8-jul): "el bot no interpreta... 50% venta y 50% sin
alucinar; sin interpretar bien no es viable". El banco de charlas prueba el
pipeline entero; ESTE banco aisla la pieza de comprension: mensaje dificil +
contexto -> que DEBERIA leer el interprete (intencion, producto, pedido,
estado), contra lo que leyo de verdad el LLM vivo.

Cada caso define chequeos PARCIALES (solo lo que importa del caso; no se fija
la lectura entera, que varia legitimamente). Casos elegidos para ser estables a
temperatura 0: ambiguedad, ironia, correcciones sobre la marcha, negaciones
dobles, decision condicionada, despedidas que parecen compra.

Uso:  python3 banco_pruebas/banco_interpretacion.py
Sale con codigo != 0 si el puntaje queda abajo del piso (0.8). Tambien lo corre
tests/test_vivo_interpretacion.py (marcado vivo).
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from banco_pruebas.sim_firestore import install

PISO = 0.8

_VISTOS = [
    {"id": "MOU0023", "nombre": "Mouse Genius DX-110 Negro", "precio": 8500},
    {"id": "MOU0024", "nombre": "Mouse Genius DX-110 Blanco", "precio": 8500},
    {"id": "MOU0009", "nombre": "Mouse Logitech M170 Negro", "precio": 12000},
]

_HIST_OFERTA = [
    {"role": "user", "content": "hola, tenes mouse?"},
    {"role": "assistant", "content":
        "Tengo el Mouse Genius DX-110 Negro a $8.500, el Mouse Genius DX-110 "
        "Blanco a $8.500 y el Mouse Logitech M170 Negro a $12.000. ¿Cuál te "
        "gusta?"},
]

_HIST_CIERRE = _HIST_OFERTA + [
    {"role": "user", "content": "el DX-110 negro"},
    {"role": "assistant", "content":
        "Buenísimo. El total del Mouse Genius DX-110 Negro con envío es "
        "$16.000. ¿Lo dejamos confirmado?"},
]


def _es(campo, *valores):
    def _chk(i):
        return i.get(campo) in valores
    return _chk


def _no_es(campo, *valores):
    def _chk(i):
        return i.get(campo) not in valores
    return _chk


def _producto_contiene(txt):
    def _chk(i):
        return txt.lower() in str(i.get("producto_resuelto") or "").lower()
    return _chk


def _criterio_barato(i):
    """El interprete leyo el criterio 'mas barato' (el SEGUNDO interprete que el
    regex del codigo no cubre: 'eco', abreviaturas, modismos)."""
    return str(i.get("criterio") or "").strip() == "mas_barato"


def _pedido_es(*pares):
    """pares = (fragmento_nombre, cantidad). Exige el pedido EXACTO en largo."""
    def _chk(i):
        ped = i.get("pedido") or []
        if len(ped) != len(pares):
            return False
        for frag, cant in pares:
            if not any(frag.lower() in str(p.get("producto") or "").lower()
                       and p.get("cantidad") == cant for p in ped):
                return False
        return True
    return _chk


def _consultados_tiene(*frags):
    """El cliente pregunto por VARIOS productos: cada fragmento tiene que
    aparecer en algun item de productos_consultados. Exige el largo exacto."""
    def _chk(i):
        pc = i.get("productos_consultados") or []
        if len(pc) != len(frags):
            return False
        for frag in frags:
            if not any(frag.lower() in str(p.get("producto") or "").lower()
                       for p in pc):
                return False
        return True
    return _chk


# Cada caso: descripcion, history, mensaje, lista de (nombre_chequeo, funcion).
CASOS = [
    ("negacion con eleccion: 'no el negro, el blanco'",
     _HIST_OFERTA, "no quiero el negro, dame el blanco",
     [("producto blanco", _producto_contiene("blanco")),
      ("no marca compra cerrada aun", _es("intencion", "aporta_dato",
                                          "pregunta_especifica",
                                          "decision_compra"))]),

    ("decision condicionada: 'dale pero antes...'",
     _HIST_CIERRE, "dale, pero antes decime si tiene garantia",
     [("no es compra cerrada", _no_es("intencion", "decision_compra"))]),

    ("ironia no es compra: 'JAJA seguro'",
     _HIST_CIERRE, "jaja si claro, seguro que manana lo tengo gratis",
     [("no es compra", _no_es("intencion", "decision_compra"))]),

    ("'ni loco pago eso' no es decision de pago",
     _HIST_CIERRE, "ni loco pago eso",
     [("no es compra", _no_es("intencion", "decision_compra"))]),

    ("correccion sobre la marcha: '2... no, mejor 3'",
     _HIST_OFERTA, "dale, dame 2 del DX-110 negro... no para, mejor 3",
     [("pedido final 3 negros", _pedido_es(("dx-110 negro", 3)))]),

    ("saco un item a mitad de frase",
     _HIST_OFERTA,
     "quiero 2 del DX-110 negro y 1 M170, pero el M170 sacalo mejor",
     [("pedido solo 2 negros", _pedido_es(("dx-110 negro", 2)))]),

    ("'listo' tras pregunta de cierre = compra",
     _HIST_CIERRE, "listo, dale",
     [("es compra", _es("intencion", "decision_compra"))]),

    ("'listo, gracias' de despedida NO es compra",
     _HIST_OFERTA, "listo, gracias por la info, cualquier cosa vuelvo",
     [("no es compra", _no_es("intencion", "decision_compra"))]),

    ("doble negacion con duda",
     _HIST_CIERRE, "no es que no me guste, pero no se si me conviene",
     [("no es compra", _no_es("intencion", "decision_compra"))]),

    ("'comprar todavia no' pese a la palabra comprar",
     _HIST_CIERRE, "comprar, lo que se dice comprar, todavia no",
     [("no es compra", _no_es("intencion", "decision_compra"))]),

    ("referencia al mas caro entre vistos: 'el barato no, el otro'",
     _HIST_OFERTA, "el barato no, el otro",
     # Lectura buena: el M170 (el que NO es barato) O duda honesta (candidatos/
     # confianza baja). Lo unico MAL es elegir confiado otra variante barata.
     [("M170 o duda honesta", lambda i: (
         "m170" in str(i.get("producto_resuelto") or "").lower()
         or len(i.get("candidatos") or []) >= 2
         or float(i.get("confianza") or 0) < 0.6))]),

    ("cantidad en palabra con typo de producto",
     _HIST_OFERTA, "dale, dame dos del dx110 negro",
     [("pedido 2 negros", _pedido_es(("dx-110 negro", 2)))]),

    ("pregunta disfrazada de afirmacion (confianza)",
     _HIST_OFERTA, "los materiales, las calidades son buenas, los envios son seguros",
     [("no es compra", _no_es("intencion", "decision_compra")),
      ("no arma pedido", lambda i: not (i.get("pedido") or []))]),

    ("emojis y jerga: 'metele q va'",
     _HIST_CIERRE, "metele q va 👍",
     [("es compra", _es("intencion", "decision_compra"))]),

    ("cambio de opinion contra el historial",
     _HIST_CIERRE, "sabes que? al final el blanco",
     [("producto blanco", _producto_contiene("blanco"))]),

    ("pregunta de precio no es compra",
     _HIST_OFERTA, "y el M170 cuanto sale con envio a Rosario?",
     [("no es compra", _no_es("intencion", "decision_compra")),
      ("resuelve M170", _producto_contiene("m170"))]),

    # ── Tanda 2 (8-jul): enredados, referencias cruzadas, regionalismos ─────
    ("mensaje largo enredado con pedido adentro",
     _HIST_OFERTA,
     "che buenas, mira te cuento, ando necesitando para el negocio de mi "
     "cuñado unas cositas, el quiere si o si algo logitech porque dice que lo "
     "demas no le sirve, asi que pasame precio del mouse logitech ese que "
     "tenes, y decime si el genius anda bien porque capaz lo convenzo",
     [("resuelve el logitech", _producto_contiene("m170")),
      ("no es compra", _no_es("intencion", "decision_compra"))]),

    ("referencia ordinal a la lista del bot: 'el segundo'",
     _HIST_OFERTA, "dale, el segundo",
     [("resuelve el blanco (2do de la lista)",
       lambda i: "blanco" in str(i.get("producto_resuelto") or "").lower()
       or any("blanco" in str(c).lower()
              for c in (i.get("candidatos") or [])))]),

    ("regionalismo cordobes con objecion",
     _HIST_OFERTA, "uh que caro que ta el logi, tenei algo ma barato?",
     [("no es compra", _no_es("intencion", "decision_compra"))]),

    ("jerga fuerte de compra: 'de una, facturame'",
     _HIST_CIERRE, "de una, facturame nomas",
     [("es compra", _es("intencion", "decision_compra"))]),

    ("pedido multiple mezclado en frase larga",
     _HIST_OFERTA,
     "pasame 1 del dx-110 negro y 2 del blanco, ah y me olvidaba, el "
     "logitech tambien, uno solo",
     [("pedido de tres lineas", _pedido_es(("dx-110 negro", 1),
                                           ("dx-110 blanco", 2),
                                           ("m170", 1)))]),

    ("referencia a lo que dijo el bot: 'el de 16 lucas'",
     _HIST_CIERRE, "si dale, el que me dijiste que salia 16 lucas total, ese",
     [("resuelve el DX-110 negro", _producto_contiene("dx-110 negro"))]),

    ("'ponele que si' es un si tibio, no un rechazo",
     _HIST_CIERRE, "ponele que si",
     [("no es rechazo", _no_es("intencion", "otra"))]),

    ("sarcasmo de queja no es compra",
     _HIST_CIERRE, "buenisimo, otra vez me dejan esperando como ayer no?",
     [("no es compra", _no_es("intencion", "decision_compra"))]),

    ("edicion de pedido: 'sacale uno' sobre 3 pedidos",
     _HIST_OFERTA + [
         {"role": "user", "content": "dame 3 del DX-110 negro"},
         {"role": "assistant", "content":
             "Perfecto, 3x Mouse Genius DX-110 Negro: $25.500 en total. "
             "¿Confirmamos?"}],
     "mejor sacale uno",
     [("pedido queda en 2", _pedido_es(("dx-110 negro", 2)))]),

    ("numero que NO es cantidad: 'cumple 15'",
     _HIST_OFERTA, "es para mi hijo que cumple 15, que me recomendas?",
     [("no arma pedido", lambda i: not (i.get("pedido") or [])),
      ("no es compra", _no_es("intencion", "decision_compra"))]),

    # ── Tanda 3 (9-jul): criterio "mas barato" abreviado, el caso real que el
    #    regex del codigo NO cubria ("Lo mas eco" cayo al fallback en produccion)
    ("criterio abreviado: 'lo mas eco'",
     _HIST_OFERTA, "dale, lo mas eco",
     [("lee criterio mas barato", _criterio_barato)]),

    ("criterio en modismo: 'mandame lo mas conveniente'",
     _HIST_OFERTA, "y bueno, mandame lo mas conveniente para el bolsillo",
     [("lee criterio mas barato", _criterio_barato)]),

    ("criterio explicito clasico: 'los mas baratos'",
     _HIST_OFERTA, "los mas baratos",
     [("lee criterio mas barato", _criterio_barato)]),

    # ── Tanda 3 (21-jul): consulta MULTIPLE, dos o mas productos en un mensaje.
    # Antes caia a producto_resuelto null sin registrar los productos; ahora van
    # a productos_consultados y no es duda.
    ("dos productos, precio de los dos",
     _HIST_OFERTA, "cuanto sale el M170 y el DX-110 negro?",
     [("consulta los dos", _consultados_tiene("m170", "dx-110 negro")),
      ("no es compra", _no_es("intencion", "decision_compra"))]),

    ("dos productos, uno precio y otro opinion (caso 17 limpio)",
     _HIST_OFERTA,
     "pasame precio del mouse logitech ese, y decime si el genius anda bien",
     [("consulta logitech y genius", _consultados_tiene("m170", "genius"))]),

    ("tres productos en la misma frase",
     _HIST_OFERTA,
     "precio del M170, del DX-110 negro y del DX-110 blanco por favor",
     [("consulta los tres",
       _consultados_tiene("m170", "dx-110 negro", "dx-110 blanco"))]),
]


# Ritmo entre llamadas para no pasar el limite por MINUTO de la capa gratis de
# Gemini (429 quota). No es una falla de interpretacion: es la API cortando por
# rate. Configurable por si la key cambia de plan. Solo del banco, no toca prod.
_PACE_SEG = float(os.getenv("BANCO_PACE_SEG", "5"))
_REINTENTOS_429 = 3


def _es_429(interp: dict) -> bool:
    return "429" in str((interp or {}).get("error") or "")


async def _interpretar_con_ritmo(interpretar_mensaje, msg, hist, tid, estado):
    """Llama al interprete respetando el rate de la free: espera fija entre
    llamadas y, si igual cae un 429, reintenta con backoff. Asi el numero del
    banco mide COMPRENSION, no el limite de la API."""
    espera = _PACE_SEG
    for intento in range(_REINTENTOS_429 + 1):
        interp = await interpretar_mensaje(
            msg, hist, tid, estado_anterior=estado, productos_vistos=_VISTOS)
        if not _es_429(interp):
            return interp
        if intento < _REINTENTOS_429:
            espera *= 2
            print(f"    (429 rate, backoff {espera:.0f}s...)")
            await asyncio.sleep(espera)
    return interp


async def correr(verbose: bool = True) -> float:
    install()
    from app.core.interpretador import interpretar_mensaje

    ok_total = 0
    fallas = []
    for idx, (desc, hist, msg, checks) in enumerate(CASOS, 1):
        if idx > 1:
            await asyncio.sleep(_PACE_SEG)
        interp = await _interpretar_con_ritmo(
            interpretar_mensaje, msg, hist, f"interp{idx:02d}",
            "esperando_confirmacion" if hist == _HIST_CIERRE else "explorando")
        fallos_caso = [n for n, chk in checks if not chk(interp)]
        if fallos_caso:
            fallas.append((idx, desc, fallos_caso, {
                "intencion": interp.get("intencion"),
                "producto": interp.get("producto_resuelto"),
                "pedido": interp.get("pedido"),
                "confianza": interp.get("confianza")}))
            estado = "FALLA"
        else:
            ok_total += 1
            estado = "ok"
        if verbose:
            print(f"[{idx:02d}] {estado}  {desc}")
    score = ok_total / len(CASOS)
    if verbose:
        print(f"\nPUNTAJE: {ok_total}/{len(CASOS)} = {score:.0%} (piso {PISO:.0%})")
        for idx, desc, fallos, leido in fallas:
            print(f"  [{idx:02d}] {desc}\n       fallo: {fallos}\n       leyo: {leido}")
    return score


if __name__ == "__main__":
    puntaje = asyncio.run(correr())
    sys.exit(0 if puntaje >= PISO else 1)
