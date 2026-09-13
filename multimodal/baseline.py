"""Per-candidate baseline storage for descriptive comparisons."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Generic, TypeVar

from .voice_analyzer import VoiceObservation
from .visual_analyzer import VisualObservation


@dataclass(frozen=True)
class BaselineProfile:
    """The latest personal observations used for same-candidate comparison."""

    voice: VoiceObservation | None = None
    visual: VisualObservation | None = None
    sample_count: int = 0
    voice_history: tuple[VoiceObservation, ...] = ()
    visual_history: tuple[VisualObservation, ...] = ()


T = TypeVar("T")


class BaselineStore(Generic[T]):
    """In-memory baseline store keyed by candidate/session identifier."""

    def __init__(self) -> None:
        self._profiles: dict[str, BaselineProfile] = {}

    def get(self, candidate_id: str) -> BaselineProfile | None:
        return self._profiles.get(_candidate_key(candidate_id))

    def update(
        self,
        candidate_id: str,
        *,
        voice: VoiceObservation | None = None,
        visual: VisualObservation | None = None,
    ) -> BaselineProfile:
        key = _candidate_key(candidate_id)
        previous = self._profiles.get(key, BaselineProfile())
        profile = replace(
            previous,
            voice=voice if voice is not None else previous.voice,
            visual=visual if visual is not None else previous.visual,
            sample_count=previous.sample_count + 1,
            voice_history=previous.voice_history + ((voice,) if voice is not None else ()),
            visual_history=previous.visual_history + ((visual,) if visual is not None else ()),
        )
        self._profiles[key] = profile
        return profile

    def clear(self, candidate_id: str) -> None:
        self._profiles.pop(_candidate_key(candidate_id), None)


def _candidate_key(candidate_id: str) -> str:
    key = candidate_id.strip()
    if not key:
        raise ValueError("candidate_id must not be empty")
    return key