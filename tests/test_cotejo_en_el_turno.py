"""
AREA: EL COTEJO CABLEADO — que las cinco comprobaciones esten en el camino
vivo del turno y no solo en su modulo.

POR QUE HACE FALTA ADEMAS DE `test_cotejo.py`. Aquel mide la PIEZA: que una
copia se reconozca y que un techo inventado se degrade. Este mide el CABLE: que
lo que sale corregido sea lo que de verdad le llega al motor, que el aviso
llegue al prompt de la vuelta siguiente, y que los numeros terminen en el
informe del turno, que es de donde los lee produccion. Una pieza correcta sin
cable es la FICHA 51 entera: el fantasma de algo que parece estar enchufado.

El doble del modelo es el mismo de `test_renglon_y_total`, importado de ahi y
no copiado: tres copias del mismo cliente falso es lo que el bloque 0 de
CLAUDE.md prohibe.
"""
import asyncio

from app.core import motor as MT
from app.core import respuesta as R
from tests.test_renglon_y_total import _Call, _ClienteFalso, _Msg

TIENDA = "verifika_prod"

# Los dos mensajes reales que destaparon los casos, por Telegram el 22-sep.
M1 = ("Dame precio de dos auriculares, dos mouse y dos memorias. El precio no "
      "sería tan importante. Lo que sí que necesito que lleven las menos "
      "partes chinas posibles. Un auricular y un mouse será envío a Córdoba "
      "capital. Un teclado y un mouse será envío a Concordia. Los otros dos "
      "artículos serán con envío a posadas. Divide el presupuesto en setenta "
      "treinta")
M11 = ("necesito una compu para mi hijo de 8 años, para que juegue y haga la "
       "tarea, que no sea muy cara")


def _correr(monkeypatch, guion, texto):
    """Corre el turno con el modelo doblado y ESPIA lo que llego al motor.

    Devuelve (informe, consultas que vio el motor, llamadas del cliente). Lo
    que se mira es lo segundo: el cotejo corrige en el lugar, asi que la unica
    forma honesta de saber si sirvio es leer lo que el motor recibio.
    """
    from app.core import llm_reintento as LR
    cli = _ClienteFalso(guion)
    monkeypatch.setattr(LR, "_cliente", lambda: cli)
    monkeypatch.setattr(LR, "_modelo", lambda: "doble")
    vistas = []
    real = MT.buscar

    def _espia(consultas, *a, **kw):
        import copy
        vistas.append(copy.deepcopy(consultas))
        return real(consultas, *a, **kw)

    monkeypatch.setattr(MT, "buscar", _espia)
    _, _, _, _, informe = asyncio.run(
        R._preguntar("", "", [], texto, "", "t", TIENDA))
    return informe, vistas, cli


def _prompts(cli) -> list:
    return ["\n".join(str(m.get("content") or "") for m in kw["messages"])
            for kw in cli.vistos]


# ── 1 · LA FIDELIDAD DEL RENGLON LLEGA AL INFORME ───────────────────────────

def test_el_informe_cuenta_los_renglones_copia(firestore_doble, monkeypatch):
    guion = [_Msg(tool_calls=[_Call(
        '{"renglones": ["dos auriculares", "dos mouse", '
        '"notebook gamer carisima"], "pedir_total": true, '
        '"consultas": [{"categoria": "auriculares"}]}')]),
        _Msg('{"tipo": "precio_multiple", "texto": "listo"}')]
    informe, _, _ = _correr(monkeypatch, guion, M1)
    assert informe["renglones"] == 3
    assert informe["renglones_copia"] == 2
    assert informe["renglones_propios"] == ["notebook gamer carisima"]


def test_la_fidelidad_se_mide_en_la_primera_llamada_y_no_se_pisa(
        firestore_doble, monkeypatch):
    """La pregunta es "de entrada, ¿transcribio o tradujo?". En la vuelta 2 el
    modelo ya tiene su propia lista delante, asi que copiarse a si mismo no
    dice nada: si se midiera ahi, el numero subiria solo."""
    guion = [
        _Msg(tool_calls=[_Call(
            '{"renglones": ["una compu carisima de gama alta"], '
            '"pedir_total": false, "consultas": [{"categoria": "notebook"}]}')]),
        _Msg(tool_calls=[_Call(
            '{"renglones": ["necesito una compu para mi hijo de 8 años"], '
            '"pedir_total": false, "consultas": [{"categoria": "mouse"}]}')]),
        _Msg('{"tipo": "recomendacion", "texto": "listo"}')]
    informe, _, _ = _correr(monkeypatch, guion, M11)
    assert informe["renglones"] == 1
    assert informe["renglones_copia"] == 0


