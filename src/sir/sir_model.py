"""
Discrete-time SIR model for KG node contamination.

Each KG node is in one of three states:
  S — Susceptible: pristine, can be contaminated by agent retrieval of bad context
  I — Infected: contains an error, can spread to downstream nodes
  R — Recovered: quarantined by ValidationAgent, no longer participates in propagation

Difference equations (per time step t):
  ΔS = -β * (S/N) * I
  ΔI = +β * (S/N) * I - γ * I
  ΔR = +γ * I

Where:
  β  = transmission rate (retrieval_frequency × llm_susceptibility)
  γ  = recovery rate (validation_efficacy)
  N  = total nodes (S + I + R, constant)
  R₀ = β / γ  (basic reproduction number)

Usage:
    from src.sir.sir_model import SIRModel
    model = SIRModel(beta=0.3, gamma=0.1)
    trajectory = model.run(S0=49990, I0=10, R0=0, steps=50)
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SIRState:
    S: float  # Susceptible node count
    I: float  # Infected node count
    R: float  # Recovered node count

    @property
    def N(self) -> float:
        return self.S + self.I + self.R

    def as_dict(self, step: int) -> dict:
        return {"step": step, "S": self.S, "I": self.I, "R": self.R, "N": self.N}


@dataclass
class SIRModel:
    """
    Discrete-time SIR compartmental model.

    Parameters
    ----------
    beta:
        Transmission rate — probability that an infected node contaminates a
        susceptible neighbour per time step. In the KG context this combines
        retrieval frequency and LLM susceptibility to bad context.
    gamma:
        Recovery rate — probability that an infected node is caught and quarantined
        by the ValidationAgent per time step.
    """

    beta: float
    gamma: float

    def step(self, state: SIRState) -> SIRState:
        """Advance one time step using forward Euler integration."""
        N = state.N
        if N == 0:
            return SIRState(S=0.0, I=0.0, R=0.0)

        new_infections = self.beta * (state.S / N) * state.I
        new_recoveries = self.gamma * state.I

        # Clamp to valid ranges to avoid floating-point drift
        new_infections = min(new_infections, state.S)
        new_recoveries = min(new_recoveries, state.I)

        return SIRState(
            S=state.S - new_infections,
            I=state.I + new_infections - new_recoveries,
            R=state.R + new_recoveries,
        )

    def run(self, S0: float, I0: float, R0: float, steps: int) -> list[dict]:
        """
        Simulate *steps* time steps from initial conditions.

        Returns a list of dicts, one per step, with keys: step, S, I, R, N.
        Step 0 is the initial state.
        """
        state = SIRState(S=float(S0), I=float(I0), R=float(R0))
        trajectory = [state.as_dict(0)]
        for t in range(1, steps + 1):
            state = self.step(state)
            trajectory.append(state.as_dict(t))
        return trajectory

    def peak_infected(self, S0: float, I0: float, R0: float, steps: int) -> dict:
        """Return the time step and count at maximum infection."""
        trajectory = self.run(S0, I0, R0, steps)
        peak = max(trajectory, key=lambda x: x["I"])
        return peak

    def equilibrium(self, S0: float, I0: float, R0: float, max_steps: int = 1000) -> dict:
        """Run until I < 1 or max_steps reached. Returns the final state dict."""
        state = SIRState(S=float(S0), I=float(I0), R=float(R0))
        for t in range(1, max_steps + 1):
            state = self.step(state)
            if state.I < 1.0:
                return state.as_dict(t)
        return state.as_dict(max_steps)
