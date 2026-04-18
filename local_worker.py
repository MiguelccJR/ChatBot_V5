import time
import json
from datetime import datetime

from db import (
    get_pending_ai_messages,
    get_chat_messages,
    create_chat_message,
    update_chat_message_status,
    get_pending_opener_requests,
    update_opener_request,
)
from local_ai import (
    generar_respuesta_ia_local,
    generar_opener_ia_local,
    detectar_intencion_ia_local,
    responder_enlace_o_red,
)

POLL_SECONDS = 1.5
BURST_WINDOW_SECONDS = 12
MAX_GROUP_MESSAGES = 4
HISTORY_LIMIT = 7


def parse_dt(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def normalizar_categorias_detectadas(valor):
    if not valor:
        return []

    if isinstance(valor, list):
        return valor

    if isinstance(valor, str):
        try:
            data = json.loads(valor)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    return []


def session_esta_en_handoff(session_id: str) -> tuple[bool, str]:
    mensajes = get_chat_messages(session_id)

    for m in reversed(mensajes):
        if m.get("role") != "assistant":
            continue

        categorias = normalizar_categorias_detectadas(m.get("categorias_detectadas"))

        for cat in categorias:
            if not isinstance(cat, dict):
                continue

            if cat.get("handoff_recommended") is True:
                reason = str(cat.get("handoff_reason", "") or "")
                return True, reason

    return False, ""


def mover_grupo_a_espera_humana(grupo, reason: str = ""):
    motivo = reason or "Waiting for human reply"

    for msg in grupo:
        update_chat_message_status(
            msg["id"],
            "waiting_human",
            error_text=motivo
        )

    ids = [m["id"] for m in grupo]
    print(f"[HANDOFF] Group {ids} moved to waiting_human | reason={motivo}")


def construir_historial_corto(session_id: str, hasta_message_id: int | None = None, limite: int = 6):
    mensajes = get_chat_messages(session_id)

    if hasta_message_id is not None:
        mensajes = [m for m in mensajes if int(m.get("id", 0)) < int(hasta_message_id)]

    historial = []
    for m in mensajes:
        role = m.get("role", "user")
        content = (m.get("content") or "").strip()

        if not content:
            continue

        historial.append(f"{role}: {content}")

    return historial[-limite:]


def agrupar_mensajes(lista_pendientes):
    grupos = []
    i = 0

    while i < len(lista_pendientes):
        actual = lista_pendientes[i]
        grupo = [actual]

        j = i + 1
        while j < len(lista_pendientes) and len(grupo) < MAX_GROUP_MESSAGES:
            candidato = lista_pendientes[j]

            if candidato.get("session_id") != actual.get("session_id"):
                break

            t1 = parse_dt(grupo[-1].get("created_at"))
            t2 = parse_dt(candidato.get("created_at"))

            if not t1 or not t2:
                break

            delta = (t2 - t1).total_seconds()

            if delta <= BURST_WINDOW_SECONDS:
                grupo.append(candidato)
                j += 1
            else:
                break

        grupos.append(grupo)
        i += len(grupo)

    return grupos


def procesar_mensaje_o_grupo(grupo):
    first_msg = grupo[0]
    last_msg = grupo[-1]

    first_message_id = first_msg["id"]
    last_message_id = last_msg["id"]
    session_id = first_msg["session_id"]
    turn_number = last_msg.get("turn_number", 0)

    # Si el chat ya está en handoff, no seguimos con IA
    en_handoff, reason = session_esta_en_handoff(session_id)
    if en_handoff:
        mover_grupo_a_espera_humana(grupo, reason)
        return

    for msg in grupo:
        update_chat_message_status(msg["id"], "processing")

    try:
        historial_corto = construir_historial_corto(
            session_id=session_id,
            hasta_message_id=first_message_id,
            limite=HISTORY_LIMIT
        )

        textos = [(m.get("content") or "").strip() for m in grupo]
        textos = [t for t in textos if t]

        if not textos:
            raise ValueError("Empty user message group")

        if len(textos) == 1:
            contenido_para_ia = textos[0]
        else:
            contenido_para_ia = (
                "The customer sent several quick messages. "
                "Reply with one natural message. "
                "Answer the main question first, and briefly acknowledge the follow-up.\n\n"
                + "\n".join(f"- {t}" for t in textos)
            )

        print(f"[DEBUG] Input for AI: {repr(contenido_para_ia)}")
        print(f"[DEBUG] History used: {historial_corto}")

        deteccion = detectar_intencion_ia_local(
            mensaje_cliente=contenido_para_ia,
            historial_corto=historial_corto,
        )

        intent_principal = deteccion.get("primary_intent", "normal_chat")
        confianza = deteccion.get("confidence", 0.0)
        handoff_recommended = deteccion.get("handoff_recommended", False)
        handoff_reason = deteccion.get("handoff_reason", "")

        print(f"[DEBUG] Intent detected: {intent_principal} | confidence={confianza}")
        print(f"[DEBUG] Handoff suggested: {handoff_recommended} | reason={handoff_reason}")

        if intent_principal == "social_link_request":
            respuesta = responder_enlace_o_red(contenido_para_ia)
        else:
            respuesta = generar_respuesta_ia_local(
                mensaje_cliente=contenido_para_ia,
                historial_corto=historial_corto,
                intenciones=[intent_principal],
                estado_cliente="chatting"
            )

        print(f"[DEBUG] Raw final reply: {repr(respuesta)}")

        if not respuesta or not respuesta.strip():
            raise ValueError("Empty response from local AI")

        create_chat_message(
            session_id=session_id,
            turn_number=turn_number,
            role="assistant",
            content=respuesta.strip(),
            status="done",
            source="local_ai",
            reply_to_message_id=last_message_id,
            idioma="en",
            categorias_detectadas=[{
                "categoria": intent_principal,
                "confianza": confianza,
                "handoff_recommended": handoff_recommended,
                "handoff_reason": handoff_reason,
            }],
            categorias_respondibles=[{
                "categoria": intent_principal,
                "confianza": confianza,
            }]
        )

        for msg in grupo:
            update_chat_message_status(msg["id"], "done")

        if handoff_recommended:
            print(f"[HANDOFF] Session {session_id} marked for human after this reply | reason={handoff_reason}")

        if len(grupo) == 1:
            print(f"[OK] Replied to message {first_message_id}")
        else:
            ids = [m["id"] for m in grupo]
            print(f"[OK] Replied to grouped messages {ids}")

    except Exception as e:
        for msg in grupo:
            update_chat_message_status(msg["id"], "error", error_text=str(e))

        if len(grupo) == 1:
            print(f"[ERROR] Message {first_message_id}: {e}")
        else:
            ids = [m["id"] for m in grupo]
            print(f"[ERROR] Group {ids}: {e}")


def procesar_opener_pendiente(item):
    opener_id = item["id"]
    session_id = item["session_id"]
    opener_type = item["opener_type"]

    en_handoff, reason = session_esta_en_handoff(session_id)
    if en_handoff:
        update_opener_request(
            opener_id,
            "waiting_human",
            error_text=reason or "Chat is waiting for human"
        )
        print(f"[HANDOFF] Opener {opener_id} skipped because session is in human handoff")
        return

    update_opener_request(opener_id, "processing")

    try:
        historial_corto = construir_historial_corto(session_id, limite=6)

        print(f"[DEBUG] Generating opener: id={opener_id}, type={opener_type}")

        sugerencia = generar_opener_ia_local(
            historial_corto=historial_corto,
            opener_type=opener_type,
            estado_cliente="chatting"
        )

        print(f"[DEBUG] Raw opener result ({opener_type}): {repr(sugerencia)}")

        if not sugerencia or not sugerencia.strip():
            raise ValueError(f"Empty opener from local AI for opener_type={opener_type}")

        update_opener_request(
            opener_id,
            "done",
            suggestion_text=sugerencia.strip()
        )

        print(f"[OK] Generated {opener_type} opener {opener_id}")

    except Exception as e:
        update_opener_request(
            opener_id,
            "error",
            error_text=str(e)
        )
        print(f"[ERROR] Opener {opener_id}: {e}")


def main():
    print("Local worker started. Waiting for pending items...")

    while True:
        try:
            pendientes_openers = get_pending_opener_requests(limit=5)
            if pendientes_openers:
                for item in pendientes_openers:
                    procesar_opener_pendiente(item)

            pendientes = get_pending_ai_messages(limit=20)
            if pendientes:
                grupos = agrupar_mensajes(pendientes)
                for grupo in grupos:
                    procesar_mensaje_o_grupo(grupo)

            time.sleep(POLL_SECONDS)

        except KeyboardInterrupt:
            print("Worker stopped by user.")
            break
        except Exception as e:
            print(f"[LOOP ERROR] {e}")
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()