"""
PressureLab AI - Hugging Face Granite Provider
Primary inference provider using IBM Granite models via Hugging Face Inference API.
"""

import httpx
import json
import logging
from typing import Optional
from .base import LLMProvider

logger = logging.getLogger(__name__)


class HuggingFaceGraniteProvider(LLMProvider):
    """
    IBM Granite inference via Hugging Face Inference API.
    Uses the conversational endpoint for chat-style interactions.
    """

    def __init__(self, api_key: str, model_id: str = "ibm-granite/granite-3.3-8b-instruct"):
        self.api_key = api_key
        self.model_id = model_id
        self.INFERENCE_URL = f"https://api-inference.huggingface.co/models/{self.model_id}/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        logger.info(f"Initialized HuggingFace Granite provider with model: {model_id}")

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 1024,
        temperature: float = 0.3,
        stop: Optional[list[str]] = None,
    ) -> str:
        """Generate completion using the chat endpoint with a single user message."""
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
        """Send chat messages to Granite via HuggingFace Inference API."""
        payload = {
            "model": self.model_id,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.INFERENCE_URL,
                    headers=self.headers,
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()

                # Extract the assistant's response
                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0].get("message", {}).get("content", "")
                    return content.strip()

                logger.warning(f"Unexpected response format: {result}")
                return self._fallback_response(messages)

        except httpx.HTTPStatusError as e:
            logger.error(f"HuggingFace API error: {e.response.status_code} - {e.response.text}")
            return self._fallback_response(messages)
        except Exception as e:
            logger.error(f"HuggingFace API error: {e}")
            return self._fallback_response(messages)

    def get_model_name(self) -> str:
        return self.model_id

    def _fallback_response(self, messages: list[dict]) -> str:
        """Signal failure — GraniteClient uses event-grounded deterministic output."""
        return ""
