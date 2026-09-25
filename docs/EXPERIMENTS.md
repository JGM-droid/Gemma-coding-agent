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
