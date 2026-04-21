import streamlit as st
from db import (
    get_archived_telegram_sessions,
    get_session_display_name,
    get_chat_messages,
)

st.set_page_config(page_title="Archived Telegram Chats", layout="wide")
st.title("Archived Telegram Chats")
st.caption("Admin-only view for archived Telegram chats")


# ----------------------------
# Auth helpers
# ----------------------------
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


def fmt_datetime(value: str | None) -> str:
    if not value:
        return "-"
    return value[:19].replace("T", " ")


def get_message_display_info(mensaje: dict):
    role = mensaje.get("role", "assistant")
    source = (mensaje.get("source") or "").strip()

    if role == "user":
        return "user", "👤", "Cliente"

    if source == "human":
        return "assistant", "🧑", "Tú"
    if source == "local_ai":
        return "assistant", "🤖", "Bot"
    if source == "streamlit":
        return "assistant", "💻", "Panel"

    return "assistant", "💬", "Asistente"


# ----------------------------
# Sidebar login
# ----------------------------
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


if not is_admin():
    st.warning("This page is only visible to admin.")
    st.stop()


# ----------------------------
# Load archived sessions
# ----------------------------
try:
    sesiones = get_archived_telegram_sessions()
except Exception as e:
    st.error(f"Error loading archived chats: {e}")
    st.stop()

if not sesiones:
    st.info("No archived chats found.")
    st.stop()

if "archived_session_id_activo" not in st.session_state:
    st.session_state.archived_session_id_activo = sesiones[0]["id"]

ids = [s["id"] for s in sesiones]
if st.session_state.archived_session_id_activo not in ids:
    st.session_state.archived_session_id_activo = ids[0]

with st.sidebar:
    st.divider()
    st.subheader("Archived chats")

    mapa_labels = {}
    for s in sesiones:
        display = get_session_display_name(s)
        mode = s.get("control_mode", "disabled")
        mapa_labels[s["id"]] = f"📦 {display} ({mode})"

    elegido = st.radio(
        "Select archived chat",
        options=ids,
        index=ids.index(st.session_state.archived_session_id_activo),
        format_func=lambda sid: mapa_labels[sid],
    )

    if elegido != st.session_state.archived_session_id_activo:
        st.session_state.archived_session_id_activo = elegido
        st.rerun()

    if st.button("Refresh archived page", use_container_width=True):
        st.rerun()

session_id_activo = st.session_state.archived_session_id_activo
sesion = next((s for s in sesiones if s["id"] == session_id_activo), None)

if not sesion:
    st.warning("Archived chat not found.")
    st.stop()

display_name = get_session_display_name(sesion)
chat_id = sesion.get("telegram_chat_id") or "-"
username = sesion.get("telegram_username") or "-"
first_name = sesion.get("telegram_first_name") or "-"
registered_at = fmt_datetime(sesion.get("created_at"))
last_activity_at = fmt_datetime(sesion.get("last_activity_at"))

st.subheader(f"📦 {display_name}")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.write(f"**Mode:** {sesion.get('control_mode', 'disabled').upper()}")
with col2:
    st.write(f"**Chat ID:** `{chat_id}`")
with col3:
    st.write(f"**Username:** {('@' + username) if username and username != '-' else '-'}")
with col4:
    st.write(f"**Last activity:** {last_activity_at}")

with st.expander("Archived chat details", expanded=False):
    st.write(f"**Session ID:** `{session_id_activo}`")
    st.write(f"**First name:** {first_name if first_name != '-' else '-'}")
    st.write(f"**Registered:** {registered_at}")
    st.write(f"**Archived:** {sesion.get('is_archived', False)}")

try:
    db_chat_messages = get_chat_messages(session_id_activo)
except Exception as e:
    st.error(f"Error loading archived chat history: {e}")
    st.stop()

st.markdown("### Chat history")

if not db_chat_messages:
    st.info("No messages yet for this archived chat.")
else:
    for mensaje in db_chat_messages[-100:]:
        chat_role, avatar, label = get_message_display_info(mensaje)
        source = mensaje.get("source", "")
        status = mensaje.get("status", "")
        turn_number = mensaje.get("turn_number", 0)

        with st.chat_message(chat_role, avatar=avatar):
            st.markdown(mensaje["content"])

            meta = [label]
            if source:
                meta.append(f"source={source}")
            if status:
                meta.append(f"status={status}")
            if turn_number is not None:
                meta.append(f"turn={turn_number}")

            st.caption(" | ".join(meta))