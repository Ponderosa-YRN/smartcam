# Backend Schema Document — SmartCam

**Status:** Draft 1 · **Date:** 2026-10-17
**Source of truth:** `smartcam/db.py`. Schema version **12**.

---

## 1. Storage engine and migration model

SQLAlchemy Core, one code path for two dialects:

| Dialect | When | DSN |
|---|---|---|
| SQLite (default) | Single-VPS deployment | `sqlite:///data/events.db` |
| PostgreSQL | `database_url` supplied | the given URL |

The DDL is written once and translated for Postgres by the single substitution
`INTEGER PRIMARY KEY AUTOINCREMENT` → `SERIAL PRIMARY KEY`. Everything else
(`TEXT`/`REAL`/`INTEGER`, `IF NOT EXISTS`, indexes) is valid in both.

**Migrations are additive and hand-listed** in `_column_migrations()` as
`(version, table, column, ddl)` tuples. Each is idempotent — it checks the column exists first —
and `LATEST_SCHEMA_VERSION` gates the run. There is no migration framework; a destructive change
needs a hand-written migration.

## 2. Conventions

- **Primary keys** — surrogate integer `id` everywhere. No natural keys except `users.username`
  and `tenants.slug`, both `UNIQUE`.
- **Timestamps** — `created_at` TEXT `YYYY-MM-DDTHH:MM:SS`; `ts` / `start_ts` / `end_ts` REAL Unix
  epoch seconds. Two conventions coexist; do not mix them in a single comparison.
- **Embeddings** — stored as JSON text, not a vector column. Similarity is computed in the agent
  layer after loading.
- **Booleans** — INTEGER 0/1 (`acknowledged`, `resolved`, `escalated`, `consent`).
- **Tenant key** — `tenant_id` INTEGER on every tenant-owned table, added by migration version 6.
  It is **nullable**: NULL means unassigned, and `ensure_default_tenant()` sweeps NULLs into the
  lowest-id tenant at startup.

## 3. Tables

### 3.1 `tenants` — the customer account

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| slug | TEXT UNIQUE NOT NULL | URL-safe, derived from company name |
| name | TEXT NOT NULL | Display name |
| plan | TEXT DEFAULT 'free' | `free` / `pro` / `enterprise` |
| billing_status | TEXT DEFAULT 'active' | |
| stripe_customer_id | TEXT DEFAULT '' | For the future payment integration |
| stripe_subscription_id | TEXT DEFAULT '' | |
| created_at | TEXT | |

Plan limits live in code (`smartcam/billing.py`): free = 2 cameras / 5 GB, pro = 25 / 100 GB,
enterprise = unlimited (-1).

### 3.2 `users` — human principals

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| username | TEXT UNIQUE NOT NULL | |
| password_hash | TEXT NOT NULL | scrypt, `scrypt$…` |
| role | TEXT NOT NULL DEFAULT 'viewer' | admin / security / manager / viewer (see `auth.ROLES`) |
| created_at | TEXT | |
| tenant_id | INTEGER | |

### 3.3 `sites` — physical locations under a tenant

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| tenant_id | INTEGER NOT NULL | |
| name | TEXT NOT NULL | |
| timezone | TEXT DEFAULT '' | |
| created_at | TEXT | |

### 3.4 `devices` — edge agents

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| tenant_id | INTEGER NOT NULL | |
| site_id | INTEGER | Nullable |
| name | TEXT NOT NULL | |
| token_hash | TEXT DEFAULT '' | |
| token_generation | INTEGER DEFAULT 0 | Bumped on rotation; invalidates older tokens |
| last_seen | REAL | Updated by heartbeat |
| created_at | TEXT | |

### 3.5 `invites` — pending user accounts

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| tenant_id | INTEGER NOT NULL | |
| email | TEXT NOT NULL | |
| role | TEXT NOT NULL DEFAULT 'viewer' | Applied at accept time |
| token | TEXT UNIQUE NOT NULL | 32-byte URL-safe |
| consumed | INTEGER DEFAULT 0 | Single use |
| expires_at | REAL | 7 days |
| created_at | TEXT | |

### 3.6 `events` — the central fact table

One row per assembled detection event.

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| camera_id | TEXT NOT NULL | Source id |
| camera_name | TEXT | Display name |
| start_ts / end_ts / duration | REAL | Epoch seconds |
| objects | TEXT | JSON array of detected classes |
| top_object | TEXT | Highest-confidence class |
| track_ids | TEXT | JSON array of ByteTrack ids |
| max_conf | REAL | |
| event_type | TEXT DEFAULT 'detection' | |
| clip_path / thumb_path | TEXT | Storage reference |
| summary | TEXT | AI-generated description |
| summary_model | TEXT | Which model produced it |
| plate | TEXT | Attached ALPR read |
| notified | INTEGER DEFAULT 0 | |
| acknowledged / resolved / escalated | INTEGER DEFAULT 0 | Triage state |
| assignee | TEXT | |
| tenant_id | INTEGER | |
| device_id | INTEGER | Source edge device |
| created_at | TEXT | |

Indexes: `idx_events_start (start_ts)`, `idx_events_camera (camera_id)`.
**Gap:** no index on `tenant_id`, which is now the predicate on nearly every read.

### 3.7 `plates` — licence plate reads

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| camera_id / camera_name | TEXT | |
| plate | TEXT | Normalised plate string |
| confidence | REAL | |
| crop_path | TEXT | Cropped plate image |
| ts | REAL | |
| tenant_id | INTEGER | |
| created_at | TEXT | |

Indexes: `idx_plates_ts`, `idx_plates_plate`.

