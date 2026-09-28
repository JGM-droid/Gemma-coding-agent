#!/usr/bin/env python3
"""Milestone 3 WI-3.2/WI-3.5a: deterministic signal extractor.

Reads the 24 counted Milestone 2 baseline runs (results/m2_baseline_v2_r1/,
_r2/, _r3/ — 8 frozen dev tasks each) and the frozen task definitions
(kaggle_data/tasks.jsonl), and extracts only the OBJECTIVE, deterministic
signals frozen in docs/ROADMAP.md's Milestone 3 "Deterministic signals to
extract" section.

This script does NOT interpret why a run failed, does NOT assign a
failure-attribution-codebook label, and does NOT judge semantic
correctness. It only reports what the raw artifacts objectively contain,
so that a later, separate work item (WI-3.3) can apply the frozen
codebook to these facts.

Read-only: this script never writes to, renames, or deletes anything
under results/ or kaggle_data/. It fails loudly (non-zero exit, clear
message) on missing or malformed required artifacts rather than
inventing a default. Output is a single deterministic JSON document,
written to stdout or to the file given by --output; nothing is written
under results/.

Invalid/dry-run result directories (results/m2_baseline_r1/,
results/m2_dryrun/, results/m2_dryrun_v2/, results/m2_post_baseline_control/)
are never read by this script; only the three counted repeats are used.

WI-3.5a (schema v2, additive only): each frozen trace step records its
own `extra.author` (e.g. "swe_baseline_agent" for the root agent,
"code_analyzer_agent" for the sub-agent invoked via that tool). The v1
schema's `prompt_tokens_by_step`/`max_recorded_prompt_tokens` fields mix
root-agent and sub-agent prompt-token series together, which understates
the root agent's own actual context growth (the sub-agent's context is a
separate, shorter-lived conversation). v2 adds root-only and sub-only
prompt-token series and derived fields alongside the unchanged v1 fields,
so root-agent context growth can be examined on its own. Every v1 field
keeps its exact name, shape and value; v2 only adds new fields and bumps
the top-level "schema" string from "m3_signal_extraction_v1" to
"m3_signal_extraction_v2". The extractor fails loudly if any trace step
carrying `metrics.prompt_tokens` lacks `extra.author`, since that author
tag is required to assign the step to the root-agent or sub-agent series.

Usage:
    python3 scripts/m3_extract_signals.py [-o OUTPUT.json]
    python3 scripts/m3_extract_signals.py --results-dir results --tasks-file kaggle_data/tasks.jsonl

Exit status: 0 on success (24 records extracted), non-zero on any
missing/malformed required artifact.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPEATS = ("r1", "r2", "r3")

# The 8 frozen Milestone 2 dev tasks, per docs/EVALUATION.md section 1.
# This is a closed, frozen list — not derived from directory listings —
# so the extractor fails loudly if a counted run's task set differs.
COUNTED_TASKS = (
    "rich_3894",
    "rich_3278",
    "rich_4076",
    "rich_3905",
    "rich_4079",
    "rich_3470",
    "rich_3130",
    "rich_3061",
)

# Tool functions whose `arguments.filepath` (or, for submit_patch,
# observation content) is relevant to the signals below.
FILE_READ_TOOLS = ("read_file",)
FILE_WRITE_TOOLS = ("edit_file", "write_file")

# Compatibility indicator only (see docs/EVALUATION.md section 6): whether
# a submission came within this many tool calls. Recorded, not
# reinterpreted as proof of competition-budget success.
COMPETITION_TOOL_CALL_THRESHOLD = 10

_CONTEXT_TOKEN_RE = re.compile(r"request \((\d+) tokens\) exceeds")

# WI-3.5a (schema v2): the root agent's own author tag, per the frozen
# trace's `extra.author` field. Any other author on a prompt-token-bearing
# step is treated as a sub-agent (e.g. "code_analyzer_agent").
ROOT_AGENT_AUTHOR = "swe_baseline_agent"

# WI-3.5a (schema v2): the token-context threshold used to locate the
# first root-agent step whose prompt-token count exceeds it (see
# `root_prompt_tokens_first_step_above_14336`). This is the
# `token_threshold` value from the host reference path's
# EventsCompactionConfig, per the 2026-09-28 audit (S4, transcribed, not
# re-retrieved this work item) — recorded here only as a fixed reference
# point for comparison, not as a claim that compaction was configured for
# the Milestone 2 runs (it was not; see WI-3.5a's EXPERIMENTS.md entry).
ROOT_PROMPT_TOKEN_REFERENCE_THRESHOLD = 14336

# WI-3.5a (schema v2): the only tool-call argument keys retained in
# `largest_root_prompt_increase.from_step_tool_args_subset`, to keep that
# field small and avoid echoing large argument payloads (e.g. full
# `new_string`/`old_string` edit bodies) into the extracted signal file.
ALLOWED_TOOL_ARG_KEYS = frozenset(
    {"filepath", "start_line", "end_line", "command", "query", "request"}
)


class ExtractorError(RuntimeError):
    """Raised for any missing or malformed required artifact. Fatal."""


def _fail(message: str) -> "None":
    raise ExtractorError(message)


def load_ndjson(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        _fail(f"required artifact missing: {path}")
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                _fail(f"malformed JSON line {line_no} in {path}: {exc}")
    return records


def load_json(path: Path) -> Any:
    if not path.is_file():
        _fail(f"required artifact missing: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _fail(f"malformed JSON in {path}: {exc}")


def diff_header_files(diff_text: str) -> list[str]:
    """Extract the set of file paths touched by a unified diff, from its
    `+++ b/...` / `--- a/...` header lines only. Purely syntactic; no
    interpretation of diff content."""
    files: set[str] = set()
    for line in diff_text.splitlines():
        if line.startswith("+++ b/") or line.startswith("--- a/"):
            files.add(line.split(" ", 1)[1][2:])
        elif line.startswith("+++ /dev/null") or line.startswith("--- /dev/null"):
            continue
    return sorted(files)


def load_task_definitions(tasks_path: Path, task_ids: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    """Return {task_id: {"gold_target_files": [...], "gold_target_test_files": [...]}}
    for exactly the requested task_ids, derived only from the frozen
    kaggle_data/tasks.jsonl `patch` and `test_patch` fields."""
    if not tasks_path.is_file():
        _fail(f"required artifact missing: {tasks_path}")
    wanted = set(task_ids)
    found: dict[str, dict[str, Any]] = {}
    with tasks_path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError as exc:
                _fail(f"malformed JSON line {line_no} in {tasks_path}: {exc}")
            iid = d.get("instance_id")
            if iid in wanted:
                found[iid] = {
                    "gold_target_files": diff_header_files(d.get("patch", "")),
                    "gold_target_test_files": diff_header_files(d.get("test_patch", "")),
                }
    missing = wanted - found.keys()
    if missing:
        _fail(f"{tasks_path} does not contain task definitions for: {sorted(missing)}")
    return found


def tool_calls_in_order(trace: dict[str, Any]) -> list[tuple[int, dict[str, Any], dict[str, Any] | None]]:
    """Flatten a trace's steps into a deterministic, 1-based-ordered list
    of (index, tool_call, observation) triples. `observation` is the
    step's single observation dict shared by every tool_call recorded in
    that step (the harness records at most one tool_call per step in the
    traces inspected during WI-3.2; if a future trace has more, each
    still shares the step's one observation, which is recorded as-is)."""
    out: list[tuple[int, dict[str, Any], dict[str, Any] | None]] = []
    idx = 0
    for step in trace.get("steps", []):
        obs = step.get("observation")
        for call in step.get("tool_calls") or []:
            idx += 1
            out.append((idx, call, obs))
    return out


def observation_status_json(obs: dict[str, Any] | None) -> dict[str, Any] | None:
    """Parse a tool observation's `content` field as JSON, if possible.
    Returns None if there is no observation or its content is not valid
    JSON (some observations, e.g. from run_command, may not parse; that
    is recorded as `content_parsed: False` by the caller, not treated as
    an error)."""
    if not obs:
        return None
    content = obs.get("content")
    if not isinstance(content, str):
        return None
    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def extract_run(
    repeat: str,
    task_id: str,
    task_result: dict[str, Any],
    trace: dict[str, Any],
    task_def: dict[str, Any],
    patch_file: Path,
    evidence_prefix: str,
) -> dict[str, Any]:
    calls = tool_calls_in_order(trace)

    resolved = bool(task_result.get("resolved"))
    reported_error = task_result.get("error")
    reported_tool_calls = task_result.get("tool_calls")
    reported_patch_size = task_result.get("agent_patch_size")

    # Patch / submission signals.
    submit_calls = [(i, c, o) for (i, c, o) in calls if c.get("function_name") == "submit_patch"]
    submit_patch_called = len(submit_calls) > 0
    submit_patch_tool_call_index = submit_calls[0][0] if submit_calls else None
    submitted_patch_empty: bool | None = None
    submitted_patch_size_from_observation: int | None = None
    if submit_calls:
        obs_json = observation_status_json(submit_calls[0][2])
        if obs_json is not None and "patch_size" in obs_json:
            submitted_patch_size_from_observation = obs_json.get("patch_size")
            submitted_patch_empty = submitted_patch_size_from_observation == 0
    if submitted_patch_empty is None and reported_patch_size is not None:
        submitted_patch_empty = reported_patch_size == 0

    patch_file_size_bytes = patch_file.stat().st_size if patch_file.is_file() else None

    submit_patch_within_threshold: bool | None = None
    if submit_patch_tool_call_index is not None:
        submit_patch_within_threshold = submit_patch_tool_call_index <= COMPETITION_TOOL_CALL_THRESHOLD

    # Tool / edit mechanics.
    total_tool_calls_recorded = len(calls)
    file_edit_error_indices: list[int] = []
    file_read_error_indices: list[int] = []
    command_error_indices: list[int] = []
    budget_exceeded_indices: list[int] = []
    for i, call, obs in calls:
        obs_json = observation_status_json(obs)
        error_type = obs_json.get("error_type") if obs_json else None
        if error_type == "FileEditError":
            file_edit_error_indices.append(i)
        elif error_type == "FileReadError":
            file_read_error_indices.append(i)
        elif error_type == "CommandError":
            command_error_indices.append(i)
        elif error_type == "BudgetExceeded":
            budget_exceeded_indices.append(i)

    # Context signals — per-step metrics, as recorded in the trace only.
    prompt_tokens_by_step = []
    for step in trace.get("steps", []):
        metrics = step.get("metrics")
        if isinstance(metrics, dict) and "prompt_tokens" in metrics:
            prompt_tokens_by_step.append(
                {"step_id": step.get("step_id"), "prompt_tokens": metrics["prompt_tokens"]}
            )
    prompt_tokens_by_step.sort(key=lambda r: r["step_id"])
    max_recorded_prompt_tokens = (
        max(r["prompt_tokens"] for r in prompt_tokens_by_step) if prompt_tokens_by_step else None
    )

    # WI-3.5a (schema v2) — split the same prompt-token-bearing steps by
    # `extra.author` into root-agent vs. sub-agent series. Fails loudly
    # (does not silently default) if a prompt-token-bearing step has no
    # recorded author, since the split cannot be made without it.
    root_step_records: list[tuple[int, int, dict[str, Any]]] = []  # (step_id, prompt_tokens, step)
    sub_agent_prompt_tokens_by_step: list[dict[str, Any]] = []
    steps_with_prompt_tokens = 0
    steps_missing_author = 0
    for step in trace.get("steps", []):
        metrics = step.get("metrics")
        if not (isinstance(metrics, dict) and "prompt_tokens" in metrics):
            continue
        steps_with_prompt_tokens += 1
        extra = step.get("extra")
        author = extra.get("author") if isinstance(extra, dict) else None
        if not author:
            steps_missing_author += 1
            _fail(
                f"{repeat}/{task_id}: trace step_id={step.get('step_id')} has "
                f"metrics.prompt_tokens but no extra.author; cannot assign it to the "
                f"root-agent or sub-agent series"
            )
        if author == ROOT_AGENT_AUTHOR:
            root_step_records.append((step.get("step_id"), metrics["prompt_tokens"], step))
        else:
            sub_agent_prompt_tokens_by_step.append(
                {"step_id": step.get("step_id"), "author": author, "prompt_tokens": metrics["prompt_tokens"]}
            )
    root_step_records.sort(key=lambda r: r[0])
    sub_agent_prompt_tokens_by_step.sort(key=lambda r: r["step_id"])

    root_agent_prompt_tokens_by_step = [
        {"step_id": sid, "prompt_tokens": pt} for (sid, pt, _step) in root_step_records
    ]
    max_root_agent_prompt_tokens = max((pt for (_sid, pt, _s) in root_step_records), default=None)
    last_root_agent_prompt_tokens = root_step_records[-1][1] if root_step_records else None
    max_sub_agent_prompt_tokens = (
        max(r["prompt_tokens"] for r in sub_agent_prompt_tokens_by_step)
        if sub_agent_prompt_tokens_by_step
        else None
    )
    last_sub_agent_prompt_tokens = (
        sub_agent_prompt_tokens_by_step[-1]["prompt_tokens"] if sub_agent_prompt_tokens_by_step else None
    )
    sub_agent_step_count = len(sub_agent_prompt_tokens_by_step)

    sub_agent_invocation_count = 0
    for step in trace.get("steps", []):
        extra = step.get("extra")
        author = extra.get("author") if isinstance(extra, dict) else None
        if author != ROOT_AGENT_AUTHOR:
            continue
        for call in step.get("tool_calls") or []:
            if call.get("function_name") == "code_analyzer_agent":
                sub_agent_invocation_count += 1

    root_prompt_values = [pt for (_sid, pt, _s) in root_step_records]
    root_prompt_tokens_nondecreasing = all(
        b >= a for a, b in zip(root_prompt_values, root_prompt_values[1:])
    )

    root_prompt_tokens_first_step_above_14336 = None
    for sid, pt, _s in root_step_records:
        if pt > ROOT_PROMPT_TOKEN_REFERENCE_THRESHOLD:
            root_prompt_tokens_first_step_above_14336 = sid
            break

    largest_root_prompt_increase = None
    best_increase = None
    for (from_sid, from_pt, from_step), (to_sid, to_pt, _to_step) in zip(
        root_step_records, root_step_records[1:]
    ):
        increase = to_pt - from_pt
        if best_increase is None or increase > best_increase:
            best_increase = increase
            from_metrics = from_step.get("metrics") or {}
            from_tool_calls = from_step.get("tool_calls") or []
            from_step_tool_names = [c.get("function_name") for c in from_tool_calls]
            args_subset: dict[str, Any] = {}
            for c in from_tool_calls:
                call_args = c.get("arguments")
                if isinstance(call_args, dict):
                    for k, v in call_args.items():
                        if k in ALLOWED_TOOL_ARG_KEYS:
                            args_subset[k] = v
            from_obs = from_step.get("observation")
            from_content = from_obs.get("content") if isinstance(from_obs, dict) else None
            from_step_observation_content_chars = (
                len(from_content) if isinstance(from_content, str) else None
            )
            largest_root_prompt_increase = {
                "from_step_id": from_sid,
                "to_step_id": to_sid,
                "increase": increase,
                "from_step_completion_tokens": from_metrics.get("completion_tokens"),
                "from_step_tool_names": from_step_tool_names,
                "from_step_tool_args_subset": args_subset,
                "from_step_observation_content_chars": from_step_observation_content_chars,
            }

    prompt_token_author_coverage = {
        "steps_with_prompt_tokens": steps_with_prompt_tokens,
        "steps_missing_author": steps_missing_author,
    }

    error_text = reported_error or ""
    context_window_exceeded_error = "ContextWindowExceededError" in error_text
    context_window_exceeded_reported_tokens = None
    if context_window_exceeded_error:
        m = _CONTEXT_TOKEN_RE.search(error_text)
        if m:
            context_window_exceeded_reported_tokens = int(m.group(1))

    malformed_output_error = "JSONDecodeError" in error_text or "Unterminated string" in error_text
    # WI-3.2 finding (see README note below and final report): the
    # frozen results/ artifacts (trace JSON, task_results.jsonl,
    # console logs) do not preserve the model-server-side token count
    # at the moment a malformed generation was produced. That evidence
    # was only ever visible via the live llama.cpp server log, which is
    # not written to results/. This field is therefore never computed
    # as True/False from these artifacts; it is set to an explicit
    # sentinel distinguishing "not applicable" from "insufficient
    # artifact data", per the WI-3.1 requirement to never silently
    # treat missing evidence as false.
    if not malformed_output_error:
        malformed_output_context_boundary_evidence = "not_applicable"
    else:
        malformed_output_context_boundary_evidence = "insufficient_artifact_data"

    # Repository interaction.
    gold_target_files = task_def["gold_target_files"]
    gold_target_test_files = task_def["gold_target_test_files"]

    read_paths = {
        c.get("arguments", {}).get("filepath")
        for (_, c, _) in calls
        if c.get("function_name") in FILE_READ_TOOLS
    }
    edited_paths = {
        c.get("arguments", {}).get("filepath")
        for (_, c, _) in calls
        if c.get("function_name") in FILE_WRITE_TOOLS
    }
    gold_target_file_read = any(p in read_paths for p in gold_target_files)
    gold_target_file_edited = any(p in edited_paths for p in gold_target_files)

    test_file_edit_indices = [
        i
        for (i, c, _) in calls
        if c.get("function_name") in FILE_WRITE_TOOLS
        and str(c.get("arguments", {}).get("filepath", "")).startswith("tests/")
    ]
    test_file_edited = len(test_file_edit_indices) > 0

    run_commands = [
        str(c.get("arguments", {}).get("command", ""))
        for (_, c, _) in calls
        if c.get("function_name") == "run_command"
    ]
    if gold_target_test_files:
        target_test_run = any(
            any(tf in cmd for tf in gold_target_test_files) for cmd in run_commands
        )
    else:
        target_test_run = "unknown"  # task definition supplied no test_patch file list

    return {
        "repeat": repeat,
        "task_id": task_id,
        "resolved": resolved,

        "submit_patch_called": submit_patch_called,
        "submit_patch_tool_call_index": submit_patch_tool_call_index,
        "submit_patch_within_10_tool_calls": submit_patch_within_threshold,
        "submitted_patch_empty": submitted_patch_empty,
        "submitted_patch_size_bytes_reported": reported_patch_size,
        "submitted_patch_size_bytes_from_observation": submitted_patch_size_from_observation,
        "patch_file_present": patch_file.is_file(),
        "patch_file_size_bytes": patch_file_size_bytes,

        "total_tool_calls_recorded_in_trace": total_tool_calls_recorded,
        "total_tool_calls_reported_by_harness": reported_tool_calls,
        "file_edit_error_count": len(file_edit_error_indices),
        "file_edit_error_tool_call_indices": file_edit_error_indices,
        "file_read_error_count": len(file_read_error_indices),
        "file_read_error_tool_call_indices": file_read_error_indices,
        "command_error_count": len(command_error_indices),
        "command_error_tool_call_indices": command_error_indices,
        "budget_exceeded_event_count": len(budget_exceeded_indices),
        "budget_exceeded_tool_call_indices": budget_exceeded_indices,

        "max_recorded_prompt_tokens": max_recorded_prompt_tokens,
        "prompt_tokens_by_step": prompt_tokens_by_step,
        "context_window_exceeded_error": context_window_exceeded_error,
        "context_window_exceeded_reported_tokens": context_window_exceeded_reported_tokens,
        "malformed_output_error": malformed_output_error,
        "malformed_output_context_boundary_evidence": malformed_output_context_boundary_evidence,

        # WI-3.5a (schema v2, additive) — root-agent-only vs. sub-agent-only
        # prompt-token series, derived from `extra.author` on each
        # prompt-token-bearing trace step. See module docstring.
        "root_agent_prompt_tokens_by_step": root_agent_prompt_tokens_by_step,
        "sub_agent_prompt_tokens_by_step": sub_agent_prompt_tokens_by_step,
        "max_root_agent_prompt_tokens": max_root_agent_prompt_tokens,
        "last_root_agent_prompt_tokens": last_root_agent_prompt_tokens,
        "max_sub_agent_prompt_tokens": max_sub_agent_prompt_tokens,
        "last_sub_agent_prompt_tokens": last_sub_agent_prompt_tokens,
        "sub_agent_step_count": sub_agent_step_count,
        "sub_agent_invocation_count": sub_agent_invocation_count,
        "root_prompt_tokens_nondecreasing": root_prompt_tokens_nondecreasing,
        "root_prompt_tokens_first_step_above_14336": root_prompt_tokens_first_step_above_14336,
        "largest_root_prompt_increase": largest_root_prompt_increase,
        "prompt_token_author_coverage": prompt_token_author_coverage,

        "gold_target_files": gold_target_files,
        "gold_target_file_read": gold_target_file_read,
        "gold_target_file_edited": gold_target_file_edited,
        "gold_target_test_files": gold_target_test_files,
        "target_test_run": target_test_run,
        "test_file_edited": test_file_edited,
        "test_file_edit_tool_call_indices": test_file_edit_indices,

        "reported_error_text": reported_error,
        "phase2_test_exit_code": task_result.get("test_exit_code"),

        "evidence": {
            "task_results_path": f"{evidence_prefix}/task_results.jsonl",
            "trace_path": f"{evidence_prefix}/traces/trace_{task_id}.json",
            "patch_path": f"{evidence_prefix}/patches/{task_id}.patch" if patch_file.is_file() else None,
        },
    }


def extract_repeat(results_dir: Path, repeat: str, task_defs: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    repeat_dir = results_dir / f"m2_baseline_v2_{repeat}"
    if not repeat_dir.is_dir():
        _fail(f"required counted-run directory missing: {repeat_dir}")

    task_results_path = repeat_dir / "task_results.jsonl"
    records = load_ndjson(task_results_path)
    found_ids = [r.get("instance_id") for r in records]
    if sorted(found_ids) != sorted(COUNTED_TASKS):
        _fail(
            f"{task_results_path} does not contain exactly the 8 frozen dev tasks; "
            f"found {sorted(found_ids)}, expected {sorted(COUNTED_TASKS)}"
        )
    by_id = {r["instance_id"]: r for r in records}

    evidence_prefix = f"results/m2_baseline_v2_{repeat}"
    out = []
    for task_id in COUNTED_TASKS:
        trace_path = repeat_dir / "traces" / f"trace_{task_id}.json"
        trace = load_json(trace_path)
        patch_file = repeat_dir / "patches" / f"{task_id}.patch"
        out.append(
            extract_run(
                repeat=repeat,
                task_id=task_id,
                task_result=by_id[task_id],
                trace=trace,
                task_def=task_defs[task_id],
                patch_file=patch_file,
                evidence_prefix=evidence_prefix,
            )
        )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("results"),
        help="Path to the results/ directory (default: results)",
    )
    parser.add_argument(
        "--tasks-file",
        type=Path,
        default=Path("kaggle_data/tasks.jsonl"),
        help="Path to kaggle_data/tasks.jsonl (default: kaggle_data/tasks.jsonl)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Write JSON output here instead of stdout. Never under results/.",
    )
    args = parser.parse_args(argv)

    if args.output is not None:
        try:
            args.output.resolve().relative_to((args.results_dir).resolve())
            _fail("--output must not be inside the results/ directory")
        except ValueError:
            pass  # good: output is not inside results/

    try:
        task_defs = load_task_definitions(args.tasks_file, COUNTED_TASKS)
        all_runs: list[dict[str, Any]] = []
        for repeat in REPEATS:
            all_runs.extend(extract_repeat(args.results_dir, repeat, task_defs))
    except ExtractorError as exc:
        print(f"m3_extract_signals: FATAL: {exc}", file=sys.stderr)
        return 1

    if len(all_runs) != len(REPEATS) * len(COUNTED_TASKS):
        print(
            f"m3_extract_signals: FATAL: extracted {len(all_runs)} runs, "
            f"expected {len(REPEATS) * len(COUNTED_TASKS)}",
            file=sys.stderr,
        )
        return 1

    all_runs.sort(key=lambda r: (r["repeat"], r["task_id"]))

    document = {
        "schema": "m3_signal_extraction_v2",
        "counted_run_count": len(all_runs),
        "repeats": list(REPEATS),
        "tasks": list(COUNTED_TASKS),
        "runs": all_runs,
    }

    text = json.dumps(document, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.write_text(text, encoding="utf-8")
        print(f"m3_extract_signals: wrote {len(all_runs)} run records to {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
