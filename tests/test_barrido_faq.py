"""
EL BARRIDO DE LA FAQ — la tercera fuente, y la que faltaba.

QUE SE BARRE ACA. El catalogo se barre pasando cada producto por el
certificador; la FAQ no se puede barrer asi, porque desde el 2-ago el ruteo de
un tema no lo hace un regex nuestro sino el MODELO, eligiendo del enum de
`consultar_temas`. Entonces lo que se barre es la unica ayuda determinista que
el modelo tiene para elegir: `_guia_de_temas`, la seña que viaja en el esquema.

LA PREGUNTA DEL BARRIDO, y sale de la fuente entera: por cada palabra con la que
el cliente puede nombrar un tema -las keywords de `faq.json` mas los
disparadores de `base_conocimiento.json`-, ¿puede el modelo saber a QUE tema
mandarla? Si dos temas reclaman la misma palabra y la guia describe a uno solo,
no puede: tiene que adivinar. Y elegir mal ahi no es un matiz, es que el bot
afirme una politica que no es la que preguntaron, que es la peor forma de
alucinar porque suena bien y viene de la fuente.

EL ANTES Y EL DESPUES, medido el 12-ago sobre las 880 señas de la fuente real:

                                        ANTES      DESPUES
    palabras que reclaman 2+ temas        32          32
    de esas, que el modelo debe adivinar  31           0
    temas que la guia describe            32          77
    largo de la guia, por llamada      2.282      3.843 caracteres

LAS DOS CAUSAS, las dos en el mismo `if` de dos lineas:

  1. LA FRONTERA SE MEDIA POR EL NOMBRE. Se consideraba que un tema podia
     confundirse con otro si compartian una raiz de su NOMBRE. Los 31 choques
     ciegos son dos temas que reclaman la misma palabra del cliente y se llaman
     distinto: 'direccion' la piden `cambio_direccion` y `ubicacion`, 'no
     funciona' la piden `defectuoso` y `producto_defectuoso`, 'iva' la piden
     `factura` y `precios_iva`. El nombre no los delata; la palabra del cliente
     si, y es un dato que ya estaba escrito en la fuente y no lo leia nadie.
  2. SE MIRABA MEDIA CASA. El filtro `tema not in faq` dejaba afuera a toda la
     base de conocimiento, que es justo la mitad contra la que choca la FAQ: en
     27 de los 31, el tema que se quedaba sin seña era el de la base.

LO QUE NO SE TOCO: el criterio viejo por raiz de nombre sigue vivo y se le SUMA
el nuevo, no lo reemplaza. La familia `envios` / `envio_exterior` /
`costo_envio` / `plazo_envio`, que es el error medido el 3-ago que hizo nacer la
guia, se sigue cubriendo por donde se cubria.

EL COSTO ESTA MEDIDO Y ES A PROPOSITO. La guia viaja en el esquema de CADA
llamada al decisor, asi que cada palabra se paga por turno. Cubrir el doble de
temas costo mil quinientos caracteres mas, y se los acoto de dos maneras: se
eligen DOS señas por tema y no tres, y va primero la que DISTINGUE -describir un
tema con una palabra que su vecino tambien reclama no desempata nada-.
"""
import collections
import re

import pytest

TIENDA = "verifika_prod"

# PESADO: recorre la fuente entera. Corre normal en el push; queda fuera de
# la pasada de cobertura del mapa, donde el tracing lo vuelve horas.
pytestmark = pytest.mark.pesado



@pytest.fixture(scope="module")
def fuente(firestore_doble):
    from app.core.contexto_turno import set_current_tienda
    from app.core.guia_venta_prosa import disparadores_de
    from app.core.herramientas import _norm, temas_consultables
    from app.storage.firestore_client import get_all_faq

    set_current_tienda(TIENDA)
    temas = temas_consultables(TIENDA)
    faq = get_all_faq(tienda_id=TIENDA)
    reclaman = collections.defaultdict(set)
    for t in temas:
        for k in list((faq.get(t) or {}).get("keywords") or []) + list(disparadores_de(t)):
            n = _norm(k).strip()
            if n:
                reclaman[n].add(t)
    return {"temas": temas, "faq": faq, "reclaman": dict(reclaman)}


def _descritos_por_la_guia(fuente) -> set:
    """Los temas que la guia del esquema realmente nombra. Se lee del TEXTO que
    viaja al modelo, no de la variable interna: es la misma regla de tau-bench
    que usa el resto del repo — se juzga por lo observado, no por lo que el
    codigo cuenta que hizo."""
    from app.core.herramientas import _guia_de_temas

    guia = _guia_de_temas(fuente["faq"], fuente["temas"])
    return set(re.findall(r"([a-z_]+) \(", guia))


