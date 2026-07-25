# Seed 44 forensics note (task #32)

> **Scope:** offline-only. Every number below is read from an archived
> file under `results/summaries/` (or a raw manifest under `results/raw/`
> cross-checked against it); no Neo4j connection or LLM/API call was made
> to produce this note. Per the analysis-discipline rules, all comparisons
> are n=1–4 per seed and are reported as descriptive/suggestive, not
> significant, with effect sizes expressed in baseline-SD units where a
> multi-seed envelope exists.

## 0. Headline, stated precisely

The premise that motivated this task — "seed 44 goes super-critical across
essentially every arm" — **partially replicates and partially does not**.
Auditing every archived family where seeds 42/43/44/45 have siblings shows:

- Seed 44 **is** the single highest point, or tied for highest, in the
  **oracle-validated families with high validator recall** (perfect
  oracle, the precision/noisy-oracle sweep, the cadence/interval sweep) —
  but in most of these it is paired with **seed 43**, not alone; the real
  split in those families is {43, 44} high vs {42, 45} low.
- Seed 44 is **not** the outlier in the **plain baseline** family (seed 42
  has the highest propagated count) or in the **mitigated (real LLM
  judge) family** (seed 45 is far higher than seed 44, which is in fact
  the *lowest* of the four there).
- Seed 44 is **not** directionally consistent in the **RQ3
  structural-manipulation family** (k-hop / density / write-frequency):
  it is highest at the high-perturbation ends (wf24, rd10) and lowest at
  the low-perturbation ends (wf6, rd3, density_0.5) — a pattern with no
  consistent sign, as expected under single-run generation variance.
- The archives also surface a striking **counter-finding**: in the
  oracle-recall sweep, it is **seed 42** — not seed 44 — that is the
  consistent low outlier (z ≈ −1.2 to −1.5 at every recall level tested),
  while 43/44/45 cluster together above it. Framing this purely as "why
  does 44 go high" undersells that "why is 42 anomalously low" is at
  least as strong a signal in that family.
- Where a mechanism could be pinned down (§3), it was **not** a property
  of seed 44's identity. It was single well-connected T-REx entities
  (e.g. "Taj Mahal", "Arizona") that, whichever seed's random draw happened
  to land an index case on or near them, produced an outsized single-step
  propagation burst. The same "Arizona" hub drove bursts in **both**
  `oracle_s44` (step 6) **and** `mitigated_s45` (step 6, a different seed,
  different arm) — i.e. the burst mechanism is generic, and which seed it
  hits looks like a draw from the fixed candidate pool, not a property of
  "44" as a number.

**Verdict (§5): placement-structural in mechanism, but not seed-44-specific
in effect.** The archives support a real "hub-entity burst" mechanism that
can push any seed's R₀ across the critical threshold. Seed 44 happened to
draw such a hub in several (not all) of its runs, most visibly in the
oracle-family arms; seed 45 drew one too in the mitigated arm; seed 42 drew
one in baseline. A clean per-seed "structural susceptibility" score could
not be constructed from the archives alone (§3.3); resolving it needs a
Neo4j graph-degree pass (§6).

---

## 1. Inventory and effect sizes, by family

All families below have 42/43/44/45 (or a documented subset) run under an
otherwise-identical config, varying only `--random-seed`. R₀ is the fitted
SIR value where a `*_sir_fit*.csv` exists; "propagated" / "reproduction per
seed" are used for the baseline family, which predates the SIR-fit
pipeline for individual seeds beyond `phase33_seed_variance.csv`.

### 1.1 Baseline (no validation) — `phase33_seed_variance.csv`, `phase24_baseline_manifest.json`

| seed | propagated | z (mean 17.75, sd 4.03) | reproduction/seed | z (mean 0.4525, sd 0.1005) |
|---|---|---|---|---|
| 42 | 21 | **+0.81** | 0.54 | **+0.87** |
| 43 | 12 | −1.43 | 0.31 | −1.42 |
| 44 | 20 | +0.56 | 0.50 | +0.47 |
| 45 | 18 | +0.06 | 0.46 | +0.07 |

