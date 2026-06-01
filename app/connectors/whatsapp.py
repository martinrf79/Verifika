"""
Conector WhatsApp Cloud API (Meta directo).
Multi-tenant: cada tienda provee su propio access_token y phone_number_id.
"""
import httpx
from app.logger import get_logger

log = get_logger(__name__)


class WhatsAppMetaConnector:
    """Conector dinamico: se instancia por tienda con su token y phone_id."""

    def __init__(self, access_token: str, phone_number_id: str):
        self.access_token = access_token
        self.phone_number_id = phone_number_id
        self.base_url = "https://graph.facebook.com/v21.0"

    async def send_message(self, user_id: str, text: str) -> bool:
        if not self.access_token or not self.phone_number_id:
            log.error("whatsapp_meta_missing_credentials")
            return False
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": user_id,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                return True
        except httpx.HTTPStatusError as e:
            log.error("whatsapp_send_http_error",
                      status=e.response.status_code,
                      body=e.response.text[:200],
                      user_id=user_id)
            return False
        except Exception as e:
            log.error("whatsapp_send_error", error=str(e), user_id=user_id)
            return False

    async def download_media(self, media_id: str) -> bytes | None:
        """Descarga un archivo multimedia de WhatsApp. Devuelve bytes o None."""
        if not self.access_token:
            return None
        headers = {"Authorization": f"Bearer {self.access_token}"}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r1 = await client.get(f"{self.base_url}/{media_id}", headers=headers)
                r1.raise_for_status()
                media_url = r1.json().get("url")
                if not media_url:
                    return None
                r2 = await client.get(media_url, headers=headers)
                r2.raise_for_status()
                return r2.content
        except Exception as e:
            log.error("whatsapp_download_error", error=str(e)[:200], media_id=media_id)
            return None


def get_whatsapp_connector_for_tienda(access_token: str,
                                      phone_number_id: str) -> WhatsAppMetaConnector:
    """Devuelve un conector configurado para una tienda especifica."""
    return WhatsAppMetaConnector(access_token, phone_number_id)


def parse_whatsapp_payload(payload: dict) -> tuple[str, str, str, str] | None:
    """
    Parsea webhook de Meta Cloud API.
    Devuelve (phone_number_id, user_id, text_o_marcador, message_id) o None.
    Para audios devuelve marcador __AUDIO__:media_id en el campo texto.
    """
    try:
        entry = payload.get("entry", [{}])[0]
        change = entry.get("changes", [{}])[0]
        value = change.get("value", {})
        metadata = value.get("metadata", {})
        phone_number_id = metadata.get("phone_number_id", "")
        messages = value.get("messages", [])
        if not messages:
            return None
        msg = messages[0]
        msg_type = msg.get("type")
        user_id = msg.get("from")
        message_id = msg.get("id", "")

        if msg_type == "text":
            text = msg.get("text", {}).get("body")
        elif msg_type in ("audio", "voice"):
            media_id = msg.get(msg_type, {}).get("id")
            if not media_id:
                return None
            text = f"__AUDIO__:{media_id}"
        else:
            log.info("whatsapp_unsupported_type_ignored", type=msg_type)
            return None

        if not user_id or not text or not phone_number_id:
            return None
        return (phone_number_id, user_id, text, message_id)
    except (IndexError, KeyError, AttributeError) as e:
        log.error("whatsapp_parse_error", error=str(e))
        return None
