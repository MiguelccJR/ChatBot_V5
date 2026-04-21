import streamlit as st
from db import (
    get_telegram_sessions,
    get_session_display_name,
)

st.set_page_config(page_title="Telegram Chats", layout="wide")
st.title("💬 Telegram Chats")
st.caption("Manage which chats the bot responds to.")


def get_auth_users():
    try:
        auth_section = st.secrets["auth"]
        users_section = auth_section["users"]
        return {k: dict(v) for k, v in users_section.items()}
    except Exception:
        return {}


AUTH_USERS = get_auth_users()


def is_logged_in():
    return st.session_state.get("auth_logged_in", False)


def is_admin():
    return is_logged_in() and st.session_state.get("auth_role") == "admin"


def login(username: str, password: str) -> bool:
    user = AUTH_USERS.get(username)
    if not user:
        return False
    if password != user.get("password"):
        return False

    st.session_state.auth_logged_in = True
    st.session_state.auth_username = username
    st.session_state.auth_role = user.get("role", "user")
    return True


def logout():
    st.session_state.auth_logged_in = False
    st.session_state.auth_username = None
    st.session_state.auth_role = None
    st.rerun()


def load_telegram_sessions():
    return get_telegram_sessions(
        include_disabled=is_admin(),
        include_archived=False,
    )


def set_control_mode(session_id: str, mode: str):
    from db import set_session_control_mode
    if mode == "human":
        set_session_control_mode(session_id, "human", "Manual takeover from Telegram Chats page")
    else:
        set_session_control_mode(session_id, mode)


def delete_session(session_id: str):
    from db import get_supabase
    supabase = get_supabase()
    supabase.table("chat_messages").delete().eq("session_id", session_id).execute()
    supabase.table("test_sessions").delete().eq("id", session_id).execute()


with st.sidebar:
    st.subheader("Access")

    if is_logged_in():
        st.success(f"Logged in as **{st.session_state.auth_username}** ({st.session_state.auth_role})")
        if st.button("Logout", use_container_width=True):
            logout()
    else:
        st.info("Normal mode active")
        with st.expander("Admin login"):
            with st.form("login_form", clear_on_submit=False):
                login_user = st.text_input("User")
                login_pass = st.text_input("Password", type="password")
                login_submit = st.form_submit_button("Login as admin", use_container_width=True)

                if login_submit:
                    if login(login_user.strip(), login_pass):
                        st.rerun()
                    else:
                        st.error("Invalid username or password")


try:
    sessions = load_telegram_sessions()
except Exception as e:
    st.error(f"Error loading sessions: {e}")
    st.stop()

if not sessions:
    st.info("No non-archived Telegram chats available.")
    st.stop()

MODE_OPTIONS = ["all", "bot", "human"] if not is_admin() else ["all", "bot", "human", "disabled"]
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

st.caption(f"Showing {len(sessions)} non-archived chats")
st.divider()

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
            st.write(f"**Archived:** {session.get('is_archived', False)}")

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

            if is_admin() and mode != "disabled":
                if st.button("🔴 Disable", key=f"disable_{session_id}", use_container_width=True):
                    set_control_mode(session_id, "disabled")
                    st.warning("Chat disabled")
                    st.rerun()

            if is_admin():
                st.write("")
                if st.button("🗑️ Delete chat", key=f"delete_{session_id}", use_container_width=True):
                    delete_session(session_id)
                    st.error("Chat deleted")
                    st.rerun()

st.divider()
st.caption("Normal users only see non-archived chats. Archived chats are admin-only.")