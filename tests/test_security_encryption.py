import pytest
from backend.security import (
    encrypt,
    decrypt,
    encrypt_json,
    decrypt_json,
    scrub_pii_for_llm,
    is_encryption_active,
    mask,
)
from backend.schemas.interview import (
    AnswerRecord,
    VisualSignal,
    HRComposureEvaluation,
    HREvaluation,
)
from multimodal.visual_analyzer import VisualAnalyzer
import numpy as np


def test_encryption_is_active_and_reversible():
    assert is_encryption_active() is True
    original = "Candidate Sarah Connor, SSN 000-11-2222, Top Secret Experience"
    token = encrypt(original)
    assert token != original
    assert len(token) > 20
    recovered = decrypt(token)
    assert recovered == original


def test_encrypt_and_decrypt_json():
    telemetry = {
        "face_detected": True,
        "composure_state": "composed",
        "tension_score": 0.12,
        "fidget_level": 0.08,
        "gaze_stability": 0.95,
        "blink_rate_indicator": "normal",
    }
    ciphertext = encrypt_json(telemetry)
    assert ciphertext != str(telemetry)
    recovered = decrypt_json(ciphertext)
    assert recovered["composure_state"] == "composed"
    assert recovered["tension_score"] == 0.12
    assert recovered["gaze_stability"] == 0.95


def test_scrub_pii_for_llm():
    raw_text = (
        "Hello, my name is Alice Smith. You can reach me at alice.smith@example.com or "
        "+1 (555) 345-6789. I live at 742 Evergreen Terrace. My ID is 123-45-6789. "
        "I built distributed microservices with Go and Kubernetes."
    )
    scrubbed = scrub_pii_for_llm(raw_text)

    # Verify PII was redacted
    assert "alice.smith@example.com" not in scrubbed
    assert "[REDACTED_EMAIL]" in scrubbed

    assert "555" not in scrubbed
    assert "[REDACTED_PHONE]" in scrubbed

    assert "123-45-6789" not in scrubbed
    assert "[REDACTED_ID]" in scrubbed

    assert "742 Evergreen Terrace" not in scrubbed
    assert "[REDACTED_ADDRESS]" in scrubbed

    # Technical content preserved
    assert "distributed microservices with Go and Kubernetes" in scrubbed


def test_mask_function():
    assert mask("Alexander", visible_chars=3) == "Ale******"
    assert mask("Bob", visible_chars=3) == "***"
    assert mask("", visible_chars=3) == "***"


def test_visual_analyzer_computes_composure_signals():
    analyzer = VisualAnalyzer()
    # Calm frame with minimal motion
    calm_frame = np.full((100, 100, 3), 128, dtype=np.uint8)
    first_obs = analyzer.analyze(calm_frame, face_bbox=(20, 20, 60, 60))
    second_obs = analyzer.analyze(calm_frame, face_bbox=(20, 20, 60, 60))

    assert second_obs.face_detected is True
    assert second_obs.composure_state in ("composed", "mild_tension")
    assert second_obs.tension_score is not None
    assert second_obs.fidget_level is not None
    assert second_obs.gaze_stability is not None


def test_schema_field_level_encryption_support():
    plain_answer = "I optimized PostgreSQL indexing which reduced query latency from 800ms to 12ms."
    encrypted_token = encrypt(plain_answer)

    record = AnswerRecord(
        question="How did you improve database performance?",
        answer=plain_answer,
        encrypted_answer=encrypted_token,
        skill="Database Tuning",
        depth="deep",
    )

    assert record.encrypted_answer == encrypted_token
    assert decrypt(record.encrypted_answer) == plain_answer

    telemetry = {
        "composure_state": "composed",
        "tension_score": 0.15,
    }
    signal = VisualSignal(
        face_detected=True,
        composure_state="composed",
        tension_score=0.15,
        fidget_level=0.10,
        gaze_stability=0.92,
        encrypted_telemetry=encrypt_json(telemetry),
    )

    assert signal.encrypted_telemetry is not None
    decrypted_telemetry = decrypt_json(signal.encrypted_telemetry)
    assert decrypted_telemetry["composure_state"] == "composed"
