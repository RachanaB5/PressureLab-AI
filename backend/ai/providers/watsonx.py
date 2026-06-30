"""
PressureLab AI - IBM watsonx.ai Granite Provider
Alternative inference provider using IBM watsonx.ai SDK.
Switch to this provider by setting LLM_PROVIDER=watsonx in .env
"""

import logging
from typing import Optional
from .base import LLMProvider

logger = logging.getLogger(__name__)


class WatsonxGraniteProvider(LLMProvider):
    """
    IBM Granite inference via watsonx.ai SDK.
    Requires: pip install ibm-watsonx-ai
    """

    def __init__(self, api_key: str, project_id: str, url: str = "https://us-south.ml.cloud.ibm.com",
                 model_id: str = "ibm/granite-3-8b-instruct"):
        self.api_key = api_key
        self.project_id = project_id
        self.url = url
        self.model_id = model_id
        self._client = None
        logger.info(f"Initialized watsonx Granite provider with model: {model_id}")

    def _get_client(self):
        """Lazy initialization of watsonx client."""
        if self._client is None:
            try:
                from ibm_watsonx_ai.foundation_models import ModelInference
                from ibm_watsonx_ai import Credentials

                credentials = Credentials(url=self.url, api_key=self.api_key)
                self._client = ModelInference(
                    model_id=self.model_id,
                    credentials=credentials,
                    project_id=self.project_id,
                )
            except ImportError:
                logger.error("ibm-watsonx-ai package not installed. Install with: pip install ibm-watsonx-ai")
                raise
        return self._client

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 1024,
        temperature: float = 0.3,
        stop: Optional[list[str]] = None,
    ) -> str:
        """Generate completion via watsonx.ai."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return await self.chat(messages, max_tokens, temperature)

    async def chat(
        self,
        messages: list[dict],
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> str:
        """Chat with Granite via watsonx.ai SDK."""
        try:
            client = self._get_client()
            response = client.chat(
                messages=messages,
                params={
                    "max_new_tokens": max_tokens,
                    "temperature": temperature,
                }
            )

            if "choices" in response and len(response["choices"]) > 0:
                return response["choices"][0]["message"]["content"].strip()

            return ""

        except Exception as e:
            logger.error(f"watsonx API error: {e}")
            return ""

    def get_model_name(self) -> str:
        return self.model_id