# ── 2 · EL RUBRO NOMBRADO Y NO PEDIDO ───────────────────────────────────────

def test_el_teclado_de_m1_llega_al_informe_y_al_prompt(firestore_doble,
                                                       monkeypatch):
    """EL CASO ENTERO: el cliente nombra un teclado en la frase del envio, el
    modelo no lo cotiza y `pedir_total` es true. Antes el presupuesto salia
    sin el teclado y ningun numero lo contaba."""
    guion = [_Msg(tool_calls=[_Call(
        '{"renglones": ["dos auriculares", "dos mouse", "dos memorias", '
        '"envio a Concordia un teclado y un mouse"], "pedir_total": true, '
        '"consultas": [{"categoria": "auriculares"}, {"categoria": "mouse"}, '
        '{"categoria": "memoria ram"}]}')]),
        _Msg('{"tipo": "precio_multiple", "texto": "listo"}')]
    informe, _, cli = _correr(monkeypatch, guion, M1)
    assert informe["rubros_sin_pedir"] == ["teclado"]
    # Y EL AVISO VIAJA: el turno no escribe el texto, le pone el dato delante
    # al modelo en la vuelta siguiente.
    assert any("teclado" in p and "no lo buscaste" in p
               for p in _prompts(cli)[1:])


def test_si_lo_busco_no_hay_aviso(firestore_doble, monkeypatch):
    guion = [_Msg(tool_calls=[_Call(
        '{"renglones": ["dos auriculares", '
        '"envio a Concordia un teclado y un mouse"], "pedir_total": true, '
        '"consultas": [{"categoria": "auriculares"}, '
        '{"categoria": "teclado"}, {"categoria": "mouse"}]}')]),
        _Msg('{"tipo": "precio_multiple", "texto": "listo"}')]
    informe, _, cli = _correr(monkeypatch, guion, M1)
    assert informe["rubros_sin_pedir"] == []
    assert not any("no lo buscaste" in p for p in _prompts(cli))


# ── 3 · LA CIFRA QUE EL CLIENTE NO DIJO NO LLEGA AL MOTOR ───────────────────

def test_el_techo_inventado_no_llega_al_motor(firestore_doble, monkeypatch):
    """Turno d5e14b3f: `precio_ars menor 500000` sobre un mensaje sin una sola
    cifra. Lo que el motor tiene que recibir es el ORDEN, no el filtro."""
    guion = [_Msg(tool_calls=[_Call(
        '{"renglones": ["necesito una compu para mi hijo de 8 años"], '
        '"pedir_total": false, "consultas": [{"categoria": "notebook", '
        '"condiciones": [{"campo": "precio_ars", "operador": "menor", '
        '"valor": "500000"}]}]}')]),
        _Msg('{"tipo": "recomendacion", "texto": "listo"}')]
    informe, vistas, _ = _correr(monkeypatch, guion, M11)
    assert informe["umbrales_degradados"] == ["precio_ars menor 500000"]
    assert vistas, "el motor no recibio ninguna consulta"
    assert vistas[0][0]["condiciones"] == []
    assert vistas[0][0]["ordenar_por"] == {"campo": "precio_ars",
                                          "direccion": "min"}


def test_la_cifra_dicha_por_el_cliente_si_llega_al_motor(firestore_doble,
                                                         monkeypatch):
    men = "mostrame notebooks de menos de 700000 pesos"
    guion = [_Msg(tool_calls=[_Call(
        '{"renglones": ["notebooks de menos de 700000 pesos"], '
        '"pedir_total": false, "consultas": [{"categoria": "notebook", '
        '"condiciones": [{"campo": "precio_ars", "operador": "menor", '
        '"valor": "700000"}]}]}')]),
        _Msg('{"tipo": "recomendacion", "texto": "listo"}')]
    informe, vistas, _ = _correr(monkeypatch, guion, men)
    assert informe["umbrales_degradados"] == []
    assert len(vistas[0][0]["condiciones"]) == 1


# ── 4 · LA VUELTA QUE NO AGREGA NADA NO SE VUELVE A BUSCAR ──────────────────

