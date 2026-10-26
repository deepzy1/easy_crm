import re
import time

from app.ai.providers import Generation, ProviderError, TextProvider, validate_identifier

BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider(TextProvider):
    name = "gemini"

    async def list_models(self):
        headers = {"x-goog-api-key": self.key("gemini")}
        models = {}
        token = None
        seen = set()
        # Bound pagination so a broken provider cannot loop or cache a partial catalogue.
        for _ in range(100):
            params = {"pageSize": 1000}
            if token:
                params["pageToken"] = token
            data = await self.request("GET", f"{BASE}/models", headers, params=params)
            rows = data.get("models", [])
            if not isinstance(rows, list):
                raise ProviderError("provider_response", "Provider returned an invalid model catalogue.")
            for row in rows:
                if not isinstance(row, dict):
                    raise ProviderError("provider_response", "Provider returned an invalid model catalogue.")
                resource = row.get("name", "")
                capabilities = row.get("supportedGenerationMethods", [])
                if not isinstance(resource, str) or not resource.startswith("models/"):
                    continue
                if not isinstance(capabilities, list) or any(
                    not isinstance(value, str) for value in capabilities
                ):
                    raise ProviderError("provider_response", "Provider returned invalid model capabilities.")
                model = resource.removeprefix("models/")
                validate_identifier(model)
                # generateContent is also used for audio/image-only models. Do not offer
                # those to a text-only adapter when modality metadata is absent.
                output = row.get("outputModalities")
                if output is not None and not isinstance(output, list):
                    raise ProviderError("provider_response", "Provider returned invalid output modalities.")
                if (
                    "generateContent" not in capabilities
                    or (output is not None and "TEXT" not in output)
                    or re.search(r"(?:^|-)(?:tts|image|audio|transcribe)(?:-|$)", model)
                ):
                    continue
                family = re.match(r"gemini-(\d+(?:\.\d+)?)", model)
                models[model] = {
                    "id": model,
                    "resource_name": resource,
                    "name": row.get("displayName") if isinstance(row.get("displayName"), str) else model,
                    "family": f"Gemini {family[1]}" if family else "Other text models",
                    "capabilities": capabilities,
                    "availability": "available",
                    "source": "provider",
                }
            token = data.get("nextPageToken")
            if not token:
                return list(models.values())
            if not isinstance(token, str) or token in seen:
                break
            seen.add(token)
        raise ProviderError(
            "provider_response", "Provider model pagination did not complete. Refresh manually later."
        )

    async def generate(self, model, prompt, *, test=False):
        validate_identifier(model)
        key = self.key("gemini")
        started = time.monotonic()
        data = await self.post(
            f"{BASE}/models/{model}:generateContent",
            {"x-goog-api-key": key},
            {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": 256 if test else 2048},
            },
        )
        try:
            text = "\n".join(
                p["text"]
                for p in data["candidates"][0]["content"]["parts"]
                if "text" in p and not p.get("thought")
            )
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
        except (KeyError, IndexError, TypeError, ValueError, AttributeError):
            raise ProviderError(
                "provider_response",
                "Provider returned no usable text (possibly blocked or token budget exhausted). No automatic retry was made.",
            ) from None
