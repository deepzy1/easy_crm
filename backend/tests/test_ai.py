import asyncio
import json

import httpx
import pytest
from app.ai.gemini import GeminiProvider
from app.ai.nvidia import NvidiaProvider
from app.ai.providers import ProviderError
from app.ai.catalogue import catalogue
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
        assert body["stream"] is False and body["max_tokens"] == 256
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
        (403, "provider_access"),
        (429, "provider_rate_limit"),
        (500, "provider_unavailable"),
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
        run(catalogue.validate(config(), "nvidia", "invented-ultra-id", lambda *_: None))


def test_settings_persist_and_generation_uses_current_preference(client, owner, monkeypatch):
    from app.api import ai

    headers, ws = owner
    url = f"/api/v1/workspaces/{ws}/ai"
    assert client.get(url + "/settings", headers=headers).json()["active"] is None
    assert client.post(url + "/generate", headers=headers, json={"prompt": "hello"}).status_code == 409
    observed = []

    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json={"models": [gemini_model("gemini-3.8-flash")]})
        observed.append((request.url.path, json.loads(request.content)))
        if "generativelanguage" in request.url.host:
            return httpx.Response(
                200, json={"candidates": [{"content": {"parts": [{"text": "Gemini response"}]}}]}
            )
        return httpx.Response(200, json={"choices": [{"message": {"content": "NVIDIA response"}}]})

    cfg = config(gemini_api_key="server-secret", nvidia_api_key="server-secret")
    monkeypatch.setattr(ai, "get_settings", lambda: cfg)
    monkeypatch.setattr(
        ai,
        "provider_for",
        lambda name, settings: (GeminiProvider if name == "gemini" else NvidiaProvider)(
            settings, httpx.MockTransport(handler)
        ),
    )
    for preference in (
        {"provider": "gemini", "model": "gemini-3.8-flash"},
        {"provider": "nvidia", "model": "nvidia/nemotron-3-ultra-550b-a55b"},
        {"provider": "gemini", "model": "gemini-3.8-flash"},
    ):
        assert client.put(url + "/settings", headers=headers, json=preference).status_code == 200
        assert client.get(url + "/settings", headers=headers).json()["active"] == preference
        result = client.post(url + "/generate", headers=headers, json={"prompt": "My test prompt"})
        assert result.status_code == 200
        assert result.json()["model"] == preference["model"]
        assert result.json()["provider"] == preference["provider"]
        assert "server-secret" not in result.text
    assert observed[0][0].endswith("gemini-3.8-flash:generateContent")
    assert observed[1][1]["model"] == "nvidia/nemotron-3-ultra-550b-a55b"
    assert observed[1][1]["messages"][0]["content"] == "My test prompt"
    assert (
        client.put(
            url + "/settings", headers=headers, json={"provider": "gemini", "model": "not-real"}
        ).status_code
        == 422
    )
    from app.core.database import SessionLocal
    from app.models.entities import ModelPreference

    with SessionLocal() as db:
        assert db.get(ModelPreference, ws).model == "gemini-3.8-flash"


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


def gemini_model(model, capabilities=None, **extra):
    return {
        "name": f"models/{model}",
        "displayName": model,
        "supportedGenerationMethods": capabilities
        if capabilities is not None
        else ["generateContent", "countTokens"],
        **extra,
    }


def test_gemini_discovery_pagination_filtering_exact_ids_and_no_generation():
    calls = []

    def handler(request):
        calls.append(request)
        assert request.method == "GET" and request.headers["x-goog-api-key"] == "discovery-secret"
        assert "key=" not in str(request.url)
        if "pageToken" not in request.url.params:
            return httpx.Response(
                200,
                json={
                    "models": [
                        gemini_model("gemini-3.8-flash"),
                        gemini_model("embedding-new", ["embedContent"]),
                        gemini_model("gemini-3.8-flash-tts"),
                        gemini_model("gemini-3.1-flash-image"),
                    ],
                    "nextPageToken": "second/page+token",
                },
            )
        assert request.url.params["pageToken"] == "second/page+token"
        return httpx.Response(
            200,
            json={
                "models": [
                    gemini_model("gemini-3.6-flash"),
                    gemini_model("gemini-3.8-flash"),
                    gemini_model("audio-output", outputModalities=["AUDIO"]),
                ]
            },
        )

    rows = run(
        GeminiProvider(config(gemini_api_key="discovery-secret"), httpx.MockTransport(handler)).list_models()
    )
    assert [row["id"] for row in rows] == ["gemini-3.8-flash", "gemini-3.6-flash"]
    assert rows[0]["resource_name"] == "models/gemini-3.8-flash"
    assert rows[0]["capabilities"] == ["generateContent", "countTokens"]
    assert len(calls) == 2


