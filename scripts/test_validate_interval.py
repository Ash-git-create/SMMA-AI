"""
Offline unit test for the RQ3 validation-interval sweep (--validate-every)
in scripts/run_contamination.py.

Exercises the two pure, Neo4j-free helpers the sweep is built on:
  accumulate_candidates — the backlog append (order-preserving, dedup)
  is_validate_step      — flush-step selection (every Nth step, plus
                           unconditionally the final step)

Does not touch Neo4j, an LLM, or run_experiment. Run from project root with
venv active:
    python scripts/test_validate_interval.py
"""

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from run_contamination import accumulate_candidates, is_validate_step

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


def test_accumulate_candidates_dedup_order_preserving():
    print("\n--- accumulate_candidates: dedup + order ---")
    pending: list[str] = []
    accumulate_candidates(pending, ["a", "b", "a", "c"])
    check("first call dedups within itself", pending == ["a", "b", "c"], str(pending))

    accumulate_candidates(pending, ["c", "d", "b", "e"])
    check("second call skips ids already queued, appends only new ones",
          pending == ["a", "b", "c", "d", "e"], str(pending))

    accumulate_candidates(pending, [])
    check("empty new_ids is a no-op", pending == ["a", "b", "c", "d", "e"])


def test_is_validate_step_n1_flushes_every_step():
    print("\n--- is_validate_step: N=1 (default, must match old per-step behavior) ---")
    total = 10
    flushed = [s for s in range(1, total + 1) if is_validate_step(s, total, 1)]
    check("N=1 flushes every step", flushed == list(range(1, total + 1)), str(flushed))


def test_is_validate_step_n_gt_1_flushes_multiples_and_final():
    print("\n--- is_validate_step: N=2/5/10 over 10 steps ---")
    total = 10
    for n, expected in (
        (2,  [2, 4, 6, 8, 10]),
        (5,  [5, 10]),
        (10, [10]),
        # 3 doesn't evenly divide 10 -> final step (10) must still flush
        # even though 10 % 3 != 0 (this is the "nothing escapes solely
        # because the sweep ended" guarantee).
        (3,  [3, 6, 9, 10]),
    ):
        flushed = [s for s in range(1, total + 1) if is_validate_step(s, total, n)]
        check(f"N={n} flushes {expected}", flushed == expected, str(flushed))


def test_is_validate_step_final_step_always_flushes():
    print("\n--- is_validate_step: final-step guarantee ---")
    # N=4 over 10 steps: 10 % 4 != 0, so without the final-step OR-clause
    # step 8's backlog (steps 8,9,10) would never be audited.
    check("N=4, step=10 (final, not a multiple) still flushes",
          is_validate_step(10, 10, 4) is True)
    check("N=4, step=9 (not final, not a multiple) does not flush",
          is_validate_step(9, 10, 4) is False)


def test_is_validate_step_n_le_1_normalizes_to_1():
    print("\n--- is_validate_step: N<=1 normalizes ---")
    check("N=0 behaves like N=1 (flushes every step)",
          all(is_validate_step(s, 10, 0) for s in range(1, 11)))


def test_end_to_end_backlog_simulation():
    """Simulate the run_experiment loop's bookkeeping over 10 steps at
    validate_every=3: every skipped step's ids must survive into the next
    flush, and the backlog must be empty immediately after a flush."""
    print("\n--- end-to-end backlog simulation, validate_every=3 ---")
    total, n = 10, 3
    pending: list[str] = []
    audited_batches = []
    for step in range(1, total + 1):
        step_ids = [f"s{step}_a", f"s{step}_b"]
        accumulate_candidates(pending, step_ids)
        if is_validate_step(step, total, n):
            audited_batches.append(list(pending))
            pending = []
    # flush steps: 3, 6, 9, 10 (final) -> backlogs of size 3,3,3,1 steps'
    # candidates (2 ids/step) = 6,6,6,2 ids
    check("4 flush events for N=3 over 10 steps", len(audited_batches) == 4,
          str([len(b) for b in audited_batches]))
    check("flush sizes are 6,6,6,2 (steps 1-3, 4-6, 7-9, 10)",
          [len(b) for b in audited_batches] == [6, 6, 6, 2],
          str([len(b) for b in audited_batches]))
    check("backlog empty after the last flush", pending == [])
    all_flushed_ids = [tid for batch in audited_batches for tid in batch]
    expected_ids = [f"s{s}_{suf}" for s in range(1, total + 1) for suf in ("a", "b")]
    check("every step's ids appear exactly once across all flushes",
          sorted(all_flushed_ids) == sorted(expected_ids))


if __name__ == "__main__":
    test_accumulate_candidates_dedup_order_preserving()
    test_is_validate_step_n1_flushes_every_step()
    test_is_validate_step_n_gt_1_flushes_multiples_and_final()
    test_is_validate_step_final_step_always_flushes()
    test_is_validate_step_n_le_1_normalizes_to_1()
    test_end_to_end_backlog_simulation()
    print(f"\n\033[32mAll tests passed.\033[0m\n")
