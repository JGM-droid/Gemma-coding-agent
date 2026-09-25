# Gemma Coding Agent

## Goal

Build a credible autonomous coding agent that can receive a software issue, investigate an unfamiliar repository, modify code, run tests, revise its work, submit a patch, and provide evidence that the result works.

Secondary goal: stay as compatible as practical with the [Google Gemma 4 Developer Agent Competition](https://www.kaggle.com/competitions/gemma-4-developer-agent), with a possible legitimate submission if that is feasible without substantial spending.

## Architecture (accepted)

- **The official `swegemma` harness is canonical.** We build on the organizers' evaluation harness rather than replacing it.
- **Docker sandbox** for repository execution and verification (the official `swebench-sandbox` image).
- **The declarative competition agent configuration stays canonical** (`agent.yaml`, prompts, sub-agents, tools, in the official submission format).
- **Local development uses a smaller real Gemma surrogate** (Gemma 4 E4B-it, Q4_0 GGUF, served by llama.cpp on the local GPU).
- **The exact competition model** (`gemma-4-31b-it-qat-w4a16-ct`) is a separate compatibility profile, used when practical.
- **Deterministic infrastructure** handles limits, filesystem boundaries, patch extraction, test results and grading.
- **The model** handles interpretation, investigation, hypotheses, edits and debugging decisions.

## Status

**Milestone 1 (Local Feasibility): PASS.** One real end-to-end run on one competition task worked: the local Gemma model investigated the repository, edited code, ran a test and submitted a patch that the harness verified independently.

That evidence proves the setup is **feasible**. It does not prove benchmark performance, competition score, or equivalence with the 31B competition model.

## Repository contents

This repository holds project documentation and, later, project code. Competition data (`kaggle_data/`), run artifacts (`results/`) and model weights stay local and are excluded by `.gitignore`.

## Read next

- [AGENTS.md](AGENTS.md): working rules for any AI agent or contributor modifying this repository
- [docs/ROADMAP.md](docs/ROADMAP.md): current state, accepted architecture, active milestone
- [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md): technical experiment records and evidence
- [docs/BUILD_JOURNAL.md](docs/BUILD_JOURNAL.md): plain-English story of what was done, why, and what was learned
