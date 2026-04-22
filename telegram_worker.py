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

def upload_media_to_supabase_storage(file_bytes: bytes, storage_path: str, content_type: str) -> str:
    """Uploads media to Supabase Storage bucket 'chat-media' and returns public URL."""
    supabase = get_supabase()
    try:
        supabase.storage.from_("chat-media").upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": content_type, "upsert": "true"}
        )
    except Exception as e:
        print(f"[STORAGE] Upload warning for {storage_path}: {e}")
    public_url = supabase.storage.from_("chat-media").get_public_url(storage_path)
    return public_url


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
            "is_archived": is_archived,
        })
        .execute()
    )
    print(
        f"[TELEGRAM] New chat registered: {telegram_chat_id} "
        f"({username or first_name}) — DISABLED | archived={is_archived}"
    )
    return response.data[0]["id"]


def set_session_archived(telegram_chat_id: str, is_archived: bool):
    supabase = get_supabase()
    response = (
        supabase.table("test_sessions")
        .update({"is_archived": is_archived})
        .eq("telegram_chat_id", str(telegram_chat_id))
        .execute()
    )
    return response.data


def save_incoming_message(
    session_id: str,
    text: str,
    turn_number: int,
    *,
    status: str = "pending_ai",
    error_text: str | None = None,
    telegram_date: str | None = None,
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
        "telegram_date": telegram_date,
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


def save_incoming_media_message(
    session_id: str,
    text: str,
    turn_number: int,
    media_type: str,
    media_url: str,
    mime_type: str,
    *,
    status: str = "pending_ai",
    error_text: str | None = None,
    telegram_date: str | None = None,
):
    """Saves a message with media (image, audio, video, sticker) stored in Supabase Storage."""
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
        "media_type": media_type,
        "media_url": media_url,
        "mime_type": mime_type,
        "telegram_date": telegram_date,
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


# ----------------------------
# Archived chats sync
# ----------------------------
def get_pending_history_import_requests(limit: int = 5) -> list:
    supabase = get_supabase()
    try:
        response = (
            supabase.table("telegram_history_import_requests")
            .select("*")
            .eq("status", "pending")
            .order("created_at")
            .limit(limit)
            .execute()
        )
        return response.data or []
    except Exception as e:
        print(f"[HISTORY] Could not fetch import requests: {e}")
        return []


def update_history_import_request(request_id: int, status: str, error_text: str | None = None):
    supabase = get_supabase()
    payload = {"status": status, "error_text": error_text}
    if status in ("done", "error"):
        payload["processed_at"] = datetime.now(timezone.utc).isoformat()
    supabase.table("telegram_history_import_requests").update(payload).eq("id", request_id).execute()


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
    media_type: str | None = None,
    media_url: str | None = None,
    mime_type: str | None = None,
) -> bool:
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
        "media_type": media_type,
        "media_url": media_url,
        "mime_type": mime_type,
    }
    try:
        supabase.table("chat_messages").insert(payload).execute()
        return True
    except Exception as e:
        print(f"[HISTORY] Skipped duplicate message {telegram_message_id}: {e}")
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


