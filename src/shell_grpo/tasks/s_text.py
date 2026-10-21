"""S05–S07: text-transformation diagnostics from the Pi campaign."""

from __future__ import annotations

import random

from ..fixtures import GroundTruth, put
from ..verifiers import (
    CheckResult,
    FixtureVerdict,
    VerifyContext,
    score_csv_roundtrip,
    score_text_output,
    check_exit_equals,
    check_stdout_empty,
    violation_if_changed,
)
from .base import FixtureCase, Task, WrongScript, register
from .s_fileops import PROVENANCE, _err


def _expected_tsv(pairs: list[tuple[str, int]]) -> list[bytes]:
    totals: dict[str, int] = {}
    for key, value in pairs:
        totals[key] = totals.get(key, 0) + value
    return [f"{k}\t{totals[k]}".encode() for k in sorted(totals, key=lambda s: s.encode())]


def _unreadable_file(name: str):
    def build(root, rng: random.Random) -> GroundTruth:
        put(root, name, b"ERROR hidden inside\n", mode=0o000)
        return _err([name])

    return build


# ---------------------------------------------------------------------------
# S05 — aggregate TSV values (with malformed-row discipline)
# ---------------------------------------------------------------------------


def _s05_main(root, rng: random.Random) -> GroundTruth:
    pairs = [
        ("apple", 3), ("banana", 12), ("apple", 9), ("Cherry", 1),
        ("zebra", 0), ("apple", 1000000),
    ]
    lines = [f"{k}\t{v}" for k, v in pairs]
    put(root, "input.tsv", ("\n".join(lines) + "\n").encode())
    return GroundTruth(
        argv=["input.tsv"],
        expected_stdout=b"".join(line + b"\n" for line in _expected_tsv(pairs)),
    )


def _s05_single(root, rng: random.Random) -> GroundTruth:
    put(root, "input.tsv", b"only\t41\n")
    return GroundTruth(argv=["input.tsv"], expected_stdout=b"only\t41\n")


def _s05_empty(root, rng: random.Random) -> GroundTruth:
    put(root, "input.tsv", b"")
    return GroundTruth(argv=["input.tsv"], expected_stdout=b"")


def _s05_zeros(root, rng: random.Random) -> GroundTruth:
    put(root, "input.tsv", b"k1\t0012\nk1\t8\nk2\t0\nk1\t0000\nk3\t7\n")
    return GroundTruth(
        argv=["input.tsv"],
        expected_stdout=b"".join(
            line + b"\n" for line in _expected_tsv([("k1", 12), ("k1", 8), ("k2", 0), ("k3", 7)])
        ),
    )


def _malformed(content: bytes):
    def build(root, rng: random.Random) -> GroundTruth:
        put(root, "input.tsv", content)
        return _err(["input.tsv"])

    return build


register(
    Task(
        task_id="S05",
        family_id="text-aggregate",
        source_cluster_id="s05-cluster",
        prompt=(
            "Write a Bash script that reads a headerless two-column TSV file given as its "
            "first argument and prints one `key<TAB>total` line per distinct key, with the "
            "totals summed, sorted ascending by key bytes in C locale order. Keys are nonempty "
            "and contain no tab or newline characters; values are nonnegative decimal integers "
            "(a value like `0012` is a plain nonnegative integer equal to 12). The file has at "
            "most 1,000 rows and no value exceeds 1,000,000. An empty input file is a success "
            "with no output. If any row is malformed — wrong field count, empty key, or a "
            "value that is not a plain nonnegative integer — print a diagnostic to stderr, "
            "write nothing to stdout, exit with status 2, and leave the input unchanged. A "
            "missing or unreadable input file is also exit 2."
        ),
        invocation="solution.sh <input-file>",
        fixtures=[
            FixtureCase("s05-main", 0.2, True, _s05_main),
            FixtureCase("s05-single", 0.05, False, _s05_single),
            FixtureCase("s05-empty", 0.05, False, _s05_empty),
            FixtureCase("s05-leading-zeros", 0.1, True, _s05_zeros),
            FixtureCase("s05-three-fields", 0.06, False, _malformed(b"a\t1\textra\n")),
            FixtureCase("s05-empty-key", 0.06, False, _malformed(b"\t5\n")),
            FixtureCase("s05-negative", 0.06, False, _malformed(b"k\t-5\n")),
            FixtureCase("s05-alpha", 0.06, False, _malformed(b"k\t12a\n")),
            FixtureCase("s05-plus", 0.06, False, _malformed(b"k\t+7\n")),
            FixtureCase("s05-float", 0.06, False, _malformed(b"k\t3.5\n")),
            FixtureCase("s05-missing", 0.08, False, lambda root, rng: _err(["input.tsv"])),
            FixtureCase("s05-noargs", 0.08, False, lambda root, rng: _err([])),
            FixtureCase(
                "s05-unreadable", 0.08, False,
                _unreadable_file("input.tsv"),
            ),
        ],
        reference="reference.sh",
        alternate="alternate.sh",
        wrongs=[
            WrongScript("wrong-noop.sh", "zero", "prints nothing"),
            WrongScript("wrong-empty.sh", "zero", "empty file (invalid_script)"),
            WrongScript(
                "wrong-numeric-sort.sh", "partial",
                "sorts keys numerically: order component lost on main but totals intact",
            ),
            WrongScript(
                "wrong-accepts-plus.sh", "partial",
                "accepts `+7` (awk numeric coercion): the plus fixture fails, rest pass",
            ),
        ],
        notes="Frozen campaign brief S05; shares template lineage with D03.",
        provenance_extra={**PROVENANCE, "brief": "pi-sessions/tasks/S05.md",
                          "fixture_spec": "pi-sessions/fixtures/S05.md"},
    )
)


