import os
import asyncio
import time
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.types import User

load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
PHONE = os.getenv("TELEGRAM_PHONE", "")
SESSION_FILE = "telegram_session_history"

POLL_SECONDS = 3


def get_supabase():
    from supabase import create_client
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY not found in .env")
    return create_client(url, key)


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
        payload["processed_at"] = datetime_now_iso()

    response = (
        supabase.table("telegram_history_import_requests")
        .update(payload)
        .eq("id", request_id)
        .execute()
    )
    return response.data


def datetime_now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def get_session_by_id(session_id: str):
    supabase = get_supabase()
    response = (
        supabase.table("test_sessions")
        .select("*")
        .eq("id", session_id)
        .limit(1)
        .execute()
    )
    if response.data:
        return response.data[0]
    return None


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
        print(f"[IMPORT] Skipped duplicated message {telegram_message_id}: {e}")
        return False


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


async def main():
    print("[HISTORY IMPORT] Starting worker...")

    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
    await client.start(phone=PHONE)

    me = await client.get_me()
    print(f"[HISTORY IMPORT] Logged in as {me.first_name} (id={me.id})")

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
                    session = get_session_by_id(session_id)
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

            await asyncio.sleep(POLL_SECONDS)

        except KeyboardInterrupt:
            print("[HISTORY IMPORT] Worker stopped by user.")
            break
        except Exception as e:
            print(f"[HISTORY IMPORT LOOP ERROR] {e}")
            await asyncio.sleep(POLL_SECONDS)

    await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass