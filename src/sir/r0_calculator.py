"""
R₀ calculator for the KG contamination SIR model.

R₀ (Basic Reproduction Number) measures how many new Infected nodes a single
Infected node produces before it is Recovered/quarantined.

  R₀ = β / γ

Interpretation:
  R₀ < 1 → contamination dies out naturally
  R₀ = 1 → endemic steady state
  R₀ > 1 → contamination spreads (epidemic in KG terms)

Beta estimation:
  β ≈ retrieval_rate × llm_susceptibility
  - retrieval_rate: how often agents pull from the KG per time step
  - llm_susceptibility: probability LLM accepts and propagates bad context

Gamma estimation:
  γ ≈ validation_frequency × detection_accuracy
  - validation_frequency: fraction of nodes ValidationAgent audits per step
  - detection_accuracy: AUROC of the classifier at catching hallucinations

Usage:
    from src.sir.r0_calculator import R0Calculator
    calc = R0Calculator(retrieval_rate=0.5, llm_susceptibility=0.3,
                        validation_frequency=0.2, detection_accuracy=0.9)
    print(calc.r0)          # → 0.833 (epidemic controlled)
    print(calc.summary())
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class R0Calculator:
    """
    Computes β, γ, and R₀ from interpretable experimental parameters.

    Parameters
    ----------
    retrieval_rate:
        Fraction of KG nodes an agent reads per time step (0–1).
    llm_susceptibility:
        Probability the LLM accepts and re-encodes a hallucinated fact (0–1).
    validation_frequency:
        Fraction of nodes the ValidationAgent audits per time step (0–1).
    detection_accuracy:
        AUROC / detection rate of the validation classifier (0–1).
    """

    retrieval_rate: float
    llm_susceptibility: float
    validation_frequency: float
    detection_accuracy: float

    @property
    def beta(self) -> float:
        """Transmission rate: how fast contamination spreads."""
        return self.retrieval_rate * self.llm_susceptibility

    @property
    def gamma(self) -> float:
        """Recovery rate: how fast ValidationAgent quarantines infected nodes."""
        return self.validation_frequency * self.detection_accuracy

    @property
    def r0(self) -> float:
        """Basic Reproduction Number. Returns inf if gamma == 0."""
        if self.gamma == 0:
            return float("inf")
        return self.beta / self.gamma

    def summary(self) -> dict:
        """Return a dict of all computed values for logging/export."""
        return {
            "retrieval_rate":      self.retrieval_rate,
            "llm_susceptibility":  self.llm_susceptibility,
            "validation_frequency": self.validation_frequency,
            "detection_accuracy":  self.detection_accuracy,
            "beta":                round(self.beta, 4),
            "gamma":               round(self.gamma, 4),
            "r0":                  round(self.r0, 4) if self.r0 != float("inf") else "inf",
            "epidemic":            self.r0 > 1,
        }

    @classmethod
    def from_beta_gamma(cls, beta: float, gamma: float) -> "R0Calculator":
        """Construct directly from raw β and γ (for fitting from observed data)."""
        return cls(
            retrieval_rate=beta,
            llm_susceptibility=1.0,
            validation_frequency=gamma,
            detection_accuracy=1.0,
        )
