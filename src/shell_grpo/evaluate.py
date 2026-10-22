"""Extraction and evaluation: completions -> scripts -> GradeResults -> records.

Output contract (DESIGN.md): exactly one Bash script in one fenced ```bash
block in the final response. Reasoning / thought-channel text is never
executed. The contract is frozen only after inspection of real E4B output
(Phase 2 records the inspected samples privately).
"""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

FENCE_RE = re.compile(r"```(?:bash|sh|shell)\s*\n(.*?)```", re.DOTALL)


@dataclass
class ExtractionResult:
    ok: bool
    script: str | None
    reason: str
    n_blocks: int = 0

    def to_dict(self) -> dict:
        return {"ok": self.ok, "reason": self.reason, "n_blocks": self.n_blocks,
                "script_sha256": hashlib.sha256(self.script.encode()).hexdigest() if self.script else None}


def extract_script(text: str) -> ExtractionResult:
    """Exactly one fenced bash/sh/shell block with nonempty content."""
    blocks = FENCE_RE.findall(text or "")
    if len(blocks) == 0:
        return ExtractionResult(False, None, "no fenced bash block in final response", 0)
    if len(blocks) > 1:
        return ExtractionResult(False, None, f"{len(blocks)} fenced bash blocks; contract allows exactly one", len(blocks))
    script = blocks[0]
    if not script.strip():
        return ExtractionResult(False, None, "fenced bash block is empty", 1)
    return ExtractionResult(True, script, "one fenced bash block", 1)


@dataclass
class EvaluationRecord:
    """Per-task/per-candidate evaluation record (PLAN Phase 2)."""

    task_id: str
    candidate_id: str
    model: dict  # repo_id, revision, quantization
    generation_settings: dict
    prompt_sha256: str
    raw_completion_ref: str  # private artifact path holding the full completion
    completion_sha256: str
    extraction: dict  # ExtractionResult.to_dict()
    script: str | None
    script_sha256: str | None
    grade_result: dict | None  # full GradeResult dict
    task_score: float | None
    aggregate_status: str | None
    critical_violations: list = field(default_factory=list)
    truncated: bool = False
    new_tokens: int = 0
    generation_ms: int = 0
    grading_ms: int = 0

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def evaluate_completion(
    task,
    generation,  # GenerationRecord-like: has task_id, completion, prompt_sha256, settings, truncated, new_tokens, duration_ms
    runner,
    *,
    candidate_id: str,
    group_seed: int,
    raw_dir: Path,
    support_files: dict | None = None,
) -> EvaluationRecord:
    """Extract the script from one completion, grade it, and build the record.

    The raw completion is persisted privately under raw_dir before any
    grading; records reference it by path + hash. Infrastructure failures
    are not model failures: the GradeResult carries its own status.
    """
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    completion_hash = hashlib.sha256(generation.completion.encode()).hexdigest()
    raw_path = raw_dir / f"{task.task_id}-{candidate_id}.txt"
    raw_path.write_text(generation.completion)

    started = time.monotonic()
    extraction = extract_script(generation.completion)
    grade_dict = None
    task_score = None
    status = None
    criticals: list = []
    if extraction.ok:
        result = grade_with_support(
            task.task_id, extraction.script, group_seed, runner,
            candidate_id=candidate_id, support_files=support_files,
        )
        grade_dict = result.to_dict()
        task_score = result.task_score
        status = result.aggregate_status
        criticals = result.critical_violations
    grading_ms = int((time.monotonic() - started) * 1000)

    return EvaluationRecord(
        task_id=task.task_id,
        candidate_id=candidate_id,
        model={"repo_id": generation.settings.get("repo_id"),
               "revision": generation.settings.get("revision")},
        generation_settings=generation.settings,
        prompt_sha256=generation.prompt_sha256,
        raw_completion_ref=str(raw_path),
        completion_sha256=completion_hash,
        extraction=extraction.to_dict(),
        script=extraction.script,
        script_sha256=hashlib.sha256(extraction.script.encode()).hexdigest() if extraction.script else None,
        grade_result=grade_dict,
        task_score=task_score,
        aggregate_status=status,
        critical_violations=criticals,
        truncated=generation.truncated,
        new_tokens=generation.new_tokens,
        generation_ms=generation.duration_ms,
        grading_ms=grading_ms,
    )


def grade_with_support(task_id, script, seed, runner, *, candidate_id, support_files):
    from .runner import grade_script

    return grade_script(
        task_id, script, seed, runner,
        candidate_id=candidate_id, group_id=f"eval-{candidate_id}",
        support_files=support_files,
    )


def summarize_pass_rate(records: list[EvaluationRecord]) -> dict:
    """Primary endpoint view: single-attempt full-pass rate + score stats."""
    total = len(records)
    full_pass = sum(1 for r in records if r.task_score == 1.0 and r.aggregate_status == "ok")
    scored = [r for r in records if r.task_score is not None]
    extraction_failures = [r for r in records if not r.extraction.get("ok")]
    by_task: dict = {}
    for r in records:
        by_task.setdefault(r.task_id, []).append(r.task_score)
    return {
        "records": total,
        "full_pass": full_pass,
        "full_pass_rate": full_pass / total if total else 0.0,
        "mean_score": (sum(s for s in (r.task_score for r in scored) if s is not None) / len(scored)) if scored else None,
        "unscorable": sum(1 for r in records if r.aggregate_status == "infrastructure_error"),
        "extraction_failures": len(extraction_failures),
        "critical_violation_records": sum(1 for r in records if r.critical_violations),
        "truncated": sum(1 for r in records if r.truncated),
        "by_task_mean": {t: (sum(s for s in scores if s is not None) / len(scores) if scores else None)
                         for t, scores in by_task.items()},
    }
