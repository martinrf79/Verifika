"""Conector Telegram: webhook + envio de mensajes + descarga de audio."""
import httpx
from app.connectors.base import BaseConnector
from app.config import get_settings
from app.logger import get_logger

log = get_logger(__name__)
settings = get_settings()


class TelegramConnector(BaseConnector):
    def __init__(self):
        self.token = settings.TELEGRAM_TOKEN
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    async def send_message(self, user_id: str, text: str) -> bool:
        """Envia mensaje a un chat de Telegram."""
        if not self.token:
            log.error("telegram_no_token")
            return False
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": user_id,
            "text": text,
            "parse_mode": "HTML",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                return True
        except Exception as e:
            log.error("telegram_send_error", error=str(e), user_id=user_id)
            return False

    async def download_file(self, file_id: str) -> bytes | None:
        """Descarga un archivo de Telegram por file_id. Devuelve bytes o None."""
        if not self.token:
            return None
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r1 = await client.get(f"{self.base_url}/getFile", params={"file_id": file_id})
                r1.raise_for_status()
                file_path = r1.json().get("result", {}).get("file_path")
                if not file_path:
                    return None
                url_file = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
                r2 = await client.get(url_file)
                r2.raise_for_status()
                return r2.content
        except Exception as e:
            log.error("telegram_download_error", error=str(e)[:200], file_id=file_id)
            return None

    def parse_incoming(self, payload: dict) -> tuple[str, str] | None:
        """Parsea el webhook de Telegram.

        Devuelve tupla chat_id, contenido.
        Contenido puede ser texto plano o marcador audio file_id para audios.
        """
        message = payload.get("message")
        if not message:
            return None
        chat_id = message.get("chat", {}).get("id")
        if not chat_id:
            return None

        text = message.get("text")
        if text:
            return (str(chat_id), text)

        voice = message.get("voice") or message.get("audio")
        if voice:
            file_id = voice.get("file_id")
            if file_id:
                return (str(chat_id), f"__AUDIO__:{file_id}")

        return None


_telegram_connector: TelegramConnector | None = None


def get_telegram_connector() -> TelegramConnector:
    global _telegram_connector
    if _telegram_connector is None:
        _telegram_connector = TelegramConnector()
    return _telegram_connector
