"""
LLM Provider Interface and Concrete Implementations.

Architectural Guarantees:
1. Unified Interface: provider.complete(system, user, json_schema) -> dict
2. Resilience: Built-in timeouts, exponential backoff retries, and never crashes calling processes.
3. Swappability: Cleanly separates LLM vendor details behind a single abstract interface.
"""

import abc
import json
import logging
import time
from typing import Any, Dict, Optional

import httpx

from app.config import settings

logger = logging.getLogger("app.llm.provider")


class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""
    pass


class LLMProvider(abc.ABC):
    """
    Abstract LLM Provider interface.
    """

    @abc.abstractmethod
    def complete(
        self,
        system: str,
        user: str,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes an LLM completion returning a parsed JSON dictionary.
        Must handle retries, timeout, and raise LLMProviderError on hard failure.
        """
        pass


class UnifiedHttpLLMProvider(LLMProvider):
    """
    Production-grade HTTP client supporting Google Gemini and OpenAI REST endpoints
    with timeouts, exponential backoff retries, and structured JSON output.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: float = 15.0,
        max_retries: int = 2,
    ):
        self.api_key = api_key or settings.LLM_API_KEY
        self.model = model or settings.LLM_MODEL
        self.timeout = timeout_seconds
        self.max_retries = max_retries

    def complete(
        self,
        system: str,
        user: str,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.api_key or self.api_key.startswith("your_") or self.api_key.strip() == "":
            raise LLMProviderError("No valid LLM_API_KEY configured. Triggering graceful deterministic fallback.")

        is_gemini = "gemini" in self.model.lower()

        last_err: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                if is_gemini:
                    return self._call_gemini(system, user, json_schema)
                else:
                    return self._call_openai(system, user, json_schema)
            except Exception as e:
                last_err = e
                logger.warning(
                    f"LLM call attempt {attempt + 1}/{self.max_retries + 1} failed: {e}. "
                    f"Retrying..." if attempt < self.max_retries else "No more retries."
                )
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)  # 1s, 2s

        raise LLMProviderError(f"LLM completion failed after {self.max_retries + 1} attempts: {last_err}")

    def _call_gemini(
        self,
        system: str,
        user: str,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        
        generation_config: Dict[str, Any] = {
            "responseMimeType": "application/json",
            "temperature": 0.2,
        }
        if json_schema:
            generation_config["responseSchema"] = json_schema

        payload = {
            "systemInstruction": {
                "parts": [{"text": system}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user}]
                }
            ],
            "generationConfig": generation_config,
        }

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

            # Extract generated text from Gemini response structure
            candidates = data.get("candidates", [])
            if not candidates:
                raise LLMProviderError("Gemini API returned no completion candidates.")
            
            raw_text = candidates[0]["content"]["parts"][0]["text"]
            return json.loads(raw_text)

    def _call_openai(
        self,
        system: str,
        user: str,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            raw_text = data["choices"][0]["message"]["content"]
            return json.loads(raw_text)


_default_provider: Optional[LLMProvider] = None


def get_llm_provider() -> LLMProvider:
    """
    Factory function returning the configured LLM provider instance.
    """
    global _default_provider
    if _default_provider is None:
        _default_provider = UnifiedHttpLLMProvider()
    return _default_provider


def set_llm_provider(provider: LLMProvider) -> None:
    """
    Allows injecting a custom or mock LLM provider for automated testing.
    """
    global _default_provider
    _default_provider = provider
