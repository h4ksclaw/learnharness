"""Tests for the Bayesian Knowledge Tracing engine."""

from app.engine.knowledge_tracing import KnowledgeTracer


class TestKnowledgeTracer:
    """Test BKT mastery updates."""

    def setup_method(self):
        self.kt = KnowledgeTracer()

    def test_initial_mastery(self):
        """Default prior is 0.5."""
        assert self.kt.prior == 0.5

    def test_correct_answer_increases_mastery(self):
        p_prior = 0.5
        p_post, delta = self.kt.update(p_prior, observed_correct=True)
        assert p_post > p_prior
        assert delta > 0

    def test_wrong_answer_decreases_mastery(self):
        p_prior = 0.5
        p_post, delta = self.kt.update(p_prior, observed_correct=False)
        assert p_post < p_prior
        assert delta < 0

    def test_mastery_ceiling(self):
        """Mastery should never exceed ~0.99."""
        p = 0.5
        for _ in range(20):
            p, _ = self.kt.update(p, observed_correct=True)
        assert p < 1.0
        assert p > 0.95

    def test_mastery_floor(self):
        """Mastery should never drop below transit floor."""
        p = 0.5
        for _ in range(20):
            p, _ = self.kt.update(p, observed_correct=False)
        assert p > 0.0
        assert p < 0.2

    def test_high_mastery_resists_wrong_answer(self):
        """A single mistake at high mastery shouldn't crash mastery."""
        p = 0.95
        p_post, delta = self.kt.update(p, observed_correct=False)
        assert p_post < 0.95
        assert p_post > 0.5

    def test_custom_parameters(self):
        kt = KnowledgeTracer(
            prior=0.3,
            slip=0.05,
            guess=0.15,
            transit=0.2,
        )
        p_post, _ = kt.update(0.3, observed_correct=True)
        assert p_post > 0.3

    def test_infer_from_chat(self):
        """Soft inference should blend between current mastery and confidence."""
        p = 0.5
        p_post, delta = self.kt.infer_from_chat(p, confidence=0.9)
        assert p_post > p
        assert p_post < 0.9  # blended, not jumped

    def test_infer_from_chat_low_confidence(self):
        p = 0.8
        p_post, delta = self.kt.infer_from_chat(p, confidence=0.2)
        assert p_post < p
