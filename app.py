import streamlit as st
import csv
import os
from datetime import datetime
from faq_bot_v5 import cargar_faqs, crear_estado_conversacion, procesar_mensaje

st.set_page_config(
    page_title="Simulador FAQ Bot Multi-Chat",
    layout="wide"
)

st.title("Internal bot simulator")
st.caption("Local testing/ simple questions")


# ----------------------------
# Helpers de chats
# ----------------------------
def crear_chat(nombre=None, plataforma="prueba"):
    chat_id = f"chat_{st.session_state.next_chat_id:03d}"
    st.session_state.next_chat_id += 1

    if nombre is None:
        nombre = f"usuario_{chat_id.split('_')[-1]}"

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
    chat_id = st.session_state.chat_activo
    return st.session_state.chats[chat_id]


def reiniciar_chat_activo():
    chat = obtener_chat_activo()
    chat["historial"] = []
    chat["estado_bot"] = crear_estado_conversacion()
    chat["ultimo_resultado"] = None
    chat["score"] = 0
    chat["etiquetas"] = []
    chat ["turn_counter"] = 0


def eliminar_chat_activo():
    chat_id = st.session_state.chat_activo
    if len(st.session_state.chats) <= 1:
        st.warning("Debe quedar al menos un chat.")
        return

    del st.session_state.chats[chat_id]
    st.session_state.chat_activo = list(st.session_state.chats.keys())[0]


def recargar_faqs():
    st.session_state.faq_data = cargar_faqs()

FEEDBACK_FILE = "feedback_log.csv"


def inicializar_feedback_file():
    if not os.path.exists(FEEDBACK_FILE):
        with open(FEEDBACK_FILE, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "timestamp",
                    "chat_name",
                    "platform",
                    "turn_id",
                    "user_message",
                    "bot_message",
                    "rating",
                    "comment",
                    "idioma",
                    "categorias_detectadas",
                    "categorias_respondibles"
                ],
                delimiter=";",
                quoting=csv.QUOTE_ALL
            )
            writer.writeheader()


def guardar_feedback_csv(chat_data, assistant_message, rating, comment):
    with open(FEEDBACK_FILE, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "timestamp",
                "chat_name",
                "platform",
                "turn_id",
                "user_message",
                "bot_message",
                "rating",
                "comment",
                "idioma",
                "categorias_detectadas",
                "categorias_respondibles"
            ],
            delimiter=";",
            quoting=csv.QUOTE_ALL
        )

        writer.writerow({
            "timestamp": datetime.now().isoformat(),
            "chat_name": chat_data["nombre"],
            "platform": chat_data["plataforma"],
            "turn_id": assistant_message.get("turn_id", ""),
            "user_message": assistant_message.get("user_message", ""),
            "bot_message": assistant_message.get("content", ""),
            "rating": rating,
            "comment": comment,
            "idioma": assistant_message.get("idioma", ""),
            "categorias_detectadas": str(assistant_message.get("categorias_detectadas", [])),
            "categorias_respondibles": str(assistant_message.get("categorias_respondibles", []))
        })
# ----------------------------
# Inicialización global app
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

    # Crear primer chat si no existe ninguno
    if not st.session_state.chats:
        chat_id, chat_data = crear_chat(nombre="usuario_001", plataforma="prueba")
        st.session_state.chats[chat_id] = chat_data
        st.session_state.chat_activo = chat_id

    # Blindaje por si el chat activo desaparece
    if st.session_state.chat_activo not in st.session_state.chats:
        st.session_state.chat_activo = list(st.session_state.chats.keys())[0]

inicializar_feedback_file()
inicializar_estado_app()