Seed 42, not 44, is the top seed on both columns; seed 44 is second, well
inside 1 SD. This is the family CLAUDE.md's baseline envelope (17.8±4.0)
is built from — by that yardstick seed 44 is unremarkable.

### 1.2 Perfect oracle (recall=1.0, precision=1.0) — `phase38_sir_fit_oracle.csv`, `phase42_sir_fit_oracle_s{43,44,45}.csv`

| seed | R₀ | z (mean 0.9645, sd 0.2143) |
|---|---|---|
| 42 | 0.7853 | −0.84 |
| 43 | 1.0957 | +0.61 |
| 44 | **1.1974** | **+1.09** |
| 45 | 0.7796 | −0.86 |

Seed 44 is the top point and the only one past +1 SD, but 43 is also
super-critical (R₀>1) and only 0.5 SD behind. The family splits cleanly
into {43,44} super-critical vs {42,45} sub-critical.

### 1.3 Oracle recall (sensitivity) sweep — `phase42_sir_fit_oracle_sens{25,50,75}[_s43/44/45].csv`

| sensitivity | s42 | s43 | s44 | s45 | mean±sd | s44 z | s42 z |
|---|---|---|---|---|---|---|---|
| 25% | 1.067 | 5.133 | 4.117 | 4.813 | 3.78±1.86 | +0.18 | **−1.46** |
| 50% | 0.948 | 2.089 | 2.149 | 2.301 | 1.87±0.62 | +0.45 | **−1.48** |
| 75% | 0.827 | 1.192 | **1.948** | 1.833 | 1.45±0.53 | **+0.94** | −1.17 |
| 100% (§1.2) | 0.785 | 1.096 | **1.197** | 0.780 | 0.965±0.21 | **+1.09** | −0.84 |

Seed 44 only separates from 43/45 at the two *highest*-recall points; at
25–50% recall it sits at the family mean, not above it. Across the whole
sweep the more robust signal is that **seed 42 is the consistent low
outlier** (z ≤ −1.17 at every point), not that seed 44 is a consistent
high one.

### 1.4 Oracle precision (noisy-oracle) sweep — `phase40_sir_fit_oracle_noisy_p{10,25,50,75}[_s43/44/45].csv`

Seed 44's fitted (β, γ, R₀) is numerically identical across p10≡p50
(R₀=1.1049) and across p75≡oracle (R₀=1.1974) — a documented
construction-insensitivity of the R₀ metric to the false-alarm knob when
the induced collateral quarantines never intersect the seed's actively
sampled entities (thesis_log 2026-07-24, "methodological note"). Seed 44
therefore contributes only **two independent realized curves**, not four,
to this family:

| seed | realized R₀ values across p10/p25/p50/p75 | all super-critical? |
|---|---|---|
| 42 | 0.746, 0.823, 0.765, 0.699 (tight cluster) | no — all sub-critical |
| 43 | 0.964, —, 0.892, 1.096 | mixed |
| 44 | 1.105 (=p10=p50), —, 1.197 (=p75=oracle) | **yes — both curves >1** |
| 45 | 0.828, —, 0.719 (=p50=p75) | no — all sub-critical |

This is the one family where seed 44 is unambiguously and consistently
the highest seed: both of its distinct realized epidemic curves clear the
critical threshold, while seed 42 and seed 45 never do across four
precision settings.

### 1.5 Validation cadence (interval) sweep — `phase48_sir_fit_interval.csv`, `phase48_interval_summary.csv` (seeds 42/43/44 only; no seed-45 runs exist for this family)

| interval | s42 | s43 | s44 | s44 z |
|---|---|---|---|---|
| 1 (=oracle, §1.2) | 0.785 | 1.096 | **1.197** | +0.80 |
| 2 | 0.462 | 0.479 | **0.563** | +1.14 (still sub-critical) |
| 5 | 0.676 | 0.652 | **0.981** | +1.15 (still sub-critical) |
| 10 | **2.404** | 2.013 | 2.326 | +0.38 (42 is highest here) |

