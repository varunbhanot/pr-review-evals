#!/usr/bin/env python3
"""Plant exactly one realistic bug in each selected PR.

Mutations target lines the PR itself added (the '+' lines in the patch),
applied to the head_files/ copy of the source. Deterministic via --seed.

For ~half the PRs (clean controls) we write ground_truth.json with
bug_type="clean" and do not mutate.

Writes per PR:
  mutated/<file>          - mutated source (mirrors head_files layout)
  mutated.diff            - unified diff of head_files -> mutated
  ground_truth.json       - {file, line, bug_type, description, clean}

Bug types:
  off_by_one, inverted_condition, wrong_default, swallowed_exception,
  missing_none_check, wrong_variable

If automatic mutation fails for a PR, ground_truth.json gets
"needs_manual": true and scripts/manual_plant_helper.md explains how
to plant by hand.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import random
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUG_TYPES = [
    "off_by_one",
    "inverted_condition",
    "wrong_default",
    "swallowed_exception",
    "missing_none_check",
    "wrong_variable",
]


@dataclass
class Mutation:
    file: str
    line: int  # 1-based line in the mutated file
    bug_type: str
    description: str
    original: str
    mutated: str


def load_added_lines(patch: str | None) -> set[int]:
    """Return 1-based new-file line numbers that the PR added ('+' lines)."""
    if not patch:
        return set()
    added: set[int] = set()
    new_line = 0
    for raw in patch.splitlines():
        if raw.startswith("@@"):
            # @@ -a,b +c,d @@
            m = re.search(r"\+(\d+)(?:,(\d+))?", raw)
            if not m:
                continue
            new_line = int(m.group(1))
            continue
        if raw.startswith("+++") or raw.startswith("---"):
            continue
        if raw.startswith("+"):
            added.add(new_line)
            new_line += 1
        elif raw.startswith("-"):
            # old line only
            continue
        else:
            # context
            new_line += 1
    return added


def package_py_candidates(pr_dir: Path) -> list[tuple[Path, set[int], dict]]:
    """Return (head_file_path, added_line_set, file_meta) for mutable .py files."""
    files = json.loads((pr_dir / "files.json").read_text())
    out = []
    for f in files:
        name = f.get("filename") or ""
        if not name.endswith(".py"):
            continue
        if f.get("status") == "removed":
            continue
        head = pr_dir / "head_files" / name
        if not head.exists():
            continue
        parts = set(Path(name).parts)
        # Prefer non-test sources but allow tests as fallback
        added = load_added_lines(f.get("patch"))
        if not added:
            continue
        out.append((head, added, f))
    # Sort: package files first, then tests
    def rank(item):
        name = item[2]["filename"]
        parts = set(Path(name).parts)
        is_test = bool(parts & {"tests", "test"}) or Path(name).name.startswith("test_")
        return (1 if is_test else 0, name)

    out.sort(key=rank)
    return out


def try_off_by_one(source: str, added: set[int], rng: random.Random) -> Mutation | None:
    lines = source.splitlines(keepends=True)
    # Look for comparisons or slices involving integers on added lines
    pattern = re.compile(
        r"(?P<a>.{0,40}?)(?P<op><=|>=|<|>|==|!=)(?P<b>\s*)(?P<num>\d+)(?P<c>\b.*)"
    )
    candidates = []
    for i, line in enumerate(lines):
        lineno = i + 1
        if lineno not in added:
            continue
        if line.lstrip().startswith("#"):
            continue
        m = pattern.search(line)
        if not m:
            continue
        num = int(m.group("num"))
        if num > 10000:
            continue
        candidates.append((lineno, line, m))
    if not candidates:
        return None
    lineno, line, m = rng.choice(candidates)
    num = int(m.group("num"))
    delta = rng.choice([-1, 1])
    new_num = max(0, num + delta)
    if new_num == num:
        new_num = num + 1
    new_line = (
        line[: m.start("num")] + str(new_num) + line[m.end("num") :]
    )
    return Mutation(
        file="",
        line=lineno,
        bug_type="off_by_one",
        description=f"Changed literal {num} to {new_num} in comparison/expression",
        original=line.rstrip("\n"),
        mutated=new_line.rstrip("\n"),
    )


def try_inverted_condition(source: str, added: set[int], rng: random.Random) -> Mutation | None:
    lines = source.splitlines(keepends=True)
    swaps = [
        ("==", "!="),
        ("!=", "=="),
        ("<=", ">"),
        (">=", "<"),
        ("<", ">="),
        (">", "<="),
        (" is not ", " is "),
        (" is ", " is not "),
        (" not in ", " in "),
        (" in ", " not in "),
    ]
    candidates = []
    for i, line in enumerate(lines):
        lineno = i + 1
        if lineno not in added:
            continue
        stripped = line.lstrip()
        if not stripped.startswith(("if ", "elif ", "while ", "assert ")):
            # also allow inline conditions
            if " if " not in line and "while " not in line:
                continue
        for old, new in swaps:
            if old in line:
                candidates.append((lineno, line, old, new))
                break
    if not candidates:
        return None
    lineno, line, old, new = rng.choice(candidates)
    # Replace only the first occurrence carefully
    new_line = line.replace(old, new, 1)
    if new_line == line:
        return None
    return Mutation(
        file="",
        line=lineno,
        bug_type="inverted_condition",
        description=f"Inverted condition: replaced {old!r} with {new!r}",
        original=line.rstrip("\n"),
        mutated=new_line.rstrip("\n"),
    )


def try_wrong_default(source: str, added: set[int], rng: random.Random) -> Mutation | None:
    lines = source.splitlines(keepends=True)
    # Match default args like foo: bool = True or foo=None
    pattern = re.compile(
        r"(def\s+\w+\s*\(.*?)(\b\w+)(\s*[:=]\s*)(True|False|None)(.*)"
    )
    candidates = []
    for i, line in enumerate(lines):
        lineno = i + 1
        if lineno not in added:
            continue
        if "def " not in line:
            continue
        for m in re.finditer(r"(\b\w+)(\s*=\s*)(True|False|None)\b", line):
            candidates.append((lineno, line, m))
    if not candidates:
        return None
    lineno, line, m = rng.choice(candidates)
    old = m.group(3)
    mapping = {"True": "False", "False": "True", "None": "''"}
    new = mapping[old]
    new_line = line[: m.start(3)] + new + line[m.end(3) :]
    return Mutation(
        file="",
        line=lineno,
        bug_type="wrong_default",
        description=f"Changed default {old} to {new}",
        original=line.rstrip("\n"),
        mutated=new_line.rstrip("\n"),
    )


def try_swallowed_exception(source: str, added: set[int], rng: random.Random) -> Mutation | None:
    lines = source.splitlines(keepends=True)
    candidates = []
    for i, line in enumerate(lines):
        lineno = i + 1
        if lineno not in added:
            continue
        if re.match(r"\s*raise\b", line):
            # Prefer raises inside except blocks: look upward for except
            for j in range(i - 1, max(-1, i - 12), -1):
                if re.match(r"\s*except\b", lines[j]):
                    candidates.append((lineno, line))
                    break
    if not candidates:
        return None
    lineno, line = rng.choice(candidates)
    indent = re.match(r"\s*", line).group(0)
    new_line = f"{indent}pass  # BUG: swallowed exception\n"
    if line.endswith("\n") is False:
        new_line = new_line.rstrip("\n")
    return Mutation(
        file="",
        line=lineno,
        bug_type="swallowed_exception",
        description="Replaced raise in except-handler with pass",
        original=line.rstrip("\n"),
        mutated=new_line.rstrip("\n"),
    )


def try_missing_none_check(source: str, added: set[int], rng: random.Random) -> Mutation | None:
    lines = source.splitlines(keepends=True)
    candidates = []
    for i, line in enumerate(lines):
        lineno = i + 1
        if lineno not in added:
            continue
        if re.search(r"\bif\s+.+\s+is\s+None\b", line) or re.search(
            r"\bif\s+.+\s+is\s+not\s+None\b", line
        ):
            # Need a following indented body to flatten
            if i + 1 < len(lines) and len(re.match(r"\s*", lines[i + 1]).group(0)) > len(
                re.match(r"\s*", line).group(0)
            ):
                candidates.append(lineno)
    if not candidates:
        return None
    lineno = rng.choice(candidates)
    line = lines[lineno - 1]
    indent = re.match(r"\s*", line).group(0)
    # Comment out the guard; leave body (slightly wrong indent is ok for a bug)
    new_line = f"{indent}# BUG: removed None check: {line.strip()}\n"
    return Mutation(
        file="",
        line=lineno,
        bug_type="missing_none_check",
        description="Removed a None-check guard (commented out)",
        original=line.rstrip("\n"),
        mutated=new_line.rstrip("\n"),
    )


def try_wrong_variable(source: str, added: set[int], rng: random.Random) -> Mutation | None:
    """Swap one local name with another name that appears nearby (AST-based)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    lines = source.splitlines(keepends=True)
    # Collect simple Name loads on added lines, and other names in the same function
    class Collector(ast.NodeVisitor):
        def __init__(self):
            self.func_names: dict[str, set[str]] = {}
            self.loads_on_added: list[tuple[int, str, str]] = []  # line, name, func
            self._func = "<module>"

        def visit_FunctionDef(self, node):
            prev = self._func
            self._func = node.name
            self.func_names.setdefault(node.name, set())
            for arg in node.args.args:
                self.func_names[node.name].add(arg.arg)
            self.generic_visit(node)
            self._func = prev

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Name(self, node):
            if isinstance(node.ctx, ast.Store):
                self.func_names.setdefault(self._func, set()).add(node.id)
            if isinstance(node.ctx, ast.Load) and node.lineno in added:
                if not node.id.startswith("__"):
                    self.loads_on_added.append((node.lineno, node.id, self._func))
            self.generic_visit(node)

    c = Collector()
    c.visit(tree)
    candidates = []
    for lineno, name, func in c.loads_on_added:
        others = [n for n in c.func_names.get(func, set()) if n != name and len(n) > 1]
        # Prefer similarly typed short names
        others = [n for n in others if not n.startswith("__")]
        if not others:
            continue
        candidates.append((lineno, name, others))
    if not candidates:
        return None
    lineno, name, others = rng.choice(candidates)
    replacement = rng.choice(sorted(others))
    line = lines[lineno - 1]
    # Replace as a whole word, first occurrence
    new_line, n = re.subn(rf"\b{re.escape(name)}\b", replacement, line, count=1)
    if n != 1 or new_line == line:
        return None
    return Mutation(
        file="",
        line=lineno,
        bug_type="wrong_variable",
        description=f"Replaced variable {name!r} with {replacement!r}",
        original=line.rstrip("\n"),
        mutated=new_line.rstrip("\n"),
    )


