import os
import asyncio
import random
import base64
from datetime import datetime, timezone
from dotenv import load_dotenv

from telethon import TelegramClient, events
from telethon.tl.types import User

load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
PHONE = os.getenv("TELEGRAM_PHONE", "")

SESSION_FILE = "telegram_session"

# ----------------------------
# Whisper audio transcription
# ----------------------------
def transcribir_audio_whisper(audio_bytes: bytes) -> str | None:
    """
    Transcribes audio using local Whisper model.
    Returns transcribed text or None if it fails.
    """
    import whisper

    tmp_path = None
    try:
        tmp_path = os.path.join(os.getcwd(), "_audio_tmp.ogg")
        with open(tmp_path, "wb") as f:
            f.write(audio_bytes)

        print(f"[WHISPER] Audio saved to {tmp_path} ({len(audio_bytes)} bytes)")

        model = whisper.load_model("base")
        result = model.transcribe(tmp_path, language=None)
        text = (result.get("text") or "").strip()
        print(f"[WHISPER] Transcription: {repr(text[:80])}")
        return text if text else None

    except Exception as e:
        print(f"[WHISPER ERROR] {e}")
        return None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


NON_TEXT_RESPONSES = [
    "Heyy, I can only read text messages for now 😊 What's on your mind?",
    "I can't open that right now 😅 Just text me what you need!",
    "Aww, I can't view that here 😊 Tell me in words?",
    "I'm text-only for now 😄 What did you want to say?",
    "Can't read that one! But I'm here — just text me 😘",
]

TYPING_DELAY_MIN = 2
TYPING_DELAY_MAX = 5
POLL_SEND_SECONDS = 2.0

# Keeps track of messages sent by THIS worker so outgoing handler
# does not treat them as manual owner replies.
BOT_SENT_MESSAGE_IDS: set[int] = set()


def get_supabase():
    from supabase import create_client
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY not found in .env")
    return create_client(url, key)


# ----------------------------
# Supabase helpers
# ----------------------------

