"""Shared transport, safe diagnostics, and provider dispatch.

Never retain provider payloads, exception messages, credentials, or URLs in errors/logs.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import logging
import re

import httpx
from app.core.config import Settings

logger = logging.getLogger("easycrm.ai")


class ProviderError(Exception):
    def __init__(self, code: str, message: str, status: int = 502, upstream_status: int | None = None):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status
        self.upstream_status = upstream_status

    def public(self):
        return {"code": self.code, "message": self.message, "upstream_status": self.upstream_status}


@dataclass
class Generation:
    provider: str
    model: str
    text: str
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int


def validate_identifier(model: str):
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._/-]{0,199}", model) or any(
        part in ("", ".", "..") for part in model.split("/")
    ):
        raise ProviderError("invalid_model", "Invalid provider model identifier.", 422)


def response_error(response: httpx.Response) -> ProviderError:
    """Use upstream text only to classify; return exclusively authored messages."""
    try:
        body = response.json()
        error = body.get("error", {}) if isinstance(body, dict) else {}
        signal = str(error).lower()
    except ValueError:
        signal = ""
    status = response.status_code
    if status == 401 or any(
        x in signal
        for x in (
            "api_key_invalid",
            "api key not valid",
            "invalid api key",
            "api key expired",
            "api_key_expired",
            "invalid_api_key",
            "api key was reported as leaked",
            "api key has been revoked",
            "unauthenticated",
        )
    ):
        code, message = (
            "provider_auth",
            "API key is invalid or expired. Ask an admin to replace the server API key and restart the backend.",
        )
    elif status == 429:
        code, message = (
            "provider_rate_limit",
            "Provider rate limit or quota reached. Check your project's limits and quota reset time; retry manually later.",
        )
    elif status == 402 or any(
        x in signal
        for x in (
            "billing",
            "payment required",
            "payment_required",
            "credit balance",
            "insufficient credits",
            "prepay",
            "free tier is not available",
            "free_tier_not_available",
        )
    ):
        code, message = (
            "provider_billing",
            "Provider billing or tier access is restricted. Check the provider project's billing, credits, and regional eligibility before retrying.",
        )
    elif status == 403:
        code, message = (
            "provider_access",
            "Provider access is restricted. Check server API key permissions, enabled API, region, and model access.",
        )
    elif status == 404 or (
        status == 400
        and any(
            x in signal
            for x in (
                "model_not_found",
                "model not found",
                "not supported for generatecontent",
                "model is not supported",
                "model is not available",
                "model not available",
                "no longer available",
                "not found for api version",
                "unsupported model",
            )
        )
    ):
        code, message = (
            "provider_model_unavailable",
            "Model is unavailable for this API key or API version. Refresh Models and select another text model; the model may have retired or access may be restricted.",
        )
    elif status == 400:
        code, message = (
            "provider_request",
            "Provider rejected the request format or parameters. Refresh Models, select a compatible text model, and check the server adapter configuration.",
        )
    elif status in (408, 504):
        code, message = "provider_timeout", "Provider timed out. Retry manually; no automatic retry was made."
    else:
        code, message = "provider_unavailable", "Provider is temporarily unavailable. Retry manually later."
    return ProviderError(code, message, 429 if status == 429 else 502, status)


class TextProvider(ABC):
    name: str

    def __init__(self, settings: Settings, transport=None):
        self.settings, self.transport = settings, transport

    @abstractmethod
    async def generate(self, model: str, prompt: str, *, test: bool = False) -> Generation: ...

    @abstractmethod
    async def list_models(self) -> list[dict]: ...

    async def check_connection(self, model: str) -> Generation:
        return await self.generate(model, "Reply with the word Connected.", test=True)

    async def request(self, method, url, headers, *, body=None, params=None):
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.ai_timeout_seconds, transport=self.transport, follow_redirects=False
            ) as client:
                response = await client.request(method, url, headers=headers, json=body, params=params)
        except httpx.TimeoutException:
            raise ProviderError(
                "provider_timeout", "Provider timed out. No automatic retry was made.", 504
            ) from None
        except httpx.RequestError:
            raise ProviderError(
                "provider_network", "Unable to reach provider. Check server network/DNS and retry manually."
            ) from None
        if response.status_code >= 300:
            exc = response_error(response)
            logger.warning(
                "provider_failure provider=%s upstream_status=%s category=%s",
                self.name,
                response.status_code,
                exc.code,
            )
            raise exc
        try:
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError()
            return data
        except ValueError:
            raise ProviderError("provider_response", "Provider returned an invalid response.") from None

    async def post(self, url, headers, body):
        return await self.request("POST", url, headers, body=body)

    def key(self, provider):
        value = getattr(self.settings, f"{provider}_api_key").get_secret_value()
        if not value:
            raise ProviderError(
                "missing_credentials", f"Set {provider.upper()}_API_KEY on the server first.", 503
            )
        return value


def provider_for(name: str, settings: Settings) -> TextProvider:
    from app.ai.gemini import GeminiProvider
    from app.ai.nvidia import NvidiaProvider

    if name == "gemini":
        return GeminiProvider(settings)
    if name == "nvidia":
        return NvidiaProvider(settings)
    raise ProviderError("invalid_provider", "Unknown AI provider.", 422)
