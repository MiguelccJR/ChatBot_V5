-- ============================================================
-- Telegram support schema
-- ============================================================

-- test_sessions: añadir campos de Telegram
alter table test_sessions
  add column if not exists telegram_chat_id text unique,
  add column if not exists telegram_username text,
  add column if not exists telegram_first_name text,
  add column if not exists active boolean default true;

-- Actualizar constraint de control_mode para incluir disabled
alter table test_sessions
  drop constraint if exists test_sessions_control_mode_check;

alter table test_sessions
  add constraint test_sessions_control_mode_check
  check (control_mode in ('bot', 'human', 'disabled'));

-- chat_messages: añadir sent_to_telegram
alter table chat_messages
  add column if not exists sent_to_telegram boolean default false;

-- Marcar mensajes existentes como ya enviados
update chat_messages
set sent_to_telegram = true
where sent_to_telegram is null;

-- Índices
create index if not exists idx_chat_messages_pending_send
  on chat_messages(sent_to_telegram, role, status, source)
  where sent_to_telegram = false
    and role = 'assistant'
    and status = 'done'
    and source = 'local_ai';

create index if not exists idx_sessions_telegram_chat_id
  on test_sessions(telegram_chat_id);

create index if not exists idx_sessions_control_mode
  on test_sessions(control_mode);

-- bot_config: owner telegram id para notificaciones
insert into bot_config (category, key, value, description)
values ('setting', 'owner_telegram_id', null, 'Your Telegram user ID for handoff notifications')
on conflict (key) do nothing;