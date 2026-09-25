"""Event store for SmartCam (SQLAlchemy Core: SQLite by default, Postgres-ready).

The default backend is SQLite (same on-disk format as before). Pass database_url
(pointing at postgresql+psycopg://...) to run on Postgres. The query layer uses
named parameters and RETURNING id so both dialects work; DDL is translated at
runtime (SQLite AUTOINCREMENT -> Postgres SERIAL).
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import create_engine, text

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    camera_id TEXT NOT NULL,
    camera_name TEXT,
    start_ts REAL,
    end_ts REAL,
    duration REAL,
    objects TEXT,
    top_object TEXT,
    track_ids TEXT,
    max_conf REAL,
    event_type TEXT DEFAULT 'detection',
    clip_path TEXT,
    thumb_path TEXT,
    summary TEXT,
    summary_model TEXT,
    plate TEXT,
    notified INTEGER DEFAULT 0,
    acknowledged INTEGER DEFAULT 0,
    resolved INTEGER DEFAULT 0,
    escalated INTEGER DEFAULT 0,
    assignee TEXT,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_start ON events(start_ts);
CREATE INDEX IF NOT EXISTS idx_events_camera ON events(camera_id);

CREATE TABLE IF NOT EXISTS plates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    camera_id TEXT,
    camera_name TEXT,
    plate TEXT,
    confidence REAL,
    crop_path TEXT,
    ts REAL,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_plates_ts ON plates(ts);
CREATE INDEX IF NOT EXISTS idx_plates_plate ON plates(plate);

CREATE TABLE IF NOT EXISTS faces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    role TEXT,
    consent INTEGER DEFAULT 0,
    embedding TEXT,
    thumb_path TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS face_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    camera_id TEXT,
    camera_name TEXT,
    face_id INTEGER,
    name TEXT,
    confidence REAL,
    embedding TEXT,
    thumb_path TEXT,
    ts REAL,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_face_matches_ts ON face_matches(ts);
CREATE INDEX IF NOT EXISTS idx_face_matches_face ON face_matches(face_id);

CREATE TABLE IF NOT EXISTS appearances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    camera_id TEXT,
    camera_name TEXT,
    track_id INTEGER,
    embedding TEXT,
    thumb_path TEXT,
    ts REAL,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_appearances_ts ON appearances(ts);

CREATE TABLE IF NOT EXISTS identities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    face_id INTEGER,
    embedding TEXT,
    thumb_path TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS sightings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identity_id INTEGER,
    camera_id TEXT,
    camera_name TEXT,
    confidence REAL,
    thumb_path TEXT,
    ts REAL,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_sightings_ts ON sightings(ts);
CREATE INDEX IF NOT EXISTS idx_sightings_identity ON sightings(identity_id);

CREATE TABLE IF NOT EXISTS occupancy_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL,
    people INTEGER,
    vehicles INTEGER
);
CREATE INDEX IF NOT EXISTS idx_occupancy_ts ON occupancy_samples(ts);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'viewer',
    created_at TEXT,
    tenant_id INTEGER
);

CREATE TABLE IF NOT EXISTS tenants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    plan TEXT DEFAULT 'free',
    billing_status TEXT DEFAULT 'active',
    stripe_customer_id TEXT DEFAULT '',
    stripe_subscription_id TEXT DEFAULT '',
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS sites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    timezone TEXT DEFAULT '',
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    site_id INTEGER,
    name TEXT NOT NULL,
    token_hash TEXT DEFAULT '',
    token_generation INTEGER DEFAULT 0,
    last_seen REAL,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS invites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    email TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'viewer',
    token TEXT NOT NULL UNIQUE,
    consumed INTEGER DEFAULT 0,
    expires_at REAL,
    created_at TEXT
);
"""

LATEST_SCHEMA_VERSION = 12

# Postgres DDL: translate the one SQLite-ism (AUTOINCREMENT) to SERIAL. The rest
# of the DDL (TEXT / REAL / INTEGER / CREATE ... IF NOT EXISTS / indexes) is valid
# in both dialects.
_POSTGRES_SCHEMA = _SCHEMA.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")


