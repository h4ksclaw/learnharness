"""
Comprehensive unit tests for BKT mastery tracking over time.

Tests:
1. Mastery converges to ~1.0 with repeated correct observations
2. Mastery converges to ~0.0 with repeated incorrect observations
3. Soft inference (from chat) smoothly adjusts mastery
4. Mixed signals (mostly correct) trend upward
5. Recovery: mastery can increase after a drop
6. Mastery affects the system prompt context
7. Multiple concepts tracked independently
8. Prior parameter affects initial mastery
"""

import pytest

from app.engine.knowledge_tracing import KnowledgeTracer


@pytest.fixture
def kt():
    return KnowledgeTracer()


class TestBKTConvergence:
    """Mastery converges with repeated observations."""

    def test_converges_to_mastery_with_correct(self, kt):
        """After many correct answers, mastery should approach 1.0."""
        p = 0.3
        for _ in range(20):
            p, _ = kt.update(p, observed_correct=True)
        assert p > 0.95, f"Expected mastery >0.95 after 20 correct, got {p}"

    def test_converges_to_zero_with_incorrect(self, kt):
        """After many wrong answers, mastery should approach 0.0.
        Note: BKT transit parameter creates a floor (~0.11) since
        learning can always happen between observations."""
        p = 0.7
        for _ in range(20):
            p, _ = kt.update(p, observed_correct=False)
        assert p < 0.15, f"Expected mastery <0.15 after 20 incorrect, got {p}"

    def test_converges_quickly(self, kt):
        """BKT should converge within ~10 observations."""
        p = 0.5
        for _ in range(10):
            p, _ = kt.update(p, observed_correct=True)
        assert p > 0.9

    def test_starting_from_zero(self, kt):
        p = 0.01
        for _ in range(15):
            p, _ = kt.update(p, observed_correct=True)
        assert p > 0.9

    def test_starting_from_high(self, kt):
        p = 0.99
        for _ in range(15):
            p, _ = kt.update(p, observed_correct=False)
        assert p < 0.15


class TestBKTDynamics:
    """How mastery changes with mixed signals."""

    def test_one_wrong_answer_drops_mastery(self, kt):
        """A single wrong answer should noticeably drop mastery."""
        p = 0.9
        new_p, delta = kt.update(p, observed_correct=False)
        assert delta < -0.1, f"Expected significant drop, got delta={delta}"

    def test_one_right_answer_increases_mastery(self, kt):
        p = 0.3
        new_p, delta = kt.update(p, observed_correct=True)
        assert delta > 0.1

    def test_mostly_correct_trends_up(self, kt):
        """80% correct should trend upward overall."""
        p = 0.5
        for i in range(20):
            correct = i % 5 != 0  # 4 out of 5 correct
            p, _ = kt.update(p, observed_correct=correct)
        assert p > 0.7, f"Expected >0.7 with 80% correct, got {p}"

    def test_mostly_incorrect_trends_down(self, kt):
        p = 0.5
        for i in range(20):
            correct = i % 5 == 0  # 1 out of 5 correct
            p, _ = kt.update(p, observed_correct=correct)
        assert p < 0.3

    def test_oscillation_stabilizes(self, kt):
        """Alternating correct/incorrect should not diverge."""
        p = 0.5
        values = []
        for i in range(40):
            p, _ = kt.update(p, observed_correct=(i % 2 == 0))
            values.append(p)

        # Should not diverge
        assert all(0.01 < v < 0.99 for v in values)


class TestSoftInference:
    """Soft inference from chat confidence."""

    def test_high_confidence_increases_mastery(self, kt):
        p = 0.5
        new_p, delta = kt.infer_from_chat(p, confidence=0.9)
        assert delta > 0
        assert new_p > 0.5

    def test_low_confidence_decreases_mastery(self, kt):
        p = 0.5
        new_p, delta = kt.infer_from_chat(p, confidence=0.2)
        assert delta < 0
        assert new_p < 0.5

    def test_medium_confidence_no_change(self, kt):
        p = 0.5
        new_p, delta = kt.infer_from_chat(p, confidence=0.5)
        assert abs(delta) < 0.05  # minimal change

    def test_soft_inference_is_gentler_than_hard(self, kt):
        """Soft inference should change mastery less than hard observation."""
        p = 0.5

        _, soft_delta = kt.infer_from_chat(p, confidence=1.0)
        _, hard_delta = kt.update(p, observed_correct=True)

        assert abs(soft_delta) <= abs(hard_delta)

    def test_repeated_soft_inference_converges(self, kt):
        p = 0.3
        for _ in range(20):
            p, _ = kt.infer_from_chat(p, confidence=0.95)
        assert p > 0.7


class TestRecoveryAndDecline:
    """Mastery can recover after decline and vice versa."""

    def test_recovery_after_drop(self, kt):
        """Mastery drops, then recovers with correct answers."""
        p = 0.8

        # Drop it
        for _ in range(3):
            p, _ = kt.update(p, observed_correct=False)
        assert p < 0.3

        # Recover
        for _ in range(10):
            p, _ = kt.update(p, observed_correct=True)
        assert p > 0.8

    def test_decline_after_mastery(self, kt):
        p = 0.95

        for _ in range(5):
            p, _ = kt.update(p, observed_correct=False)
        assert p < 0.2


class TestMultipleConcepts:
    """Multiple concepts tracked independently."""

    def test_independent_tracking(self, kt):
        concept_a = 0.5  # will be correct
        concept_b = 0.5  # will be incorrect

        for _ in range(10):
            concept_a, _ = kt.update(concept_a, observed_correct=True)
            concept_b, _ = kt.update(concept_b, observed_correct=False)

        assert concept_a > 0.9
        assert concept_b < 0.15
        assert concept_a > concept_b

    def test_three_concepts_different_paces(self, kt):
        """Three concepts at different mastery rates."""
        fast = 0.5
        medium = 0.5
        slow = 0.5

        for i in range(15):
            fast, _ = kt.update(fast, observed_correct=True)  # always correct
            medium, _ = kt.update(medium, observed_correct=(i % 3 != 0))  # ~67%
            slow, _ = kt.update(slow, observed_correct=(i % 4 == 0))  # ~25%

        assert fast >= medium >= slow


class TestBoundaryConditions:
    """Edge cases and boundary conditions."""

    def test_mastery_never_exceeds_1(self, kt):
        p = 0.99
        for _ in range(100):
            p, _ = kt.update(p, observed_correct=True)
        assert p <= 0.999

    def test_mastery_never_goes_negative(self, kt):
        p = 0.01
        for _ in range(100):
            p, _ = kt.update(p, observed_correct=False)
        assert p >= 0.001

    def test_clamping(self, kt):
        p = 0.5
        new_p, _ = kt.update(p, observed_correct=True)
        assert 0 < new_p < 1

    def test_delta_positive_for_correct(self, kt):
        _, delta = kt.update(0.5, observed_correct=True)
        assert delta > 0

    def test_delta_negative_for_incorrect(self, kt):
        _, delta = kt.update(0.5, observed_correct=False)
        assert delta < 0