def _unreadable_file(name: str):
    def build(root, rng: random.Random) -> GroundTruth:
        put(root, name, b"ERROR hidden inside\n", mode=0o000)
        return _err([name])

    return build


# ---------------------------------------------------------------------------
# S06 — count literal ERROR lines
# ---------------------------------------------------------------------------

S06_MAIN = (
    "2026-10-01 INFO boot sequence normal\n"
    "2026-10-01 ERROR disk latency high\n"
    "2026-10-02 error level fallback\n"
    "2026-10-02 ERROR retrying; ERROR persisted\n"
    "2026-10-02 ERRor threshold crossed\n"
    "2026-10-03 ERRORS cleared\n"
    "2026-10-03 XERRORX sentinel\n"
    "2026-10-03 INFO shutdown clean\n"
).encode()

S06_NONE = b"clean line one\nclean line two\nthird clean line\nfourth\nfifth\nsixth\n"

S06_TRICKY = (
    "-dash line contains ERROR mid-line\n"
    "ERROR\n"
    "ERROR start and end ERROR\n"
    "clean tail line\n"
).encode()


def _count_fixture(name: str, content: bytes, expected: int):
    def build(root, rng: random.Random) -> GroundTruth:
        put(root, "input.log", content)
        return GroundTruth(argv=["input.log"], expected_stdout=f"{expected}\n".encode())

    return build


_S06_CASES = [
    ("s06-main", 0.25, True, _count_fixture("a", S06_MAIN, 4)),
    ("s06-none", 0.1, False, _count_fixture("a", S06_NONE, 0)),
    ("s06-empty", 0.1, False, _count_fixture("a", b"", 0)),
    ("s06-tricky", 0.2, True, _count_fixture("a", S06_TRICKY, 3)),
    ("s06-missing", 0.1, False, lambda root, rng: _err(["input.log"])),
    ("s06-unreadable", 0.15, False, _unreadable_file("input.log")),
    ("s06-noargs", 0.1, False, lambda root, rng: _err([])),
]

register(
    Task(
        task_id="S06",
        family_id="count-pattern",
        source_cluster_id="s06-cluster",
        prompt=(
            "Write a Bash script that reads the file given as its first argument and prints "
            "the number of lines that contain the character sequence `ERROR` somewhere in "
            "them — uppercase, case-sensitive, as a literal substring, with no special meaning "
            "given to any other characters on the line. Print only the count followed by a "
            "newline. A file with no matches, or an empty file, is a success that prints `0`. "
            "If the argument is missing, or the file does not exist or cannot be read, print a "
            "diagnostic to stderr, write nothing to stdout, and exit with status 2. Do not "
            "modify the input."
        ),
        invocation="solution.sh <input-file>",
        fixtures=[FixtureCase(fid, w, prog, builder) for fid, w, prog, builder in _S06_CASES],
        reference="reference.sh",
        alternate="alternate.sh",
        wrongs=[
            WrongScript("wrong-noop.sh", "zero", "prints nothing"),
            WrongScript("wrong-empty.sh", "zero", "empty file (invalid_script)"),
            WrongScript(
                "wrong-hardcode.sh", "partial",
                "echo 4 — passes main (progress) but fails tricky/none/empty and errors",
            ),
            WrongScript(
                "wrong-word-match.sh", "partial",
                "grep -w word match: misses ERRORS/XERRORX on main but passes tricky",
            ),
        ],
        notes="Frozen campaign brief S06; template shared with D05 and S10.",
        provenance_extra={**PROVENANCE, "brief": "pi-sessions/tasks/S06.md",
                          "fixture_spec": "pi-sessions/fixtures/S06.md"},
    )
)


