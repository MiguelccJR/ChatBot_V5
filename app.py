import streamlit as st
import time

from faq_bot_v5 import (
    cargar_faqs,
    crear_estado_conversacion,
    obtener_opener,
)

from db import (
    create_test_session,
    save_feedback,
    create_chat_message,
    get_chat_messages,
)

st.set_page_config(
    page_title="FAQ Bot Multi-Chat Simulator",
    layout="wide"
)

st.title("Internal bot simulator")
st.caption("Local testing / simple questions")


# ----------------------------
# Chat helpers
# ----------------------------
def crear_chat(nombre=None, plataforma="test"):
    chat_id = f"chat_{st.session_state.next_chat_id:03d}"
    st.session_state.next_chat_id += 1

    if nombre is None:
        nombre = f"user_{chat_id.split('_')[-1]}"

    return chat_id, {
        "nombre": nombre,
        "plataforma": plataforma,
        "historial": [],
        "estado_bot": crear_estado_conversacion(),
        "ultimo_resultado": None,
        "score": 0,
        "etiquetas": [],
        "turn_counter": 0,
        "db_session_id": None,
    }


def obtener_chat_activo():
    return st.session_state.chats[st.session_state.chat_activo]


def reiniciar_chat_activo():
    chat = obtener_chat_activo()
    chat["historial"] = []
    chat["estado_bot"] = crear_estado_conversacion()
    chat["ultimo_resultado"] = None
    chat["score"] = 0
    chat["etiquetas"] = []
    chat["turn_counter"] = 0
    chat["db_session_id"] = None


def eliminar_chat_activo():
    chat_id = st.session_state.chat_activo
    if len(st.session_state.chats) <= 1:
        st.warning("At least one chat must remain.")
        return

    del st.session_state.chats[chat_id]
    st.session_state.chat_activo = list(st.session_state.chats.keys())[0]


def recargar_faqs():
    st.session_state.faq_data = cargar_faqs()


# ----------------------------
# Global app initialization
# ----------------------------
def inicializar_estado_app():
    if "faq_data" not in st.session_state:
        st.session_state.faq_data = cargar_faqs()

    if "chats" not in st.session_state:
        st.session_state.chats = {}

    if "next_chat_id" not in st.session_state:
        st.session_state.next_chat_id = 1

    if "chat_activo" not in st.session_state:
        st.session_state.chat_activo = None

    # Backfill missing keys for old chats created before new schema
    for cid, chat in st.session_state.chats.items():
        if "nombre" not in chat:
            chat["nombre"] = cid
        if "plataforma" not in chat:
            chat["plataforma"] = "test"
        if "historial" not in chat:
            chat["historial"] = []
        if "estado_bot" not in chat:
            chat["estado_bot"] = crear_estado_conversacion()
        if "ultimo_resultado" not in chat:
            chat["ultimo_resultado"] = None
        if "score" not in chat:
            chat["score"] = 0
        if "etiquetas" not in chat:
            chat["etiquetas"] = []
        if "turn_counter" not in chat:
            chat["turn_counter"] = 0
        if "db_session_id" not in chat:
            chat["db_session_id"] = None

    if "mostrar_debug" not in st.session_state:
        st.session_state.mostrar_debug = True

    if "tester_name" not in st.session_state:
        st.session_state.tester_name = ""

    if "turn_number_global" not in st.session_state:
        st.session_state.turn_number_global = 0

    if "suggested_opener" not in st.session_state:
        st.session_state.suggested_opener = ""

    if "suggested_opener_type" not in st.session_state:
        st.session_state.suggested_opener_type = ""

    if not st.session_state.chats:
        chat_id, chat_data = crear_chat(nombre="user_001", plataforma="test")
        st.session_state.chats[chat_id] = chat_data
        st.session_state.chat_activo = chat_id

    if st.session_state.chat_activo not in st.session_state.chats:
        st.session_state.chat_activo = list(st.session_state.chats.keys())[0]


inicializar_estado_app()


