"""Reproducible guardrail evaluation, not a live model accuracy benchmark.

Fixtures provide model outputs. Actual schema/evidence checks, scoped retrieval,
scores, escalation, persistence and replay behavior execute against PostgreSQL.
"""

import json
from pathlib import Path

import pytest

from app.ai.providers import Generation
from app.api import ai
from test_qualification import setup, message

CASES = json.loads((Path(__file__).parent / "fixtures/qualification_eval.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_evaluation_fixture(client, owner, monkeypatch, case):
    _, lead = setup(client, owner)
    headers, ws = owner
    source = client.post(
        f"/api/v1/workspaces/{ws}/qualification/knowledge",
        headers=headers,
        json={"title": "Fictional delivery policy", "text": "Delivery takes 5 days.", "approved": True},
    ).json()
    calls = []

    class Fixture:
        async def generate(self, model, prompt):
            calls.append(prompt)
            output = case["output"]
            raw = (output if isinstance(output, str) else json.dumps(output)).replace("$SOURCE", source["id"])
            return Generation("nvidia", model, raw, 0, 0, 0)

    monkeypatch.setattr(ai, "provider_for", lambda *_: Fixture())
    result = message(client, owner, lead, case["message"], "evaluation-receipt")
    assert result["state"] == case["expected_state"]
    assert result["assessment"]["score"] == case["expected_score"]
    assert {k: v["value"] for k, v in result["fields"].items()} == case["expected_fields"]
    assert len(calls) == case.get("expected_calls", 1)
    if "expected_citation" in case:
        assert result["citations"][0]["quote"] == case["expected_citation"]
        assert case["expected_citation"] in result["reply"]
    else:
        assert not result["citations"]
    replay = message(client, owner, lead, case["message"], "evaluation-receipt")
    assert replay["duplicate"] and len(calls) == case.get("expected_calls", 1)
