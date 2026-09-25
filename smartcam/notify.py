"""Mobile notifications via apprise (ntfy, Pushover, Telegram, ...).

The primary path uses apprise and works out of the box. An optional
end-to-end encrypted path encrypts the message with the recipient's X25519
public key (NaCl box) before publishing it to ntfy; enable it with
"e2e_encrypt": true and provide the recipient's base64 public key.
"""
from __future__ import annotations

import base64
import logging
from typing import Any

from .config import NotifyConfig
from .utils import format_duration, ts_to_iso

log = logging.getLogger("smartcam.notify")


class Notifier:
    def __init__(self, cfg: NotifyConfig):
        self.cfg = cfg
        self._apprise = None
        if cfg.apprise_url:
            try:
                import apprise

                self._apprise = apprise.Apprise()
                if not self._apprise.add(cfg.apprise_url):
                    log.warning("apprise rejected notification URL")
            except Exception as exc:  # noqa: BLE001
                log.warning("apprise unavailable: %s", exc)

    def send_alert(self, title: str, body: str) -> bool:
        if not self.cfg.enabled or self._apprise is None:
            return False
        try:
            return bool(self._apprise.notify(title=title, body=body))
        except Exception as exc:  # noqa: BLE001
            log.warning("alert notify failed: %s", exc)
            return False

    def send_report(self, title: str, body: str) -> bool:
        if not self.cfg.enabled or self._apprise is None:
            return False
        try:
            return bool(self._apprise.notify(title=title, body=body))
        except Exception as exc:  # noqa: BLE001
            log.warning("report notify failed: %s", exc)
            return False

    def send_event(self, event: dict[str, Any], summary: str | None = None) -> bool:
        if not self.cfg.enabled:
            return False
        title = self._title(event)
        body = self._body(event, summary)
        ok = False
        if self._apprise is not None:
            try:
                ok = bool(self._apprise.notify(title=title, body=body))
            except Exception as exc:  # noqa: BLE001
                log.warning("notify failed: %s", exc)
        if self.cfg.e2e_encrypt:
            try:
                ok = self._send_ntfy_e2e(title, body) or ok
            except Exception as exc:  # noqa: BLE001
                log.warning("ntfy E2E send failed: %s", exc)
        return ok

    # -- formatting -------------------------------------------------------
    @staticmethod
    def _title(event: dict[str, Any]) -> str:
        if event.get("event_type") == "fall":
            return "🚨 URGENT: Possible fall detected"
        objs = event.get("objects") or ["motion"]
        return f"Security event: {', '.join(objs[:3])}"

    @staticmethod
    def _body(event: dict[str, Any], summary: str | None) -> str:
        from .utils import ts_to_iso

        cam = event.get("camera_name") or event.get("camera_id") or "camera"
        lines = [
            f"Camera: {cam}",
            f"Time: {ts_to_iso(event.get('start_ts'))}",
            f"Duration: {format_duration(event.get('duration'))}",
            f"Objects: {', '.join(event.get('objects') or [])}",
        ]
        if event.get("plate"):
            lines.append(f"Plate: {event['plate']}")
        if summary:
            lines.append("")
            lines.append(f"AI summary: {summary}")
        return "\n".join(lines)

    # -- ntfy end-to-end encryption --------------------------------------
    def _send_ntfy_e2e(self, title: str, body: str) -> bool:
        """Encrypt (NaCl box) and publish to ntfy. Requires pynacl and a
        configured ntfy topic + recipient public key."""
        if not self.cfg.ntfy_topic:
            log.warning("E2E enabled but ntfy_topic not set")
            return False

        try:
            import nacl.public
            import nacl.utils
        except ImportError:
            log.warning("pynacl not installed; skipping E2E (pip install pynacl)")
            return False

        pubkey = getattr(self.cfg, "ntfy_public_key", "") or ""
        if not pubkey:
            log.warning("E2E enabled but recipient public key not set")
            return False

        import requests

        # Decode the recipient's base64 public key.
        recipient_pub = nacl.public.PublicKey(base64.b64decode(self._fix_b64(pubkey)))
        ephemeral = nacl.public.PrivateKey.generate()
        box = nacl.public.Box(ephemeral, recipient_pub)
        message = f"{title}\n{body}".encode("utf-8")
        nonce = nacl.utils.random(nacl.public.Box.NONCE_SIZE)
        encrypted = box.encrypt(message, nonce)  # nonce + ciphertext
        payload = base64.b64encode(ephemeral.public_key.encode() + encrypted).decode("ascii")

        topic = self.cfg.ntfy_topic
        url = self.cfg.ntfy_server.rstrip("/") + "/" + topic
        resp = requests.post(
            url,
            data=payload.encode("utf-8"),
            headers={"X-Message-Type": "e2e", "Content-Type": "text/plain"},
            timeout=15,
        )
        return resp.status_code < 300

    @staticmethod
    def _fix_b64(s: str) -> str:
        s = s.strip().replace("-", "+").replace("_", "/")
        return s + "=" * (-len(s) % 4)
