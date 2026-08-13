"""
EL BARRIDO DE LOS FILTROS — 205 celdas de campo por operador, por el codigo que
las contesta.

POR QUE EXISTE, con su caso (Martin, 12-ago-2026): probo en WhatsApp por la
garantia y el bot no contesto con la garantia, con `garantia_meses` cargado en
los 880 productos. El dato estaba; lo que no habia era nadie que barriera el
cruce entre la CONDICION del cliente y la ficha.

Y atras estaba el reclamo de fondo, textual: "si con cada nueva pregunta hay que
hacer un arreglo nuevo, el bot no razona". Esto es la respuesta: la grilla de lo
que se puede preguntar sobre un atributo es finita —41 campos por 5 operadores—
y se barre entera, con valores sacados de la ficha misma. Una pregunta nueva cae
adentro de una celda ya probada.

LAS PROPIEDADES, todas de negocio y ninguna comparando contra un texto grabado:

  1. NINGUNA CONDICION EXPLOTA, ni la torcida.
  2. NADA SE PIERDE EN SILENCIO. Toda condicion sale aplicada o descartada CON
     MOTIVO. Un filtro que desaparece es peor que uno que falla: el modelo cree
     que se aplico y afirma sobre algo que nadie verifico.
  3. EL QUE PASA, CUMPLE. Todo producto que sobrevive satisface la condicion
     contra su ficha. Es la unica forma de que el bot no venda lo que no cumple.
  4. EL SILENCIO NO ES UN SI. Un producto sin el dato nunca sobrevive.
  5. EL VALOR DE LA FICHA VUELVE A SU FICHA. La mas fuerte, y la que atrapa la
     forma del error de la garantia: si `Negro` esta escrito en un producto y se
     pregunta por `color contiene Negro`, ESE producto tiene que volver. Cuando
     no vuelve, el filtro da cero y el bot dice que no hay con el dato en la
     mano.
  6. `no_contiene` SACA LO QUE `contiene` TRAE. Son complementarios sobre los
     que tienen el dato: si no, "no quiero chino" no significa nada.
  7. COMPARAR ES MONOTONO. `menor 100` no puede traer mas que `menor 200`.
  8. CUANDO NO QUEDA NINGUNO, EL CODIGO SABE DECIR CUAL FALLO. La regla dura de
     este repo —ninguna herramienta devuelve vacio— con su evidencia: el
     ranking por cercania trae algo y nombra la condicion incumplida.

CORRE OFFLINE Y GRATIS: catalogo real, cero llamadas al modelo.
"""
import sys
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from banco_pruebas import barrido_filtros as BF  # noqa: E402

TIENDA = BF.TIENDA


class _Cond:
    """Una condicion suelta, con la misma forma que el molde Pydantic.

    Se usa un objeto propio a proposito: el molde `Filtro` ata `operador` a un
    Literal, asi que un operador desconocido no se puede ni construir. Eso esta
    bien arriba y no alcanza abajo: el codigo tiene que aguantar igual, porque
    `aplicar` tambien la recibe de la reposicion y del reconciliador, que no
    pasan por el molde."""

    def __init__(self, campo, operador, valor):
        self.campo, self.operador, self.valor = campo, operador, valor

    def __repr__(self):
        return f"{self.campo} {self.operador} {self.valor!r}"


@pytest.fixture(scope="module")
def catalogo(firestore_doble):
    return BF._productos(TIENDA)


@pytest.fixture(scope="module")
def barrido(firestore_doble, catalogo):
    from app.core.filtros_catalogo import aplicar
    corridas = []
    for c in BF.casos():
        cond = _Cond(c["campo"], c["operador"], c["valor"])
        try:
            r = aplicar(catalogo, [cond], TIENDA)
            error = None
        except BaseException as e:  # noqa: BLE001 — es justo lo que se mide
            r, error = None, f"{type(e).__name__}: {str(e)[:160]}"
        corridas.append({**c, "cond": cond, "r": r, "error": error})
    return corridas


def _ids(r) -> set:
    return {p.get("id") for p in (r or {}).get("productos") or []}


def _nom(c) -> str:
    return f"{c['campo']} {c['operador']} {str(c['valor'])[:34]!r}"


