import streamlit as st
from db import get_supabase

st.set_page_config(page_title="Telegram Chats", layout="wide")
st.title("💬 Telegram Chats")
st.caption("Manage which chats the bot responds to.")


def get_supabase_direct():
    import os
    from supabase import create_client
    url = os.getenv("SUPABASE_URL") or st.secrets["SUPABASE_URL"]
    key = os.getenv("SUPABASE_KEY") or st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


def load_telegram_sessions():
    supabase = get_supabase_direct()
    response = (
        supabase.table("test_sessions")
        .select("*")
        .eq("platform", "telegram")
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []


def set_control_mode(session_id: str, mode: str):
    from datetime import datetime, timezone
    supabase = get_supabase_direct()
    payload = {"control_mode": mode}
    if mode == "bot":
        payload["handoff_reason"] = None
        payload["handoff_since"] = None
    supabase.table("test_sessions").update(payload).eq("id", session_id).execute()


def delete_session(session_id: str):
    supabase = get_supabase_direct()
    # Delete messages first
    supabase.table("chat_messages").delete().eq("session_id", session_id).execute()
    supabase.table("test_sessions").delete().eq("id", session_id).execute()


# ----------------------------
# Load sessions
# ----------------------------
try:
    sessions = load_telegram_sessions()
except Exception as e:
    st.error(f"Error loading sessions: {e}")
    st.stop()

if not sessions:
    st.info("No Telegram chats registered yet. They will appear here automatically when someone writes to the account.")
    st.stop()

# ----------------------------
# Filter
# ----------------------------
MODE_OPTIONS = ["all", "bot", "human", "disabled"]
MODE_COLORS = {
    "bot": "🟢",
    "human": "🟡",
    "disabled": "🔴",
}

filter_mode = st.selectbox(
    "Filter by mode",
    options=MODE_OPTIONS,
    index=0,
    format_func=lambda x: "All" if x == "all" else f"{MODE_COLORS.get(x, '')} {x.title()}"
)

if filter_mode != "all":
    sessions = [s for s in sessions if s.get("control_mode") == filter_mode]

st.caption(f"Showing {len(sessions)} chats")
st.divider()

# ----------------------------
# Session list
# ----------------------------
for session in sessions:
    session_id = session["id"]
    mode = session.get("control_mode", "disabled")
    username = session.get("telegram_username") or ""
    first_name = session.get("telegram_first_name") or ""
    chat_id = session.get("telegram_chat_id") or ""
    handoff_reason = session.get("handoff_reason") or ""
    created_at = (session.get("created_at") or "")[:19].replace("T", " ")

    display_name = f"@{username}" if username else first_name or f"ID {chat_id}"
    icon = MODE_COLORS.get(mode, "⚪")

    with st.expander(f"{icon} {display_name} — {mode.upper()}", expanded=False):
        col1, col2 = st.columns([3, 2])

        with col1:
            st.write(f"**Chat ID:** `{chat_id}`")
            if username:
                st.write(f"**Username:** @{username}")
            if first_name:
                st.write(f"**Name:** {first_name}")
            st.write(f"**Registered:** {created_at}")
            if handoff_reason:
                st.write(f"**Handoff reason:** {handoff_reason}")

        with col2:
            st.write("**Change mode:**")

            if mode != "bot":
                if st.button("🟢 Activate bot", key=f"bot_{session_id}", use_container_width=True):
                    set_control_mode(session_id, "bot")
                    st.success("Bot activated")
                    st.rerun()

            if mode != "human":
                if st.button("🟡 Human mode", key=f"human_{session_id}", use_container_width=True):
                    set_control_mode(session_id, "human")
                    st.info("Switched to human mode")
                    st.rerun()

            if mode != "disabled":
                if st.button("🔴 Disable", key=f"disable_{session_id}", use_container_width=True):
                    set_control_mode(session_id, "disabled")
                    st.warning("Chat disabled")
                    st.rerun()

            st.write("")
            if st.button("🗑️ Delete chat", key=f"delete_{session_id}", use_container_width=True):
                delete_session(session_id)
                st.error("Chat deleted")
                st.rerun()

st.divider()
st.caption("🟢 Bot = AI responds automatically | 🟡 Human = you reply manually | 🔴 Disabled = bot ignores this chat")