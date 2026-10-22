"""Enabling biometrics requires an acknowledged lawful basis.

Not a technical control - it is the record that somebody with authority said yes, and the
refusal is deliberate: flipping the switch off silently would leave an operator believing
face recognition was running when it was not.
"""
import pytest
from fastapi import HTTPException

from smartcam.api import _require_biometric_consent
from smartcam.config import AppConfig


def test_face_recognition_without_consent_is_refused():
    cfg = AppConfig()
    cfg.face.enabled = True
    with pytest.raises(HTTPException) as exc:
        _require_biometric_consent(cfg)
    assert exc.value.status_code == 400
    assert "biometrics_consent" in exc.value.detail


def test_reidentification_without_consent_is_refused():
    cfg = AppConfig()
    cfg.reid.enabled = True
    with pytest.raises(HTTPException):
        _require_biometric_consent(cfg)


def test_consent_permits_biometrics():
    cfg = AppConfig()
    cfg.face.enabled = True
    cfg.reid.enabled = True
    cfg.privacy.biometrics_consent = True
    _require_biometric_consent(cfg)  # must not raise


def test_consent_alone_enables_nothing():
    """Ticking the box is not the same as switching the feature on."""
    cfg = AppConfig()
    cfg.privacy.biometrics_consent = True
    assert cfg.face.enabled is False
    assert cfg.reid.enabled is False
    _require_biometric_consent(cfg)  # must not raise
