# Experiments

Technical record of experiments and their evidence. For the plain-English story, see [BUILD_JOURNAL.md](BUILD_JOURNAL.md).

**Artifact locations.** These are local only and never committed:
- `kaggle_data/`: official competition subset (Windows project folder, git-ignored)
- `results/`: run artifacts (Windows project folder, git-ignored)
- WSL: harness venv `/home/jesse/venvs/gemma4-harness`, model `/home/jesse/models/`, dev model mapping `/home/jesse/gemma4-dev/dev_models.yaml`, sandbox build context `/home/jesse/docker-build/swebench-sandbox/`

The helper scripts used to drive Milestone 1 were temporary and are not in the repository. The essential commands are recorded below.

---

## Milestone 1: Local Feasibility

### Experiment: Machine and environment inventory

**Goal:** determine whether this machine can support local development.

**Method:** inspect the hardware and software stack.

**Result:** PASS

**Evidence:**
- Windows 11 Home (10.0.26200).
- WSL2 Ubuntu 24.04.4 with system Python 3.12.3. `ensurepip`, pip and venv support are not installed.
- Docker Desktop with the WSL2 backend (cgroup v2).
- NVIDIA RTX 3070, 8 GB VRAM, driver 591.86 (CUDA 13.1). About 2.1 GB of VRAM is used by the Windows desktop at idle.
- Ryzen 7 5800X (8 cores / 16 threads) and about 16 GB RAM, as reported by the owner. WSL sees about 7.7 GB RAM plus 2 GB swap.
- C: had about 73 GB free at the start.

**Interpretation:** enough for the harness, Docker sandboxes and a small local model. Not enough for the 31B competition model, which needs about 16–18 GB of VRAM for weights alone (HARNESS_README).

**Limitations:** little headroom in VRAM (about 2.4 GB free with the model loaded) and in WSL memory.

---

### Experiment: Official competition and harness discovery

**Goal:** identify the minimum official materials for one local feasibility run.

**Method:** read the competition Overview and Data pages, the organizer "Getting Started" notebook (`ryanholbrook/getting-started-gemma-4-developer-agent`) and `HARNESS_README.md`. Download only the subset needed.

**Result:** PASS

**Evidence:**
- Dataset: 524 files, 22.42 GB in total; 129 public tasks across `fastapi`, `rich`, `requests` and `httpx`.
- Downloaded subset (about 45 MB, every file size-verified against Kaggle's listing), in `kaggle_data/`:
  - `HARNESS_README.md`, `tasks.jsonl`
  - `docker/` (4 files), `sandbox/setup.py`, `sample_submission/` (10 files)
  - `snapshots/requests_6644.tgz`, plus the matching graph `.json` and embedding `.npz`
  - `wheels/`: the 4 task wheels (urllib3, idna, certifi, charset_normalizer)
- Harness wheels come from the Kaggle dataset `metric/gemma-4-developer-agent-wheelhouse`: `swegemma-0.2.7`, `adk_submission-0.2.11`, `adk_eval_core-0.1.0`, `google_adk-1.36.1`, `google_genai-2.11.0`.
- Required submission model: `gemma-4-31b-it-qat-w4a16-ct`.
- The `swegemma` CLI does **not** read the submission's `eval_config.yaml`; CLI flags set the budgets. Only Kaggle's inference script reads it.
- Task chosen: `requests_6644` ("Trim excess leading path separators"). The patch is small, the Phase 2 test is self-contained (`tests/test_adapters.py`) and the snapshot is 36 MB.

**Interpretation:** the official harness, submission format and scoring path are fully inspectable locally.

**Limitations:** the other 128 tasks and the full sandbox wheel set were not downloaded.

---

### Experiment: Minimal harness CLI import test

**Goal:** can the `swegemma` control-plane CLI run without the GPU and model-serving stack?

**Method:**
- In a fresh WSL venv (pip bootstrapped from PyPI's official wheel, since system Python lacks `ensurepip`), install the 5 harness wheels with `--no-deps`.
- Then add only the packages that real imports demand, one at a time.
- Run `import swegemma, adk_submission, adk_eval_core`, `swegemma --help` and `swegemma eval --help`.

**Result:** PASS

**Evidence:**
- A normal dependency resolution would have pulled 175 packages, including torch 2.14, triton and the CUDA 13 `nvidia-*` libraries, because `swegemma` declares `torchvision` and `accelerate`.
- The incremental approach needed 37 lightweight packages. `google-cloud-storage` is required because ADK imports it at module level.
- All three commands succeeded without torch, transformers or CUDA.

**Interpretation:** the harness control plane is independent of the model-serving stack.

**Limitations:** `pip check` is intentionally not clean. Declared-but-unused dependencies are absent.

---

### Experiment: Subprocess sandbox attempt

**Goal:** run the task setup and Phase 2 verification with `--sandbox subprocess`, which doesn't need Docker.

**Method:** `swegemma eval --task-id requests_6644 --sandbox subprocess --skip-agent-patch`.

**Result:** FAIL

**Evidence:**
- The run exited before snapshot extraction.
- The harness creates a per-task venv with `venv.create(with_pip=True)`. Ubuntu's patched `venv` calls `sys.exit(1)` when `ensurepip` is missing (`/usr/lib/python3.12/venv/__init__.py` lines 365–378).
- `swegemma`'s fallback catches only `Exception`, not `SystemExit`.

**Interpretation:** the subprocess backend depends on the host Python. It also uses host Python 3.12, while the official sandbox uses Python 3.13.

**Limitations:** the fix would need `sudo apt install python3.12-venv`, which was declined, so this path was abandoned in favour of Docker.

---

### Experiment: Docker sandbox build

**Goal:** build and run the official sandbox image.

**Method:**
- Stage unmodified copies of `Dockerfile.public`, `imp.py`, `telnetlib.py` and `wheels/` in a temporary build context, with SHA-256 checked against the originals.
- `docker build -f Dockerfile.public -t swebench-sandbox:latest .`

**Result:** PASS

**Evidence:**
- Image 387 MB. Python 3.13.15, pytest 9.1.1, pytest-timeout 2.1.0, git 2.47.3, `/bin/bash`, `WORKDIR /workspace`.
- `--memory=4g --cpus=2` is enforced (cgroup `memory.max` 4294967296, `cpu.max` `200000 100000`).
- Docker disk use grew by about 0.9 GB.

**Interpretation:** the official sandbox runs locally with the harness's per-container limits.

**Limitations:** `nproc` inside a limited container still reports 16 cores.

---

### Experiment: Docker-backed Phase 2 baseline verification

**Goal:** prove snapshot, setup, `test_patch`, pytest and grading work, with no agent and no model.

**Method:** `swegemma eval --task-id requests_6644 --sandbox docker --image swebench-sandbox:latest --skip-agent-patch --concurrency 1`

**Result:** PASS

**Evidence:**
- Exit 0 in 7.5 s.
- `tests/test_adapters.py::test_request_url_trims_leading_path_separators` **failed** as expected: `assert '/v:h' == '//v:h'`.
- `test_exit_code 1`, `resolved=false`.
- Artifacts are in `results/m1_requests_6644_skip_agent_docker/`.

**Interpretation:** the clean verification path works, and the task's fail-to-pass baseline holds.

**Limitations:** no agent or model involved.

---

### Experiment: Local Gemma E4B llama.cpp smoke test (Stage A)

**Goal:** serve a real Gemma 4 model locally at the harness's 32K context and confirm structured tool calling.

**Method:**
- Model: `google/gemma-4-E4B-it-qat-q4_0-gguf` at commit `4b4a2c1d…`, file `gemma-4-E4B_q4_0-it.gguf`, 5,154,941,280 bytes, SHA-256 `676c3507…fbaee` (verified). Apache-2.0, not gated.
- Server: `ghcr.io/ggml-org/llama.cpp:server-cuda12@sha256:1f4b9cf5…0ab6` (build b11176, CUDA 12.8).
- Flags: `-c 32768 -np 1 -ngl 99 --fit off -fa on -ctk q8_0 -ctv q8_0 --jinja --alias gemma-4-e4b-it`, published on `127.0.0.1:8080`.
- Container: `gemma4-e4b-server`.

**Result:** PASS

**Evidence:**
- 43/43 layers offloaded to the GPU. `n_ctx 32768`, KV cache q8_0 (293 MiB), flash attention on.
- VRAM went from 2,136 to 5,549 MiB used. The container uses about 1.9 GiB RAM.
- `GET /v1/models` succeeded. A plain chat returned exactly `MODEL_OK`.
- A tool request returned `tool_calls: read_file {"filepath":"src/example.py","start_line":1,"end_line":20}`.
- The request model name `main_lora` was accepted: the server serves its single model under any name.

**Interpretation:** the dev profile model fits and speaks structured tool calls.

**Limitations:** llama.cpp's template-based tool parsing is not the competition's vLLM `gemma4` parser. The image is 6.99 GB.

---

### Experiment: First Stage B run (dependency-blocked)

**Goal:** a first real agent run with the local model.

**Method:**
- Dev mapping `/home/jesse/gemma4-dev/dev_models.yaml`, following the schema in `swegemma/models/registry.py`:
  ```yaml
  models:
    gemma-4-31b-it-qat-w4a16-ct: {path: openai/gemma-4-e4b-it, api_base: http://127.0.0.1:8080/v1}
    main_lora:                   {path: openai/gemma-4-e4b-it, api_base: http://127.0.0.1:8080/v1}
    tool_lora:                   {path: openai/gemma-4-e4b-it, api_base: http://127.0.0.1:8080/v1}
  ```
  (The actual file uses block YAML with comments; the content is equivalent.)
- Before the run, 21 more lightweight runtime packages were added for real LiteLLM HTTP calls (openai, tiktoken, tokenizers, aiohttp and its dependencies, jinja2 and others). No torch, transformers or accelerate.

**Result:** PARTIAL PASS

**Evidence:**
- Phase 1 started: the submission compiled, the sandbox was created, the snapshot extracted and the prompts were built.
- The run failed before the first LLM call: `ModuleNotFoundError: No module named 'authlib'`, via `google/adk/auth/oauth2_credential_util.py:21`, reached through `LlmAgent` → `SingleFlow` → `auth_preprocessor`.
- 0 LLM calls. Artifacts are in `results/m1_requests_6644_agent_e4b_docker/`.

**Interpretation:** a packaging gap, not an architecture problem. The preflight had tested the model object directly, not the full agent pipeline.

**Limitations:** no model interaction happened.

---

### Experiment: Final real-model end-to-end run on `requests_6644`

**Goal:** prove a real local model can drive the official harness end to end.

**Method:**
- Add `authlib` 1.8.0 and `joserfc` 1.7.5. Stage B added 23 packages in total.
- Preflight one ADK `Runner` → `LlmAgent` → `SingleFlow` turn.
- Run once:
  ```bash
  swegemma eval --tasks kaggle_data/tasks.jsonl --snapshots-dir kaggle_data/snapshots \
    --submission-dir kaggle_data/sample_submission --results-dir results/m1_requests_6644_agent_e4b_docker_rerun \
    --image swebench-sandbox:latest --sandbox docker --models-yaml /home/jesse/gemma4-dev/dev_models.yaml \
    --task-id requests_6644 --max-tool-calls 30 --max-time-minutes 20 --concurrency 1 --display single --verbose
  ```
- Official `sample_submission` unmodified. Effective budgets: 30 tool calls, 20 minutes, 300 s per command.

**Result:** PASS

**Evidence:**
- **Task and model:** task `requests_6644`. Model: official Google Gemma 4 E4B-it Q4_0 GGUF, via the llama.cpp OpenAI-compatible server, context 32,768.
- **Calls:** 8 LLM calls (69,785 prompt tokens, 60,181 of them cached; 2,783 completion tokens). 7 executed tool calls, all `status: ok`. The harness budget counter showed 6/30.
- **Tool sequence:** `read_file` ×4 (`sessions.py`, `utils.py`, `structures.py`, `models.py`) → `edit_file` (`src/requests/models.py`) → `run_command` (`pytest tests/test_structures.py`: 20 passed) → `submit_patch` (429 bytes, 1 file).
- **Patch:** in `RequestEncodingMixin.path_url`, a path beginning with `/` is collapsed to a single leading `/`.
- **Phase 2:** `tests/test_adapters.py` → **1 passed**, `test_exit_code 0`, **`resolved=true`**.
- **Time and memory:** task wall-clock about 63.7 s (agent time 46.8 s). No out-of-memory errors. Peak VRAM 5,611 MiB used of 8,192. Peak WSL RAM 3,491 MiB used, swap about 1.3 GB.
- **Artifacts:** `results/m1_requests_6644_agent_e4b_docker_rerun/`, containing `summary.json`, `task_results.jsonl`, `patches/requests_6644.patch`, `test_outputs/requests_6644.log`, `traces/trace_requests_6644.json` and `logs/requests_6644.log`. Also in `results/`: console, server and memory logs named `m1_requests_6644_agent_e4b_rerun_*`.

**Interpretation:** local real-model feasibility is proven. The model called tools, read and edited the repository, tested, and submitted a patch that the independent clean verification accepted.

**Limitations:**
- One easy task, one run, the smaller E4B surrogate. Performance, variance and 31B behaviour are unproven.
- The agent's own test (`test_structures.py`) wasn't the task's target test.
- The graph tools and the `code_analyzer` sub-agent weren't used.

---

## Milestone 2: Baseline Agent and Reproducible Evaluation (in progress)

Findings from benchmark validation (WI-2.1 and WI-2.2). No model has been run in Milestone 2 so far. These findings changed the Milestone 2 design (see [ROADMAP.md](ROADMAP.md)).

**Artifact locations** (local only, never committed):
- `kaggle_data/`: the Milestone 1 files plus the Milestone 2 downloads below.
- `results/m2_gate_*`: gate runs under the stale Milestone 1 wheel cache. `results/m2_gate2_*`: gate runs under the rebuilt cache.
- WSL: the harness wheel cache at `/tmp/swegemma_sp_cache_v8/`.

The helper scripts (a gate wrapper and an import-path probe) were temporary and are not in the repository. The gate command was the Milestone 1 `swegemma eval` command with `--skip-agent-patch --sandbox docker --image swebench-sandbox:latest --concurrency 1 --task-id <id>` and no `--models-yaml`. The default 300 s command timeout applied. The import-path probe replayed the harness's own Phase 2 setup functions in a throwaway container, applied `test_patch`, and ran a one-line test printing `<package>.__file__` under the harness's own pytest command.

---

### Experiment: Selection and feasibility survey (WI-2.1)

**Goal:** choose the dev tasks by a mechanical rule and check whether the official materials could support them.

**Method:** local `tasks.jsonl` metadata only (repo, `instance_id`, `base_commit`, files touched by the gold `patch`). Problem statements were not used for selection. Sizes came from the Kaggle Data page file listing (read-only).

**Result:** PARTIAL PASS (selection and sizes settled; environment support was unknown at this point).

**Evidence:**
- Population: gold patch changes exactly one file, excluding `httpx` (its one task changes 7 files) and `requests_6644`. That leaves 90 tasks: fastapi 43, rich 37, requests 10.
- Order within each repo: ascending `sha256(instance_id)`.
- The initial design was 4 fastapi, 3 rich and 1 requests.
- The first 16 rich candidates in hash order: rich_3894, rich_3772, rich_3278, rich_4076, rich_3905, rich_3472, rich_4079, rich_3470, rich_3130, rich_3061, rich_3521, rich_3782, rich_3296, rich_3043, rich_3953, rich_3469.
- Snapshots: fastapi 211 to 335 MB each, rich about 91 to 97 MB, requests about 36 to 38 MB. Graphs and embeddings are 1 to 6 MB each.
- The official wheel folder holds 124 files, about 27.8 MB in total (approximate: the sum of per-file sizes shown in the listing, which are rounded). It is one shared pool, not per task.
- Installed harness code (`container_setup.py`, `_deduplicate_wheels`) keeps only the newest Python 3.13-compatible wheel per package. Older versions are never injected. VERIFIED from code.

**Interpretation:** the wheel pool is small, and listing-based estimates place the worst-case Milestone 2 download total at approximately 1.9 GB, which is expected to fit within the 2 GB cap. Because some source sizes are rounded, the cap remains a hard runtime boundary: stop before any download that would cause the measured cumulative total to exceed 2 GB. Whether the sandbox could run fastapi and rich tasks was unknown at this point.

**Limitations:** the wheel total is a sum of rounded listing values, not exact bytes.

---

### Experiment: Stage 1 eligibility gates under the stale 4-wheel cache

**Goal:** check that rich and requests candidates fail their target tests by assertion in the official Docker sandbox.

**Method:** downloaded (via Claude in Chrome, with the owner's signed-in Kaggle session) the snapshots, graphs and embeddings for `rich_3894`, `rich_3772`, `rich_3278` and `requests_7427`, plus 45 wheel files (the 37 the harness selection needs plus 8 older versions fetched by mistake). The 4 wheels from Milestone 1 were already present. The gates ran before the stale cache was discovered (next experiments).

**Result:** PARTIAL PASS (three of four eligible under this cache).

**Evidence:**
- Downloads: all sizes matched Kaggle's listing, and the four `.tgz` files passed `gzip -t`. New task files 336.39 MB and 45 new wheels 12.13 MB, so 348.52 MB.
- `rich_3894` (95,693,148 B, SHA-256 prefix `0f5d343dab89018c`): `resolved=false`, 1 failed (`test_qualname_in_slots`, an assertion caused by a `TypeError` in `rich/text.py`).
- `rich_3278` (92,497,686 B, `bda96e09e9e02fa3`): `resolved=false`, 16 assertion failures in `test_strip_private_escape_sequences[…]`.
- `requests_7427` (37,176,965 B, `d8f2092187969feb`): `resolved=false`, 1 failed and 215 passed (`test_should_bypass_proxies_no_proxy_domain_boundary[http://prelocalhost/-False]`, `assert True == False`).
- Determinism: `requests_7427` was run twice. Both runs gave the same result and identical logs apart from timing.
- Import-path probe (workspace code under test): `rich.__file__ = /workspace/rich/__init__.py` for both rich tasks, and `requests.__file__ = /workspace/src/requests/__init__.py`.

**Interpretation:** under this environment the three tasks were valid fail-to-pass tasks. The conclusion for `requests_7427` changed after the cache was rebuilt (below).

**Limitations:** only prefixes of the SHA-256 values are recorded here. The full values were printed in the work-item report.

---

### Experiment: `rich_3772` timeout

**Goal:** gate `rich_3772`.

**Result:** INELIGIBLE. VERIFIED.

**Evidence:**
- Test exit code 124 (the command timed out) after 308.8 s. The rerun gave 308.1 s and the same outcome, so it is reproducible.
- A diagnostic replay showed every earlier test in `tests/test_traceback.py` passing. The hang is in `test_recursive_exception`, the test added by the task's `test_patch`.
- No assertion failure was produced.
- The project owner then fixed an additional skip reason: the gate may not exceed the frozen 300-second command timeout. This rule was stated after `rich_3772` was observed. It applies to it because the task already failed the original gate requirement (fail on an assertion).

**Interpretation:** the unfixed bug probably causes an unterminated loop, which would explain the hang. That cause is UNPROVEN.

---

### Experiment: Harness wheel cache discovery

**Goal:** explain why fastapi failed to import `starlette` although `starlette-1.6.0` was in the wheel pool.

**Method:** read the installed harness code (`swegemma/harness/container_setup.py`) and inspected the WSL temp directory.

**Result:** finding. VERIFIED.

**Evidence:**
- `_build_unpacked_wheels_tar` writes the unpacked wheels to `/tmp/swegemma_sp_cache_v8/sp_base.tar` (inside WSL) and returns it if it already exists. The cache is keyed only by file name. Adding, removing or changing wheels does not invalidate it.
- The cache found on 2026-09-25 was created at 14:51 during Milestone 1. It was 1,802,240 bytes and held only `certifi`, `charset_normalizer`, `idna` and `urllib3`. So Milestone 1's `requests_6644` PASS and the Stage 1 gates above ran under a 4-wheel dependency environment, regardless of the wheels present in `kaggle_data/wheels/`.
- After the owner approved deleting only that directory, the next run rebuilt it: 37,683,200 bytes, holding the pool's newest wheels (starlette, pydantic, pydantic_core, annotated_types, anyio, httpx, httpcore, fastapi, requests, rich, flask, jinja2, typer, pygments, markdown_it and others).
- Nothing else was modified: no repository file, harness source, image, Dockerfile, `sample_submission` or wheel.

**Interpretation:** the dependency environment silently depends on a temporary directory that outlives runs. Results are only comparable if the cache is rebuilt at defined points and fingerprinted (Milestone 2 decision D8).

**Limitations:** the cache lives in `/tmp` in WSL. A WSL restart could delete it and change results without warning. That has not been tested.

---

### Experiment: FastAPI probe (`fastapi_11355`)

**Goal:** find out whether fastapi tasks can run in the unmodified official environment.

**Method:** downloaded `fastapi_11355` (snapshot 229,097,851 B, SHA-256 prefix `221c813ac48ec994`; graph 4,393,596 B; embedding 4,877,106 B; 238.4 MB in total; cumulative Milestone 2 download 586.9 MB). Ran the gate under the stale cache and again after rebuilding it.

**Result:** INELIGIBLE. VERIFIED.

**Evidence:**
- Stale cache: `resolved=false`, exit 2, collection error `ModuleNotFoundError: No module named 'starlette'`. The traceback shows the workspace `fastapi/__init__.py`, so workspace code is under test.
- Rebuilt cache: starlette imports. The next failure is at pydantic: `fastapi/types.py:5 from pydantic import BaseModel` → `pydantic/errors.py:9 from typing_inspection.introspection import Qualifier` → `ModuleNotFoundError: No module named 'typing_inspection'`. Exit 2, 10.4 s.
- `pydantic-2.13.4` declares `typing-inspection>=0.4.2` as a required dependency (read from the wheel's `METADATA`). No `typing_inspection` wheel exists in the official 124-file listing. VERIFIED.
- `h11` (required by `httpcore`, so by the `httpx` client Starlette's `TestClient` uses) and `annotated-doc` (required by the pool's own fastapi wheel) are also absent from the listing. Whether they would fail in practice is UNPROVEN, because the run stops earlier.

**Interpretation:** every fastapi task imports pydantic, so fastapi cannot run in the official environment unless the environment changes (an extra package from outside the official materials). That is not permitted in Milestone 2.

**Limitations:** only one fastapi task was probed. The other fastapi candidates were not downloaded.

---

### Experiment: Requests shadowing under the rebuilt cache

**Goal:** re-verify `requests_7427` under the rebuilt cache.

**Result:** INELIGIBLE. VERIFIED.

**Evidence:**
- Rebuilt cache, no patch: `resolved=true`, exit 0, 216 passed and 13 skipped. The same result twice, with identical logs (so deterministic).
- The probe reports `requests.__file__ = /usr/local/lib/python3.13/site-packages/requests/__init__.py`. That is the pool's `requests-2.34.2` wheel, which already contains the fix. The workspace code is at `/workspace/src/requests`.
- `sys.path[:4]` starts with `/workspace`. Because requests uses a `src/` layout, `/workspace` does not contain a `requests` package.

**Interpretation:** under this environment, tests exercise the installed wheel. An agent edit to `/workspace/src/requests` would not be tested. Requests tasks therefore cannot measure agent edits here. The Milestone 1 control `requests_6644` (also `src/` layout) would probably behave the same way under the rebuilt cache, but it has not been re-run.

**Limitations:** the ordering of `sys.path` entries was observed but not traced to its source. Only one requests task was tested.

---

### Experiment: Rich under the rebuilt cache

**Goal:** re-verify the rich gates under the rebuilt cache.

**Result:** `rich_3894` and `rich_3278` are ELIGIBLE. VERIFIED.

**Evidence:**
- `rich_3894`: `resolved=false`, exit 1, same assertion failure as before.
- `rich_3278`: `resolved=false`, exit 1, same 16 assertion failures.
- The probe shows `rich.__file__ = /workspace/rich/__init__.py` for both, although the rebuilt cache now contains a `rich` directory in site-packages (from the pool's `rich-15.0.0` wheel). `sys.path[0]` is `/workspace`, and rich uses a flat layout, so `/workspace/rich` is found first.
- `rich_3772` remains ineligible.

**Limitations:** why `/workspace` is first on `sys.path` was not traced (possibly pytest's handling of the root `conftest.py`). That is UNPROVEN.

---

### Milestone 2 validation summary

**VERIFIED**
- The official wheel pool has 124 files.
- The harness wheel cache is keyed by name only and was stale from Milestone 1.
- `rich_3894` and `rich_3278` are eligible under both the stale and the rebuilt cache, with workspace code under test.
- `rich_3772` is ineligible (reproducible timeout at the 300 s command limit).
- `fastapi_11355` cannot import pydantic because `typing_inspection` is not in the official wheel listing.
- `requests_7427` resolves with no patch under the rebuilt cache because the installed wheel shadows the workspace.
- Determinism: `requests_7427` gave identical results twice under both caches.
- Determinism of an eligible Rich task under the canonical environment: `rich_3894` gave identical results in three gate runs (status changed from UNPROVEN, see the WI-2.2c record below).

**PARTIAL**
- FastAPI as a whole repository: one task was probed. The missing package affects every task that imports pydantic, but the other fastapi tasks were not run.
- The requests conclusion rests on one task and one probe.
- The wheel-pool size (about 27.8 MB) is a sum of rounded listing values.

**UNPROVEN**
- Whether `h11` or `annotated-doc` would also fail for fastapi.
- What makes the `rich_3772` test hang.
- Why `/workspace` is first on `sys.path`.
- Whether the Milestone 1 control `requests_6644` would shadow under the rebuilt cache.
- Whether official Kaggle scoring uses the same wheel-injection behaviour.
- Whether a WSL restart clears the cache.

---

### Experiment: Milestone 2 dry run (`rich_3894`)

**Goal:** validate the frozen runbook, model-server path, harness invocation, environment fingerprints and artifact generation with one real agent run, before the 24 measured baseline runs. This is a procedure and infrastructure check only. **It is not one of the 24 measured baseline runs**, and its model result must not be used to tune anything (see [EVALUATION.md](EVALUATION.md)).

**Result:** procedure **PASS**. Model result **NOT RESOLVED**.

**Method:**
- Preconditions: HEAD `27ceeb5`, clean tree, 124 wheels, pool fingerprint checked.
- Cleared only `/tmp/swegemma_sp_cache_v8/`; the harness rebuilt it during the run.
- Started the existing `gemma4-e4b-server` container (`docker start`, not recreated).
- Ran exactly one task, with no other dev task:
  ```bash
  source /home/jesse/venvs/gemma4-harness/bin/activate
  swegemma eval --tasks kaggle_data/tasks.jsonl --snapshots-dir kaggle_data/snapshots \
    --submission-dir kaggle_data/sample_submission --results-dir results/m2_dryrun \
    --image swebench-sandbox:latest --sandbox docker --models-yaml /home/jesse/gemma4-dev/dev_models.yaml \
    --task-ids rich_3894 \
    --max-tool-calls 30 --max-time-minutes 20 --timeout-seconds 300 \
    --concurrency 1 --display single --verbose
  ```
  It exited with code 0. A background logger sampled VRAM and WSL memory every 3 s.

**Evidence:**
- **Environment:** 124 wheels; pool fingerprint `e02d3059f9c04716d0b6e46d90364a5370e45385b284ab8c1c56a9c0d63aba60`; rebuilt cache `sp_base.tar` 37,683,200 bytes, fingerprint `c52a777befd2b12c719eb6363c547a82f3fe1c8e1f5821d72beea3a4e612bc47`. Both fingerprints were unchanged after the run.
- **Server:** the container started healthy, `/v1/models` returned `gemma-4-e4b-it`, the three names in `dev_models.yaml` resolve to it, and the server log showed no restart, out-of-memory or error.
- **Run:** 7 LLM calls (prompt tokens 68,319 of which 52,940 cached; completion tokens 3,016). The harness counted 5 of 30 tool calls; 6 executed, all status ok: `run_command` (find), `read_file` (`rich/_inspect.py`), `edit_file` (`rich/_inspect.py`), `run_command` (find), `run_command` (`pytest tests/test_inspect.py`), `submit_patch`. `submit_patch` was called with a patch of 815 bytes in 1 file.
- **Time and resources:** wall time 72.95 s, agent time about 51 s. No timeout, out-of-memory or crash. Peak VRAM 5,876 MiB of 8,192. Peak WSL RAM 4,039 MiB used and peak swap 1,192 MiB (33 samples).
- **Phase 2:** `resolved=false`, exit 1, `7 failed, 35 passed, 4 skipped`. The target test `test_qualname_in_slots` no longer fails. The patch introduced seven regressions in `tests/test_inspect.py` (`test_render`, `test_inspect_module_with_class`, and five `test_can_handle_special_characters_in_docstrings[…]` variants). The patch replaced `name or getattr(obj, "__qualname__", name)` with a chain that prefers `__qualname__`, then `__name__`, then `name`, so the explicit `name` lost priority. Failure category: Phase 2 tests failed.
- **Workspace code under test:** the agent's edit to `/workspace/rich/_inspect.py` changed which tests fail (one fixed, seven newly failing), so the workspace code was what ran.
- **Sampling, as observed in the llama.cpp server log (`-lv 4`), 7 requests:**
  - `temp = 0.200` and `top_p = 0.950` on all 7.
  - `top_k = 64` and `min_p = 0.05` also applied. These are server defaults, not settings the submission controls.
  - `common_reasoning: activated, budget=2147483647 tokens` (effectively unlimited reasoning budget).
  - No per-request output limit is logged. The longest reply was 2,144 tokens.
  - The trace has `thinking` events on the 7 model steps.
- **Artifacts** (local, ignored): `results/m2_dryrun/` (`summary.json`, `task_results.jsonl`, `patches/rich_3894.patch`, `test_outputs/rich_3894.log`, `traces/trace_rich_3894.json`, `logs/rich_3894.log`), plus `results/m2_dryrun_console.log` and `results/m2_dryrun_resources.log`.

**Interpretation:** the end-to-end procedure works in the frozen environment. The model did not solve the task: it fixed the target failure but broke seven other tests. That is a model-quality result and is not a reason to change the baseline.

**Limitations:** one run of one task. It says nothing about the baseline pass rate.

**VERIFIED**
- The workflow ran end to end (server, harness, tools, patch capture, Phase 2, artifacts) with `resolved=false`.
- Pool and cache fingerprints were unchanged, and the repository stayed clean.
- Temperature 0.2 and top_p 0.95 reached the llama.cpp server.
- Workspace code was under test.
- No timeout, out-of-memory or crash occurred.

**PARTIAL**
- Whether "thoughts included" is honoured: the trace holds thinking events, but their cause (submission setting or server default) is not shown.
- Resource peaks come from 3-second samples of one run.

**UNPROVEN**
- `max_output_tokens` 16384 reaching the server (not observable per request).
- Whether the harness sends the thinking budget of 4096 and llama.cpp ignores it. The server logged an effectively unlimited reasoning budget (2147483647), so the 4096 budget was not visibly enforced.
- How consistent this run's speed and tool use are across other tasks.

---

### Experiment: WI-2.2c, Rich eligibility walk under the canonical environment

**Goal:** establish the eligible Rich dev-task set under the canonical environment, with no model.

**Method:**
- Canonical wheel pool: 124 official wheels, 27,810,465 bytes, pool fingerprint `e02d3059f9c04716d0b6e46d90364a5370e45385b284ab8c1c56a9c0d63aba60`.
- Cleared only `/tmp/swegemma_sp_cache_v8/` and let the first gate rebuild it. Canonical eligibility-session cache: `sp_base.tar`, 37,683,200 bytes, member-list fingerprint `c52a777befd2b12c719eb6363c547a82f3fe1c8e1f5821d72beea3a4e612bc47`.
- Walked the deterministic Rich order (see the WI-2.1 record) from rank 1. For each candidate not yet local, downloaded only its snapshot, graph and embedding (Chrome, signed-in Kaggle session), checked filename, size against Kaggle's listing and archive integrity, then ran the gate: `--skip-agent-patch --sandbox docker --image swebench-sandbox:latest --concurrency 1` at the 300 s command timeout, in a fresh results directory (`results/m2_canon_*`), plus the import-path probe.
- Stopped once 8 tasks were eligible.

**Result:** PASS. 8 eligible tasks after walking 10 candidates.

**Evidence:**

| Rank | Task | Gate | Verdict |
|---|---|---|---|
| 1 | `rich_3894` | exit 1; 1 failed, `test_inspect.py::test_qualname_in_slots` | eligible |
| 2 | `rich_3772` | 309.9 s, exit 124, `resolved=false`, no assertion failure | **ineligible** |
| 3 | `rich_3278` | exit 1; 16 failed, `test_ansi.py::test_strip_private_escape_sequences[…]` | eligible |
| 4 | `rich_4076` | exit 1; 4 failed in `test_ansi.py` | eligible |
| 5 | `rich_3905` | exit 1; 1 failed, `test_progress.py::test_no_output_if_progress_is_disabled_non_interactive` | eligible |
| 6 | `rich_3472` | exit 2; collection error `ModuleNotFoundError: No module named 'attr'` (`tests/test_pretty.py:9`) | **ineligible** |
| 7 | `rich_4079` | exit 1; 1 failed, `test_markdown.py::test_inline_code_in_table_cells` | eligible |
| 8 | `rich_3470` | exit 1; 1 failed, `test_console.py::test_capture_and_record` | eligible |
| 9 | `rich_3130` | exit 1; 5 failed in `test_markdown.py` | eligible |
| 10 | `rich_3061` | exit 1; 12 failed in `test_panel.py` and `test_text.py`, 11 assertions and 1 `AttributeError` for a method the fix adds (`Text.extend_style`) | eligible |

- **Frozen eligible Rich tasks, in order:** `rich_3894`, `rich_3278`, `rich_4076`, `rich_3905`, `rich_4079`, `rich_3470`, `rich_3130`, `rich_3061`.
- **Recorded ineligible candidates:**
  - `rich_3772`: the gate exceeds the frozen 300-second timeout under the canonical environment. The canonical re-check took 309.9 s with exit 124 and `resolved=false` (earlier runs under the stale cache also timed out).
  - `rich_3472`: collection failure, because `attr` (`attrs`) is not in the official dependency pool.
- **Workspace code:** every eligible task's import-path probe reported `rich.__file__ = /workspace/rich/__init__.py`.
- **Environment:** the pool fingerprint and the cache fingerprint were unchanged throughout, checked again at the end. `git status` stayed clean.
- **Determinism:** `rich_3894` was gated three times under the same canonical cache. All three runs gave `resolved=false`, exit 1, the same failing test ID (`tests/test_inspect.py::test_qualname_in_slots`), the same failure types, and workspace code imported. The pytest logs are identical apart from timing.
- **Downloads:**
  - WI-2.2c incremental: 690,756,307 bytes (21 files, seven candidates: `rich_4076`, `rich_3905`, `rich_3472`, `rich_4079`, `rich_3470`, `rich_3130`, `rich_3061`).
  - Exact Milestone 2 cumulative after WI-2.2c: 1,292,763,887 bytes, recomputed from the local files. It counts files downloaded in Milestone 2 only, and excludes the three `requests_6644` files and the four wheels from Milestone 1.
  - Remaining headroom under the 2,000,000,000-byte working cap: 707,236,113 bytes.

**Anomalies:**
- `rich_3905`: one gate was run before its files had downloaded and returned "Snapshot file not found". That result was discarded, not treated as a gate result, and its results directory was deleted. The gate was re-run after a verified download.
- `rich_3130`: a temporary browser interruption stopped one download batch. The file accounting was reconciled and the cumulative total was recomputed from the files on disk.

**Interpretation:** eight Rich tasks fail in the intended way under the canonical environment with the workspace code under test, and the gate is deterministic for the task tested.

**Limitations:**
- No gold-patch grader exists, so a task may fail for reasons the gate cannot detect. The `test_markdown.py` tasks (`rich_3130`, `rich_4079`) may be environment-sensitive.
- No agent or baseline result is recorded here.

**VERIFIED**
- 8 eligible Rich tasks, and the two ineligible candidates with their reasons.
- Workspace Rich code under test for every eligible task.
- Pool and cache fingerprints unchanged.
- Determinism of `rich_3894` across three gate runs.
- The download accounting above.

**PARTIAL**
- Determinism was tested on one task, not all eight.

**UNPROVEN**
- Whether the `test_markdown.py` failures would also occur with the gold fix (no gold-patch grader).
- What makes `rich_3772` hang.

---

### Experiment: Milestone 2 baseline r1, attempt 1 (INVALID, diagnostic only)

**Goal:** the first measured baseline repeat (r1) over the 8 frozen Rich tasks, per [EVALUATION.md](EVALUATION.md).

**Result:** **INVALID as baseline data.** The raw score of 1/8 resolved must not enter any x/3 tally, and is not a baseline result. An Opus 5.5 Medium audit concluded: invalidate and repeat r1.

**Why it is invalid:** the pinned `swegemma` 0.2.7 host installation is missing `cachetools`. The audit reports that the package metadata declares `cachetools>=5.0.0` as an unconditional requirement (recorded from the audit; not re-checked in the work item that wrote this record). During r1, graph and search tools failed with `SimilaritySearchError: No module named 'cachetools'` in 7 of the 8 tasks. The eighth, `rich_3894`, did not call them. The frozen plan describes the unmodified `sample_submission` with graph and embedding tools included, so r1 did not measure the intended frozen agent. This is classified as an incomplete host harness installation. The dry run did not reveal it because it used no graph tool.

**Method:** the frozen r1 command from [EVALUATION.md](EVALUATION.md) (8 tasks, budgets 30 tool calls, 20 minutes and 300 s, `--max-turns` omitted, concurrency 1), results directory `results/m2_baseline_r1/`, run detached. The cache was cleared first and the existing `gemma4-e4b-server` container (already running since the dry run) was used.

**Evidence:**
- **Repository:** HEAD `66288d6`, clean working tree, before and after.
- **Environment:** the wheel pool fingerprint was unchanged (`e02d3059f9c04716d0b6e46d90364a5370e45385b284ab8c1c56a9c0d63aba60`), and the cache fingerprint was unchanged (`c52a777befd2b12c719eb6363c547a82f3fe1c8e1f5821d72beea3a4e612bc47`). The server had 0 restarts and no out-of-memory flag.
- **Raw completed result (diagnostic only):** 1/8 resolved, `rich_3905`. The harness executed the tasks in `tasks.jsonl` order.

| Task | Outcome | Notes |
|---|---|---|
| `rich_4079` | NOT RESOLVED | `ContextWindowExceededError`: request 34,722 tokens against the 32,768-token context, no Phase 2 verification. **Classification: context-budget failure** (not infrastructure). |
| `rich_4076` | NOT RESOLVED | Phase 2 exit 2, patch 51,170 bytes |
| `rich_3894` | NOT RESOLVED | Phase 2 exit 1 |
| `rich_3905` | RESOLVED | Phase 2 exit 0. Diagnostic only, not baseline credit. |
| `rich_3470` | NOT RESOLVED | all 30 tool calls used, Phase 2 exit 1 |
| `rich_3278` | NOT RESOLVED | `submit_patch` called twice, final recorded patch empty, Phase 2 exit 1 |
| `rich_3130` | NOT RESOLVED | Phase 2 exit 1 |
| `rich_3061` | NOT RESOLVED | only 2 LLM calls and 2 tool calls before a host stall, final wall time 4,861.89 s, "Agent exceeded session timeout (20.0 min)". **Classification: infrastructure failure** (WSL and Docker became unresponsive under severe memory pressure). |

- **Batch totals:** 105 counted tool calls, 128 LLM calls, 1,512,078 prompt tokens, 46,185 completion tokens, 5,797.6 s summed task time.
- **Resources:** peak VRAM 5,777 MiB. WSL RAM reached about 7,830 MiB of about 7.9 GiB, and swap reached its 2,048 MiB limit. The resource logger lost WSL access during the stall, so its record is incomplete.
- **Observed memory consumers after recovery** (not proven to be the cause): the Gemma model server about 4.4 GiB, an unrelated `openclaw` Node process about 1.3 GB, and unrelated `repotriage` containers about 0.2 GB.
- **First-launch anomaly:** an earlier launch of r1 was stopped seconds after it started, because of the interactive execution time limit. One LLM call occurred and no task completed. The partial results directory and console log were deleted, and the cache was cleared before the later full launch. That deletion cannot be undone, and it was contrary to the evidence-preservation rule adopted afterwards (see [EVALUATION.md](EVALUATION.md), Amendment 1). The deleted artifacts cannot be recovered. Future aborted attempts are preserved. This does not by itself invalidate the later run.
- **Artifacts of the completed invalid attempt** (local, ignored): `results/m2_baseline_r1/`, `results/m2_baseline_r1_console.log` and `results/m2_baseline_r1_resources.log`. **They must remain untouched and must never be overwritten.** SHA-256 recorded from the Windows-visible files:
  - `results/m2_baseline_r1/summary.json`: `f05158a9504a73e9f63c0f2cd3d896b9c8a172d7a81c5f5c4a28bdf8242b7f79`
  - `results/m2_baseline_r1/task_results.jsonl`: `0b7d7abd4d4bd0af357f37ef68a5f61a5e360a2d03edc95516d75a72f83639ce`

**Interpretation:** the run is useful only as diagnostic evidence about the environment (missing dependency, memory pressure, context budget). It says nothing about the frozen agent's baseline pass rate. Nothing was tuned in response.

**Limitations:** `cachetools` is not installed as of this record, and no corrective action has been taken. Other dependency gaps may exist. Which unrelated processes caused the memory pressure is not proven, and the WSL and sandbox memory limits are unchanged.

**VERIFIED**
- r1 attempt 1 ran to completion with 8 task results, of which 1 was resolved.
- The wheel pool and cache fingerprints were unchanged, and the working tree was clean.
- `SimilaritySearchError: No module named 'cachetools'` occurred on graph and search tools in 7 of 8 tasks.
- `rich_4079` exceeded the frozen context (34,722 against 32,768 tokens) and had no Phase 2 verification.
- `rich_3061` ran for 4,861.89 s (about 81 minutes) after only 2 LLM calls, while WSL and Docker were unresponsive.

**PARTIAL**
- The resource log covers only part of the batch.

**UNPROVEN**
- That `cachetools>=5.0.0` is an unconditional dependency of `swegemma` 0.2.7 (reported by the audit, not re-checked here).
- Whether other declared dependencies are missing (a diagnostic `pip check` is pending).
- What consumed the WSL memory.

---

### Experiment: Milestone 2 corrective host environment (OpenClaw and graph-tool dependencies)

**Goal:** remove the two causes found after the invalid r1 attempt 1: an unrelated auto-starting workload consuming WSL memory, and two missing declared dependencies of the pinned harness. No measurement was run.

**Result:** PASS. No model, graph-tool smoke test, dry run, baseline run or eligibility gate was run in this work item, and the model server was not started.

**Method and evidence**

*Diagnosis after the approved `wsl --shutdown` recovery (read-only):*
- After a fresh WSL start, `openclaw-gateway.service` (a systemd **user** service) started within about a second of boot and used 0.5 to 1.0 GB. It is enabled (`WantedBy=default.target`, enable link in `~/.config/systemd/user/default.target.wants/`), has `Restart=always`, and `loginctl` shows `Linger=yes`. That is VERIFIED automatic startup. No cron entry, PM2 directory or shell-startup reference was found.
- `swegemma` 0.2.7 declares `cachetools>=5.0.0` and `networkx>=3.0` as unconditional requirements, and `swegemma/graph/graph_utils.py` imports both. Neither was installed, so the graph and search tools failed (`No module named 'cachetools'`; `networkx` would have failed next).

*OpenClaw, changed to manual start only:*
- Before: `active`, `enabled`, main PID 265, about 631 MiB RSS (systemd reported 792 MB).
- Commands run:
  ```bash
  systemctl --user stop openclaw-gateway.service
  systemctl --user disable openclaw-gateway.service
  ```
- After: `inactive`, `disabled`, no OpenClaw Node process remains, and the enablement link (and its now-empty `default.target.wants/` directory) was removed.
- **Unchanged on purpose:** the service file `/home/jesse/.config/systemd/user/openclaw-gateway.service` still exists, with the same `ExecStart` and `Restart=always`. `Linger=yes` is unchanged. OpenClaw was not uninstalled or reconfigured, and was not started again.
- Manual use, when wanted:
  ```bash
  systemctl --user start openclaw-gateway.service   # start manually
  systemctl --user stop openclaw-gateway.service    # stop manually
  ```
- **WSL RAM (`free -m`):** before stopping, 2,133 MiB used and 5,776 MiB available. After, 1,537 MiB used and 6,372 MiB available. Swap 0 used throughout.

*Host dependency repair, scoped to the two verified gaps only:*
- Environment: `/home/jesse/venvs/gemma4-harness`, Python 3.12.3, pip 26.2.1, run from `/tmp`.
- Resolver dry run (`pip install --dry-run "cachetools>=5.0.0" "networkx>=3.0"`): would install only `cachetools-7.2.0` and `networkx-3.7`, with no upgrade, downgrade or removal and no extra package.
- Install command: `pip install "cachetools>=5.0.0" "networkx>=3.0"`. Result: `cachetools 7.2.0` and `networkx 3.7` installed. **No additional dependency was installed.** The `pip freeze` difference is exactly those two lines.
- Pinned harness packages unchanged: `swegemma` 0.2.7, `adk-submission` 0.2.11, `adk-eval-core` 0.1.0, `google-adk` 1.36.1, `google-genai` 2.11.0.
- Import verification: `cachetools` 7.2.0 and `networkx` 3.7 import, and `swegemma.graph.graph_utils`, `swegemma.graph.retrieval_utils`, `swegemma.graph.embedding_utils` and `swegemma.tools.graph` all import.
- **Sorted `pip freeze` SHA-256 (evidence only, not the dependency specification):**
  - old (65 lines): `220dd9067a7d540ddb6bd923c5e90b380c7be1712a1dcbd7dd78a07ba18c8bc4`
  - new (67 lines): `230b3b5fcf75222666413c3dac9c013a8111f0bbba3ebf4e613645f6af571c40`

*Remaining `python -m pip check` findings (diagnostic only, not repaired, exit 1, 45 lines):* no `cachetools` or `networkx` complaint remains. What remains, classified:
- **Declared but deliberately excluded** (Milestone 1 omitted the torch stack on purpose): `swegemma` requires `accelerate`, `safetensors`, `torchvision`, `transformers`.
- **Declared but unexercised** (the agent ran end to end without them): `google-adk` requires `aiosqlite`, `google-api-python-client`, `google-cloud-aiplatform`, `google-cloud-bigquery`, `google-cloud-bigquery-storage`, `google-cloud-bigtable`, `google-cloud-dataplex`, `google-cloud-discoveryengine`, `google-cloud-pubsub`, `google-cloud-secret-manager`, `google-cloud-spanner`, `google-cloud-speech`, `graphviz`, `jsonschema`, `mcp`, `opentelemetry-exporter-gcp-logging`, `-gcp-monitoring`, `-gcp-trace`, `opentelemetry-exporter-otlp-proto-http`, `opentelemetry-resourcedetector-gcp`, `opentelemetry-sdk`, `pyarrow`, `sqlalchemy`, `sqlalchemy-spanner`, `tzlocal`, `uvicorn`, `watchdog`; `rich` 15.0.0 requires `markdown-it-py` and `pygments`; `requests` requires `charset-normalizer` (the harness prints a `RequestsDependencyWarning` about it).
- **Unrelated or transitive:** `importlib-metadata` (`zipp`), `google-auth` (`pyasn1-modules`), `cffi` (`pycparser`), `google-cloud-storage` (`google-crc32c`, `google-resumable-media`), `openai` (`tqdm`), `tiktoken` (`regex`), `tokenizers` (`huggingface-hub`), `google-api-core` (`proto-plus`), `litellm` (`boto3`, `jsonschema`).
- **Uncertain:** whether any of the above matters on an exercised path. None was shown to.

**Interpretation:** the two graph-tool import gaps are closed, and OpenClaw no longer starts by itself. The graph tools have not been run, so whether they now work end to end is untested.

**VERIFIED**
- OpenClaw was auto-starting, is now stopped and disabled, and is still installed.
- `cachetools` 7.2.0 and `networkx` 3.7 installed, with no extra package and no change to the pinned harness packages.
- The four `swegemma` graph modules import.

**PARTIAL**
- The remaining `pip check` findings were classified from evidence of what ran, not proven irrelevant.

**UNPROVEN**
- That the graph and search tools work end to end (the no-model smoke test is the next step).
- That other tools are not affected by the remaining gaps.

---

### Experiment: Milestone 2 no-model graph-tool smoke test (Amendment 1, step 3)

**Goal:** show that the graph and search tools that failed in r1 attempt 1 (`No module named 'cachetools'`) now initialise and complete a small representative operation, with no model involved.

**Result:** PASS. No model was run, the model server stayed stopped, no task was solved, no patch was generated or applied, no benchmark result was produced, and no coding-performance result was measured.

**Material used:** the already-known dev task `rich_3894` (repo `Textualize/rich`, base commit `4d6d631a3d2deddf8405522d4b8c976a6d35726c`), read-only from `kaggle_data/tasks.jsonl`, `kaggle_data/graphs/rich_4d6d631a….json` and `kaggle_data/embeddings/rich_4d6d631a….npz`. No held-out task was read, and the repository snapshot was not touched.

**Precondition (VERIFIED):** branch `main`, HEAD `4428c79`, clean tree. WSL responsive, `uptime` 25 min. `docker ps` empty. `openclaw-gateway.service` inactive and disabled. Before: RAM 1,543 MiB used and 6,366 MiB available, swap 0 of 2,048 used.

**Dependency versions** (harness venv `/home/jesse/venvs/gemma4-harness`, run from `/tmp`): `cachetools` 7.2.0, `networkx` 3.7. `swegemma.graph.graph_utils`, `swegemma.graph.retrieval_utils`, `swegemma.graph.embedding_utils` and `swegemma.tools.graph` all import.

**Invocation.** A throwaway script (kept outside the repository, not committed) called the installed `swegemma.tools.graph` functions directly, the same code path the agent's tools use, with a stub context (`task` = `{instance_id, repo, base_commit}` for `rich_3894`, `graph_dir` = `kaggle_data/graphs`, `embeddings_dir` = `kaggle_data/embeddings`, budget check always allowing):
1. `get_code_subgraph(ctx, [])`, an initial probe. It returned `SubgraphExtractionError: subset_nodes cannot be empty.` This is the tool rejecting an empty input, not a dependency fault, and it was not the intended initialisation check. The graph was then loaded directly in step 2.
2. `swegemma.graph.get_graph(repo_name="rich_4d6d631a…", …)`: initialised. 1,986 nodes, 5,680 edges, all 1,986 nodes hydrated with embeddings.
3. `get_code_neighbors(ctx, "rich.text.Text", None, 10)`: `status ok`, 10 neighbors.
4. `search_similar_code(ctx, "rich.text.Text", 5)`: `status ok`, 5 results, each with `node_name`, `code`, `similarity`.
5. `get_code_subgraph(ctx, <first 5 nodes>)`: `status ok`, 5 nodes, 8 edges.

Result counts and shapes only. Relevance was not judged and is not model-quality evidence.

**Timing and resources:** the graph operations took 0.91 s, and the whole process 6.5 s wall time including imports. Peak process RSS was 343 MB. After: RAM 1,545 MiB used and 6,364 MiB available, swap 0 used. The host stayed responsive.

**Warnings:** `RequestsDependencyWarning: Unable to find acceptable character detection dependency (chardet or charset_normalizer)`. It comes from `requests`, is the known `charset-normalizer` gap already recorded above, and did not affect the graph path. Two `ResourceWarning` lines came from the throwaway script (an unclosed file handle) and are not harness warnings. No `ModuleNotFoundError`, no `SimilaritySearchError` and no crash occurred.

**Post-test state (VERIFIED):** `docker ps` empty (Gemma server stopped), OpenClaw inactive and disabled, repository clean before this record, `results/m2_baseline_r1/` and its logs untouched, no `m2_baseline_v2_*` directory exists.

**VERIFIED**
- The graph and search tool path (`get_code_neighbors`, `search_similar_code`, `get_code_subgraph`) initialises and completes on `rich_3894` materials with `cachetools` 7.2.0 and `networkx` 3.7, with no missing-dependency error.

**PARTIAL**
- Only one repository's graph (`rich_3894`) and three tools were exercised, called directly rather than through the agent loop, with a stub context.

**UNPROVEN**
- That the tools behave the same inside a full agent run (the new dry run is the next step).
- That other tools are unaffected by the remaining `pip check` gaps.
- Nothing about model or agent quality.

---

### Experiment: Milestone 2 corrective dry run on `rich_3894` (Amendment 1 §11.5, step 4)

**Goal:** exercise the REAL `swegemma` agent/evaluation path (harness → ADK runner → model → tools → workspace → verification → results) on `rich_3894`, through the repaired environment, to confirm the run reaches actual agent/model behaviour rather than failing on an ordinary missing prerequisite. This is a diagnostic dry run, **not** a baseline run, and its result is not counted toward Milestone 2 performance.

**Result:** run completed cleanly end to end. `resolved=false` (model failure, Phase 2 tests failed), no infrastructure error, no dependency error. This is expected diagnostic behaviour, not a measured baseline outcome.

**Precondition (VERIFIED):** branch `main`, HEAD `19091bb`, working tree clean, synced with `origin/main`, before and after. Pool fingerprint recomputed and confirmed unchanged (`e02d3059f9c0…aba60`, 124 files). Harness cache absent before the run (expected: cleared per the run procedure). OpenClaw inactive and disabled. `docker ps` empty. Port 8080 free. GPU: RTX 3070, 8,192 MiB, ~1.5–1.6 GiB used by unrelated processes. RAM before: 1,705 MiB used, 6,204 MiB available; swap 0/2,048. Disk: 946 GB free. `cachetools` 7.2.0 and `networkx` 3.7 confirmed importable from the exact harness venv (`/home/jesse/venvs/gemma4-harness`) that executed `swegemma eval`.

**Result namespace:** `results/m2_dryrun_v2/` (console log `results/m2_dryrun_v2_console.log`), an unmistakably non-baseline name distinct from both the original `results/m2_dryrun/` (pre-corrective) and any `m2_baseline_v2_*` namespace. Neither `results/m2_dryrun/`, `results/m2_baseline_r1/` nor any `m2_baseline_v2_*` path was written to, read from destructively, or overwritten.

**Cache.** `/tmp/swegemma_sp_cache_v8/` confirmed absent, then `rm -rf` run explicitly (no-op, already absent) before starting the eval. The run rebuilt it from the frozen wheel pool; after the first task's setup, the cache fingerprint was recomputed and matched the frozen value exactly: `c52a777befd2b12c719eb6363c547a82f3fe1c8e1f5821d72beea3a4e612bc47`.

**Server.** Started with the exact frozen command from [EVALUATION.md](EVALUATION.md) §4 (`docker start gemma4-e4b-server`, an existing container built from the pinned digest `ghcr.io/ggml-org/llama.cpp:server-cuda12@sha256:1f4b9cf58982…60ab6`). `GET /v1/models` answered within 1 s with `gemma-4-e4b-it`, context 32,768, `Q4_0`. `RestartCount` 0, `OOMKilled` false. GPU used rose to about 4.95–4.99 GiB, consistent with prior runs. The server was stopped (`docker stop`) after the run, restoring the quiet-host baseline; the container and image were not removed or modified.

**Invocation:** the frozen r-repeat command from EVALUATION.md §5, restricted to one task and pointed at the new namespace:
```bash
swegemma eval --tasks kaggle_data/tasks.jsonl --snapshots-dir kaggle_data/snapshots \
  --submission-dir kaggle_data/sample_submission --results-dir results/m2_dryrun_v2 \
  --image swebench-sandbox:latest --sandbox docker --models-yaml /home/jesse/gemma4-dev/dev_models.yaml \
  --task-ids rich_3894 \
  --max-tool-calls 30 --max-time-minutes 20 --timeout-seconds 300 \
  --concurrency 1 --display single --verbose
```

**Agent transcript (factual, not a quality judgment):** the agent found `rich/_inspect.py` (`run_command find`), read it (`read_file`), edited it (`edit_file`, 1 occurrence), ran `pytest tests/test_inspect.py` twice (both times other, unrelated assertions failed — the agent itself judged them unrelated to its fix), then called `submit_patch` (668 bytes, 1 file changed, `status: ok`), and finished with a natural-language summary. **The graph/search tools (`get_code_neighbors`, `search_similar_code`, `get_code_subgraph`) were available to both the root agent and the `code_analyzer` sub-agent (registered in `agent.yaml` and `sub_agents/code_analyzer.yaml`) but were not invoked by the model this run** — this was the model's own choice, not a tool failure, so this run does not directly demonstrate the graph tools succeeding inside the live agent loop (only the standalone smoke test recorded above does that).

**Harness result** (`results/m2_dryrun_v2/summary.json`, `task_results.jsonl`): `resolved=false`, `agent_patch_size=668`, `test_exit_code=1`, `tool_calls=5`, `total_llm_calls=7`, `duration_seconds=67.96`, `error=null`. Total 0/1 resolved.

**Warnings/errors:** only the known, harmless `RequestsDependencyWarning` about `charset_normalizer`. No `ModuleNotFoundError`, no `SimilaritySearchError`, no `Traceback`, no budget-exceeded message, no crash.

**Post-run state:** `docker ps` empty after stopping the server, OpenClaw inactive and disabled, repository clean, no baseline namespace touched. RAM after: 2,491 MiB used, 5,418 MiB available; swap rose to 5/2,048 MiB (consistent with a completed Docker Phase 2 verification and buffered container I/O, not exhaustion). GPU used 4,987 MiB right after the run (server still up at that point, before being stopped).

**Limitation, recorded honestly:** the intended continuous RAM/swap/GPU background logger (10 s interval) died when its WSL invocation ended, because it was started with `nohup … &` but not `disown`ed in that shell session — an operator error, not an infrastructure or dependency fault. No per-interval resource trace exists for the run's interior; only point-in-time RAM/swap/GPU readings before and immediately after are available (above), plus the Docker `RestartCount`/`OOMKilled` evidence. The run completed in 68 seconds, well under any budget, and the host remained responsive throughout (confirmed by the still-running monitor and successful result-file writes), so this gap does not put the PASS classification below in doubt, but it is a real coverage gap for anyone auditing the fine-grained resource curve.

**VERIFIED**
- The real agent/harness path (harness → ADK `Runner`/`agent_tool` → LiteLlm model client → tools → Docker sandbox verification → result writing) runs to completion on `rich_3894` with the repaired dependencies, with no missing-prerequisite failure.
- `cachetools` 7.2.0 and `networkx` 3.7 are visible to the exact process that ran the eval.
- Both fingerprints (pool and rebuilt cache) match their frozen values.
- The model server, sandbox image and harness versions match their pins exactly.
- No infrastructure error, dependency error, crash, or budget breach occurred. The model failure (unresolved patch) is an ordinary model-quality outcome, not an environment defect.

**PARTIAL**
- The graph/search tools were not exercised inside this particular live agent run (the model didn't call them); their live-loop behaviour still rests only on the earlier stub-context smoke test plus the fact that they are correctly registered as tools for both agents.
- The continuous resource log is missing for the run's interior, for the operator-error reason stated above; only pre/post point readings and Docker's own restart/OOM flags are available.

**UNPROVEN**
- General coding performance or competition-relevant conclusions. This is one non-counted diagnostic task, explicitly excluded from any x/3 tally.
- Whether the graph tools would behave identically inside the live loop if a task caused the model to actually call them (no task has yet forced that in this repaired environment).

---

### Experiment: Milestone 2 baseline v2, repeat 1 (`m2_baseline_v2_r1`) — COUNTED

**This is one of the 24 measured baseline runs (D1/D5/D6, EVALUATION.md).** Its `resolved` values count toward the frozen 8-task × 3-repeat baseline tally, per Amendment 1 §11.5 step 5. It is the first repeat after the two invalid/diagnostic attempts (`m2_baseline_r1` and the two corrective dry runs) recorded above.

**Precondition (VERIFIED):** branch `main`, HEAD `261370c`, clean, synced with `origin/main`, before and after. Pool fingerprint recomputed and confirmed unchanged: `e02d3059f9c04716d0b6e46d90364a5370e45385b284ab8c1c56a9c0d63aba60`, 124 files. Cache cleared (`/tmp/swegemma_sp_cache_v8/` was already absent from the prior corrective dry run; `rm -rf` run explicitly as a no-op), then rebuilt by the run itself; the cache fingerprint after the first task's setup matched the frozen value exactly: `c52a777befd2b12c719eb6363c547a82f3fe1c8e1f5821d72beea3a4e612bc47`. OpenClaw inactive and disabled throughout. RAM before: 1,757 MiB used, 6,152 MiB available; swap 5/2,048. GPU: RTX 3070, 8,192 MiB, ~1.56 GiB used by unrelated processes. Disk: 946 GB free. Model file SHA-256 reverified: `676c35070db6dbe52f93e9c864ee0fba4eddea94b9c875d9cb10daff453fbaee` (matches the frozen pin). All 8 dev tasks' snapshots, `tasks.jsonl` entries, graph JSON files and embedding NPZ files verified present for their exact base commits before starting. `cachetools` 7.2.0 and `networkx` 3.7 confirmed importable from the exact harness venv that ran `swegemma eval`.

**Result namespace:** `results/m2_baseline_v2_r1/` (console log `results/m2_baseline_v2_r1_console.log`, resource log `results/m2_baseline_v2_r1_resources.log`), confirmed absent before the run and not present anywhere else in the repository. `results/m2_baseline_r1/` (hashes reverified unchanged: `summary.json` `f05158a9…b7f79`, `task_results.jsonl` `0b7d7ab…639ce`), `results/m2_dryrun/` and `results/m2_dryrun_v2/` were not written to or modified.

**Server.** `docker start gemma4-e4b-server` (existing container, pinned digest `ghcr.io/ggml-org/llama.cpp:server-cuda12@sha256:1f4b9cf58982dd4d7cc497aea31b1a456ca9a3a1f94f527d317d3fdee0d60ab6`). Ready within 18 s (`gemma-4-e4b-it`, context 32,768, `Q4_0`). `RestartCount` 0 and `OOMKilled` false for the whole run. Stopped after the run.

**Telemetry.** The corrective dry run's telemetry logger died because it was launched with `nohup … &` but not detached from the WSL session; investigation traced this to WSL's own idle-VM shutdown closing the whole distro instance between tool calls with no open connection, not merely orphaning the process. The fix: a dedicated long-lived `Monitor`-driven `wsl` connection was kept open continuously for the run's duration (re-armed once, at its ~30-minute internal window boundary, with no gap) purely to prevent that idle shutdown, while a separate `setsid`-launched shell script (`/tmp/reslogger.sh`) appended one `timestamp mem_used_mb mem_avail_mb swap_used_mb gpu_used_mib` line every 10 s to `results/m2_baseline_v2_r1_resources.log`. This is host telemetry only, written outside `results/m2_baseline_v2_r1/`'s harness-owned files, and never fed into task evaluation. The logger's PID (5534) was confirmed alive immediately after launch and again after the baseline process (PID 5592) was confirmed running, and was killed cleanly after the run. **128 samples were captured, spanning 18:58:35–19:19:52 UTC**, covering the run's full duration (server start to task 8 completion) with no gap.

**Invocation** (exact, from EVALUATION.md §5, restricted only by result directory):
```bash
swegemma eval --tasks kaggle_data/tasks.jsonl --snapshots-dir kaggle_data/snapshots \
  --submission-dir kaggle_data/sample_submission --results-dir results/m2_baseline_v2_r1 \
  --image swebench-sandbox:latest --sandbox docker --models-yaml /home/jesse/gemma4-dev/dev_models.yaml \
  --task-ids rich_3894 rich_3278 rich_4076 rich_3905 rich_4079 rich_3470 rich_3130 rich_3061 \
  --max-tool-calls 30 --max-time-minutes 20 --timeout-seconds 300 \
  --concurrency 1 --display single --verbose
```
The harness executed the 8 tasks in `tasks.jsonl` order (not the `--task-ids` order), matching EVALUATION.md §5: `rich_4079`, `rich_4076`, `rich_3894`, `rich_3905`, `rich_3470`, `rich_3278`, `rich_3130`, `rich_3061`.

**Per-task result** (from `results/m2_baseline_v2_r1/task_results.jsonl` and `summary.json`, the primary evidence; console impressions used only to add tool/graph-usage detail):

| # | Task | Resolved | Patch size | Test exit | Tool calls | LLM calls | Duration (s) | Error | Category |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `rich_4079` | false | 722 | 1 | 10 | 12 | 89.47 | null | Phase 2 tests failed |
| 2 | `rich_4076` | false | 606 | 1 | 13 | 15 | 88.07 | null | Phase 2 tests failed |
| 3 | `rich_3894` | false | 698 | 1 | 7 | 9 | 55.77 | null | Phase 2 tests failed |
| 4 | `rich_3905` | **true** | 521 | 0 | 7 | 9 | 48.91 | null | resolved |
| 5 | `rich_3470` | false | 602 | 1 | 20 | 26 | 173.63 | null | Phase 2 tests failed |
| 6 | `rich_3278` | false | 0 | 1 | 20 | 24 | 147.10 | null | empty patch |
| 7 | `rich_3130` | false | 0 | 1 | 30 | 38 | 215.55 | null | budget exhausted (30/30 tool calls), then empty patch |
| 8 | `rich_3061` | false | 0 | -1 | 21 | 23 | 375.83 | `Sandbox execution error: Unterminated string starting at: line 1 column 12 (char 11)` | infra-adjacent model output error (see below) |

**Aggregate (from `summary.json`):** `total_tasks=8`, `resolved=1`, `resolution_rate=0.125`, `errors=1`. As x/3 so far (repeat 1 of 3): `rich_4079` 0/3, `rich_4076` 0/3, `rich_3894` 0/3, `rich_3905` 1/3, `rich_3470` 0/3, `rich_3278` 0/3, `rich_3130` 0/3, `rich_3061` 0/3. No stable-pass or stable-fail classification is made after only 1 of 3 repeats (EVALUATION.md §7 requires all 3).

**Graph-tool usage (observed, factual, not treated as quality evidence):** the graph/search tools were invoked by the live agent loop in 6 of 8 tasks (`rich_4079`, `rich_4076`, `rich_3894` at the root-agent level; `rich_3470`, `rich_3278`, `rich_3130` via the `code_analyzer_agent` sub-agent calling `search_similar_code` and, in `rich_3130`, `get_code_neighbors`), each with `status: ok`, `SimilaritySearchError`-free responses (some legitimately empty, `count: 0`, when no similar node existed). `rich_3905` and `rich_3061` did not invoke a graph tool. This is the first baseline evidence that the graph and sub-agent (`agent_tool`) path works inside the real, unmodified `sample_submission` configuration, not just in the earlier stub-context smoke test.

**Failure classification, per the precedence in EVALUATION.md §6:**
- **Model/agent outcomes:** `rich_4079`, `rich_4076`, `rich_3894`, `rich_3470` — patch submitted, Phase 2 tests failed (assertion-level, matching each task's known target tests). `rich_3278` — agent's own final summary claimed a fix, but the actually submitted patch was empty (`patch_size: 0`, `files_changed: 0`) after four consecutive `FileEditError: old_string not found` attempts on `rich/ansi.py`; recorded as an empty-patch model failure, and the discrepancy between the agent's narrated success and the empty artifact is noted for the record.
- **Budget outcome:** `rich_3130` exhausted the frozen 30-tool-call budget (`BudgetExceeded: Tool call budget exhausted (30 calls)`) while still searching for `TableDataElement`'s definition (the graph tool's `search_similar_code` and `get_code_neighbors` calls for this symbol returned no/unhelpful results across many attempts), then submitted an empty patch. Per §6's precedence order (infra, then no `submit_patch`, then empty patch, then patch not applied, then Phase 2 failed), this is classified as a budget/no-patch outcome, not an infrastructure failure.
- **Context-budget failure, not infrastructure (Amendment 1 §11.3):** `rich_3061`'s final LLM call generated 11,913 completion tokens before the llama.cpp server itself truncated it (`stop processing: n_tokens = 32767, truncated = 1`), i.e. the request hit the frozen 32,768-token context window, not the `max_output_tokens` 16384 setting. The truncation cut a tool-call argument mid-string, and the harness correctly caught this and reported `Non-retryable model error: JSONDecodeError: Unterminated string starting at: line 1 column 12 (char 11)`, recorded in `task_results.jsonl` as `test_exit_code: -1` and the sandbox-execution error text above. This is a **context-budget failure per Amendment 1 §11.3**: it is explicitly *not*, by itself, an infrastructure rerun condition, and this run was **not rerun**, consistent with the model-failure-is-never-rerun rule (only a genuine infrastructure failure, e.g. OOM or container crash, would qualify for the one-time rerun in EVALUATION.md §6/§9's rerun rule, and neither occurred here).
- **No infrastructure failure occurred in this run.** `docker ps` was clean throughout except for the expected per-task Phase 2 sandbox containers; `RestartCount` 0 and `OOMKilled` false for the model server for the whole run; no `ModuleNotFoundError` or `SimilaritySearchError` occurred; the harness process exited with `SWEGEMMA_EXIT_CODE=0` (a clean harness exit, independent of the individual tasks' model-level outcomes).

**Resources (from the 128-sample telemetry log, 10 s cadence, full run coverage):**
- RAM used climbed steadily across the batch as Docker layers/caches accumulated: from 2,186 MiB (run start) to a peak of **6,897 MiB** used (of 7,910 MiB total) during task 8 (`rich_3061`, the same task that caused the WSL/Docker stall in the original invalid r1 attempt 1). Available RAM reached a low of about 1.24 GiB but never zero.
- Swap climbed from 40 MiB to a peak of **737 MiB** (of the 2,048 MiB cap) — well under the cap, and never reached it.
- GPU used stayed in a narrow band, peak **5,017 MiB** of 8,192 MiB.
- Unlike the original invalid r1 attempt 1 (WSL/Docker became unresponsive under similar or lesser pressure), **the host remained fully responsive throughout this run**: `docker ps`, `free -m` and the model server's `/v1/models` endpoint all answered promptly at every check during the memory-pressure window, and the harness itself completed and exited cleanly. This is treated as improved evidence for the corrective host changes (OpenClaw disabled, dependency repair), though the margin (about 1.0–1.2 GiB free RAM at the tightest point) remains narrow and worth watching in r2/r3.

**Warnings/errors:** the known, harmless `RequestsDependencyWarning` about `charset_normalizer` at process start. Six `E srv send_error: request (34722 tokens) exceeds the available context size` lines appear in `docker logs gemma4-e4b-server`, but their timestamp format and exact wording match the already-documented `rich_4079` context-overflow error from the original invalid r1 attempt 1 (see above); `docker start` preserves a container's log history across restarts, and no task in this run's own console log or `task_results.jsonl` shows that error, so these are treated as stale, pre-existing log lines, not new errors from this run. The one genuine error this run produced (`rich_3061`'s `JSONDecodeError`) is documented above under context-budget failure.

**Post-run validation:** `summary.json` and `task_results.jsonl` inspected directly (table above). Model server stopped cleanly after confirming `RestartCount`/`OOMKilled`. Telemetry logger confirmed alive throughout and stopped cleanly afterward. `docker ps` empty after stopping the server. OpenClaw confirmed inactive and disabled after the run. Final RAM/swap: 1,571 MiB used, 6,338 MiB available, swap 226/2,048 (recovered after the last sandbox container exited). `results/m2_baseline_r1/` hashes reverified unchanged.

**VERIFIED**
- All 8 frozen dev tasks ran under the exact frozen configuration (budgets, model, image, harness pins, environment fingerprints) and completed to a written `summary.json`/`task_results.jsonl`.
- 1 of 8 tasks resolved (`rich_3905`).
- No infrastructure failure occurred: 0 restarts, no OOM, no missing-dependency error, clean harness exit.
- The graph/search tools and the `code_analyzer_agent` sub-agent both functioned correctly inside the real, unmodified agent loop across 6 of 8 tasks.
- The host remained responsive under peak memory pressure (6,897 MiB used, 737 MiB swap) that resembled the pressure that stalled the original invalid r1 attempt 1.
- `rich_3061`'s failure is a context-window overflow (32,768-token limit), not an infrastructure defect, per Amendment 1 §11.3, and was correctly not rerun.

**PARTIAL**
- The telemetry gap-recovery method (a long-lived keep-alive `wsl` connection) is evidence specific to this operating environment (Windows + WSL2) and was necessary only because of WSL's own idle-VM shutdown; it is not a change to the frozen experimental configuration.
- `rich_3278`'s agent narrated a successful fix while submitting an empty patch; this discrepancy between the model's self-report and the actual artifact is recorded but not further analyzed here (out of scope for a measurement milestone).

**UNPROVEN**
- Task-level stability: only 1 of the frozen 3 repeats is complete. No task can yet be classified stable-pass, unstable or stable-fail (EVALUATION.md §7 requires all 3 repeats).
- Whether `rich_3061`'s context overflow would recur in r2/r3 given the lack of a fixed seed (EVALUATION.md §4).
- General coding performance, competition-relevant conclusions, or any comparison to a future change (the comparison rule in EVALUATION.md §7 requires the full 3-repeat baseline first).
