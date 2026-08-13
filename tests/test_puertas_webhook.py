"""
LA PUERTA DE ENTRADA — los dos webhooks, por HTTP, como los llama Meta.

POR QUE EXISTE, y es la funcion mas cara que estaba sin una sola prueba. Por
`whatsapp_webhook` y `telegram_webhook` entra TODO. Si se rompen, el cliente no
recibe nada: no es que conteste mal, es que no contesta. Y ya paso: el 29-jul,
un barrido de codigo muerto borro `_process_and_reply_telegram` y el webhook
quedo llamando a un nombre que no existia. Cualquier mensaje por Telegram tiraba
NameError. **Nadie se entero porque ningun test entraba por la puerta**, y el
canal vivo era WhatsApp. Esta prueba habria salido roja en el mismo commit.

QUE MIDE, y es a proposito lo que NO mide ningun otro test:
  - que la puerta abra: el 200 y el turno procesado de punta a punta;
  - las tres formas de NO procesar, que valen tanto como procesar: payload que
    no parsea, mensaje repetido -Meta reenvia-, y tienda desconocida;
  - que un turno que revienta NO deje al cliente sin respuesta.

`tests/test_puertas_humo.py` es su hermano un piso mas abajo: aquel prueba que
abran las nueve herramientas, este que abra la puerta de calle.

COMO CORRE. Con el TestClient de FastAPI, o sea el webhook de verdad con su
router, su idempotencia y sus BackgroundTasks, que el TestClient ejecuta antes
de devolver. Lo unico doblado es lo que sale a la red -los conectores, que
mandan HTTP a Meta y a Telegram- y el turno, que se reemplaza por un espia para
poder afirmar QUE se proceso sin arrastrar el hub entero a cada caso.
"""
import sys
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

TIENDA = "verifika_prod"


class _ConectorFalso:
    """Lo unico que se dobla: la salida a la red. Guarda lo que se le mando."""

    def __init__(self):
        self.enviados = []
        self.descargas = {}

    async def send_message(self, user_id, texto):
        self.enviados.append((user_id, texto))
        return True

    async def download_file(self, file_id):
        return self.descargas.get(file_id)

    async def download_media(self, media_id):
        return self.descargas.get(media_id)

    def parse_incoming(self, payload):
        msg = (payload.get("message") or {})
        if not msg.get("text"):
            return None
        return str(msg["chat"]["id"]), msg["text"]


@pytest.fixture
def puerta(monkeypatch, firestore_doble):
    """El app de verdad, con la red doblada y el turno espiado."""
    import app.main as main

    conector = _ConectorFalso()
    turnos = []

    async def _turno_espia(user_id, text, canal="telegram", tienda_id=None):
        turnos.append({"user_id": user_id, "text": text, "canal": canal})
        return f"respuesta a {text}"

    monkeypatch.setattr(main, "get_telegram_connector", lambda: conector)
    monkeypatch.setattr(main, "process_message", _turno_espia)
    # Idempotencia limpia por test: el doble recuerda los ids entre casos y el
    # segundo test se veria a si mismo como duplicado del primero.
    vistos: set = set()

    def _already(mid):
        mid = str(mid or "")
        if not mid or mid in vistos:
            return bool(mid)
        vistos.add(mid)
        return False

    monkeypatch.setattr(main, "already_processed", _already)

    from fastapi.testclient import TestClient
    with TestClient(main.app) as cliente:
        yield cliente, conector, turnos, main, monkeypatch


def _update(update_id, texto, chat_id="42"):
    return {"update_id": update_id,
            "message": {"chat": {"id": chat_id}, "text": texto}}


# ── TELEGRAM ────────────────────────────────────────────────────────────────
def test_telegram_procesa_el_turno_y_contesta(puerta):
    """EL CASO DEL 29-JUL. Si `_process_and_reply_telegram` no existe o
    revienta, el turno no se procesa y al cliente no le llega nada."""
    cliente, conector, turnos, _, _ = puerta
    r = cliente.post("/webhook/telegram", json=_update(1, "hola, tenes mouse?"))
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert len(turnos) == 1, "el webhook devolvio 200 y NO proceso el turno"
    assert turnos[0]["text"] == "hola, tenes mouse?"
    assert turnos[0]["canal"] == "telegram"
    assert conector.enviados, "se proceso el turno y no se le mando nada al cliente"
    assert "hola, tenes mouse?" in conector.enviados[0][1]