@pytest.mark.parametrize(
    "status,payload,code",
    [
        (
            400,
            {"status": "INVALID_ARGUMENT", "message": "API key not valid. Please pass a valid API key."},
            "provider_auth",
        ),
        (403, {"message": "API key expired"}, "provider_auth"),
        (403, {"message": "permission denied"}, "provider_access"),
        (
            400,
            {
                "status": "FAILED_PRECONDITION",
                "message": "Free tier is not available in your country. Enable billing.",
            },
            "provider_billing",
        ),
        (402, {}, "provider_billing"),
        (429, {"status": "RESOURCE_EXHAUSTED", "message": "Quota exceeded"}, "provider_rate_limit"),
        (
            429,
            {"message": "You exceeded your current quota, please check your plan and billing details."},
            "provider_rate_limit",
        ),
        (404, {"status": "NOT_FOUND", "message": "Model not found"}, "provider_model_unavailable"),
        (400, {"message": "model is not supported for generateContent"}, "provider_model_unavailable"),
        (400, {"message": "Invalid JSON payload received"}, "provider_request"),
        (503, {}, "provider_unavailable"),
    ],
)
def test_detailed_discovery_and_generation_errors(status, payload, code, caplog):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"error": {**payload, "sensitive": "sentinel-secret payload"}})

    adapter = GeminiProvider(config(gemini_api_key="sentinel-secret"), httpx.MockTransport(handler))
    for operation in (adapter.list_models(), adapter.check_connection("gemini-3.8-flash")):
        with pytest.raises(ProviderError) as result:
            run(operation)
        assert result.value.code == code
        assert result.value.upstream_status == status
        assert "sentinel-secret" not in str(result.value)
    assert "sentinel-secret" not in caplog.text
    assert "payload" not in caplog.text
    assert len(calls) == 2


@pytest.mark.parametrize(
    "payload", [{"models": "bad"}, {"models": [None]}, {"models": [], "nextPageToken": "loop"}]
)
def test_malformed_or_looping_discovery_never_returns_partial_success(payload):
    adapter = GeminiProvider(
        config(gemini_api_key="test"), httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    )
    with pytest.raises(ProviderError) as result:
        run(adapter.list_models())
    assert result.value.code == "provider_response"


def test_cache_refresh_failure_expiry_and_key_rotation():
    from app.ai.catalogue import ModelCatalogue

    cache = ModelCatalogue()
    calls = []
    fail = False

    def handler(request):
        calls.append(request)
        if fail:
            return httpx.Response(429, json={"error": {"message": "quota"}})
        return httpx.Response(200, json={"models": [gemini_model("gemini-3.8-flash")]})

    def factory(name, cfg):
        return GeminiProvider(cfg, httpx.MockTransport(handler))

    cfg = config(gemini_api_key="first")
    assert run(cache.get(cfg, "gemini", factory))["cached"] is False
    assert run(cache.get(cfg, "gemini", factory))["cached"] is True
    assert len(calls) == 1
    assert run(cache.get(cfg, "gemini", factory, refresh=True))["cached"] is False
    fail = True
    stale = run(cache.get(cfg, "gemini", factory, refresh=True))
    assert stale["stale"] and stale["error"]["code"] == "provider_rate_limit"
    assert cache.decorate(stale, "ws", cfg)["models"][0]["availability"] == "unknown"
    rotated = run(cache.get(config(gemini_api_key="second"), "gemini", factory))
    assert rotated["models"] == [] and not rotated["stale"]
    fail = False
    expired = config(gemini_api_key="first", ai_models_cache_seconds=0)
    run(cache.get(expired, "gemini", factory))
    assert run(cache.get(expired, "gemini", factory))["cached"] is False


def test_nvidia_discovery_respects_chat_allowlist():
    cfg = config(
        nvidia_api_key="private", nvidia_models=["nvidia/nemotron-3-ultra-550b-a55b", "nvidia/retired-chat"]
    )

    def handler(request):
        assert request.method == "GET" and request.url.path == "/v1/models"
        assert request.headers["authorization"] == "Bearer private"
        return httpx.Response(200, json={"data": [{"id": cfg.nvidia_models[0]}, {"id": "embedding-only"}]})

    rows = run(NvidiaProvider(cfg, httpx.MockTransport(handler)).list_models())
    assert [row["id"] for row in rows] == cfg.nvidia_models
    assert [row["availability"] for row in rows] == ["available", "unavailable"]