# ── EL CANDADO: que el barrido cubra la grilla entera ──────────────────────
def test_el_barrido_cubre_la_grilla_entera(firestore_doble):
    """La superficie sale del catalogo vivo. Si mañana la fuente suma una
    columna, esto baja solo y lo dice en el mismo push, que es lo contrario de
    enterarse tres sesiones despues."""
    cob = BF.cobertura()
    assert cob["cobertura"] == 100.0, (
        f"quedaron celdas sin barrer: {cob['pendientes'][:12]}")
    assert cob["campos"] > 30, (
        f"solo {cob['campos']} campos filtrables: el registro se deriva del "
        f"catalogo y algo lo dejo flaco")
    assert cob["celdas"] == cob["campos"] * cob["operadores"]


# ── LAS OCHO PROPIEDADES ───────────────────────────────────────────────────
def test_1_ninguna_condicion_explota(barrido, catalogo, firestore_doble):
    from app.core.filtros_catalogo import aplicar
    rotas = [f"{_nom(c)}: {c['error']}" for c in barrido if c["error"]]
    for t in BF.torcidos():
        try:
            aplicar(catalogo, [_Cond(t["campo"], t["operador"], t["valor"])],
                    TIENDA)
        except BaseException as e:  # noqa: BLE001
            rotas.append(f"{t['porque']}: {type(e).__name__}: {str(e)[:120]}")
    assert not rotas, "\n  ".join(rotas[:8])


def test_2_nada_se_pierde_en_silencio(barrido, catalogo, firestore_doble):
    """Toda condicion sale por una de las dos puertas: aplicada, o descartada
    con el motivo escrito. La tercera —desaparecer— es la peor de las tres,
    porque el modelo la da por cumplida."""
    from app.core.filtros_catalogo import aplicar
    perdidas = []
    for c in barrido:
        r = c["r"] or {}
        if len(r.get("aplicados") or []) + len(r.get("descartados") or []) != 1:
            perdidas.append(_nom(c))
    for t in BF.torcidos():
        r = aplicar(catalogo, [_Cond(t["campo"], t["operador"], t["valor"])],
                    TIENDA)
        d = r.get("descartados") or []
        if len(d) + len(r.get("aplicados") or []) != 1:
            perdidas.append(f"[torcido] {t['porque']}")
            continue
        if d and not str(d[0].get("motivo") or "").strip():
            perdidas.append(f"[torcido sin motivo] {t['porque']}")
    assert not perdidas, ("estas condiciones no salieron ni aplicadas ni "
                         "descartadas con motivo:\n  " + "\n  ".join(perdidas[:8]))


def test_3_el_que_pasa_el_filtro_lo_cumple(barrido, firestore_doble):
    """Contra la ficha, uno por uno. Si un producto pasa sin cumplir, el bot lo
    ofrece como si cumpliera: es la venta de algo que no es."""
    from app.core.filtros_catalogo import evaluar
    malos = []
    for c in barrido:
        r = c["r"] or {}
        if not r.get("aplicados"):
            continue
        for p in r["productos"][:40]:
            if evaluar(p, c["campo"], c["operador"], c["valor"],
                       c["tipo"]) is not True:
                malos.append(f"{_nom(c)}: paso {str(p.get('nombre'))[:34]} y "
                             f"su ficha dice {str(p.get(c['campo']))[:40]!r}")
                break
    assert not malos, "\n  ".join(malos[:8])


def test_4_el_silencio_no_es_un_si(barrido, firestore_doble):
    """Un producto sin el dato no cumple ni incumple: no se sabe. Nunca puede
    colarse en el resultado, y la cuenta de `sin_dato` tiene que cerrar contra
    los evaluados."""
    from app.core.filtros_catalogo import evaluar
    malos = []
    for c in barrido:
        r = c["r"] or {}
        for a in (r.get("aplicados") or []):
            if a["quedaron"] + a["sin_dato"] > a["evaluados"]:
                malos.append(f"{_nom(c)}: {a['quedaron']} + {a['sin_dato']} "
                             f"sin dato sobre {a['evaluados']} evaluados")
        # Solo si la condicion se APLICO. Cuando se descarta -y descartarla es
        # lo correcto para `mayor` sobre un campo de texto- la lista vuelve
        # intacta, asi que mirar quien sobrevivio ahi no mide nada: mide la
        # entrada. La primera version de esta prueba no lo distinguia y
        # reportaba 200 defectos que no existian.
        if not r.get("aplicados"):
            continue
        for p in (r.get("productos") or [])[:40]:
            if evaluar(p, c["campo"], c["operador"], c["valor"],
                       c["tipo"]) is None:
                malos.append(f"{_nom(c)}: paso {str(p.get('nombre'))[:34]} y su "
                             f"ficha no dice nada de {c['campo']}")
                break
    assert not malos, "\n  ".join(malos[:8])


