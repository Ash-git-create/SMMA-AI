"""
Phase 1 simulation runner — end-to-end SIR pipeline demo.

What it does per time step:
  1. Seeds N_seed random Susceptible nodes as Infected (one-off at T=0).
  2. Advances the theoretical SIR model one step (β, γ from CLI).
  3. Runs one ValidationAgent audit pass against the real Neo4j KG.
  4. Records both the theoretical SIR curve and the observed KG state counts.
  5. Writes the full trajectory to results/raw/simulation_<timestamp>.csv.

This is a Phase 1 proof-of-concept: spread is modelled mathematically (SIRModel)
while the validation pipeline (OrchestrationAgent + cascade deprecation) is real.
Full LLM-driven contamination spread starts in Phase 2.

Run from project root with venv active:
    python scripts/run_simulation.py
    python scripts/run_simulation.py --steps 20 --seed-infected 100 --beta 0.3 --gamma 0.05
    python scripts/run_simulation.py --steps 10 --no-llm   # skip LLM audit, count-only mode
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

# Windows consoles default to cp1252, which can't print β/γ/R₀
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.graph.neo4j_client import Neo4jClient
from src.graph.provenance_schema import STATE_INFECTED, STATE_SUSCEPTIBLE
from src.sir.r0_calculator import R0Calculator
from src.sir.sir_model import SIRModel, SIRState

logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")

RESULTS_DIR = ROOT / "results" / "raw"


def seed_infected(client: Neo4jClient, n: int) -> list[str]:
    """Randomly mark n Susceptible nodes as Infected. Returns their IDs."""
    candidates = client.search_triplets(state=STATE_SUSCEPTIBLE, limit=n * 2, randomize=True)
    if not candidates:
        logger.error("No Susceptible nodes found — load the KG first (scripts/load_kg.py).")
        sys.exit(1)
    chosen = random.sample(candidates, min(n, len(candidates)))
    for t in chosen:
        client.update_state(t["id"], STATE_INFECTED)
    logger.warning(f"Seeded {len(chosen)} nodes as Infected (state=I).")
    return [t["id"] for t in chosen]


def run_simulation(
    steps: int,
    n_seed: int,
    beta: float,
    gamma: float,
    audit_sample: int,
    use_llm: bool,
) -> list[dict]:
    """
    Run the simulation and return the trajectory as a list of row dicts.

    Each row contains:
        step, theo_S, theo_I, theo_R, obs_S, obs_I, obs_R, quarantined, cascaded
    """
    model = SIRModel(beta=beta, gamma=gamma)
    calc = R0Calculator.from_beta_gamma(beta=beta, gamma=gamma)
    logger.info(f"SIR params: β={beta}, γ={gamma}, R₀={calc.r0:.3f} "
                f"({'EPIDEMIC' if calc.r0 > 1 else 'controlled'})")

    trajectory = []

    with Neo4jClient() as client:
        # --- T=0: seed infected nodes and record initial state ---
        seed_infected(client, n_seed)
        obs = client.count_by_state()
        S0 = float(obs.get(STATE_SUSCEPTIBLE, 0))
        I0 = float(obs.get(STATE_INFECTED, 0))
        R0_obs = float(obs.get("R", 0))

        theo_state = SIRState(S=S0, I=I0, R=R0_obs)
        trajectory.append(_row(0, theo_state, obs, quarantined=0, cascaded=0))
        logger.info(f"T=0 | Theo S={theo_state.S:.0f} I={theo_state.I:.0f} R={theo_state.R:.0f} "
                    f"| Obs {obs}")

        for t in range(1, steps + 1):
            # --- Theoretical SIR step ---
            theo_state = model.step(theo_state)

            # --- Real validation pass ---
            quarantined = 0
            cascaded = 0
            if use_llm:
                from src.agents.validation_agent import ValidationAgent
                agent = ValidationAgent(neo4j_client=client)
                result = agent.run_audit_pass(sample_size=audit_sample)
                quarantined = result["quarantined"]
                cascaded = result["cascaded"]
            else:
                # Count-only mode: just record KG state without LLM calls
                pass

            obs = client.count_by_state()
            trajectory.append(_row(t, theo_state, obs, quarantined, cascaded))
            logger.info(
                f"T={t:02d} | "
                f"Theo S={theo_state.S:.0f} I={theo_state.I:.0f} R={theo_state.R:.0f} | "
                f"Obs {obs} | quarantined={quarantined} cascaded={cascaded}"
            )

    return trajectory


def _row(step: int, theo: SIRState, obs: dict, quarantined: int, cascaded: int) -> dict:
    return {
        "step":        step,
        "theo_S":      round(theo.S, 2),
        "theo_I":      round(theo.I, 2),
        "theo_R":      round(theo.R, 2),
        "obs_S":       obs.get("S", 0),
        "obs_I":       obs.get("I", 0),
        "obs_R":       obs.get("R", 0),
        "quarantined": quarantined,
        "cascaded":    cascaded,
    }


def save_csv(trajectory: list[dict], beta: float, gamma: float) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = RESULTS_DIR / f"simulation_b{beta}_g{gamma}_{ts}.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=trajectory[0].keys())
        writer.writeheader()
        writer.writerows(trajectory)
    logger.success(f"Trajectory saved → {out}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 1 SIR simulation runner")
    parser.add_argument("--config",         type=str,   default=None, help="YAML config (experiments/configs/*.yaml); CLI flags override")
    parser.add_argument("--steps",          type=int,   default=10,   help="Number of time steps")
    parser.add_argument("--seed-infected",  type=int,   default=50,   help="Nodes to seed as Infected at T=0")
    parser.add_argument("--beta",           type=float, default=0.3,  help="Transmission rate β")
    parser.add_argument("--gamma",          type=float, default=0.05, help="Recovery rate γ")
    parser.add_argument("--audit-sample",   type=int,   default=100,  help="Nodes audited per step (LLM mode)")
    parser.add_argument("--random-seed",    type=int,   default=42,   help="Seed for Python RNG (reproducibility)")
    parser.add_argument("--no-llm",         action="store_true",      help="Skip LLM audit — count-only mode")

    # Config file values become the defaults; explicit CLI flags still win.
    pre_args, _ = parser.parse_known_args()
    if pre_args.config:
        from src.config import load_config
        cfg = load_config(pre_args.config)
        parser.set_defaults(**cfg)
    args = parser.parse_args()

    random.seed(args.random_seed)

    logger.info("=== Phase 1 Simulation Runner ===")
    logger.info(f"steps={args.steps}, seed={args.seed_infected}, β={args.beta}, γ={args.gamma}, "
                f"rng_seed={args.random_seed}, llm={'OFF' if args.no_llm else 'ON'}")

    trajectory = run_simulation(
        steps=args.steps,
        n_seed=args.seed_infected,
        beta=args.beta,
        gamma=args.gamma,
        audit_sample=args.audit_sample,
        use_llm=not args.no_llm,
    )

    out_path = save_csv(trajectory, args.beta, args.gamma)

    # Print summary table
    print(f"\n{'step':>4} | {'theo_S':>8} {'theo_I':>8} {'theo_R':>8} | "
          f"{'obs_S':>7} {'obs_I':>7} {'obs_R':>7}")
    print("-" * 70)
    for row in trajectory:
        print(
            f"{row['step']:>4} | "
            f"{row['theo_S']:>8.0f} {row['theo_I']:>8.0f} {row['theo_R']:>8.0f} | "
            f"{row['obs_S']:>7} {row['obs_I']:>7} {row['obs_R']:>7}"
        )
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    main()
