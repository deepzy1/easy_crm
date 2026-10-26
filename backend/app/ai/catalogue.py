"""Bounded process-local discovery and observation cache, never containing secrets.

Discovery is keyed by a credential fingerprint; generation observations are additionally
workspace scoped. Preferences remain durable in PostgreSQL, observations expire.
"""

from collections import OrderedDict
from datetime import datetime, timezone
import hashlib
import time
from threading import RLock

from app.ai.nvidia import configured_models
from app.ai.providers import ProviderError, validate_identifier

STATUS = {
    "provider_auth": "access_restricted",
    "provider_access": "access_restricted",
    "provider_billing": "access_restricted",
    "provider_rate_limit": "rate_limited",
    "provider_model_unavailable": "unavailable",
    "invalid_model": "unavailable",
}


def stamp():
    return datetime.now(timezone.utc).isoformat()


class ModelCatalogue:
    def __init__(self):
        self.entries = OrderedDict()
        self.observations = OrderedDict()
        self.lock = RLock()

    def clear(self):
        with self.lock:
            self.entries.clear()
            self.observations.clear()

    def key(self, settings, provider):
        if provider not in ("gemini", "nvidia"):
            raise ProviderError("invalid_provider", "Unknown AI provider.", 422)
        fingerprint = hashlib.sha256(
            getattr(settings, f"{provider}_api_key").get_secret_value().encode()
        ).hexdigest()
        return (
            provider,
            fingerprint,
            tuple(settings.nvidia_models) if provider == "nvidia" else (),
            settings.ai_models_cache_seconds,
        )

    def put(self, target, key, value, limit):
        with self.lock:
            target[key] = value
            target.move_to_end(key)
            while len(target) > limit:
                target.popitem(last=False)

    async def get(self, settings, provider, factory, refresh=False):
        key = self.key(settings, provider)
        with self.lock:
            previous = self.entries.get(key)
        if not refresh and previous and time.monotonic() < previous[0]:
            return {**previous[1], "cached": True, "stale": False, "error": None}
        try:
            rows = await factory(provider, settings).list_models()
            result = {"provider": provider, "models": rows, "fetched_at": stamp()}
            self.put(self.entries, key, (time.monotonic() + settings.ai_models_cache_seconds, result), 16)
            return {**result, "cached": False, "stale": False, "error": None}
        except ProviderError as exc:
            return {
                "provider": provider,
                "models": previous[1]["models"]
                if previous
                else configured_models(settings)
                if provider == "nvidia"
                else [],
                "fetched_at": previous[1]["fetched_at"] if previous else None,
                "cached": bool(previous),
                "stale": bool(previous),
                "error": exc.public(),
            }

    async def validate(self, settings, provider, model, factory):
        validate_identifier(model)
        self.key(settings, provider)
        if provider == "nvidia":
            valid = model in settings.nvidia_models
        else:
            result = await self.get(settings, provider, factory)
            if result["error"]:
                info = result["error"]
                raise ProviderError(info["code"], info["message"], 503, info["upstream_status"])
            valid = any(row["id"] == model for row in result["models"])
        if not valid:
            raise ProviderError(
                "invalid_model",
                "This model is absent from the text model catalogue. Refresh Models and choose an available model.",
                422,
            )

    def record(self, ws, settings, provider, model, error=None):
        key = (str(ws), self.key(settings, provider), model)
        self.put(
            self.observations,
            key,
            (
                time.monotonic() + 900,
                {
                    "availability": STATUS.get(error.code, "unknown") if error else "verified_working",
                    "checked_at": stamp(),
                    "error": error.public() if error else None,
                },
            ),
            2048,
        )

    def decorate(self, result, ws, settings):
        rows = []
        key = self.key(settings, result["provider"])
        for row in result["models"]:
            with self.lock:
                observed = self.observations.get((str(ws), key, row["id"]))
            info = observed[1] if observed and time.monotonic() < observed[0] else {}
            availability = "unknown" if result["stale"] else row["availability"]
            rows.append(
                {**row, "availability": availability, "checked_at": None, **info, "free_tier": "unverified"}
            )
        return {**result, "models": rows}


catalogue = ModelCatalogue()
