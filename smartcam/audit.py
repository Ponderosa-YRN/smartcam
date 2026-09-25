"""Append-only audit trail for dashboard and pipeline actions."""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path


def audit_log(log_path: str | Path, role: str, action: str, detail: str = "") -> None:
    """Append a timestamped audit line. Best-effort; never raises."""
    try:
        p = Path(log_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.fromtimestamp(time.time()).strftime("%Y-%m-%dT%H:%M:%S")
        line = f"{ts} | {role or '-'} | {action} | {detail}\n"
        with open(p, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass
