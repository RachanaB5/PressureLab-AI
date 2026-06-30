"""
PressureLab AI - Abstract LLM Provider Interface
Modular provider design: switch between HuggingFace and watsonx without changing business logic.
"""

from abc import ABC, abstractmethod
from typing import Optional


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 1024,
        temperature: float = 0.3,
        stop: Optional[list[str]] = None,
    ) -> str:
        """Generate a completion from the LLM."""
        pass

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> str:
        """Send a chat-style request to the LLM."""
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the model identifier being used."""
        pass
