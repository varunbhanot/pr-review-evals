#!/usr/bin/env python3
"""Score a folder (or extracted branch) of review.json files against private answers.

Prints recall, false-alarm rate, and per-bug-type recall as a markdown table.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from score_one import score  # noqa: E402


def find_reviews(reviews_root: Path) -> dict[str, Path]:
    """Map slug -> review.json path. Accepts flat or traces/<slug>/**/review.json."""
    found: dict[str, Path] = {}
    if not reviews_root.exists():
        return found
    # Flat: reviews_root/<slug>/review.json
    for p in reviews_root.glob("*/review.json"):
        found[p.parent.name] = p
    # Nested traces layout
    for p in reviews_root.glob("**/review.json"):
        parts = p.relative_to(reviews_root).parts
        if len(parts) >= 2:
            slug = parts[0]
            # Prefer deeper / later paths only if not already set; allow override
            found.setdefault(slug, p)
            # If path contains a run id after slug, prefer it when flat missing
            if slug not in found or found[slug] == p:
                found[slug] = p
    # Also: reviews_root itself is traces/
    for p in reviews_root.glob("*/*/review.json"):
        found[p.parent.parent.name] = p
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reviews",
        type=Path,
        required=True,
        help="Folder of reviews: either <slug>/review.json or traces/<slug>/<run>/review.json",
    )
    parser.add_argument(
        "--answers-dir",
        type=Path,
        required=True,
        help="Private answers directory",
    )
    parser.add_argument("--line-slop", type=int, default=3)
    parser.add_argument("-o", "--output", type=Path, help="Optional markdown output path")
    args = parser.parse_args()

    reviews = find_reviews(args.reviews)
    if not reviews:
        # try treating --reviews as a traces tree checked out from a branch
        reviews = find_reviews(args.reviews)

    answer_slugs = sorted(
        p.name
        for p in args.answers_dir.iterdir()
        if p.is_dir() and (p / "ground_truth.json").exists()
    )
    if not answer_slugs:
        print(f"No answers in {args.answers_dir}", file=sys.stderr)
        return 1

    seeded_results = []
    clean_results = []
    missing = []

    for slug in answer_slugs:
        truth = json.loads((args.answers_dir / slug / "ground_truth.json").read_text())
        if truth.get("needs_manual"):
            continue
        rev_path = reviews.get(slug)
        if not rev_path:
            missing.append(slug)
            continue
        review = json.loads(rev_path.read_text())
        result = score(truth, review, line_slop=args.line_slop)
        result["slug"] = slug
        if truth.get("clean"):
            clean_results.append(result)
        else:
            result["bug_type"] = truth.get("bug_type")
            seeded_results.append(result)

    seeded_n = len(seeded_results)
    caught = sum(1 for r in seeded_results if r.get("pass"))
    clean_n = len(clean_results)
    false_alarms = [r for r in clean_results if not r.get("pass")]
    fa_n = len(false_alarms)

    by_type: dict[str, list] = defaultdict(list)
    for r in seeded_results:
        by_type[r.get("bug_type") or "unknown"].append(r)

    lines = []
    lines.append("# Eval score summary")
    lines.append("")
    lines.append(f"- Reviews dir: `{args.reviews}`")
    lines.append(f"- Answers dir: `{args.answers_dir}`")
    lines.append(f"- Seeded scored: {seeded_n}  |  Clean scored: {clean_n}  |  Missing reviews: {len(missing)}")
    if missing:
        lines.append(f"- Missing slugs: {', '.join(missing)}")
    lines.append("")
    recall = (caught / seeded_n) if seeded_n else 0.0
    fa_rate = (fa_n / clean_n) if clean_n else 0.0
    lines.append(f"**Recall (planted bugs caught):** {caught}/{seeded_n} = {recall:.0%}")
    lines.append(f"**False-alarm rate (clean controls):** {fa_n}/{clean_n} = {fa_rate:.0%}")
    lines.append("")
    lines.append("## Per-bug-type recall")
    lines.append("")
    lines.append("| Bug type | Caught | Total | Recall |")
    lines.append("|---|---:|---:|---:|")
    for bt in sorted(by_type):
        rs = by_type[bt]
        c = sum(1 for r in rs if r.get("pass"))
        lines.append(f"| {bt} | {c} | {len(rs)} | {c/len(rs):.0%} |")
    lines.append("")
    lines.append("## Seeded detail")
    lines.append("")
    lines.append("| Slug | Bug type | Result |")
    lines.append("|---|---|---|")
    for r in seeded_results:
        lines.append(f"| {r['slug']} | {r.get('bug_type')} | {'PASS' if r.get('pass') else 'FAIL'} |")
    lines.append("")
    lines.append("## Clean false alarms")
    lines.append("")
    if not false_alarms:
        lines.append("None.")
    else:
        lines.append("| Slug | False-alarm findings |")
        lines.append("|---|---:|")
        for r in false_alarms:
            lines.append(f"| {r['slug']} | {r.get('false_alarm_count')} |")

    text = "\n".join(lines) + "\n"
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
        print(f"Wrote {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
