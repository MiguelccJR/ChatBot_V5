import hmac
import time
import streamlit as st

from db import (
    get_telegram_sessions,
    get_session_display_name,
    get_chat_messages,
    get_session_control_state,
    set_session_control_mode,
    save_feedback,
    create_opener_request,
    get_latest_opener_request,
    create_chat_message,
    create_telegram_history_import_request,
    get_latest_telegram_history_import_request,
)

st.set_page_config(
    page_title="Telegram Control Panel",
    layout="wide"
)

from auth import login_gate as _login_gate
_login_gate()

st.title("Telegram Control Panel")
st.caption("Viewer and control panel for real Telegram chats")


OPENER_LABELS = {
    "soft": "Soft opener",
    "flirty": "Flirty opener",
    "upsell": "Upsell opener",
}

MODE_ICONS = {
    "bot": "🟢",
    "human": "🟡",
    "disabled": "🔴",
}

SOURCE_LABELS = {
    "telegram": "Cliente",
    "local_ai": "Bot",
    "human": "Tú",
    "streamlit": "Panel",
}

SOURCE_AVATARS = {
    "telegram": "👤",
    "local_ai": "🤖",
    "human": "🐒❤️",
    "streamlit": "💻",
}


# ----------------------------
# Auth helpers
# ----------------------------
def get_auth_users() -> dict:
    """
    Expected secrets.toml structure:

    [auth.users.admin]
    password = "TU_PASSWORD"
    role = "admin"

    [auth.users.operador]
    password = "OTRA_PASSWORD"
    role = "user"
    """
    try:
        auth_cfg = st.secrets["auth"]
        users_cfg = auth_cfg["users"]
    except Exception:
        return {}

    users = {}
    for username in users_cfg:
        entry = users_cfg[username]
        users[username] = {
            "password": str(entry["password"]),
            "role": str(entry.get("role", "user")),
        }
    return users


AUTH_USERS = get_auth_users()


def init_auth_state():
    if "auth_username" not in st.session_state:
        st.session_state.auth_username = None
    if "auth_role" not in st.session_state:
        st.session_state.auth_role = "user"
    if "manual_reply_text" not in st.session_state:
        st.session_state.manual_reply_text = ""
    if "chat_version" not in st.session_state:
        st.session_state.chat_version = 0
    if "session_id_activo" not in st.session_state:
        st.session_state.session_id_activo = None


init_auth_state()


def is_admin() -> bool:
    return st.session_state.get("auth_role") == "admin"


def is_logged_in() -> bool:
    return bool(st.session_state.get("auth_username"))


def login(username: str, password: str) -> bool:
    user = AUTH_USERS.get(username)
    if not user:
        return False
    if not hmac.compare_digest(password, user["password"]):
        return False

    st.session_state.auth_username = username
    st.session_state.auth_role = user.get("role", "user")
    return True


def logout():
    st.session_state.auth_username = None
    st.session_state.auth_role = "user"
    st.rerun()


# ----------------------------
# Helpers
# ----------------------------
def cargar_sesiones(include_disabled: bool):
    try:
        return get_telegram_sessions(include_disabled=include_disabled)
    except Exception as e:
        st.error(f"Error loading Telegram sessions: {e}")
        return []


def obtener_session_id_activo(sesiones):
    if "session_id_activo" not in st.session_state:
        st.session_state.session_id_activo = None

    ids = [s["id"] for s in sesiones]

    if not ids:
        st.session_state.session_id_activo = None
        return None

    if st.session_state.session_id_activo not in ids:
        st.session_state.session_id_activo = ids[0]

    return st.session_state.session_id_activo


def procesar_estado_opener(session_id: str, opener_type: str | None):
    if not session_id or not opener_type:
        return None

    try:
        return get_latest_opener_request(session_id, opener_type)
    except Exception as e:
        st.error(f"Error loading opener suggestion: {e}")
        return None


def fmt_datetime(value: str | None) -> str:
    if not value:
        return "-"
    try:
        from datetime import datetime, timezone, timedelta
        dt_str = value[:19].replace("T", " ")
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        year = dt.year
        march_last_sunday = max(datetime(year, 3, day) for day in range(25, 32) if datetime(year, 3, day).weekday() == 6)
        oct_last_sunday = max(datetime(year, 10, day) for day in range(25, 32) if datetime(year, 10, day).weekday() == 6)
        naive_dt = dt.replace(tzinfo=None)
        offset = timedelta(hours=2) if march_last_sunday <= naive_dt < oct_last_sunday else timedelta(hours=1)
        local_dt = dt + offset
        return local_dt.strftime("%d/%m %H:%M")
    except Exception:
        return value[:19].replace("T", " ")


def get_message_display_info(mensaje: dict) -> tuple[str, str, str]:
    role = mensaje.get("role", "assistant")
    source = (mensaje.get("source") or "").strip()

    if role == "user":
        return "user", "👤", "Cliente"

    if source == "human":
        return "assistant", "🐒", "Tú"
    if source == "local_ai":
        return "assistant", "🤖", "Bot"
    if source == "streamlit":
        return "assistant", "💻", "Panel"

    return "assistant", "💬", "Asistente"


def get_next_turn_number(messages: list) -> int:
    if not messages:
        return 1
    try:
        return max((m.get("turn_number") or 0) for m in messages) + 1
    except Exception:
        return 1


def get_last_user_message_id(messages: list) -> int | None:
    for m in reversed(messages):
        if m.get("role") == "user":
            return m.get("id")
    return None


def queue_manual_reply(session_id: str, messages: list, text: str, control_mode: str):
    text = (text or "").strip()
    if not text:
        raise ValueError("Reply text is empty")

    if control_mode == "disabled":
        raise ValueError("Cannot send manual reply while chat is disabled")

    if control_mode == "bot":
        set_session_control_mode(session_id, "human", "Manual reply from control panel")

    create_chat_message(
        session_id=session_id,
        turn_number=get_next_turn_number(messages),
        role="assistant",
        content=text,
        status="done",
        source="human",
        reply_to_message_id=get_last_user_message_id(messages),
        idioma="en",
        categorias_detectadas=[],
        categorias_respondibles=[],
    )


# ----------------------------
# Sidebar auth
# ----------------------------
with st.sidebar:
    st.subheader("Access")

    if is_logged_in():
        st.success(f"Logged in as **{st.session_state.auth_username}** ({st.session_state.auth_role})")
        if st.button("Logout", use_container_width=True):
            logout()
    else:
        st.info("Normal mode active")
        st.caption("Disabled chats stay hidden unless you log in as admin.")

        if AUTH_USERS:
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
        else:
            st.warning("Admin login is not configured. Check .streamlit/secrets.toml")



# ----------------------------
# Load sessions
# ----------------------------
sesiones = cargar_sesiones(include_disabled=is_admin())

with st.sidebar:
    st.subheader("Telegram chats")

    if not sesiones:
        st.info("No Telegram chats registered yet.")
    else:
        total = len(sesiones)
        total_bot = sum(1 for s in sesiones if s.get("control_mode") == "bot")
        total_human = sum(1 for s in sesiones if s.get("control_mode") == "human")
        total_disabled = sum(1 for s in sesiones if s.get("control_mode") == "disabled")

        st.write(f"**Total:** {total}")
        st.write(f"**Bot:** {total_bot}")
        st.write(f"**Human:** {total_human}")
        if is_admin():
            st.write(f"**Disabled:** {total_disabled}")

        st.divider()

        mode_options = ["all", "bot", "human"]
        if is_admin():
            mode_options.append("disabled")

        filtro_modo = st.selectbox(
            "Filter by mode",
            options=mode_options,
            index=0
        )

        busqueda = st.text_input("Search", placeholder="username, name, chat id...").strip().lower()

        sesiones_filtradas = sesiones
        if filtro_modo != "all":
            sesiones_filtradas = [s for s in sesiones_filtradas if s.get("control_mode") == filtro_modo]

        if busqueda:
            tmp = []
            for s in sesiones_filtradas:
                texto = " ".join([
                    str(get_session_display_name(s)),
                    str(s.get("telegram_chat_id") or ""),
                    str(s.get("telegram_username") or ""),
                    str(s.get("telegram_first_name") or ""),
                    str(s.get("tester_name") or ""),
                ]).lower()
                if busqueda in texto:
                    tmp.append(s)
            sesiones_filtradas = tmp

        if not sesiones_filtradas:
            st.warning("No chats match the current filter.")
        else:
            session_id_activo = obtener_session_id_activo(sesiones_filtradas)

            opciones = [s["id"] for s in sesiones_filtradas]
            mapa_labels = {}

            for s in sesiones_filtradas:
                mode = s.get("control_mode", "disabled")
                icon = MODE_ICONS.get(mode, "⚪")
                display = get_session_display_name(s)
                mapa_labels[s["id"]] = f"{icon} {display}"

            elegido = st.radio(
                "Select chat",
                options=opciones,
                index=opciones.index(session_id_activo) if session_id_activo in opciones else 0,
                format_func=lambda sid: mapa_labels[sid]
            )

            if elegido != st.session_state.session_id_activo:
                st.session_state.session_id_activo = elegido
                st.session_state.chat_version = st.session_state.get("chat_version", 0) + 1

                # reset controlado del panel
                st.session_state.pending_opener_type = None
                st.session_state.manual_reply_text = ""

                # limpiar widgets dinámicos de feedback del chat anterior
                keys_to_delete = [
                    k for k in list(st.session_state.keys())
                    if (
                        k.startswith("rating_")
                        or k.startswith("comment_")
                        or k.startswith("save_")
                        or k.startswith("use_opener_")
                        or k.startswith("send_opener_")
                        or k.startswith("import_")
                    )
                ]
                for key in keys_to_delete:
                    del st.session_state[key]

                st.rerun()

        if st.button("Refresh panel", use_container_width=True):
            st.rerun()


