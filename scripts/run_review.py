#!/usr/bin/env python3
"""Run one PR review headless with local Claude Code (optional path).

Preferred path for Varun: cloud Claude Code. See CLOUD-CLAUDE-CODE.md.

This local runner only exposes reviewer-safe inputs:
  - data/prs/<slug>/meta.json  (title, body, url, SHAs)
  - data/prs/<slug>/review_input.diff
  - data/prs/<slug>/files/     (working tree overlay)

It never reads ground_truth, mutated.diff, diff.patch, or head_files.

Verified Claude flags (claude --help, 6 Oct 2026):
  -p / --print
  --output-format json
  --json-schema
  --tools Read,Glob,Grep
  --permission-mode dontAsk
  --permission-prompts none
  --system-prompt
  --max-budget-usd
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPOS_DIR = ROOT / "data" / "repos"
DEFAULT_ANSWERS = ROOT.parent / "pr-review-evals-answers"


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, text=True, capture_output=True, **kwargs)


def ensure_clone(owner: str, repo: str) -> Path:
    dest = REPOS_DIR / f"{owner}-{repo}"
    if (dest / ".git").exists():
        run(["git", "-C", str(dest), "fetch", "--all", "--tags"])
        return dest
    REPOS_DIR.mkdir(parents=True, exist_ok=True)
    url = f"https://github.com/{owner}/{repo}.git"
    print(f"Cloning {url} into {dest} (one-time)...")
    proc = run(["git", "clone", url, str(dest)])
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr)
    return dest


def prepare_worktree(clone: Path, head_sha: str, files_dir: Path, work: Path) -> None:
    if work.exists():
        run(["git", "-C", str(clone), "worktree", "remove", "--force", str(work)])
        if work.exists():
            shutil.rmtree(work)
    proc = run(["git", "-C", str(clone), "worktree", "add", "--detach", str(work), head_sha])
    if proc.returncode != 0:
        run(["git", "-C", str(clone), "fetch", "origin", head_sha])
        proc = run(["git", "-C", str(clone), "worktree", "add", "--detach", str(work), head_sha])
        if proc.returncode != 0:
            raise RuntimeError(f"worktree add failed:\n{proc.stderr}")
    for src in files_dir.rglob("*"):
        if src.is_file():
            rel = src.relative_to(files_dir)
            dest = work / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)


def build_user_prompt(meta: dict, review_diff: str) -> str:
    body = (meta.get("body") or "").strip()
    if len(body) > 3000:
        body = body[:3000] + "\n...[truncated]..."
    if len(review_diff) > 80000:
        review_diff = review_diff[:80000] + "\n...[diff truncated]..."
    return f"""Review the following pull request.

## PR metadata
- Repo: {meta['owner']}/{meta['repo']}
- Number: #{meta['number']}
- Title: {meta['title']}
- Author: {meta.get('author')}
- URL: {meta.get('url')}
- Base SHA: {meta.get('base_sha')}
- Head SHA: {meta.get('head_sha')}

## PR description
{body or '(empty)'}

## Unified diff under review
```diff
{review_diff}
```

The working tree matches this diff. You may Read/Glob/Grep nearby code.
Return the JSON review object now.
"""


def extract_review(cli_json: dict) -> dict:
    if isinstance(cli_json.get("structured_output"), dict):
        return cli_json["structured_output"]
    result = cli_json.get("result")
    if isinstance(result, dict):
        return result
    if isinstance(result, str):
        text = result.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        return json.loads(text)
    raise ValueError("Could not find review JSON in Claude CLI output")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr", required=True, help="PR slug, e.g. encode-httpx-2278")
    parser.add_argument("--model", default=None)
    parser.add_argument("--budget", type=float, default=1.0)
    parser.add_argument("--keep-worktree", action="store_true")
    parser.add_argument(
        "--answers-dir",
        type=Path,
        default=DEFAULT_ANSWERS,
        help="private answers dir for optional auto-score (never sent to the model)",
    )
    parser.add_argument("--skip-score", action="store_true")
    args = parser.parse_args()

    pr_dir = ROOT / "data" / "prs" / args.pr
    for required in ("meta.json", "review_input.diff", "files"):
        path = pr_dir / required
        if not path.exists():
            print(f"Missing {path}", file=sys.stderr)
            return 1

    if shutil.which("claude") is None:
        print("ERROR: `claude` not on PATH. Prefer CLOUD-CLAUDE-CODE.md.", file=sys.stderr)
        return 1

    meta = json.loads((pr_dir / "meta.json").read_text())
    review_diff = (pr_dir / "review_input.diff").read_text()
    system_prompt = (ROOT / "prompts" / "reviewer.md").read_text()
    schema = (ROOT / "prompts" / "review_schema.json").read_text().strip()

    clone = ensure_clone(meta["owner"], meta["repo"])
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    work = ROOT / "data" / "worktrees" / f"{args.pr}-{run_id}"
    work.parent.mkdir(parents=True, exist_ok=True)

    print(f"Preparing worktree at {meta['head_sha'][:10]} ...")
    prepare_worktree(clone, meta["head_sha"], pr_dir / "files", work)

    user_prompt = build_user_prompt(meta, review_diff)
    out_dir = ROOT / "traces" / args.pr / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "user_prompt.md").write_text(user_prompt)
    (out_dir / "meta.json").write_text(
        json.dumps({"run_id": run_id, "pr": args.pr, "model": args.model}, indent=2) + "\n"
    )

    cmd = [
        "claude",
        "-p",
        user_prompt,
        "--output-format",
        "json",
        "--json-schema",
        schema,
        "--tools",
        "Read,Glob,Grep",
        "--permission-mode",
        "dontAsk",
        "--permission-prompts",
        "none",
        "--system-prompt",
        system_prompt,
        "--max-budget-usd",
        str(args.budget),
    ]
    if args.model:
        cmd.extend(["--model", args.model])

    print("Running Claude Code headless (read-only tools)...")
    started = time.time()
    proc = subprocess.run(cmd, cwd=str(work), text=True, capture_output=True)
    elapsed = time.time() - started
    (out_dir / "claude_stdout.txt").write_text(proc.stdout)
    (out_dir / "claude_stderr.txt").write_text(proc.stderr)
    (out_dir / "exit_code.txt").write_text(str(proc.returncode) + "\n")

    def cleanup() -> None:
        if not args.keep_worktree:
            run(["git", "-C", str(clone), "worktree", "remove", "--force", str(work)])

    if proc.returncode != 0:
        print(f"Claude exited {proc.returncode}. See {out_dir}/claude_stderr.txt", file=sys.stderr)
        print(proc.stderr[-2000:], file=sys.stderr)
        cleanup()
        return proc.returncode

    try:
        cli_json = json.loads(proc.stdout)
        review = extract_review(cli_json)
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to parse review: {exc}", file=sys.stderr)
        cleanup()
        return 1

    (out_dir / "claude_raw.json").write_text(json.dumps(cli_json, indent=2) + "\n")
    (out_dir / "review.json").write_text(json.dumps(review, indent=2) + "\n")
    usage = {
        "elapsed_s": round(elapsed, 2),
        "total_cost_usd": cli_json.get("total_cost_usd"),
        "usage": cli_json.get("usage"),
        "session_id": cli_json.get("session_id"),
    }
    (out_dir / "usage.json").write_text(json.dumps(usage, indent=2) + "\n")
    print(f"Saved {out_dir}/review.json")
    print(f"Cost: {usage.get('total_cost_usd')}  elapsed: {usage['elapsed_s']}s")
    print(f"Verdict: {review.get('verdict')}  findings: {len(review.get('findings') or [])}")

    if not args.skip_score:
        score_proc = run(
            [
                sys.executable,
                str(ROOT / "scripts" / "score_one.py"),
                "--pr",
                args.pr,
                "--review",
                str(out_dir / "review.json"),
                "--answers-dir",
                str(args.answers_dir),
            ]
        )
        print(score_proc.stdout)
        if score_proc.returncode != 0:
            print(score_proc.stderr, file=sys.stderr)

    cleanup()
    print()
    print("Week 4 one-liners (do not use yet):")
    print('  Codex:  codex exec --json --sandbox read-only "..."')
    print('  OpenCode:  opencode run --format json "..."')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
