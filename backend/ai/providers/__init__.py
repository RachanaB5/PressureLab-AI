"""
PressureLab AI - Providers Package
Factory function to create the right LLM provider based on configuration.
"""

from .base import LLMProvider
from .huggingface import HuggingFaceGraniteProvider
from .watsonx import WatsonxGraniteProvider


def create_llm_provider(
    provider_type: str = "huggingface",
    hf_api_key: str = "",
    granite_model_id: str = "ibm-granite/granite-3.3-8b-instruct",
    watsonx_api_key: str = "",
    watsonx_project_id: str = "",
    watsonx_url: str = "https://us-south.ml.cloud.ibm.com",
) -> LLMProvider:
    """
    Factory function to create the appropriate LLM provider.

    Args:
        provider_type: "huggingface" or "watsonx"
        hf_api_key: Hugging Face API key
        granite_model_id: Granite model identifier
        watsonx_api_key: IBM watsonx API key
        watsonx_project_id: IBM watsonx project ID
        watsonx_url: IBM watsonx endpoint URL

    Returns:
        LLMProvider instance
    """
    if provider_type == "watsonx":
        if not watsonx_api_key or not watsonx_project_id:
            raise ValueError("watsonx provider requires WATSONX_API_KEY and WATSONX_PROJECT_ID")
        return WatsonxGraniteProvider(
            api_key=watsonx_api_key,
            project_id=watsonx_project_id,
            url=watsonx_url,
            model_id="ibm/granite-3-8b-instruct",
        )
    else:
        if not hf_api_key:
            raise ValueError("HuggingFace provider requires HF_API_KEY")
        return HuggingFaceGraniteProvider(
            api_key=hf_api_key,
            model_id=granite_model_id,
        )


__all__ = [
    "LLMProvider",
    "HuggingFaceGraniteProvider",
    "WatsonxGraniteProvider",
    "create_llm_provider",
]