if not sesiones:
    st.stop()

session_id_activo = st.session_state.get("session_id_activo")
sesion = next((s for s in sesiones if s["id"] == session_id_activo), None)

if not sesion:
    st.warning("No active Telegram chat selected.")
    st.stop()

if sesion.get("control_mode") == "disabled" and not is_admin():
    st.error("You do not have permission to view disabled chats.")
    st.stop()

display_name = get_session_display_name(sesion)
chat_id = sesion.get("telegram_chat_id") or "-"
username = sesion.get("telegram_username") or "-"
first_name = sesion.get("telegram_first_name") or "-"
registered_at = fmt_datetime(sesion.get("created_at"))
last_activity_at = fmt_datetime(sesion.get("last_activity_at"))

try:
    control_state = get_session_control_state(session_id_activo)
    control_mode = control_state.get("control_mode", "disabled")
    handoff_reason = control_state.get("handoff_reason", "")
    handoff_since = control_state.get("handoff_since")
except Exception:
    control_mode = "disabled"
    handoff_reason = ""
    handoff_since = None

db_chat_messages = []
try:
    db_chat_messages = get_chat_messages(session_id_activo)
except Exception as e:
    st.error(f"Error loading chat history: {e}")

# Version key — forces widget re-render when switching chats
cv = f"{session_id_activo}_{st.session_state.get('chat_version', 0)}"

latest_history_import = None
try:
    latest_history_import = get_latest_telegram_history_import_request(session_id_activo)
except Exception:
    pass

hay_import_pendiente = bool(
    latest_history_import and
    latest_history_import.get("status") in ("pending", "processing")
)

mensajes_pendientes = [
    m for m in db_chat_messages
    if m["role"] == "user" and m["status"] in ("pending_ai", "processing", "waiting_human")
]

hay_pendiente = len(mensajes_pendientes) > 0
ultimo_pendiente = mensajes_pendientes[-1] if hay_pendiente else None

# opener state
if "pending_opener_type" not in st.session_state:
    st.session_state.pending_opener_type = None

latest_requested_opener = procesar_estado_opener(
    session_id_activo,
    st.session_state.pending_opener_type
)
hay_opener_pendiente = False

if latest_requested_opener:
    hay_opener_pendiente = latest_requested_opener.get("status") in ("pending", "processing")


# ----------------------------
# Header
# ----------------------------
st.subheader(f"{display_name}")

col_meta1, col_meta2, col_meta3, col_meta4 = st.columns(4)
with col_meta1:
    st.write(f"**Mode:** {MODE_ICONS.get(control_mode, '⚪')} {control_mode.upper()}")
with col_meta2:
    st.write(f"**Chat ID:** `{chat_id}`")
with col_meta3:
    st.write(f"**Username:** {('@' + username) if username and username != '-' else '-'}")
with col_meta4:
    st.write(f"**Last activity:** {last_activity_at}")

with st.expander("Chat details", expanded=False):
    st.write(f"**Session ID:** `{session_id_activo}`")
    st.write(f"**First name:** {first_name if first_name != '-' else '-'}")
    st.write(f"**Registered:** {registered_at}")
    if handoff_reason:
        st.write(f"**Handoff reason:** {handoff_reason}")
    if handoff_since:
        st.write(f"**Handoff since:** {fmt_datetime(handoff_since)}")


# ----------------------------
# Control buttons
# ----------------------------
col_ctrl1, col_ctrl2, col_ctrl3 = st.columns(3)

