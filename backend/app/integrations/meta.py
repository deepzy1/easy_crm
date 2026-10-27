"""Official Graph transport. No redirects, arbitrary hosts, or token-bearing URLs."""

import hashlib
import hmac

import httpx
from fastapi import HTTPException

from app.core.config import get_settings


class MetaError(Exception):
    def __init__(self, code, retryable=False, ambiguous=False):
        self.code, self.retryable, self.ambiguous = code, retryable, ambiguous


def connection(integration):
    config = get_settings().meta_connections.get(integration.credential_alias)
    if (
        not config
        or config.workspace_id != integration.workspace_id
        or config.kind != integration.kind
        or config.external_account_id != integration.external_account_id
        or not all(
            x.get_secret_value() for x in (config.app_secret, config.verify_token, config.access_token)
        )
    ):
        raise HTTPException(409, "Configure this workspace's Meta credentials on the backend")
    return config


async def graph(config, method, path, *, body=None, params=None):
    host = "graph.instagram.com" if config.kind == "instagram" else "graph.facebook.com"
    url = f"https://{host}/{get_settings().meta_graph_version}/{path}"
    token = config.access_token.get_secret_value()
    proof = hmac.new(
        config.app_secret.get_secret_value().encode(), token.encode(), hashlib.sha256
    ).hexdigest()
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
            response = await client.request(
                method,
                url,
                headers={"Authorization": f"Bearer {token}"},
                json=body,
                params={"appsecret_proof": proof, **(params or {})},
            )
    except (httpx.ConnectError, httpx.ConnectTimeout):
        raise MetaError("meta_connection_failed", retryable=True) from None
    except httpx.RequestError:
        raise MetaError(
            "meta_delivery_unknown", ambiguous=method == "POST", retryable=method == "GET"
        ) from None
    if response.status_code == 429:
        raise MetaError("meta_rate_limited", retryable=True)
    if response.status_code >= 500:
        # Meta may have accepted a POST before returning an upstream failure.
        raise MetaError("meta_upstream_unavailable", retryable=method == "GET", ambiguous=method == "POST")
    if response.status_code in (401, 403):
        raise MetaError("meta_credentials_or_permissions")
    if not response.is_success:
        raise MetaError("meta_request_rejected")
    try:
        result = response.json()
        if not isinstance(result, dict) or "error" in result:
            raise ValueError()
        return result
    except ValueError:
        raise MetaError("meta_invalid_response", ambiguous=method == "POST") from None


async def send_text(integration, recipient, text, callback_id):
    config = connection(integration)
    if integration.kind != "whatsapp":
        raise MetaError("channel_send_unavailable")
    result = await graph(
        config,
        "POST",
        f"{config.external_account_id}/messages",
        body={
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "text",
            "text": {"preview_url": False, "body": text},
            "biz_opaque_callback_data": callback_id,
        },
    )
    try:
        identity = result["messages"][0]["id"]
        if not isinstance(identity, str) or not 1 <= len(identity) <= 200:
            raise ValueError()
        return identity
    except (KeyError, IndexError, TypeError, ValueError):
        raise MetaError("meta_delivery_unknown", ambiguous=True) from None


async def fetch_lead(integration, lead_id):
    result = await graph(
        connection(integration),
        "GET",
        lead_id,
        params={"fields": "id,created_time,field_data,ad_id,form_id,campaign_id"},
    )
    if result.get("id") != lead_id or not isinstance(result.get("field_data"), list):
        raise MetaError("meta_invalid_lead_response")
    return result
