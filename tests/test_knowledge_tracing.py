"""Test the BKT knowledge tracer."""

from app.engine.knowledge_tracing import KnowledgeTracer


def test_bkt_correct_increases_mastery():
    kt = KnowledgeTracer(prior=0.5, slip=0.1, guess=0.25, transit=0.1)
    new_p, delta = kt.update(0.5, observed_correct=True)
    assert new_p > 0.5
    assert delta > 0


def test_bkt_incorrect_decreases_mastery():
    kt = KnowledgeTracer(prior=0.5, slip=0.1, guess=0.25, transit=0.1)
    new_p, delta = kt.update(0.8, observed_correct=False)
    assert new_p < 0.8
    assert delta < 0


def test_bkt_converges_with_repeated_correct():
    kt = KnowledgeTracer(prior=0.3, slip=0.1, guess=0.25, transit=0.1)
    p = 0.3
    for _ in range(10):
        p, _ = kt.update(p, True)
    assert p > 0.9


def test_bkt_clamps():
    kt = KnowledgeTracer()
    p, _ = kt.update(0.99, True)
    assert p <= 0.99
    p, _ = kt.update(0.01, False)
    assert p >= 0.01


def test_soft_inference():
    kt = KnowledgeTracer()
    # High confidence → mastery should increase
    new_p, delta = kt.infer_from_chat(0.5, confidence=0.9)
    assert new_p > 0.5
    assert delta > 0

    # Low confidence → mastery should decrease
    new_p, delta = kt.infer_from_chat(0.8, confidence=0.2)
    assert new_p < 0.8
    assert delta < 0