# ----------------------------
# Sidebar
# ----------------------------
with st.sidebar:
    st.subheader("Chats")

    st.session_state.tester_name = st.text_input(
        "Tester name",
        value=st.session_state.tester_name
    )

    with st.expander("New chat", expanded=False):
        nuevo_nombre = st.text_input("New chat name", value="")
        nueva_plataforma = st.selectbox(
            "Platform",
            options=["test", "telegram", "onlyfans"],
            index=0,
            key="select_nueva_plataforma"
        )

        if st.button("Create chat", use_container_width=True):
            nombre_final = nuevo_nombre.strip() if nuevo_nombre.strip() else None
            chat_id, chat_data = crear_chat(
                nombre=nombre_final,
                plataforma=nueva_plataforma
            )
            st.session_state.chats[chat_id] = chat_data
            st.session_state.chat_activo = chat_id
            st.rerun()

    opciones_chat = []
    mapa_labels = {}

    for cid, cdata in st.session_state.chats.items():
        label = f"{cdata['nombre']} [{cdata['plataforma']}]"
        opciones_chat.append(cid)
        mapa_labels[cid] = label

    chat_seleccionado = st.radio(
        "Select chat",
        options=opciones_chat,
        index=opciones_chat.index(st.session_state.chat_activo),
        format_func=lambda cid: mapa_labels[cid]
    )

    if chat_seleccionado != st.session_state.chat_activo:
        st.session_state.chat_activo = chat_seleccionado
        st.rerun()

    st.divider()

    chat_activo = obtener_chat_activo()

    st.subheader("Edit active chat")

    nuevo_nombre_chat = st.text_input(
        "Display name",
        value=chat_activo["nombre"],
        key="input_nombre_chat_activo"
    )

    nueva_plataforma_chat = st.selectbox(
        "Chat platform",
        options=["test", "telegram", "onlyfans"],
        index=["test", "telegram", "onlyfans"].index(chat_activo["plataforma"]),
        key="select_plataforma_chat_activo"
    )

    if st.button("Save chat changes", use_container_width=True):
        chat_activo["nombre"] = nuevo_nombre_chat.strip() if nuevo_nombre_chat.strip() else chat_activo["nombre"]
        chat_activo["plataforma"] = nueva_plataforma_chat
        st.success("Chat updated")
        st.rerun()

    col_sidebar_1, col_sidebar_2 = st.columns(2)

    with col_sidebar_1:
        if st.button("Reset chat", use_container_width=True):
            reiniciar_chat_activo()
            st.rerun()

    with col_sidebar_2:
        if st.button("Delete chat", use_container_width=True):
            eliminar_chat_activo()
            st.rerun()

    st.divider()

    if st.button("Reload FAQs", use_container_width=True):
        recargar_faqs()
        st.success("FAQs reloaded")

    st.session_state.mostrar_debug = st.checkbox(
        "Show technical debug",
        value=st.session_state.mostrar_debug
    )

    st.divider()
    st.subheader("Active chat summary")
    st.write(f"**Name:** {chat_activo['nombre']}")
    st.write(f"**Platform:** {chat_activo['plataforma']}")
    st.write(f"**Score:** {chat_activo['score']}")
    st.write(f"**Tags:** {', '.join(chat_activo['etiquetas']) if chat_activo['etiquetas'] else '-'}")
    st.write(f"**DB session:** {chat_activo.get('db_session_id') if chat_activo.get('db_session_id') else '-'}")

    if st.session_state.mostrar_debug:
        st.divider()
        st.subheader("Bot internal state")
        st.json(chat_activo["estado_bot"])

        if chat_activo["ultimo_resultado"] is not None:
            resultado = chat_activo["ultimo_resultado"]

            st.divider()
            st.subheader("Latest analysis")
            st.write(f"**Detected language:** `{resultado['idioma']}`")

            st.write("**Detected categories:**")
            if resultado["categorias_detectadas"]:
                for item in resultado["categorias_detectadas"]:
                    if "puntuacion" in item and "confianza" in item:
                        st.write(
                            f"- {item['categoria']} | score={item['puntuacion']} | confidence={item['confianza']}"
                        )
                    else:
                        st.write(f"- {item['categoria']}")
            else:
                st.write("- None")

            st.write("**Respondable categories:**")
            if resultado["categorias_respondibles"]:
                for item in resultado["categorias_respondibles"]:
                    if "puntuacion" in item and "confianza" in item:
                        st.write(
                            f"- {item['categoria']} | score={item['puntuacion']} | confidence={item['confianza']}"
                        )
                    else:
                        st.write(f"- {item['categoria']}")
            else:
                st.write("- None")

            st.write("**Generated messages:**")
            for i, msg in enumerate(resultado["mensajes_respuesta"], start=1):
                st.write(f"{i}. {msg}")


# ----------------------------
# Main area
# ----------------------------
chat_activo = obtener_chat_activo()

db_chat_messages = []
if chat_activo["db_session_id"] is not None:
    try:
        db_chat_messages = get_chat_messages(chat_activo["db_session_id"])
    except Exception as e:
        st.error(f"Error loading chat messages: {e}")

