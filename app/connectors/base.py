"""Interfaz base para conectores de mensajería."""
from abc import ABC, abstractmethod

from app.logger import get_logger

log = get_logger(__name__)

# Un mensaje corto solo no se manda: se pega al anterior.
_MIN_PARTE = 120
_MAX_PARTES = 3


def partir_respuesta(texto: str) -> list[str]:
    """Parte la respuesta en 2 o 3 mensajes para que el cliente empiece a leer antes (pedido de Martin, 30-jul)."""
    t = str(texto or "").strip()
    if not t:
        return []
    bloques = [b.strip() for b in t.split("\n\n") if b.strip()]
    if len(bloques) < 2:
        return [t]
    partes: list[str] = []
    for b in bloques:
        # se acumula mientras la parte en curso no tenga cuerpo, y una vez
        # llegado al tope todo lo que queda va en la ultima.
        if partes and (len(partes[-1]) < _MIN_PARTE
                       or len(partes) >= _MAX_PARTES):
            partes[-1] += "\n\n" + b
        else:
            partes.append(b)
    return partes or [t]


async def enviar_respuesta(connector, user_id: str, texto: str) -> bool:
    """Manda la respuesta en partes, EN ORDEN y esperando cada una: mandarlas de a varias en paralelo las puede
    entregar desordenadas, y una respuesta desordenada es peor que una lenta."""
    partes = partir_respuesta(texto)
    if len(partes) <= 1:
        return await connector.send_message(user_id, texto)
    for i, p in enumerate(partes):
        ok = await connector.send_message(user_id, p)
        if not ok:
            log.warning("envio_parcial", user_id=user_id, parte=i + 1,
                        total=len(partes))
            return False
    log.info("envio_en_partes", user_id=user_id, partes=len(partes))
    return True


class BaseConnector(ABC):
    """Interfaz que todos los conectores (Telegram, WhatsApp) deben implementar."""

    @abstractmethod
    async def send_message(self, user_id: str, text: str) -> bool:
        """Envía un mensaje al usuario."""
        pass

    @abstractmethod
    def parse_incoming(self, payload: dict) -> tuple[str, str] | None:
        """Parsea un webhook entrante y devuelve (user_id, message_text)."""
        pass
