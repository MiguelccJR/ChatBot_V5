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
)

st.set_page_config(
    page_title="Telegram Control Panel",
    layout="wide"
)

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
    "human": "🧑",
    "streamlit": "💻",
}


# ----------------------------
# Helpers
# ----------------------------
def cargar_sesiones():
    try:
        return get_telegram_sessions(include_disabled=True)
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
    return value[:19].replace("T", " ")


def get_message_display_info(mensaje: dict) -> tuple[str, str, str]:
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
# Load sessions
# ----------------------------
sesiones = cargar_sesiones()

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
        st.write(f"**Disabled:** {total_disabled}")

        st.divider()

        filtro_modo = st.selectbox(
            "Filter by mode",
            options=["all", "bot", "human", "disabled"],
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

if ultimo_pendiente:
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

    if opener_status == "pending":
        st.info(f"Generating {opener_label.lower()}...")
    elif opener_status == "processing":
        st.info(f"Preparing {opener_label.lower()}...")
    elif opener_status == "error":
        st.warning(f"{opener_label} error: {latest_requested_opener.get('error_text', 'unknown error')}")
        st.session_state.pending_opener_type = None
    elif opener_status == "done" and latest_requested_opener.get("suggestion_text"):
        st.success(latest_requested_opener["suggestion_text"])
        st.caption("Copy and send manually if you want.")
        st.session_state.pending_opener_type = None


# ----------------------------
# Chat history
# ----------------------------
st.markdown("### Chat history")

if not db_chat_messages:
    st.info("No messages yet for this chat.")
else:
    for i, mensaje in enumerate(db_chat_messages[-100:]):
        role = mensaje["role"]
        source = mensaje.get("source", "")
        status = mensaje.get("status", "")
        turn_number = mensaje.get("turn_number", 0)

        chat_role, avatar, label = get_message_display_info(mensaje)

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

            if role == "assistant":
                unique_id = f"{session_id_activo}_{turn_number}_{i}"

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
if hay_pendiente or hay_opener_pendiente:
    time.sleep(2)
    st.rerun()