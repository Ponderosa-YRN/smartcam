# Backend Schema Document — SmartCam
**Version 2.0 · schema v12 · 15 tables**

Source of truth: `smartcam/db.py`.

---

## 1. Storage and migrations

SQLAlchemy Core over two dialects: SQLite (default) and PostgreSQL (translation is one substitution,
`INTEGER PRIMARY KEY AUTOINCREMENT` → `SERIAL PRIMARY KEY`).

Migrations are **additive and hand-listed** in `_column_migrations()` as `(version, table, column, ddl)`,
each idempotent, gated on `LATEST_SCHEMA_VERSION = 12`. There is no migration framework; a destructive
change needs a hand-written one.

Conventions: surrogate `id` keys; `created_at` TEXT display timestamps alongside `ts`/`start_ts` REAL
epoch seconds; embeddings as JSON text; booleans as INTEGER 0/1; `tenant_id` INTEGER on every
tenant-owned table (**nullable** — NULL means unassigned, and `ensure_default_tenant()` sweeps NULLs
into the lowest-id tenant at startup).

Indexes are created **after** the column migrations, because they reference `tenant_id`, which the
migrations add. Tenant-first composites: `events(tenant_id, start_ts)`, `plates(tenant_id, ts)`.

---

## 2. Tables

### `tenants`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| slug | TEXT UNIQUE NOT NULL | |
| name | TEXT NOT NULL | |
| plan | TEXT DEFAULT 'free' | free / pro / enterprise |
| billing_status | TEXT DEFAULT 'active' | |
| stripe_customer_id, stripe_subscription_id | TEXT | For a payment integration that does not exist |
| created_at | TEXT | |

### `users`
| Column | Type | Notes |
|---|---|---|
| id, username (UNIQUE), password_hash | | scrypt |
| role | TEXT DEFAULT 'viewer' | admin / **security** / manager / viewer |
| tenant_id | INTEGER | |
| created_at | TEXT | |

### `sites` — tenant_id, name, timezone
### `devices` — tenant_id, site_id, name, token_hash, token_generation, last_seen
### `invites` — tenant_id, email, role, token (UNIQUE), consumed, expires_at

### `events` — the fact table
| Column | Notes |
|---|---|
| camera_id, camera_name | |
| start_ts, end_ts, duration | REAL epoch |
| objects, track_ids | JSON arrays |
| top_object, max_conf | |
| event_type | detection / loitering / intrusion / queue / fall / abandoned / parking |
| clip_path, thumb_path, summary, summary_model, plate | |
| acknowledged, resolved, escalated, assignee, notified | triage state |
| tenant_id, device_id | ownership |
| created_at | |

Indexes: `start_ts`, `camera_id`, `(tenant_id, start_ts)`.

### `plates` — camera_id, camera_name, plate, confidence, crop_path, ts, tenant_id
Indexes: `ts`, `plate`, `(tenant_id, ts)`.

### `faces` — name, role, **consent**, embedding, thumb_path, tenant_id
### `face_matches` — camera_id, face_id, name, confidence, embedding, ts, tenant_id
### `identities` — name, face_id, embedding (**gallery of up to 10**), thumb_path, tenant_id
### `sightings` — identity_id, camera_id, confidence, thumb_path, ts, tenant_id
### `appearances` — camera_id, track_id, embedding, thumb_path, ts, tenant_id
### `occupancy_samples` — ts, people, vehicles, tenant_id, device_id
### `schema_meta` — key, value (schema version on Postgres)

---

## 3. Migration history

| v | Change |
|---|---|
| 1 | events.event_type, events.plate |
| 2 | events.acknowledged, resolved, assignee |
| 3 | events.escalated |
| 4 | faces.consent |
| 5 | users.tenant_id |
| 6 | tenant_id on all eight data tables — the multi-tenancy cut-over |
| 7 | tenants.plan, billing_status, stripe ids |
| 11 | devices.token_generation |
| 12 | events.device_id, occupancy_samples.device_id |

Versions 8–10 are absent. Harmless, but don't assume a contiguous history.

---

## 4. Multi-tenancy rules

1. Every tenant-owned table carries `tenant_id`
2. Reads filter by the **token's** tenant, never the request body or path
3. Writes should stamp the caller's tenant — `add_source` now does; several legacy biometric write
   paths still use `local_tenant_id`
4. NULL means a shared demo feed — visible to every tenant
5. Camera ownership is derived from `cfg.sources[].tenant_id`, not a column on events

---

## 5. Retention and storage

Media on disk (`clips_dir`, `thumbs_dir`) or S3; `RetentionConfig.retention_days` drives the pruner
(default 30). Usage metering sums directory sizes and **counts all enabled cameras rather than the
tenant's**, so per-tenant usage is overstated in a multi-tenant deployment.

---

## 6. Known schema issues

| # | Issue | Impact |
|---|---|---|
| 1 | Legacy biometric writes use `local_tenant_id` | Cross-tenant misfiling |
| 2 | Two timestamp conventions | Easy to write a comparison that silently matches nothing |
| 3 | `devices.token_hash` unused (validation is signature + generation) | Dead column |
| 4 | No foreign keys | Orphans possible; cascades are application code |
| 5 | `faces.consent` has no enforcement | A face can be stored without consent recorded |
| 6 | Migration numbering gaps | Cosmetic |
| 7 | No index on `events.device_id` | Device-scoped queries scan |

---

## 7. Next schema work

1. Thread the caller's tenant through every write path
2. Gate `add_face` on `consent = 1`
3. Real foreign keys with cascades for biometric tables
4. Normalise on REAL epoch everywhere, or document `created_at` as display-only
5. `daily_counts(day, tenant_id, people_in, people_out, vehicles_in, vehicles_out)` if directional counting is built
