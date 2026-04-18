import os
from datetime import datetime, timezone

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from supabase import create_client


def get_supabase():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        try:
            url = st.secrets["SUPABASE_URL"]
            key = st.secrets["SUPABASE_KEY"]
        except Exception:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY not found in .env or st.secrets")
    return create_client(url, key)


def create_test_session(tester_name: str, platform: str) -> str:
    supabase = get_supabase()
    response = (
        supabase.table("test_sessions")
        .insert({
            "tester_name": tester_name,
            "platform": platform,
            "control_mode": "bot",
        })
        .execute()
    )
    return response.data[0]["id"]


def get_test_session(session_id: str):
    supabase = get_supabase()
    response = (
        supabase.table("test_sessions")
        .select("*")
        .eq("id", session_id)
        .limit(1)
        .execute()
    )
    if response.data:
        return response.data[0]
    return None


def get_session_control_state(session_id: str) -> dict:
    row = get_test_session(session_id)
    if not row:
        return {
            "control_mode": "bot",
            "handoff_reason": "",
            "handoff_since": None,
        }

    return {
        "control_mode": row.get("control_mode", "bot") or "bot",
        "handoff_reason": row.get("handoff_reason", "") or "",
        "handoff_since": row.get("handoff_since"),
    }


def set_session_control_mode(session_id: str, control_mode: str, handoff_reason: str | None = None):
    supabase = get_supabase()

    if control_mode not in ("bot", "human"):
        raise ValueError("control_mode must be 'bot' or 'human'")

    payload = {
        "control_mode": control_mode,
    }

    if control_mode == "human":
        payload["handoff_reason"] = handoff_reason or ""
        payload["handoff_since"] = datetime.now(timezone.utc).isoformat()
    else:
        payload["handoff_reason"] = None
        payload["handoff_since"] = None

    response = (
        supabase.table("test_sessions")
        .update(payload)
        .eq("id", session_id)
        .execute()
    )
    return response.data


def save_message_turn(
    session_id: str,
    turn_number: int,
    user_message: str,
    bot_messages: list,
    idioma: str,
    categorias_detectadas: list,
    categorias_respondibles: list
):
    supabase = get_supabase()
    (
        supabase.table("messages")
        .insert({
            "session_id": session_id,
            "turn_number": turn_number,
            "user_message": user_message,
            "bot_messages": bot_messages,
            "idioma": idioma,
            "categorias_detectadas": categorias_detectadas,
            "categorias_respondibles": categorias_respondibles
        })
        .execute()
    )


def save_feedback(session_id: str, turn_number: int, rating: str, comment: str):
    supabase = get_supabase()
    (
        supabase.table("feedback")
        .insert({
            "session_id": session_id,
            "turn_number": turn_number,
            "rating": rating,
            "comment": comment
        })
        .execute()
    )


def create_chat_message(
    session_id: str,
    turn_number: int,
    role: str,
    content: str,
    status: str = "done",
    source: str = "streamlit",
    reply_to_message_id: int | None = None,
    idioma: str | None = None,
    categorias_detectadas: list | None = None,
    categorias_respondibles: list | None = None,
    error_text: str | None = None,
):
    supabase = get_supabase()

    payload = {
        "session_id": session_id,
        "turn_number": turn_number,
        "role": role,
        "content": content,
        "status": status,
        "source": source,
        "reply_to_message_id": reply_to_message_id,
        "idioma": idioma,
        "categorias_detectadas": categorias_detectadas or [],
        "categorias_respondibles": categorias_respondibles or [],
        "error_text": error_text,
    }

    response = supabase.table("chat_messages").insert(payload).execute()
    return response.data[0]


def get_chat_messages(session_id: str):
    supabase = get_supabase()
    response = (
        supabase.table("chat_messages")
        .select("*")
        .eq("session_id", session_id)
        .order("created_at", desc=False)
        .execute()
    )
    return response.data or []


def get_pending_ai_messages(limit: int = 20):
    supabase = get_supabase()
    response = (
        supabase.table("chat_messages")
        .select("*")
        .eq("role", "user")
        .eq("status", "pending_ai")
        .order("created_at")
        .limit(limit)
        .execute()
    )
    return response.data or []


def update_chat_message_status(
    message_id: int,
    status: str,
    error_text: str | None = None,
):
    supabase = get_supabase()

    payload = {
        "status": status,
        "error_text": error_text
    }

    response = (
        supabase.table("chat_messages")
        .update(payload)
        .eq("id", message_id)
        .execute()
    )
    return response.data


def mark_chat_message_processed(message_id: int, status: str = "done", error_text: str | None = None):
    supabase = get_supabase()
    response = (
        supabase.table("chat_messages")
        .update({
            "status": status,
            "error_text": error_text,
            "processed_at": "now()"
        })
        .eq("id", message_id)
        .execute()
    )
    return response.data


def create_opener_request(session_id: str, opener_type: str = "soft"):
    supabase = get_supabase()
    response = (
        supabase.table("opener_suggestions")
        .insert({
            "session_id": session_id,
            "opener_type": opener_type,
            "status": "pending"
        })
        .execute()
    )
    return response.data[0]


def get_latest_opener_request(session_id: str, opener_type: str = "soft"):
    supabase = get_supabase()
    response = (
        supabase.table("opener_suggestions")
        .select("*")
        .eq("session_id", session_id)
        .eq("opener_type", opener_type)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if response.data:
        return response.data[0]
    return None


def get_pending_opener_requests(limit: int = 5):
    supabase = get_supabase()
    response = (
        supabase.table("opener_suggestions")
        .select("*")
        .eq("status", "pending")
        .order("created_at")
        .limit(limit)
        .execute()
    )
    return response.data


def update_opener_request(
    opener_id: int,
    status: str,
    suggestion_text: str | None = None,
    error_text: str | None = None,
):
    supabase = get_supabase()

    payload = {
        "status": status,
        "suggestion_text": suggestion_text,
        "error_text": error_text,
    }

    response = (
        supabase.table("opener_suggestions")
        .update(payload)
        .eq("id", opener_id)
        .execute()
    )
    return response.data


# ============================================================
# bot_config helpers
# ============================================================

def get_bot_config(category: str | None = None) -> list:
    """Returns all config rows, optionally filtered by category."""
    supabase = get_supabase()
    query = supabase.table("bot_config").select("*").eq("active", True)
    if category:
        query = query.eq("category", category)
    response = query.order("category").order("key").execute()
    return response.data or []


def get_bot_config_dict(category: str | None = None) -> dict:
    """Returns config as {key: value} dict for easy lookup."""
    rows = get_bot_config(category)
    return {row["key"]: row["value"] for row in rows}


def upsert_bot_config(category: str, key: str, value: str, description: str = "") -> dict:
    """Create or update a config entry."""
    supabase = get_supabase()
    response = (
        supabase.table("bot_config")
        .upsert({
            "category": category,
            "key": key,
            "value": value,
            "description": description,
            "active": True,
        }, on_conflict="key")
        .execute()
    )
    return response.data[0] if response.data else {}


def delete_bot_config(key: str) -> bool:
    """Soft delete by setting active=False."""
    supabase = get_supabase()
    response = (
        supabase.table("bot_config")
        .update({"active": False})
        .eq("key", key)
        .execute()
    )
    return bool(response.data)