def test_5_el_valor_de_la_ficha_vuelve_a_su_ficha(barrido, firestore_doble):
    """LA PROPIEDAD FUERTE, y la forma exacta del error de la garantia: el dato
    esta cargado, el cliente pregunta por el, y el filtro devuelve cero.

    Se pregunta por un valor que se leyo de un producto REAL, asi que hay una
    respuesta correcta conocida sin escribir ninguna: ese producto. Si no
    vuelve, la herramienta contesta que no hay y el bot le dice que no al
    cliente teniendo el producto en gondola."""
    malos = []
    for c in barrido:
        if c["espera"] != "trae_al_testigo" or c["error"]:
            continue
        r = c["r"] or {}
        if not r.get("aplicados"):
            malos.append(f"{_nom(c)}: la condicion ni se aplico "
                         f"({r.get('descartados')})")
            continue
        if c["testigo"] not in _ids(r):
            malos.append(
                f"{_nom(c)}: el valor salio de {c['testigo']} y ese producto "
                f"NO volvio ({len(r['productos'])} resultados)")
    assert not malos, ("el dato esta en la ficha y el filtro no lo encuentra:\n"
                       "  " + "\n  ".join(malos[:10]))


def test_6_no_contiene_saca_lo_que_contiene_trae(barrido, firestore_doble):
    """Complementarios sobre los que tienen el dato. Sin esto "no quiero marca
    china" no significa nada, y es la condicion que mas cuesta cuando falla:
    filtrar al reves es peor que no filtrar."""
    from app.core.filtros_catalogo import aplicar
    malos = []
    for c in barrido:
        if c["espera"] != "excluye_al_testigo" or c["error"]:
            continue
        if c["testigo"] in _ids(c["r"]):
            malos.append(f"{_nom(c)}: el valor salio de {c['testigo']} y "
                         f"no_contiene igual lo dejo pasar")
    # Y el complemento como conjunto, sobre una muestra de campos de texto.
    vistos = set()
    for c in barrido:
        if c["operador"] != "contiene" or c["tipo"] != "texto":
            continue
        if c["campo"] in vistos or c.get("como_pregunta_el_cliente"):
            continue
        vistos.add(c["campo"])
        cruce = _ids(c["r"]) & _ids(aplicar(
            BF._productos(TIENDA),
            [_Cond(c["campo"], "no_contiene", c["valor"])], TIENDA))
        if cruce:
            malos.append(f"{_nom(c)}: {len(cruce)} productos cumplen contiene "
                         f"Y no_contiene el mismo valor")
    assert not malos, "\n  ".join(malos[:8])


