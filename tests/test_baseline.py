import pytest

from multimodal.baseline import BaselineStore
from multimodal.visual_analyzer import VisualObservation


def test_baseline_store_keeps_candidates_isolated():
    store = BaselineStore()
    visual = VisualObservation(True, .5, None, 10, 10)
    profile = store.update("candidate-a", visual=visual)
    assert profile.sample_count == 1
    assert store.get("candidate-a").visual == visual
    assert store.get("candidate-a").visual_history == (visual,)
    assert store.get("candidate-b") is None


def test_baseline_store_rejects_blank_ids():
    with pytest.raises(ValueError):
        BaselineStore().get("  ")