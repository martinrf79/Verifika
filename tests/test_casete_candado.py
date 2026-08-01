"""
CANDADO DE LA MAQUINA DE CASETES.

El banco de charlas corre el turno completo contra el modelo grabado. Esa red tiene un modo de falla silencioso y peligroso, y
es el mismo que veniamos sufriendo con otra cara: si alguien agrega una puerta
NUEVA al modelo, o le cambia el nombre a una de las dos que hay, el casete deja
de interceptarla y los tests siguen en VERDE probando cada vez menos. Verde
sobre codigo que no se esta corriendo es peor que rojo, porque da confianza
falsa; de eso se trataba el problema entero.

Estos candados son baratos y cubren la clase de error, no un caso puntual.
"""
import ast
from pathlib import Path

import pytest

_APP = Path(__file__).resolve().parent.parent / "app"


def test_la_puerta_al_modelo_existe():
    """`casete.py` parchea exactamente este nombre. Si se renombra, el casete
    deja de interceptar y hay que actualizarlo en el mismo commit."""
    from app.core import hub_venta
    assert callable(hub_venta._cliente)


def test_no_hay_una_tercera_puerta_al_modelo():
    """Nadie construye su propio cliente OpenAI por fuera de las dos puertas.

    Es la regla que ya se aprendio a la mala DOS veces con la guardia de
    promesas: cada cliente duplicado queda apuntando al provider anterior cuando
    el sistema cambia, y el consumidor muere en silencio con sus tests en verde.
    Ahora ademas rompe la grabacion, porque una llamada que el casete no ve es
    una llamada que en CI se va a la red de verdad o revienta.

    Si hace falta una puerta nueva de verdad, se agrega aca Y en
    `banco_pruebas/casete._parchar`, en el mismo commit.
    """
    # Las dos puertas que el casete SI intercepta, mas el transcriptor de audio,
    # que no participa del turno de texto. La lista es corta a proposito: cada
    # nombre que se le suma es una llamada al modelo que los tests dejan de ver.
    # Este mismo test encontro `llm_adapter.llm_complete` -que usan
    # `cierre.extraer_datos_cliente` y `tools.query_faq`, o sea que corre en
    # turnos reales- despues de que la lista la tapara sin querer.
    permitidos = {"hub_venta.py", "llm_adapter.py", "transcriber.py"}
    culpables = []
    for py in sorted(_APP.rglob("*.py")):
        if py.name in permitidos:
            continue
        arbol = ast.parse(py.read_text(encoding="utf-8"))
        for n in ast.walk(arbol):
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                    and n.func.id == "OpenAI"):
                culpables.append(f"{py.relative_to(_APP.parent)}:{n.lineno}")
    assert not culpables, (
        "clientes del modelo armados por fuera de las dos puertas: "
        + ", ".join(culpables)
        + ". Usar hub_venta._cliente(), o sumar la puerta nueva a "
          "banco_pruebas/casete._parchar.")


def test_reproducir_intercepta_de_verdad():
    """El contrato del casete: adentro de `reproducir` ninguna llamada sale a la
    red, y lo que se devuelve es lo grabado. Sin este test, un casete roto se
    veria igual que uno que anda."""
    import json

    from banco_pruebas.casete import Casete, reproducir
    from app.core import hub_venta

    grabado = json.dumps({"content": "", "tool_calls": [
        {"name": "consultar_politica", "arguments": '{"tema": "envios"}'}]})
    casete = Casete("_prueba", [{"mensaje": "hola", "llamadas": [
        {"etapa": "herramientas", "salida": grabado}]}])
    with reproducir(casete):
        casete.abrir_turno("hola")
        # LLAMADA UNO: la que lleva las herramientas. Lo grabado son los tool
        # calls, no un texto: si el casete devolviera solo content, un turno con
        # herramientas reproduciria vacio y el test quedaria verde de mentira.
        r = hub_venta._cliente().chat.completions.create(
            model="x", messages=[{"role": "user", "content": "hola"}],
            tools=[{"type": "function", "function": {"name": "consultar_politica"}}])
        tc = r.choices[0].message.tool_calls
        assert tc and tc[0].function.name == "consultar_politica"

        # una etapa sin grabar NO devuelve algo inventado: corta como un timeout
        # del provider, que es lo que el consumidor ya sabe manejar.
        with pytest.raises(TimeoutError):
            hub_venta._cliente().chat.completions.create(
                model="x", messages=[])
        assert casete.fallas

    # y al salir, la puerta queda como estaba
    assert hub_venta._cliente.__name__ == "_cliente"


def test_las_dos_llamadas_del_turno_se_graban_por_separado():
    """La llamada uno lleva herramientas y la dos no. Si las dos cayeran en la
    misma etapa, la grabacion de un turno se pisaria a si misma."""
    from banco_pruebas.casete import _etapa

    assert _etapa({"tools": [{"type": "function"}]}) == "herramientas"
    assert _etapa({"messages": []}) != "herramientas"
