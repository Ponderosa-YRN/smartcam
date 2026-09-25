"""Deliver event payloads to an external webhook/API."""
from __future__ import annotations

import logging
from typing import Any

from .config import WebhookConfig

log = logging.getLogger("smartcam.webhook")


class Webhook:
    def __init__(self, cfg: WebhookConfig):
        self.cfg = cfg

    def send(self, event: dict[str, Any]) -> bool:
        if not self.cfg.enabled or not self.cfg.url:
            return False
        try:
            import requests

            resp = requests.post(self.cfg.url, json=event, timeout=self.cfg.timeout_sec)
            return resp.status_code < 300
        except Exception as exc:  # noqa: BLE001
            log.warning("webhook failed: %s", exc)
            return False
