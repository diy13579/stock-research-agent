"""
Feishu Bot API client.

Handles:
- Tenant access token (auto-refresh)
- Sending messages (text and interactive cards) to chats
- Replying to specific messages
"""

import os
import time
import httpx


_FEISHU_BASE = "https://open.feishu.cn/open-apis"

# Simple in-process token cache
_token_cache: dict = {"token": None, "expires_at": 0}


def _get_tenant_access_token() -> str:
    """Fetch (or return cached) tenant access token."""
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"] - 60:
        return _token_cache["token"]

    resp = httpx.post(
        f"{_FEISHU_BASE}/auth/v3/tenant_access_token/internal",
        json={
            "app_id": os.environ["FEISHU_APP_ID"],
            "app_secret": os.environ["FEISHU_APP_SECRET"],
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Failed to get tenant access token: {data}")

    _token_cache["token"] = data["tenant_access_token"]
    _token_cache["expires_at"] = now + data.get("expire", 7200)
    return _token_cache["token"]


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_get_tenant_access_token()}",
        "Content-Type": "application/json",
    }


def send_text(chat_id: str, text: str) -> dict:
    """Send a plain text message to a chat."""
    import json as _json
    resp = httpx.post(
        f"{_FEISHU_BASE}/im/v1/messages?receive_id_type=chat_id",
        headers=_headers(),
        json={
            "receive_id": chat_id,
            "msg_type": "text",
            "content": _json.dumps({"text": text}),
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def send_card(chat_id: str, card: dict) -> dict:
    """Send an interactive card message to a chat."""
    import json as _json
    resp = httpx.post(
        f"{_FEISHU_BASE}/im/v1/messages?receive_id_type=chat_id",
        headers=_headers(),
        json={
            "receive_id": chat_id,
            "msg_type": "interactive",
            "content": _json.dumps(card),
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def reply_text(message_id: str, text: str) -> dict:
    """Reply to a specific message with plain text."""
    import json as _json
    resp = httpx.post(
        f"{_FEISHU_BASE}/im/v1/messages/{message_id}/reply",
        headers=_headers(),
        json={
            "msg_type": "text",
            "content": _json.dumps({"text": text}),
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def reply_card(message_id: str, card: dict) -> dict:
    """Reply to a specific message with an interactive card."""
    import json as _json
    resp = httpx.post(
        f"{_FEISHU_BASE}/im/v1/messages/{message_id}/reply",
        headers=_headers(),
        json={
            "msg_type": "interactive",
            "content": _json.dumps(card),
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def get_chat_id_from_open_id(open_id: str) -> str:
    """
    Look up a user's single-chat ID from their open_id.
    Useful for sending DMs to the bot operator.
    """
    resp = httpx.get(
        f"{_FEISHU_BASE}/im/v1/chats",
        headers=_headers(),
        params={"user_id_type": "open_id"},
        timeout=10,
    )
    resp.raise_for_status()
    # Returns paginated list; for DMs, use create_p2p_chat instead
    return resp.json()