MUTATORS = [
    try_swallowed_exception,
    try_missing_none_check,
    try_inverted_condition,
    try_off_by_one,
    try_wrong_default,
    try_wrong_variable,
]


def apply_mutation(source: str, mut: Mutation) -> str:
    lines = source.splitlines(keepends=True)
    idx = mut.line - 1
    ending = "\n" if lines[idx].endswith("\n") else ""
    lines[idx] = mut.mutated + ending
    return "".join(lines)


def make_unified_diff(old: str, new: str, path: str) -> str:
    import difflib

    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_lines, new_lines, fromfile=f"a/{path}", tofile=f"b/{path}"
    )
    return "".join(diff)


def seed_one(pr_dir: Path, rng: random.Random, clean: bool) -> dict:
    meta = json.loads((pr_dir / "meta.json").read_text())
    slug = meta["slug"]

    if clean:
        gt = {
            "slug": slug,
            "clean": True,
            "bug_type": "clean",
            "file": None,
            "line": None,
            "description": "Clean control: no planted bug",
            "needs_manual": False,
        }
        (pr_dir / "ground_truth.json").write_text(json.dumps(gt, indent=2) + "\n")
        # Copy head_files to mutated/ unchanged so the runner can always use mutated/
        mutated_root = pr_dir / "mutated"
        if mutated_root.exists():
            shutil.rmtree(mutated_root)
        shutil.copytree(pr_dir / "head_files", mutated_root)
        (pr_dir / "mutated.diff").write_text("")
        return gt

    candidates = package_py_candidates(pr_dir)
    if not candidates:
        gt = {
            "slug": slug,
            "clean": False,
            "bug_type": None,
            "file": None,
            "line": None,
            "description": "No mutable .py added lines found",
            "needs_manual": True,
        }
        (pr_dir / "ground_truth.json").write_text(json.dumps(gt, indent=2) + "\n")
        return gt

    # Prefer a bug type chosen for this PR, then fall back through the rest.
    files_order = candidates[:]
    rng.shuffle(files_order)
    preferred = rng.choice(MUTATORS)
    mutators = [preferred] + [m for m in MUTATORS if m is not preferred]
    rng.shuffle(mutators[1:])  # keep preferred first, shuffle fallbacks

    last_error = None
    for head_path, added, fmeta in files_order:
        source = head_path.read_text(encoding="utf-8", errors="replace")
        rel = fmeta["filename"]
        for mutator in mutators:
            try:
                mut = mutator(source, added, rng)
            except Exception as exc:  # noqa: BLE001
                last_error = f"{mutator.__name__}: {exc}"
                continue
            if mut is None:
                continue
            mut.file = rel
            new_source = apply_mutation(source, mut)
            # Basic sanity: still parses as Python (soft check)
            try:
                ast.parse(new_source)
            except SyntaxError:
                continue
            mutated_root = pr_dir / "mutated"
            if mutated_root.exists():
                shutil.rmtree(mutated_root)
            shutil.copytree(pr_dir / "head_files", mutated_root)
            dest = mutated_root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(new_source)
            (pr_dir / "mutated.diff").write_text(make_unified_diff(source, new_source, rel))
            gt = {
                "slug": slug,
                "clean": False,
                "bug_type": mut.bug_type,
                "file": mut.file,
                "line": mut.line,
                "description": mut.description,
                "original_line": mut.original,
                "mutated_line": mut.mutated,
                "needs_manual": False,
            }
            (pr_dir / "ground_truth.json").write_text(json.dumps(gt, indent=2) + "\n")
            return gt

    gt = {
        "slug": slug,
        "clean": False,
        "bug_type": None,
        "file": None,
        "line": None,
        "description": f"Auto-seed failed. Last error: {last_error}",
        "needs_manual": True,
    }
    (pr_dir / "ground_truth.json").write_text(json.dumps(gt, indent=2) + "\n")
    return gt


