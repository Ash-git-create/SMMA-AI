# Phase 4 protocol — graph density arms (RQ3, task #21)

Status: protocol only. No density-arm runs have been executed yet; this
document defines how they will be, once Phase 4 (2026-07-30 → 2026-08-19)
opens. Cross-reference against `docs/thesis_log.md` when the first run
lands and update the `[PENDING-#21-RUN]` marker below per CLAUDE.md rule 9.

## Why this is a load-stage argument, not a run_contamination config

RQ3 asks how graph density affects contamination velocity and reach.
`run_contamination.py` already has a retrieval-time density *proxy*
(`--context-limit`, the number of KG facts served per synthesis/extraction
unit), but that caps an existing neighborhood — it does not change the
neighborhood itself. Two KGs with identical `context_limit=5` behave very
differently if one entity has degree 6 (barely capped) and the other has
degree 600 (99% of its neighborhood is invisible to every retrieval call).
Structural density is a property of the KG the loader builds, not of any
single contamination run, so it belongs in `scripts/load_kg.py`
(`--density`, `--density-seed`; see `src/graph/density.py` for the
sparsification / densification-by-restriction algorithms and their
docstrings for the exact procedure). `experiments/configs/*.yaml` files
remain unchanged — they describe `run_contamination.py` arguments only.

## 3-stage clean room per density arm

Every contamination run in this project uses the 3-stage clean room from
CLAUDE.md rule 8 (load_kg --clear → run_extraction → run_contamination)
with the Neo4j preflight poll. Density arms are the same 3 stages, with
`--density` added to stage 1 and `--tag density_<factor>` added to stage 3
so results are distinguishable in `results/raw/` and `results/summaries/`:

```
# Stage 1 — load, with density manipulation. --clear is MANDATORY whenever
# --density != 1.0 (scripts/load_kg.py refuses otherwise) so a
# density-manipulated KG can never be silently mistaken for the standard
# baseline KG in results/raw/.
python scripts/load_kg.py --clear --density 0.5 --density-seed 42

# Stage 2 — extraction, UNCHANGED from the standard protocol. No new flags:
# extraction's KG-context retrieval (--kg-context, on by default) will
# behave differently under a sparsified/densified KG purely as a
# consequence of stage 1 — see "Measured covariate" below.
python scripts/run_extraction.py --config experiments/configs/extraction_baseline.yaml

# Stage 3 — contamination run, tagged so the density factor is traceable
# end-to-end through results/raw/contamination_density_0.5_<timestamp>_*.
python scripts/run_contamination.py --config experiments/configs/contamination_baseline.yaml \
    --tag density_0.5
```

Repeat per density factor. The realized (not just requested) density is
archived automatically by stage 1 to
`results/raw/kg_density_density_<factor>.json` — always cite the realized
figures in analysis, per CLAUDE.md rule 1 ("numbers come from archived
files"), since sparsification/densification are best-effort and may not
hit the requested factor exactly (this is reported honestly by
`apply_density`, not hidden).

## Proposed grid

| Arm | `--density` | Expected direction |
|---|---|---|
| Sparse | 0.5 | Lower mean entity degree — fewer facts per retrieval neighborhood, contamination should be harder to encounter (lower beta) but each contaminated fact is a larger fraction of what's visible if it IS reached |
| Standard (existing baseline) | 1.0 | No change — current Phase 2/3 arms are this row, already run |
| Dense | 2.0 | Higher mean entity degree — more facts compete for the same `context_limit` retrieval window, so contamination exposure is diluted per-context but the KG overall carries more traversable structure |

All three arms should otherwise use the SAME contamination config
(`contamination_baseline.yaml`: `context_limit=5`, `retrieval_threshold=0.0`,
`audits_per_step=0`, `random_seed=42`) so density is the only manipulated
axis — matching the existing "config diff, not a code diff" discipline
already used for baseline-vs-mitigated arms.

## Caveat: extraction-stage behavior is a measured covariate, not a confound to hide

`run_extraction.py`'s `--kg-context` retrieval calls the SAME
`get_related_triplets(subject=key, obj=key, ...)` that contamination's
transmission cycle uses. Under `--density 0.5`, extraction units whose key
maps to a thinned entity will see a smaller (or empty) KG context passed to
the ExtractionAgent; under `--density 2.0`, restricted-entity keys may see a
richer context while entities excluded by restriction see none at all
(their retrieval pool is now empty, since their triplets were dropped from
the loaded KG entirely — NOT because of `--retrieval-threshold`). This
changes what the ExtractionAgent synthesizes at write-back time, which is
itself part of what RQ3 is asking about (does density change contamination
dynamics, and if so, through which stage of the pipeline). Do not treat this
as noise to control away: instrument it. At minimum, record per-arm from the
stage-2 manifest:
  - fraction of extraction units where `kg_context` was non-empty
  - mean context size actually served (bounded by `context_limit` but not
    always reaching it under `--density 0.5`)

and report these alongside the stage-3 SIR/AUROC/USR outcomes so a density
effect can be attributed to (a) the retrieval/transmission channel in
`run_contamination`, (b) the extraction-stage synthesis channel, or (c)
both — rather than collapsed into a single undifferentiated "density
changed the outcome" claim. This mirrors the existing beta decomposition
instrumentation in `run_contamination.transmission_cycle` (retrieval
component vs reproduction component) — density arms extend that
decomposition one stage earlier.

## What still needs live-Neo4j validation

Everything above the "Proposed grid" section is exercised offline
(`scripts/test_density.py`, pure-function unit tests, no Neo4j). NOT yet
validated against a live KG:
  - `Neo4jClient.bulk_load_triplets` on a density-manipulated (non-1.0)
    record list — the sidecar/report path in `load_kg.py` has not been run
    end-to-end against a real Neo4j instance.
  - Realized density stats on the ACTUAL T-REx degree distribution
    (`data/processed/trex_triplets.jsonl`, 50,000 records) — the synthetic
    hub-and-spoke fixtures in `scripts/test_density.py` are illustrative,
    not a substitute for the real distribution's hub structure. A dry run
    of `apply_density` against the real file (no Neo4j needed) would be a
    cheap sanity step before spending a Neo4j `--clear` cycle.
  - Whether `get_related_triplets`'s `ORDER BY confidence DESC, id` retrieval
    order changes materially under restriction (all kept triplets have
    confidence=1.0 at load time, so this is expected to be a non-issue, but
    unconfirmed against a real run).
  - End-to-end stage 2/3 timing and Groq TPD budget impact of adding a third
    axis (density) on top of the existing seed/arm grid, given the
    documented ~1–3 runs/day free-tier pacing (CLAUDE.md rule 7).

`[PENDING-#21-RUN]` — no density-arm run has been launched. This section
must be resolved (results cited or explicitly still pending) before this
document is treated as anything more than a protocol.
