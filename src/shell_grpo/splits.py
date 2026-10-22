"""Split assignment by connected component (PLAN Phase 3).

A component is a set of tasks sharing a solution template or source episode.
Components are assigned WHOLLY to one split before any variants are created,
and the assignment here is the single source of truth: the dataset builder
and the audit both read it.

Design recorded 2026-10-22 (authored-only path):
- Every D/S/V diagnostic is a development-pool component (DESIGN.md: diagnostic
  exercises and their derivatives never enter the final unseen test set).
- The six held-out T families (T1..T6, authored 2026-10-22 with solution
  patterns distinct from every development family) are the reserved test
  components.
- Within development, train/validation is grouped by component: the components
  where the baseline already earns partial credit (D01, D05 families — the
  checkpoint-selection signal) sit in validation together with the independent
  S07/S09/V02/V05 components; everything else trains.
- Target proportions are 60/20/20 but components are never split to meet
  them; actual counts are reported by the dataset audit.
"""

from __future__ import annotations

SPLITS = ("train", "validation", "test")

# component_id -> {split, origin, tasks, families}
COMPONENTS: dict[str, dict] = {
    # ---- development / train ------------------------------------------------
    "comp-d02": {"split": "train", "origin": "dev-diagnostic",
                 "tasks": ["D02", "S02"], "families": ["copy-recursive"]},
    "comp-d03": {"split": "train", "origin": "dev-diagnostic",
                 "tasks": ["D03", "S05"], "families": ["text-aggregate"]},
    "comp-d04": {"split": "train", "origin": "dev-diagnostic",
                 "tasks": ["D04", "S08"], "families": ["repair-copy"]},
    "comp-s03": {"split": "train", "origin": "dev-diagnostic",
                 "tasks": ["S03"], "families": ["move-select"]},
    "comp-s04": {"split": "train", "origin": "dev-diagnostic",
                 "tasks": ["S04"], "families": ["file-list-nul"]},
    "comp-v01": {"split": "train", "origin": "dev-diagnostic",
                 "tasks": ["V01"], "families": ["copy-flat"]},
    "comp-v03": {"split": "train", "origin": "dev-diagnostic",
                 "tasks": ["V03"], "families": ["repair-listing"]},
    "comp-v04": {"split": "train", "origin": "dev-diagnostic",
                 "tasks": ["V04"], "families": ["text-slice"]},
    # ---- development / validation ------------------------------------------
    "comp-d01": {"split": "validation", "origin": "dev-diagnostic",
                 "tasks": ["D01", "S01"], "families": ["file-select-count"]},
    "comp-d05": {"split": "validation", "origin": "dev-diagnostic",
                 "tasks": ["D05", "S06", "S10"], "families": ["count-pattern", "repair-count"]},
    "comp-s07": {"split": "validation", "origin": "dev-diagnostic",
                 "tasks": ["S07"], "families": ["csv-extract"]},
    "comp-s09": {"split": "validation", "origin": "dev-diagnostic",
                 "tasks": ["S09"], "families": ["repair-literal-search"]},
    "comp-v02": {"split": "validation", "origin": "dev-diagnostic",
                 "tasks": ["V02"], "families": ["file-select-aggregate"]},
    "comp-v05": {"split": "validation", "origin": "dev-diagnostic",
                 "tasks": ["V05"], "families": ["file-select-argmax"]},
    # ---- held-out test -------------------------------------------------------
    **{
        f"comp-{task_id.lower()[:2]}-{variant}": {
            "split": "test", "origin": "held-out-test",
            "tasks": [task_id], "families": [family],
        }
        for task_id, family, variant in [
            ("T1a", "dedup-order", "sorted"), ("T1b", "dedup-order", "first-seen"),
            ("T2a", "column-projection", "field2"), ("T2b", "column-projection", "swap"),
            ("T3a", "rename-batch", "htm-html"), ("T3b", "rename-batch", "backup-prefix"),
            ("T4a", "zero-janitor", "delete"), ("T4b", "zero-janitor", "count"),
            ("T5a", "head-tail", "all-lines"), ("T5b", "head-tail", "skip-blank"),
            ("T6a", "line-numbering", "all"), ("T6b", "line-numbering", "nonblank"),
        ]
    },
}

# Component ids for T-families: stable explicit form (comp-t1-sorted etc.) is
# generated above; keep the visible mapping for the audit.
TASK_TO_COMPONENT = {
    task_id: comp
    for comp, spec in COMPONENTS.items()
    for task_id in spec["tasks"]
}
TASK_TO_SPLIT = {
    task_id: COMPONENTS[comp]["split"]
    for comp, spec in COMPONENTS.items()
    for task_id in spec["tasks"]
}


def split_for(task_id: str) -> str:
    if task_id not in TASK_TO_SPLIT:
        raise KeyError(f"task {task_id!r} has no component assignment")
    return TASK_TO_SPLIT[task_id]


def component_for(task_id: str) -> str:
    return TASK_TO_COMPONENT[task_id]


def all_components() -> dict[str, dict]:
    return dict(COMPONENTS)


def split_counts(tasks: list[str]) -> dict[str, int]:
    counts = {s: 0 for s in SPLITS}
    for task_id in tasks:
        counts[split_for(task_id)] += 1
    return counts


def check_integrity(known_tasks: list[str]) -> list[str]:
    """Adversarial leakage checks; returns a list of violations (empty = clean)."""
    problems = []
    seen = {}
    for comp, spec in COMPONENTS.items():
        if spec["split"] not in SPLITS:
            problems.append(f"{comp}: invalid split {spec['split']!r}")
        for task_id in spec["tasks"]:
            if task_id in seen:
                problems.append(f"task {task_id} in two components: {seen[task_id]}, {comp}")
            seen[task_id] = comp
    for task_id in known_tasks:
        if task_id not in seen:
            problems.append(f"registered task {task_id} has no component assignment")
    for task_id, comp in seen.items():
        if task_id not in known_tasks:
            problems.append(f"component {comp} references unknown task {task_id}")
    # family leakage: a family may appear in only one split
    family_split: dict[str, str] = {}
    for comp, spec in COMPONENTS.items():
        for family in spec["families"]:
            if family in family_split and family_split[family] != spec["split"]:
                problems.append(
                    f"family {family} appears in {family_split[family]} and {spec['split']}"
                )
            family_split[family] = spec["split"]
    # diagnostics never in test
    for comp, spec in COMPONENTS.items():
        if spec["split"] == "test" and spec["origin"] != "held-out-test":
            problems.append(f"test split contains non-held-out component {comp}")
    return problems