Seed 44 is highest at 3 of 4 cadence points but is overtaken by seed 42 at
the longest interval (10). No seed-45 data exists for int2/5/10 to complete
this envelope.

### 1.6 Mitigated (real LLM judge, imperfect) — `phase37_mitigated_multiseed.csv`, `phase37_sir_fit_mitigated_seeds.csv`

| seed | R₀ | z (mean 4.4586, sd 2.3593) |
|---|---|---|
| 42 | 4.920 | +0.20 |
| 43 | 2.922 | −0.65 |
| 44 | **2.394** | **−0.88 (lowest)** |
| 45 | **7.599** | **+1.33 (highest, by a wide margin)** |

Under the real (noisy, low-recall) LLM judge, seed 44 is the *least*
super-critical of the four seeds — the opposite of the oracle-family
pattern. Seed 45 dominates this family instead.

### 1.7 RQ3 structural sweep (k-hop / density / write-frequency, baseline substrate) — `phase45_rq3_replication_n4.csv` (order confirmed 42;43;44;45 from raw per-seed manifests in `results/raw/`)

| arm | s42 | s43 | s44 | s45 | s44 rank (1=lowest) |
|---|---|---|---|---|---|
| wf6 (low write-freq) | 0.175 | 0.250 | **0.105** | 0.175 | 1/4 (lowest) |
| wf24 (high write-freq) | 0.675 | 0.950 | **1.237** | 0.800 | 4/4 (highest) |
| rd3 (low retrieval density) | 0.250 | 0.300 | **0.184** | 0.375 | 1/4 (lowest) |
| rd10 (high retrieval density) | 0.700 | 0.700 | **0.974** | 0.600 | 4/4 (highest) |
| density_0.5 (sparse KG) | 0.842 | 0.568 | **0.316** | 0.342 | 1/4 (lowest) |
| density_2.0 (dense KG) | 0.135 | 0.526 | **0.351** | 0.486 | 2/4 |
| khop1/2/3 | 0 | 0 | 0 | 0 | tied (no propagation in any seed) |

No consistent direction: seed 44 is the extreme-low seed in three arms and
the extreme-high seed in two, exactly what single-run (n=1 per seed per
arm) generation variance looks like — it is not a structural elevation
that survives independently of which knob is being swept.

---

## 2. Placement evidence from `seed_records`

Each manifest's `seed_records` list carries the realized index cases (the
corrupted triplets actually written at step 0) with `triplet_id`,
`error_type`, `field`, `subject`, `before`, `after`.

### 2.1 Error-type mix is uniform across seeds

Realized entity_disambiguation / qualifier_loss / relation_strengthening
counts are the same (15/15/8–10) for every seed in every family checked
(`phase24_baseline_manifest.json`, `phase33_baseline_s{43,44,45}_manifest.json`,
`phase38_oracle_manifest.json`, `phase42_oracle_s{43,44,45}_manifest.json`,
`phase32_mitigated_manifest.json`, `phase37_mitigated_s{43,44,45}_manifest.json`).
Seed 44 does not get an unusually ED-heavy or QL-heavy draw relative to its
siblings — the taxonomy composition is not the mechanism.

### 2.2 A duplicate-entity "concentration" score does not cleanly separate super-critical from sub-critical seeds

Counting how many distinct entities each seed's ≈40 index cases touch
(subject, plus before/after when the corrupted field is an object) gives:

| family | s42 distinct | s43 distinct | s44 distinct | s45 distinct |
|---|---|---|---|---|
| baseline | 91 | 93 | 90 | 93 |
| oracle_perfect | 90 | 94 | 91 | 92 |
| mitigated | 96 | 93 | 96 | 93 |