def test_la_vuelta_calcada_no_dispara_una_segunda_busqueda(firestore_doble,
                                                           monkeypatch):
    """Turno 04f589dc: la vuelta 2 fue la vuelta 1 con las claves barajadas."""
    v1 = ('{"renglones": ["dos auriculares"], "pedir_total": false, '
          '"consultas": [{"categoria": "auriculares", "busco": "varios"}]}')
    v2 = ('{"renglones": ["dos auriculares"], "pedir_total": false, '
          '"consultas": [{"busco": "varios", "categoria": "auriculares"}]}')
    guion = [_Msg(tool_calls=[_Call(v1)]), _Msg(tool_calls=[_Call(v2)]),
             _Msg('{"tipo": "precio_multiple", "texto": "listo"}')]
    informe, vistas, cli = _correr(monkeypatch, guion, M1)
    assert informe["vueltas_sin_aporte"] == 1
    assert len(vistas) == 1, "busco dos veces lo mismo"
    # LA REPETIDA SE SIGUE CONTANDO. Que el numero baje justo cuando se empieza
    # a atajar el defecto seria un instrumento midiendose a si mismo.
    assert informe["repetidas"] == 1
    assert informe["consultas"] == 2
    assert any("ya lo buscaste" in p for p in _prompts(cli)[1:])


def test_una_casilla_nueva_en_la_vuelta_2_si_se_busca(firestore_doble,
                                                      monkeypatch):
    """Repetir la consulta Y traer un tema nuevo no es una vuelta sin aporte:
    el tema hay que ir a buscarlo."""
    con = '{"categoria": "auriculares", "busco": "varios"}'
    guion = [
        _Msg(tool_calls=[_Call('{"renglones": ["dos auriculares"], '
                               '"pedir_total": false, "consultas": [' + con
                               + ']}')]),
        _Msg(tool_calls=[_Call('{"renglones": ["dos auriculares"], '
                               '"pedir_total": false, "consultas": [' + con
                               + '], "temas": ["garantia"]}')]),
        _Msg('{"tipo": "multipregunta", "texto": "listo"}')]
    informe, vistas, _ = _correr(monkeypatch, guion, M1)
    assert informe["vueltas_sin_aporte"] == 0
    assert len(vistas) == 2


# ── 5 · LO DECLARADO NO SE PIERDE ENTRE VUELTAS ─────────────────────────────

def test_la_condicion_que_la_vuelta_2_perdio_vuelve_al_motor(firestore_doble,
                                                             monkeypatch):
    """Turno 2eb9ace4: la vuelta 1 manda `pais_fabricacion evita china` en las
    tres consultas y la vuelta 2 manda las mismas tres SIN la condicion. Las
    filas de esa segunda busqueda no cumplian lo que el cliente pidio y se
    sumaban a las fichas con las que el modelo redacta."""
    guion = [
        _Msg(tool_calls=[_Call(
            '{"renglones": ["dos auriculares"], "pedir_total": false, '
            '"consultas": [{"categoria": "auriculares", "condiciones": '
            '[{"campo": "pais_fabricacion", "operador": "evita", '
            '"valor": "china"}]}]}')]),
        _Msg(tool_calls=[_Call(
            '{"renglones": ["dos auriculares"], "pedir_total": false, '
            '"consultas": [{"categoria": "auriculares", "cuantos": 6}]}')]),
        _Msg('{"tipo": "precio_multiple", "texto": "listo"}')]
    informe, vistas, _ = _correr(monkeypatch, guion, M1)
    assert informe["condiciones_repuestas"], "no repuso nada"
    assert len(vistas) == 2
    conds = vistas[1][0].get("condiciones") or []
    assert any(c.get("campo") == "pais_fabricacion"
               and c.get("operador") == "evita" for c in conds)


def test_el_turno_sin_nada_que_cotejar_no_se_cae(firestore_doble, monkeypatch):
    """Un pedido sin renglones y sin condiciones tiene que pasar derecho: el
    cotejo no puede ser un lugar nuevo donde el turno se rompa."""
    guion = [_Msg(tool_calls=[_Call('{"consultas": [{"texto": "teclado"}]}')]),
             _Msg('{"tipo": "precio_simple", "texto": "listo"}')]
    informe, vistas, _ = _correr(monkeypatch, guion, "teclado")
    assert informe["renglones"] == 0
    assert informe["rubros_sin_pedir"] == []
    assert len(vistas) == 1
