# Milestone 2 evaluation protocol and runbook

This is the frozen protocol for the Milestone 2 baseline. It is committed **before any dev-set model run**. Decisions and rationale live in [ROADMAP.md](ROADMAP.md). Experiment evidence lives in [EXPERIMENTS.md](EXPERIMENTS.md). This file says only what to do, and what must not change.

**Change control:** nothing below may change during the baseline. A change to the dev set, environment, budgets, sampling, submission or comparison rule creates a different benchmark and needs the project owner's approval.

## 1. Frozen dev set

Eight Rich tasks, in deterministic order (ascending `sha256(instance_id)` among Rich tasks whose gold patch changes exactly one file):

| # | Task |
|---|---|
| 1 | `rich_3894` |
| 2 | `rich_3278` |
| 3 | `rich_4076` |
| 4 | `rich_3905` |
| 5 | `rich_4079` |
| 6 | `rich_3470` |
| 7 | `rich_3130` |
| 8 | `rich_3061` |

Each passed the eligibility gate under the canonical environment (below): `resolved=false` with `--skip-agent-patch`, target tests reached, assertion or test failure (not collection, import or setup), `/workspace/rich` under test, gate within 300 s. Gate results are in [EXPERIMENTS.md](EXPERIMENTS.md).

**Skipped candidates** (walked in the same order, before the eighth eligible task was found):

| Task | Reason |
|---|---|
| `rich_3772` | Ineligible: the gate exceeds the frozen 300-second command timeout under the canonical environment (309.9 s, exit 124). |
| `rich_3472` | Ineligible: collection failure, `attr` (`attrs`) is not in the official dependency pool. |

**Held-out rule:** the held-out tasks begin at the next eligible Rich candidate in the same deterministic order after the frozen dev set (the first candidate not yet walked is `rich_3521`). No held-out task is frozen, downloaded or validated, and nobody reads them until needed.

## 2. Canonical environment

The canonical environment is the complete, unmodified official wheel pool, plus a harness wheel cache rebuilt from it.

| Item | Frozen value |
|---|---|
| Wheel pool | 124 files in `kaggle_data/wheels/`, 27,810,465 bytes |
| **Pool fingerprint** | `e02d3059f9c04716d0b6e46d90364a5370e45385b284ab8c1c56a9c0d63aba60` |
| Harness cache | `/tmp/swegemma_sp_cache_v8/sp_base.tar` (WSL), 37,683,200 bytes |
| **Cache fingerprint** | `c52a777befd2b12c719eb6363c547a82f3fe1c8e1f5821d72beea3a4e612bc47` |

**Rules**
- No wheel may be added, removed or replaced during the baseline.
- No dependency may be installed from the internet.
- No harness, `setup.py`, Dockerfile, sandbox image or `sample_submission` modification is allowed.
- Any wheel-pool change creates a different environment and invalidates comparability with this baseline.

**Pool fingerprint.** SHA-256 of the UTF-8 lines `filename size sha256` (one per wheel, sorted by filename, joined with newlines, no trailing newline):

```bash
cd kaggle_data/wheels
printf '%s' "$(for f in $(ls | LC_ALL=C sort); do echo "$f $(stat -c %s "$f") $(sha256sum "$f" | cut -d' ' -f1)"; done)" | sha256sum
```

**Cache fingerprint.** Run in WSL:

```bash
tar -tf /tmp/swegemma_sp_cache_v8/sp_base.tar | LC_ALL=C sort | sha256sum
```

## 3. Cache procedure

The harness builds the cache once and never checks it again (see EXPERIMENTS), so it must be rebuilt at fixed points.

