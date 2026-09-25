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

**Status: APPROVED, NOT STARTED.** Plan approved by the project owner after an architecture and evaluation audit. The first work item is WI-2.1.

### Purpose

Turn the one-off Milestone 1 run into a reproducible baseline that can show whether a later change helps, hurts, or makes no measurable difference.

This is a measurement milestone. It does **not** try to improve the agent.

What the project owner should be able to explain at the end:
- how much the local E4B setup varies from run to run
- the baseline result on a small, fixed task set
- the procedure for re-running the baseline from the repository alone

### Scope

1. A dev set of 8 measured tasks, chosen by a fixed, mechanical rule, plus `requests_6644` as a separate known-positive control.
2. An eligibility gate each dev task must pass before it is used.
3. A frozen baseline configuration: the unmodified `sample_submission`, the E4B dev profile, fixed budgets, and environment pins (the pins are already recorded in [EXPERIMENTS.md](EXPERIMENTS.md)).
4. One committed protocol and runbook document, `docs/EVALUATION.md`. It is created in WI-2.3 and committed **before any dev-set model run**.
5. A baseline of 3 repeats over the dev set and the control.
6. Results in [EXPERIMENTS.md](EXPERIMENTS.md), and a comparison rule for judging future changes.
7. A build journal entry when the milestone closes.

### Non-goals

- No changes to the agent, prompts, tools, sub-agents, sampling or submission. No budget changes after they are frozen.
- No 31B runs, no claim about competition score, no Kaggle submission.
- No LoRA, RL, fine-tuning, multi-agent designs, custom harness or grader. No gold-patch grader.
- No dashboards, databases, plotting, Python package or wrapper script.
- No changes to the sandbox image or `Dockerfile.public`. If one turns out to be needed, stop and ask.
- No held-out run, and no A/A noise run.
- No paid API or cloud GPU.

### Approved decisions

| # | Decision |
|---|---|
| D1 | **8 measured dev tasks × 3 repeats (24 runs), plus `requests_6644` × 3 as a control, reported separately (27 runs in total).** Selection rule below. |
| D2 | **2 GB hard cap** on additional downloads. Stop and ask per repo once WI-2.1 reports actual sizes. |
| D3 | **One committed runbook (`docs/EVALUATION.md`), no wrapper script** unless a later, verified need justifies one. `swegemma eval --task-ids` runs several tasks in one command (VERIFIED from `--help`). |
| D4 | **No held-out set is frozen, downloaded or validated now.** Only the rule is frozen: the held-out tasks are the next eligible tasks in each repo's deterministic order, after the dev-set picks. Nobody reads them until they are needed. |
| D5 | **The baseline is the unmodified official `sample_submission`**, graph and embedding tools included, so each dev task's graph and embedding files are downloaded. Sampling is `configs/sampling.yaml` (temperature 0.2, top_p 0.95, no seed). |
| D6 | **Development budgets, frozen before any model run:** `--max-tool-calls 30`, `--max-time-minutes 20`, `--timeout-seconds 300`. `--max-turns` is the value Milestone 1 actually used, taken from its evidence. That value is **UNPROVEN** until then. If it can't be verified, stop before the baseline runs rather than invent a value. These are local development budgets, **not** the sample submission's Kaggle budgets (`eval_config.yaml`: 10 calls, 1 min, 50 turns, 60 s), which the CLI ignores. |
| D7 | **Exclude the single `httpx` task.** |

### Evaluation strategy

**Task selection** (mechanical, and fixed before any task is inspected):
- **Population:** tasks whose gold `patch` changes exactly one file, excluding `httpx`.
- **Allocation:** 4 fastapi, 3 rich, 1 requests.
- **Order:** within each repo, candidates are ordered by `sha256(instance_id)`, and problem statements are not read while choosing. `requests_6644` is excluded from the measured set because it is the control.
- **Skips:** walk the order and take the first eligible tasks. A task may be skipped only for one of these pre-declared, objective reasons:
  - it would break the D2 download cap
  - the unmodified sandbox can't set it up
  - it fails the eligibility gate
- Every skip is recorded with its reason.

**Eligibility gate.** Each dev task must, in Docker:
- give `resolved=false` under `--skip-agent-patch`
- reach its intended target tests
- fail those tests on assertions, not on import, collection or environment errors

**Run procedure:**
- One llama.cpp server per batch, with no restarts between tasks. The server logs are checked for unplanned restarts.
- Each repeat (r1, r2, r3) is one `swegemma eval` command over the 8 dev tasks plus the control, with `--concurrency 1`.
- A background VRAM/RAM log runs during each batch.

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
- the control result, reported separately

No variance statistic is reported: three repeats describe stability but don't estimate it precisely.

