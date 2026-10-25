-- Clario: accounts + practice history.
-- Run once in the Supabase dashboard: SQL Editor -> New query -> paste -> Run.
-- (The "recordings" storage bucket is created automatically by the backend.)

create table if not exists public.users (
  id            uuid primary key default gen_random_uuid(),
  username      text not null unique,
  password_hash text not null,
  created_at    timestamptz not null default now()
);

create table if not exists public.attempts (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references public.users (id) on delete cascade,
  created_at      timestamptz not null default now(),
  mode            text not null check (mode in ('word', 'sentence')),
  target_word     text not null,
  accuracy        real not null,
  n_phonemes      integer not null,
  n_errors        integer not null,
  n_words         integer not null,
  n_words_correct integer not null,
  word_accuracy   real,
  duration_sec    real not null,
  error_threshold real not null,
  word_warning    text,
  waveform_rate   integer not null,
  phonemes        jsonb not null,
  words           jsonb not null,
  waveform_q      text,           -- plot waveform as base64-encoded int8 samples
  audio_path      text            -- object path in the "recordings" bucket
);

create index if not exists attempts_user_created_idx
  on public.attempts (user_id, created_at desc);

-- Lock both tables down: with RLS on and no policies, the public (anon /
-- publishable) key can't read or write anything. Only the backend's secret
-- (service role) key, which bypasses RLS, can.
alter table public.users    enable row level security;
alter table public.attempts enable row level security;
