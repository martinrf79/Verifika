"""
EL BARRIDO DE LA COMPATIBILIDAD — 482 filas de fuente, por el camino que las
responde.

POR QUE EXISTE (Martin, 13-ago-2026): "hay respuestas juradas de compatibilidad
que, al ser muy importantes, tambien tienen que estar dentro de estos barridos".

Tenia razon. `compatibilidad.csv` tiene 482 filas y lo unico que las tocaba era
el barrido de COHERENCIA, que mira que el DATO no se contradiga. La RESPUESTA
—pasar los pares por `evaluar_par`, la funcion que contesta "¿esto le sirve a mi
equipo?"— no la barria nadie: solo unos pocos casos escritos a mano.

Contestar mal aca no es una respuesta fea: es una devolucion.

LAS PROPIEDADES, todas de negocio y ninguna comparando contra un texto:

  1. EL VEREDICTO ES UNO DE TRES. compatible, incompatible o sin_dato. Nada
     mas, y nunca vacio.
  2. ES SIMETRICO. Si A va con B, B va con A. Preguntar al reves no puede
     cambiar la respuesta.
  3. EL NO EXPLICITO MANDA. Si la fuente dice que A no es compatible con lo que
     B ES, el veredicto es incompatible, pase lo que pase con las familias.
  4. NO SE AFIRMA SIN EVIDENCIA. Sin ninguna arista que cruce, jamas
     "compatible": ahi va sin_dato, que es la respuesta honesta.
  5. CON EVIDENCIA NO SE ESCONDE. Si las aristas cruzan de verdad, no puede
     salir sin_dato: el dato esta en la fuente y hay que usarlo.
  6. NUNCA LEVANTA. Con un producto vacio, sin ficha o con basura.

UN APRENDIZAJE QUE QUEDA ESCRITO, porque costo una falsa alarma: la primera
version del generador marcaba como "negado" un mouse contra una placa de video
—la placa dice que no anda en notebook, el mouse dice que si anda en notebook— y
daba 60 defectos que no existian. `sin_dato` era el veredicto correcto. **Un
generador laxo inventa defectos**, y eso cuesta tanto como no encontrar los
reales. El criterio quedo estricto: negado es que uno declare no compatible lo
que el otro ES, no lo que el otro soporta.

CORRE OFFLINE Y GRATIS.
"""
import sys
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from banco_pruebas import barrido_compatibilidad as BC  # noqa: E402

TIENDA = BC.TIENDA


@pytest.fixture(scope="module")
def barrido(firestore_doble):
    from app.core.compatibilidad import evaluar_par, evaluar
    from app.core.contexto_turno import set_current_tienda
    set_current_tienda(TIENDA)
    pares = BC.pares()
    corridas = []
    for x in pares:
        try:
            ida = evaluar_par(x["a"], x["b"], TIENDA)
            vuelta = evaluar_par(x["b"], x["a"], TIENDA)
            error = None
        except BaseException as e:  # noqa: BLE001 — es justo lo que se mide
            ida = vuelta = (None, None)
            error = f"{type(e).__name__}: {str(e)[:160]}"
        corridas.append({**x, "ida": ida, "vuelta": vuelta, "error": error})
    plataformas = []
    for x in BC.contra_plataforma():
        try:
            r = evaluar(x["producto"], x["plataforma"], TIENDA)
            error = None
        except BaseException as e:  # noqa: BLE001
            r, error = (None, None), f"{type(e).__name__}: {str(e)[:160]}"
        plataformas.append({**x, "resultado": r, "error": error})
    return {"pares": corridas, "plataformas": plataformas,
            "cobertura": BC.cobertura()}


def _nom(c) -> str:
    return (f"{str(c['a'].get('nombre'))[:34]} vs "
            f"{str(c['b'].get('nombre'))[:34]} [{c['clase']}]")


# ── EL CANDADO: que el barrido no se apague y cubra la fuente ──────────────
def test_el_barrido_recorre_la_fuente_de_compatibilidad(barrido):
    cob = barrido["cobertura"]
    assert cob["productos_con_compat"] > 400, (
        f"solo {cob['productos_con_compat']} productos con compatibilidad "
        f"cargada: la fuente se quedo sin datos o el lector se rompio")
    assert cob["plataformas_cubiertas"] == cob["plataformas"], (
        f"quedaron plataformas sin barrer: {cob['plataformas_cubiertas']} de "
        f"{cob['plataformas']}")
    assert set(cob["clases"]) == {"cruzan", "ajenos", "mismo", "negados"}, (
        f"falta alguna clase de par: {cob['clases']}")
    assert len(barrido["pares"]) >= 200


