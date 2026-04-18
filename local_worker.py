import time
from datetime import datetime

from db import (
    get_pending_ai_messages,
    get_chat_messages,
    create_chat_message,
    update_chat_message_status,
    get_pending_opener_requests,
    update_opener_request,
    get_session_control_state,
    set_session_control_mode,
    get_bot_config_dict,
)
from local_ai import (
    generar_respuesta_ia_local,
    generar_opener_ia_local,
    detectar_intencion_ia_local,
    responder_enlace_o_red,
    generar_respuesta_catalogo,
)

POLL_SECONDS = 1.5
BURST_WINDOW_SECONDS = 12
MAX_GROUP_MESSAGES = 4
HISTORY_LIMIT = 7

# Config cache: reload every 60 seconds to avoid hitting Supabase on every message
_config_cache = {}
_config_last_loaded = 0
CONFIG_TTL_SECONDS = 60


def get_config_cached() -> dict:
    global _config_cache, _config_last_loaded
    now = time.time()
    if now - _config_last_loaded > CONFIG_TTL_SECONDS:
        try:
            _config_cache = get_bot_config_dict()
            _config_last_loaded = now
            print("[CONFIG] Reloaded bot config from Supabase")
        except Exception as e:
            print(f"[CONFIG ERROR] Could not load bot config: {e}")
    return _config_cache


def parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def session_esta_en_handoff(session_id: str) -> tuple[bool, str]:
    state = get_session_control_state(session_id)
    control_mode = state.get("control_mode", "bot")
    handoff_reason = state.get("handoff_reason", "") or ""
    return control_mode == "human", handoff_reason


def mover_grupo_a_espera_humana(grupo, reason: str = ""):
    motivo = reason or "Waiting for human reply"
    for msg in grupo:
        update_chat_message_status(msg["id"], "waiting_human", error_text=motivo)
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
            if (t2 - t1).total_seconds() <= BURST_WINDOW_SECONDS:
                grupo.append(candidato)
                j += 1
            else:
                break

        grupos.append(grupo)
        i += len(grupo)

    return grupos


def construir_precios_texto(config: dict) -> str:
    """Builds a readable price list from config for the AI system prompt."""
    lineas = []
    for key, value in config.items():
        if key.startswith("price_") or key.startswith("pack_") or key.startswith("video_") or key.startswith("custom_"):
            if value:
                desc = key.replace("_", " ").title()
                lineas.append(f"- {desc}: {value}")
            else:
                desc = key.replace("_", " ").title()
                lineas.append(f"- {desc}: price on request (escalate to human)")
    return "\n".join(lineas) if lineas else ""


def cliente_pregunta_catalogo(mensaje: str) -> bool:
    """Detects if the customer is asking what is available."""
    t = mensaje.lower()
    keywords = [
        "what do you have", "what do you offer", "what can i get",
        "what's available", "what is available", "show me what",
        "what kind of content", "what content do you", "what do you sell",
        "menu", "price list", "what do you do", "options", "packages",
        "what can i buy", "what can i order", "what packs",
        "tell me what you have", "what are your",
    ]
    return any(kw in t for kw in keywords)


def procesar_mensaje_o_grupo(grupo):
    first_msg = grupo[0]
    last_msg = grupo[-1]

    first_message_id = first_msg["id"]
    last_message_id = last_msg["id"]
    session_id = first_msg["session_id"]
    turn_number = last_msg.get("turn_number", 0)

    en_handoff, reason = session_esta_en_handoff(session_id)
    if en_handoff:
        mover_grupo_a_espera_humana(grupo, reason)
        return

    for msg in grupo:
        update_chat_message_status(msg["id"], "processing")

    try:
        config = get_config_cached()
        precios_texto = construir_precios_texto(config)
        handoff_message = config.get("handoff_message", "Give me just a sec, let me check that for you 😊")

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

        # Check if price is unknown for a specific request
        if intent_principal in ("price_interest", "custom_request", "specific_content_request"):
            precio_desconocido = detectar_precio_desconocido(contenido_para_ia, config)
            if precio_desconocido:
                handoff_recommended = True
                handoff_reason = f"Price unknown for: {precio_desconocido}"
                print(f"[HANDOFF] Unknown price detected: {precio_desconocido}")

        if intent_principal == "social_link_request":
            respuesta = responder_enlace_o_red(contenido_para_ia, config)
        elif handoff_recommended:
            # Send bridge message before handing off
            respuesta = handoff_message
        elif cliente_pregunta_catalogo(contenido_para_ia):
            respuesta = generar_respuesta_catalogo(precios_texto)
        else:
            respuesta = generar_respuesta_ia_local(
                mensaje_cliente=contenido_para_ia,
                historial_corto=historial_corto,
                intenciones=[intent_principal],
                estado_cliente="chatting",
                precios_texto=precios_texto,
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
            set_session_control_mode(
                session_id=session_id,
                control_mode="human",
                handoff_reason=handoff_reason or f"Handoff triggered by {intent_principal}",
            )
            print(f"[HANDOFF] Session {session_id} switched to HUMAN mode | reason={handoff_reason}")

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


def detectar_precio_desconocido(mensaje: str, config: dict) -> str | None:
    """
    Returns a description if the customer is asking about something
    whose price is null/unknown in config.
    """
    t = mensaje.lower()

    # Only check if the message seems price-related
    price_signals = ["how much", "price", "cost", "how many", "what does", "pay", "buy", "get"]
    if not any(s in t for s in price_signals):
        return None

    # Check config for null-value price entries
    for key, value in config.items():
        if not (key.startswith("price_") or key.startswith("pack_") or
                key.startswith("video_") or key.startswith("custom_")):
            continue
        if value is None or value.strip() == "":
            # Check if message hints at this product
            key_words = key.replace("_", " ").lower().split()
            if any(w in t for w in key_words if len(w) > 3):
                return key.replace("_", " ")

    # If it's a custom request and no price found, always escalate
    if "custom" in t or "personali" in t or "special" in t or "specific" in t:
        return "custom content"

    return None


def procesar_opener_pendiente(item):
    opener_id = item["id"]
    session_id = item["session_id"]
    opener_type = item["opener_type"]

    en_handoff, reason = session_esta_en_handoff(session_id)
    if en_handoff:
        update_opener_request(opener_id, "waiting_human", error_text=reason or "Chat is waiting for human")
        print(f"[HANDOFF] Opener {opener_id} skipped because session is in HUMAN mode")
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

        update_opener_request(opener_id, "done", suggestion_text=sugerencia.strip())
        print(f"[OK] Generated {opener_type} opener {opener_id}")

    except Exception as e:
        update_opener_request(opener_id, "error", error_text=str(e))
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