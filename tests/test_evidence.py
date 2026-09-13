"""
Unit tests for EvidenceManager and dynamic Evidence Gap calculations.
Updated (PM Audit): EvidenceManager now requires explicit competency map — using get_default_competencies().
"""

from evaluation.evidence_manager import EvidenceManager
from evaluation.mocks import get_default_competencies
from evaluation.schemas import EvidenceItem, DepthLevel, EvidenceStatus, Claim


def _make_em() -> EvidenceManager:
    """Helper: creates a fresh EvidenceManager with default SE competencies."""
    return EvidenceManager(get_default_competencies())


def test_evidence_manager_initialization():
    em = _make_em()
    live_map = em.get_live_map()
    assert len(live_map) >= 4
    assert "System Design" in live_map

    # Untested competency has maximum gap = (1.0 - 0.0) * Priority
    sys_design = live_map["System Design"]
    assert sys_design.evidence_gap == sys_design.priority * 1.0


def test_evidence_manager_largest_gap():
    em = _make_em()
    # System Design has priority 5.0, so initially it has the largest gap (5.0)
    comp_name, gap = em.get_largest_evidence_gap()
    assert comp_name == "System Design"
    assert gap == 5.0


def test_evidence_manager_add_evidence():
    em = _make_em()
    ev1 = EvidenceItem(
        id="ev_1",
        competency="System Design",
        demonstrated_fact="Configured Redis read replicas",
        quote="We used Redis read replicas for scale",
        depth_level=DepthLevel.ADVANCED,
        confidence_score=0.85,
    )
    ev2 = EvidenceItem(
        id="ev_2",
        competency="System Design",
        demonstrated_fact="Handled cache invalidation with TTL",
        quote="We set volatile-lru TTL",
        depth_level=DepthLevel.INTERMEDIATE,
        confidence_score=0.80,
    )

    state = em.add_turn_evidence("System Design", [ev1, ev2], technical_accuracy=4.5)

    assert len(state.evidence_list) == 2
    assert state.score >= 4.0
    assert state.confidence >= 0.50
    # Gap should have decreased
    assert state.evidence_gap < 5.0


def test_evidence_manager_claim_resolution():
    em = _make_em()
    claim = Claim(
        claim_id="claim_backend_01",
        claim_text="I designed the entire backend",
        target_competency="System Design",
        verification_needed=True,
    )
    em.register_claim(claim)
    assert len(em.get_competency("System Design").claims_pending) == 1

    # Resolve claim positively
    resolved = em.resolve_claim(
        claim_id="claim_backend_01",
        verified=True,
        verification_response="I personally designed the Kafka partition keys and DB schema.",
    )
    assert resolved.verified is True
    # The verified claim was upgraded to an EvidenceItem
    sys_design = em.get_competency("System Design")
    assert any("ev_claim_" in e.id for e in sys_design.evidence_list)


def test_information_gain_decreases_as_tested():
    em = _make_em()
    initial_gain = em.calculate_information_gain("System Design")
    assert initial_gain == 1.0

    ev = EvidenceItem(
        id="ev_test",
        competency="System Design",
        demonstrated_fact="Database indexing",
        quote="Created B-tree composite index",
        depth_level=DepthLevel.ADVANCED,
        confidence_score=0.90,
    )
    em.add_turn_evidence("System Design", [ev])
    new_gain = em.calculate_information_gain("System Design")
    assert new_gain < initial_gain
