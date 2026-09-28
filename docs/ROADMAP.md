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

## Milestone 2: Baseline Agent and Reproducible Evaluation (**PASS**, closed)

**Status: CLOSED — PASS (baseline measurement).** Evidence: [EXPERIMENTS.md](EXPERIMENTS.md) (per-run metrics, three-round synthesis, post-baseline environment control). Narrative: [BUILD_JOURNAL.md](BUILD_JOURNAL.md), entries 15–20.

**Formal result:** by the PASS/PARTIAL PASS/FAIL rule and acceptance criteria below (frozen before any model run), the measured baseline satisfies the numeric PASS conditions: 8 eligible Rich tasks, 2 of the 24 measured runs resolved (≥1 required), $0 spend, and no FAIL trigger. AC-1 through AC-10 are all now satisfied, including AC-9 (the build journal entry, entries 15–20) and AC-10 (the post-baseline environment control, which reproduced the pre-baseline eligibility state exactly). A poor pass rate is not a failure under this rule; the milestone measured the baseline and did not require a good score.

**Verified (see EXPERIMENTS.md for full evidence):**
- A reproducible, $0, fully local three-repeat baseline exists for the unmodified official `sample_submission` on the frozen 8-task Rich dev set: 2 of 24 measured runs resolved (r1: 1/8, r2: 0/8, r3: 1/8).
- Only `rich_3905` showed any run-to-run instability (2/3); the other 7 tasks were stable-fail (0/3) across all three repeats.
- The graph/search tools and the `agent_tool` sub-agent mechanism function correctly inside the real, unmodified agent (zero dependency or tool-level errors across all 24 measured runs), once the missing `cachetools`/`networkx` dependencies were repaired.
- No infrastructure failure occurred in any of the 24 measured runs or the post-baseline control; both frozen environment fingerprints matched exactly throughout.
- The post-baseline environment control reproduced the exact pre-baseline eligibility signature (same `resolved` values, same failing test IDs, same failure types) for all 8 tasks.

**Important limitation:** this is a measurement milestone on one repository's 8-task slice, using the local E4B surrogate model, not the 31B competition model. It does **not** prove general coding capability, competition score, or production readiness, and it does not establish that the graph tools' results are useful (only that they run without error).

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

This rule's false-positive rate has not been measured. **Milestone 3 note (recorded, rule unchanged):** no baseline task reached 3/3 in Milestone 2, so the comparison rule currently has no stable-pass task against which a "loss" could be observed, and "improvement" requires at least two tasks to move all the way from ≤1/3 to 3/3 — a substantial, all-or-nothing movement, not incremental progress. This is a known sensitivity property of the frozen rule, recorded factually; the rule itself is not altered because of it.

### Work items (closed)

- **WI-2.1: Selection and feasibility survey (read-only).** Complete (PARTIAL PASS).
- **WI-2.2: Download and eligibility probe (Stages 1 and 2).** Complete.
- **WI-2.2a: Record findings and revise the design.** Complete.
- **WI-2.2b: Complete the canonical wheel pool.** Complete.
- **WI-2.2c: Rich eligibility walk.** Complete.
- **WI-2.3: Protocol freeze and dry run.** Complete.
- **WI-2.4: Baseline runs** r1, r2 and r3, then the post-baseline environment control. Complete.
- **WI-2.5: Analysis.** Complete — formal three-round synthesis in [EXPERIMENTS.md](EXPERIMENTS.md).
- **WI-2.6: Close.** Complete — build journal entries 15–20 and this Current State update.

All work items WI-2.1 through WI-2.6 are complete. Milestone 2 is closed. See [EXPERIMENTS.md](EXPERIMENTS.md) for the full evidence trail from WI-2.1 through the formal three-round synthesis and closure.

### Acceptance criteria

