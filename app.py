import streamlit as st
from faq_bot_v5 import cargar_faqs, crear_estado_conversacion, procesar_mensaje, obtener_opener
from db import create_test_session, save_message_turn, save_feedback


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
        "turn_counter": 0
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

    if "mostrar_debug" not in st.session_state:
        st.session_state.mostrar_debug = True

    if "tester_name" not in st.session_state:
        st.session_state.tester_name = ""

    if "db_session_id" not in st.session_state:
        st.session_state.db_session_id = None

    if "turn_number_global" not in st.session_state:
        st.session_state.turn_number_global = 0

    if not st.session_state.chats:
        chat_id, chat_data = crear_chat(nombre="user_001", plataforma="test")
        st.session_state.chats[chat_id] = chat_data
        st.session_state.chat_activo = chat_id

    if st.session_state.chat_activo not in st.session_state.chats:
        st.session_state.chat_activo = list(st.session_state.chats.keys())[0]


inicializar_estado_app()
if "suggested_oppener" not in st.session_state:
    st.session_state.suggested_oppener = ""

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

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Reset chat", use_container_width=True):
            reiniciar_chat_activo()
            st.rerun()

    with col2:
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

st.subheader(f"Active chat: {chat_activo['nombre']} [{chat_activo['plataforma']}]")

st.markdown("### Suggested openers")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("Soft opener", use_container_width=True):
        st.session_state.suggested_opener = obtener_opener("opener_soft", st.session_state.faq_data) or ""

with col2:
    if st.button("Flirty opener", use_container_width=True):
        st.session_state.suggested_opener = obtener_opener("opener_flirty", st.session_state.faq_data) or ""

with col3:
    if st.button("Upsell opener", use_container_width=True):
        st.session_state.suggested_opener = obtener_opener("opener_upsell", st.session_state.faq_data) or ""

if st.session_state.suggested_opener:
    st.info(st.session_state.suggested_opener)

for i, mensaje in enumerate(chat_activo["historial"][-40:]):
    with st.chat_message(mensaje["role"]):
        st.markdown(mensaje["content"])

        if mensaje["role"] == "assistant":
            turn_number = mensaje.get("turn_number", 0)
            unique_id = f"{chat_activo['nombre']}_{turn_number}_{i}"

            if not mensaje.get("feedback_saved", False):
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
                        session_id=st.session_state.db_session_id,
                        turn_number=turn_number,
                        rating=rating,
                        comment=comment
                    )
                    mensaje["feedback_saved"] = True
                    mensaje["feedback_comment"] = comment
                    mensaje["feedback_rating"] = rating
                    st.success("Feedback saved")
                    st.rerun()
            else:
                st.caption(f"Saved feedback: {mensaje.get('feedback_rating', '-')}")
                if mensaje.get("feedback_comment"):
                    st.caption(f"Comment: {mensaje['feedback_comment']}")


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
    if st.session_state.db_session_id is None:
        st.session_state.db_session_id = create_test_session(
            tester_name=st.session_state.tester_name or "anonymous",
            platform=chat_activo["plataforma"]
        )

    chat_activo["turn_counter"] += 1
    turn_id = chat_activo["turn_counter"]

    # Save user message in UI
    chat_activo["historial"].append({
        "role": "user",
        "content": texto_usuario,
        "turn_id": turn_id
    })

    # Process with this chat's state
    resultado = procesar_mensaje(
        texto_usuario,
        st.session_state.faq_data,
        chat_activo["estado_bot"]
    )

    # Save turn in DB
    st.session_state.turn_number_global += 1
    current_turn_number = st.session_state.turn_number_global

    save_message_turn(
        session_id=st.session_state.db_session_id,
        turn_number=current_turn_number,
        user_message=texto_usuario,
        bot_messages=resultado["mensajes_respuesta"],
        idioma=resultado["idioma"],
        categorias_detectadas=resultado["categorias_detectadas"],
        categorias_respondibles=resultado["categorias_respondibles"]
    )

    chat_activo["ultimo_resultado"] = resultado

    # Save bot replies in UI
    for respuesta in resultado["mensajes_respuesta"]:
        chat_activo["historial"].append({
            "role": "assistant",
            "content": respuesta,
            "turn_number": current_turn_number,
            "feedback_saved": False,
            "feedback_comment": "",
            "feedback_rating": ""
        })

    st.rerun()
