"""
JUEZ LLM PARA DEEPEVAL — atado a DeepSeek.

DeepEval juzga con OpenAI por default; este wrapper lo reemplaza para que las
metricas (faithfulness, hallucination, answer relevancy, G-Eval) las evalue el
MISMO modelo barato que ya paga el proyecto. Regla del repo: DeepSeek por
default, no OpenAI/Gemini/Claude sin permiso de Martin.

Contrato de DeepEval 4.x para un modelo CUSTOM (no nativo): la metrica llama
generate(prompt, schema=Pydantic) y espera de vuelta, SIN tupla de costo, o bien
una instancia del schema o bien un JSON string que DeepEval parsea. Sin schema,
espera texto crudo. Por eso generate() devuelve el resultado pelado, no (out, cost).
"""
import asyncio
import json
import os
from typing import Optional

from openai import OpenAI
from pydantic import BaseModel
from deepeval.models.base_model import DeepEvalBaseLLM

_BASE_DEFAULT = "https://api.deepseek.com/v1"


def _thinking_off(model: str) -> dict:
    """Los DeepSeek v4 razonan por default y el pensamiento se come los tokens
    de la respuesta (JSON vacio o cortado). Se apaga igual que en el camino vivo
    (app/verifika/llm_adapter._deepseek_thinking_off)."""
    return ({"extra_body": {"thinking": {"type": "disabled"}}}
            if "v4" in model.lower() else {})


class JuezDeepSeek(DeepEvalBaseLLM):
    """Modelo juez para DeepEval, cliente OpenAI-compatible contra DeepSeek."""

    def __init__(self, model: Optional[str] = None,
                 base_url: Optional[str] = None):
        # OJO: DeepEvalBaseLLM.__init__ pisa self.model con load_model(). El id
        # del modelo va en self.model_id para que no lo aplaste.
        self.model_id = model or os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
        self.base_url = base_url or os.getenv("DEEPSEEK_BASE_URL", _BASE_DEFAULT)
        self._client: Optional[OpenAI] = None
        super().__init__(self.model_id)

    # ── contrato DeepEvalBaseLLM ────────────────────────────────────────────
    def load_model(self) -> OpenAI:
        if self._client is None:
            key = os.getenv("DEEPSEEK_API_KEY", "")
            if not key:
                raise RuntimeError(
                    "Falta DEEPSEEK_API_KEY: el juez de DeepEval corre sobre DeepSeek.")
            self._client = OpenAI(api_key=key, base_url=self.base_url)
        return self._client

    def get_model_name(self) -> str:
        return f"deepseek:{self.model_id}"

    def supports_structured_outputs(self) -> Optional[bool]:
        # DeepSeek /v1 no acepta el response_format=schema estricto de OpenAI;
        # se ata por json_object + parse manual.
        return False

    def supports_json_mode(self) -> Optional[bool]:
        return True

    # ── generacion ──────────────────────────────────────────────────────────
    def _completar(self, prompt: str, como_json: bool) -> str:
        client = self.load_model()
        kwargs = dict(
            model=self.model_id,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        if como_json:
            kwargs["response_format"] = {"type": "json_object"}
        kwargs.update(_thinking_off(self.model_id))
        resp = client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""

    def generate(self, prompt: str, schema: Optional[BaseModel] = None):
        if schema is None:
            return self._completar(prompt, como_json=False)
        crudo = self._completar(prompt, como_json=True)
        # DeepEval sabe parsear un JSON string; le devolvemos ya la instancia si
        # valida, y si no, el string crudo para que su parser tolerante lo intente.
        try:
            data = json.loads(crudo)
            return schema.model_validate(data)
        except Exception:
            return crudo

    async def a_generate(self, prompt: str, schema: Optional[BaseModel] = None):
        return await asyncio.to_thread(self.generate, prompt, schema)