# ── LAS SEIS PROPIEDADES ───────────────────────────────────────────────────
def test_1_el_veredicto_es_siempre_uno_de_los_tres(barrido):
    malos = [f"{_nom(c)}: {c['ida'][0]!r}" for c in barrido["pares"]
             if c["ida"][0] not in BC.VEREDICTOS]
    assert not malos, ("estos pares devolvieron un veredicto que no existe:\n  "
                       + "\n  ".join(malos[:8]))


def test_2_preguntar_al_reves_da_la_misma_respuesta(barrido):
    """Si A va con B, B va con A. Una asimetria significa que la respuesta
    depende de en que orden lo escribio el cliente, que es puro azar."""
    malos = [f"{_nom(c)}: ida {c['ida'][0]} / vuelta {c['vuelta'][0]}"
             for c in barrido["pares"] if c["ida"][0] != c["vuelta"][0]]
    assert not malos, "\n  ".join(malos[:8])


def test_3_el_no_explicito_de_la_fuente_manda(barrido):
    """Cuando la fuente dice que uno NO es compatible con lo que el otro ES, no
    hay cruce de familias que valga. Es el caso de la memoria de escritorio
    contra la notebook: por familias daba sin_dato y hay que negarlo sin dudar."""
    malos = [f"{_nom(c)}: {c['ida'][0]}" for c in barrido["pares"]
             if c["clase"] == "negados" and c["ida"][0] != "incompatible"]
    assert not malos, ("la fuente los declara no compatibles y el veredicto no "
                       "lo dice:\n  " + "\n  ".join(malos[:8]))


def test_4_sin_evidencia_nunca_se_afirma_compatible(barrido):
    """La regla cero de este repo, en el eje de compatibilidad: sin una arista
    que cruce, el honesto es sin_dato. Un 'si' de compromiso es el que termina
    en devolucion."""
    malos = [f"{_nom(c)}: {c['ida'][0]}" for c in barrido["pares"]
             if c["clase"] == "ajenos" and c["ida"][0] == "compatible"]
    assert not malos, ("afirmo compatible sin ninguna arista que lo respalde:\n"
                       "  " + "\n  ".join(malos[:8]))


def test_5_con_evidencia_no_se_esconde_en_sin_dato(barrido):
    """El otro lado: si las aristas cruzan de verdad, el dato esta en la fuente
    y hay que usarlo. Contestar sin_dato teniendolo es perder la venta con la
    respuesta en la mano."""
    malos = [f"{_nom(c)}: cruza {c.get('familias')} y contesto {c['ida'][0]}"
             for c in barrido["pares"]
             if c["clase"] == "cruzan" and c["ida"][0] == "sin_dato"]
    assert not malos, "\n  ".join(malos[:8])


def test_6_nunca_levanta_ni_con_un_producto_roto(barrido, firestore_doble):
    from app.core.compatibilidad import evaluar_par, evaluar
    rotas = [f"{_nom(c)}: {c['error']}" for c in barrido["pares"] if c["error"]]
    rotas += [f"{x['plataforma']}: {x['error']}"
              for x in barrido["plataformas"] if x["error"]]
    assert not rotas, "\n  ".join(rotas[:8])
    # Y con basura de entrada, que es lo que un id inventado deja llegar.
    for a, b in (({}, {}), ({"nombre": "x"}, {}), (None, {"nombre": "y"}),
                 ({"nombre": None, "categoria": 7}, {"id": "ZZZ9999"})):
        v, _m = evaluar_par(a or {}, b or {}, TIENDA)
        assert v in BC.VEREDICTOS
    for p in ({}, {"nombre": "x"}, {"categoria": None}):
        r = evaluar(p, "play 5", TIENDA)
        assert isinstance(r, tuple) and r[0] in BC.VEREDICTOS


# ── EL OTRO EJE: producto contra plataforma generica ───────────────────────
def test_contra_plataforma_no_afirma_lo_que_la_ficha_no_dice(barrido):
    """"¿Sirve para la Play 5?" es la forma en que el cliente pregunta esto de
    verdad. Si la ficha no declara esa plataforma, el veredicto no puede ser
    compatible: seria inventar sobre la fuente."""
    from app.core.compatibilidad import compat_de
    malos = []
    for x in barrido["plataformas"]:
        veredicto = x["resultado"][0]
        assert veredicto in BC.VEREDICTOS, f"{x['plataforma']}: {veredicto!r}"
        if veredicto != "compatible":
            continue
        declaradas = {str(p).strip().lower()
                      for p in (compat_de(x["producto"], TIENDA)
                                .get("plataformas") or [])}
        if str(x["plataforma"]).strip().lower() not in declaradas:
            malos.append(f"{str(x['producto'].get('nombre'))[:36]} + "
                         f"{x['plataforma']}: dijo compatible y la ficha "
                         f"declara {sorted(declaradas)}")
    assert not malos, "\n  ".join(malos[:8])