def test_telegram_no_procesa_el_mismo_update_dos_veces(puerta):
    """Telegram reintenta. Sin idempotencia el cliente recibe la respuesta
    duplicada y, si el turno cobraba, se cobra dos veces."""
    cliente, _, turnos, _, _ = puerta
    cliente.post("/webhook/telegram", json=_update(7, "cuanto sale"))
    r = cliente.post("/webhook/telegram", json=_update(7, "cuanto sale"))
    assert r.json() == {"ok": True, "duplicate": True}
    assert len(turnos) == 1, "el update repetido se proceso dos veces"


def test_telegram_ignora_lo_que_no_es_un_mensaje_de_texto(puerta):
    """Telegram manda updates que no son mensajes -ediciones, estados-. Se
    contesta 200 igual, porque un 500 le hace reintentar en loop."""
    cliente, conector, turnos, _, _ = puerta
    r = cliente.post("/webhook/telegram", json={"update_id": 9, "edited": {}})
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert not turnos and not conector.enviados


def test_telegram_no_deja_al_cliente_sin_respuesta_si_el_turno_revienta(puerta):
    """La red de la puerta. Un blip del modelo no puede terminar en silencio:
    el cliente tiene que recibir el aviso de sobrecarga, que sale de la FUENTE."""
    cliente, conector, _, main, mp = puerta

    async def _explota(*a, **kw):
        raise RuntimeError("blip del modelo")

    mp.setattr(main, "process_message", _explota)
    r = cliente.post("/webhook/telegram", json=_update(11, "hola"))
    assert r.status_code == 200
    assert conector.enviados, "el turno reventó y el cliente quedo sin respuesta"
    assert conector.enviados[-1][1] == main._sobrecarga()


def test_el_audio_que_no_se_puede_bajar_avisa_y_no_procesa(puerta):
    """El audio es una entrada de primera clase. Si no se puede bajar, el
    cliente se entera; no queda esperando."""
    cliente, conector, turnos, _, _ = puerta
    cliente.post("/webhook/telegram", json=_update(13, "__AUDIO__:no_existe"))
    assert not turnos, "se proceso un turno sin texto"
    assert conector.enviados
    assert "audio" in conector.enviados[-1][1].lower()


def test_el_audio_que_no_transcribe_avisa_y_no_procesa(puerta):
    """Mismo criterio: transcripcion vacia es un no-texto, no un turno vacio."""
    cliente, conector, turnos, main, mp = puerta
    conector.descargas["abc"] = b"ruido"
    import app.core.transcriber as tr
    mp.setattr(tr, "transcribir_audio", lambda b: "")
    cliente.post("/webhook/telegram", json=_update(15, "__AUDIO__:abc"))
    assert not turnos
    assert conector.enviados
    assert "audio" in conector.enviados[-1][1].lower()


def test_el_audio_que_transcribe_entra_como_un_turno_normal(puerta):
    """Y el camino feliz, que es el que de verdad usa el cliente."""
    cliente, conector, turnos, _, mp = puerta
    conector.descargas["ok1"] = b"audio"
    import app.core.transcriber as tr
    mp.setattr(tr, "transcribir_audio", lambda b: "quiero dos mouse")
    cliente.post("/webhook/telegram", json=_update(17, "__AUDIO__:ok1"))
    assert len(turnos) == 1, "el audio transcripto no entro como turno"
    assert turnos[0]["text"] == "quiero dos mouse"


# ── WHATSAPP, el canal VIVO ─────────────────────────────────────────────────
def _payload_wa(message_id, texto, phone_id="PHONE1", user="5491100000000"):
    return {"entry": [{"changes": [{"value": {
        "metadata": {"phone_number_id": phone_id},
        "messages": [{"id": message_id, "from": user, "type": "text",
                      "text": {"body": texto}}]}}]}]}


@pytest.fixture
def puerta_wa(puerta):
    """La puerta de WhatsApp: se dobla la resolucion de tienda -vive en
    Firestore- y el turno, que aca es `_process_and_reply_whatsapp`."""
    cliente, conector, _turnos, main, mp = puerta
    turnos_wa = []

    async def _turno_wa(tienda_id, user_id, text, token, phone_id):
        turnos_wa.append({"tienda_id": tienda_id, "user_id": user_id,
                          "text": text, "phone_id": phone_id})

    mp.setattr(main, "_process_and_reply_whatsapp", _turno_wa)
    mp.setattr(main, "get_tienda_by_phone_id",
               lambda pid: ({"tienda_id": TIENDA, "whatsapp_token": "tok"}
                            if pid == "PHONE1" else None))
    return cliente, turnos_wa, main, mp