**Comparison rule for future changes** (frozen before any baseline model run). A later change is measured on the same dev set with the same procedure and 3 repeats. Then:
- **Gain:** a task moves from ≤1/3 to 3/3.
- **Loss:** a task moves from 3/3 to ≤1/3.
- **Improvement:** at least 2 gains and 0 losses.
- **Regression:** at least 1 loss and 0 gains.
- **Otherwise:** inconclusive. Moves into or out of 2/3 don't count.

This rule's false-positive rate has not been measured.

### Work items (in order)

- **WI-2.1: Selection and feasibility survey (read-only).** Details below.
- **WI-2.2: Download and eligibility gate.**
  - Download only the approved tasks' files, size-verified, within D2.
  - Run the eligibility gate for each task.
  - Run `--skip-agent-patch` twice on one task to confirm grading is deterministic.
- **WI-2.3: Protocol freeze and dry run.**
  - Verify the Milestone 1 `--max-turns` value (D6).
  - Write `docs/EVALUATION.md`: the selection rule, frozen dev IDs and skips, the command line, budgets, the environment pins (referring to EXPERIMENTS), the runbook, and the comparison and rerun rules. Commit it.
  - Then dry-run the control (`requests_6644`) strictly from the runbook in a fresh shell, and confirm the sampling settings reach llama.cpp.
- **WI-2.4: Baseline runs** r1, r2 and r3.
- **WI-2.5: Analysis.** Record the results in [EXPERIMENTS.md](EXPERIMENTS.md).
- **WI-2.6: Close.** Write the build journal entry and update the ROADMAP.

### Acceptance criteria

- **AC-1:** `docs/EVALUATION.md`, with the selection rule and frozen dev IDs, is committed **before** the first dev-set model run. Git history shows the ordering.
- **AC-2:** Every dev task has eligibility-gate evidence. Every skipped candidate is listed with its pre-declared reason.
- **AC-3:** Running `--skip-agent-patch` twice on one task gives identical `resolved` values and identical failing test IDs.
- **AC-4:** The frozen command, all four budget values (with `--max-turns` verified), the dev model mapping and the environment pins are recorded. The control dry run was executed from the runbook alone in a fresh shell.
- **AC-5:** All 27 runs completed under the infra rerun rule, with every attempt recorded.
- **AC-6:** [EXPERIMENTS.md](EXPERIMENTS.md) records the per-run metrics and the reporting described above.
- **AC-7:** The comparison rule above is unchanged from its pre-run form.
- **AC-8:** Spend is $0. The working tree is clean. No data, results or weights are committed.
- **AC-9:** The build journal entry is written.

### PASS / PARTIAL PASS / FAIL

- **PASS:**
  - AC-1 to AC-9 are met
  - 8 eligible measured dev tasks
  - at least 1 of the 24 measured dev runs resolved
  - $0 spend
- **PARTIAL PASS:** the pipeline works, but any of these holds:
  - only 5 to 7 eligible dev tasks, or one repo can't be supported by the unmodified sandbox (documented)
  - 0 of 24 dev runs resolved. A baseline stuck at zero can't detect regressions.
  - an infrastructure failure that is still unresolved after its one rerun
- **FAIL:** any of these:
  - fewer than 5 eligible dev tasks
  - the baseline needed changes to the harness, submission, sandbox image or Dockerfile
  - grading is non-deterministic (AC-3)
  - the runbook can't reproduce the procedure
  - spend above $0

A poor pass rate is not a failure. The milestone measures the baseline and does not require a good score.

### Known risks

- **Setup for fastapi and rich is unverified.** Only the requests materials are local. WI-2.1 addresses this.
- **Solvability is only partly checked.** The CLI has no gold-patch option (VERIFIED from `--help`), so a task may be unsolvable in this environment in ways the gate doesn't catch.
- **E4B may resolve almost nothing** (floor effect). The single-file population lowers this risk but also narrows what the result represents.
- **Eight tasks can only detect large changes.**
- **Surrogate, not target:**
  - E4B results say little about the 31B competition model.
  - llama.cpp's tool-call parsing is not the competition's vLLM parser.
  - The public tasks may appear in the model's training data, which could inflate the absolute pass rate.
- **Memory limits:** harder tasks may hit VRAM or WSL RAM limits. Such failures are classified as infrastructure failures.

### First bounded work item: WI-2.1, selection and feasibility survey (read-only)

WI-2.1 **must**:
- use the local `tasks.jsonl`
- apply the single-file filter
- exclude `httpx` and `requests_6644` from the measured candidates
- compute the `sha256(instance_id)` order without reading problem statements
- list enough fastapi, rich and requests candidates to survive objective skips
- inspect Kaggle's file listings for snapshot, graph, embedding and wheel sizes
- determine whether the existing sandbox and setup path appears to support fastapi and rich
- propose the final 4/3/1 dev set in chat for approval

WI-2.1 **must not**:
- download files
- run models or evaluations
- change application code

# Future direction

After a reproducible baseline exists, later work may measure the agent across more tasks and check compatibility with the exact competition model. Those milestones will be defined only when they are reached.
