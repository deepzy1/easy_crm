import time

from app.ai.providers import Generation, ProviderError, TextProvider, validate_identifier

BASE = "https://integrate.api.nvidia.com/v1"


def configured_models(settings):
    return [
        {
            "id": model,
            "resource_name": model,
            "name": model,
            "family": "Nemotron" if "nemotron" in model.lower() else model.split("/")[0],
            "capabilities": ["chat/completions"],
            "availability": "unknown",
            "source": "configured",
        }
        for model in settings.nvidia_models
    ]


class NvidiaProvider(TextProvider):
    name = "nvidia"

    async def list_models(self):
        # NVIDIA's generic catalogue does not guarantee chat capability. The server
        # list is an explicit chat allowlist, with presence refreshed from /models.
        data = await self.request("GET", f"{BASE}/models", {"Authorization": f"Bearer {self.key('nvidia')}"})
        rows = data.get("data")
        if not isinstance(rows, list) or any(
            not isinstance(row, dict) or not isinstance(row.get("id"), str) for row in rows
        ):
            raise ProviderError("provider_response", "Provider returned an invalid model catalogue.")
        if data.get("has_more"):
            raise ProviderError(
                "provider_response",
                "NVIDIA returned an incomplete catalogue. Use the configured chat catalogue and retry refresh later.",
            )
        ids = {row["id"] for row in rows}
        return [
            {**row, "availability": "available" if row["id"] in ids else "unavailable"}
            for row in configured_models(self.settings)
        ]

    async def generate(self, model, prompt, *, test=False):
        validate_identifier(model)
        key = self.key("nvidia")
        started = time.monotonic()
        data = await self.post(
            f"{BASE}/chat/completions",
            {"Authorization": f"Bearer {key}"},
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 256 if test else 2048,
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
        except (KeyError, IndexError, TypeError, ValueError, AttributeError):
            raise ProviderError(
                "provider_response",
                "Provider returned no usable text (possibly token budget exhausted). No automatic retry was made.",
            ) from None