- **AC-1:** `docs/EVALUATION.md`, with the selection rule and frozen dev IDs, is committed **before** the first dev-set model run. Git history shows the ordering. **SATISFIED.**
- **AC-2:** Every dev task has eligibility-gate evidence, including the `/workspace` path evidence. Every skipped candidate is listed with its pre-declared reason. **SATISFIED.**
- **AC-3:** Running `--skip-agent-patch` twice on one eligible task, under the canonical environment, gives identical `resolved` values and identical failing test IDs. **SATISFIED.**
- **AC-4:** The frozen command, the budget values, the dev model mapping and the environment pins are recorded. The pool and cache fingerprints are recorded and match across phases. The dry run was executed from the runbook alone in a fresh shell. **SATISFIED.**
- **AC-5:** All 24 measured runs completed under the infra rerun rule, with every attempt recorded. **SATISFIED** (no infra failure occurred; the rerun rule was never invoked).
- **AC-6:** [EXPERIMENTS.md](EXPERIMENTS.md) records the per-run metrics and the reporting described above. **SATISFIED.**
- **AC-7:** The comparison rule above is unchanged from its pre-run form. **SATISFIED.**
- **AC-8:** Spend is $0. The working tree is clean. No data, results or weights are committed. **SATISFIED.**
- **AC-9:** The build journal entry is written. **SATISFIED** (entries 15–20).
- **AC-10:** The post-baseline environment control matches the pre-baseline gate results. **SATISFIED.**

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

**Final result: PASS.** All acceptance criteria satisfied; 8 eligible Rich tasks; 2 of 24 measured runs resolved; $0 spend; no FAIL condition triggered.

### Known risks

- **Single-repository benchmark.** Results describe Rich tasks only. They say little about fastapi, requests or httpx tasks, and the official test set uses other repositories.
- **Why `/workspace` wins for Rich is not traced.** A `rich` directory exists in site-packages from the pool wheel, yet `/workspace` is first on `sys.path` (observed). The mechanism is unexplained, so the path evidence is required for every dev task.
- **Official scoring parity is unknown.** Kaggle's scoring may not behave the same way as the local wheel injection (cache, `sys.path`, shadowing).
- **The canonical environment depends on the full official wheel pool** and on a temporary cache in WSL `/tmp`. A WSL restart, or a pool change, silently changes the environment unless the fingerprints are checked.
- **Solvability is only partly checked.** The CLI has no gold-patch option (VERIFIED from `--help`), so a task may be unsolvable in this environment in ways the gate doesn't catch.
- **The 16-candidate walk may not yield 8.** Timeouts like `rich_3772` are possible. The outcome then follows the PARTIAL PASS or FAIL rules.
- **E4B may resolve almost nothing** (floor effect). **Observed:** the floor effect did not fully occur (2/24 resolved), but the rate is very low.
- **Eight tasks can only detect large changes.**
- **Surrogate, not target:**
  - E4B results say little about the 31B competition model.
  - llama.cpp's tool-call parsing is not the competition's vLLM parser.
  - The public tasks may appear in the model's training data, which could inflate the absolute pass rate.
- **Memory limits:** harder tasks may hit VRAM or WSL RAM limits. Such failures are classified as infrastructure failures. **Observed:** none occurred (see EXPERIMENTS.md), though r2 reached full swap saturation on one task without failing.

# Active Milestone

## Milestone 3: Baseline Failure Attribution

**Status: APPROVED, IN PROGRESS.** Established by WI-3.1. This is a documentation-and-analysis milestone: it studies the existing, frozen Milestone 2 evidence. It does not run the model, the agent, or any new benchmark attempt, and it does not change the agent, prompts, tools, sampling, budgets, or submission.

### Purpose

Milestone 2 measured a low, honest baseline (2 of 24 resolved). Before changing anything about the agent, determine **why** the other 22 runs failed, using only the evidence already collected, and distinguish — as far as that evidence permits — among:

- **model/capability limitations** (the model reasoned or edited incorrectly given a fair chance to solve the task)
- **agent-workflow friction** (the tool loop, edit mechanism, or budget shape got in the way of a model that might otherwise have succeeded)
- **local development-profile limitations/artifacts** (the E4B surrogate, the 32,768-token local context, or llama.cpp's tool-call parsing specifically, rather than something that would also affect the 31B competition profile)

What the project owner should be able to explain at the end: which of the 24 runs failed for which directly-evidenced reason, which reasons recur, and — if the evidence supports it — exactly one specific, evidence-backed hypothesis for what a later milestone should try changing, or an explicit statement that the evidence does not yet support choosing one.

### Evidence-language discipline (binding for all Milestone 3 work items)

Do not state that a number of baseline failures were definitively "caused by the context limit." The currently justified statement, established in Milestone 2 and carried forward as fact rather than re-derived, is:
- four failures terminated with an explicit `ContextWindowExceededError`;
- one additional `JSONDecodeError` (r1 `rich_3061`) has direct trace evidence of the terminating generation running to the 32,768-token context boundary before truncating;
- therefore **five** of the 24 failures have direct context-limit involvement in their terminal event.

Whether that context pressure arose primarily from model verbosity, workflow design (e.g., large tool outputs accumulating in context), the local 32K profile specifically, or some combination, is the open question this milestone exists to investigate — it is not assumed by this statement and must not be asserted without further evidence.

### Scope (WI-3.1 only)

WI-3.1 is documentation/codebook only:
1. Establish this milestone as active (this section).
2. Freeze the failure-attribution codebook below, before any run is labelled.
3. Define, but do not extract, the deterministic signals a later work item will pull from the frozen artifacts.
4. Document the Milestone 3 evaluation design (evidence base, what counts, what doesn't, relationship to the frozen Milestone 2 comparison rule).
5. Record the known comparison-rule sensitivity limitation (already added to the Milestone 2 section above).
6. Define the Milestone 3 acceptance criteria (not yet satisfied — established here for later work items to meet).
7. Define the governance for one later, narrowly-scoped read-only analysis script, without implementing it.

### Non-goals (WI-3.1 and, unless a later work item explicitly changes them, Milestone 3 generally)

- No running Gemma, the agent, or any new benchmark attempt.
- No labelling of the 24 runs yet (that is a later work item, against the codebook frozen here).
- No implementation of the analysis script (governance only, in this work item).
- No changes to prompts, tools, sampling, budgets, model configuration, or submission configuration.
- No implementation of context management, edit safeguards, or test-file protections — those would be Milestone 4 interventions, not this milestone's job.
- No downloads, no paid resources, no 31B model, no held-out tasks, no dev-set expansion.
- No changes to `docs/EVALUATION.md` or the frozen Milestone 2 comparison rule.
- No changes to any baseline result artifact under `results/`.
- No Milestone 4 work.
- No new planning documents beyond this roadmap section.

### Work items (WI-3.1 through WI-3.3 complete; WI-3.4 onward not yet started)

- **WI-3.1: Establish the milestone.** Complete. Froze the codebook, defined signals and evaluation design, defined acceptance criteria, defined script governance. Documentation only.
- **WI-3.2: Deterministic signal-extraction script.** Complete. `scripts/m3_extract_signals.py`, per the governance frozen in WI-3.1. See [EXPERIMENTS.md](EXPERIMENTS.md).
- **WI-3.3: Label all 24 counted runs.** Complete. Applied the frozen codebook to all 24 counted runs (22 failures labelled, 2 `rich_3905` runs recorded as resolved contrast cases); every label cites its supporting raw artifact. See [EXPERIMENTS.md](EXPERIMENTS.md). AC3-6 (owner spot-check) remains PENDING — a bounded 4-run sample was proposed, not yet reviewed.
- **WI-3.4 (future):** Project-owner spot-check of a bounded sample of labels.
- **WI-3.5 (future):** Competition-budget compatibility analysis — compare the frozen local dev budgets (30 tool calls / 20 min / 300 s) against the sample submission's own Kaggle budgets (`eval_config.yaml`: 10 calls / 1 min / 50 turns / 60 s, ignored by the local CLI) in light of the labelled failure modes, particularly the tool-call-budget and context-budget categories.
- **WI-3.6 (future):** Synthesize the labelled evidence; pre-register secondary process metrics for a later intervention experiment; select exactly one evidence-backed next-intervention hypothesis, or conclude explicitly that the evidence is insufficient to select one.
- **WI-3.7 (future):** Close — build journal entry, ROADMAP update.

### The failure-attribution codebook (frozen by WI-3.1)

**Candidate failure dimensions/categories**, each distinguished by specific artifact evidence:

1. **Localization failure** — evidence: the task's gold-target file(s) (from the task's known single-file gold patch) were never read and never edited in the run's trace, or edits were applied only to a different file. Treated as a *qualifier*, not a separate terminal mechanism (see precedence below).
2. **Diagnosis / incorrect fix** — evidence: the gold-target file was read and edited, a non-empty patch was submitted, and Phase 2 failed on an assertion mismatch (not on a context/budget/malformed-output termination).
3. **Edit mechanics failure** — evidence: one or more `FileEditError: old_string not found` events on the correct target file. Recorded as an observed contributing factor; only becomes the terminal label if it directly causes an empty-patch or budget-exhaustion termination (see precedence).
4. **Context budget / context pressure** — evidence: an explicit `ContextWindowExceededError` in the run's `error` field, with its reported token count.
5. **Tool-call budget exhaustion** — evidence: `tool_calls` reaches the frozen cap (30) and/or an explicit "tool call budget exhausted" error.
6. **Malformed/truncated output or tool-call formatting** — evidence: a `JSONDecodeError` or equivalent tool-call parsing failure in `error`. Sub-classified as **context-boundary-evidenced** (the run's own trace/server log shows the terminating generation reaching token counts at or near the 32,768-token limit before truncating) or **undetermined-cause** (no such direct evidence).
7. **Verification behavior** — evidence: Phase 2 exit code; whether the task's relevant/target test(s) were run before `submit_patch`; whether a test file itself was read or modified during the run (distinct from an implementation edit).
8. **Submission failure / empty patch** — evidence: `agent_patch_size: 0` and/or no `submit_patch` call recorded before the run ended.

**Multiple mechanisms per run.** Most runs will show more than one candidate signal (for example, several `FileEditError` events followed by a clean, non-empty submitted patch that still fails Phase 2). The codebook requires recording **every** observed mechanism present in a run's trace, but assigning exactly **one terminal failure mechanism** — the mechanism that directly explains why the run ended in its recorded state — using the fixed precedence order below, so labelling is deterministic and reproducible by anyone re-applying the codebook to the same artifacts.

**Precedence order for terminal-mechanism assignment** (first matching condition wins):
1. `resolved: true` — not a failure; used as a contrast case (see below), never labelled with a failure category.
2. Infrastructure failure — already established as not present in any of the 24 counted runs (Milestone 2 synthesis); would take precedence over all model-layer categories if it ever occurred.
3. Context budget / context pressure (category 4).
4. Malformed/truncated tool-call output (category 6), sub-classified context-boundary-evidenced vs. undetermined-cause.
5. Tool-call budget exhaustion (category 5).
6. Submission failure / empty patch (category 8) — applies when none of the above terminal mechanisms is present and the run nonetheless ended with an empty or absent patch.
7. Diagnosis / incorrect fix (category 2) — applies when a non-empty patch was submitted and Phase 2 failed, and none of the above applies.
8. Localization failure (category 1) is recorded as a qualifier on whichever terminal mechanism above applies (most often category 7), not as its own precedence rung.

Edit-mechanics failures (category 3) are recorded as an observed contributing factor on every run where they occur, regardless of the run's terminal label; they become the reason cited under the terminal label only when they are what directly produced an empty-patch or budget-exhaustion outcome.

**Explicit "undetermined" outcome.** If a run's terminal state cannot be matched to any category above from the artifacts alone, it must be labelled **undetermined** — never forced into a category for convenience or tidiness. Undetermined is an expected, valid outcome of applying this codebook honestly, not a labelling failure.

**Observed terminal mechanism vs. inferred root cause.** The codebook labels only the **directly evidenced, artifact-supported terminal mechanism** that ended a run (for example, "ContextWindowExceededError at 46,447 tokens"). It does not assert a **root cause** (for example, "the model is too verbose" or "the graph-tool results caused the overflow") unless the specific evidence directly supports that causal claim. Root-cause attribution — model behavior vs. agent-workflow design vs. tool-output size vs. the local 32K profile specifically — is the open question this milestone exists to investigate using the deterministic signals below, not something the codebook assumes.

**Using the two resolved runs as contrast cases.** `rich_3905` (resolved in r1 and r3) is never labelled with a failure category. Its traces serve as **positive contrast cases**: the same deterministic signals (tool-call count, LLM-call count, whether the gold-target file was read/edited, whether tests were run before submission, patch size, presence/absence of `FileEditError` events) are extracted from these two successful runs so the labelled failure runs can be compared against "what a successful run's process looks like" on this same task set, not against an assumption of what success should look like.

### Deterministic signals to extract (defined here; extraction is a later work item)

- `FileEditError` count and sequence (position among tool calls) per run.
- Prompt-token growth by step, where the trace or console/server log records it (llama.cpp server log `n_prompt_tokens`/`n_gen` lines, or harness-recorded token counts).
- Largest context/tool-output contributors, where the trace records tool-response sizes (for example, large `read_file` or `search_similar_code` payloads).
- Whether, and at what tool-call index, `submit_patch` occurred (or "never").
- Whether the task's gold-target file(s) were read and/or edited during the run.
- Whether the task's relevant/target test(s) were run before `submit_patch`.
- Evidence of test-file modification (already directly observed once, in r3 `rich_3061`; the extraction should check for this pattern across all 24 runs, not assume it is unique).
- Empty vs. non-empty submitted patch, and patch size.
- Context-limit events (`ContextWindowExceededError`, with token count) and malformed-output events (`JSONDecodeError`, with any available token-count context).

### Evaluation design

- **Evidence base:** exactly the 24 counted runs in `results/m2_baseline_v2_r1/`, `_r2/`, `_r3/`, frozen and unchanged.
- **Diagnostic-only evidence** (the invalid `results/m2_baseline_r1/` attempt, `results/m2_dryrun/`, `results/m2_dryrun_v2/`) may inform narrative interpretation but is never counted in any Milestone 3 statistic, matching its treatment in Milestone 2.
- **The Milestone 2 primary comparison rule** (above, and `docs/EVALUATION.md` §7) is unchanged and is not superseded by anything in Milestone 3.
- **Secondary process metrics** (for example, `FileEditError` rate, tool-call efficiency, or context-headroom-at-submission) may be pre-registered in a later Milestone 3 work item for use in a future intervention experiment, but must never retroactively replace the frozen primary gain/loss rule.
- **Traceability:** every interpretive label or claim in Milestone 3 must cite the specific raw artifact(s) (file, and field or line) it is drawn from.
- **`results/` remains unchanged** throughout Milestone 3; all Milestone 3 output is new evidence, never a modification of Milestone 2 evidence.

### Acceptance criteria (established now; **not yet satisfied** — for later Milestone 3 work items to meet)

- **AC3-1:** the failure-attribution codebook was frozen (committed) before any run was labelled. *(Satisfied by this entry once committed; labelling has not yet occurred.)*
- **AC3-2:** all 24 counted runs are analyzed and labelled, or explicitly marked undetermined.
- **AC3-3:** the deterministic signals are reproducibly extracted from the frozen artifacts (same inputs give the same outputs).
- **AC3-4:** raw evidence under `results/` remains unchanged throughout.
- **AC3-5:** every interpretive/attribution label cites its supporting raw-artifact evidence.
- **AC3-6:** the project owner spot-checks a bounded sample of labels for agreement.
- **AC3-7:** all context-involved failures (the 4 `ContextWindowExceededError` runs, plus the `JSONDecodeError` runs, sub-classified by context-boundary evidence) receive explicit treatment per the codebook.
- **AC3-8:** a competition-budget compatibility analysis is performed.
- **AC3-9:** secondary process metrics for a later intervention experiment are pre-registered before any intervention is attempted.
- **AC3-10:** the milestone concludes with exactly one evidence-backed next-intervention hypothesis, or an explicit, evidence-based conclusion that the evidence is insufficient to select one.
- **AC3-11:** $0 spend throughout.
- **AC3-12:** a build-journal closure entry is written when the milestone closes.

None of AC3-2 through AC3-12 was satisfied by WI-3.1; this work item establishes the criteria and the codebook only. **Status update (WI-3.3, recorded here for traceability; full evidence in EXPERIMENTS.md):** AC3-2 (all 24 runs labelled/undetermined), AC3-3 (reproducible deterministic extraction, from WI-3.2), AC3-4 (raw evidence under `results/` unchanged, re-verified), AC3-5 (every label cites raw-artifact evidence), and AC3-7 (all context-involved failures received explicit treatment) are now satisfied. AC3-6 (owner spot-check), AC3-8 (budget-compatibility analysis), AC3-9 (secondary-metric pre-registration), AC3-10 (intervention hypothesis or explicit insufficiency conclusion), and AC3-12 (build-journal closure entry) remain **not yet satisfied**. AC3-11 ($0 spend) holds throughout.

### Analysis script governance (defined now; **not implemented** in WI-3.1)

A later work item may implement exactly one narrowly-scoped, read-only, deterministic analysis script to extract the signals above reproducibly. Before that implementation, this governance applies:

- **Purpose:** deterministically extract the defined signals from the frozen `results/m2_baseline_v2_r1/`, `_r2/`, `_r3/` artifacts into a reproducible, citable form.
- **Allowed inputs:** read-only access to `results/m2_baseline_v2_r1/`, `_r2/`, `_r3/` (`task_results.jsonl`, `summary.json`, `patches/`, `test_outputs/`, `traces/`, `logs/`), the corresponding `*_console.log` files, and `kaggle_data/tasks.jsonl`/task definitions (for gold-target-file identification only). No other inputs, and no held-out task material.
- **Expected outputs:** a structured, deterministic summary (for example, one record per run) of the defined signals, written to a location **outside** `results/`, so it is never mistaken for baseline evidence. The exact output location and format are fixed by the implementing work item, not here.
- **Prohibitions:** the script must never write to, modify, rename, or delete anything under `results/`; it must not invoke the model, the harness, or Docker; it must not access held-out tasks; it must not become a general-purpose analysis framework, dashboard, package, or introduce a new dependency — the smallest single-purpose script that satisfies reproducibility is the ceiling.
- **Retention (open governance decision, deliberately left unresolved here):** whether the script remains in the repository after producing its one-time reproducible output, or is removed once that output is committed as evidence, is **not decided by WI-3.1**. The default preference, absent a project-owner decision, leans toward removing it after use (matching the "no wrapper script unless a later, verified need justifies one" precedent from Milestone 2's D3), but the implementing work item must record whichever choice is made and why.

# Future direction

After Milestone 3 identifies which failure mechanisms dominate the frozen baseline, a later milestone may design and measure exactly one evidence-backed intervention against the frozen Milestone 2 comparison rule, and/or check compatibility with the exact competition model. Those milestones will be defined only when they are reached, and only after Milestone 3's synthesis (WI-3.6) is reviewed and approved by the project owner.