### 3.8 `faces` — the biometric gallery

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| name | TEXT | |
| role | TEXT | Free-text label (staff, resident, …) |
| consent | INTEGER DEFAULT 0 | Consent recorded — **no workflow enforces it** |
| embedding | TEXT | JSON array |
| thumb_path | TEXT | |
| tenant_id | INTEGER | |
| created_at | TEXT | |

### 3.9 `face_matches` — a face seen in a frame

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| camera_id / camera_name | TEXT | |
| face_id | INTEGER | FK-by-convention to `faces.id` |
| name | TEXT | Denormalised for fast display |
| confidence | REAL | |
| embedding | TEXT | The observed embedding |
| thumb_path | TEXT | |
| ts | REAL | |
| tenant_id | INTEGER | |
| created_at | TEXT | |

Indexes: `idx_face_matches_ts`, `idx_face_matches_face`.

### 3.10 `identities` — re-ID gallery

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| name | TEXT | |
| face_id | INTEGER | Optional link to a known face |
| embedding | TEXT | JSON array; **gallery** of up to 10 embeddings per identity |
| thumb_path | TEXT | |
| tenant_id | INTEGER | |
| created_at | TEXT | |

### 3.11 `sightings` — where an identity has been seen

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| identity_id | INTEGER | |
| camera_id / camera_name | TEXT | |
| confidence | REAL | |
| thumb_path | TEXT | |
| ts | REAL | |
| tenant_id | INTEGER | |
| created_at | TEXT | |

Indexes: `idx_sightings_ts`, `idx_sightings_identity`.

### 3.12 `appearances` — raw re-ID tracks

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| camera_id / camera_name | TEXT | |
| track_id | INTEGER | ByteTrack id |
| embedding | TEXT | |
| thumb_path | TEXT | |
| ts | REAL | |
| tenant_id | INTEGER | |
| created_at | TEXT | |

Index `idx_appearances_ts`.

### 3.13 `occupancy_samples` — people and vehicle counts over time

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| ts | REAL | |
| people | INTEGER | |
| vehicles | INTEGER | |
| tenant_id | INTEGER | |
| device_id | INTEGER | |

Index `idx_occupancy_ts`.

### 3.14 `schema_meta` — migration bookkeeping

`key TEXT PRIMARY KEY, value TEXT`. Holds `schema_version`.

## 4. Migration history

| Version | Change |
|---|---|
| 1 | `events.event_type`, `events.plate` |
| 2 | `events.acknowledged`, `events.resolved`, `events.assignee` |
| 3 | `events.escalated` |
| 4 | `faces.consent` |
| 5 | `users.tenant_id` |
| 6 | `tenant_id` added to all eight data tables — the multi-tenancy cut-over |
| 7 | `tenants.plan`, `billing_status`, `stripe_customer_id`, `stripe_subscription_id` |
| 11 | `devices.token_generation` — token rotation |
| 12 | `events.device_id`, `occupancy_samples.device_id` — edge attribution |

(8, 9, 10 are unrepresented in the list; version numbering has gaps, which is harmless but should
be understood before assuming a contiguous history.)

## 5. Multi-tenancy rules

1. **Every tenant-owned table carries `tenant_id`.** The eight data tables were migrated in
   version 6.
2. **Reads must filter by `tenant_id`**, taken from the authenticated token — never from the
   request body or path.
3. **Writes should stamp the caller's tenant.** ⚠ Several write paths currently stamp
   `self.local_tenant_id` (the process-wide tenant) instead: `add_plate`, `add_face`,
   `add_face_match`, `add_appearance`, `add_identity`, `add_sighting`. In a single-tenant
   deployment this is invisible; in a multi-tenant one it files another tenant's data under the
   default tenant.
4. **NULL `tenant_id`** is legacy/unassigned. `ensure_default_tenant()` reassigns NULL rows to the
   lowest-id tenant at each startup.
5. **Camera ownership** is not a column on `events` — it is derived from `cfg.sources[].tenant_id`.
   A camera with no `tenant_id` is a shared demo feed visible to every tenant.

## 6. Retention and storage

Media is on disk, not in the database: `cfg.clips_dir`, `cfg.thumbs_dir`, optionally S3 via
`StorageConfig`. `RetentionConfig` drives pruning. Usage metering
(`billing.tenant_usage`) sums directory sizes — note it counts **all** enabled cameras rather than
filtering by tenant, so per-tenant usage is currently overstated in a multi-tenant deployment.

## 7. Known schema issues

| # | Issue | Impact |
|---|---|---|
| 1 | No index on `events.tenant_id` or `plates.tenant_id` | Every tenant-scoped list scans |
| 2 | Two timestamp conventions (TEXT vs REAL) | Easy to write a comparison that silently matches nothing |
| 3 | `token_hash` is present but device tokens are validated by signature + generation | Column is effectively unused; either use it or drop it |
| 4 | No foreign keys declared | Orphans are possible; cascade deletes are done in application code |
| 5 | `faces.consent` has no enforcement | A biometric can be stored without consent |
| 6 | Write attribution uses the process tenant (§5.3) | Cross-tenant misfiling |
| 7 | Version numbers skip 8–10 | Harmless, but confusing |
| 8 | No index on `events.device_id` | Device-scoped queries scan |

## 8. Recommended next schema work

1. Add `(tenant_id, start_ts)` composite indexes to `events` and `plates`.
2. Thread the caller's tenant through every write path instead of `local_tenant_id`.
3. Add a consent gate before `add_face` — refuse to store an embedding without `consent = 1`.
4. Introduce real foreign keys with `ON DELETE CASCADE` for the biometric tables.
5. Normalise on REAL epoch seconds and migrate the TEXT `created_at` columns, or formally document
   that `created_at` is display-only.
