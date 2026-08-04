"""
EL CLON DE PRODUCCION. El banco corre el MISMO codigo que el bot vivo.

POR QUE EXISTE (Martin, 31-jul-2026). Decenas de veces el deploy salio verde y
la PRIMERA charla real trajo errores y alucinaciones. La causa no era el modelo:
era que el banco probaba OTRO camino. Llamaba a `procesar_venta` directo, asi
que se salteaba el antijailbreak, el RESET_CODE y, sobre todo, el PARTIDO del
mensaje: el juez leia un bloque entero que el cliente nunca recibe entero.

Este modulo saca la copia del medio. `turno()` llama a la funcion REAL del
webhook de WhatsApp, `app.main._process_and_reply_whatsapp`, con un conector de
mentira que en vez de pegarle a Meta guarda los mensajes. Todo lo de adentro
-orchestrator, antijailbreak, hub atado, interprete, solver, guardias, cierre,
memoria, particion en partes, y hasta el fallback de "estoy con mucha demanda"-
es el mismo codigo que corre en la nube, sin una linea reescrita.

QUE SIGUE SIENDO DISTINTO, y no se puede evitar:
  1. La llamada HTTP a Meta. El conector guarda en vez de mandar. Es lo unico
     que el cliente no ve igual, y no cambia el texto ni una coma.
  2. Firestore es el doble en RAM (`sim_firestore`), cargado con el catalogo,
     la FAQ y la CONFIG reales. `verificar_clon.py` confirma que no derivo.
  3. El audio: la transcripcion no se ejercita (el banco manda texto).
  4. La env de Cloud Run. `verificar_clon.py` lista lo que no se puede leer
     desde afuera; el banner de cada corrida imprime lo que el clon usa, para
     que una diferencia se vea en la primera linea y no en la charla real.

USO, y el orden importa:
    from banco_pruebas import clon_produccion
    clon_produccion.preparar_entorno()      # ANTES de importar app.*
    info = clon_produccion.instalar()
    partes = await clon_produccion.turno("cliente1", "hola, tenes notebooks?")

`preparar_entorno()` va primero porque `app.config` lee el entorno al importarse:
si se importa antes, el clon queda con la clave y la tienda equivocadas.
"""
import os
from pathlib import Path

TIENDA = "verifika_prod"

# Datos del canal. En produccion son el token y el phone_number_id de Meta; el
# codigo los usa solo para construir el conector, que aca esta doblado.
_TOKEN_BANCO = "banco-token"
_PHONE_ID_BANCO = "banco-phone-id"

_conectores: dict = {}
_preparado = False


class ConectorBanco:
    """El conector de WhatsApp, con el envio doblado. Implementa lo que
    `_process_and_reply_whatsapp` le pide: `send_message` y `download_media`.
    Guarda cada parte por separado, que es como la recibe el cliente."""

    def __init__(self, user_id: str = ""):
        self.user_id = user_id
        self.enviados: list[str] = []
        self.fallas = 0

    async def send_message(self, user_id: str, text: str) -> bool:
        self.enviados.append(text)
        return True

    async def download_media(self, media_id: str):
        return None


def preparar_entorno() -> dict:
    """Deja el entorno como el de la nube. Correr ANTES de importar `app.*`.

    Lo unico que toca:
      - GEMINI_API_KEY: el codigo lee SOLO ese nombre. La clave paga viaja en
        GEMINI_API_KEY_PROD.
      - TIENDA_ID: la tienda viva.

    LA CLAVE PAGA AHORA SE PIDE, NO SE TOMA (Martin, 4-ago-2026). Hasta hoy esto
    cambiaba SOLO a la paga con que `GEMINI_API_KEY_PROD` estuviera en el
    entorno, y en las maquinas de trabajo esa env esta siempre puesta: o sea que
    TODA corrida de banco iba a la clave paga sin que nadie lo pidiera. Con
    varias corridas de 130 turnos por dia eso se llevo mas de diez dolares en
    unos dias, y ninguna de esas corridas NECESITABA la paga: el banco mide
    comportamiento, no cuota.

    Ahora el default es la clave GRATIS y la paga entra solo con
    `BANCO_CLAVE_PAGA=true`. Si el limite gratis se agota la corrida lo va a
    mostrar como 429 y ahi se decide gastar, que es una decision y no un
    accidente.
    """
    global _preparado
    paga = (os.environ.get("GEMINI_API_KEY_PROD") or "").strip()
    quiere_paga = os.environ.get("BANCO_CLAVE_PAGA", "").lower() == "true"
    if paga and quiere_paga:
        os.environ["GEMINI_API_KEY"] = paga
        detalle = {"clave": "GEMINI_API_KEY_PROD (PAGA, pedida a proposito)"}
    else:
        # No alcanza con no pisarla: si el proceso hereda la paga en
        # GEMINI_API_KEY, seguiria gastando. Se fuerza la gratis.
        gratis = (os.environ.get("GEMINI_API_KEY_FREE")
                  or os.environ.get("GEMINI_API_KEY") or "").strip()
        if gratis and gratis == paga:
            log_msg = ("GEMINI_API_KEY es la MISMA que la paga: no hay clave "
                       "gratis distinta en el entorno")
            detalle = {"clave": f"gratis NO disponible ({log_msg})"}
        else:
            os.environ["GEMINI_API_KEY"] = gratis
            detalle = {"clave": "GEMINI_API_KEY (gratis, default)"}
    os.environ.setdefault("TIENDA_ID", TIENDA)
    _preparado = True
    return detalle


