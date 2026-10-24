-- Warns when the most recent day has noticeably fewer reporting warehouses
-- than the best day of the last 30 -- i.e. a partial scrape that would skew
-- the average. Returns the offending day, if any.
{{ config(severity='warn') }}

with recent as (
    select *
    from {{ ref('costco_daily_avg') }}
    where date >= current_date - 30
),

latest as (
    select * from recent order by date desc limit 1
),

best as (
    select
        max(reg_station_count) as reg,
        max(prm_station_count) as prm
    from recent
)

select latest.*
from latest
cross join best
where latest.reg_station_count < 0.8 * best.reg
   or latest.prm_station_count < 0.8 * best.prm