def test_7_comparar_es_monotono(catalogo, firestore_doble):
    """`menor 100` no puede traer mas que `menor 200`. Es la unica forma de que
    un presupuesto signifique algo: si el orden se rompe, "hasta 100 mil" puede
    devolver cosas que "hasta 200 mil" no devuelve."""
    from app.core.filtros_catalogo import aplicar
    malos = []
    for campo, tipo in BF.campos().items():
        if tipo != "numero":
            continue
        vals = sorted({v for v in (BF._valor_de_numero(p, campo)
                                   for p in catalogo) if v is not None})
        if len(vals) < 3:
            continue
        bajo, medio, alto = vals[0], vals[len(vals) // 2], vals[-1]
        for a, b in ((bajo, medio), (medio, alto)):
            chico = _ids(aplicar(catalogo, [_Cond(campo, "menor", str(a))],
                                 TIENDA))
            grande = _ids(aplicar(catalogo, [_Cond(campo, "menor", str(b))],
                                  TIENDA))
            if not chico <= grande:
                malos.append(f"{campo} menor {a} trae "
                             f"{len(chico - grande)} que menor {b} no trae")
            arriba = _ids(aplicar(catalogo, [_Cond(campo, "mayor", str(b))],
                                  TIENDA))
            abajo = _ids(aplicar(catalogo, [_Cond(campo, "mayor", str(a))],
                                 TIENDA))
            if not arriba <= abajo:
                malos.append(f"{campo} mayor {b} trae "
                             f"{len(arriba - abajo)} que mayor {a} no trae")
    assert not malos, "\n  ".join(malos[:8])


def test_8_cuando_no_queda_ninguno_el_codigo_dice_cual_fallo(catalogo,
                                                             firestore_doble):
    """NINGUNA HERRAMIENTA DEVUELVE VACIO (Martin, 2-ago), con la evidencia al
    lado: cuando el conjunto de condiciones no deja nada, el ranking por
    cercania trae algo, dice cuantos empatan y NOMBRA la condicion incumplida
    con el dato real de la ficha. Sin eso nace el muro: "no tenemos"."""
    from app.core.filtros_catalogo import (aplicar, rankear_por_cercania,
                                           incumplidos, dato_que_falla)
    # Condiciones que sabemos imposibles JUNTAS, armadas con valores de la
    # fuente: dos colores distintos del mismo producto no existen.
    reg = BF.campos()
    imposibles = []
    for campo, tipo in reg.items():
        vals = BF.valores_de(campo, catalogo)
        if tipo == "texto" and len(vals) >= 2:
            imposibles.append([_Cond(campo, "igual", vals[0]["valor"]),
                               _Cond(campo, "igual", vals[-1]["valor"])])
        if tipo == "numero" and len(vals) >= 2:
            nums = sorted(float(str(v["valor"]).replace(",", "."))
                          for v in vals)
            if nums[0] != nums[-1]:
                imposibles.append([_Cond(campo, "mayor", str(nums[-1])),
                                   _Cond(campo, "menor", str(nums[0]))])
    assert imposibles, "no se pudo armar ni un conjunto imposible de la fuente"
    mudos = []
    for conds in imposibles[:25]:
        r = aplicar(catalogo, conds, TIENDA)
        if r["productos"]:
            continue                       # no era imposible, no prueba nada
        cercanos, empatados, faltan = rankear_por_cercania(catalogo, conds,
                                                           TIENDA)
        if not cercanos:
            mudos.append(f"{conds}: nada cumple y el rescate tambien vino vacio")
            continue
        p = cercanos[0]
        if not incumplidos(p, conds, TIENDA):
            mudos.append(f"{conds}: no cumple y no sabe decir cual condicion")
        if not str(dato_que_falla(p, conds, TIENDA)).strip():
            mudos.append(f"{conds}: no puede mostrar el dato real que falla")
        if empatados < 1:
            mudos.append(f"{conds}: no informa el empate")
    assert not mudos, "\n  ".join(mudos[:8])


# ── LA PUERTA REAL: la herramienta que el modelo llama ─────────────────────
def test_la_condicion_entra_por_la_puerta_de_produccion(firestore_doble,
                                                        catalogo):
    """Los ocho de arriba prueban el motor. Este prueba que el motor este
    ENCHUFADO: la misma condicion, pero pedida como la pide el modelo, por
    `buscar_productos`. Un barrido que no entra por la puerta de produccion
    mide una copia, y este repo ya pago ese error.

    Lo que se exige es lo minimo que no puede fallar: con una condicion sacada
    de la ficha de un producto de esa categoria, la herramienta NO puede
    contestar que no hay nada."""
    from app.core.herramientas import buscar_productos, BuscarProductos, Filtro
    from app.core.filtros_catalogo import _valor_crudo
    malos = []
    probados = 0
    for campo, tipo in BF.campos().items():
        if tipo != "texto" or campo in ("nombre", "descripcion"):
            continue
        testigo = next((p for p in catalogo
                        if _valor_crudo(p, campo) not in (None, "", [], {})
                        and (p.get("stock") or 0) > 0), None)
        if not testigo:
            continue
        valor = str(_valor_crudo(testigo, campo))[:60]
        r = buscar_productos(BuscarProductos(
            categoria=testigo.get("categoria"),
            filtros=[Filtro(campo=campo, operador="contiene", valor=valor)]),
            TIENDA)
        probados += 1
        if r.get("estado") in ("no_encontrado", "no_vendemos"):
            malos.append(f"{campo} contiene {valor[:30]!r} sobre "
                         f"{testigo.get('categoria')}: estado {r['estado']}")
        elif not r.get("productos"):
            malos.append(f"{campo} contiene {valor[:30]!r}: sin productos")
    assert probados >= 20, f"solo se probaron {probados} campos por la puerta"
    assert not malos, "\n  ".join(malos[:8])
