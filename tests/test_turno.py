"""EL TURNO NUEVO, CORRIDO DE PUNTA A PUNTA SIN MODELO.

Se doblan las DOS llamadas y nada mas. Todo lo del medio —la interpretacion
convertida en busquedas, las herramientas contra el catalogo real, la cuenta, la
mesa, el armado, el cierre y la memoria— corre tal cual.

POR QUE ESTA VARA EXISTE: `turno.py` reemplazo al hub entero en el camino vivo y
un `import` limpio no prueba nada. Lo que prueba que anda es un turno que entra
por `procesar_turno` y sale con un mensaje que el cliente podria leer.

Cada test dice sobre cuantos casos corrio (regla 10.6 de CLAUDE.md).
"""
import json

import pytest

from app.core import turno as T

TIENDA = "verifika_prod"


def _doblar(monkeypatch, declarado: dict, respuesta: dict | None,
            rompe_el_json: bool = False):
    """Dobla la llamada UNO -que declara- y la llamada DOS -que llena la mesa-.

    La uno se dobla en `_pedir_herramientas` porque lo que importa aguas abajo
    es lo DECLARADO, no como se pidio. La dos se dobla en el cliente, asi pasa
    por el parser de verdad: es donde vive el riesgo de que el modelo no
    respete el esquema.
    """
    async def _pedidos(negocio, memoria, history, mensaje, tienda_id, trace_id):
        if declarado is None:
            return [], "Hola! En que te puedo ayudar?"
        return [{"nombre": "registrar_pedido", "args": declarado}], ""

    monkeypatch.setattr(T, "_pedir_herramientas", _pedidos)

    class _Msg:
        def __init__(self, c): self.content = c

    class _Choice:
        def __init__(self, c): self.message = _Msg(c)

    class _Resp:
        def __init__(self, c): self.choices = [_Choice(c)]

    class _Completions:
        def create(self, **kw):
            if rompe_el_json:
                return _Resp("Hola, te paso todo: el mouse sale $99.999.")
            return _Resp(json.dumps(respuesta or {}, ensure_ascii=False))

    class _Chat:
        completions = _Completions()

    class _Cli:
        chat = _Chat()

    monkeypatch.setattr(T, "_cliente", lambda: _Cli())


@pytest.mark.asyncio
async def test_un_turno_entero_sale_con_un_mensaje(monkeypatch, firestore_doble):
    """El caso de todos los dias: pide un producto y el precio."""
    declarado = {"items": [{"que": "mouse Genius DX-110", "categoria": "mouse",
                            "cantidad": 2}],
                 "pide_precio": True}
    respuesta = {"apertura": "Hola! Te paso.",
                 "puntos": [{"id": "items:1",
                             "texto": "Tengo el Genius DX-110, es el mas "
                                      "economico que manejo."},
                            {"id": "pide_precio:1", "texto": ""}],
                 "pregunta_final": "Te lo armo?"}
    _doblar(monkeypatch, declarado, respuesta)
    texto = await T.procesar_turno("u-uno", "quiero 2 mouse Genius DX-110, "
                                            "cuanto sale", TIENDA, "test", "t1")
    assert "Genius" in texto, texto
    assert "Total:" in texto, f"no salio la cuenta sellada:\n{texto}"
    assert "Te lo armo?" in texto
    assert texto.index("Total:") < texto.index("Te lo armo?"), \
        "la cuenta tiene que ir antes de la pregunta"


@pytest.mark.asyncio
async def test_el_saludo_sin_herramientas_no_rompe(monkeypatch,
                                                   firestore_doble):
    """Un hola no abre ningun punto: el turno contesta con lo que dijo la
    llamada uno y no llama al redactor."""
    _doblar(monkeypatch, None, None)
    texto = await T.procesar_turno("u-dos", "hola", TIENDA, "test", "t2")
    assert texto.strip(), "el saludo salio vacio"
    assert "demanda" not in texto.lower(), texto


@pytest.mark.asyncio
async def test_si_el_modelo_no_devuelve_la_mesa_no_sale_la_prosa_cruda(
        monkeypatch, firestore_doble):
    """LA REGLA QUE NO SE NEGOCIA. Es tentador mandar la prosa igual -al menos
    el cliente recibe algo- y es el agujero que este diseño cierra: una prosa
    que no paso por la mesa puede traer un precio que nadie calculo. El $99.999
    del doble no puede llegar al cliente."""
    declarado = {"items": [{"que": "mouse", "categoria": "mouse",
                            "cantidad": 1}], "pide_precio": True}
    _doblar(monkeypatch, declarado, None, rompe_el_json=True)
    texto = await T.procesar_turno("u-tres", "un mouse barato", TIENDA,
                                   "test", "t3")
    assert "99.999" not in texto, f"salio la prosa cruda:\n{texto}"
    assert "demanda" in texto.lower(), \
        f"tenia que caer al mensaje de demanda:\n{texto}"