def test_ninguna_palabra_del_cliente_queda_sin_desambiguar(fuente):
    """EL BARRIDO. Por cada palabra que dos o mas temas reclaman, la guia tiene
    que describir a TODOS los que la reclaman. Si describe a uno solo, el modelo
    no tiene con que elegir y adivina.

    Es la prueba generada desde la fuente: no hay un solo caso escrito a mano,
    los da `faq.json` mas `base_conocimiento.json`. Sumar un tema nuevo que pise
    una palabra ya usada pone esto en rojo el mismo dia, y no seis semanas
    despues por una politica equivocada que le llego a un cliente."""
    descritos = _descritos_por_la_guia(fuente)
    choques = {k: v for k, v in fuente["reclaman"].items() if len(v) > 1}
    assert choques, "el barrido se quedo sin casos: revisar keywords y disparadores"
    ciegos = {k: sorted(v) for k, v in choques.items()
              if not all(t in descritos for t in v)}
    assert not ciegos, (
        f"{len(ciegos)} de {len(choques)} palabras que el modelo tiene que "
        f"adivinar, p.ej. {dict(list(ciegos.items())[:5])}")


def test_la_guia_no_se_desborda(fuente):
    """PISO Y TECHO, porque esto se paga en CADA llamada al decisor.

    El techo evita que cubrir un tema nuevo devuelva la guia al tamaño que ya se
    recorto una vez a proposito: describir los 129 temas costaba once mil
    caracteres, mas que las dos herramientas que esto reemplazo juntas. El piso
    evita lo contrario, que un refactor la deje muda sin que nadie lo note —
    que es exactamente como estuvo media guia hasta hoy."""
    from app.core.herramientas import _guia_de_temas

    guia = _guia_de_temas(fuente["faq"], fuente["temas"])
    assert 3000 < len(guia) < 6000, f"la guia mide {len(guia)} caracteres"


def test_la_seña_que_distingue_va_primero(fuente):
    """Describir un tema con una palabra que su vecino TAMBIEN reclama no
    desempata nada: si `cuotas` y `cuotas_financiacion` piden las dos
    'financiacion', esa palabra no le dice al modelo cual elegir. La propia si.

    Se exige sobre los temas que TIENEN alguna seña propia; el que solo tiene
    palabras compartidas se describe igual con las que hay, porque decir algo es
    mejor que no decir nada."""
    from app.core.guia_venta_prosa import disparadores_de
    from app.core.herramientas import _guia_de_temas, _norm

    guia = _guia_de_temas(fuente["faq"], fuente["temas"])
    emitidas = dict(re.findall(r"([a-z_]+) \(([^)]*)\)", guia))
    sin_propia_primero = []
    for tema, texto in emitidas.items():
        propias_disponibles = [
            k for k in (list((fuente["faq"].get(tema) or {}).get("keywords") or [])
                        + list(disparadores_de(tema)))
            if k and len(fuente["reclaman"].get(_norm(k).strip(), ())) == 1
            and not set(_norm(k).split()) <= set(_norm(tema).replace("_", " ").split())
        ]
        if not propias_disponibles:
            continue
        primera = texto.split(",")[0].strip()
        if len(fuente["reclaman"].get(_norm(primera).strip(), ())) > 1:
            sin_propia_primero.append((tema, primera))
    assert not sin_propia_primero, (
        f"temas descritos con una palabra compartida teniendo una propia: "
        f"{sin_propia_primero[:5]}")


def test_todo_tema_del_enum_se_puede_nombrar(fuente):
    """El otro borde de la misma pregunta: un tema que entra al enum y no tiene
    NINGUNA palabra con la que el cliente lo pueda nombrar es un tema que nunca
    se va a consultar. No es un error del codigo, es un hueco de la fuente, y
    por eso se lockea con nombre: `varias_preguntas` es de conduccion, no lo
    nombra un cliente, y es el unico que puede estar asi."""
    from app.core.guia_venta_prosa import disparadores_de

    mudos = [t for t in fuente["temas"]
             if not (list((fuente["faq"].get(t) or {}).get("keywords") or [])
                     + list(disparadores_de(t)))]
    assert mudos == ["varias_preguntas"], (
        f"cambio la lista de temas que ninguna palabra nombra: {mudos}")
