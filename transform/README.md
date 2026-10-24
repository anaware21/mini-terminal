# transform (dbt)

Builds the derived views on top of the raw tables the scrapers write to.

- **Raw tables, RLS, grants on raw tables** → `supabase/migrations/` (unchanged)
- **Anything computed from raw tables** → `models/` here

GitHub Actions runs `dbt build` + `dbt source freshness` right after each scrape.

## Running locally

```sh
pip install -r transform/requirements.txt
cd transform
export DBT_PROFILES_DIR=.
export SUPABASE_DB_HOST=...  SUPABASE_DB_USER=...  SUPABASE_DB_PASSWORD=...
dbt build                  # prod views + tests
TABLE_PREFIX=test_ dbt build   # test_ views
dbt source freshness
```

Against a local `supabase start` instead: `SUPABASE_DB_HOST=127.0.0.1
SUPABASE_DB_PORT=54322 SUPABASE_DB_USER=postgres SUPABASE_DB_PASSWORD=postgres
SUPABASE_DB_SSLMODE=disable`.

## Gotchas

- `costco_daily_avg` was originally created by a migration. dbt now owns it; a
  `supabase db reset` recreates the migration version and the next `dbt build`
  replaces it. Don't change the view in a new migration.
- Supabase's default privileges grant anon `ALL` on every new view, and dbt's
  `grants` config can't take them away on Postgres -- so models set access in
  `post_hook`s (see `costco_daily_avg.sql`). Copy that pattern for new models.