def get_session_by_telegram_id(telegram_chat_id: str) -> dict | None:
    supabase = get_supabase()
    response = (
        supabase.table("test_sessions")
        .select("*")
        .eq("telegram_chat_id", str(telegram_chat_id))
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def register_new_chat(
    telegram_chat_id: str,
    username: str = "",
    first_name: str = "",
    *,
    is_archived: bool = False,
) -> str:
    """
    Registers a new chat with control_mode = 'disabled'.
    The bot will not respond until the owner activates it.
    """
    supabase = get_supabase()
    response = (
        supabase.table("test_sessions")
        .insert({
            "tester_name": username or first_name or f"tg_{telegram_chat_id}",
            "platform": "telegram",
            "control_mode": "disabled",
            "telegram_chat_id": str(telegram_chat_id),
            "telegram_username": username,
            "telegram_first_name": first_name,
            "active": True,
        })
        .execute()
    )
    print(f"[TELEGRAM] New chat registered: {telegram_chat_id} ({username or first_name}) — DISABLED")
    return response.data[0]["id"]


def save_incoming_message(
    session_id: str,
    text: str,
    turn_number: int,
    *,
    status: str = "pending_ai",
    error_text: str | None = None,
):
    supabase = get_supabase()
    supabase.table("chat_messages").insert({
        "session_id": session_id,
        "turn_number": turn_number,
        "role": "user",
        "content": text,
        "status": status,
        "source": "telegram",
        "idioma": "en",
        "categorias_detectadas": [],
        "categorias_respondibles": [],
        "error_text": error_text,
    }).execute()


def save_incoming_message_with_image(
    session_id: str,
    text: str,
    turn_number: int,
    img_b64: str,
    *,
    status: str = "pending_ai",
    error_text: str | None = None,
):
    """Saves a message with an embedded image for vision processing."""
    supabase = get_supabase()
    supabase.table("chat_messages").insert({
        "session_id": session_id,
        "turn_number": turn_number,
        "role": "user",
        "content": text,
        "status": status,
        "source": "telegram",
        "idioma": "en",
        "categorias_detectadas": [{"image_b64": img_b64}],
        "categorias_respondibles": [],
        "error_text": error_text,
    }).execute()


def save_manual_reply(session_id: str, text: str, turn_number: int):
    supabase = get_supabase()
    supabase.table("chat_messages").insert({
        "session_id": session_id,
        "turn_number": turn_number,
        "role": "assistant",
        "content": text,
        "status": "done",
        "source": "human",
        "sent_to_telegram": True,
        "idioma": "en",
        "categorias_detectadas": [],
        "categorias_respondibles": [],
    }).execute()


def get_next_turn_number(session_id: str) -> int:
    supabase = get_supabase()
    response = (
        supabase.table("chat_messages")
        .select("turn_number")
        .eq("session_id", session_id)
        .order("turn_number", desc=True)
        .limit(1)
        .execute()
    )
    if response.data:
        return (response.data[0]["turn_number"] or 0) + 1
    return 1


def set_human_mode(session_id: str, reason: str = "Owner replied manually"):
    supabase = get_supabase()
    supabase.table("test_sessions").update({
        "control_mode": "human",
        "handoff_reason": reason,
        "handoff_since": datetime.now(timezone.utc).isoformat(),
    }).eq("id", session_id).execute()


def get_pending_replies_to_send() -> list:
    supabase = get_supabase()
    response = (
        supabase.table("chat_messages")
        .select("*, test_sessions(telegram_chat_id, control_mode)")
        .eq("role", "assistant")
        .eq("status", "done")
        .eq("sent_to_telegram", False)
        .in_("source", ["local_ai", "human", "streamlit"])
        .order("created_at")
        .limit(20)
        .execute()
    )
    return response.data or []


def mark_message_sent(message_id: int):
    supabase = get_supabase()
    supabase.table("chat_messages").update(
        {"sent_to_telegram": True}
    ).eq("id", message_id).execute()


def get_owner_telegram_id() -> str | None:
    supabase = get_supabase()
    response = (
        supabase.table("bot_config")
        .select("value")
        .eq("key", "owner_telegram_id")
        .eq("active", True)
        .limit(1)
        .execute()
    )
    return response.data[0].get("value") if response.data else None

def get_pending_history_import_requests(limit: int = 5):
    supabase = get_supabase()
    response = (
        supabase.table("telegram_history_import_requests")
        .select("*")
        .eq("status", "pending")
        .order("created_at")
        .limit(limit)
        .execute()
    )
    return response.data or []


def update_history_import_request(request_id: int, status: str, error_text: str | None = None):
    supabase = get_supabase()

    payload = {
        "status": status,
        "error_text": error_text,
    }

    if status in ("done", "error"):
        payload["processed_at"] = datetime.now(timezone.utc).isoformat()

    response = (
        supabase.table("telegram_history_import_requests")
        .update(payload)
        .eq("id", request_id)
        .execute()
    )
    return response.data

def get_oldest_imported_telegram_message_id(session_id: str):
        supabase = get_supabase()
        response = (
            supabase.table("chat_messages")
            .select("telegram_message_id")
            .eq("session_id", session_id)
            .not_.is_("telegram_message_id", "null")
            .order("telegram_message_id", desc=False)
            .limit(1)
            .execute()
        )
        if response.data:
            return response.data[0].get("telegram_message_id")
        return None

def save_imported_message(
    session_id: str,
    telegram_message_id: int,
    role: str,
    content: str,
    turn_number: int,
):
    supabase = get_supabase()

    payload = {
        "session_id": session_id,
        "telegram_message_id": telegram_message_id,
        "turn_number": turn_number,
        "role": role,
        "content": content,
        "status": "done" if role == "assistant" else "waiting_human",
        "source": "human" if role == "assistant" else "telegram",
        "idioma": "en",
        "categorias_detectadas": [],
        "categorias_respondibles": [],
        "sent_to_telegram": True if role == "assistant" else False,
    }

    try:
        supabase.table("chat_messages").insert(payload).execute()
        return True
    except Exception as e:
        print(f"[HISTORY IMPORT] Skipped duplicated message {telegram_message_id}: {e}")
        return False

def get_test_session_by_id(session_id: str):
    supabase = get_supabase()
    response = (
        supabase.table("test_sessions")
        .select("*")
        .eq("id", session_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None

# ----------------------------
# Archived chats sync
# ----------------------------

async def main():
    print(f"[TELEGRAM] Starting worker for {PHONE}")

    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
    await client.start(phone=PHONE)

    me = await client.get_me()
    print(f"[TELEGRAM] Logged in as {me.first_name} (id={me.id})")

    # ----------------------------
    # Incoming messages from customers
    # ----------------------------
    @client.on(events.NewMessage(incoming=True))
    async def handle_incoming(event):
        if not event.is_private:
            return

        sender = await event.get_sender()
        if not isinstance(sender, User):
            return

        chat_id = str(event.chat_id)
        text = (event.message.text or "").strip()
        has_media = bool(event.message.media)

        session = get_session_by_telegram_id(chat_id)

        # New chat — register as disabled, do nothing else
        if not session:
            username = getattr(sender, "username", "") or ""
            first_name = getattr(sender, "first_name", "") or ""
            register_new_chat(chat_id, username, first_name)
            return

        # If an archived chat writes again, optionally keep it archived.
        # For now we do not change is_archived automatically.

        # Disabled — save for monitoring but do not process with AI
        if session.get("control_mode", "disabled") == "disabled":
            preview = repr(text[:80]) if text else "[media]"
            print(f"[MONITOR] Disabled chat {chat_id}: {preview}")

            turn_number = get_next_turn_number(session["id"])

            if has_media and not text:
                save_incoming_message(
                    session["id"],
                    "[Disabled chat media message]",
                    turn_number,
                    status="waiting_human",
                    error_text="Disabled chat monitored only",
                )
            else:
                save_incoming_message(
                    session["id"],
                    text or "[Empty message]",
                    turn_number,
                    status="waiting_human",
                    error_text="Disabled chat monitored only",
                )
            return

        print(f"[TELEGRAM] Incoming from {chat_id}: {repr(text[:60]) if text else '[media]'}")

        control_mode = session.get("control_mode", "disabled")
        session_id = session["id"]

        # Human mode — save message but don't process with AI
        if control_mode == "human":
            if text:
                turn_number = get_next_turn_number(session_id)
                save_incoming_message(
                    session_id,
                    text,
                    turn_number,
                    status="waiting_human",
                    error_text="Waiting for human reply",
                )
            print(f"[TELEGRAM] Chat in HUMAN mode — saved, not processing")
            return

        # Handle media messages
        if has_media and not text:
            msg_media = event.message.media

            # --- Voice/audio message: transcribe with Whisper ---
            is_voice = hasattr(msg_media, 'document') and any(
                getattr(attr, '__class__.__name__', '') in ('DocumentAttributeAudio',)
                for attr in getattr(getattr(msg_media, 'document', None), 'attributes', [])
            )

            if not is_voice:
                is_voice = getattr(getattr(msg_media, 'document', None), 'mime_type', '') in (
                    'audio/ogg', 'audio/mpeg', 'audio/mp4', 'audio/m4a', 'audio/wav'
                )

            if is_voice:
                print(f"[TELEGRAM] Voice message from {chat_id} — transcribing with Whisper")
                try:
                    audio_bytes = await client.download_media(event.message, bytes)
                    transcription = transcribir_audio_whisper(audio_bytes)
                    if transcription:
                        text = f"[Voice message]: {transcription}"
                        turn_number = get_next_turn_number(session_id)
                        save_incoming_message(session_id, text, turn_number)
                        print(f"[TELEGRAM] Voice transcribed and saved | session={session_id}")
                        return
                    else:
                        print(f"[TELEGRAM] Whisper returned empty — sending fallback")
                        await client.send_message(
                            int(chat_id),
                            "Sorry, I couldn't hear that clearly 😅 Could you type it instead?"
                        )
                        return
                except Exception as e:
                    print(f"[TELEGRAM] Audio processing error: {e}")
                    await client.send_message(
                        int(chat_id),
                        "Sorry, I couldn't hear that clearly 😅 Could you type it instead?"
                    )
                    return

            # --- Photo: try to send to vision AI ---
            is_photo = hasattr(msg_media, 'photo') or (
                hasattr(msg_media, 'document') and
                any('image' in str(getattr(attr, 'mime_type', ''))
                    for attr in getattr(getattr(msg_media, 'document', None), 'attributes', []))
            )

            if is_photo:
                print(f"[TELEGRAM] Photo received from {chat_id} — attempting vision processing")
                try:
                    img_bytes = await client.download_media(event.message, bytes)
                    img_b64 = base64.b64encode(img_bytes).decode('utf-8')

                    turn_number = get_next_turn_number(session_id)
                    image_text = "[Image attached — base64 data available for vision model]"
                    save_incoming_message_with_image(session_id, image_text, turn_number, img_b64)
                    print(f"[TELEGRAM] Photo saved for vision processing | session={session_id}")
                    return
                except Exception as e:
                    print(f"[TELEGRAM] Could not process photo: {e} — sending fallback")

            # --- Fallback for unsupported media ---
            print(f"[TELEGRAM] Unsupported media from {chat_id} — sending friendly reply")
            delay = random.uniform(TYPING_DELAY_MIN, TYPING_DELAY_MAX)
            await asyncio.sleep(delay)
            async with client.action(int(chat_id), 'typing'):
                await asyncio.sleep(1.5)
            response = random.choice(NON_TEXT_RESPONSES)
            sent = await client.send_message(int(chat_id), response)
            BOT_SENT_MESSAGE_IDS.add(int(sent.id))
            return

        # Bot mode — save as pending_ai for local_worker
        if not text:
            return

        turn_number = get_next_turn_number(session_id)
        save_incoming_message(session_id, text, turn_number)
        print(f"[TELEGRAM] Saved as pending_ai | session={session_id}")

    # ----------------------------
    # Outgoing messages (owner replies from phone)
    # ----------------------------
    @client.on(events.NewMessage(outgoing=True))
    async def handle_outgoing(event):
        if not event.is_private:
            return

        # Ignore messages sent by this worker itself
        if int(event.message.id) in BOT_SENT_MESSAGE_IDS:
            BOT_SENT_MESSAGE_IDS.discard(int(event.message.id))
            return

        chat_id = str(event.chat_id)
        text = (event.message.text or "").strip()

        if not text:
            return

        session = get_session_by_telegram_id(chat_id)
        if not session:
            return

        session_id = session["id"]
        control_mode = session.get("control_mode", "disabled")

        # If bot was active and owner replied manually — switch to human mode
        if control_mode == "bot":
            set_human_mode(session_id, "Owner replied manually from Telegram")
            print(f"[TELEGRAM] Owner replied — session {session_id} → HUMAN mode")

        # Save manual reply to history
        turn_number = get_next_turn_number(session_id)
        save_manual_reply(session_id, text, turn_number)

    # ----------------------------
    # Poll: send pending AI/manual replies
    # ----------------------------
    async def send_pending_replies():
        while True:
            try:
                pending = get_pending_replies_to_send()
                for msg in pending:
                    session_data = msg.get("test_sessions") or {}
                    telegram_chat_id = session_data.get("telegram_chat_id")
                    control_mode = session_data.get("control_mode", "disabled")

                    if not telegram_chat_id:
                        mark_message_sent(msg["id"])
                        continue

                    # Don't send if session switched to human or disabled,
                    # unless the message source is human/streamlit and you want manual sends.
                    source = msg.get("source", "")
                    if control_mode in ("human", "disabled") and source == "local_ai":
                        mark_message_sent(msg["id"])
                        continue

                    try:
                        delay = random.uniform(TYPING_DELAY_MIN, TYPING_DELAY_MAX)
                        await asyncio.sleep(delay)
                        async with client.action(int(telegram_chat_id), 'typing'):
                            await asyncio.sleep(random.uniform(1.0, 2.0))

                        sent = await client.send_message(int(telegram_chat_id), msg["content"])
                        BOT_SENT_MESSAGE_IDS.add(int(sent.id))
                        mark_message_sent(msg["id"])
                        print(f"[TELEGRAM] Sent to {telegram_chat_id}: {repr(msg['content'][:50])}")

                        cats = msg.get("categorias_detectadas") or []
                        handoff = any(
                            c.get("handoff_recommended")
                            for c in cats if isinstance(c, dict)
                        )
                        if handoff:
                            await notify_owner(client, msg, telegram_chat_id)

                    except Exception as e:
                        print(f"[TELEGRAM ERROR] Could not send to {telegram_chat_id}: {e}")

            except Exception as e:
                print(f"[TELEGRAM POLL ERROR] {e}")

            await asyncio.sleep(POLL_SEND_SECONDS)

    async def notify_owner(client, msg, customer_chat_id: str):
        owner_id = get_owner_telegram_id()
        if not owner_id:
            print("[TELEGRAM] No owner_telegram_id configured — skipping notification")
            return

        cats = msg.get("categorias_detectadas") or []
        reason = next(
            (c.get("handoff_reason", "") for c in cats
             if isinstance(c, dict) and c.get("handoff_recommended")),
            ""
        )

        session = None
        try:
            supabase = get_supabase()
            res = supabase.table("test_sessions").select(
                "telegram_username, telegram_first_name"
            ).eq("telegram_chat_id", str(customer_chat_id)).limit(1).execute()
            if res.data:
                session = res.data[0]
        except Exception:
            pass

        name = ""
        if session:
            name = session.get("telegram_username") or session.get("telegram_first_name") or ""

        notification = (
            f"⚠️ *A customer needs your attention*\n\n"
            f"{'@' + name if name else 'Chat ID: ' + str(customer_chat_id)}\n"
            f"Reason: _{reason or 'High intent detected'}_\n\n"
            f"Open Telegram and reply to take over 💬"
        )

        try:
            await client.send_message(int(owner_id), notification, parse_mode="markdown")
            print(f"[TELEGRAM] Handoff notification sent to owner")
        except Exception as e:
            print(f"[TELEGRAM] Could not notify owner: {e}")

    print("[TELEGRAM] Worker running. Listening for messages...")
    try:
        await asyncio.gather(
            client.run_until_disconnected(),
            send_pending_replies(),
            process_history_import_requests(client),
        )
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("[TELEGRAM] Worker stopped by user.")
    finally:
        await client.disconnect()
        print("[TELEGRAM] Disconnected cleanly.")

async def import_older_messages_for_session(client, session_id: str, telegram_chat_id: str, count_to_import: int):
    entity = await client.get_entity(int(telegram_chat_id))

    oldest_known_id = get_oldest_imported_telegram_message_id(session_id)

    collected = []

    if oldest_known_id:
        async for msg in client.iter_messages(entity, limit=count_to_import, max_id=int(oldest_known_id)):
            collected.append(msg)
    else:
        async for msg in client.iter_messages(entity, limit=count_to_import):
            collected.append(msg)

    collected.reverse()

    inserted = 0
    for msg in collected:
        text = (msg.message or "").strip()
        if not text:
            continue

        turn_number = get_next_turn_number(session_id)
        role = "assistant" if msg.out else "user"

        ok = save_imported_message(
            session_id=session_id,
            telegram_message_id=int(msg.id),
            role=role,
            content=text,
            turn_number=turn_number,
        )
        if ok:
            inserted += 1

    return inserted

async def process_history_import_requests(client):
    while True:
        try:
            pending = get_pending_history_import_requests(limit=5)

            for item in pending:
                request_id = item["id"]
                session_id = item["session_id"]
                count_to_import = item.get("count_to_import", 10) or 10

                print(f"[HISTORY IMPORT] Processing request {request_id} for session {session_id}")
                update_history_import_request(request_id, "processing")

                try:
                    session = get_test_session_by_id(session_id)
                    if not session:
                        raise ValueError("Session not found")

                    telegram_chat_id = session.get("telegram_chat_id")
                    if not telegram_chat_id:
                        raise ValueError("telegram_chat_id not found in session")

                    inserted = await import_older_messages_for_session(
                        client,
                        session_id=session_id,
                        telegram_chat_id=str(telegram_chat_id),
                        count_to_import=count_to_import,
                    )

                    print(f"[HISTORY IMPORT] Request {request_id} done | inserted={inserted}")
                    update_history_import_request(request_id, "done")

                except Exception as e:
                    print(f"[HISTORY IMPORT ERROR] Request {request_id}: {e}")
                    update_history_import_request(request_id, "error", error_text=str(e))

        except Exception as e:
            print(f"[HISTORY IMPORT LOOP ERROR] {e}")

        await asyncio.sleep(3)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass