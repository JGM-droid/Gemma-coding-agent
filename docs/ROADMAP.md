# Roadmap

This is the project's only roadmap. There is exactly one active milestone at a time. See [AGENTS.md](../AGENTS.md) for working rules.

# Current State

## Milestone 1: Local Feasibility (**PASS**)

Evidence: [EXPERIMENTS.md](EXPERIMENTS.md). Narrative: [BUILD_JOURNAL.md](BUILD_JOURNAL.md).

**Verified:**
- The Windows 11 / WSL2 / Docker Desktop foundation works.
- The official `swegemma` CLI runs locally in a WSL virtual environment, without torch, CUDA or model-serving packages.
- The official Docker sandbox image (`swebench-sandbox:latest`) builds from the unmodified `Dockerfile.public` and runs.
- Docker-backed Phase 2 verification works. An unfixed task correctly grades as `resolved=false`.
- The official Google Gemma 4 E4B-it Q4_0 GGUF serves on the local RTX 3070 (8 GB) at a 32,768-token context via llama.cpp.
- Structured OpenAI-compatible tool calling works.
- Harness model-alias mapping works: `--models-yaml` redirects the competition alias to the local model without changing the submission.
- One real end-to-end `requests_6644` agent run completed:
  - The model read repository files, edited source code, ran a targeted test and called `submit_patch`.
  - Phase 2 verified the patch independently: `resolved=true`.
  - No out-of-memory errors.
- The normal development path remained $0.

**Important limitation:** this proves **feasibility only**. It does **not** prove:
- broad coding performance
- competition score
- equivalence with the 31B competition model
- that the graph tools are useful
- that multi-agent configurations are useful
- production readiness

## Accepted architecture

- The official `swegemma` harness is canonical.
- Docker is the preferred local sandbox. The subprocess sandbox is not used on this machine (see EXPERIMENTS).
- The declarative competition agent configuration stays canonical.
- **Dev profile:** local Gemma 4 E4B-it Q4_0 served by llama.cpp (Docker, GPU). The harness reaches it through a development `models.yaml` kept outside the repository.
- **Exact profile:** the competition-required `gemma-4-31b-it-qat-w4a16-ct`, when practical. It isn't runnable on the local 8 GB GPU.
- A single root `LlmAgent` is the baseline until experiments justify more complexity.
- No LoRA, RL, multi-agent designs or custom harness replacement unless evidence later justifies them.

# Active Milestone

## Milestone 2: Baseline Agent and Reproducible Evaluation

**Status: APPROVED, IN PROGRESS.** The design was revised at WI-2.2a after benchmark validation exposed environment problems (see [EXPERIMENTS.md](EXPERIMENTS.md), Milestone 2). WI-2.1 and WI-2.2 are complete. The next work item is WI-2.2b.

### Purpose

Turn the one-off Milestone 1 run into a reproducible baseline that can show whether a later change helps, hurts, or makes no measurable difference.

This is a measurement milestone. It does **not** try to improve the agent.

What the project owner should be able to explain at the end:
- how much the local E4B setup varies from run to run
- the baseline result on a small, fixed set of Rich tasks
- the procedure for re-running the baseline from the repository alone
- why the benchmark uses only Rich tasks (the environment findings)

### Scope

1. A dev set of 8 measured **Rich** tasks, chosen by a fixed, mechanical rule and validated by an eligibility gate.
2. A canonical environment (D8) that is fingerprinted and rebuilt at defined points.
3. A frozen baseline configuration: the unmodified `sample_submission`, the E4B dev profile, fixed budgets, and environment pins (the model, image and harness pins are already recorded in [EXPERIMENTS.md](EXPERIMENTS.md)).
4. One committed protocol and runbook document, `docs/EVALUATION.md`. It is created in WI-2.3 and committed **before any dev-set model run**.
5. A baseline of 3 repeats over the dev set (24 measured runs).
6. A post-baseline environment control (see the run procedure).
7. Results in [EXPERIMENTS.md](EXPERIMENTS.md), and a comparison rule for judging future changes.
8. A build journal entry when the milestone closes.

### Non-goals

- No changes to the agent, prompts, tools, sub-agents, sampling or submission. No budget changes after they are frozen.
- No 31B runs, no claim about competition score, no Kaggle submission.
- No LoRA, RL, fine-tuning, multi-agent designs, custom harness or grader. No gold-patch grader.
- No dashboards, databases, plotting, Python package or wrapper script.
- No changes to the sandbox image or `Dockerfile.public`. If one turns out to be needed, stop and ask.
- No hidden environment fixes: no dependency installs, no `setup.py` changes, no harness changes, no curated wheel subset.
- No fastapi or requests measurement (see D8).
- No held-out run, and no A/A noise run.
- No paid API or cloud GPU.