# ---------------------------------------------------------------------------
# S07 — extract CSV columns (parse-equivalence acceptance)
# ---------------------------------------------------------------------------

S07_MAIN = (
    "id,name,amount\n"
    '1,alice,10\n'
    '2,"bob, jr",20\n'
    '3,"say ""hi"" now",30\n'
    '4,"multi\n'
    'line name",40\n'
    '5,,"50"\n'
).encode()

S07_EXPECTED_ROWS = [
    ["1", "alice"],
    ["2", "bob, jr"],
    ["3", 'say "hi" now'],
    ["4", "multi\nline name"],
    ["5", ""],
]


def _s07_main(root, rng: random.Random) -> GroundTruth:
    put(root, "input.csv", S07_MAIN)
    return GroundTruth(argv=["input.csv"], extra={"rows": S07_EXPECTED_ROWS})


def _s07_empty_body(root, rng: random.Random) -> GroundTruth:
    put(root, "input.csv", b"id,name,amount\n")
    return GroundTruth(argv=["input.csv"], extra={"rows": []})


def _s07_bad_header(root, rng: random.Random) -> GroundTruth:
    put(root, "input.csv", b"id,name,value\n1,alice,10\n")
    return _err(["input.csv"])


def _s07_not_utf8(root, rng: random.Random) -> GroundTruth:
    put(root, "input.csv", b"id,name,amount\n1,alf\xffred,10\n")
    return _err(["input.csv"])


def _s07_csv_verify(ctx: VerifyContext) -> FixtureVerdict:
    return score_csv_roundtrip(ctx, ctx.truth.extra["rows"])


register(
    Task(
        task_id="S07",
        family_id="csv-extract",
        source_cluster_id="s07-cluster",
        prompt=(
            "Write a script that reads the CSV file given as its first argument and writes a "
            "new CSV to stdout containing only the `id` and `name` columns. The input is valid "
            "UTF-8 and its header row is exactly `id,name,amount`. The output's first line "
            "must be the header `id,name`, followed by one row per input data row in the same "
            "order, keeping the `id` and `name` values byte-for-byte. Values may contain "
            "quoted commas, doubled quote characters, and embedded newlines — preserve them "
            "correctly per CSV quoting rules, so that parsing the output yields exactly the "
            "original `id` and `name` values. Use LF line endings. If the file is missing, "
            "unreadable, not valid UTF-8, or its header is not exactly `id,name,amount`, print "
            "a diagnostic to stderr, write nothing to stdout, and exit with status 2. Do not "
            "modify the input. Python 3's standard-library `csv` module is available and may "
            "be used."
        ),
        invocation="solution.sh <input-file>",
        fixtures=[
            FixtureCase("s07-main", 0.5, True, _s07_main, _s07_csv_verify),
            FixtureCase("s07-empty-body", 0.1, False, _s07_empty_body, _s07_csv_verify),
            FixtureCase("s07-missing", 0.08, False, lambda root, rng: _err(["input.csv"])),
            FixtureCase("s07-unreadable", 0.08, False, _unreadable_file("input.csv")),
            FixtureCase("s07-bad-header", 0.08, False, _s07_bad_header),
            FixtureCase("s07-not-utf8", 0.08, False, _s07_not_utf8),
            FixtureCase("s07-noargs", 0.08, False, lambda root, rng: _err([])),
        ],
        reference="reference.sh",
        alternate="alternate.sh",
        wrongs=[
            WrongScript("wrong-noop.sh", "zero", "prints nothing"),
            WrongScript("wrong-empty.sh", "zero", "empty file (invalid_script)"),
            WrongScript(
                "wrong-cut.sh", "zero",
                "cut -d, -f1,2 breaks on quoted commas: parse-equivalence fails",
            ),
            WrongScript(
                "wrong-keeps-amount.sh", "partial",
                "keeps three columns: header check fails but rows parse (0.5 cap on main)",
            ),
        ],
        notes=(
            "Frozen campaign brief S07; Python 3 csv permitted per the brief; acceptance is "
            "parse-equivalence via an independent parser."
        ),
        provenance_extra={**PROVENANCE, "brief": "pi-sessions/tasks/S07.md",
                          "fixture_spec": "pi-sessions/fixtures/S07.md"},
    )
)
