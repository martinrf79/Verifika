"""Interfaz base para conectores de mensajería."""
from abc import ABC, abstractmethod


class BaseConnector(ABC):
    """
    Interfaz que todos los conectores (Telegram, WhatsApp) deben implementar.
    El núcleo no sabe ni le importa qué conector se usa.
    """

    @abstractmethod
    async def send_message(self, user_id: str, text: str) -> bool:
        """Envía un mensaje al usuario."""
        pass

    @abstractmethod
    def parse_incoming(self, payload: dict) -> tuple[str, str] | None:
        """
        Parsea un webhook entrante y devuelve (user_id, message_text).
        Devuelve None si no es un mensaje procesable.
        """
        pass