def test_models_endpoint_refresh_test_status_and_workspace_isolation(client, owner, monkeypatch):
    from app.api import ai

    headers, ws = owner
    cfg = config(gemini_api_key="private")
    posts = []
    limited = False

    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json={"models": [gemini_model("gemini-3.8-flash")]})
        posts.append(request)
        assert json.loads(request.content)["generationConfig"]["maxOutputTokens"] == 256
        if limited:
            return httpx.Response(429, json={"error": {"message": "quota"}})
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "Connected"}]}}]})

    monkeypatch.setattr(ai, "get_settings", lambda: cfg)
    monkeypatch.setattr(
        ai, "provider_for", lambda name, settings: GeminiProvider(settings, httpx.MockTransport(handler))
    )
    url = f"/api/v1/workspaces/{ws}/ai"
    result = client.get(url + "/models?provider=gemini", headers=headers)
    assert result.status_code == 200
    assert result.json()["models"][0]["availability"] == "available"
    assert result.json()["models"][0]["free_tier"] == "unverified"
    assert not posts and "private" not in result.text
    assert client.get(url + "/models?provider=gemini&refresh=true", headers=headers).json()["cached"] is False
    preference = {"provider": "gemini", "model": "gemini-3.8-flash"}
    assert client.post(url + "/test", headers=headers, json=preference).status_code == 200
    assert (
        client.get(url + "/models?provider=gemini", headers=headers).json()["models"][0]["availability"]
        == "verified_working"
    )
    limited = True
    assert client.post(url + "/test", headers=headers, json=preference).status_code == 429
    assert (
        client.get(url + "/models?provider=gemini", headers=headers).json()["models"][0]["availability"]
        == "rate_limited"
    )
    other = client.post("/api/v1/workspaces", headers=headers, json={"name": "Other workspace"}).json()["id"]
    other_models = client.get(f"/api/v1/workspaces/{other}/ai/models?provider=gemini", headers=headers)
    assert other_models.json()["models"][0]["availability"] == "available"
    from uuid import uuid4

    assert (
        client.get(f"/api/v1/workspaces/{uuid4()}/ai/models?provider=gemini", headers=headers).status_code
        == 404
    )
    assert client.get(url + "/models?provider=unknown", headers=headers).status_code == 422


def test_saved_generation_does_not_depend_on_discovery(client, owner, monkeypatch):
    from app.api import ai

    headers, ws = owner
    url = f"/api/v1/workspaces/{ws}/ai"
    pref = {"provider": "nvidia", "model": "nvidia/nemotron-3-ultra-550b-a55b"}
    assert client.put(url + "/settings", headers=headers, json=pref).status_code == 200

    def handler(request):
        assert request.method == "POST"
        return httpx.Response(404, json={"error": {"message": "Model not found private-key"}})

    monkeypatch.setattr(
        ai,
        "provider_for",
        lambda name, settings: NvidiaProvider(
            config(nvidia_api_key="private-key"), httpx.MockTransport(handler)
        ),
    )
    result = client.post(url + "/generate", headers=headers, json={"prompt": "hello"})
    assert result.status_code == 502
    assert result.json()["error"]["code"] == "provider_model_unavailable"
    assert result.json()["error"]["details"]["upstream_status"] == 404
    assert "private-key" not in result.text


@pytest.mark.parametrize("model", ["../secret", "models/../secret", "nvidia//model", "model?key=abc"])
def test_unsafe_model_ids_never_make_provider_requests(model):
    def handler(request):
        pytest.fail("Unsafe identifier reached provider")

    with pytest.raises(ProviderError):
        run(
            GeminiProvider(config(gemini_api_key="secret"), httpx.MockTransport(handler)).generate(
                model, "hello"
            )
        )


@pytest.mark.parametrize("failure", [httpx.ConnectError, httpx.ReadTimeout])
def test_discovery_network_failures_are_sanitized(failure):
    def handler(request):
        raise failure("server-secret in sensitive network failure", request=request)

    adapter = GeminiProvider(config(gemini_api_key="server-secret"), httpx.MockTransport(handler))
    with pytest.raises(ProviderError) as result:
        run(adapter.list_models())
    assert result.value.code == ("provider_timeout" if failure is httpx.ReadTimeout else "provider_network")
    assert "server-secret" not in str(result.value)


def test_expired_observation_does_not_claim_verified_access():
    from app.ai.catalogue import ModelCatalogue

    cache = ModelCatalogue()
    cfg = config(gemini_api_key="one")
    result = {
        "provider": "gemini",
        "models": [{"id": "gemini-3.8-flash", "availability": "available"}],
        "stale": False,
    }
    cache.record("workspace", cfg, "gemini", "gemini-3.8-flash")
    assert cache.decorate(result, "workspace", cfg)["models"][0]["availability"] == "verified_working"
    key = next(iter(cache.observations))
    _, info = cache.observations[key]
    cache.observations[key] = (0, info)
    assert cache.decorate(result, "workspace", cfg)["models"][0]["availability"] == "available"
    assert cache.decorate(result, "workspace", cfg)["models"][0]["free_tier"] == "unverified"


@pytest.mark.parametrize("capabilities", [None, {"generateContent": True}, [None]])
def test_invalid_capability_metadata_is_safe(capabilities):
    adapter = GeminiProvider(
        config(gemini_api_key="test"),
        httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "models": [
                        {"name": "models/gemini-3.8-flash", "supportedGenerationMethods": capabilities}
                    ]
                },
            )
        ),
    )
    with pytest.raises(ProviderError) as result:
        run(adapter.list_models())
    assert result.value.code == "provider_response"
