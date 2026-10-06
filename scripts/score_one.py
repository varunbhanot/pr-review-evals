#!/usr/bin/env python3
"""Score one review.json against a private ground_truth.json.

Hit rule (seeded bugs): same file AND abs(finding.line - truth.line) <= 3.
Clean controls: fail if any finding has severity blocker/major.

Ground truth lives OUTSIDE the public repo by default:
  ../pr-review-evals-answers/<slug>/ground_truth.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ANSWERS = ROOT.parent / "pr-review-evals-answers"


def score(truth: dict, review: dict, line_slop: int = 3) -> dict:
    findings = review.get("findings") or []
    if truth.get("clean"):
        false_alarms = [
            f
            for f in findings
            if (f.get("severity") or "").lower() in {"blocker", "major"}
        ]
        return {
            "slug": truth.get("slug"),
            "clean": True,
            "pass": len(false_alarms) == 0,
            "false_alarm_count": len(false_alarms),
            "finding_count": len(findings),
            "matched_finding": None,
            "reason": "clean control: no blocker/major findings expected",
        }

    target_file = truth.get("file")
    target_line = truth.get("line")
    if not target_file or not target_line:
        return {
            "slug": truth.get("slug"),
            "clean": False,
            "pass": False,
            "reason": "ground truth missing file/line",
            "finding_count": len(findings),
            "matched_finding": None,
        }

    matched = None
    for f in findings:
        f_file = (f.get("file") or "").lstrip("./")
        t_file = target_file.lstrip("./")
        if f_file != t_file and Path(f_file).name != Path(t_file).name:
            if not (f_file.endswith(t_file) or t_file.endswith(f_file)):
                continue
        try:
            f_line = int(f.get("line"))
        except (TypeError, ValueError):
            continue
        if abs(f_line - int(target_line)) <= line_slop:
            matched = f
            break

    return {
        "slug": truth.get("slug"),
        "clean": False,
        "pass": matched is not None,
        "bug_type": truth.get("bug_type"),
        "truth_file": target_file,
        "truth_line": target_line,
        "finding_count": len(findings),
        "matched_finding": matched,
        "reason": "hit within +/-3 lines" if matched else "no finding near planted bug",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr", required=True, help="PR slug")
    parser.add_argument("--review", required=True, type=Path, help="path to review.json")
    parser.add_argument(
        "--answers-dir",
        type=Path,
        default=DEFAULT_ANSWERS,
        help="private answers directory (default: ../pr-review-evals-answers)",
    )
    parser.add_argument("--line-slop", type=int, default=3)
    args = parser.parse_args()

    truth_path = args.answers_dir / args.pr / "ground_truth.json"
    if not truth_path.exists():
        print(f"Missing {truth_path}", file=sys.stderr)
        print(
            "Answers must stay outside the public repo. "
            "Pass --answers-dir if yours lives elsewhere.",
            file=sys.stderr,
        )
        return 1
    if not args.review.exists():
        print(f"Missing {args.review}", file=sys.stderr)
        return 1

    truth = json.loads(truth_path.read_text())
    review = json.loads(args.review.read_text())
    result = score(truth, review, line_slop=args.line_slop)

    out = args.review.with_name("score.json") if args.review.name == "review.json" else Path(
        str(args.review) + ".score.json"
    )
    out.write_text(json.dumps(result, indent=2) + "\n")

    # Never write score next to public PR inputs
    private_score = args.answers_dir / args.pr / "last_score.json"
    private_score.parent.mkdir(parents=True, exist_ok=True)
    private_score.write_text(json.dumps(result, indent=2) + "\n")

    status = "PASS" if result.get("pass") else "FAIL"
    if result.get("clean"):
        print(
            f"[{status}] {args.pr} clean-control "
            f"false_alarms={result.get('false_alarm_count')} "
            f"findings={result.get('finding_count')}"
        )
    else:
        print(
            f"[{status}] {args.pr} bug={result.get('bug_type')} "
            f"truth={result.get('truth_file')}:{result.get('truth_line')} "
            f"findings={result.get('finding_count')} "
            f"({result.get('reason')})"
        )
    print(f"Wrote {out}")
    print(f"Wrote private {private_score}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