- **Before each of these phases:** the dry run, r1, r2, r3, and the post-baseline environment control, delete only `/tmp/swegemma_sp_cache_v8/` (WSL: `rm -rf /tmp/swegemma_sp_cache_v8`).
- The normal harness run then rebuilds it from the frozen pool. Do nothing else to it.
- After the rebuild (once the first task's setup has run), record the cache fingerprint. **It must equal `c52a777b…bc47`. If it does not, STOP** and do not continue the batch.
- The cache may be reused within one batch (one phase).

## 4. Frozen baseline configuration

| Item | Frozen value |
|---|---|
| Agent | the unmodified official `kaggle_data/sample_submission` (graph and embedding tools included) |
| Model | Google Gemma 4 E4B-it Q4_0 GGUF (`gemma-4-E4B_q4_0-it.gguf`, 5,154,941,280 bytes, SHA-256 `676c35070db6dbe52f93e9c864ee0fba4eddea94b9c875d9cb10daff453fbaee`), a development surrogate, not the 31B competition model |
| Model server | llama.cpp `ghcr.io/ggml-org/llama.cpp:server-cuda12`, digest `sha256:1f4b9cf58982dd4d7cc497aea31b1a456ca9a3a1f94f527d317d3fdee0d60ab6`, container `gemma4-e4b-server`, context 32,768 |
| Model mapping | `/home/jesse/gemma4-dev/dev_models.yaml` (outside the repository), below |
| Sandbox | Docker image `swebench-sandbox:latest`, ID `sha256:76734ccbf1c4b7ef5bfbb52e16e6dddec462d376d2093db97f9188e796135818` |
| Harness | `swegemma` 0.2.7, `adk-submission` 0.2.11, `adk-eval-core` 0.1.0, `google-adk` 1.36.1, `google-genai` 2.11.0 (WSL venv `/home/jesse/venvs/gemma4-harness`) |
| Concurrency | 1 |

**Model server command** (start a fresh container, or `docker start gemma4-e4b-server` if it already exists):

```bash
docker run -d --name gemma4-e4b-server --gpus all -p 127.0.0.1:8080:8080 \
  -v /home/jesse/models/gemma-4-E4B-it-qat-q4_0-gguf:/models:ro \
  ghcr.io/ggml-org/llama.cpp@sha256:1f4b9cf58982dd4d7cc497aea31b1a456ca9a3a1f94f527d317d3fdee0d60ab6 \
  -m /models/gemma-4-E4B_q4_0-it.gguf --alias gemma-4-e4b-it -c 32768 -np 1 -ngl 99 \
  --fit off -fa on -ctk q8_0 -ctv q8_0 --jinja --no-webui --host 0.0.0.0 --port 8080 -lv 4
```

**`dev_models.yaml`** redirects the three names the submission uses to the local server:

```yaml
models:
  gemma-4-31b-it-qat-w4a16-ct: {path: openai/gemma-4-e4b-it, api_base: http://127.0.0.1:8080/v1}
  main_lora:                   {path: openai/gemma-4-e4b-it, api_base: http://127.0.0.1:8080/v1}
  tool_lora:                   {path: openai/gemma-4-e4b-it, api_base: http://127.0.0.1:8080/v1}
```

**Run budgets** (local development budgets, not the submission's Kaggle budgets in `eval_config.yaml`, which the CLI ignores):

- max tool calls: **30** (`--max-tool-calls 30`)
- max time: **20 minutes** (`--max-time-minutes 20`)
- command timeout: **300 seconds** (`--timeout-seconds 300`)
- `--max-turns` is **omitted**. Milestone 1 omitted it. The harness then applies no turn budget, and falls back internally to 500 LLM calls (VERIFIED from the installed `agent_runner.py`). Passing 500 explicitly would also add a "max loop iterations" line to the task prompt and so change behaviour, so the baseline keeps the omission.

**Sampling** (from `sample_submission/configs/sampling.yaml`, unmodified): temperature 0.2, top_p 0.95, `max_output_tokens` 16384, thinking budget 4096 with thoughts included. There is **no fixed seed**, and none is added. The model is stochastic, so identical outputs are not claimed. Repeats are used instead. Whether these settings reach the llama.cpp server is confirmed in the dry run.

## 5. Baseline runs

- **24 measured agent runs:** 8 tasks × 3 repeats (r1, r2, r3), one `swegemma eval` command per repeat over all 8 tasks, run sequentially at concurrency 1.
- **Execution order:** the harness filters `--task-ids` against `tasks.jsonl` and runs the tasks in `tasks.jsonl` order, not the order given on the command line. For the frozen set that order is `rich_4079`, `rich_4076`, `rich_3894`, `rich_3905`, `rich_3470`, `rich_3278`, `rich_3130`, `rich_3061` (VERIFIED from `evaluate.py` and `tasks.jsonl`). The ranking in section 1 is the selection order only.
- **One server per repeat**, with no restarts between tasks. Check the server logs for unplanned restarts. Keep a background VRAM/RAM log during each repeat.
- **Unique result directories, never overwritten:** `results/m2_baseline_r1/`, `results/m2_baseline_r2/`, `results/m2_baseline_r3/`.

Command for repeat N (WSL, from the repository root, after the pre-run checklist):

```bash
source /home/jesse/venvs/gemma4-harness/bin/activate
swegemma eval --tasks kaggle_data/tasks.jsonl --snapshots-dir kaggle_data/snapshots \
  --submission-dir kaggle_data/sample_submission --results-dir results/m2_baseline_rN \
  --image swebench-sandbox:latest --sandbox docker --models-yaml /home/jesse/gemma4-dev/dev_models.yaml \
  --task-ids rich_3894 rich_3278 rich_4076 rich_3905 rich_4079 rich_3470 rich_3130 rich_3061 \
  --max-tool-calls 30 --max-time-minutes 20 --timeout-seconds 300 \
  --concurrency 1 --display single --verbose
```

**Dry run.** After this file is committed, one procedure check runs from a fresh shell, with the cache cleared first (section 3). Its results directory is `results/m2_dryrun/`.

- **Dry-run task:** `rich_3894`
- **Status:** APPROVED
- **Purpose:** the dry run validates the frozen runbook, model-server path, harness invocation, environment fingerprints, artifact generation and end-to-end evaluation procedure before the 24 measured baseline runs. It also confirms that the sampling settings reach llama.cpp.
- **The dry-run result is NOT part of the 24-run baseline.** It is run once and never counted. (It shows one dev task's behaviour before the baseline. That trade-off was accepted.)
- **No tuning.** The dry run must not be used to tune or alter the prompts, agent configuration, sampling settings, model mapping, budgets, tool configuration, task set or comparison rule. A model-quality failure during the dry run is not a reason to change the baseline configuration. Only a verified infrastructure or procedure defect may justify stopping and correcting the run procedure, and any such correction must be documented before baseline r1.

## 6. Record per run

For each of the 24 runs, record in [EXPERIMENTS.md](EXPERIMENTS.md):

- task ID and repeat number
- `resolved`
- whether `submit_patch` was called, and whether the patch was empty
- tool calls used, LLM calls and tokens if available
- wall-clock time
- whether a budget was hit, whether an OOM occurred, whether a crash occurred
- the Phase 2 outcome: tests failed, tests errored, or patch not applied
- the failure category (below)
- whether `/workspace` code was under test
- the pool fingerprint and cache fingerprint for that repeat
- the environment pins (section 4)
- for resolved runs, whether the submission came within 10 counted tool calls (a compatibility indicator only)

**Failure category**, assigned in this order of precedence: infra error, then no `submit_patch`, then empty patch, then patch not applied, then Phase 2 tests failed or errored.

**Rerun rule.** A genuine infrastructure failure (OOM, container crash, server crash) may be rerun **once**, and both attempts are recorded. A model failure is **never** rerun, and none is rerun silently.

## 7. Reporting and comparison rule

**Baseline report:**
- each task as 0/3, 1/3, 2/3 or 3/3
- the number of stable-pass tasks (3/3), unstable tasks (1/3 or 2/3) and stable-fail tasks (0/3)
- total resolved runs out of 24

A single pooled percentage is never reported alone. No variance statistic is reported.

**Comparison rule for future changes** (frozen now, before any baseline model run, and not to be changed after seeing baseline results). A later change is measured on the same dev set, the same environment and this procedure, with 3 repeats. For each task:
- **gain:** baseline ≤1/3 resolved and the new version 3/3
- **loss:** baseline 3/3 resolved and the new version ≤1/3

Then:
- **improvement:** at least 2 gains and 0 losses
- **regression:** at least 1 loss and 0 gains
- **otherwise:** inconclusive. Moves into or out of 2/3 do not count.

The false-positive rate of this rule has not been measured.

## 8. Post-baseline environment control

After r3:
1. Clear the harness cache (section 3) and let it rebuild.
2. Confirm the cache fingerprint matches, and recompute the pool fingerprint.
3. Re-run the `--skip-agent-patch` eligibility gates for all 8 dev tasks (`--sandbox docker --image swebench-sandbox:latest --concurrency 1`, fresh result directories, no model).
4. Compare with the pre-baseline gate results: the same `resolved` value, the same failing test IDs, the same failure type, and `/workspace` code under test.

Any unexplained eligibility or fingerprint change **invalidates the baseline** until it is investigated.

## 9. Pre-run checklist

Before the dry run and before each of r1, r2 and r3:

- [ ] `git status` is clean, and HEAD is the commit containing this file
- [ ] `kaggle_data/wheels/` has 124 files, and the pool fingerprint matches
- [ ] the cache is cleared (`rm -rf /tmp/swegemma_sp_cache_v8`) and, after the first task's setup, rebuilt with a matching cache fingerprint
- [ ] the model server is healthy (container running, `GET http://127.0.0.1:8080/v1/models` answers, VRAM logging on)
- [ ] `/home/jesse/gemma4-dev/dev_models.yaml` has the mapping in section 4
- [ ] the sandbox is `swebench-sandbox:latest` with the frozen ID, with `--sandbox docker`
- [ ] the budgets are 30 tool calls, 20 minutes and 300 seconds, with `--max-turns` omitted
- [ ] `--concurrency 1`
- [ ] the result directory is new and unique
- [ ] no unapproved environment change (no installs, no wheel changes, no harness, Dockerfile or `setup.py` edits)

**Stop and report** if any check fails, if the cache fingerprint mismatches, if the pool fingerprint changes, if the repository changes, or if a spend above $0 would occur.

## 10. Known limitations

- The benchmark covers **Rich only**. It says little about other repositories.
- FastAPI is excluded: the official dependency materials are insufficient in this local setup (`typing_inspection` is not in the official wheel pool).
- Requests is excluded: the installed `requests` wheel shadows the `src/`-layout workspace code, so tests cannot measure agent edits.
- E4B is a development surrogate, not the required 31B competition model, and llama.cpp's tool-call parsing differs from the competition's vLLM parser.
- Eight tasks is statistically small and can only detect large changes.
- No gold-patch grader is used, so a task may fail for reasons the gate cannot detect.
- Some Rich tests may still be environment-sensitive (for example the markdown tests in `rich_3130` and `rich_4079`), and `rich_3061` includes one `AttributeError` for a method the fix adds.
- The results measure this frozen local development profile only. They are not a competition score, and official Kaggle scoring may not behave identically.
