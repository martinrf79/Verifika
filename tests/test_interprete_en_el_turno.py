"""EL INTERPRETE EN EL TURNO VIVO — `respuesta._preguntar` y `procesar_turno`.

Desde el 23-sep el modelo ya no escribe el pedido del motor: el traductor llena
una ficha y `app/core/interprete.py` decide en codigo. Estos tests miden el
CABLEADO, no la interpretacion —esa la mide el banco—: que la ficha llegue al
motor, que el modelo solo redacte, que la memoria nueva se guarde en la charla
y resuelva el turno siguiente, y que un traductor caido no deje mudo al bot.

El modelo es un doble: la primera llamada de cada turno es el traductor y
devuelve la ficha escrita a mano; las demas son el redactor.
"""
import asyncio
import json

from app.core import respuesta as R

TIENDA = "verifika_prod"


def _parte(dice, **k):
    p = {"dice": dice, "quiere": "precio", "origen": "tienda",
         "rubro": "ninguno", "producto": "", "criterios": [], "cantidad": 0,
         "destino": "", "refiere": "no", "posiciones": [], "para": ""}
    p.update(k)
    return p


def _ficha(texto, *partes):
    return {"partes": list(partes), "afirma": [], "reescrita": texto,
            "criterios_generales": [], "reparto": []}


class _Modelo:
    """El traductor devuelve las fichas en orden; el redactor, un texto."""

    def __init__(self, fichas):
        self.fichas = list(fichas)
        self.llamadas = []
        self.chat = self
        self.completions = self

    def create(self, *, model, messages, **kw):
        rf = (kw.get("response_format") or {}).get("json_schema") or {}
        es_traductor = rf.get("name") == "ficha"
        self.llamadas.append({"traductor": es_traductor,
                              "tools": bool(kw.get("tools")),
                              "mensajes": messages})
        if es_traductor:
            contenido = json.dumps(self.fichas.pop(0)) if self.fichas \
                else "{roto"
        else:
            contenido = json.dumps({"tipo": "precio_simple",
                                    "texto": "Te paso lo que encontre."})
        msg = type("M", (), {"content": contenido, "tool_calls": None})()

        class _R:
            choices = [type("C", (), {"message": msg})()]
        return _R()


def _con_modelo(modelo, fn):
    from app.core import llm_reintento as LR
    viejo = LR._cliente
    LR._cliente = lambda: modelo
    try:
        return fn()
    finally:
        LR._cliente = viejo


def _preguntar(modelo, mensaje, estado=None):
    return _con_modelo(modelo, lambda: asyncio.run(R._preguntar(
        "V", "", [], mensaje, "F", "t", TIENDA, estado_interprete=estado)))


def test_la_ficha_llega_al_motor_y_el_modelo_solo_redacta(firestore_doble):
    texto = "cuanto sale el teclado K120 negro?"
    m = _Modelo([_ficha(texto, _parte(texto, rubro="teclado",
                                      producto="K120 negro"))])
    salida, fichas, _env, _cta, informe = _preguntar(m, texto)
    assert [x["traductor"] for x in m.llamadas] == [True, False], \
        "una llamada para traducir y una para redactar, nada mas"
    assert not any(x["tools"] for x in m.llamadas), \
        "el redactor ya no recibe herramientas: no busca"
    assert any("k120" in str(f.get("modelo", "")).lower() for f in fichas)
    assert informe["llamadas"] == 1 and informe["consultas"] == 1
    assert salida["texto"] and salida["interprete"]["turno"] == 1


def test_lo_que_volvio_del_motor_llega_al_redactor(firestore_doble):
    texto = "cuanto sale el teclado K120 negro?"
    m = _Modelo([_ficha(texto, _parte(texto, rubro="teclado",
                                      producto="K120 negro"))])
    _preguntar(m, texto)
    redactor = json.dumps(m.llamadas[-1]["mensajes"], ensure_ascii=False)
    assert "K120" in redactor and "Volvio:" in redactor


def test_la_repregunta_le_llega_al_redactor_con_las_opciones(firestore_doble):
    """"Cuanto sale el logitech?" es de varios rubros: el codigo pregunta, y el
    redactor recibe la orden de no elegir con las opciones reales."""
    texto = "cuanto sale el logitech?"
    m = _Modelo([_ficha(texto, _parte(texto, producto="logitech"))])
    _preguntar(m, texto)
    redactor = json.dumps(m.llamadas[-1]["mensajes"], ensure_ascii=False)
    assert "NO ELIJAS VOS" in redactor


def test_la_memoria_se_guarda_y_resuelve_el_turno_siguiente(firestore_doble):
    """Dos turnos por `procesar_turno`, con la charla guardada en el doble de
    Firestore en el medio: 'el segundo' apunta al segundo que se mostro."""
    from app.storage.firestore_client import get_conversation
    t1 = "mostrame 3 mouse logitech"
    t2 = "el segundo cuanto pesa?"
    m = _Modelo([
        _ficha(t1, _parte(t1, quiere="buscar", rubro="mouse", cantidad=3,
                          criterios=[{"concepto": "marca",
                                      "valor": "logitech",
                                      "fuerza": "debe"}])),
        _ficha(t2, _parte(t2, quiere="caracteristica", refiere="posicion",
                          posiciones=[2]))])
    usuario = "sonda_interprete_memoria"

    def dos_turnos():
        asyncio.run(R.procesar_turno(usuario, t1, TIENDA, "telegram", "t1"))
        conv = get_conversation(usuario, tienda_id=TIENDA)
        lista = conv["interprete"]["listas"][-1]["items"]
        asyncio.run(R.procesar_turno(usuario, t2, TIENDA, "telegram", "t2"))
        return lista, get_conversation(usuario, tienda_id=TIENDA)

    lista, conv = _con_modelo(m, dos_turnos)
    assert len(lista) >= 2
    segundo = lista[1]["ids"]
    foco = [i for it in conv["interprete"]["foco"] for i in it["ids"]]
    assert foco == segundo


def test_un_traductor_caido_no_deja_mudo_al_bot(firestore_doble):
    """Ficha rota: el motor no busca nada y el redactor contesta igual."""
    m = _Modelo([])  # el traductor devuelve un JSON roto
    salida, fichas, *_ = _preguntar(m, "hola")
    assert salida["texto"] and fichas == []
