"""Task/fixture-case framework and the diagnostic registry.

A task module declares: prompt, fixture cases (builder + verifier), declared
weights, progress fixtures, reference/alternate/wrong scripts and provenance.
The runner and acceptance harness consume only what is defined here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..contracts import TaskRecord
from ..fixtures import Builder, GroundTruth
from ..verifiers import FixtureVerdict, VerifyContext

BuilderFn = Builder
VerifyFn = Callable[[VerifyContext], FixtureVerdict]

SCRIPTS_ROOT_HINT = "data/examples/scripts"


@dataclass
class WrongScript:
    filename: str
    expect: str  # "zero" (task reward must be 0) or "partial" (score in (0,1))
    note: str


@dataclass
class FixtureCase:
    fixture_id: str
    weight: float
    progress: bool
    build: BuilderFn
    verify: VerifyFn | None = None  # None -> score_simple on the declared truth

    def fixture_record(self) -> dict:
        return {"fixture_id": self.fixture_id, "progress": self.progress, "weight": self.weight}


@dataclass
class Task:
    task_id: str
    family_id: str
    source_cluster_id: str
    prompt: str
    invocation: str
    fixtures: list[FixtureCase]
    reference: str
    alternate: str
    wrongs: list[WrongScript]
    notes: str = ""
    provenance_extra: dict = field(default_factory=dict)
    support_files_hint: dict = field(default_factory=dict)

    def fixture_ids(self) -> list[str]:
        return [f.fixture_id for f in self.fixtures]

    def progress_ids(self) -> list[str]:
        return [f.fixture_id for f in self.fixtures if f.progress]

    def weights(self) -> dict[str, float]:
        return {f.fixture_id: f.weight for f in self.fixtures}

    def record(self, split: str = "development_pool") -> TaskRecord:
        provenance = {
            "source": "authored",
            "rationale": self.notes,
            "campaign": "phase1-diagnostics",
        }
        provenance.update(self.provenance_extra)
        return TaskRecord(
            task_id=self.task_id,
            family_id=self.family_id,
            source_cluster_id=self.source_cluster_id,
            prompt=[{"role": "user", "content": self.prompt}],
            fixture_id=f"{self.task_id}-fixtures-v1",
            verifier_id=f"{self.task_id}-verifier-v1",
            invocation=self.invocation,
            split=split,
            provenance=provenance,
            fixtures_declared=[f.fixture_record() for f in self.fixtures],
        )


_REGISTRY: dict[str, Task] = {}


def register(task: Task) -> Task:
    if task.task_id in _REGISTRY:
        raise ValueError(f"duplicate task id {task.task_id}")
    total = sum(f.weight for f in task.fixtures)
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"{task.task_id}: fixture weights sum to {total}, expected 1.0")
    _REGISTRY[task.task_id] = task
    return task


def get_task(task_id: str) -> Task:
    if task_id not in _REGISTRY:
        raise KeyError(f"unknown task {task_id!r}; known: {sorted(_REGISTRY)}")
    return _REGISTRY[task_id]


def all_tasks() -> list[Task]:
    return [_REGISTRY[k] for k in sorted(_REGISTRY)]