### Approved decisions

| # | Decision |
|---|---|
| D1 | **8 measured Rich dev tasks × 3 repeats = 24 measured runs.** Population: the 37 Rich tasks whose gold `patch` changes exactly one file. Order: ascending `sha256(instance_id)` (the ordering already in use). Eligibility probing walks at most the first 16 Rich candidates and stops once 8 are eligible. The gate is not loosened to reach 8. |
| D2 | **2 GB hard cap** on additional downloads, counted across the whole milestone. The official wheel pool is 124 files, about 27.8 MB (approximate: summed from rounded Kaggle listing values). Downloads so far total about 587 MB (measured). Current listing-based estimates place the worst-case Milestone 2 download total (walking all 16 Rich candidates and completing the wheel pool) at approximately 1.9 GB, which is expected to fit within the 2 GB cap. Because some source sizes are rounded, the cap remains a hard runtime boundary: stop before any download that would cause the measured cumulative total to exceed 2 GB. |
| D3 | **One committed runbook (`docs/EVALUATION.md`), no wrapper script** unless a later, verified need justifies one. `swegemma eval --task-ids` runs several tasks in one command (VERIFIED from `--help`). |
| D4 | **No held-out set is frozen, downloaded or validated now.** Only the rule is frozen: the held-out tasks are the next eligible Rich tasks in the same deterministic order, after the dev-set picks. |
| D5 | **The baseline is the unmodified official `sample_submission`**, graph and embedding tools included, so each dev task's graph and embedding files are downloaded. Sampling is `configs/sampling.yaml` (temperature 0.2, top_p 0.95, no seed). |
| D6 | **Development budgets, frozen before any model run:** `--max-tool-calls 30`, `--max-time-minutes 20`, `--timeout-seconds 300`. `--max-turns` is **omitted**, as in Milestone 1. The harness then falls back to a limit of 500 LLM calls internally (VERIFIED from the installed `agent_runner.py`, indirect for Milestone 1: no artifact records a runtime value). Passing 500 explicitly would also add a "max loop iterations" line to the task prompt, so it is not passed. These are local development budgets, **not** the sample submission's Kaggle budgets (`eval_config.yaml`: 10 calls, 1 min, 50 turns, 60 s), which the CLI ignores. |
| D7 | **Repositories and tasks that the canonical environment cannot support are excluded through the eligibility process**, not by naming exceptions. (`httpx`'s single task is also outside the single-file population.) |
| D8 | **Canonical environment.** See below. |

**D8: Canonical environment**

- The **complete official wheel pool** (all 124 files): no curated subset, no added packages, no removed packages.
- A **freshly rebuilt harness wheel cache** at the defined boundaries below.
- **Fingerprints recorded:**
  - the pool fingerprint: SHA-256 of the sorted list of lines `filename size sha256`, one line per wheel file
  - the cache fingerprint, recorded after every cache rebuild: `tar -tf sp_base.tar | sort | sha256sum`
- **Fingerprints must match across benchmark phases.** A mismatch invalidates the batch and requires investigation before continuing.
- **Consequences, both VERIFIED (see EXPERIMENTS):**
  - FastAPI is unsupported for Milestone 2: pydantic 2.13.4 needs `typing_inspection`, which is not in the official wheel listing.
  - Requests is unusable for Milestone 2: the installed `requests` wheel shadows the `src/`-layout workspace code, so tests can't measure agent edits.
- **Positive control:** `requests_6644` is no longer a measured control. It is replaced by the post-baseline environment control below.

### Evaluation strategy

**Task selection** (mechanical, and fixed before any further candidate is inspected):
- Population and order as in D1. Problem statements are not read while choosing.
- Already probed under the canonical rules (see EXPERIMENTS): `rich_3894` and `rich_3278` eligible, `rich_3772` ineligible (timeout). Their results are re-verified in WI-2.2c under the freshly rebuilt cache.
- Walk the order, download and gate each candidate in turn, and stop once 8 are eligible or after the 16th candidate.
- A task may be skipped only for one of these pre-declared, objective reasons:
  - it would break the D2 download cap
  - the canonical environment can't set it up
  - it fails the eligibility gate (below), including the 300-second rule
- Every skip is recorded with its reason.

**Eligibility gate.** Each dev task must, in Docker with `--skip-agent-patch`, `--sandbox docker`, `--image swebench-sandbox:latest` and `--concurrency 1`:
- give `resolved=false`
- reach its intended target tests
- fail those tests on assertions, not on collection, import, setup or environment errors
- show traceback or path evidence that the `/workspace` code is under test (for example a workspace-relative traceback path, or the import-path probe)
- complete within the frozen 300-second command timeout. The gate exceeding it is a fixed skip reason, decided before further candidates were tested.

**Cache rules.**
- Clear `/tmp/swegemma_sp_cache_v8/` before each of: the eligibility-gate session, the dry run, r1, r2, r3, and the post-baseline environment control.
- The cache may be reused within one batch.
- Record the pool and cache fingerprints (D8) at each of these points.

**Run procedure:**
- One llama.cpp server per batch, with no restarts between tasks. The server logs are checked for unplanned restarts.
- Each repeat (r1, r2, r3) is one `swegemma eval` command over the 8 dev tasks, with `--concurrency 1`.
- A background VRAM/RAM log runs during each batch.
- **Post-baseline environment control:** after r3, clear the cache, re-run the eligibility gates for the 8 dev tasks, and compare them with the pre-baseline gate results (same `resolved` values, same failing tests, same fingerprints).

**Infra rerun rule:**
- A genuine infrastructure failure (OOM, container crash, server crash) may be rerun **once**, and both attempts are recorded.
- A model failure is never rerun.

**Recorded per run:**
- `resolved`
- tool calls, turns, time and tokens
- whether `submit_patch` was called
- budget-hit, OOM or crash status
- whether the patch was empty
- the Phase 2 outcome type: tests failed, tests errored, or patch not applied
- for resolved runs, whether the submission came within 10 counted tool calls (a compatibility indicator only)
- a failure category, assigned in this order of precedence: infra error, then no `submit_patch`, then empty patch, then patch not applied, then Phase 2 tests failed or errored

**Reporting:**
- per-task pass counts (x/3)
- how many tasks are stable-pass (3/3), unstable (1/3 or 2/3) and stable-fail (0/3)
- total resolved runs out of 24
- the post-baseline environment control result

No variance statistic is reported: three repeats describe stability but don't estimate it precisely.

**Comparison rule for future changes** (frozen before any baseline model run). A later change is measured on the same dev set with the same procedure and 3 repeats. Then:
- **Gain:** a task moves from ≤1/3 to 3/3.
- **Loss:** a task moves from 3/3 to ≤1/3.
- **Improvement:** at least 2 gains and 0 losses.
- **Regression:** at least 1 loss and 0 gains.
- **Otherwise:** inconclusive. Moves into or out of 2/3 don't count.

This rule's false-positive rate has not been measured.

### Work items (in order)

- **WI-2.1: Selection and feasibility survey (read-only).** Complete (PARTIAL PASS). Recorded in [EXPERIMENTS.md](EXPERIMENTS.md).
- **WI-2.2: Download and eligibility probe (Stages 1 and 2).** Complete. It found the cache, fastapi and requests problems and led to this revision.
- **WI-2.2a: Record findings and revise the design.** This revision.
- **WI-2.2b: Complete the canonical wheel pool.**
  - Download the remaining official wheels (about 75 files, about 15 MB) with the owner's Chrome session.
  - Verify the count of 124 and each file's size against Kaggle's listing.
  - Record the pool fingerprint.
- **WI-2.2c: Rich eligibility walk.**
  - Clear the cache, rebuild it, and record the cache fingerprint.
  - Re-verify `rich_3894` and `rich_3278`.
  - Then walk the Rich order (`rich_4076` next), downloading and gating one candidate at a time, until 8 are eligible or 16 are walked. Stop for approval if a download would break the D2 cap.
  - Run `--skip-agent-patch` twice on one eligible task to confirm grading is deterministic under the canonical environment.
  - Record every result and skip in [EXPERIMENTS.md](EXPERIMENTS.md).
- **WI-2.3: Protocol freeze and dry run.**
  - Write `docs/EVALUATION.md`: the selection rule, frozen dev IDs and skips, the command line, budgets, the fingerprint and cache rules, the runbook, and the comparison and rerun rules. Commit it.
  - Then dry-run the runbook from a fresh shell and confirm the sampling settings reach llama.cpp. Which task the dry run uses is decided in WI-2.3 (see the risks).
- **WI-2.4: Baseline runs** r1, r2 and r3, then the post-baseline environment control.
- **WI-2.5: Analysis.** Record the results in [EXPERIMENTS.md](EXPERIMENTS.md).
- **WI-2.6: Close.** Write the build journal entry and update the ROADMAP.

### Acceptance criteria

- **AC-1:** `docs/EVALUATION.md`, with the selection rule and frozen dev IDs, is committed **before** the first dev-set model run. Git history shows the ordering.
- **AC-2:** Every dev task has eligibility-gate evidence, including the `/workspace` path evidence. Every skipped candidate is listed with its pre-declared reason.
- **AC-3:** Running `--skip-agent-patch` twice on one eligible task, under the canonical environment, gives identical `resolved` values and identical failing test IDs.
- **AC-4:** The frozen command, the budget values, the dev model mapping and the environment pins are recorded. The pool and cache fingerprints are recorded and match across phases. The dry run was executed from the runbook alone in a fresh shell.
- **AC-5:** All 24 measured runs completed under the infra rerun rule, with every attempt recorded.
- **AC-6:** [EXPERIMENTS.md](EXPERIMENTS.md) records the per-run metrics and the reporting described above.
- **AC-7:** The comparison rule above is unchanged from its pre-run form.
- **AC-8:** Spend is $0. The working tree is clean. No data, results or weights are committed.
- **AC-9:** The build journal entry is written.
- **AC-10:** The post-baseline environment control matches the pre-baseline gate results.

### PASS / PARTIAL PASS / FAIL

- **PASS:**
  - AC-1 to AC-10 are met
  - 8 eligible Rich tasks
  - at least 1 of the 24 measured model runs resolves
  - $0 spend
- **PARTIAL PASS:** any of these:
  - only 5 to 7 eligible Rich tasks
  - 0 of the 24 measured runs resolves. A baseline stuck at zero (a floor effect) can't detect regressions.
  - another condition the project owner explicitly approves
- **FAIL:** any of these:
  - fewer than 5 eligible Rich tasks
  - a curated or modified dependency pool is required
  - the harness, submission, sandbox image or Dockerfile needs to be modified
  - an environment fingerprint mismatch can't be resolved
  - grading is non-deterministic (AC-3), or the reproducibility procedure fails
  - spend above $0

A poor pass rate is not a failure. The milestone measures the baseline and does not require a good score.

### Known risks

- **Single-repository benchmark.** Results describe Rich tasks only. They say little about fastapi, requests or httpx tasks, and the official test set uses other repositories.
- **Why `/workspace` wins for Rich is not traced.** A `rich` directory exists in site-packages from the pool wheel, yet `/workspace` is first on `sys.path` (observed). The mechanism is unexplained, so the path evidence is required for every dev task.
- **Official scoring parity is unknown.** Kaggle's scoring may not behave the same way as the local wheel injection (cache, `sys.path`, shadowing).
- **The canonical environment depends on the full official wheel pool** and on a temporary cache in WSL `/tmp`. A WSL restart, or a pool change, silently changes the environment unless the fingerprints are checked.
- **Solvability is only partly checked.** The CLI has no gold-patch option (VERIFIED from `--help`), so a task may be unsolvable in this environment in ways the gate doesn't catch.
- **The 16-candidate walk may not yield 8.** Timeouts like `rich_3772` are possible. The outcome then follows the PARTIAL PASS or FAIL rules.
- **E4B may resolve almost nothing** (floor effect).
- **Eight tasks can only detect large changes.**
- **Dry-run task choice.** A dry run on a dev task would show one dev task's behaviour before the baseline. Its choice and handling are decided in WI-2.3.
- **Surrogate, not target:**
  - E4B results say little about the 31B competition model.
  - llama.cpp's tool-call parsing is not the competition's vLLM parser.
  - The public tasks may appear in the model's training data, which could inflate the absolute pass rate.
- **Memory limits:** harder tasks may hit VRAM or WSL RAM limits. Such failures are classified as infrastructure failures.

### Next bounded work item: WI-2.2b, complete the canonical wheel pool

WI-2.2b **must**:
- download only the remaining official wheel files that are not yet in `kaggle_data/wheels/`, using the owner's signed-in Chrome session
- verify the file count (124) and each file's size against Kaggle's listing
- compute and record the pool fingerprint

WI-2.2b **must not**:
- run gates or models
- change the cache or any repository file other than recording results
- download task material

# Future direction

After a reproducible baseline exists, later work may measure the agent across more tasks and check compatibility with the exact competition model. Those milestones will be defined only when they are reached.
