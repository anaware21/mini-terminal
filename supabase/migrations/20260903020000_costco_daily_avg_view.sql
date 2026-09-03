-- Replace the costco_daily_avg TABLE with a VIEW derived from the raw
-- per-location tables (and do the same for the test_ mirror).
--
-- Why: the table stored an average computed once at ingest time. Any backfill,
-- corrected scrape, or added warehouse left every historical average silently
-- wrong with no way to recompute. As a view, the average is always derived from
-- whatever the raw tables currently hold.
--
-- PRECISION NOTE: `price` is `real` (float4) in the baseline schema, so a plain
-- avg(price) returns double precision and carries float noise -- an average of
-- 4.00/4.20/4.40 comes back as 4.2000000476837158. Rounding to numeric(_,3)
-- matches how US pump prices are actually quoted (the trailing 9/10 cent) and
-- makes the view reconcile cleanly against the legacy stored values.
--
-- This migration RENAMES the old tables instead of dropping them. Verify the
-- views reproduce the legacy rows (queries at the bottom), then drop the
-- _legacy tables in a follow-up migration.

alter table if exists public.costco_daily_avg
    rename to costco_daily_avg_legacy;

-- security_invoker = on makes the view execute with the CALLER's permissions,
-- so it respects RLS on the underlying tables. Without it a view runs as its
-- owner and hands out every row regardless of policy -- which would defeat the
-- read-only policies in the next migration. (Supabase's linter flags the
-- default as `security_definer_view`.)
create view public.costco_daily_avg
with (security_invoker = on) as
select
    coalesce(r.date, p.date)         as date,
    r.avg_reg_price,
    p.avg_prm_price,
    coalesce(r.reg_station_count, 0) as reg_station_count,
    coalesce(p.prm_station_count, 0) as prm_station_count
from (
    select
        date,
        round(avg(price)::numeric, 3) as avg_reg_price,
        count(price)                  as reg_station_count
    from public.costco_reg_gas_by_loc
    where price is not null and date is not null
    group by date
) r
full outer join (
    select
        date,
        round(avg(price)::numeric, 3) as avg_prm_price,
        count(price)                  as prm_station_count
    from public.costco_prm_gas_by_loc
    where price is not null and date is not null
    group by date
) p on r.date = p.date;

comment on view public.costco_daily_avg is
    'Daily network average Costco gas price, derived from the per-location '
    'tables. The station_count columns report how many warehouses actually '
    'reported that day -- a low count means a degraded scrape, not a real move.';

-- Test mirror, so a workflow_dispatch run exercises the same shape as prod.
alter table if exists public.test_costco_daily_avg
    rename to test_costco_daily_avg_legacy;

create view public.test_costco_daily_avg
with (security_invoker = on) as
select
    coalesce(r.date, p.date)         as date,
    r.avg_reg_price,
    p.avg_prm_price,
    coalesce(r.reg_station_count, 0) as reg_station_count,
    coalesce(p.prm_station_count, 0) as prm_station_count
from (
    select
        date,
        round(avg(price)::numeric, 3) as avg_reg_price,
        count(price)                  as reg_station_count
    from public.test_costco_reg_gas_by_loc
    where price is not null and date is not null
    group by date
) r
full outer join (
    select
        date,
        round(avg(price)::numeric, 3) as avg_prm_price,
        count(price)                  as prm_station_count
    from public.test_costco_prm_gas_by_loc
    where price is not null and date is not null
    group by date
) p on r.date = p.date;

-- ---------------------------------------------------------------------------
-- VERIFY before dropping the legacy tables. Compared with a tolerance because
-- the legacy column is `real` (~7 significant digits) while the view is exact
-- numeric. This should return zero rows:
--
--   select l.date,
--          l.avg_reg_price as legacy_reg, v.avg_reg_price as view_reg,
--          l.avg_prm_price as legacy_prm, v.avg_prm_price as view_prm
--   from public.costco_daily_avg_legacy l
--   join public.costco_daily_avg v using (date)
--   where abs(l.avg_reg_price::numeric - v.avg_reg_price) > 0.001
--      or abs(l.avg_prm_price::numeric - v.avg_prm_price) > 0.001;
--
-- And check for dates in one but not the other:
--
--   select coalesce(l.date, v.date) as date,
--          l.date is null as missing_from_legacy,
--          v.date is null as missing_from_view
--   from public.costco_daily_avg_legacy l
--   full outer join public.costco_daily_avg v using (date)
--   where l.date is null or v.date is null;
--
-- Then, in a NEW migration:
--   drop table public.costco_daily_avg_legacy;
--   drop table public.test_costco_daily_avg_legacy;
-- ---------------------------------------------------------------------------