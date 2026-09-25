"""AI event summaries via a pluggable vision-language model.

Supports any OpenAI-compatible chat/completions endpoint (OpenAI, OpenRouter,
vLLM, etc.) and local Ollama. Falls back gracefully if no model is configured.
"""
from __future__ import annotations

import base64
import io
import logging
from typing import Any

from .config import VLMSummarizerConfig

log = logging.getLogger("smartcam.summarize")


class VLMSummarizer:
    def __init__(self, cfg: VLMSummarizerConfig):
        self.cfg = cfg

    @property
    def available(self) -> bool:
        if not self.cfg.enabled:
            return False
        if self.cfg.provider == "ollama":
            return bool(self.cfg.base_url and self.cfg.model)
        return bool(self.cfg.base_url and self.cfg.model and self.cfg.api_key)

    def summarize(self, event: dict[str, Any], keyframe_paths: list[str]) -> str | None:
        """Return a one-paragraph summary, or None if unavailable/failed."""
        if not self.available:
            return None
        try:
            images = [self._encode_image(p) for p in keyframe_paths if p]
            images = [i for i in images if i][: self.cfg.max_keyframes]
            prompt = self._build_prompt(event)
            if self.cfg.provider == "ollama":
                return self._call_ollama(prompt, images)
            return self._call_openai(prompt, images)
        except Exception as exc:  # noqa: BLE001 - never break the pipeline for summaries
            log.warning("summary failed: %s", exc)
            return None

    # -- prompt -----------------------------------------------------------
    @staticmethod
    def _build_prompt(event: dict[str, Any]) -> str:
        from .utils import format_duration, ts_to_iso

        objects = event.get("objects") or []
        objs = ", ".join(objects) if objects else "unknown"
        start = ts_to_iso(event.get("start_ts"))
        dur = format_duration(event.get("duration"))
        cam = event.get("camera_name") or event.get("camera_id") or "unknown camera"
        return (
            "You are a concise, professional security analyst reviewing a surveillance event. "
            "Write a single short paragraph (max 90 words) summarizing what happened, focusing on "
            "people, vehicles, actions, and anything notable. Do not speculate beyond what is visible.\n\n"
            f"Camera: {cam}\n"
            f"Time: {start}\n"
            f"Duration: {dur}\n"
            f"Detected objects: {objs}\n"
            "Keyframes from the clip are attached."
        )

    @staticmethod
    def _encode_image(path: str, max_side: int = 768) -> str | None:
        from PIL import Image

        try:
            img = Image.open(path).convert("RGB")
            img.thumbnail((max_side, max_side))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            return base64.b64encode(buf.getvalue()).decode("ascii")
        except Exception as exc:  # noqa: BLE001
            log.debug("encode image failed: %s", exc)
            return None

    # -- providers --------------------------------------------------------
    def _call_openai(self, prompt: str, images_b64: list[str]) -> str | None:
        import requests

        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for b in images_b64:
            content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b}"}})

        payload = {
            "model": self.cfg.model,
            "messages": [
                {"role": "system", "content": "You are a security event summarizer."},
                {"role": "user", "content": content},
            ],
            "max_tokens": 250,
            "temperature": 0.2,
        }
        url = self.cfg.base_url.rstrip("/") + "/chat/completions"
        resp = requests.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {self.cfg.api_key}"},
            timeout=self.cfg.timeout_sec,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()

    def _call_ollama(self, prompt: str, images_b64: list[str]) -> str | None:
        import requests

        payload = {
            "model": self.cfg.model,
            "prompt": prompt,
            "images": images_b64,
            "stream": False,
        }
        url = self.cfg.base_url.rstrip("/") + "/api/chat"
        resp = requests.post(url, json=payload, timeout=self.cfg.timeout_sec)
        resp.raise_for_status()
        data = resp.json()
        return (data.get("message") or {}).get("content", "").strip()