def pr_sort_key(pr_dir: Path) -> str:
    return pr_dir.name


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prs", type=Path, default=ROOT / "data" / "prs")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--clean-count",
        type=int,
        default=20,
        help="How many PRs to leave as clean controls (default 20 across all)",
    )
    parser.add_argument(
        "--only",
        nargs="*",
        help="Optional list of slug prefixes/names to process",
    )
    args = parser.parse_args()

    pr_dirs = sorted(
        [p for p in args.prs.iterdir() if p.is_dir() and (p / "meta.json").exists()],
        key=pr_sort_key,
    )
    if args.only:
        pr_dirs = [
            p
            for p in pr_dirs
            if p.name in args.only or any(p.name.startswith(x) for x in args.only)
        ]
    if not pr_dirs:
        print(f"No PRs found under {args.prs}. Run scripts/fetch_prs.py first.")
        return 1

    rng = random.Random(args.seed)
    # Deterministic choice of which PRs are clean controls
    indices = list(range(len(pr_dirs)))
    rng.shuffle(indices)
    clean_n = min(args.clean_count, len(pr_dirs) // 2)  # never more than half
    # Prefer to spread cleans across repos: take every other after shuffle
    clean_set = set(indices[:clean_n])

    clean_dirs = {pr_dirs[j] for j in indices[:clean_n]}
    stats = {"seeded": 0, "clean": 0, "manual": 0, "by_type": {}}

    print(f"Seeding {len(pr_dirs)} PRs (seed={args.seed}, clean_controls={len(clean_dirs)})")
    for pr_dir in pr_dirs:
        clean = pr_dir in clean_dirs
        # Per-PR RNG derived from global seed + slug so order is stable
        pr_rng = random.Random(
            int(hashlib.sha256(f"{args.seed}:{pr_dir.name}".encode()).hexdigest()[:16], 16)
        )
        gt = seed_one(pr_dir, pr_rng, clean=clean)
        if gt.get("clean"):
            stats["clean"] += 1
            flag = "CLEAN"
        elif gt.get("needs_manual"):
            stats["manual"] += 1
            flag = "MANUAL"
        else:
            stats["seeded"] += 1
            stats["by_type"][gt["bug_type"]] = stats["by_type"].get(gt["bug_type"], 0) + 1
            flag = gt["bug_type"]
        print(f"  {flag:20} {pr_dir.name}")

    print()
    print("Summary:")
    print(f"  auto-seeded: {stats['seeded']}")
    print(f"  clean controls: {stats['clean']}")
    print(f"  needs manual: {stats['manual']}")
    if stats["by_type"]:
        print("  by type:", ", ".join(f"{k}={v}" for k, v in sorted(stats["by_type"].items())))
    if stats["manual"]:
        print()
        print("Some PRs need manual planting. See scripts/manual_plant_helper.md")
        print("Typical auto-seed success on httpx/click is about 80 to 95%.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