# ----------------------------
# Sidebar: gestión de chats
# ----------------------------
with st.sidebar:
    st.subheader("Chats")

    # Crear nuevo chat
    with st.expander("Nuevo chat", expanded=False):
        nuevo_nombre = st.text_input("Nombre del nuevo chat", value="")
        nueva_plataforma = st.selectbox(
            "Plataforma",
            options=["prueba", "telegram", "onlyfans"],
            index=0,
            key="select_nueva_plataforma"
        )

        if st.button("Crear chat", use_container_width=True):
            nombre_final = nuevo_nombre.strip() if nuevo_nombre.strip() else None
            chat_id, chat_data = crear_chat(
                nombre=nombre_final,
                plataforma=nueva_plataforma
            )
            st.session_state.chats[chat_id] = chat_data
            st.session_state.chat_activo = chat_id
            st.rerun()

    # Selector de chat activo
    opciones_chat = []
    mapa_labels = {}

    for cid, cdata in st.session_state.chats.items():
        label = f"{cdata['nombre']} [{cdata['plataforma']}]"
        opciones_chat.append(cid)
        mapa_labels[cid] = label

    chat_seleccionado = st.radio(
        "Selecciona chat",
        options=opciones_chat,
        index=opciones_chat.index(st.session_state.chat_activo),
        format_func=lambda cid: mapa_labels[cid]
    )

    if chat_seleccionado != st.session_state.chat_activo:
        st.session_state.chat_activo = chat_seleccionado
        st.rerun()

    st.divider()

    chat_activo = obtener_chat_activo()

    st.subheader("Editar chat activo")

    nuevo_nombre_chat = st.text_input(
        "Nombre visible",
        value=chat_activo["nombre"],
        key="input_nombre_chat_activo"
    )

    nueva_plataforma_chat = st.selectbox(
        "Plataforma del chat",
        options=["prueba", "telegram", "onlyfans"],
        index=["prueba", "telegram", "onlyfans"].index(chat_activo["plataforma"]),
        key="select_plataforma_chat_activo"
    )

    if st.button("Guardar cambios chat", use_container_width=True):
        chat_activo["nombre"] = nuevo_nombre_chat.strip() if nuevo_nombre_chat.strip() else chat_activo["nombre"]
        chat_activo["plataforma"] = nueva_plataforma_chat
        st.success("Chat actualizado")
        st.rerun()

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Reiniciar chat", use_container_width=True):
            reiniciar_chat_activo()
            st.rerun()

    with col2:
        if st.button("Eliminar chat", use_container_width=True):
            eliminar_chat_activo()
            st.rerun()

    st.divider()

    if st.button("Recargar FAQs", use_container_width=True):
        recargar_faqs()
        st.success("FAQs recargadas")

    st.session_state.mostrar_debug = st.checkbox(
        "Mostrar debug técnico",
        value=st.session_state.mostrar_debug
    )

    st.divider()
    st.subheader("Resumen chat activo")
    st.write(f"**Nombre:** {chat_activo['nombre']}")
    st.write(f"**Plataforma:** {chat_activo['plataforma']}")
    st.write(f"**Score:** {chat_activo['score']}")
    st.write(f"**Etiquetas:** {', '.join(chat_activo['etiquetas']) if chat_activo['etiquetas'] else '-'}")

    if st.session_state.mostrar_debug:
        st.divider()
        st.subheader("Estado interno del bot")
        st.json(chat_activo["estado_bot"])

        if chat_activo["ultimo_resultado"] is not None:
            resultado = chat_activo["ultimo_resultado"]

            st.divider()
            st.subheader("Último análisis")
            st.write(f"**Idioma detectado:** `{resultado['idioma']}`")

            st.write("**Categorías detectadas:**")
            if resultado["categorias_detectadas"]:
                for item in resultado["categorias_detectadas"]:
                    if "puntuacion" in item and "confianza" in item:
                        st.write(
                            f"- {item['categoria']} | puntuación={item['puntuacion']} | confianza={item['confianza']}"
                        )
                    else:
                        st.write(f"- {item['categoria']}")
            else:
                st.write("- Ninguna")

            st.write("**Categorías respondibles:**")
            if resultado["categorias_respondibles"]:
                for item in resultado["categorias_respondibles"]:
                    if "puntuacion" in item and "confianza" in item:
                        st.write(
                            f"- {item['categoria']} | puntuación={item['puntuacion']} | confianza={item['confianza']}"
                        )
                    else:
                        st.write(f"- {item['categoria']}")
            else:
                st.write("- Ninguna")

            st.write("**Mensajes generados:**")
            for i, msg in enumerate(resultado["mensajes_respuesta"], start=1):
                st.write(f"{i}. {msg}")


# ----------------------------
# Zona principal
# ----------------------------
chat_activo = obtener_chat_activo()

st.subheader(f"Chat activo: {chat_activo['nombre']} [{chat_activo['plataforma']}]")

# Mostrar solo últimos mensajes para no cargar demasiado
for i, mensaje in enumerate(chat_activo["historial"][-40:]):
    with st.chat_message(mensaje["role"]):
        st.markdown(mensaje["content"])

        if mensaje["role"] == "assistant":
            turn_id = mensaje.get("turn_id", f"no_turn_{i}")

            if mensaje.get("feedback") is None:
                rating_key = f"rating_{chat_activo['nombre']}_{turn_id}"
                comment_key = f"comment_{chat_activo['nombre']}_{turn_id}"
                save_key = f"save_{chat_activo['nombre']}_{turn_id}"

                rating = st.radio(
                    "Rate this reply",
                    options=["Good", "Regular", "Bad"],
                    horizontal=True,
                    key=rating_key
                )

                comment = st.text_input(
                    "Optional comment",
                    placeholder="What sounds good or bad here?",
                    key=comment_key
                )

                if st.button("Save feedback", key=save_key):
                    mensaje["feedback"] = rating
                    mensaje["feedback_comment"] = comment
                    guardar_feedback_csv(chat_activo, mensaje, rating, comment)
                    st.success("Feedback saved")
                    st.rerun()
            else:
                st.caption(f"Saved feedback: {mensaje['feedback']}")
                if mensaje.get("feedback_comment"):
                    st.caption(f"Comment: {mensaje['feedback_comment']}")


# ----------------------------
# Input de chat
# ----------------------------
texto_usuario = st.chat_input(
    f"Escribe como {chat_activo['nombre']}..."
)


# ----------------------------
# Procesamiento
# ----------------------------
if texto_usuario and texto_usuario.strip():
    chat_activo["turn_counter"] += 1
    turn_id = chat_activo["turn_counter"]

    # Save user message
    chat_activo["historial"].append({
        "role": "user",
        "content": texto_usuario,
        "turn_id": turn_id
    })

    # Process using this chat's own bot state
    resultado = procesar_mensaje(
        texto_usuario,
        st.session_state.faq_data,
        chat_activo["estado_bot"]
    )

    chat_activo["ultimo_resultado"] = resultado

    # Save bot reply as a single grouped message
    chat_activo["historial"].append({
        "role": "assistant",
        "content": "\n\n".join(resultado["mensajes_respuesta"]),
        "turn_id": turn_id,
        "feedback": None,
        "feedback_comment": "",
        "user_message": texto_usuario,
        "idioma": resultado["idioma"],
        "categorias_detectadas": resultado["categorias_detectadas"],
        "categorias_respondibles": resultado["categorias_respondibles"]
    })

    st.rerun()

    st.rerun()
