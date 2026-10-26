import asyncio
import json

import httpx
import pytest
from app.ai.providers import GeminiProvider, NvidiaProvider, ProviderError, validate_model
from app.core.config import Settings, get_settings


def run(awaitable):
    return asyncio.run(awaitable)


def config(**kwargs):
    return Settings(_env_file=None, **kwargs)


@pytest.mark.parametrize("provider", [GeminiProvider, NvidiaProvider])
def test_missing_keys(provider):
    with pytest.raises(ProviderError) as error:
        run(provider(config()).generate("anything", "hello"))
    assert error.value.code == "missing_credentials"


def test_gemini_payload_response_usage_and_key_header():
    def handler(request):
        assert request.headers["x-goog-api-key"] == "test-server-key"
        assert "key=" not in str(request.url)
        assert request.url.path.endswith("/models/gemini-2.5-flash:generateContent")
        assert json.loads(request.content)["contents"][0]["parts"][0]["text"] == "hello"
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": "Hello"}]}}],
                "usageMetadata": {"promptTokenCount": 2, "candidatesTokenCount": 1},
            },
        )

    result = run(
        GeminiProvider(config(gemini_api_key="test-server-key"), httpx.MockTransport(handler)).generate(
            "gemini-2.5-flash", "hello"
        )
    )
    assert result.text == "Hello" and result.input_tokens == 2 and result.output_tokens == 1
    assert result.provider == "gemini"


def test_nvidia_openai_payload_and_normalization():
    def handler(request):
        assert request.headers["authorization"] == "Bearer test-nvidia-key"
        assert str(request.url) == "https://integrate.api.nvidia.com/v1/chat/completions"
        body = json.loads(request.content)
        assert body["model"] == "nvidia/nemotron-3-ultra-550b-a55b"
        assert body["stream"] is False and body["max_tokens"] == 2048
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Connected"}}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 1},
            },
        )

    result = run(
        NvidiaProvider(
            config(nvidia_api_key="test-nvidia-key"), httpx.MockTransport(handler)
        ).check_connection("nvidia/nemotron-3-ultra-550b-a55b")
    )
    assert result.text == "Connected" and result.input_tokens == 4
    assert result.provider == "nvidia"


@pytest.mark.parametrize(
    "adapter,key", [(GeminiProvider, "gemini_api_key"), (NvidiaProvider, "nvidia_api_key")]
)
@pytest.mark.parametrize(
    "status,code",
    [
        (401, "provider_auth"),
        (403, "provider_auth"),
        (429, "provider_rate_limit"),
        (500, "provider_rejected"),
    ],
)
def test_sanitized_errors_no_retry(adapter, key, status, code):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"error": "secret-test-key echoed by upstream"})

    with pytest.raises(ProviderError) as error:
        run(
            adapter(config(**{key: "secret-test-key"}), httpx.MockTransport(handler)).generate(
                "model", "hello"
            )
        )
    assert error.value.code == code
    assert "secret-test-key" not in error.value.message
    assert len(calls) == 1


@pytest.mark.parametrize(
    "adapter,key", [(GeminiProvider, "gemini_api_key"), (NvidiaProvider, "nvidia_api_key")]
)
def test_timeout_no_retry(adapter, key):
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("contains secrets", request=request)

    with pytest.raises(ProviderError) as error:
        run(adapter(config(**{key: "test-key"}), httpx.MockTransport(handler)).generate("model", "hi"))
    assert error.value.code == "provider_timeout" and error.value.status == 504
    assert len(calls) == 1


@pytest.mark.parametrize("payload", [{}, {"choices": []}, {"choices": [{"message": {"content": None}}]}])
def test_malformed_or_empty_response(payload):
    with pytest.raises(ProviderError) as error:
        run(
            NvidiaProvider(
                config(nvidia_api_key="test"),
                httpx.MockTransport(lambda _: httpx.Response(200, json=payload)),
            ).generate("model", "hi")
        )
    assert error.value.code == "provider_response"


def test_invalid_model():
    with pytest.raises(ProviderError):
        validate_model(config(), "nvidia", "invented-ultra-id")


def test_settings_persist_and_generation_uses_current_preference(client, owner, monkeypatch):
    from app.api import ai

    headers, ws = owner
    url = f"/api/v1/workspaces/{ws}/ai"
    assert client.get(url + "/settings", headers=headers).json()["active"] is None
    assert client.post(url + "/generate", headers=headers, json={"prompt": "hello"}).status_code == 409
    for preference in (
        {"provider": "gemini", "model": "gemini-2.5-flash"},
        {"provider": "nvidia", "model": "nvidia/nemotron-3-ultra-550b-a55b"},
    ):
        assert client.put(url + "/settings", headers=headers, json=preference).status_code == 200
        assert client.get(url + "/settings", headers=headers).json()["active"] == preference
    assert (
        client.put(
            url + "/settings", headers=headers, json={"provider": "nvidia", "model": "not-real"}
        ).status_code
        == 422
    )
    assert (
        client.post(url + "/generate", headers=headers, json={"prompt": "hello"}).json()["error"]["code"]
        == "missing_credentials"
    )
    observed = []

    def handler(request):
        observed.append(json.loads(request.content))
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "Actual mocked adapter response"}}]}
        )

    monkeypatch.setattr(
        ai,
        "provider_for",
        lambda name, settings: NvidiaProvider(
            config(nvidia_api_key="server-secret"), httpx.MockTransport(handler)
        ),
    )
    result = client.post(url + "/generate", headers=headers, json={"prompt": "My test prompt"})
    assert result.status_code == 200
    assert result.json()["provider"] == "nvidia"
    assert observed[0]["model"] == "nvidia/nemotron-3-ultra-550b-a55b"
    assert observed[0]["messages"][0]["content"] == "My test prompt"
    assert "server-secret" not in result.text


def test_credentials_never_returned_and_missing_key_connection(client, owner, monkeypatch, caplog):
    headers, ws = owner
    url = f"/api/v1/workspaces/{ws}/ai"
    config = get_settings()
    from pydantic import SecretStr

    monkeypatch.setattr(config, "gemini_api_key", SecretStr("server-only-sentinel"))
    result = client.get(url + "/settings", headers=headers)
    assert result.json()["providers"][0]["configured"] is True
    assert "server-only-sentinel" not in result.text
    assert "server-only-sentinel" not in caplog.text
    test = client.post(
        url + "/test",
        headers=headers,
        json={"provider": "nvidia", "model": "nvidia/nemotron-3-ultra-550b-a55b"},
    )
    assert test.status_code == 503 and test.json()["error"]["code"] == "missing_credentials"
