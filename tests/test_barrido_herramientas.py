"""
EL BARRIDO DE LAS HERRAMIENTAS — por la puerta por donde entra el modelo.

POR QUE EXISTE (Martin, 12-ago-2026): "esta hecho totalmente el barrido o no
esta hecho... siempre se me dice que le faltan etapas. Es desgastante".

Tenia razon, y el numero lo confirma: el barrido anterior entra por
`calculate_total`, una funcion INTERNA, y se saltea `armar_presupuesto`, que es
la herramienta que el modelo llama. Ademas sus entradas son todas legitimas por
construccion. Los cinco defectos que Martin encontro en real el 12-ago venian
TODOS de una entrada torcida sobre una herramienta.

ESTE ARCHIVO CIERRA ESA PUERTA, y la cobertura no la declara nadie: la calcula
`banco_pruebas/barrido_entradas.py` leyendo los moldes Pydantic vivos. Si
mañana alguien agrega un campo a una herramienta, la cuenta baja de 100% y el
candado se pone rojo con el nombre exacto de lo que falta.

LAS CINCO PROPIEDADES, y ninguna compara contra un texto esperado:

  1. NUNCA EXPLOTA. Ninguna entrada, ni la mas absurda, puede hacer levantar a
     `ejecutar` ni devolver algo sin `estado`.
  2. LO VALIDO SE ATIENDE. Una entrada legitima no puede terminar en
     `pedido_mal_formado`: si pasa, o el molde es mas estricto de lo que el
     modelo puede cumplir, o el generador miente.
  3. NUNCA SE INVENTA UN PRODUCTO. Todo nombre que sale en un bloque existe en
     el catalogo real.
  4. LA PLATA CIERRA SIEMPRE. Todo bloque que lleva cuenta pasa los invariantes
     de aritmetica, venga de la entrada que venga.
  5. LO QUE NO SE ENTIENDE NO SE COBRA EN SILENCIO. Es la que Martin pidio con
     todas las letras: "si no entiende la pregunta tiene la salida de responder
     con una pregunta, o sea que no hay excusas". Aplicada a la maquina: una
     entrada TORCIDA que igual termina en una cuenta tiene que DECLARAR lo que
     supuso, o rechazar. Un `ok` mudo que cobra es el peor resultado posible,
     peor que un error.

CORRE OFFLINE Y GRATIS: doble local de Firestore con el catalogo y la FAQ
reales, cero llamadas al modelo, cero credenciales.
"""
import sys
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from banco_pruebas import barrido_entradas as B  # noqa: E402
from app.verifika import invariantes as INV  # noqa: E402

TIENDA = "verifika_prod"

# Los estados con los que una herramienta dice honestamente que no pudo. No son
# fallas: son la respuesta correcta a una entrada que no se puede resolver.
_HONESTOS = {"pedido_mal_formado", "no_encontrado", "no_se_pudo", "sin_items",
             "ambiguo", "herramienta_desconocida", "sin_datos", "vacio"}


@pytest.fixture(scope="module")
def barrido(firestore_doble):
    """Los 135 casos corridos UNA vez por `H.ejecutar`, que es exactamente por
    donde entra el modelo. Los tests de abajo leen de aca."""
    from app.core import herramientas as H
    from app.core.contexto_turno import set_current_tienda
    from app.core.estado_venta import set_current_estado
    from app.storage.firestore_client import get_all_products
    set_current_tienda(TIENDA)
    # UNO A LA VEZ mas DE A PARES sobre las herramientas que tocan plata: un
    # campo torcido solo suele caer en un rechazo limpio, y los errores de plata
    # viven en la interaccion de dos. El del 12-ago fue exactamente eso: un
    # destino compuesto MAS un reparto de pago.
    casos = B.casos() + B.pares()
    corridas = []
    for c in casos:
        # Estado limpio en cada caso: un barrido donde un caso le deja memoria
        # al siguiente no prueba lo que dice probar.
        set_current_estado({})
        try:
            r = H.ejecutar(c["herramienta"], c["args"], TIENDA)
            error = None
        except BaseException as e:  # noqa: BLE001 — eso es justo lo que se mide
            r, error = None, f"{type(e).__name__}: {str(e)[:200]}"
        corridas.append({**c, "resultado": r, "error": error})
    set_current_estado(None)
    vocabulario = {str(p.get("nombre") or "")
                   for p in get_all_products(tienda_id=TIENDA) if p.get("nombre")}
    return {"corridas": corridas, "casos": casos,
            "cobertura": B.cobertura(casos), "vocabulario": vocabulario}


