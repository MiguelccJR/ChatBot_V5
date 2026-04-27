import time
import streamlit as st
from auth import login_gate, is_admin, render_sidebar_auth
from db import get_telegram_sessions, get_session_display_name, set_session_control_mode

st.set_page_config(page_title="Telegram Chats", layout="wide")
login_gate()
render_sidebar_auth()

st.title("💬 Telegram Chats")
st.caption("Manage which chats the bot responds to.")

# Auto-refresh every 10 seconds
if "last_refresh_tcp" not in st.session_state:
    st.session_state.last_refresh_tcp = time.time()

col_r1, col_r2 = st.columns([1, 4])
with col_r1:
    if st.button("🔄 Refresh", use_container_width=True):
        st.rerun()
if time.time() - st.session_state.last_refresh_tcp > 10:
    st.session_state.last_refresh_tcp = time.time()
    st.rerun()

try:
    # All logged-in users see all chats including disabled
    sessions = get_telegram_sessions(include_disabled=True)
except Exception as e:
    st.error(f"Error loading sessions: {e}")
    st.stop()

if not sessions:
    st.info("No Telegram chats available.")
    st.stop()

MODE_COLORS = {"bot": "🟢", "human": "🟡", "disabled": "🔴"}
MODE_OPTIONS = ["all", "bot", "human", "disabled"]

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

def set_mode(session_id, mode):
    if mode == "human":
        set_session_control_mode(session_id, "human", "Manual takeover from Telegram Chats page")
    else:
        set_session_control_mode(session_id, mode)

def delete_session(session_id):
    from db import get_supabase
    supabase = get_supabase()
    supabase.table("chat_messages").delete().eq("session_id", session_id).execute()
    supabase.table("opener_suggestions").delete().eq("session_id", session_id).execute()
    supabase.table("telegram_history_import_requests").delete().eq("session_id", session_id).execute()
    supabase.table("feedback").delete().eq("session_id", session_id).execute()
    supabase.table("test_sessions").delete().eq("id", session_id).execute()

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
                    set_mode(session_id, "bot")
                    st.rerun()
            if mode != "human":
                if st.button("🟡 Human mode", key=f"human_{session_id}", use_container_width=True):
                    set_mode(session_id, "human")
                    st.rerun()
            if mode != "disabled":
                if st.button("🔴 Disable", key=f"disable_{session_id}", use_container_width=True):
                    set_mode(session_id, "disabled")
                    st.rerun()
            if is_admin():
                if st.button("🗑️ Delete", key=f"delete_{session_id}", use_container_width=True):
                    delete_session(session_id)
                    st.rerun()