#!/usr/bin/env python3
"""Build review_input.diff from private diff.patch + ground_truth.

Used when regenerating public inputs from the answers directory.
For seeded PRs: replace the single '+' line at ground_truth.line in the
target file with the mutated line. For clean PRs: copy diff.patch as-is.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ANSWERS = ROOT.parent / "pr-review-evals-answers"


def replace_in_file_section(section: str, target_line: int, original: str, mutated: str) -> tuple[str, int]:
    lines = section.splitlines(keepends=True)
    out = []
    new_line = None
    replacements = 0
    meta_prefixes = (
        "+++", "---", "diff ", "index ", "new file", "deleted file",
        "old mode", "new mode", "similarity", "rename ", "copy ", "Binary", "#",
    )
    for line in lines:
        if line.startswith("@@"):
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if m:
                new_line = int(m.group(1))
            out.append(line)
            continue
        if line.startswith(meta_prefixes):
            out.append(line)
            continue
        if new_line is None:
            out.append(line)
            continue
        if line.startswith("+"):
            content = line[1:].rstrip("\n")
            if new_line == target_line:
                ending = "\n" if line.endswith("\n") else ""
                out.append("+" + mutated + ending)
                replacements += 1
            else:
                out.append(line)
            new_line += 1
        elif line.startswith("-"):
            out.append(line)
        else:
            out.append(line)
            new_line += 1
    return "".join(out), replacements


def split_file_sections(diff_text: str) -> list[tuple[str | None, str]]:
    lines = diff_text.splitlines(keepends=True)
    sections: list[tuple[str | None, str]] = []
    current_name = None
    buf: list[str] = []
    for line in lines:
        if line.startswith("diff --git "):
            if buf:
                sections.append((current_name, "".join(buf)))
            buf = [line]
            m = re.search(r"diff --git a/(.+?) b/(.+)$", line.rstrip("\n"))
            current_name = m.group(2) if m else None
        else:
            buf.append(line)
    if buf:
        sections.append((current_name, "".join(buf)))
    return sections


def build_one(answers_slug: Path, out_diff: Path) -> None:
    gt = json.loads((answers_slug / "ground_truth.json").read_text())
    diff_patch = (answers_slug / "diff.patch").read_text()
    if gt.get("clean"):
        out_diff.write_text(diff_patch)
        return
    if gt.get("needs_manual"):
        raise RuntimeError(f"{answers_slug.name}: needs_manual, skip")
    target_file = gt["file"]
    target_line = int(gt["line"])
    mutated = gt["mutated_line"]
    original = gt["original_line"]
    sections = split_file_sections(diff_patch)
    new_sections = []
    total = 0
    found = False
    for name, sec in sections:
        if name == target_file:
            found = True
            new_sec, n = replace_in_file_section(sec, target_line, original, mutated)
            total += n
            new_sections.append(new_sec)
        else:
            new_sections.append(sec)
    if not found:
        raise RuntimeError(f"{answers_slug.name}: file {target_file} not in diff.patch")
    if total != 1:
        raise RuntimeError(f"{answers_slug.name}: expected 1 replacement, got {total}")
    out_diff.write_text("".join(new_sections))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--answers-dir", type=Path, default=DEFAULT_ANSWERS)
    parser.add_argument("--prs-dir", type=Path, default=ROOT / "data" / "prs")
    parser.add_argument("--slug", help="optional single slug")
    args = parser.parse_args()

    slugs = [args.slug] if args.slug else sorted(
        p.name for p in args.answers_dir.iterdir() if p.is_dir()
    )
    ok = fail = 0
    for slug in slugs:
        ans = args.answers_dir / slug
        if not (ans / "ground_truth.json").exists():
            continue
        gt = json.loads((ans / "ground_truth.json").read_text())
        if gt.get("needs_manual"):
            print(f"skip manual {slug}")
            continue
        out_dir = args.prs_dir / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        try:
            build_one(ans, out_dir / "review_input.diff")
            print(f"ok {slug}")
            ok += 1
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL {slug}: {exc}", file=sys.stderr)
            fail += 1
    print(f"done ok={ok} fail={fail}")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
