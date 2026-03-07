-- Satomi Bot: Supabase テーブル定義
-- Supabase の SQL Editor でこのスクリプトを実行してください

create table if not exists user_profiles (
  id               bigserial primary key,
  line_user_id     text unique not null,
  nickname         text,
  message_count    integer not null default 0,
  is_premium       boolean not null default false,
  registered_at    timestamptz not null default now(),
  last_active_at   timestamptz not null default now()
);

-- message_count 列が古いテーブルに存在しない場合は以下を実行
-- alter table user_profiles add column if not exists message_count integer not null default 0;
-- alter table user_profiles add column if not exists is_premium boolean not null default false;
-- alter table user_profiles add column if not exists last_active_at timestamptz not null default now();

-- インデックス
create index if not exists idx_user_profiles_line_user_id on user_profiles(line_user_id);