def _column_migrations():
    """(version, table, column, ddl) — ordered additive column migrations.

    Append new entries here (and bump LATEST_SCHEMA_VERSION) when the schema
    changes. Each migration is idempotent (it checks the column exists first).
    """
    return [
        (1, "events", "event_type", "ALTER TABLE events ADD COLUMN event_type TEXT DEFAULT 'detection'"),
        (1, "events", "plate", "ALTER TABLE events ADD COLUMN plate TEXT"),
        (2, "events", "acknowledged", "ALTER TABLE events ADD COLUMN acknowledged INTEGER DEFAULT 0"),
        (2, "events", "resolved", "ALTER TABLE events ADD COLUMN resolved INTEGER DEFAULT 0"),
        (2, "events", "assignee", "ALTER TABLE events ADD COLUMN assignee TEXT"),
        (3, "events", "escalated", "ALTER TABLE events ADD COLUMN escalated INTEGER DEFAULT 0"),
        (4, "faces", "consent", "ALTER TABLE faces ADD COLUMN consent INTEGER DEFAULT 0"),
        (5, "users", "tenant_id", "ALTER TABLE users ADD COLUMN tenant_id INTEGER"),
        (6, "events", "tenant_id", "ALTER TABLE events ADD COLUMN tenant_id INTEGER"),
        (6, "plates", "tenant_id", "ALTER TABLE plates ADD COLUMN tenant_id INTEGER"),
        (6, "faces", "tenant_id", "ALTER TABLE faces ADD COLUMN tenant_id INTEGER"),
        (6, "face_matches", "tenant_id", "ALTER TABLE face_matches ADD COLUMN tenant_id INTEGER"),
        (6, "appearances", "tenant_id", "ALTER TABLE appearances ADD COLUMN tenant_id INTEGER"),
        (6, "identities", "tenant_id", "ALTER TABLE identities ADD COLUMN tenant_id INTEGER"),
        (6, "sightings", "tenant_id", "ALTER TABLE sightings ADD COLUMN tenant_id INTEGER"),
        (6, "occupancy_samples", "tenant_id", "ALTER TABLE occupancy_samples ADD COLUMN tenant_id INTEGER"),
        (7, "tenants", "plan", "ALTER TABLE tenants ADD COLUMN plan TEXT DEFAULT 'free'"),
        (7, "tenants", "billing_status", "ALTER TABLE tenants ADD COLUMN billing_status TEXT DEFAULT 'active'"),
        (7, "tenants", "stripe_customer_id", "ALTER TABLE tenants ADD COLUMN stripe_customer_id TEXT DEFAULT ''"),
        (7, "tenants", "stripe_subscription_id", "ALTER TABLE tenants ADD COLUMN stripe_subscription_id TEXT DEFAULT ''"),
        (11, "devices", "token_generation", "ALTER TABLE devices ADD COLUMN token_generation INTEGER DEFAULT 0"),
        (12, "events", "device_id", "ALTER TABLE events ADD COLUMN device_id INTEGER"),
        (12, "occupancy_samples", "device_id", "ALTER TABLE occupancy_samples ADD COLUMN device_id INTEGER"),
    ]