async def import_older_messages_for_session(
    client, session_id: str, telegram_chat_id: str, count_to_import: int
) -> int:
    import time as _time

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

    print(f"[HISTORY] Found {len(collected)} messages to process")

    for msg in collected:
        turn_number = get_next_turn_number(session_id)
        role = "assistant" if msg.out else "user"
        media_type = None
        media_url = None
        mime_type = None
        text = (msg.message or "").strip()
        has_media = bool(msg.media)
        print(f"[HISTORY] msg_id={msg.id} role={role} text={repr(text[:40])} has_media={has_media}")

        # Handle media
        if msg.media:
            try:
                msg_media = msg.media
                doc = getattr(msg_media, 'document', None)
                doc_mime = (getattr(doc, 'mime_type', '') or '') if doc else ''

                is_photo = hasattr(msg_media, 'photo')
                is_sticker = False
                is_voice = False
                is_video = False

                if doc:
                    if doc_mime.startswith('image/'):
                        is_photo = True
                    if doc_mime == 'image/webp':
                        is_sticker = True
                    for attr in getattr(doc, 'attributes', []):
                        cls = attr.__class__.__name__
                        if cls == 'DocumentAttributeSticker':
                            is_sticker = True
                        if cls == 'DocumentAttributeAudio':
                            is_voice = True
                        if cls == 'DocumentAttributeVideo':
                            is_video = True
                    if doc_mime in ('audio/ogg', 'audio/mpeg', 'audio/mp4', 'audio/m4a', 'audio/wav'):
                        is_voice = True
                    if doc_mime.startswith('video/'):
                        is_video = True

                if is_sticker:
                    mime = 'image/webp'
                    ext = 'webp'
                    folder = 'stickers'
                    media_type = 'sticker'
                    label = 'Sticker'
                elif is_photo:
                    mime = doc_mime or 'image/jpeg'
                    if hasattr(msg_media, 'photo'):
                        mime = 'image/jpeg'
                    ext = 'jpg' if 'jpeg' in mime else mime.split('/')[-1]
                    folder = 'images'
                    media_type = 'image'
                    label = 'Photo'
                elif is_voice:
                    mime = doc_mime or 'audio/ogg'
                    ext = mime.split('/')[-1].split(';')[0] or 'ogg'
                    folder = 'audio'
                    media_type = 'audio'
                    label = 'Voice message'
                elif is_video:
                    mime = doc_mime or 'video/mp4'
                    ext = mime.split('/')[-1].split(';')[0] or 'mp4'
                    folder = 'video'
                    media_type = 'video'
                    label = 'Video'
                else:
                    mime = None

                if media_type and mime:
                    media_bytes = await client.download_media(msg, bytes)
                    ts = int(_time.time())
                    storage_path = f"{folder}/{telegram_chat_id}_{msg.id}_{ts}.{ext}"
                    media_url = upload_media_to_supabase_storage(media_bytes, storage_path, mime)
                    mime_type = mime
                    if not text:
                        text = f"[{label}]"

            except Exception as e:
                print(f"[HISTORY] Could not process media for msg {msg.id}: {e}")

        if not text and not media_type:
            continue

        ok = save_imported_message(
            session_id=session_id,
            telegram_message_id=int(msg.id),
            role=role,
            content=text or f"[{media_type or 'media'}]",
            turn_number=turn_number,
            media_type=media_type,
            media_url=media_url,
            mime_type=mime_type,
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

                print(f"[HISTORY] Processing request {request_id} for session {session_id}")
                update_history_import_request(request_id, "processing")

                try:
                    session = get_test_session_by_id(session_id)
                    if not session:
                        raise ValueError("Session not found")
                    telegram_chat_id = session.get("telegram_chat_id")
                    if not telegram_chat_id:
                        raise ValueError("telegram_chat_id not found")

                    inserted = await import_older_messages_for_session(
                        client,
                        session_id=session_id,
                        telegram_chat_id=str(telegram_chat_id),
                        count_to_import=count_to_import,
                    )
                    print(f"[HISTORY] Request {request_id} done | inserted={inserted}")
                    update_history_import_request(request_id, "done")

                except Exception as e:
                    print(f"[HISTORY ERROR] Request {request_id}: {e}")
                    update_history_import_request(request_id, "error", error_text=str(e))

        except Exception as e:
            print(f"[HISTORY LOOP ERROR] {e}")

        await asyncio.sleep(3)


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
            register_new_chat(chat_id, username, first_name, is_archived=False)
            return

        # If an archived chat writes again, optionally keep it archived.
        # For now we do not change is_archived automatically.

        # Disabled — save for monitoring but do not process with AI
        if session.get("control_mode", "disabled") == "disabled":
            preview = repr(text[:80]) if text else "[media]"
            print(f"[MONITOR] Disabled chat {chat_id}: {preview}")

            session_id_dis = session["id"]
            turn_number = get_next_turn_number(session_id_dis)

            if has_media and not text:
                msg_media = event.message.media

                # Check if photo
                is_photo_dis = hasattr(msg_media, 'photo')
                if not is_photo_dis and hasattr(msg_media, 'document'):
                    doc_mime_dis = getattr(msg_media.document, 'mime_type', '') or ''
                    is_photo_dis = doc_mime_dis.startswith('image/')

                # Check if sticker
                is_sticker_dis = False
                if hasattr(msg_media, 'document'):
                    doc_mime_dis = getattr(msg_media.document, 'mime_type', '') or ''
                    is_sticker_dis = doc_mime_dis == 'image/webp'
                    for attr in getattr(msg_media.document, 'attributes', []):
                        if attr.__class__.__name__ == 'DocumentAttributeSticker':
                            is_sticker_dis = True
                            break

                # Detect media type
                doc_dis = getattr(msg_media, 'document', None)
                doc_mime_dis = (getattr(doc_dis, 'mime_type', '') or '') if doc_dis else ''

                is_voice_dis = False
                is_video_dis = False
                if doc_dis:
                    for attr in getattr(doc_dis, 'attributes', []):
                        cls = attr.__class__.__name__
                        if cls == 'DocumentAttributeAudio':
                            is_voice_dis = True
                        if cls == 'DocumentAttributeVideo':
                            is_video_dis = True
                    if doc_mime_dis in ('audio/ogg', 'audio/mpeg', 'audio/mp4', 'audio/m4a', 'audio/wav'):
                        is_voice_dis = True
                    if doc_mime_dis.startswith('video/'):
                        is_video_dis = True

                import time as _time
                ts_dis = int(_time.time())

                try:
                    media_bytes_dis = await client.download_media(event.message, bytes)

                    if is_photo_dis or is_sticker_dis:
                        mime_dis = 'image/webp' if is_sticker_dis else (doc_mime_dis or 'image/jpeg')
                        if hasattr(msg_media, 'photo') and not is_sticker_dis:
                            mime_dis = 'image/jpeg'
                        ext_dis = 'webp' if is_sticker_dis else ('jpg' if 'jpeg' in mime_dis else mime_dis.split('/')[-1])
                        folder_dis = 'stickers' if is_sticker_dis else 'images'
                        mtype_dis = 'sticker' if is_sticker_dis else 'image'
                        label_dis = 'Sticker' if is_sticker_dis else 'Photo'

                    elif is_voice_dis:
                        mime_dis = doc_mime_dis or 'audio/ogg'
                        ext_dis = mime_dis.split('/')[-1].split(';')[0] or 'ogg'
                        folder_dis = 'audio'
                        mtype_dis = 'audio'
                        label_dis = 'Voice message'

                    elif is_video_dis:
                        mime_dis = doc_mime_dis or 'video/mp4'
                        ext_dis = mime_dis.split('/')[-1].split(';')[0] or 'mp4'
                        folder_dis = 'video'
                        mtype_dis = 'video'
                        label_dis = 'Video'

                    else:
                        save_incoming_message(session_id_dis, "[Media received while disabled]", turn_number,
                            status="waiting_human", error_text="Disabled chat monitored only")
                        return

                    storage_path_dis = f"{folder_dis}/{chat_id}_{ts_dis}.{ext_dis}"
                    media_url_dis = upload_media_to_supabase_storage(media_bytes_dis, storage_path_dis, mime_dis)
                    save_incoming_media_message(
                        session_id_dis, f"[{label_dis} received while disabled]",
                        turn_number, media_type=mtype_dis, media_url=media_url_dis, mime_type=mime_dis,
                        status="waiting_human", error_text="Disabled chat monitored only",
                    )
                    print(f"[MONITOR] Saved {mtype_dis} from disabled chat {chat_id}")

                except Exception as e:
                    print(f"[MONITOR] Could not save media from disabled chat: {e}")
                    save_incoming_message(session_id_dis, "[Media received while disabled — upload failed]",
                        turn_number, status="waiting_human", error_text="Disabled chat monitored only")
            else:
                save_incoming_message(
                    session_id_dis,
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
                tg_date = event.message.date.isoformat() if event.message.date else None
                save_incoming_message(
                    session_id,
                    text,
                    turn_number,
                    status="waiting_human",
                    error_text="Waiting for human reply",
                    telegram_date=tg_date,
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
                        tg_date = event.message.date.isoformat() if event.message.date else None
                        save_incoming_message(session_id, text, turn_number, telegram_date=tg_date)
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

            # --- Photo: upload to Supabase Storage ---
            is_photo = hasattr(msg_media, 'photo')
            if not is_photo and hasattr(msg_media, 'document'):
                doc_mime = getattr(msg_media.document, 'mime_type', '') or ''
                is_photo = doc_mime.startswith('image/')

            if is_photo:
                print(f"[TELEGRAM] Photo from {chat_id} — uploading to storage")
                try:
                    img_bytes = await client.download_media(event.message, bytes)
                    doc_mime = getattr(getattr(msg_media, 'document', None), 'mime_type', '') or 'image/jpeg'
                    if hasattr(msg_media, 'photo'):
                        doc_mime = 'image/jpeg'
                    ext = 'jpg' if 'jpeg' in doc_mime or doc_mime == 'image/jpg' else doc_mime.split('/')[-1]
                    storage_path = f"images/{chat_id}_{int(__import__('time').time())}.{ext}"
                    media_url = upload_media_to_supabase_storage(img_bytes, storage_path, doc_mime)
                    turn_number = get_next_turn_number(session_id)
                    tg_date = event.message.date.isoformat() if event.message.date else None
                    save_incoming_media_message(
                        session_id, "[Customer sent a photo]", turn_number,
                        media_type="image", media_url=media_url, mime_type=doc_mime,
                        telegram_date=tg_date,
                    )
                    print(f"[TELEGRAM] Photo uploaded to storage | session={session_id}")
                    return
                except Exception as e:
                    print(f"[TELEGRAM] Could not process photo: {e} — sending fallback")

            # --- Sticker: save as image if it's a static sticker (webp) ---
            is_sticker = False
            if hasattr(msg_media, 'document'):
                doc_mime = getattr(msg_media.document, 'mime_type', '') or ''
                is_sticker = doc_mime == 'image/webp'
                for attr in getattr(msg_media.document, 'attributes', []):
                    if attr.__class__.__name__ == 'DocumentAttributeSticker':
                        is_sticker = True
                        break

            if is_sticker:
                print(f"[TELEGRAM] Sticker from {chat_id} — uploading to storage")
                try:
                    sticker_bytes = await client.download_media(event.message, bytes)
                    storage_path = f"stickers/{chat_id}_{int(__import__('time').time())}.webp"
                    media_url = upload_media_to_supabase_storage(sticker_bytes, storage_path, 'image/webp')
                    turn_number = get_next_turn_number(session_id)
                    tg_date = event.message.date.isoformat() if event.message.date else None
                    save_incoming_media_message(
                        session_id, "[Customer sent a sticker]", turn_number,
                        media_type="sticker", media_url=media_url, mime_type="image/webp",
                        telegram_date=tg_date,
                    )
                    print(f"[TELEGRAM] Sticker uploaded | session={session_id}")
                    return
                except Exception as e:
                    print(f"[TELEGRAM] Could not process sticker: {e}")

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
        tg_date = event.message.date.isoformat() if event.message.date else None
        save_incoming_message(session_id, text, turn_number, telegram_date=tg_date)
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


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass