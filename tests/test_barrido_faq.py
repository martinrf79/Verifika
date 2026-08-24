"""
EL BARRIDO DE LA FAQ — la tercera fuente, y la que faltaba.

QUE SE BARRE ACA. El catalogo se barre pasando cada producto por el
certificador; la FAQ no se puede barrer asi, porque desde el 2-ago el ruteo de
un tema no lo hace un regex nuestro sino el MODELO, eligiendo del enum de
`consultar_temas`. Entonces lo que se barre es la unica ayuda determinista que
el modelo tiene para elegir. Hasta el 23-ago eso era `_guia_de_temas`, la seña
que viajaba en el esquema; desde la FICHA 06 el modelo nombra el tema con las
palabras del cliente y lo resuelve `certificar_tema`, con las MISMAS señas, del
lado del codigo. La pregunta del barrido no cambio; lo que cambio es que ahora
se puede medir el RESULTADO -a que tema llega cada palabra- y no la pista.

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


def test_ninguna_palabra_del_cliente_queda_sin_desambiguar(fuente):
    """EL BARRIDO. Por cada palabra que dos o mas temas reclaman, la
    certificacion tiene que servir a TODOS los que la reclaman. Si sirve a uno
    solo, el otro no llega nunca y el bot contesta la politica que no era.

    QUE CAMBIO EL 23-AGO (FICHA 06) Y QUE NO. La pregunta es la misma; lo que
    cambio es QUIEN la contesta y por lo tanto QUE se puede medir. Antes el
    enum lo elegia el modelo y lo unico observable era si la guia del esquema
    NOMBRABA los dos temas; ahora elige `certificar_tema`, asi que se mide el
    resultado y no la pista: a que tema llega de verdad cada palabra de la
    fuente. Es la misma regla de tau-bench del resto del repo, un paso mas
    cerca de lo observado.

    Y CERRO CUATRO CHOQUES QUE ESTABAN ABIERTOS -`cuotas` contra
    `cuotas_financiacion`, `regalo` contra `envoltorio_regalo`, `envios` contra
    `envio_zonas`, `devoluciones` contra `cambios_devoluciones`-: ante empate no
    se elige, se sirven los dos, y el modelo contesta con las dos politicas
    enteras delante."""
    from app.core.herramientas import certificar_tema

    choques = {k: v for k, v in fuente["reclaman"].items() if len(v) > 1}
    assert choques, "el barrido se quedo sin casos: revisar keywords y disparadores"
    ciegos = {}
    for k, v in choques.items():
        servidos = certificar_tema(k, TIENDA)["temas"]
        if not all(t in servidos for t in v):
            ciegos[k] = (sorted(v), servidos)
    assert not ciegos, (
        f"{len(ciegos)} de {len(choques)} palabras donde la certificacion deja "
        f"afuera a un tema que la reclama, p.ej. {dict(list(ciegos.items())[:5])}")


def test_toda_seña_de_la_fuente_llega_a_su_tema(fuente):
    """EL BARRIDO ENTERO, no solo los choques: las 785 señas, una por una.

    Una seña que vuelve `not_found` es un agujero por el que el cliente pregunta
    algo que la casa TIENE escrito y no se le sirve. Se toleran las que no
    tienen ni una palabra propia -'ese no', 'uno a', 'es para'-: son muletillas
    que la fuente guardo como disparador y no hay con que resolverlas; el numero
    esta clavado para que sumar una mas se vea."""
    from app.core.herramientas import certificar_tema, _fichas

    sin_ficha = [k for k in fuente["reclaman"] if not _fichas(k)]
    perdidas = [k for k in fuente["reclaman"]
                if _fichas(k)
                and certificar_tema(k, TIENDA)["veredicto"] == "not_found"]
    assert not perdidas, (
        f"{len(perdidas)} señas de la fuente no llegan a ningun tema: "
        f"{perdidas[:8]}")
    assert len(sin_ficha) <= 12, (
        f"{len(sin_ficha)} señas sin una sola palabra propia: {sin_ficha}")


def test_la_certificacion_no_desborda_de_candidatos(fuente):
    """PISO Y TECHO, y ahora se paga en la FUENTE y no en el esquema.

    La guia vieja costaba 3.843 caracteres en CADA llamada al decisor. La
    certificacion cuesta cero: no viaja nada. Lo que si tiene precio es servir
    de mas —cada tema son varios parrafos de politica en el prompt del
    redactor—, asi que se mide el promedio de candidatos por seña. Uno seria
    perfecto y no se puede: la fuente tiene 32 palabras que dos temas reclaman."""
    from app.core.herramientas import certificar_tema

    servidos = [len(certificar_tema(k, TIENDA)["temas"])
                for k in fuente["reclaman"]]
    promedio = sum(servidos) / len(servidos)
    assert 1.0 <= promedio <= 1.6, f"promedio de {promedio:.2f} temas por seña"
    assert max(servidos) <= 3, "la certificacion sirve mas de tres temas juntos"