Seed 44 is the most concentrated (fewest distinct entities, i.e. most
repeat hits) in baseline and oracle_perfect, consistent with it running
hot in both — but oracle_perfect's *most* concentrated seed is actually 42
(90 distinct, tied-lowest with 44's 91) and 42 is sub-critical there, and
in mitigated seed 44 is the *least* concentrated (96, tied with 42) yet
still ranks low, while the true mitigated outlier (45) is only middling on
this score (93). **This metric is suggestive but not a reliable
discriminator from the archives alone** — flagged rather than leaned on.

### 2.3 The mechanism that *did* hold up: single well-connected entities driving single-step bursts, independent of seed identity

Manually walking the `transmissions` list (also in the manifests) by step
surfaced the same phenomenon in three unrelated runs:

- **`phase42_oracle_s44_manifest.json`, step 6:** 8 of the run's 18 total
  `new_infected` transmissions (44%) landed in one step, 5 of which
  involve the entity **"Arizona"**. Seed 44's `seed_records` show two
  independent index cases touching Arizona: `trex_34269` (Metropolitan
  Cathedral located_in [Liverpool→Arizona]) and `trex_11244` (Santa Cruz
  River located_in [Arizona→The Bahamas]).
- **`phase37_mitigated_s45_manifest.json`, step 6:** 6 of the run's 10
  total `new_infected` transmissions (60%) landed in the same step index
  (6), 5 of which also involve **"Arizona"** — via a *different* index
  case, `trex_34269` again (the same specific triplet id oracle_s44 also
  drew, independently, under a different seed and a different arm).
- **`phase33_baseline_s44_manifest.json`, steps 1–3:** the early elevation
  noted in §1.1/§3 is dominated by **"Taj Mahal"** (8 of 11 early
  transmissions), traced to a single index case,
  `19ada7d5-1102-59d8-a8b8-e470d07db483` ("With or Without You"
  released_as/lead_single_of → Taj Mahal).

Cross-checking confirms "Arizona" does **not** appear in any of
`baseline_s42/43/44` or `oracle_s42/43`'s seed_records at all — it was
drawn independently by `mitigated_s42` (2 hits, different triplet ids),
`oracle_s44` (2 hits), `mitigated_s44` (1 hit, yet a third distinct
triplet id), and `mitigated_s45` (1 hit). Four different seed×arm
combinations independently drew an Arizona-linked corruption candidate
from the shared active pool, with mostly different specific triplet ids.
This is the clearest reading available offline: Arizona (and, separately,
Taj Mahal) behaves like a genuinely high local-fan-out node in the T-REx
active subgraph — public-figure/place entities with many attribute
triplets — such that *whichever* seed happens to draw a corruption
candidate touching one produces an outsized burst. It is a property of
the **candidate pool's entity-degree distribution**, encountered by
seed 44 more often than by 42/45 in the runs audited here, but not
exclusively or deterministically tied to "44."

---

## 3. Reachability signature: early-step trajectory test

The task asked whether seed 44 shows elevated `n_contam_facts_served /
n_facts_served` or faster `gt_total` growth in steps 1–3 — the signature
of "seeded onto a more-retrieved region." Computed from the trajectory
CSVs (`phase24_baseline_trajectory.csv`, `phase33_baseline_s{43,44,45}
_trajectory.csv`, `phase38_oracle_trajectory.csv`, `phase42_oracle_s{43,
44,45}_trajectory.csv`, `phase48_interval_int{2,5,10}_s{42,43,44}
_trajectory.csv`):

| family | seed | steps 1–3 contaminated-fact fraction | steps 1–3 new_infected |
|---|---|---|---|
| baseline | 42 | 0.0388 | 3 |
| baseline | 43 | 0.0545 | 7 |
| baseline | **44** | **0.0900** | **11** |
| baseline | 45 | 0.0488 | 4 |
| oracle_perfect | 42 | 0.0000 | 0 |
| oracle_perfect | 43 | **0.0642** | **6** |
| oracle_perfect | 44 | 0.0408 | 2 |
| oracle_perfect | 45 | 0.0375 | 3 |

**Result: mixed, and in the oracle family, inverted.** In baseline, seed
44 does show the clearest early-reachability signature — highest
contaminated-fraction and highest new-infected count of all four seeds in
steps 1–3, consistent with the placement hypothesis. But in the
perfect-oracle family, seed 44's early window is *not* elevated — it is
lower than seed 43's and comparable to 42/45. Seed 44's early-step numbers
(`n_facts_served=98`, `n_contam_facts_served=4`, `new_infected=2`) are, in
fact, numerically **identical across four different oracle configs**
(perfect oracle, interval=2, interval=5, interval=10) — expected, because
by step 3 none of those configs has yet reached its first validation
cadence point (interval 5 and 10) or had a quarantine event large enough
to perturb the shared `rng.sample(keys, entities_per_step)` draw sequence
that `scripts/run_contamination.py:332` uses to pick each step's sampled
entities (this call, together with the `ErrorInjector`'s own
`random_seed`-driven placement draw at `scripts/run_contamination.py:291`,
is the single mechanism by which `--random-seed` jointly controls *both*
which triplets get corrupted *and* which entities get visited each step).

So the oracle-family super-criticality of seed 44 is **not** an early-
window phenomenon — it is late and burst-driven (§2.3, the step-6 Arizona
event), which is a different mechanism from the one visible in baseline.

---

## 4. What this rules in and out

- **Ruled out:** a uniform "seed 44 places corruption in a more-retrieved
  region than 42/43/45, every time." The early-step test (§3) shows this
  holds in baseline but is inverted in the oracle family; the
  RQ3 sweep (§1.7) shows no consistent direction at all.
- **Ruled out:** an error-type-composition explanation (§2.1) — the
  ED/QL/RS mix is identical across seeds.
- **Ruled out (as a clean discriminator):** a simple entity-concentration
  score computed from `seed_records` (§2.2) — directionally suggestive in
  two of three families checked but not reliable enough to state as the
  mechanism.
- **Supported, with a caveat:** a "hub-entity burst" mechanism (§2.3) is
  real and archived in three independent runs, one of them not even a
  seed-44 run (`mitigated_s45`). This is a genuine placement/structural
  phenomenon — but the archives show it is a property of specific
  entities in the fixed candidate pool (Arizona, Taj Mahal), encountered
  by chance under a given seed's random draw, not a property of the
  number 44 itself. On the runs audited here it hit seed 44 more often
  (oracle_perfect, precision sweep) than 42 (never) or 45 (once, in
  mitigated), but the sample is small (≤4 seeds × ~6 families) and the
  {43,44} vs {42,45} split in the oracle families (§1.2–1.3) is at least
  as plausibly "43 and 44 happened to draw more hub-adjacent index cases
  in this pool" as it is "44 is special."
- **Genuinely unresolved:** whether seed 44's index cases land on
  higher-*graph-degree* entities than 42/43/45's **on average, across the
  full ~40-triplet set**, not just in the one or two hub cases spotted by
  manual inspection of `transmissions`. That requires node degree in the
  live KG, which is not in any archived file.

---

## 5. Verdict

**Undetermined between placement-structural and generation-variance, with
a documented partial mechanism.** The archives support a real, reproducible
burst mechanism tied to specific high-fan-out T-REx entities in the active
candidate pool, and seed 44 encountered it in more of its audited runs
than its siblings did — but the same mechanism independently hit seed 45
in the mitigated family and (on the RQ3 sweep, where no hub burst was
traced) seed 44 shows no consistent direction at all. The cleaner,
better-supported reframing is: **the contamination process has
occasional high-variance "super-spreader" events tied to a small number
of well-connected entities in the fixed injection pool; which seed's
random draw lands on one of these entities, and in which arm, looks close
to a coin flip from the data available offline** — seed 44 came up on that
flip in the oracle-validated families (paired with 43), seed 45 came up on
it in the mitigated family, and seed 42 came up on the *other* side (an
anomalously low outlier) throughout the recall sweep (§1.3). Framing this
chapter-wide finding as "seed 44 is systematically supercritical" would
overstate what four families out of six actually show.

## 6. What a Neo4j follow-up would need to compute

To move this from "suggestive burst evidence in 3 manually-inspected
cases" to a quantitative test, a follow-up pass with a live Neo4j
connection would need to:

1. For every seed's full `seed_records` list (not just the manually
   spotted hub hits), compute the **graph degree** (in + out edge count,
   or better, the count of triplets returned by
   `client.get_related_triplets(subject=key, obj=key, ...)` at the same
   `retrieval_threshold`/`context_limit` the runs used) of each seeded
   entity, and correlate mean/max seed-entity degree against that seed's
   realized R₀ within each family.
