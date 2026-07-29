"""
AREA: MEMORIA STICKY DEL CAMINO VIVO (hub_atado).

Cuando produccion paso de interprete_libre al flujo atado, tres memorias se
quedaron sin escribir: `construir_estado` las LEIA cada turno pero nadie las
GUARDABA, asi que valian un solo turno y se perdian.

  - preferencias_cliente: "no quiero de China", tope de plata, uso previsto.
  - producto_anotado: el ancla de "ese me gusta, anotalo".
  - grupos_envio: que item va a cada destino.

Este test corre un turno REAL del hub con el interprete y el solver mockeados
(sin LLM, sin red) y exige que las tres queden persistidas.
"""
import asyncio

TIENDA = "verifika_prod"


def _turno(monkeypatch, user, mensaje, interp):
    # importes DENTRO: el doble de Firestore se instala con la fixture, y los
    # modulos que importan sus nombres arriba tienen que verlo ya parcheado.
    import app.core.hub_atado as H
    import app.core.generador_v2 as G

    async def _fake_interpretar(*a, **k):
        return interp

    async def _fake_fragmentos(*a, **k):
        return ([{"tipo": "prosa", "texto": "Dale, tomo nota."}], [], "", [], {})

    # el extractor de datos del cierre llama al LLM: fuera, este test es offline.
    import app.core.cierre as C
    monkeypatch.setattr(C, "extraer_datos_cliente", lambda *a, **k: {})
    monkeypatch.setattr(H, "interpretar_mensaje", _fake_interpretar)
    monkeypatch.setattr(G, "generar_fragmentos", _fake_fragmentos)
    return asyncio.new_event_loop().run_until_complete(
        H.procesar_atado(user, mensaje, TIENDA, "sim", "t_sticky"))


def test_el_hub_persiste_preferencias_y_ancla(monkeypatch, firestore_doble):
    from app.storage.firestore_client import get_conversation, reset_conversation
    user = "u_sticky_atado"
    reset_conversation(user, tienda_id=TIENDA)
    interp = {
        "intencion": "pregunta_especifica",
        "producto_resuelto": "Mouse Genius DX-110 Negro",
        "productos_consultados": [], "pedido": [], "solicitud_nueva": [],
        "categorias": ["mouse"],
        "exclusiones": [{"tipo": "origen", "valor": "China"}],
        "tope_presupuesto": 200000, "uso_previsto": "diseño",
    }
    _turno(monkeypatch, user, "no quiero nada chino, hasta 200 lucas", interp)
    # y el ancla: el cliente ELIGE, y eso tiene que sobrevivir al turno.
    _turno(monkeypatch, user, "ese me gusta, anotalo", interp)

    conv = get_conversation(user, tienda_id=TIENDA)
    prefs = conv.get("preferencias_cliente") or {}
    assert prefs.get("tope_presupuesto") == 200000, (
        "la preferencia de plata no sobrevivio el turno")
    assert prefs.get("exclusiones"), "la exclusion de origen no se persistio"
    assert (conv.get("producto_anotado") or {}).get("nombre"), (
        "el ancla del producto resuelto no quedo guardada")
    assert "grupos_envio" in conv


def test_las_preferencias_se_acumulan_entre_turnos(monkeypatch, firestore_doble):
    from app.storage.firestore_client import get_conversation, reset_conversation
    user = "u_sticky_acumula"
    reset_conversation(user, tienda_id=TIENDA)
    base = {"intencion": "pregunta_especifica", "producto_resuelto": None,
            "productos_consultados": [], "pedido": [], "solicitud_nueva": [],
            "categorias": ["mouse"]}
    _turno(monkeypatch, user, "que no sea chino",
           {**base, "exclusiones": [{"tipo": "origen", "valor": "China"}]})
    _turno(monkeypatch, user, "y hasta 150 mil",
           {**base, "tope_presupuesto": 150000})

    prefs = (get_conversation(user, tienda_id=TIENDA)
             .get("preferencias_cliente") or {})
    assert prefs.get("tope_presupuesto") == 150000
    assert prefs.get("exclusiones"), (
        "la preferencia del turno 1 se piso con la del turno 2")
