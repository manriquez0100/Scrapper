"""LLM Provider - matches ExamenIntegra analyzer.ts pattern exactly (no auth header)"""

import os
import httpx
from abc import ABC, abstractmethod
from typing import List, Dict, Any


class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, messages: List[Dict[str, str]], **kwargs) -> str:
        pass


class LMStudioProvider(LLMProvider):
    """Matches analyzer.ts callAI() pattern exactly - no auth header"""
    
    def __init__(self, base_url: str = None, model: str = None):
        raw_url = base_url or os.getenv("LM_STUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
        if raw_url.endswith("/v1"):
            self.base_url = raw_url[:-3]
        else:
            self.base_url = raw_url.rstrip("/")
        self.chat_url = f"{self.base_url}/v1/chat/completions"
        self.model = model or os.getenv("LM_STUDIO_MODEL", "google/gemma-4-e4b")
        self.timeout_seconds = float(os.getenv("LM_STUDIO_TIMEOUT_SECONDS", "180"))
        self._client: httpx.AsyncClient | None = None
        self._headers = {"Content-Type": "application/json"}

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout_seconds)
        return self._client

    async def generate(self, messages: List[Dict[str, str]], **kwargs) -> str:
        temperature = kwargs.get("temperature", 0.1)
        max_tokens = kwargs.get("max_tokens", 800)
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "text"}
        }
        
        client = await self._get_client()
        response = await client.post(
            self.chat_url,
            headers=self._headers,
            json=payload
        )
        
        if not response.is_success:
            error_text = response.text
            raise Exception(f"LM Studio API error: {response.status_code} - {error_text}")
        
        data = response.json()
        content = data["choices"][0]["message"].get("content", "")
        return content if isinstance(content, str) else ""

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


def get_llm_provider() -> LLMProvider:
    return LMStudioProvider()


if __name__ == "__main__":
    import asyncio
    async def test():
        provider = get_llm_provider()
        result = await provider.generate([{"role": "user", "content": "Say hello in Spanish"}])
        print(result)
    asyncio.run(test())
