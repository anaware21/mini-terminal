-- Replaces the view created in supabase/migrations/*_costco_daily_avg_view.sql;
-- see that file for why this is a view and why prices are rounded to 3 places.
--
-- Access is set in post_hooks rather than dbt's `grants` config: Supabase's
-- default privileges hand anon/authenticated ALL on every new view, and dbt
-- only ever adds grants on Postgres, never revokes them.
--   * security_invoker = on makes the view run with the CALLER's permissions,
--     so it respects RLS on the raw tables (dbt has no config for this).
--   * anon gets SELECT on the prod view only; the dashboard never reads test_.
{% set is_test = env_var('TABLE_PREFIX', '') != '' %}
{{ config(
    alias=env_var('TABLE_PREFIX', '') ~ 'costco_daily_avg',
    post_hook=[
        "alter view {{ this }} set (security_invoker = on)",
        "revoke all on {{ this }} from anon, authenticated",
    ] + ([] if is_test else ["grant select on {{ this }} to anon"]),
) }}

with regular as (
    select
        date,
        round(avg(price)::numeric, 3) as avg_reg_price,
        count(price)                  as reg_station_count
    from {{ source('gas', 'costco_reg_gas_by_loc') }}
    where price is not null and date is not null
    group by date
),

premium as (
    select
        date,
        round(avg(price)::numeric, 3) as avg_prm_price,
        count(price)                  as prm_station_count
    from {{ source('gas', 'costco_prm_gas_by_loc') }}
    where price is not null and date is not null
    group by date
)

select
    coalesce(r.date, p.date)         as date,
    r.avg_reg_price,
    p.avg_prm_price,
    coalesce(r.reg_station_count, 0) as reg_station_count,
    coalesce(p.prm_station_count, 0) as prm_station_count
from regular r
full outer join premium p on r.date = p.date
