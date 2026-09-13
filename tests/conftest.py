import sys
from pathlib import Path

# Add person3-evaluation root to python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from evaluation.schemas import CompetencyState, EvidenceStatus
from evaluation.mocks import get_default_competencies


@pytest.fixture
def default_competencies():
    return get_default_competencies()


@pytest.fixture
def sample_strong_answer():
    return (
        "In our notification service, we used Redis as a fast in-memory cache and message broker with Pub/Sub. "
        "To handle high write throughput and prevent database connection saturation, we placed Celery task workers "
        "behind Redis. When traffic surged to 50k requests/min, we identified a bottleneck in Redis memory limits, "
        "so we configured volatile-lru eviction policies and added a Redis replica cluster with read sharding."
    )


@pytest.fixture
def sample_vague_answer():
    return "We built a very scalable and modern cloud microservice. Everything was nice and clean, using best practices."


@pytest.fixture
def sample_ownership_claim_answer():
    return (
        "I designed the entire backend architecture myself from scratch for the enterprise platform, "
        "including all microservices and databases."
    )
