"""Neutral, frame-level visual observations for interview practice.

This module reports observable image signals and non-verbal composure metrics
(gaze stability, micro-motion fidgeting, tension indicators) for HR interview coaching.
Zero raw video is persisted.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
from typing import Any

import numpy as np


@dataclass(frozen=True)
class VisualObservation:
    """Descriptive measurements for one camera frame."""

    frame_available: bool
    brightness: float | None
    motion: float | None
    frame_width: int | None = None
    frame_height: int | None = None
    face_detected: bool | None = None
    gaze_direction: str | None = None
    head_orientation: str | None = None
    face_quality: float | None = None
    lighting_quality: float | None = None
    confidence: float | None = None

    # HR Non-Verbal Composure & Tension Metrics
    composure_state: str | None = None       # "composed", "mild_tension", "elevated_anxiety"
    tension_score: float | None = None       # 0.0 to 1.0
    fidget_level: float | None = None        # 0.0 to 1.0
    gaze_stability: float | None = None      # 0.0 to 1.0


class VisualAnalyzer:
    """Calculate inexpensive, dependency-light camera observations."""

    def __init__(self, face_detector: Callable[[np.ndarray], Any] | None = None) -> None:
        self._previous_gray: np.ndarray | None = None
        self._face_detector = face_detector

    def analyze(self, frame: Any | None, *, face_bbox: tuple[float, float, float, float] | None = None) -> VisualObservation:
        """Analyze an RGB, grayscale, or image-like NumPy frame.

        ``None`` and malformed frames produce an unavailable observation rather
        than failing an otherwise usable audio interview turn.
        """
        if frame is None:
            return VisualObservation(False, None, None)
        try:
            values = np.asarray(frame)
            if values.ndim not in (2, 3) or values.size == 0:
                return VisualObservation(False, None, None)
            numeric = values.astype(np.float32, copy=False)
            if numeric.ndim == 3:
                gray = numeric.mean(axis=2)
            else:
                gray = numeric
            if not np.isfinite(gray).all():
                return VisualObservation(False, None, None)
            scale = 255.0 if float(np.max(gray)) > 1.0 else 1.0
            normalized = np.clip(gray / scale, 0.0, 1.0)
            motion = None
            if self._previous_gray is not None and self._previous_gray.shape == normalized.shape:
                motion = float(np.mean(np.abs(normalized - self._previous_gray)))
            self._previous_gray = normalized.copy()
            height, width = normalized.shape
            brightness = float(np.mean(normalized))
            lighting_quality = max(0.0, 1.0 - abs(brightness - 0.5) * 2.0)
            detected_bbox = face_bbox
            face_detected: bool | None = None
            if detected_bbox is None and self._face_detector is not None:
                try:
                    detected_bbox = _coerce_bbox(self._face_detector(values))
                    face_detected = detected_bbox is not None
                except (TypeError, ValueError):
                    face_detected = False
            elif detected_bbox is not None:
                face_detected = True

            # Calculate composure indicators
            fidget_level = float(np.clip(motion if motion is not None else 0.0, 0.0, 1.0))
            if detected_bbox is None:
                composure_state = "composed" if fidget_level < 0.20 else ("mild_tension" if fidget_level < 0.40 else "elevated_anxiety")
                tension_score = round(fidget_level * 0.8, 2)
                return VisualObservation(
                    True, brightness, motion, width, height, face_detected,
                    None, None, None, lighting_quality,
                    lighting_quality if face_detected is False else None,
                    composure_state=composure_state,
                    tension_score=tension_score,
                    fidget_level=fidget_level,
                    gaze_stability=0.85 if face_detected else 0.0,
                )

            x, y, box_width, box_height = _clip_bbox(detected_bbox, width, height)
            area_ratio = (box_width * box_height) / (width * height)
            face_quality = max(0.0, min(1.0, area_ratio / 0.20))
            center_x = (x + box_width / 2) / width
            center_y = (y + box_height / 2) / height
            gaze = "approximate_forward" if abs(center_x - 0.5) <= 0.2 else "away_from_camera"
            orientation = "level" if abs(center_y - 0.5) <= 0.2 else ("slightly_down" if center_y > 0.5 else "slightly_up")
            confidence = face_quality * lighting_quality

            # Objective composure calculation
            is_forward = gaze == "approximate_forward"
            gaze_stability = 0.92 if is_forward else 0.45
            tension_score = round(min(1.0, (fidget_level * 0.65) + (0.35 if not is_forward else 0.0)), 2)

            if tension_score < 0.25:
                composure_state = "composed"
            elif tension_score < 0.55:
                composure_state = "mild_tension"
            else:
                composure_state = "elevated_anxiety"

            return VisualObservation(
                True, brightness, motion, width, height, True, gaze, orientation,
                face_quality, lighting_quality, confidence,
                composure_state=composure_state,
                tension_score=tension_score,
                fidget_level=fidget_level,
                gaze_stability=gaze_stability,
            )
        except (TypeError, ValueError):
            return VisualObservation(False, None, None)

    def reset(self) -> None:
        """Forget the previous frame used for motion comparison."""
        self._previous_gray = None


def _coerce_bbox(value: Any) -> tuple[float, float, float, float] | None:
    if isinstance(value, dict):
        value = (value.get("x"), value.get("y"), value.get("width"), value.get("height"))
    if value is None:
        return None
    if len(value) != 4:
        raise ValueError("face detector must return x, y, width, height")
    numbers = tuple(float(item) for item in value)
    if not all(np.isfinite(item) for item in numbers) or numbers[2] <= 0 or numbers[3] <= 0:
        raise ValueError("face bounding box must contain finite positive dimensions")
    return numbers


def _clip_bbox(bbox: tuple[float, float, float, float], width: int, height: int) -> tuple[float, float, float, float]:
    x, y, box_width, box_height = bbox
    x = max(0.0, min(x, width))
    y = max(0.0, min(y, height))
    box_width = min(box_width, width - x)
    box_height = min(box_height, height - y)
    if box_width <= 0 or box_height <= 0:
        raise ValueError("face bounding box must overlap the frame")
    return x, y, box_width, box_height