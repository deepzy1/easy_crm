from abc import ABC, abstractmethod
from dataclasses import dataclass
import time

import httpx
from app.core.config import Settings


class ProviderError(Exception):
    def __init__(self, code: str, message: str, status: int = 502):
        self.code, self.message, self.status = code, message, status


@dataclass
class Generation:
    provider: str
    model: str
    text: str
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int


class TextProvider(ABC):
    def __init__(self, settings: Settings, transport=None):
        self.settings, self.transport = settings, transport

    @abstractmethod
    async def generate(self, model: str, prompt: str) -> Generation: ...

    async def check_connection(self, model: str) -> Generation:
        return await self.generate(model, "Reply with the word Connected.")

    async def post(self, url, headers, body):
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.ai_timeout_seconds, transport=self.transport, follow_redirects=False
            ) as client:
                response = await client.post(url, headers=headers, json=body)
        except httpx.TimeoutException:
            raise ProviderError("provider_timeout", "Provider timed out. No automatic retry was made.", 504)
        except httpx.RequestError:
            raise ProviderError("provider_unavailable", "Unable to connect to provider. Try again later.")
        if response.status_code in (401, 403):
            raise ProviderError("provider_auth", "Provider rejected the server credentials or model access.")
        if response.status_code == 429:
            raise ProviderError("provider_rate_limit", "Provider quota or rate limit reached.", 429)
        if response.status_code >= 400:
            raise ProviderError(
                "provider_rejected",
                "Provider rejected this request. Check model availability and configuration.",
            )
        try:
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError()
            return data
        except ValueError:
            raise ProviderError("provider_response", "Provider returned an invalid response.")

    def key(self, provider):
        value = getattr(self.settings, f"{provider}_api_key").get_secret_value()
        if not value:
            raise ProviderError(
                "missing_credentials", f"Set {provider.upper()}_API_KEY on the server first.", 503
            )
        return value


class GeminiProvider(TextProvider):
    async def generate(self, model, prompt):
        key = self.key("gemini")
        started = time.monotonic()
        data = await self.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            {"x-goog-api-key": key},
            {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": 2048},
            },
        )
        try:
            text = "\n".join(p["text"] for p in data["candidates"][0]["content"]["parts"] if "text" in p)
            usage = data.get("usageMetadata", {})
            if not text.strip():
                raise ValueError()
            return Generation(
                "gemini",
                model,
                text,
                usage.get("promptTokenCount"),
                usage.get("candidatesTokenCount"),
                int((time.monotonic() - started) * 1000),
            )
        except (KeyError, IndexError, TypeError, ValueError):
            raise ProviderError(
                "provider_response", "Provider returned no usable text (possibly blocked or truncated)."
            )


class NvidiaProvider(TextProvider):
    async def generate(self, model, prompt):
        key = self.key("nvidia")
        started = time.monotonic()
        data = await self.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            {"Authorization": f"Bearer {key}"},
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 2048,
                "stream": False,
            },
        )
        try:
            text = data["choices"][0]["message"]["content"]
            if not isinstance(text, str) or not text.strip():
                raise ValueError()
            usage = data.get("usage", {})
            return Generation(
                "nvidia",
                model,
                text,
                usage.get("prompt_tokens"),
                usage.get("completion_tokens"),
                int((time.monotonic() - started) * 1000),
            )
        except (KeyError, IndexError, TypeError, ValueError):
            raise ProviderError(
                "provider_response", "Provider returned no usable text (possibly token budget exhausted)."
            )


def provider_for(name: str, settings: Settings) -> TextProvider:
    if name == "gemini":
        return GeminiProvider(settings)
    if name == "nvidia":
        return NvidiaProvider(settings)
    raise ProviderError("invalid_provider", "Unknown AI provider.", 422)


def validate_model(settings: Settings, provider: str, model: str):
    if provider not in ("gemini", "nvidia") or model not in getattr(settings, f"{provider}_models", []):
        raise ProviderError(
            "invalid_model",
            "This model is not in the server catalogue. Ask an admin to update configuration.",
            422,
        )
