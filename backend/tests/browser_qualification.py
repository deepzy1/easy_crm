"""Explicit browser-test launcher, never imported by the production application.

Only qualification generation uses deterministic fictional fixtures. All HTTP,
auth, SQL transactions, retrieval, evidence checking and scoring are real services.
Other AI calls retain real missing-key behavior. No fixture sends provider requests.
"""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api import ai  # noqa: E402
from app.ai.providers import Generation  # noqa: E402
from app.main import app  # noqa: E402, F401

original_provider_for = ai.provider_for


class FixtureProvider:
    def __init__(self, adapter):
        self.adapter = adapter

    def __getattr__(self, name):
        return getattr(self.adapter, name)

    async def generate(self, model, prompt, **kwargs):
        if not prompt.startswith("You extract lead qualification facts."):
            return await self.adapter.generate(model, prompt, **kwargs)
        context = json.loads(prompt.split("Context:\n", 1)[1])
        text = context["current_message"]
        # These values belong only to the explicitly labeled fictional browser case.
        values = {"product": "software", "budget": 5000, "timeline": "next month", "buyer_role": "owner"}
        fields = [
            {"key": k, "value": v, "evidence": str(v), "confidence": 0.95}
            for k, v in values.items()
            if str(v) in text and k in {r["key"] for r in context["rules"]["criteria"]}
        ]
        quotes = [
            {"source_id": s["source_id"], "quote": "Delivery takes 5 days."}
            for s in context["reviewed_sources"]
            if "delivery" in text.lower() and "Delivery takes 5 days." in s["text"]
        ]
        return Generation(
            self.adapter.name, model, json.dumps({"fields": fields, "quotes": quotes}), 100, 30, 2
        )


ai.provider_for = lambda name, config: FixtureProvider(original_provider_for(name, config))