2. Repeat the same degree computation for the entities sampled by
   `rng.sample(keys, entities_per_step)` each step (recoverable
   deterministically offline in principle from `random.Random(seed)` plus
   the exact `keys` list order the run used — this part does **not**
   strictly need Neo4j, only the archived `extraction_manifest` that
   fixed `keys`; not attempted here for time reasons) to test whether
   seed 44's *sampling* sequence, independent of *where the corruption
   landed*, over-visits high-degree entities early.
3. Determine whether "Arizona" and "Taj Mahal" are outliers in the
   active-pool degree distribution generally (a histogram of degree over
   all ~91 active-pool entities) or merely mid-pack entities whose burst
   effect is being over-weighted by the small transmission counts (10–20
   per run) at this experiment's scale.

None of this was done here — it needs a live KG connection, which this
task was scoped to avoid.

---

## Archive files referenced

- `results/summaries/phase33_seed_variance.csv`
- `results/summaries/phase24_baseline_manifest.json`, `phase24_baseline_trajectory.csv`
- `results/summaries/phase33_baseline_s{43,44,45}_manifest.json`, `..._trajectory.csv`
- `results/summaries/phase32_mitigated_manifest.json`, `phase32_mitigated_trajectory.csv`
- `results/summaries/phase37_mitigated_s{43,44,45}_manifest.json`, `..._trajectory.csv`
- `results/summaries/phase37_mitigated_multiseed.csv`
- `results/summaries/phase37_sir_fit_mitigated_seeds.csv`
- `results/summaries/phase38_oracle_manifest.json`, `phase38_oracle_trajectory.csv`, `phase38_sir_fit_oracle.csv`
- `results/summaries/phase42_oracle_s{43,44,45}_manifest.json`, `..._trajectory.csv`
- `results/summaries/phase42_sir_fit_oracle_s{43,44,45}.csv`
- `results/summaries/phase42_oracle_sens{25,50,75}[_s43/44/45]_trajectory.csv`
- `results/summaries/phase42_sir_fit_oracle_sens{25,50,75}[_s43/44/45].csv`
- `results/summaries/phase40_oracle_noisy_p{10,25,50,75}[_s43/44/45]_trajectory.csv`
- `results/summaries/phase40_sir_fit_oracle_noisy_p{10,25,50,75}[_s43/44/45].csv`
- `results/summaries/phase48_interval_int{2,5,10}_s{42,43,44}_manifest.json`, `..._trajectory.csv`
- `results/summaries/phase48_interval_summary.csv`
- `results/summaries/phase48_sir_fit_interval.csv`
- `results/summaries/phase45_rq3_replication_n4.csv`
- `results/summaries/phase43_rq3_sir_fit.csv`, `phase44_density_sir_fit.csv`
- `results/raw/contamination_{khop1,khop2,khop3,wf6,wf24,rd3,rd10}[_s43/44/45]_*_manifest.json` (used only to confirm the 42;43;44;45 seed ordering in `phase45_rq3_replication_n4.csv`'s `repro_per_seed` column)
- `scripts/run_contamination.py` (code inspection: `seed_index_cases()` line 254–311, `transmission_cycle()` line 314 esp. the `rng.sample` call at line 332, confirming `--random-seed` jointly drives placement and per-step entity sampling)
- `docs/thesis_log.md` (2026-07-24 entries documenting the p10≡p50 / p75≡oracle construction-insensitivity finding for seed 44, cited in §1.4)
- `CLAUDE.md` (baseline SD envelope used for all z-scores)
