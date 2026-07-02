"""
Smoke-test for agents and SIR module.

Tests:
  1. ExtractionAgent._parse_response — JSON parsing + fence stripping
  2. OrchestrationAgent._parse_response — verdict parsing
  3. SIRModel.run — trajectory shape and conservation (N constant)
  4. R0Calculator — β, γ, R₀ computations
  5. LineageFormula — DNF formula builders

No Neo4j or LLM calls required. Run from project root with venv active:
    python scripts/test_agents.py
"""

import sys
from pathlib import Path

# Windows consoles default to cp1252, which can't print → and other symbols
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.agents.extraction_agent import ExtractionAgent
from src.agents.orchestration_agent import OrchestrationAgent
from src.evaluation.metrics import (
    detection_auroc,
    exact_match,
    normalize_answer,
    token_f1,
    unsupported_ratio,
    veracity_report,
)
from src.graph.provenance_schema import LineageFormula
from src.injection.error_injector import ErrorInjector
from src.sir.r0_calculator import R0Calculator
from src.sir.sir_model import SIRModel

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"


def check(name: str, condition: bool, detail: str = "") -> None:
    tag = PASS if condition else FAIL
    msg = f"  [{tag}] {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    if not condition:
        sys.exit(1)


def test_extraction_parsing():
    print("\n--- ExtractionAgent._parse_response ---")
    agent = ExtractionAgent.__new__(ExtractionAgent)
    agent.agent_id = "test"

    # Clean JSON
    raw = '[{"subject":"Paris","predicate":"capital_of","object":"France"}]'
    result = agent._parse_response(raw)
    check("clean JSON", len(result) == 1 and result[0]["subject"] == "Paris")

    # Markdown-fenced JSON
    fenced = '```json\n[{"subject":"A","predicate":"rel","object":"B"}]\n```'
    result = agent._parse_response(fenced)
    check("markdown-fenced JSON", len(result) == 1 and result[0]["object"] == "B")

    # Empty array
    result = agent._parse_response("[]")
    check("empty array", result == [])

    # Invalid JSON → empty list (no crash)
    result = agent._parse_response("not json at all")
    check("invalid JSON → empty list", result == [])

    # Missing fields → filtered out
    partial = '[{"subject":"X"}]'
    result = agent._parse_response(partial)
    check("missing fields filtered", result == [])


def test_orchestration_parsing():
    print("\n--- OrchestrationAgent._parse_response ---")
    agent = OrchestrationAgent.__new__(OrchestrationAgent)
    agent.agent_id = "test"

    good = '{"verdict":"SUPPORTED","confidence":0.9,"reason":"directly stated"}'
    r = agent._parse_response(good)
    check("SUPPORTED verdict", r["verdict"] == "SUPPORTED" and r["confidence"] == 0.9)

    bad_verdict = '{"verdict":"MAYBE","confidence":0.5,"reason":"?"}'
    r = agent._parse_response(bad_verdict)
    check("invalid verdict clamped to UNCERTAIN", r["verdict"] == "UNCERTAIN")

    out_of_range = '{"verdict":"SUPPORTED","confidence":1.5,"reason":"x"}'
    r = agent._parse_response(out_of_range)
    check("confidence clamped to 1.0", r["confidence"] == 1.0)

    r = agent._parse_response("bad json !!!")
    check("bad JSON → None (no fake verdict)", r is None)


def test_sir_model():
    print("\n--- SIRModel ---")
    model = SIRModel(beta=0.3, gamma=0.05)
    trajectory = model.run(S0=49990, I0=10, R0=0, steps=100)

    check("trajectory length = steps+1", len(trajectory) == 101)

    # Conservation: N must be constant throughout the whole trajectory
    N0 = trajectory[0]["N"]
    max_dev = max(abs(t["N"] - N0) for t in trajectory)
    check("N conserved across all steps", max_dev < 0.01,
          f"max deviation = {max_dev:.4f}")

    # With R₀ > 1, I should peak above initial value
    peak = model.peak_infected(S0=49990, I0=10, R0=0, steps=200)
    check("I peaks above initial", peak["I"] > 10, f"peak I = {peak['I']:.1f}")

    # With β=0, no spreading
    zero_spread = SIRModel(beta=0.0, gamma=0.1)
    traj = zero_spread.run(S0=1000, I0=10, R0=0, steps=10)
    check("β=0 → no new infections", traj[-1]["S"] == 1000.0)