def _bloques(corridas) -> list:
    """(caso, texto) de toda salida que le llegaria al cliente."""
    fuera = []
    for c in corridas:
        r = c.get("resultado") or {}
        for clave in ("bloque", "presentacion", "mensaje"):
            t = r.get(clave)
            if isinstance(t, str) and t.strip():
                fuera.append((c, t))
    return fuera


# ── EL CANDADO DE COBERTURA: el numero que nadie declara ────────────────────
def test_la_cobertura_de_la_superficie_es_completa(barrido):
    """EL CANDADO QUE PEDIO MARTIN. La superficie sale de los moldes vivos: si
    aparece un campo nuevo en una herramienta, o alguien saca los valores de uno
    que estaba, este test se pone rojo y NOMBRA lo que falta. 'Esta completo' o
    'le falta esto': no hay tercera opcion ni hace falta que nadie lo declare."""
    cob = barrido["cobertura"]
    assert not cob["pendientes"], (
        f"la superficie del modelo esta cubierta al {cob['porcentaje']}% "
        f"({cob['cubiertas']} de {cob['celdas']} celdas campo-por-clase). "
        f"Falta escribirle valores a:\n  " + "\n  ".join(cob["pendientes"][:20]))
    assert cob["porcentaje"] == 100.0


def test_el_barrido_no_se_apaga_solo(barrido):
    """La trampa del tablero verde que este repo ya pago: si el generador se
    apaga, todo lo de abajo pasa vacio y nadie se entera."""
    assert len(barrido["corridas"]) >= 340, (
        f"el barrido corrio {len(barrido['corridas'])} casos: se apago")
    assert any("+" in c["clase"] for c in barrido["corridas"]), (
        "no corrio ningun caso de dos campos torcidos a la vez")
    assert len(B.herramientas()) == 4, (
        "cambio la cantidad de herramientas internas: "
        "revisa que el barrido las cubra todas")


# ── LAS CINCO PROPIEDADES ───────────────────────────────────────────────────
def test_1_ninguna_entrada_hace_explotar_una_herramienta(barrido):
    """`ejecutar` promete no levantar nunca: un fallo vuelve como estado para
    que el turno siga. Aca se comprueba contra la entrada mas absurda."""
    rotas = [f"{c['herramienta']}.{c['campo']}[{c['clase']}]: {c['error']}"
             for c in barrido["corridas"] if c["error"]]
    assert not rotas, "estas entradas hicieron levantar la herramienta:\n  " + \
        "\n  ".join(rotas[:10])
    mudas = [f"{c['herramienta']}.{c['campo']}[{c['clase']}]"
             for c in barrido["corridas"]
             if not isinstance(c["resultado"], dict)
             or not (c["resultado"] or {}).get("estado")]
    assert not mudas, ("estas entradas devolvieron algo sin `estado`, que el "
                       "hub no puede contar honesto:\n  " + "\n  ".join(mudas[:10]))


def test_2_una_entrada_valida_no_se_rechaza(barrido):
    """Si el molde rechaza lo que el modelo puede mandar bien, el turno se cae
    por una razon que el cliente no puede arreglar."""
    malas = [f"{c['herramienta']}.{c['campo']}[{c['clase']}]"
             for c in barrido["corridas"]
             if c["clase"] in (B.VALIDO, B.BORDE)  # los pares no, llevan torcido
             and (c["resultado"] or {}).get("estado") in
             ("pedido_mal_formado", "error", "herramienta_desconocida")]
    assert not malas, ("estas entradas legitimas las rechazo el molde:\n  "
                       + "\n  ".join(malas[:10]))


