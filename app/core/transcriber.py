"""Transcripcion de audio usando Groq Whisper."""
import os
import tempfile
from groq import Groq
from app.logger import get_logger

log = get_logger(__name__)


def transcribir_audio(audio_bytes: bytes, filename: str = "audio.ogg") -> str | None:
    """Recibe bytes de audio y devuelve texto transcrito.

    Retorna None si falla.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        log.error("transcriber_no_groq_key")
        return None

    try:
        client = Groq(api_key=api_key)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        with open(tmp_path, "rb") as f:
            transcription = client.audio.transcriptions.create(
                file=(filename, f.read()),
                model="whisper-large-v3-turbo",
                language="es",
                response_format="text",
            )

        os.unlink(tmp_path)
        texto = str(transcription).strip()
        log.info("transcriber_ok", chars=len(texto))
        return texto
    except Exception as e:
        log.error("transcriber_error", error=str(e)[:200])
        return None