def test_r0_calculator():
    print("\n--- R0Calculator ---")
    calc = R0Calculator(
        retrieval_rate=0.5,
        llm_susceptibility=0.6,
        validation_frequency=0.2,
        detection_accuracy=0.9,
    )
    check("beta = retrieval × susceptibility", abs(calc.beta - 0.30) < 1e-9)
    check("gamma = freq × accuracy", abs(calc.gamma - 0.18) < 1e-9)
    check("R₀ = beta / gamma", abs(calc.r0 - (0.30 / 0.18)) < 1e-6)
    check("epidemic flag when R₀ > 1", calc.r0 > 1 and calc.summary()["epidemic"])

    # Controlled scenario
    controlled = R0Calculator(
        retrieval_rate=0.2,
        llm_susceptibility=0.3,
        validation_frequency=0.5,
        detection_accuracy=0.95,
    )
    check("controlled: R₀ < 1", controlled.r0 < 1, f"R₀={controlled.r0:.3f}")

    # Zero gamma → inf R₀
    no_validation = R0Calculator(
        retrieval_rate=0.5,
        llm_susceptibility=0.5,
        validation_frequency=0.0,
        detection_accuracy=0.9,
    )
    check("γ=0 → R₀=inf", no_validation.r0 == float("inf"))

    # from_beta_gamma convenience constructor
    calc2 = R0Calculator.from_beta_gamma(beta=0.3, gamma=0.15)
    check("from_beta_gamma", abs(calc2.r0 - 2.0) < 1e-9)


def test_lineage_formula():
    print("\n--- LineageFormula ---")
    f1 = LineageFormula.from_single("src_a")
    check("from_single", f1 == "src_a")

    conj = LineageFormula.conjunction(["src_a", "src_b", "src_c"])
    check("conjunction", conj == "src_a AND src_b AND src_c")

    disj = LineageFormula.disjunction(["src_x", "src_y"])
    check("disjunction", disj == "src_x OR src_y")

    ancestors = LineageFormula.ancestors("src_a AND src_b OR src_c")
    check("ancestors parsed", ancestors == {"src_a", "src_b", "src_c"})


def test_metrics():
    print("\n--- evaluation.metrics ---")
    check("normalize strips articles/punct",
          normalize_answer("The  Beatles!") == "beatles")
    check("EM exact hit", exact_match("Paris", "paris.") == 1)
    check("EM miss", exact_match("London", "Paris") == 0)
    check("F1 partial overlap", 0.0 < token_f1("John Doman actor", "John Doman") < 1.0)
    check("F1 empty pred", token_f1("", "Paris") == 0.0)

    rep = veracity_report(["SUPPORTS", "REFUTES", "BOGUS"],
                          ["SUPPORTS", "SUPPORTS", "NOT ENOUGH INFO"])
    check("veracity accuracy", abs(rep["accuracy"] - 2 / 3) < 1e-9)
    check("bogus label mapped to NEI", rep["confusion"]["NOT ENOUGH INFO"].get("NOT ENOUGH INFO") == 1)

    check("AUROC separable", detection_auroc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == 1.0)
    check("AUROC single class → 0.5", detection_auroc([0, 0], [0.1, 0.9]) == 0.5)
    check("USR", unsupported_ratio([True, False, False]) == 2 / 3)


def test_error_injector_transforms():
    print("\n--- ErrorInjector pure transforms ---")
    check("qualifier: parenthetical stripped",
          ErrorInjector.strip_qualifier("Arthur's Magazine (1844-1846)") == "Arthur's Magazine")
    check("qualifier: trailing comma-qualifier stripped",
          ErrorInjector.strip_qualifier("Los Angeles, California") == "Los Angeles")
    check("qualifier: temporal clause stripped",
          ErrorInjector.strip_qualifier("president from 1990 until 1995").startswith("president"))
    check("qualifier: none present → None",
          ErrorInjector.strip_qualifier("Paris") is None)
    check("qualifier: full date → year",
          ErrorInjector.strip_qualifier("24 October 1968") == "1968")
    check("qualifier: ISO date → year",
          ErrorInjector.strip_qualifier("1968-10-24") == "1968")
    check("qualifier: bare year untouched",
          ErrorInjector.strip_qualifier("1968") is None)

    check("strengthen: nominated for → winner of",
          ErrorInjector.strengthen_predicate("nominated for") == "winner of")
    check("strengthen: cast member → lead actor",
          ErrorInjector.strengthen_predicate("cast member") == "lead actor")

    check("strengthen: associated with → caused",
          ErrorInjector.strengthen_predicate("is associated with") == "is caused")
    check("strengthen: member of → leader of",
          ErrorInjector.strengthen_predicate("was a member of") == "was a leader of")
    check("strengthen: no weak form → None",
          ErrorInjector.strengthen_predicate("was born in") is None)


if __name__ == "__main__":
    test_extraction_parsing()
    test_orchestration_parsing()
    test_sir_model()
    test_r0_calculator()
    test_lineage_formula()
    test_metrics()
    test_error_injector_transforms()
    print(f"\n\033[32mAll tests passed.\033[0m\n")