mensajes_pendientes = [
    m for m in db_chat_messages
    if m["role"] == "user" and m["status"] in ("pending_ai", "processing")
]

hay_pendiente = len(mensajes_pendientes) > 0
ultimo_pendiente = mensajes_pendientes[-1] if hay_pendiente else None

st.subheader(f"Active chat: {chat_activo['nombre']} [{chat_activo['plataforma']}]")

col_refresh1, col_refresh2 = st.columns([1, 4])

with col_refresh1:
    if st.button("Refresh chat"):
        st.rerun()

with col_refresh2:
    if chat_activo.get("db_session_id"):
        st.caption(f"Session ID: {chat_activo['db_session_id']}")

if ultimo_pendiente:
    if ultimo_pendiente["status"] == "pending_ai":
        st.info("Reading...")
    elif ultimo_pendiente["status"] == "processing":
        st.info("Typing...")

st.markdown("### Suggested openers")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("Soft opener", use_container_width=True):
        st.session_state.suggested_opener = obtener_opener("opener_soft", st.session_state.faq_data) or ""
        st.session_state.suggested_opener_type = "opener_soft"

with col2:
    if st.button("Flirty opener", use_container_width=True):
        st.session_state.suggested_opener = obtener_opener("opener_flirty", st.session_state.faq_data) or ""
        st.session_state.suggested_opener_type = "opener_flirty"

with col3:
    if st.button("Upsell opener", use_container_width=True):
        st.session_state.suggested_opener = obtener_opener("opener_upsell", st.session_state.faq_data) or ""
        st.session_state.suggested_opener_type = "opener_upsell"

if st.session_state.suggested_opener:
    st.info(st.session_state.suggested_opener)

    if st.button("Use opener in chat", use_container_width=True):
        if chat_activo["db_session_id"] is None:
            chat_activo["db_session_id"] = create_test_session(
                tester_name=st.session_state.tester_name or "anonymous",
                platform=chat_activo["plataforma"]
            )

        chat_activo["turn_counter"] += 1
        opener_turn_number = chat_activo["turn_counter"]

        create_chat_message(
            session_id=chat_activo["db_session_id"],
            turn_number=opener_turn_number,
            role="assistant",
            content=st.session_state.suggested_opener,
            status="done",
            source="streamlit",
            reply_to_message_id=None,
            idioma="en",
            categorias_detectadas=[{
                "categoria": st.session_state.suggested_opener_type,
                "puntuacion": 1,
                "confianza": "manual"
            }],
            categorias_respondibles=[{
                "categoria": st.session_state.suggested_opener_type,
                "puntuacion": 1,
                "confianza": "manual"
            }]
        )

        chat_activo["estado_bot"]["ultimo_opener"] = st.session_state.suggested_opener_type
        st.session_state.suggested_opener = ""
        st.session_state.suggested_opener_type = ""
        st.rerun()

for i, mensaje in enumerate(db_chat_messages[-40:]):
    with st.chat_message(mensaje["role"]):
        st.markdown(mensaje["content"])

        if mensaje["role"] == "assistant":
            turn_number = mensaje.get("turn_number", 0)
            session_part = chat_activo["db_session_id"] or "no_session"
            unique_id = f"{session_part}_{turn_number}_{i}"

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
                save_feedback(
                    session_id=chat_activo["db_session_id"],
                    turn_number=turn_number,
                    rating=rating,
                    comment=comment
                )
                st.success("Feedback saved")
                st.rerun()

if hay_pendiente:
    time.sleep(2)
    st.rerun()


# ----------------------------
# Chat input
# ----------------------------
texto_usuario = st.chat_input(
    f"Write as {chat_activo['nombre']}..."
)


# ----------------------------
# Processing
# ----------------------------
if texto_usuario and texto_usuario.strip():
    if chat_activo["db_session_id"] is None:
        chat_activo["db_session_id"] = create_test_session(
            tester_name=st.session_state.tester_name or "anonymous",
            platform=chat_activo["plataforma"]
        )

    chat_activo["turn_counter"] += 1
    current_turn_number = chat_activo["turn_counter"]

    create_chat_message(
        session_id=chat_activo["db_session_id"],
        turn_number=current_turn_number,
        role="user",
        content=texto_usuario,
        status="pending_ai",
        source="streamlit",
        idioma="en",
        categorias_detectadas=[],
        categorias_respondibles=[]
    )

    st.rerun()