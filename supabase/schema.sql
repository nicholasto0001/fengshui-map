-- 會員資料表
--
-- 喺 Supabase 個 SQL Editor 貼一次就得，可以重複執行。
--
-- 呢個唔係 Phase 1 嘅最小結構，係整份 roadmap 嘅骨架 —— 但只起到之後改就要
-- 搬資料嗰幾樣，用唔著嘅嘢一律唔起。四個決定：
--
--  1. 「人」唔等於「帳戶」。八字係掛喺人身上，而戶主只係佢自己戶口入面第一
--     個人；老婆、仔女、外父係同一種東西。如果等到 Phase 3 先加，八字就會
--     同時掛喺兩種唔同嘅東西上面，所有查詢要寫兩次。
--
--  2. 同意唔係一個剔，係一連串唔改得嘅紀錄。私隱專員問「證明佢同意過」，
--     答「資料庫有個格係 true」唔夠 —— 要知邊個、幾時、同意邊個版本。而
--     政策一定會改（Phase 2 加八字就要改），舊用戶同意嘅係舊版。
--
--  3. 用戶有幾種。加個 role 欄而家成本係零，Phase 5 加師傅就唔使處理所有
--     現存用戶。
--
--  4. 樓宇嘅名同分數喺呢度再存一份。開「收藏」要即刻畫到出嚟，唔可以為咗
--     顯示一行字去載成塊圖磚。分數每日變，所以存嘅係收藏當日嗰個。
--
-- 每張表都開 RLS。個公開 key 本來就擺喺網頁入面全世界睇到，RLS 係唯一道門。

-- ============================================================== 帳戶 ===
create table if not exists public.profiles (
  id           uuid primary key references auth.users(id) on delete cascade,
  role         text not null default 'member'
               check (role in ('member', 'practitioner', 'admin')),
  display_name text,
  avatar_url   text,
  created_at   timestamptz not null default now(),
  last_seen_at timestamptz not null default now()
);
create index if not exists profiles_seen_idx on public.profiles(last_seen_at desc);
create index if not exists profiles_created_idx on public.profiles(created_at);

-- ================================================================ 人 ===
-- Phase 2/3 會喺呢度填出生資料同八字。而家全部可以係 null —— 張表存在，
-- 但唔會問用戶任何嘢。
create table if not exists public.persons (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  name        text check (name is null or char_length(trim(name)) <= 40),
  relation    text not null default 'self'
              check (relation in ('self','spouse','child','parent',
                                  'parent_in_law','sibling','other')),
  is_self     boolean not null default false,
  birth_at    timestamptz,          -- 出生時刻
  birth_tz    text,                 -- 出生地時區
  birth_lat   double precision,     -- 真太陽時要用（香港 114.17°E 對 120°E
  birth_lon   double precision,     --   差約 23 分鐘，足以差一個時辰）
  birth_place text,
  -- 命卦要性別先定得到（男女兩條唔同公式）。
  sex         text check (sex in ('m','f')),
  -- 好多人真係唔記得時辰。記低佢係唔記得，好過夾硬當中午 ——
  -- 時辰影響時柱，亦都影響扶抑用神（差幾個鐘可以完全相反）。
  hour_known  boolean not null default false,
  created_at  timestamptz not null default now()
);

-- 由本機升級上嚟嘅戶口：加返上面兩欄。
alter table public.persons add column if not exists sex text;
alter table public.persons add column if not exists hour_known boolean not null default false;
do $$ begin
  alter table public.persons add constraint persons_sex_chk check (sex in ('m','f'));
exception when duplicate_object then null; end $$;
create index if not exists persons_user_idx on public.persons(user_id, created_at);
-- 一個戶口只可以有一個「自己」
create unique index if not exists persons_one_self
  on public.persons(user_id) where is_self;

-- ============================================================ 同意書 ===
-- 只准新增，唔准修改。現時狀態 = 每個 kind 最新嗰一行。
create table if not exists public.consents (
  id      uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  kind    text not null check (kind in ('privacy','marketing','analytics')),
  version text not null,                    -- 例如 '2026-09-20'
  granted boolean not null,                 -- false = 撤回
  source  text,                             -- 'signup' / 'settings'
  at      timestamptz not null default now()
);
create index if not exists consents_user_idx on public.consents(user_id, kind, at desc);

create or replace view public.current_consents as
  select distinct on (user_id, kind)
         user_id, kind, version, granted, at
    from public.consents
   order by user_id, kind, at desc;

-- ============================================================== 清單 ===
create table if not exists public.lists (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users(id) on delete cascade,
  name       text not null check (char_length(trim(name)) between 1 and 40),
  sort       int not null default 0,
  created_at timestamptz not null default now()
);
create index if not exists lists_user_idx on public.lists(user_id, sort, created_at);

-- ============================================================ 已收藏 ===
create table if not exists public.saved (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  list_id     uuid references public.lists(id) on delete set null,
  building_id text not null,
  lat         double precision,
  lon         double precision,
  tc          text,
  en          text,
  district    text,
  total       numeric,          -- 收藏當日嘅分數
  now_code    text,             -- 收藏當日嘅九運判語
  note        text check (note is null or char_length(note) <= 500),
  created_at  timestamptz not null default now(),
  unique (user_id, building_id, list_id)
);
create index if not exists saved_user_idx on public.saved(user_id, created_at desc);
create index if not exists saved_list_idx on public.saved(list_id, created_at desc);