with col_ctrl1:
    if control_mode != "bot":
        if st.button("🟢 Set BOT mode", use_container_width=True):
            try:
                set_session_control_mode(session_id_activo, "bot")
                st.success("Bot mode activated.")
                st.rerun()
            except Exception as e:
                st.error(f"Error switching to bot mode: {e}")

with col_ctrl2:
    if control_mode != "human":
        if st.button("🟡 Set HUMAN mode", use_container_width=True):
            try:
                set_session_control_mode(session_id_activo, "human", "Manual takeover from control panel")
                st.info("Human mode activated.")
                st.rerun()
            except Exception as e:
                st.error(f"Error switching to human mode: {e}")

with col_ctrl3:
    if control_mode != "disabled":
        if st.button("🔴 Set DISABLED mode", use_container_width=True):
            try:
                set_session_control_mode(session_id_activo, "disabled")
                st.warning("Chat disabled.")
                st.rerun()
            except Exception as e:
                st.error(f"Error switching to disabled mode: {e}")


# ----------------------------
# Status banners
# ----------------------------
if control_mode == "human":
    st.warning(
        "🤚 Human mode active — the bot is paused for this chat."
        + (f" Reason: *{handoff_reason}*" if handoff_reason else "")
        + (f" Since: {fmt_datetime(handoff_since)}" if handoff_since else "")
    )
elif control_mode == "disabled":
    st.error("🔴 Disabled mode — this chat is ignored by the bot.")
else:
    st.success("🤖 Bot mode active — AI can respond automatically.")

# Do not show waiting_human/reading/typing banner for disabled chats
if ultimo_pendiente and control_mode != "disabled":
    estado = ultimo_pendiente["status"]
    if estado == "pending_ai":
        st.info("Reading...")
    elif estado == "processing":
        st.info("Typing...")
    elif estado == "waiting_human":
        st.info("Waiting for human reply...")


# ----------------------------
# Suggested openers
# ----------------------------
st.markdown("### Suggested openers")

col1, col2 = st.columns(2)
with col1:
    if st.button("Soft opener", use_container_width=True):
        try:
            create_opener_request(session_id_activo, "soft")
            st.session_state.pending_opener_type = "soft"
            st.rerun()
        except Exception as e:
            st.error(f"Error requesting opener: {e}")

with col2:
    if st.button("Flirty opener", use_container_width=True):
        try:
            create_opener_request(session_id_activo, "flirty")
            st.session_state.pending_opener_type = "flirty"
            st.rerun()
        except Exception as e:
            st.error(f"Error requesting opener: {e}")

if latest_requested_opener:
    opener_status = latest_requested_opener.get("status")
    opener_type = latest_requested_opener.get("opener_type") or st.session_state.pending_opener_type
    opener_label = OPENER_LABELS.get(opener_type, "Opener")
    opener_text = latest_requested_opener.get("suggestion_text", "")

    if opener_status == "pending":
        st.info(f"Generating {opener_label.lower()}...")
    elif opener_status == "processing":
        st.info(f"Preparing {opener_label.lower()}...")
    elif opener_status == "error":
        st.warning(f"{opener_label} error: {latest_requested_opener.get('error_text', 'unknown error')}")
        st.session_state.pending_opener_type = None
    elif opener_status == "done" and opener_text:
        st.success(opener_text)

        op_col1, op_col2 = st.columns(2)
        with op_col1:
            if st.button("Use opener in reply box", key=f"use_opener_{latest_requested_opener['id']}", use_container_width=True):
                st.session_state.manual_reply_text = opener_text
                st.success("Opener copied to manual reply box")
                st.rerun()

        with op_col2:
            if st.button("Send opener now", key=f"send_opener_{latest_requested_opener['id']}", use_container_width=True):
                try:
                    queue_manual_reply(
                        session_id=session_id_activo,
                        messages=db_chat_messages,
                        text=opener_text,
                        control_mode=control_mode,
                    )
                    st.session_state.pending_opener_type = None
                    st.session_state.manual_reply_text = ""
                    st.success("Opener queued for Telegram")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error sending opener: {e}")


# ----------------------------
# Manual reply box
# ----------------------------
st.markdown("### Manual reply")

if control_mode == "disabled":
    st.caption("Disabled chats cannot send manual replies.")