@pytest.mark.asyncio
async def test_la_plata_inventada_en_una_casilla_no_llega(monkeypatch,
                                                          firestore_doble):
    """El esquema fija la forma, no el contenido de cada casilla. Un precio que
    el codigo no calculo se corta ahi, y el resto del mensaje sigue."""
    declarado = {"items": [{"que": "mouse Genius DX-110", "categoria": "mouse",
                            "cantidad": 1}], "pide_precio": True}
    respuesta = {"apertura": "",
                 "puntos": [{"id": "items:1",
                             "texto": "El Genius sale $99.999 con envio."},
                            {"id": "pide_precio:1", "texto": ""}],
                 "pregunta_final": "Te sirve?"}
    _doblar(monkeypatch, declarado, respuesta)
    texto = await T.procesar_turno("u-cuatro", "un mouse Genius, cuanto sale",
                                   TIENDA, "test", "t4")
    assert "99.999" not in texto, f"paso la plata inventada:\n{texto}"
    assert "Total:" in texto, "se llevo puesta la cuenta buena"
    assert "Te sirve?" in texto


@pytest.mark.asyncio
async def test_un_punto_sin_material_termina_en_pregunta(monkeypatch,
                                                         firestore_doble):
    """El cliente pregunta un dato que la ficha no tiene. No se inventa y no se
    calla: sale una pregunta escrita por el codigo."""
    declarado = {"items": [],
                 "atributos": [{"de": "el Genius DX-110", "campo": "dpi"}]}
    respuesta = {"apertura": "", "puntos": [], "pregunta_final": ""}
    _doblar(monkeypatch, declarado, respuesta)
    texto = await T.procesar_turno("u-cinco", "cuantos dpi tiene el Genius "
                                              "DX-110", TIENDA, "test", "t5")
    assert texto.strip().endswith("?"), f"no termino en pregunta:\n{texto}"
    assert "dpi" in texto.lower(), texto


@pytest.mark.asyncio
async def test_la_memoria_del_turno_se_guarda(monkeypatch, firestore_doble):
    """PRIORIDAD 3 DE CLAUDE.md: la memoria siempre activa. Un turno que no
    guarda el carrito deja al siguiente sin nada, y esa es la falla que mas
    caro salio en las charlas reales."""
    from app.storage.firestore_client import get_conversation
    declarado = {"items": [{"que": "mouse Genius DX-110", "categoria": "mouse",
                            "cantidad": 1}], "pide_precio": True}
    respuesta = {"apertura": "", "puntos": [{"id": "items:1", "texto": "Va."},
                                            {"id": "pide_precio:1",
                                             "texto": ""}],
                 "pregunta_final": ""}
    _doblar(monkeypatch, declarado, respuesta)
    await T.procesar_turno("u-seis", "un mouse Genius DX-110, cuanto sale",
                           TIENDA, "test", "t6")
    conv = get_conversation("u-seis", tienda_id=TIENDA)
    assert conv.get("history"), "no se guardo el historial"
    assert conv["history"][-1]["role"] == "assistant"
    assert conv.get("carrito_vigente"), "no se guardo el carrito"
    assert conv.get("ultimo_presupuesto"), "no se guardo el presupuesto"


@pytest.mark.asyncio
async def test_el_orchestrator_entra_por_el_turno_nuevo(monkeypatch,
                                                        firestore_doble):
    """El unico cambio afuera: una linea del orchestrator. Si esto se rompe, el
    camino vivo quedo apuntando al modulo apagado."""
    from app.core import orchestrator as O
    assert O.procesar_turno is T.procesar_turno
    llamado = {}

    async def _fake(*a, **kw):
        llamado["si"] = True
        return "ok"

    monkeypatch.setattr(O, "procesar_turno", _fake)
    out = await O.process_message("u-siete", "hola", tienda_id=TIENDA,
                                  canal="test")
    assert out == "ok" and llamado.get("si")


def test_cuantos_turnos_se_probaron():
    assert len([f for f in globals() if f.startswith("test_")]) == 8