-- ============================================================== 睇過 ===
create table if not exists public.viewed (
  user_id     uuid not null references auth.users(id) on delete cascade,
  building_id text not null,
  lat         double precision,
  lon         double precision,
  tc          text,
  en          text,
  district    text,
  total       numeric,
  seen_count  int not null default 1,
  last_seen   timestamptz not null default now(),
  primary key (user_id, building_id)
);
create index if not exists viewed_recent_idx on public.viewed(user_id, last_seen desc);

-- ============================================================== RLS ===
alter table public.profiles enable row level security;
alter table public.persons  enable row level security;
alter table public.consents enable row level security;
alter table public.lists    enable row level security;
alter table public.saved    enable row level security;
alter table public.viewed   enable row level security;

do $$
declare t text;
begin
  -- profiles 用 id 做主鍵，其餘用 user_id
  execute 'drop policy if exists own_rows on public.profiles';
  execute 'create policy own_rows on public.profiles for all
             using (auth.uid() = id) with check (auth.uid() = id)';

  foreach t in array array['persons','lists','saved','viewed'] loop
    execute format('drop policy if exists own_rows on public.%I', t);
    execute format('create policy own_rows on public.%I for all
                      using (auth.uid() = user_id)
                      with check (auth.uid() = user_id)', t);
  end loop;

  -- 同意書只准睇同加，唔准改唔准刪 —— 改得就唔算證據。
  execute 'drop policy if exists own_read on public.consents';
  execute 'create policy own_read on public.consents for select
             using (auth.uid() = user_id)';
  execute 'drop policy if exists own_insert on public.consents';
  execute 'create policy own_insert on public.consents for insert
             with check (auth.uid() = user_id)';
end $$;

-- ================================================ 開戶時整定嘅嘢 ===
create or replace function public.on_user_created()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, display_name, avatar_url)
  values (new.id,
          new.raw_user_meta_data->>'full_name',
          new.raw_user_meta_data->>'avatar_url')
  on conflict (id) do nothing;

  -- 第一張清單同第一個「人」，等佢一入嚟就用得，唔使自己開
  insert into public.lists (user_id, name, sort) values (new.id, '我的收藏', 0);
  insert into public.persons (user_id, relation, is_self, name)
  values (new.id, 'self', true, new.raw_user_meta_data->>'full_name');
  return new;
end $$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.on_user_created();

-- ==================================================== 睇過就記一次 ===
create or replace function public.mark_viewed(
  p_building_id text, p_lat double precision, p_lon double precision,
  p_tc text, p_en text, p_district text, p_total numeric)
returns void
language sql
security invoker
as $$
  insert into public.viewed
    (user_id, building_id, lat, lon, tc, en, district, total)
  values
    (auth.uid(), p_building_id, p_lat, p_lon, p_tc, p_en, p_district, p_total)
  on conflict (user_id, building_id) do update
    set seen_count = public.viewed.seen_count + 1,
        last_seen  = now(),
        total      = excluded.total;
$$;

create or replace function public.touch_last_seen()
returns void language sql security invoker as $$
  update public.profiles set last_seen_at = now() where id = auth.uid();
$$;

-- ======================================================== 後台數字 ===
-- RLS 令每個人只見到自己嘅行，所以統計要用 security definer 繞過，
-- 而繞過之前一定要自己檢查身分 —— 唔查就等於冇 RLS。
create or replace function public.admin_metrics()
returns json
language plpgsql
security definer
set search_path = public
as $$
declare result json;
begin
  if not exists (select 1 from public.profiles
                  where id = auth.uid() and role = 'admin') then
    raise exception 'not an admin';
  end if;

  select json_build_object(
    'members',        (select count(*) from profiles),
    'new_today',      (select count(*) from profiles
                        where created_at >= date_trunc('day', now())),
    'new_7d',         (select count(*) from profiles
                        where created_at >= now() - interval '7 days'),
    'dau',            (select count(*) from profiles
                        where last_seen_at >= now() - interval '1 day'),
    'wau',            (select count(*) from profiles
                        where last_seen_at >= now() - interval '7 days'),
    'mau',            (select count(*) from profiles
                        where last_seen_at >= now() - interval '30 days'),
    -- 註冊咗但一個樓盤都未儲過，等於未啟動
    'activated',      (select count(distinct user_id) from saved),
    'saved_total',    (select count(*) from saved),
    'lists_total',    (select count(*) from lists),
    'viewed_total',   (select count(*) from viewed),
    'marketing_optin',(select count(*) from current_consents
                        where kind = 'marketing' and granted),
    -- 新用戶第二日／第七日有冇返嚟
    'ret_d1',         (select count(*) from profiles
                        where created_at < now() - interval '1 day'
                          and last_seen_at >= created_at + interval '1 day'),
    'ret_d7',         (select count(*) from profiles
                        where created_at < now() - interval '7 days'
                          and last_seen_at >= created_at + interval '7 days'),
    'cohort_d1',      (select count(*) from profiles
                        where created_at < now() - interval '1 day'),
    'cohort_d7',      (select count(*) from profiles
                        where created_at < now() - interval '7 days'),
    'top_districts',  (select coalesce(json_agg(d), '[]'::json) from (
                        select district, count(*) as n from saved
                         where district is not null
                         group by district order by n desc limit 8) d),
    'as_of',          now()
  ) into result;
  return result;
end $$;

revoke all on function public.admin_metrics() from public;
grant execute on function public.admin_metrics() to authenticated;
