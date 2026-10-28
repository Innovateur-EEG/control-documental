# Entity type normalization and database audit

## Canonical values

- `personas.tipo`: `Fisica` or `Moral`.
- `configuracion_campos.tipo_persona` and `configuracion_evidencias.tipo_persona`: `Ambas`, `Fisica`, or `Moral`.

Application writes normalize recognized case/accent variants. Unknown values are rejected for writes and fail closed during applicability checks. This change intentionally does **not** add database constraints or automatically rewrite existing rows.

## Read-only database audit (Step 6)

Run from a configured local checkout that points to the intended Supabase database:

```powershell
mise setup
mise exec -- python scripts/audit_entity_types.py
```

The script only runs grouped `SELECT` queries. It reports each stored value, its count, a proposed canonical value for recognized variants, and whether manual review is required. It does not update or delete data.

Before running it, verify that `DATABASE_URL` (or the configured `.secret` values used by the project) points to the **dev/test Supabase database**, not another environment. Do not paste credentials into GitHub or chat.

## Supabase SQL Editor alternative (read-only)

Run each query separately in the Supabase SQL Editor for the project linked to the dev Streamlit app:

```sql
select 'personas.tipo' as source, tipo as raw_value, count(*) as row_count
from public.personas
group by tipo
order by tipo;

select 'configuracion_campos.tipo_persona' as source, tipo_persona as raw_value, count(*) as row_count
from public.configuracion_campos
group by tipo_persona
order by tipo_persona;

select 'configuracion_evidencias.tipo_persona' as source, tipo_persona as raw_value, count(*) as row_count
from public.configuracion_evidencias
group by tipo_persona
order by tipo_persona;
```

These queries are read-only. Share the output (without credentials or unrelated personal data) before any existing values are corrected. Known variants can be mapped safely; unknown values need a manual decision. No data correction, schema migration, or database constraint is part of this commit.