else:
    if control_mode == "bot":
        st.caption("Sending a manual reply will switch this chat to HUMAN mode automatically.")
    else:
        st.caption("Manual replies are sent as you and stored for future context.")

    manual_text = st.text_area(
        "Write a reply",
        key="manual_reply_text",
        height=120,
        placeholder="Write here or use an opener above...",
    )

    if st.button("Send manual reply", use_container_width=True):
        try:
            queue_manual_reply(
                session_id=session_id_activo,
                messages=db_chat_messages,
                text=manual_text,
                control_mode=control_mode,
            )
            st.session_state.pending_opener_type = None
            st.session_state.manual_reply_text = ""
            st.success("Manual reply queued for Telegram")
            st.rerun()
        except Exception as e:
            st.error(f"Error sending manual reply: {e}")


# ----------------------------
# Chat history (most recent first)
# ----------------------------
st.markdown("### Chat history")

col_imp1, col_imp2 = st.columns([1, 3])
with col_imp1:
    if st.button("⬆️ Import 10 older", key=f"import_{cv}", use_container_width=True):
        try:
            create_telegram_history_import_request(
                session_id=session_id_activo,
                requested_by=st.session_state.get("auth_username", "user"),
                count_to_import=10,
            )
            st.success("Import queued")
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")
with col_imp2:
    if latest_history_import:
        imp_status = latest_history_import.get("status")
        if imp_status == "pending":
            st.info("Import queued...")
        elif imp_status == "processing":
            st.info("Importing older messages...")
        elif imp_status == "done":
            st.caption("Last import completed ✓")
        elif imp_status == "error":
            st.warning(f"Import error: {latest_history_import.get('error_text', '')}")

st.caption("Most recent messages at the top")

MEDIA_PLACEHOLDERS = {
    "[Video received while disabled]",
    "[Photo received while disabled]",
    "[Sticker received while disabled]",
    "[Voice message received while disabled]",
    "[Customer sent a photo]",
    "[Customer sent a sticker]",
    "[Media received while disabled]",
    "[Media received while disabled — upload failed]",
}

if not db_chat_messages:
    st.info("No messages yet for this chat.")
else:
    mensajes_mostrar = list(reversed(db_chat_messages[-100:]))

    for i, mensaje in enumerate(mensajes_mostrar):
        role = mensaje["role"]
        source = mensaje.get("source", "")
        status = mensaje.get("status", "")
        turn_number = mensaje.get("turn_number", 0)
        media_type = (mensaje.get("media_type") or "").strip()
        media_url = (mensaje.get("media_url") or "").strip()
        message_id = mensaje.get("id", f"{turn_number}_{i}")
        text_content = (mensaje.get("content") or "").strip()

        chat_role, avatar, label = get_message_display_info(mensaje)

        with st.chat_message(chat_role, avatar=avatar):

            if media_type and media_url:
                if media_type in ("image", "sticker"):
                    try:
                        st.image(media_url)
                    except Exception:
                        st.caption(f"📷 {media_url}")
                elif media_type == "audio":
                    try:
                        st.audio(media_url)
                    except Exception:
                        st.caption(f"🎵 {media_url}")
                elif media_type == "video":
                    try:
                        st.video(media_url)
                    except Exception:
                        st.caption(f"🎬 {media_url}")

            is_placeholder = text_content in MEDIA_PLACEHOLDERS or text_content.startswith("[Voice message]:")
            if text_content and not (media_type and is_placeholder):
                st.markdown(text_content)

            # Use telegram_date if available, else created_at
            date_to_show = mensaje.get("telegram_date") or mensaje.get("created_at")
            meta = [label, fmt_datetime(date_to_show)]
            if status:
                meta.append(f"status={status}")
            st.caption(" | ".join(m for m in meta if m and m != "-"))

            if role == "assistant" and source == "local_ai":
                unique_id = f"{cv}_{message_id}"
                rating = st.radio(
                    "Rate this reply",
                    options=["Good", "Regular", "Bad"],
                    horizontal=True,
                    key=f"rating_{unique_id}"
                )
                comment = st.text_input(
                    "Optional comment",
                    key=f"comment_{unique_id}",
                    placeholder="What sounds good or wrong here?"
                )
                if st.button("Save feedback", key=f"save_{unique_id}"):
                    try:
                        save_feedback(
                            session_id=session_id_activo,
                            turn_number=turn_number,
                            rating=rating,
                            comment=comment
                        )
                        st.success("Feedback saved")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error saving feedback: {e}")


# ----------------------------
# Auto-refresh
# ----------------------------
if hay_pendiente or hay_opener_pendiente or hay_import_pendiente:
    time.sleep(2)
    st.rerun()