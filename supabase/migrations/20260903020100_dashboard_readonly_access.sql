-- Read-only access for the Streamlit dashboard (app/streamlit_app.py).
--
-- STARTING STATE (from the pulled baseline): RLS is already enabled on every
-- costco_* table, but NO policies exist anywhere. RLS with zero policies denies
-- everything to non-bypass roles, so the anon key can currently read nothing.
-- The scraper is unaffected because it connects as service_role, which has
-- BYPASSRLS. The `enable row level security` statements below are therefore
-- no-ops kept for self-containment; the policies are the actual change.
--
-- !! BEFORE APPLYING: confirm the scraper's SUPABASE_KEY is the SERVICE ROLE
-- !! key. If it is the anon key, the daily insert in data/gas/upload.py is
-- !! already failing (RLS denies it today) -- rotate it to service_role.

alter table public.costco_reg_gas_by_loc enable row level security;
alter table public.costco_prm_gas_by_loc enable row level security;

-- Gas prices are public information; there is no per-user row filtering here.
-- `using (true)` exposes every row for SELECT and nothing else. Writes stay
-- denied because no INSERT/UPDATE/DELETE policy exists.
create policy "dashboard reads regular prices"
    on public.costco_reg_gas_by_loc
    for select
    to anon
    using (true);

create policy "dashboard reads premium prices"
    on public.costco_prm_gas_by_loc
    for select
    to anon
    using (true);

-- The baseline hands anon GRANT ALL on every public table. Strip the write
-- grants as defense in depth behind the policies above.
revoke insert, update, delete, truncate on public.costco_reg_gas_by_loc from anon;
revoke insert, update, delete, truncate on public.costco_prm_gas_by_loc from anon;

grant select on public.costco_reg_gas_by_loc to anon;
grant select on public.costco_prm_gas_by_loc to anon;

-- costco_daily_avg is a security_invoker view, so it reads THROUGH the two
-- policies above rather than needing one of its own. It still needs a grant.
grant select on public.costco_daily_avg to anon;

-- The legacy tables are retained only until the views are verified against
-- them; never expose them to the dashboard.
revoke all on public.costco_daily_avg_legacy from anon;
revoke all on public.test_costco_daily_avg_legacy from anon;

-- The test_ tables intentionally get NO anon policy: they keep RLS enabled with
-- zero policies, so anon cannot read them. Inspect test runs via the SQL editor
-- or the service role. The dashboard only ever reads prod.

-- Note: grants here are to `anon` only. If you later add Supabase Auth and want
-- signed-in users to read too, repeat the policies and grants for the
-- `authenticated` role.