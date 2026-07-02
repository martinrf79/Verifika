"""
AREA: Divergencia INTERPRETE <-> SOLVER — la guarda determinista del caso
'interprete BIEN, solver MAL'.

Cuando el interprete marca ofrecer_opciones (dos caminos y no puede elegir con
certeza) pero el solver ignora eso y elige una opcion sin preguntar, una guarda
determinista FUERZA la pregunta A/B. Asi la divergencia no se resuelve con una
eleccion silenciosa del solver sino con una pregunta de confirmacion.

Cubre _forzar_pregunta_si_ambiguo (app/core/interprete_libre.py). Es logica pura,
sin LLM ni Firestore.

Los otros dos ejes de divergencia (solver alucina un NUMERO, identidad de
producto AMBIGUA) ya los cubren tests/test_verificador.py y
tests/test_certificador.py: esos son las guardas deterministas que atrapan la
divergencia sobre HECHOS. Este archivo cubre el hueco que faltaba: la eleccion.
"""
from app.core.interprete_libre import _forzar_pregunta_si_ambiguo


OPCIONES = ["Mouse G203 negro, $37.500", "Mouse G203 blanco, $37.500"]


def test_solver_eligio_una_sin_preguntar_fuerza_pregunta():
    """Interprete marco dos opciones; el solver eligio una y no pregunto: se
    fuerza la pregunta A/B con el detalle del interprete."""
    interp = {"ofrecer_opciones": OPCIONES, "confianza": 0.5}
    resp = "Te recomiendo el Mouse G203 negro, sale $37.500."
    forzada = _forzar_pregunta_si_ambiguo(interp, resp)
    assert forzada is not None
    assert "Opción A" in forzada and "Opción B" in forzada
    assert "¿Cuál preferís?" in forzada


def test_solver_ya_pregunto_las_dos_se_respeta():
    """Si el solver YA planteo la eleccion (pregunta y nombra las dos opciones),
    la guarda no toca su redaccion."""
    interp = {"ofrecer_opciones": OPCIONES, "confianza": 0.5}
    resp = ("Tengo el Mouse G203 en negro y en blanco, los dos a $37.500. "
            "¿Cuál preferís?")
    assert _forzar_pregunta_si_ambiguo(interp, resp) is None


def test_sin_opciones_no_fuerza_nada():
    """Sin ofrecer_opciones (caso claro), la guarda no interviene."""
    assert _forzar_pregunta_si_ambiguo({"ofrecer_opciones": None}, "Sale $37.500.") is None
    assert _forzar_pregunta_si_ambiguo({}, "Sale $37.500.") is None


def test_opciones_incompletas_no_fuerza():
    """Una sola opcion o vacias no dispara la pregunta A/B."""
    assert _forzar_pregunta_si_ambiguo({"ofrecer_opciones": ["una sola"]}, "x") is None
    assert _forzar_pregunta_si_ambiguo({"ofrecer_opciones": ["", ""]}, "x") is None


def test_pregunta_generica_no_alcanza_para_respetar():
    """El solver que pregunta algo generico pero NO nombra las dos opciones no
    conto como plantear la eleccion: igual se fuerza la pregunta A/B."""
    interp = {"ofrecer_opciones": OPCIONES}
    resp = "¿Te lo envío a domicilio?"  # pregunta, pero no es la eleccion A/B
    forzada = _forzar_pregunta_si_ambiguo(interp, resp)
    assert forzada is not None and "Opción A" in forzada
