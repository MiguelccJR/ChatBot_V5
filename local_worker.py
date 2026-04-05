import time
from db import (
    get_pending_ai_messages,
    get_chat_messages,
    create_chat_message,
    update_chat_message_status,
)
from local_ai import generar_respuesta_ia_local


POLL_SECONDS = 1.5


def construir_historial_corto(session_id: str, limite: int = 6):
    mensajes = get_chat_messages(session_id)

    historial = []
    for m in mensajes[-limite:]:
        role = m.get("role", "user")
        content = m.get("content", "")
        historial.append(f"{role}: {content}")

    return historial


def procesar_mensaje_pendiente(mensaje):
    message_id = mensaje["id"]
    session_id = mensaje["session_id"]
    turn_number = mensaje.get("turn_number", 0)
    content = mensaje["content"]

    # Marcar como procesando
    update_chat_message_status(message_id, "processing")

    try:
        historial_corto = construir_historial_corto(session_id, limite=6)

        respuesta = generar_respuesta_ia_local(
            mensaje_cliente=content,
            historial_corto=historial_corto,
            intenciones=[],
            estado_cliente="chatting"
        )

        if not respuesta:
            raise ValueError("Empty response from local AI")

        # Guardar mensaje del assistant
        create_chat_message(
            session_id=session_id,
            turn_number=turn_number,
            role="assistant",
            content=respuesta,
            status="done",
            source="local_ai",
            reply_to_message_id=message_id,
            idioma="en",
            categorias_detectadas=[],
            categorias_respondibles=[]
        )

        # Marcar mensaje user como resuelto
        update_chat_message_status(message_id, "done")

        print(f"[OK] Replied to message {message_id}")

    except Exception as e:
        update_chat_message_status(message_id, "error", error_text=str(e))
        print(f"[ERROR] Message {message_id}: {e}")


def main():
    print("Local worker started. Waiting for pending_ai messages...")

    while True:
        try:
            pendientes = get_pending_ai_messages(limit=5)

            if pendientes:
                for mensaje in pendientes:
                    procesar_mensaje_pendiente(mensaje)

            time.sleep(POLL_SECONDS)

        except KeyboardInterrupt:
            print("Worker stopped by user.")
            break
        except Exception as e:
            print(f"[LOOP ERROR] {e}")
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()