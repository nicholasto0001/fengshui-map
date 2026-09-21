-- 貼呢個檔落 Supabase 嘅 SQL Editor 跑一次就得。
-- 全部係 create or replace，跑幾多次都冇所謂，唔會整爛現有嘢。
-- （同一段亦都已經加咗落 schema.sql 最底，呢個檔只係方便你 copy。）

-- ==================================================== 後台（加強版）===
-- 以下兩個函數喺 admin_metrics 之上加：走勢圖、漏斗、每批人嘅存活、
-- 同埋一張會員名單。
--
-- 一個限制要講明：profiles 只存一個 last_seen_at（最後一次見到），
-- 冇逐日嘅活動紀錄。即係話歷史 DAU 係還原唔到嘅，畫條「每日活躍」
-- 出嚟會係作嘅。真正有日期嘅動作得兩樣：profiles.created_at（幾時
-- 註冊）同 saved.created_at（幾時收藏）。下面淨係用呢兩樣。
-- 想要真留存曲線就要開一張 events 表，第日先算。

create or replace function public.admin_overview(p_days int default 60)
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
    -- 走勢：由 p_days 日前開始，每日一行，冇人嗰日都要有行（補零），
    -- 否則條線會自己駁埋，睇落似冇斷過。
    'daily', (
      select coalesce(json_agg(json_build_object(
               'd', to_char(g.d,'YYYY-MM-DD'),
               'signups', coalesce(s.n,0),
               'saves',   coalesce(v.n,0)) order by g.d), '[]'::json)
        from generate_series(
               (current_date - (p_days-1))::date, current_date, '1 day') g(d)
        left join (select created_at::date d, count(*) n from profiles
                    group by 1) s on s.d = g.d::date
        left join (select created_at::date d, count(*) n from saved
                    group by 1) v on v.d = g.d::date),

    -- 漏斗：members → viewed → saved → bazi → family 係層層包含嘅，
    -- 所以跌幅睇得出邊度甩人。optin 唔屬於呢條鏈（登入嗰陣剔），
    -- 一齊回傳但前台要分開擺，否則條 bar 會反彈。
    'funnel', (
      select json_build_object(
        'members',   (select count(*) from profiles),
        'viewed',    (select count(distinct user_id) from viewed),
        'saved',     (select count(distinct user_id) from saved),
        'bazi',      (select count(distinct user_id) from persons
                       where birth_at is not null),
        'family',    (select count(*) from (
                        select user_id from persons where birth_at is not null
                         group by user_id having count(*) > 1) f),
        'optin',     (select count(*) from current_consents
                       where kind='marketing' and granted))),

    -- 每星期一批人，睇佢哋而家仲有幾多個活躍。冇逐日紀錄，所以
    -- 「存活」= 最近 30 日內見過。細過 5 個人唔計百分比。
    'cohorts', (
      select coalesce(json_agg(c order by c.wk desc), '[]'::json) from (
        select to_char(date_trunc('week', created_at),'YYYY-MM-DD') wk,
               count(*) size,
               count(*) filter (
                 where last_seen_at >= now() - interval '30 days') alive,
               round(percentile_cont(0.5) within group (
                 order by extract(epoch from (last_seen_at - created_at))/86400
               )::numeric, 1) med_days
          from profiles
         where created_at >= now() - interval '12 weeks'
         group by 1) c),

    -- 八字：入咗幾多、男女幾多、記唔記得時辰。呢度全部係數量，
    -- 冇一個人嘅出生資料。
    'bazi', (
      select json_build_object(
        'people',     count(*),
        'with_birth', count(*) filter (where birth_at is not null),
        'hour_known', count(*) filter (where hour_known),
        'male',       count(*) filter (where sex='m'),
        'female',     count(*) filter (where sex='f'),
        'self',       count(*) filter (where is_self),
        'relations',  (select coalesce(json_agg(r), '[]'::json) from (
                        select relation, count(*) n from persons
                         group by 1 order by n desc) r))
        from persons),

    -- 人哋真係收藏咗啲乜。區已經有，呢度落到逐幢樓。
    'top_buildings', (
      select coalesce(json_agg(b), '[]'::json) from (
        select tc, district, count(*) n, round(avg(total),1) avg_total
          from saved where tc is not null
         group by 1,2 order by n desc limit 12) b),

    -- 收藏落去嘅分數分佈 —— 人哋係咪只儲高分樓？
    'score_bands', (
      select coalesce(json_agg(s order by s.lo), '[]'::json) from (
        select (floor(total/10)*10)::int lo, count(*) n
          from saved where total is not null group by 1) s),

    'as_of', now()
  ) into result;
  return result;
end $$;

revoke all on function public.admin_overview(int) from public;
grant execute on function public.admin_overview(int) to authenticated;


-- 會員名單。email 喺 auth.users，唔喺 profiles，所以要 join ——
-- 呢個係 security definer 先做得到，而上面已經查咗身分。
--
-- 刻意唔出生日日期／時辰：營運上用唔著，而佢係成張表最敏感嗰欄。
-- 出「有冇入咗」就夠。真係要睇返某一個人，好過逐次去 SQL Editor 查，
-- 有紀錄可追。
create or replace function public.admin_members(
  p_limit int default 50,
  p_offset int default 0,
  p_q text default null,
  p_sort text default 'new')
returns json
language plpgsql
security definer
set search_path = public
as $$
declare result json; q text;
begin
  if not exists (select 1 from public.profiles
                  where id = auth.uid() and role = 'admin') then
    raise exception 'not an admin';
  end if;
  q := nullif(trim(coalesce(p_q,'')), '');

  select json_build_object(
    'total', (select count(*) from profiles p
               join auth.users u on u.id = p.id
              where q is null
                 or u.email ilike '%'||q||'%'
                 or coalesce(p.display_name,'') ilike '%'||q||'%'),
    'rows', coalesce((
      select json_agg(row_to_json(r)) from (
        select p.id,
               u.email,
               p.display_name                                   as name,
               p.role,
               p.created_at,
               p.last_seen_at,
               (select count(*) from saved   s where s.user_id = p.id) as saves,
               (select count(*) from lists   l where l.user_id = p.id) as lists,
               (select count(*) from viewed  v where v.user_id = p.id) as views,
               (select count(*) from persons x
                 where x.user_id = p.id and x.birth_at is not null)    as people,
               coalesce((select c.granted from current_consents c
                          where c.user_id = p.id and c.kind='marketing'),
                        false)                                  as optin,
               (select s.district from saved s
                 where s.user_id = p.id and s.district is not null
                 group by s.district order by count(*) desc limit 1) as top_district
          from profiles p
          join auth.users u on u.id = p.id
         where q is null
            or u.email ilike '%'||q||'%'
            or coalesce(p.display_name,'') ilike '%'||q||'%'
         order by
           case when p_sort = 'seen'   then p.last_seen_at end desc nulls last,
           case when p_sort = 'active' then
             (select count(*) from saved s where s.user_id = p.id) end desc nulls last,
           p.created_at desc
         limit greatest(1, least(p_limit, 200)) offset greatest(0, p_offset)
      ) r), '[]'::json)
  ) into result;
  return result;
end $$;

revoke all on function public.admin_members(int,int,text,text) from public;
grant execute on function public.admin_members(int,int,text,text) to authenticated;
