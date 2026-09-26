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
- Determinism of an eligible rich task under the rebuilt cache (not yet repeated).
