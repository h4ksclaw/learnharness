"""Bayesian Knowledge Tracing — updates mastery probability after each interaction.

Classic BKT: P(L) = probability the learner has mastered the skill.
After each observation (correct/incorrect), we update P(L) via Bayes' rule.

P(L|correct) = P(correct|L) * P(L) / P(correct)
P(correct) = P(correct|L)*P(L) + P(correct|!L)*(1-P(L))

Then apply transit: P(L_new) = P(L|obs) + (1 - P(L|obs)) * P(T)
"""

from app.config import settings


class KnowledgeTracer:
    """Bayesian Knowledge Tracing for per-concept mastery estimation."""

    def __init__(
        self,
        prior: float | None = None,
        slip: float | None = None,
        guess: float | None = None,
        transit: float | None = None,
    ):
        self.prior = prior or settings.bkt_prior
        self.slip = slip or settings.bkt_slip
        self.guess = guess or settings.bkt_guess
        self.transit = transit or settings.bkt_transit

    def update(self, p_mastery: float, observed_correct: bool) -> tuple[float, float]:
        """Update mastery probability after an observation.

        Args:
            p_mastery: current P(known), 0-1
            observed_correct: was the response correct?

        Returns:
            (new_p_mastery, delta)
        """
        # Bayesian update
        if observed_correct:
            # P(known | correct)
            p_known_given_obs = (
                (1 - self.slip)
                * p_mastery
                / ((1 - self.slip) * p_mastery + self.guess * (1 - p_mastery))
            )
        else:
            # P(known | incorrect)
            p_known_given_obs = (
                self.slip * p_mastery / (self.slip * p_mastery + (1 - self.guess) * (1 - p_mastery))
            )

        # Apply transit (learning can happen between observations)
        new_p = p_known_given_obs + (1 - p_known_given_obs) * self.transit

        # Clamp
        new_p = max(0.01, min(0.99, new_p))

        return new_p, new_p - p_mastery

    def infer_from_chat(self, p_mastery: float, confidence: float) -> tuple[float, float]:
        """Soften mastery from conversational inference (not a hard correct/incorrect).

        When the LLM analyzes a chat message and assigns a confidence score (0-1)
        that the learner demonstrated mastery, we update more gently.

        Args:
            p_mastery: current P(known)
            confidence: LLM's confidence the learner knows this concept (0-1)

        Returns:
            (new_p_mastery, delta)
        """
        # Treat as a soft observation — blend toward the inference
        alpha = 0.3  # learning rate for soft updates
        new_p = (1 - alpha) * p_mastery + alpha * confidence
        new_p = max(0.01, min(0.99, new_p))
        return new_p, new_p - p_mastery


# Singleton
knowledge_tracer = KnowledgeTracer()
