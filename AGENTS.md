# AGENTS.md: rules for agents working in this repository

These rules apply to Claude, Codex, Copilot and any other agent or contributor that modifies this repository. They are authoritative. If a request conflicts with them, stop and ask the project owner.

## A. Before modifying the repository

1. Read this file completely.
2. Read **Current State** and **Active Milestone** in [docs/ROADMAP.md](docs/ROADMAP.md).
3. Read only the relevant parts of [README.md](README.md), [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md) and [docs/BUILD_JOURNAL.md](docs/BUILD_JOURNAL.md).
4. Inspect the actual repository state: `git status` and `git diff`.
5. Do not trust a previous agent's handoff without verifying the repository state yourself.

## B. One modifying agent at a time

- Only one implementation agent may modify the repository for a given work item.
- Do not create competing roadmaps or planning documents. [docs/ROADMAP.md](docs/ROADMAP.md) is the only roadmap.
- Do not redesign the accepted architecture (see ROADMAP) without explicit approval from the project owner.

## C. Scope discipline

- Work only on the active milestone and the bounded task you were given.
- Do not begin later-milestone work.
- No unrelated refactors, speculative abstractions or placeholder production code.
- No unnecessary dependencies or files.
- Preserve user-authored and previously verified work.
- Never commit competition data (`kaggle_data/`), run artifacts (`results/`), model weights, or credentials.

## D. Deterministic vs model-driven responsibilities

**Deterministic software controls:**
- permissions
- paths
- limits and budgets
- validation
- workflow state
- Git patch extraction
- pass/fail test results
- safety boundaries

**The model may decide:**
- issue interpretation
- which code to inspect
- hypotheses
- debugging steps
- which commands to run
- code edits
- interpretation of failures

Do not move a deterministic responsibility into the model, or the reverse, without explicit approval.

## E. Verification

- Run the tests the task requires.
- Report exact commands and exact results.
- Label every claim **VERIFIED**, **PARTIAL** or **UNPROVEN**.
- Never claim something works without evidence.

## F. Implementation report (required for every completed work item)

1. What changed, and which files changed
2. Commands and tests run, with exact results
3. What is verified, partial or unproven
4. Remaining risks or decisions
5. Recommended next bounded task
6. Whether the repository is safe to hand off

## G. Agent handoffs

Before switching agents:
- Stop at a clean boundary when practical.
- Inspect `git status` and `git diff`.
- Run the relevant tests.
- Record completed, incomplete and unproven work, with exact commands and failures.
- Commit verified work when appropriate.
- Use a temporary `docs/HANDOFF.md` only if incomplete work genuinely needs transferring. Remove or clear it once the transfer is resolved.

## H. Build journal requirement (important)

At the end of each completed milestone or meaningful project stage, update [docs/BUILD_JOURNAL.md](docs/BUILD_JOURNAL.md).

Its purpose is **learning and recall for the project owner**, not technical logging. Each entry explains in plain English:

- What I was trying to prove or accomplish
- What I did
- Why I did it that way
- What happened
- What failed or surprised me
- What I learned
- What changed because of this
- What came next

Rules:
- Write for the project owner, not for another AI.
- Use plain English, and explain important technical terms the first time they appear.
- Focus on reasoning and learning, not package or version dumps.
- Don't duplicate detailed commands or hashes from [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md); refer to it instead.
- Keep chronological order. Add new entries at the end.
- Don't rewrite old entries to make the story cleaner. If an earlier assumption was wrong, record the correction honestly in a new entry.
- **A milestone is not closed until its journal entry is written.**

When a significant architectural concept comes up during implementation, explain it in the journal in practical language. Examples: clean verification container, deterministic controls vs model reasoning, sandbox isolation, model serving, tool calling, the Git patch as the artifact, evaluation budgets, reproducibility.