class EventStore:
    """Thread-safe event store (SQLite default; Postgres via database_url)."""

    def __init__(self, db_path=None, database_url=None):
        self._lock = threading.RLock()
        if database_url:
            self._url = str(database_url)
            self._is_sqlite = self._url.startswith("sqlite")
            self.db_path = None
        else:
            p = Path(db_path) if db_path else Path("data/events.db")
            p.parent.mkdir(parents=True, exist_ok=True)
            self.db_path = p
            self._url = "sqlite:///" + str(p)
            self._is_sqlite = True
        connect_args = {"check_same_thread": False} if self._is_sqlite else {}
        self._engine = create_engine(self._url, connect_args=connect_args)
        self._conn = self._engine.connect()

        with self._lock:
            script = _SCHEMA if self._is_sqlite else _POSTGRES_SCHEMA
            for stmt in script.split(";"):
                s = stmt.strip()
                if s:
                    self._conn.execute(text(s))
            self._conn.commit()
            for (_ver, table, col, ddl) in _column_migrations():
                if col not in self._table_columns(table):
                    self._conn.execute(text(ddl))
                    self._conn.commit()
            self._set_schema_version(LATEST_SCHEMA_VERSION)
            self._conn.commit()
        self.local_tenant_id = self.ensure_default_tenant()

    # -- schema helpers ---------------------------------------------------
    def _table_columns(self, table: str) -> set[str]:
        if self._is_sqlite:
            rows = self._conn.execute(text("PRAGMA table_info(" + table + ")")).fetchall()
            return {r[1] for r in rows}
        rows = self._conn.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name = :t"), {"t": table}
        ).fetchall()
        return {r[0] for r in rows}

    def _schema_version(self) -> int:
        if self._is_sqlite:
            row = self._conn.execute(text("PRAGMA user_version")).fetchone()
            return int(row[0])
        self._conn.execute(text("CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT)"))
        row = self._conn.execute(text("SELECT value FROM schema_meta WHERE key = 'schema_version'")).fetchone()
        return int(row[0]) if row else 0

    def _set_schema_version(self, version: int) -> None:
        if self._is_sqlite:
            self._conn.execute(text("PRAGMA user_version = " + str(version)))
        else:
            self._conn.execute(text("CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT)"))
            self._conn.execute(
                text("INSERT INTO schema_meta (key, value) VALUES ('schema_version', :v) ON CONFLICT (key) DO UPDATE SET value = :v"),
                {"v": str(version)},
            )

    # -- users -------------------------------------------------------------
    def create_user(self, username: str, password_hash: str, role: str = "viewer", tenant_id: int | None = None) -> int:
        with self._lock:
            res = self._conn.execute(
                text("INSERT INTO users (username, password_hash, role, tenant_id, created_at) VALUES (:u, :p, :r, :t, :c) RETURNING id"),
                {"u": username, "p": password_hash, "r": role, "t": tenant_id, "c": time.strftime("%Y-%m-%dT%H:%M:%S")},
            )
            uid = res.fetchone()[0]
            self._conn.commit()
            return int(uid)

    def get_user(self, user_id: int) -> dict | None:
        with self._lock:
            row = self._conn.execute(text("SELECT * FROM users WHERE id = :id"), {"id": user_id}).fetchone()
            return dict(row._mapping) if row else None

    def get_user_by_username(self, username: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(text("SELECT * FROM users WHERE username = :u"), {"u": username}).fetchone()
            return dict(row._mapping) if row else None

    def list_users(self, tenant_id: int | None = None) -> list[dict]:
        with self._lock:
            if tenant_id is None:
                rows = self._conn.execute(text("SELECT * FROM users ORDER BY id")).fetchall()
            else:
                rows = self._conn.execute(text("SELECT * FROM users WHERE tenant_id = :t ORDER BY id"), {"t": tenant_id}).fetchall()
            return [dict(r._mapping) for r in rows]

    def update_user(self, user_id: int, **fields: Any) -> None:
        allowed = {"username", "password_hash", "role"}
        sets: list[str] = []
        params: dict[str, Any] = {"id": user_id}
        for key, value in fields.items():
            if key in allowed:
                sets.append(key + " = :" + key)
                params[key] = value
        if not sets:
            return
        with self._lock:
            self._conn.execute(text("UPDATE users SET " + ", ".join(sets) + " WHERE id = :id"), params)
            self._conn.commit()

    def delete_user(self, user_id: int) -> None:
        with self._lock:
            self._conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
            self._conn.commit()

    def count_users(self) -> int:
        with self._lock:
            row = self._conn.execute(text("SELECT COUNT(*) AS n FROM users")).fetchone()
            return int(row._mapping["n"])

    # -- tenants / sites / devices ----------------------------------------
    def create_tenant(self, slug: str, name: str, plan: str = "free") -> int:
        with self._lock:
            res = self._conn.execute(
                text("INSERT INTO tenants (slug, name, plan, created_at) VALUES (:s, :n, :p, :c) RETURNING id"),
                {"s": slug, "n": name, "p": plan, "c": time.strftime("%Y-%m-%dT%H:%M:%S")},
            )
            tid = res.fetchone()[0]
            self._conn.commit()
            return int(tid)

    def get_tenant(self, tenant_id: int) -> dict | None:
        with self._lock:
            row = self._conn.execute(text("SELECT * FROM tenants WHERE id = :id"), {"id": tenant_id}).fetchone()
            return dict(row._mapping) if row else None

    def get_tenant_by_slug(self, slug: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(text("SELECT * FROM tenants WHERE slug = :s"), {"s": slug}).fetchone()
            return dict(row._mapping) if row else None

    def list_tenants(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(text("SELECT * FROM tenants ORDER BY id")).fetchall()
            return [dict(r._mapping) for r in rows]

    def update_tenant(self, tenant_id: int, **fields: Any) -> None:
        allowed = {"slug", "name", "plan", "billing_status", "stripe_customer_id", "stripe_subscription_id"}
        sets: list[str] = []
        params: dict[str, Any] = {"id": tenant_id}
        for key, value in fields.items():
            if key in allowed:
                sets.append(key + " = :" + key)
                params[key] = value
        if not sets:
            return
        with self._lock:
            self._conn.execute(text("UPDATE tenants SET " + ", ".join(sets) + " WHERE id = :id"), params)
            self._conn.commit()

    def delete_tenant(self, tenant_id: int) -> None:
        with self._lock:
            self._conn.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})
            self._conn.commit()

    def count_tenants(self) -> int:
        with self._lock:
            row = self._conn.execute(text("SELECT COUNT(*) AS n FROM tenants")).fetchone()
            return int(row._mapping["n"])

    def ensure_default_tenant(self) -> int:
        """Create a 'default' tenant if none exist and backfill legacy users."""
        with self._lock:
            row = self._conn.execute(text("SELECT id FROM tenants ORDER BY id LIMIT 1")).fetchone()
            if row is None:
                res = self._conn.execute(
                    text("INSERT INTO tenants (slug, name, created_at) VALUES (:s, :n, :c) RETURNING id"),
                    {"s": "default", "n": "Default", "c": time.strftime("%Y-%m-%dT%H:%M:%S")},
                )
                tid = int(res.fetchone()[0])
                self._conn.commit()
            else:
                tid = int(row._mapping["id"])
            self._conn.execute(text("UPDATE users SET tenant_id = :t WHERE tenant_id IS NULL"), {"t": tid})
            for table in ("events", "plates", "faces", "face_matches", "appearances", "identities", "sightings", "occupancy_samples"):
                self._conn.execute(text("UPDATE " + table + " SET tenant_id = :t WHERE tenant_id IS NULL"), {"t": tid})
            self._conn.commit()
            return tid

    def create_site(self, tenant_id: int, name: str, timezone: str = "") -> int:
        with self._lock:
            res = self._conn.execute(
                text("INSERT INTO sites (tenant_id, name, timezone, created_at) VALUES (:t, :n, :z, :c) RETURNING id"),
                {"t": tenant_id, "n": name, "z": timezone, "c": time.strftime("%Y-%m-%dT%H:%M:%S")},
            )
            sid = res.fetchone()[0]
            self._conn.commit()
            return int(sid)

    def list_sites(self, tenant_id: int | None = None) -> list[dict]:
        with self._lock:
            if tenant_id is None:
                rows = self._conn.execute(text("SELECT * FROM sites ORDER BY id")).fetchall()
            else:
                rows = self._conn.execute(text("SELECT * FROM sites WHERE tenant_id = :t ORDER BY id"), {"t": tenant_id}).fetchall()
            return [dict(r._mapping) for r in rows]

    def delete_site(self, site_id: int) -> None:
        with self._lock:
            self._conn.execute(text("DELETE FROM sites WHERE id = :id"), {"id": site_id})
            self._conn.commit()

    def create_device(self, tenant_id: int, name: str, site_id: int | None = None) -> int:
        with self._lock:
            res = self._conn.execute(
                text("INSERT INTO devices (tenant_id, site_id, name, created_at) VALUES (:t, :s, :n, :c) RETURNING id"),
                {"t": tenant_id, "s": site_id, "n": name, "c": time.strftime("%Y-%m-%dT%H:%M:%S")},
            )
            did = res.fetchone()[0]
            self._conn.commit()
            return int(did)

    def list_devices(self, tenant_id: int | None = None) -> list[dict]:
        with self._lock:
            if tenant_id is None:
                rows = self._conn.execute(text("SELECT * FROM devices ORDER BY id")).fetchall()
            else:
                rows = self._conn.execute(text("SELECT * FROM devices WHERE tenant_id = :t ORDER BY id"), {"t": tenant_id}).fetchall()
            return [dict(r._mapping) for r in rows]

    def delete_device(self, device_id: int) -> None:
        with self._lock:
            self._conn.execute(text("DELETE FROM devices WHERE id = :id"), {"id": device_id})
            self._conn.commit()

    def get_device(self, device_id: int) -> dict | None:
        with self._lock:
            row = self._conn.execute(text("SELECT * FROM devices WHERE id = :id"), {"id": device_id}).fetchone()
            return dict(row._mapping) if row else None

    def bump_device_token_generation(self, device_id: int) -> int:
        """Increment a device's token generation (invalidates old tokens) and return it."""
        with self._lock:
            self._conn.execute(text("UPDATE devices SET token_generation = token_generation + 1 WHERE id = :id"), {"id": device_id})
            self._conn.commit()
            row = self._conn.execute(text("SELECT token_generation FROM devices WHERE id = :id"), {"id": device_id}).fetchone()
            return int(row._mapping["token_generation"]) if row else 0

    def touch_device(self, device_id: int) -> None:
        with self._lock:
            self._conn.execute(text("UPDATE devices SET last_seen = :ts WHERE id = :id"), {"ts": time.time(), "id": device_id})
            self._conn.commit()

    # -- invites -----------------------------------------------------------
    def create_invite(self, tenant_id: int, email: str, role: str, token: str, expires_at: float) -> int:
        with self._lock:
            res = self._conn.execute(
                text("INSERT INTO invites (tenant_id, email, role, token, expires_at, created_at) VALUES (:t, :e, :r, :tok, :x, :c) RETURNING id"),
                {"t": tenant_id, "e": email, "r": role, "tok": token, "x": expires_at, "c": time.strftime("%Y-%m-%dT%H:%M:%S")},
            )
            iid = res.fetchone()[0]
            self._conn.commit()
            return int(iid)

    def get_invite_by_token(self, token: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(text("SELECT * FROM invites WHERE token = :t"), {"t": token}).fetchone()
            return dict(row._mapping) if row else None

    def list_invites(self, tenant_id: int | None = None) -> list[dict]:
        with self._lock:
            if tenant_id is None:
                rows = self._conn.execute(text("SELECT * FROM invites ORDER BY id DESC")).fetchall()
            else:
                rows = self._conn.execute(text("SELECT * FROM invites WHERE tenant_id = :t ORDER BY id DESC"), {"t": tenant_id}).fetchall()
            return [dict(r._mapping) for r in rows]

    def consume_invite(self, invite_id: int) -> None:
        with self._lock:
            self._conn.execute(text("UPDATE invites SET consumed = 1 WHERE id = :id"), {"id": invite_id})
            self._conn.commit()

    def delete_invite(self, invite_id: int) -> None:
        with self._lock:
            self._conn.execute(text("DELETE FROM invites WHERE id = :id"), {"id": invite_id})
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            finally:
                self._engine.dispose()

    def schema_version(self) -> int:
        with self._lock:
            return self._schema_version()

    # -- writes -----------------------------------------------------------
    def add_event(self, event: dict[str, Any], *, tenant_id: int | None = None, device_id: int | None = None) -> int:
        tid = tenant_id if tenant_id is not None else event.get("tenant_id", self.local_tenant_id)
        did = device_id if device_id is not None else event.get("device_id")
        with self._lock:
            res = self._conn.execute(
                text("""
                INSERT INTO events
                  (camera_id, camera_name, start_ts, end_ts, duration, objects,
                   top_object, track_ids, max_conf, event_type, clip_path, thumb_path, created_at, tenant_id, device_id)
                VALUES
                  (:camera_id, :camera_name, :start_ts, :end_ts, :duration, :objects,
                   :top_object, :track_ids, :max_conf, :event_type, :clip_path, :thumb_path, :created_at, :tenant_id, :device_id)
                RETURNING id
                """),
                {
                    "camera_id": event.get("camera_id", "camera-1"),
                    "camera_name": event.get("camera_name", ""),
                    "start_ts": event.get("start_ts"),
                    "end_ts": event.get("end_ts"),
                    "duration": event.get("duration"),
                    "objects": json.dumps(event.get("objects", [])),
                    "top_object": event.get("top_object"),
                    "track_ids": json.dumps(event.get("track_ids", [])),
                    "max_conf": event.get("max_conf"),
                    "event_type": event.get("event_type", "detection"),
                    "clip_path": event.get("clip_path"),
                    "thumb_path": event.get("thumb_path"),
                    "created_at": event.get("created_at"),
                    "tenant_id": tid,
                    "device_id": did,
                },
            )
            eid = res.fetchone()[0]
            self._conn.commit()
            return int(eid)

    def update_event(self, event_id: int, **fields: Any) -> None:
        if not fields:
            return
        allowed = {
            "end_ts", "duration", "objects", "top_object", "track_ids",
            "max_conf", "event_type", "clip_path", "thumb_path", "summary", "summary_model", "plate", "notified", "acknowledged", "resolved", "escalated", "assignee",
        }
        sets = []
        params: dict[str, Any] = {"id": event_id}
        for key, value in fields.items():
            if key not in allowed:
                continue
            if key in ("objects", "track_ids") and not isinstance(value, str):
                value = json.dumps(value)
            sets.append(key + " = :" + key)
            params[key] = value
        if not sets:
            return
        with self._lock:
            self._conn.execute(text("UPDATE events SET " + ", ".join(sets) + " WHERE id = :id"), params)
            self._conn.commit()

    def mark_notified(self, event_id: int) -> None:
        self.update_event(event_id, notified=1)

    def acknowledge(self, event_id: int) -> None:
        self.update_event(event_id, acknowledged=1)

    def resolve(self, event_id: int) -> None:
        self.update_event(event_id, resolved=1)

    def assign(self, event_id: int, user: str) -> None:
        self.update_event(event_id, assignee=user)

    def escalate(self, event_id: int) -> None:
        self.update_event(event_id, escalated=1)

    def list_open_alerts(self, limit: int = 200, tenant_id: int | None = None) -> list[dict[str, Any]]:
        with self._lock:
            if tenant_id is None:
                rows = self._conn.execute(
                    text("SELECT * FROM events WHERE resolved = 0 ORDER BY escalated DESC, start_ts DESC LIMIT :l"), {"l": limit}
                ).fetchall()
            else:
                rows = self._conn.execute(
                    text("SELECT * FROM events WHERE resolved = 0 AND tenant_id = :t ORDER BY escalated DESC, start_ts DESC LIMIT :l"),
                    {"t": tenant_id, "l": limit},
                ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # -- reads ------------------------------------------------------------
    def get_event(self, event_id: int) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(text("SELECT * FROM events WHERE id = :id"), {"id": event_id}).fetchone()
        return self._row_to_dict(row) if row else None

    def list_events(
        self,
        limit: int = 100,
        offset: int = 0,
        camera_id: str | None = None,
        since: float | None = None,
        until: float | None = None,
        event_type: str | None = None,
        tenant_id: int | None = None,
        order: str = "DESC",
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: dict[str, Any] = {}
        if camera_id:
            clauses.append("camera_id = :camera_id")
            params["camera_id"] = camera_id
        if event_type:
            clauses.append("event_type = :event_type")
            params["event_type"] = event_type
        if tenant_id is not None:
            clauses.append("tenant_id = :tenant_id")
            params["tenant_id"] = tenant_id
        if since is not None:
            clauses.append("start_ts >= :since")
            params["since"] = since
        if until is not None:
            clauses.append("start_ts <= :until")
            params["until"] = until
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        order_sql = "DESC" if order.upper() == "DESC" else "ASC"
        params["limit"] = limit
        params["offset"] = offset
        with self._lock:
            rows = self._conn.execute(
                text("SELECT * FROM events " + where + " ORDER BY start_ts " + order_sql + " LIMIT :limit OFFSET :offset"),
                params,
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def count_events(self, tenant_id: int | None = None) -> int:
        with self._lock:
            if tenant_id is None:
                row = self._conn.execute(text("SELECT COUNT(*) AS n FROM events")).fetchone()
            else:
                row = self._conn.execute(text("SELECT COUNT(*) AS n FROM events WHERE tenant_id = :t"), {"t": tenant_id}).fetchone()
        return int(row._mapping["n"])

    def purge_older_than(self, ts: float) -> dict[str, list[str]]:
        """Delete events older than *ts*; return the clip/thumb paths to unlink."""
        with self._lock:
            rows = self._conn.execute(text("SELECT clip_path, thumb_path FROM events WHERE start_ts < :ts"), {"ts": ts}).fetchall()
            self._conn.execute(text("DELETE FROM events WHERE start_ts < :ts"), {"ts": ts})
            self._conn.commit()
        clips = [r._mapping["clip_path"] for r in rows if r._mapping["clip_path"]]
        thumbs = [r._mapping["thumb_path"] for r in rows if r._mapping["thumb_path"]]
        return {"clips": clips, "thumbs": thumbs}

    def count_by_type(self, since: float | None = None, tenant_id: int | None = None) -> dict[str, int]:
        q = "SELECT event_type, COUNT(*) AS n FROM events"
        clauses: list[str] = []
        params: dict[str, Any] = {}
        if since is not None:
            clauses.append("start_ts >= :since")
            params["since"] = since
        if tenant_id is not None:
            clauses.append("tenant_id = :tenant_id")
            params["tenant_id"] = tenant_id
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        q += " GROUP BY event_type"
        with self._lock:
            rows = self._conn.execute(text(q), params).fetchall()
        return {r._mapping["event_type"] or "detection": int(r._mapping["n"]) for r in rows}

    # -- plates (ANPR) ----------------------------------------------------
    def insert_plate(self, plate: dict[str, Any]) -> int:
        with self._lock:
            res = self._conn.execute(
                text("""
                INSERT INTO plates (camera_id, camera_name, plate, confidence, crop_path, ts, created_at, tenant_id)
                VALUES (:camera_id, :camera_name, :plate, :confidence, :crop_path, :ts, :created_at, :tenant_id)
                RETURNING id
                """),
                {
                    "camera_id": plate.get("camera_id", ""),
                    "camera_name": plate.get("camera_name", ""),
                    "plate": plate.get("plate", ""),
                    "confidence": plate.get("confidence"),
                    "crop_path": plate.get("crop_path"),
                    "ts": plate.get("ts"),
                    "created_at": plate.get("created_at"),
                    "tenant_id": self.local_tenant_id,
                },
            )
            pid = res.fetchone()[0]
            self._conn.commit()
            return int(pid)

    def list_plates(self, limit: int = 100, camera_id: str | None = None, since: float | None = None, until: float | None = None, tenant_id: int | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: dict[str, Any] = {}
        if camera_id:
            clauses.append("camera_id = :camera_id")
            params["camera_id"] = camera_id
        if tenant_id is not None:
            clauses.append("tenant_id = :tenant_id")
            params["tenant_id"] = tenant_id
        if since is not None:
            clauses.append("ts >= :since")
            params["since"] = since
        if until is not None:
            clauses.append("ts <= :until")
            params["until"] = until
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params["limit"] = limit
        with self._lock:
            rows = self._conn.execute(text("SELECT * FROM plates " + where + " ORDER BY ts DESC LIMIT :limit"), params).fetchall()
        return [dict(r._mapping) for r in rows]

    def search_plates(self, term: str, limit: int = 100) -> list[dict[str, Any]]:
        t = "%" + term.strip().upper() + "%"
        with self._lock:
            rows = self._conn.execute(
                text("SELECT * FROM plates WHERE upper(plate) LIKE :p ORDER BY ts DESC LIMIT :l"), {"p": t, "l": limit}
            ).fetchall()
        return [dict(r._mapping) for r in rows]

    def recent_plate(self, camera_id: str, since_ts: float, until_ts: float) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                text("SELECT * FROM plates WHERE camera_id = :c AND ts >= :s AND ts <= :e ORDER BY ts DESC LIMIT 1"),
                {"c": camera_id, "s": since_ts, "e": until_ts},
            ).fetchone()
        return dict(row._mapping) if row else None

    # -- faces (recognition) ---------------------------------------------
    def add_face(self, name: str, role: str, embedding, thumb_path: str | None = None, consent: int = 0) -> int:
        emb = json.dumps([float(x) for x in embedding])
        with self._lock:
            res = self._conn.execute(
                text("INSERT INTO faces (name, role, consent, embedding, thumb_path, created_at, tenant_id) VALUES (:n, :r, :c, :e, :t, :a, :tid) RETURNING id"),
                {"n": name, "r": role, "c": 1 if consent else 0, "e": emb, "t": thumb_path, "a": time.strftime("%Y-%m-%dT%H:%M:%S"), "tid": self.local_tenant_id},
            )
            fid = res.fetchone()[0]
            self._conn.commit()
            return int(fid)

    def delete_person(self, name: str | None = None, face_id: int | None = None) -> None:
        """Delete a person's data: face, face matches, identity, and sightings."""
        with self._lock:
            if face_id is None and name:
                row = self._conn.execute(text("SELECT id FROM faces WHERE name = :n"), {"n": name}).fetchone()
                face_id = row._mapping["id"] if row else None
            if face_id is None:
                return
            ident = self._conn.execute(text("SELECT id FROM identities WHERE face_id = :f"), {"f": face_id}).fetchone()
            self._conn.execute(text("DELETE FROM faces WHERE id = :f"), {"f": face_id})
            self._conn.execute(text("DELETE FROM face_matches WHERE face_id = :f"), {"f": face_id})
            if ident is not None:
                self._conn.execute(text("DELETE FROM identities WHERE id = :i"), {"i": ident._mapping["id"]})
                self._conn.execute(text("DELETE FROM sightings WHERE identity_id = :i"), {"i": ident._mapping["id"]})
            self._conn.commit()

    def list_faces(self, tenant_id: int | None = None) -> list[dict[str, Any]]:
        with self._lock:
            if tenant_id is None:
                rows = self._conn.execute(text("SELECT * FROM faces ORDER BY name")).fetchall()
            else:
                rows = self._conn.execute(text("SELECT * FROM faces WHERE tenant_id = :t ORDER BY name"), {"t": tenant_id}).fetchall()
        out = []
        for r in rows:
            d = dict(r._mapping)
            d["embedding"] = json.loads(d["embedding"]) if d.get("embedding") else []
            out.append(d)
        return out

    def delete_face(self, face_id: int) -> None:
        with self._lock:
            self._conn.execute(text("DELETE FROM faces WHERE id = :id"), {"id": face_id})
            self._conn.commit()

    def add_face_match(self, match: dict[str, Any]) -> int:
        emb = json.dumps([float(x) for x in match.get("embedding", [])])
        with self._lock:
            res = self._conn.execute(
                text("INSERT INTO face_matches (camera_id, camera_name, face_id, name, confidence, embedding, thumb_path, ts, created_at, tenant_id) VALUES (:c, :cn, :f, :n, :cf, :e, :t, :ts, :a, :tid) RETURNING id"),
                {
                    "c": match.get("camera_id", ""), "cn": match.get("camera_name", ""), "f": match.get("face_id"),
                    "n": match.get("name", "unknown"), "cf": match.get("confidence"), "e": emb,
                    "t": match.get("thumb_path"), "ts": match.get("ts"), "a": time.strftime("%Y-%m-%dT%H:%M:%S"), "tid": self.local_tenant_id,
                },
            )
            mid = res.fetchone()[0]
            self._conn.commit()
            return int(mid)

    def list_face_matches(self, limit: int = 100, face_id: int | None = None, name: str | None = None, tenant_id: int | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: dict[str, Any] = {}
        if face_id is not None:
            clauses.append("face_id = :face_id")
            params["face_id"] = face_id
        if name:
            clauses.append("name = :name")
            params["name"] = name
        if tenant_id is not None:
            clauses.append("tenant_id = :tenant_id")
            params["tenant_id"] = tenant_id
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params["limit"] = limit
        with self._lock:
            rows = self._conn.execute(text("SELECT * FROM face_matches " + where + " ORDER BY ts DESC LIMIT :limit"), params).fetchall()
        out = []
        for r in rows:
            d = dict(r._mapping)
            d["embedding"] = json.loads(d["embedding"]) if d.get("embedding") else []
            out.append(d)
        return out

    # -- ReID (cross-camera person tracking) -----------------------------
    def add_appearance(self, camera_id, camera_name, track_id, embedding, thumb_path, ts) -> int:
        emb = json.dumps([float(x) for x in embedding])
        with self._lock:
            res = self._conn.execute(
                text("INSERT INTO appearances (camera_id, camera_name, track_id, embedding, thumb_path, ts, created_at, tenant_id) VALUES (:c, :cn, :t, :e, :th, :ts, :a, :tid) RETURNING id"),
                {"c": camera_id, "cn": camera_name, "t": track_id, "e": emb, "th": thumb_path, "ts": ts, "a": time.strftime("%Y-%m-%dT%H:%M:%S"), "tid": self.local_tenant_id},
            )
            aid = res.fetchone()[0]
            self._conn.commit()
            return int(aid)

    def recent_appearance(self, camera_id: str, since_ts: float, until_ts: float) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                text("SELECT * FROM appearances WHERE camera_id = :c AND ts >= :s AND ts <= :e ORDER BY ts DESC LIMIT 1"),
                {"c": camera_id, "s": since_ts, "e": until_ts},
            ).fetchone()
        if not row:
            return None
        d = dict(row._mapping)
        d["embedding"] = json.loads(d["embedding"]) if d.get("embedding") else []
        return d

    def add_identity(self, name: str, face_id: int | None, embedding, thumb_path: str | None = None) -> int:
        emb = json.dumps([[float(x) for x in embedding]])
        with self._lock:
            res = self._conn.execute(
                text("INSERT INTO identities (name, face_id, embedding, thumb_path, created_at, tenant_id) VALUES (:n, :f, :e, :t, :a, :tid) RETURNING id"),
                {"n": name, "f": face_id, "e": emb, "t": thumb_path, "a": time.strftime("%Y-%m-%dT%H:%M:%S"), "tid": self.local_tenant_id},
            )
            iid = res.fetchone()[0]
            self._conn.commit()
            return int(iid)

    def list_identities(self, tenant_id: int | None = None) -> list[dict[str, Any]]:
        with self._lock:
            if tenant_id is None:
                rows = self._conn.execute(text("SELECT * FROM identities ORDER BY name")).fetchall()
            else:
                rows = self._conn.execute(text("SELECT * FROM identities WHERE tenant_id = :t ORDER BY name"), {"t": tenant_id}).fetchall()
        out = []
        for r in rows:
            d = dict(r._mapping)
            d["embedding"] = json.loads(d["embedding"]) if d.get("embedding") else []
            if d["embedding"] and not isinstance(d["embedding"][0], (list, tuple)):
                d["embedding"] = [d["embedding"]]
            out.append(d)
        return out

    def add_identity_embedding(self, identity_id: int, embedding) -> None:
        """Append an embedding to an identity's gallery (capped at 10)."""
        with self._lock:
            row = self._conn.execute(text("SELECT embedding FROM identities WHERE id = :id"), {"id": identity_id}).fetchone()
            gallery = json.loads(row._mapping["embedding"]) if row and row._mapping["embedding"] else []
            if gallery and not isinstance(gallery[0], (list, tuple)):
                gallery = [gallery]
            gallery.append([float(x) for x in embedding])
            gallery = gallery[-10:]
            self._conn.execute(text("UPDATE identities SET embedding = :e WHERE id = :id"), {"e": json.dumps(gallery), "id": identity_id})
            self._conn.commit()

    def delete_identity(self, identity_id: int) -> None:
        with self._lock:
            self._conn.execute(text("DELETE FROM identities WHERE id = :id"), {"id": identity_id})
            self._conn.commit()

    def add_sighting(self, identity_id: int, camera_id, camera_name, confidence, thumb_path, ts) -> int:
        with self._lock:
            res = self._conn.execute(
                text("INSERT INTO sightings (identity_id, camera_id, camera_name, confidence, thumb_path, ts, created_at, tenant_id) VALUES (:i, :c, :cn, :cf, :th, :ts, :a, :tid) RETURNING id"),
                {"i": identity_id, "c": camera_id, "cn": camera_name, "cf": confidence, "th": thumb_path, "ts": ts, "a": time.strftime("%Y-%m-%dT%H:%M:%S"), "tid": self.local_tenant_id},
            )
            sid = res.fetchone()[0]
            self._conn.commit()
            return int(sid)

    def list_sightings(self, identity_id: int, limit: int = 500, tenant_id: int | None = None) -> list[dict[str, Any]]:
        with self._lock:
            if tenant_id is None:
                rows = self._conn.execute(
                    text("SELECT * FROM sightings WHERE identity_id = :i ORDER BY ts DESC LIMIT :l"), {"i": identity_id, "l": limit}
                ).fetchall()
            else:
                rows = self._conn.execute(
                    text("SELECT * FROM sightings WHERE identity_id = :i AND tenant_id = :t ORDER BY ts DESC LIMIT :l"),
                    {"i": identity_id, "t": tenant_id, "l": limit},
                ).fetchall()
        return [dict(r._mapping) for r in rows]

    # -- occupancy samples -----------------------------------------------
    def add_occupancy_sample(self, ts: float, people: int, vehicles: int, tenant_id: int | None = None, device_id: int | None = None) -> int:
        tid = tenant_id if tenant_id is not None else self.local_tenant_id
        with self._lock:
            res = self._conn.execute(
                text("INSERT INTO occupancy_samples (ts, people, vehicles, tenant_id, device_id) VALUES (:ts, :p, :v, :t, :d) RETURNING id"),
                {"ts": ts, "p": people, "v": vehicles, "t": tid, "d": device_id},
            )
            oid = res.fetchone()[0]
            self._conn.commit()
            return int(oid)

    def list_occupancy_samples(self, since: float | None = None, limit: int = 2000, tenant_id: int | None = None) -> list[dict[str, Any]]:
        with self._lock:
            if tenant_id is None:
                if since is None:
                    rows = self._conn.execute(text("SELECT * FROM occupancy_samples ORDER BY ts DESC LIMIT :l"), {"l": limit}).fetchall()
                else:
                    rows = self._conn.execute(text("SELECT * FROM occupancy_samples WHERE ts >= :s ORDER BY ts DESC LIMIT :l"), {"s": since, "l": limit}).fetchall()
            else:
                if since is None:
                    rows = self._conn.execute(text("SELECT * FROM occupancy_samples WHERE tenant_id = :t ORDER BY ts DESC LIMIT :l"), {"t": tenant_id, "l": limit}).fetchall()
                else:
                    rows = self._conn.execute(text("SELECT * FROM occupancy_samples WHERE tenant_id = :t AND ts >= :s ORDER BY ts DESC LIMIT :l"), {"t": tenant_id, "s": since, "l": limit}).fetchall()
        return [dict(r._mapping) for r in rows]

    def list_events_since_id(self, last_id: int, limit: int = 500) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                text("SELECT * FROM events WHERE id > :id ORDER BY id ASC LIMIT :l"), {"id": last_id, "l": limit}
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def list_occupancy_since_id(self, last_id: int, limit: int = 500) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                text("SELECT * FROM occupancy_samples WHERE id > :id ORDER BY id ASC LIMIT :l"), {"id": last_id, "l": limit}
            ).fetchall()
        return [dict(r._mapping) for r in rows]

    def events_needing_summary(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                text("SELECT * FROM events WHERE summary IS NULL AND clip_path IS NOT NULL ORDER BY start_ts DESC LIMIT 50")
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # -- helpers ----------------------------------------------------------
    @staticmethod
    def _row_to_dict(row) -> dict[str, Any]:
        d = dict(row._mapping)
        for key in ("objects", "track_ids"):
            if d.get(key):
                try:
                    d[key] = json.loads(d[key])
                except (TypeError, json.JSONDecodeError):
                    pass
        return d

    # -- search -----------------------------------------------------------
    def search(self, terms: Iterable[str], limit: int = 200, tenant_id: int | None = None) -> list[dict[str, Any]]:
        """Text search over object labels and summaries."""
        results: dict[int, dict[str, Any]] = {}
        for term in terms:
            t = f"%{term}%"
            with self._lock:
                if tenant_id is None:
                    rows = self._conn.execute(
                        text("""
                        SELECT * FROM events
                        WHERE objects LIKE :p OR top_object LIKE :p OR summary LIKE :p OR plate LIKE :p
                        ORDER BY start_ts DESC LIMIT :l
                        """),
                        {"p": t, "l": limit},
                    ).fetchall()
                else:
                    rows = self._conn.execute(
                        text("""
                        SELECT * FROM events
                        WHERE (objects LIKE :p OR top_object LIKE :p OR summary LIKE :p OR plate LIKE :p) AND tenant_id = :t
                        ORDER BY start_ts DESC LIMIT :l
                        """),
                        {"p": t, "t": tenant_id, "l": limit},
                    ).fetchall()
            for r in rows:
                d = self._row_to_dict(r)
                results.setdefault(d["id"], d)
        return list(results.values())