def test_whatsapp_procesa_el_turno_con_la_tienda_resuelta(puerta_wa):
    """El multi-tenant no lo decide el modelo: lo resuelve el backend por
    `phone_number_id`. Es la regla 2 de las tecnicas no negociables."""
    cliente, turnos, _, _ = puerta_wa
    r = cliente.post("/webhook/whatsapp", json=_payload_wa("m1", "tenes stock?"))
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert len(turnos) == 1, "el webhook devolvio 200 y NO proceso el turno"
    assert turnos[0]["tienda_id"] == TIENDA
    assert turnos[0]["text"] == "tenes stock?"


def test_whatsapp_no_procesa_el_mismo_mensaje_dos_veces(puerta_wa):
    """Meta reenvia el mismo mensaje. Sin esto, un pedido se toma dos veces."""
    cliente, turnos, _, _ = puerta_wa
    cliente.post("/webhook/whatsapp", json=_payload_wa("m2", "quiero 2 mouse"))
    r = cliente.post("/webhook/whatsapp", json=_payload_wa("m2", "quiero 2 mouse"))
    assert r.json() == {"ok": True, "duplicate": True}
    assert len(turnos) == 1, "Meta reenvio y el pedido se tomo dos veces"


def test_whatsapp_con_tienda_desconocida_no_procesa_nada(puerta_wa):
    """Un phone_id que no es de ninguna tienda no puede caer en la tienda
    default: seria contestarle a un desconocido con el catalogo de otro."""
    cliente, turnos, _, _ = puerta_wa
    r = cliente.post("/webhook/whatsapp",
                     json=_payload_wa("m3", "hola", phone_id="AJENO"))
    assert r.status_code == 200
    assert r.json().get("error") == "tienda no registrada"
    assert not turnos


def test_whatsapp_ignora_los_payloads_que_no_traen_mensaje(puerta_wa):
    """Meta manda status de entrega y de lectura por el mismo webhook. Se
    contesta 200 y no se procesa nada."""
    cliente, turnos, _, _ = puerta_wa
    for payload in ({}, {"entry": []},
                    {"entry": [{"changes": [{"value": {"statuses": [{}]}}]}]}):
        r = cliente.post("/webhook/whatsapp", json=payload)
        assert r.status_code == 200, f"payload {payload} no devolvio 200"
    assert not turnos


def test_la_verificacion_de_meta_rechaza_el_token_que_no_es(puerta):
    """El GET con el que Meta da de alta el webhook. Sin `hub.mode=subscribe`
    se rechaza sin siquiera ir a Firestore."""
    cliente = puerta[0]
    r = cliente.get("/webhook/whatsapp",
                    params={"hub.mode": "otra_cosa", "hub.challenge": "x"})
    assert r.status_code == 403


def test_la_prosa_de_la_puerta_sale_de_la_fuente(puerta):
    """`_prosa` y `_sobrecarga` son los unicos textos al cliente que escribe
    `main.py`. Tienen que salir de la fuente, no de un literal: es la regla del
    3-ago y `test_prosa_en_la_fuente.py` la exige. Aca se verifica que el
    lector ande de verdad, no solo que este escrito."""
    main = puerta[3]
    from app.core.guia_venta_prosa import mensaje
    assert main._prosa("audio_no_entendido", "RESPALDO") == mensaje(
        "audio_no_entendido", "RESPALDO")
    assert main._sobrecarga(), "el aviso de sobrecarga salio vacio"
    assert main._prosa("clave_que_no_existe_ni_va_a_existir", "RESPALDO") == \
        "RESPALDO", "el respaldo no funciona: una clave mal escrita saldria vacia"


def test_sin_clave_de_transcripcion_el_audio_devuelve_nada_y_no_revienta(monkeypatch):
    """EL CONTRATO QUE LA PUERTA DA POR SENTADO. `_process_and_reply_telegram`
    trata el `None` de `transcribir_audio` como "no se entendio" y le avisa al
    cliente. Si en vez de devolver None levantara una excepcion, el turno se
    caeria al `except` de arriba y el cliente recibiria el aviso de sobrecarga
    -que dice otra cosa- en lugar del de audio. La transcripcion de verdad sale
    a la red y esta fuera del alcance offline; ESTA rama no."""
    import app.core.transcriber as tr
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert tr.transcribir_audio(b"lo que sea") is None