def test_3_nunca_se_cotiza_un_producto_que_no_existe(barrido):
    """La regla cero, medida sobre toda la superficie: un id inventado no puede
    volverse un renglon con precio."""
    fallas = []
    for c, texto in _bloques(barrido["corridas"]):
        for f in INV.productos_del_catalogo(texto, barrido["vocabulario"]):
            fallas.append(f"{c['herramienta']}.{c['campo']}[{c['clase']}]: "
                          f"{f['detalle']}")
    assert not fallas, "\n  ".join(fallas[:10])


def test_4_la_plata_cierra_venga_de_donde_venga(barrido):
    """La aritmetica de todo bloque que sale, sobre las 135 entradas."""
    fallas = []
    for c, texto in _bloques(barrido["corridas"]):
        for f in INV.cuenta_cierra(texto) + INV.un_solo_total_por_concepto(texto):
            fallas.append(f"{c['herramienta']}.{c['campo']}[{c['clase']}]: "
                          f"{f['regla']} — {f['detalle']}")
    assert not fallas, "\n  ".join(fallas[:10])


def test_5_lo_que_no_se_entiende_no_se_cobra_en_silencio(barrido):
    """LA PROPIEDAD QUE PIDIO MARTIN, aplicada a la maquina.

    Una entrada TORCIDA es una que el sistema no puede resolver sin suponer:
    una cantidad en cero, un reparto de pago que no suma cien, un destino que
    son dos lugares. Si la herramienta igual devuelve una cuenta, tiene que
    DECIR que supuso algo o que algo quedo sin cerrar. Cobrar en silencio sobre
    una entrada que no se entendio es el peor resultado posible: el cliente no
    tiene como saber que le pasaron por encima.

    No se exige rechazar: para varias de esas entradas hay una lectura
    razonable, y frenar la venta seria peor. Se exige DECLARARLO."""
    from app.core.herramientas import TITULO_REPARTO
    marcas = ("supuse", "supuesto", "asumi", "decime", "aclarame", "confirmame",
              "no pude", "falta", "sin asignar", "no coincide", "revisa",
              "tene en cuenta", "por las dudas", TITULO_REPARTO.lower(),
              "lo puse por", "si va al reves")
    mudas = []
    for c in barrido["corridas"]:
        if B.TORCIDO not in c["clase"]:
            continue
        r = c["resultado"] or {}
        if r.get("estado") in _HONESTOS:
            continue           # dijo honestamente que no pudo: es correcto
        bloque = " ".join(str(r.get(k) or "") for k in
                          ("bloque", "presentacion", "mensaje", "motivo"))
        if not bloque.strip():
            continue           # no cobro nada: no hay silencio que castigar
        if not any(m in bloque.lower() for m in marcas):
            mudas.append(f"{c['herramienta']}.{c['campo']}: "
                         f"{str(c['args'])[:120]}\n      -> {bloque[:200]}")
    assert not mudas, (
        "estas entradas TORCIDAS terminaron en una cuenta que no declara nada "
        "de lo que supuso el codigo:\n    " + "\n    ".join(mudas[:8]))


# ── COHERENCIA ENTRE LO QUE SE COBRA Y LO QUE SE ESCRIBE ────────────────────
def test_el_reparto_solo_nombra_destinos_que_se_cotizaron(barrido):
    """Un reparto que nombra un lugar que no esta entre los cotizados le dice al
    cliente que su compra va a un lado y le cobra el envio de otro."""
    from app.core.herramientas import RENGLON_REPARTO
    import re
    fallas = []
    for c in barrido["corridas"]:
        r = c.get("resultado") or {}
        bloque = str(r.get("bloque") or "")
        if RENGLON_REPARTO.strip() not in bloque:
            continue
        cotizados = {str(e.get("localidad") or "").lower()
                     for e in (r.get("envios") or [])}
        if not cotizados:
            continue
        for m in re.finditer(r"^\s*" + re.escape(RENGLON_REPARTO.strip())
                             + r"\s+([^:]+):", bloque, re.MULTILINE):
            dest = m.group(1).strip().lower()
            if not any(dest in q or q in dest for q in cotizados if q):
                fallas.append(f"{c['herramienta']}.{c['campo']}[{c['clase']}]: "
                              f"el reparto nombra '{m.group(1).strip()}' y los "
                              f"envios cotizados son {sorted(cotizados)}")
    assert not fallas, "\n  ".join(fallas[:10])
