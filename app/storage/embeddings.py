"""
Cliente de embeddings con DeepSeek.
DeepSeek tiene endpoint compatible OpenAI para embeddings.
Modelo recomendado: text-embedding-3-small (compatible) o el suyo propio.

Uso:
- Al cargar producto: generar embedding una vez, guardar en Firestore.
- En búsqueda: generar embedding de la query, comparar con productos.
"""
import math
from openai import OpenAI
from app.config import get_settings
from app.logger import get_logger

log = get_logger(__name__)
settings = get_settings()

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        # Provider configurable. openai usa OPENAI_API_KEY contra api.openai.com
        # (modelo text-embedding-3-small, barato y de buena calidad). deepseek
        # queda como legacy por si algun dia expone embeddings.
        if settings.EMBEDDINGS_PROVIDER == "openai":
            _client = OpenAI(api_key=settings.OPENAI_API_KEY)
        else:
            _client = OpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url="https://api.deepseek.com/v1",
            )
    return _client


def generate_embedding(text: str, model: str | None = None) -> list[float] | None:
    """
    Genera el embedding de un texto. Devuelve lista de floats o None si falla.
    El modelo y el provider salen de settings (EMBEDDINGS_MODEL / EMBEDDINGS_PROVIDER).
    """
    try:
        client = _get_client()
        resp = client.embeddings.create(
            model=model or settings.EMBEDDINGS_MODEL,
            input=text,
        )
        return resp.data[0].embedding
    except Exception as e:
        log.warning("embedding_failed", provider=settings.EMBEDDINGS_PROVIDER,
                    error=str(e)[:120])
        return None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Similitud coseno entre dos vectores."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def generate_product_embedding(producto: dict) -> list[float] | None:
    """
    Genera embedding del producto combinando nombre + categoría + descripción.
    """
    texto = f"{producto['nombre']}. Categoría: {producto['categoria']}. {producto['descripcion']}"
    return generate_embedding(texto)
