import os
import asyncio
import random
import base64
import io
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
    try:
        import whisper
        import tempfile
        import os

        # Save bytes to temp file
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            model = whisper.load_model("base")
            result = model.transcribe(tmp_path)
            text = (result.get("text") or "").strip()
            print(f"[WHISPER] Transcription: {repr(text[:80])}")
            return text if text else None
        finally:
            os.unlink(tmp_path)

    except Exception as e:
        print(f"[WHISPER ERROR] {e}")
        return None

# Responses for non-text messages
NON_TEXT_RESPONSES = [
    "Heyy, I can only read text messages for now 😊 What's on your mind?",
    "I can't open that right now 😅 Just text me what you need!",
    "Aww, I can't view that here 😊 Tell me in words?",
    "I'm text-only for now 😄 What did you want to say?",
    "Can't read that one! But I'm here — just text me 😘",
]

# Typing delay range in seconds (min, max)
TYPING_DELAY_MIN = 2
TYPING_DELAY_MAX = 5
POLL_SEND_SECONDS = 2.0


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


def register_new_chat(telegram_chat_id: str, username: str = "", first_name: str = "") -> str:
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


def save_incoming_message(session_id: str, text: str, turn_number: int):
    supabase = get_supabase()
    supabase.table("chat_messages").insert({
        "session_id": session_id,
        "turn_number": turn_number,
        "role": "user",
        "content": text,
        "status": "pending_ai",
        "source": "telegram",
        "idioma": "en",
        "categorias_detectadas": [],
        "categorias_respondibles": [],
    }).execute()


def save_incoming_message_with_image(session_id: str, text: str, turn_number: int, img_b64: str):
    """Saves a message with an embedded image for vision processing."""
    supabase = get_supabase()
    supabase.table("chat_messages").insert({
        "session_id": session_id,
        "turn_number": turn_number,
        "role": "user",
        "content": text,
        "status": "pending_ai",
        "source": "telegram",
        "idioma": "en",
        "categorias_detectadas": [{"image_b64": img_b64}],
        "categorias_respondibles": [],
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
        .eq("source", "local_ai")
        .order("created_at")
        .limit(10)
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


# ----------------------------
# Main
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
            username = getattr(sender, 'username', '') or ''
            first_name = getattr(sender, 'first_name', '') or ''
            register_new_chat(chat_id, username, first_name)
            return

        # Disabled — stop here, don't log or store anything
        if session.get("control_mode", "disabled") == "disabled":
            return

        print(f"[TELEGRAM] Incoming from {chat_id}: {repr(text[:60]) if text else '[media]'}")

        control_mode = session.get("control_mode", "disabled")
        session_id = session["id"]

        # Disabled — ignore completely, don't log message content
        if control_mode == "disabled":
            return

        # Human mode — save message but don't process with AI
        if control_mode == "human":
            if text:
                turn_number = get_next_turn_number(session_id)
                save_incoming_message(session_id, text, turn_number)
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
                # Also check for voice attribute directly
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
                    # Download image bytes
                    img_bytes = await client.download_media(event.message, bytes)
                    img_b64 = base64.b64encode(img_bytes).decode('utf-8')

                    # Save as pending_ai with image data embedded
                    turn_number = get_next_turn_number(session_id)
                    image_text = f"[Image attached — base64 data available for vision model]"
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
            await client.send_message(int(chat_id), response)
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
    # Poll: send pending AI replies
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

                    # Don't send if session switched to human or disabled
                    if control_mode in ("human", "disabled"):
                        mark_message_sent(msg["id"])
                        continue

                    try:
                        # Simulate human typing delay
                        delay = random.uniform(TYPING_DELAY_MIN, TYPING_DELAY_MAX)
                        await asyncio.sleep(delay)
                        async with client.action(int(telegram_chat_id), 'typing'):
                            await asyncio.sleep(random.uniform(1.0, 2.0))
                        await client.send_message(int(telegram_chat_id), msg["content"])
                        mark_message_sent(msg["id"])
                        print(f"[TELEGRAM] Sent to {telegram_chat_id}: {repr(msg['content'][:50])}")

                        # Check if this message triggered handoff
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

        # Get customer name from session
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
        )
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("[TELEGRAM] Worker stopped by user.")
    finally:
        await client.disconnect()
        print("[TELEGRAM] Disconnected cleanly.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass