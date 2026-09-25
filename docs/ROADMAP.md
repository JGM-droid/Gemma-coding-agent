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

**Status: NOT STARTED**

The detailed purpose, scope, tests and acceptance criteria must be reviewed and approved by the project owner before any implementation begins.

# Future direction

After a reproducible baseline exists, later work may measure the agent across more tasks and check compatibility with the exact competition model. Those milestones will be defined only when they are reached.