def instalar() -> dict:
    """Instala el doble de Firestore y engancha el conector de banco en el
    camino vivo. Devuelve el inventario para el banner de la corrida."""
    if not _preparado:
        preparar_entorno()

    from banco_pruebas.sim_firestore import install
    info = install()

    import app.main as main

    def _conector(token: str, phone_number_id: str):
        # Uno por corrida, no por usuario: `_process_and_reply_whatsapp` lo pide
        # de nuevo en su rama de error y tiene que ser el mismo.
        return _conectores.setdefault("actual", ConectorBanco())

    main.get_whatsapp_connector_for_tienda = _conector

    from app.config import get_settings
    from app.core.leads import modo_cierre
    settings = get_settings()
    info.update({
        "solver_model": settings.GEMINI_MODEL,
        "interprete": settings.INTERPRETER_PROVIDER,
        "tienda": settings.TIENDA_ID,
        "modo_cierre": modo_cierre(TIENDA),
        "clave": ("PROD (paga)" if (os.environ.get("GEMINI_API_KEY_PROD") or "")
                  .strip() == (os.environ.get("GEMINI_API_KEY") or "").strip()
                  and os.environ.get("GEMINI_API_KEY_PROD") else "GEMINI_API_KEY"),
        "config_tienda": sorted(_config_cargada()),
    })
    return info


def _config_cargada() -> list:
    from banco_pruebas import sim_firestore
    return list(sim_firestore._CONFIG.keys())


async def turno(user_id: str, texto: str) -> list[str]:
    """Un turno completo por el camino VIVO. Devuelve las partes tal como las
    recibe el cliente en WhatsApp: una por mensaje, en orden."""
    import app.main as main

    conector = _conectores.setdefault("actual", ConectorBanco())
    conector.enviados = []
    await main._process_and_reply_whatsapp(
        TIENDA, user_id, texto, _TOKEN_BANCO, _PHONE_ID_BANCO)
    return list(conector.enviados)


def reiniciar_cliente(user_id: str) -> None:
    """Borra la conversacion y los leads del usuario, como el RESET_CODE."""
    from app.storage.firestore_client import reset_conversation
    from app.core.leads import descartar_leads_activos
    try:
        reset_conversation(user_id, tienda_id=TIENDA)
    except Exception:
        pass
    try:
        descartar_leads_activos(user_id, "whatsapp", TIENDA)
    except Exception:
        pass


def sembrar_conversacion(user_id: str, history: list, summary: str = "",
                         **extra) -> None:
    """Arranca la charla con memoria previa, como le pasa a un cliente que ya
    hablo antes. En produccion NADIE arranca en cero; el banco si, y por eso no
    veia los defectos que solo aparecen con historia encima."""
    from app.storage.firestore_client import save_conversation
    save_conversation(user_id, history, summary, tienda_id=TIENDA, **extra)


# El texto exacto del fallback de produccion. Si sale esto, el turno EXPLOTO y
# el cliente recibio una disculpa en vez de una respuesta: es una falla, no una
# respuesta pobre, y el banco tiene que gritarlo.
FALLBACK_PRODUCCION = "estoy con mucha demanda en este momento"


def es_fallback(texto: str) -> bool:
    return FALLBACK_PRODUCCION in (texto or "").lower()
