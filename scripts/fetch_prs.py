#!/usr/bin/env python3
"""Fetch small/medium merged PRs from encode/httpx and pallets/click.

Saves each PR under data/prs/<owner>-<repo>-<number>/ with:
  meta.json   - metadata (SHAs, author, sizes, title, body)
  files.json  - list of changed files with patches
  diff.patch  - unified diff (PR head vs base)
  head_files/ - copies of changed .py source files at the PR head SHA

Uses the GitHub CLI (`gh`) so auth is whatever `gh auth login` set up.
No Deutsche Telekom / DTDL content. Public open-source only.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPOS = ["encode/httpx", "pallets/click"]
BOT_LOGINS = {
    "dependabot",
    "dependabot[bot]",
    "renovate",
    "renovate[bot]",
    "pre-commit-ci",
    "pre-commit-ci[bot]",
    "github-actions",
    "github-actions[bot]",
    "imgbot",
    "imgbot[bot]",
}
DOC_ONLY_EXTS = {".md", ".rst", ".txt", ".adoc"}
DOC_PREFIXES = ("docs/", "doc/", ".github/", "examples/")
SKIP_TITLE_RE = re.compile(
    r"(bump |chore:|docs?:|documentation|typo|spell|readme|changelog|"
    r"release |version \d|merge .*into|start \d|ci:|dependabot|"
    r"faq entry|third.party|upgrade python (formatter|type)|"
    r"update dependencies|sponsorship)",
    re.I,
)


def run_gh(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    cmd = ["gh"] + args
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"gh {' '.join(args)} failed ({proc.returncode}):\n{proc.stderr.strip()}"
        )
    return proc


def list_merged(owner: str, repo: str, pages: int = 4, page_size: int = 50) -> list[dict]:
    """Recent merged PRs via GraphQL (includes additions/deletions)."""
    nodes: list[dict] = []
    cursor = None
    for _ in range(pages):
        after_line = f'after: "{cursor}"' if cursor else ""
        query = f"""
        query {{
          repository(owner: "{owner}", name: "{repo}") {{
            pullRequests(
              states: MERGED
              first: {page_size}
              orderBy: {{field: UPDATED_AT, direction: DESC}}
              {after_line}
            ) {{
              pageInfo {{ hasNextPage endCursor }}
              nodes {{
                number
                title
                body
                additions
                deletions
                changedFiles
                mergedAt
                url
                author {{ login }}
                baseRefOid
                headRefOid
                mergeCommit {{ oid }}
              }}
            }}
          }}
        }}
        """
        proc = run_gh(["api", "graphql", "-f", f"query={query}"])
        data = json.loads(proc.stdout)
        if "errors" in data:
            raise RuntimeError(f"GraphQL errors: {data['errors']}")
        pr_conn = data["data"]["repository"]["pullRequests"]
        nodes.extend(pr_conn["nodes"])
        if not pr_conn["pageInfo"]["hasNextPage"]:
            break
        cursor = pr_conn["pageInfo"]["endCursor"]
    return nodes


def get_files(owner: str, repo: str, number: int) -> list[dict]:
    proc = run_gh(
        [
            "api",
            f"repos/{owner}/{repo}/pulls/{number}/files",
            "--paginate",
        ]
    )
    # --paginate may concatenate JSON arrays; gh usually returns one array per page
    text = proc.stdout.strip()
    if not text:
        return []
    # Handle concatenated arrays from pagination: ][
    text = text.replace("][", ",")
    files = json.loads(text)
    return files


def is_bot(login: str | None) -> bool:
    if not login:
        return True
    return login.lower() in BOT_LOGINS or login.endswith("[bot]")


def py_source_files(files: list[dict]) -> list[dict]:
    out = []
    for f in files:
        name = f.get("filename") or ""
        if not name.endswith(".py"):
            continue
        # Prefer package/source files; still allow tests (useful for some mutations)
        out.append(f)
    return out


def is_docs_or_deps_only(files: list[dict], title: str) -> bool:
    if SKIP_TITLE_RE.search(title or ""):
        return True
    if not files:
        return True
    non_doc = []
    for f in files:
        name = f.get("filename") or ""
        lower = name.lower()
        if any(lower.startswith(p) for p in DOC_PREFIXES):
            continue
        if Path(name).suffix.lower() in DOC_ONLY_EXTS:
            continue
        if Path(name).name in {
            "requirements.txt",
            "requirements.in",
            "poetry.lock",
            "Pipfile.lock",
            "uv.lock",
            "package-lock.json",
            "yarn.lock",
            "pnpm-lock.yaml",
        }:
            continue
        if lower.endswith((".yml", ".yaml")) and ".github/" in lower:
            continue
        non_doc.append(f)
    if not non_doc:
        return True
    # Must touch at least one .py file
    if not any((f.get("filename") or "").endswith(".py") for f in non_doc):
        return True
    return False


def build_diff(files: list[dict]) -> str:
    parts = []
    for f in files:
        patch = f.get("patch")
        if not patch:
            # binary or too large; note it
            parts.append(f"diff --git a/{f['filename']} b/{f['filename']}\n")
            parts.append(f"# (no patch available for {f['filename']}, status={f.get('status')})\n")
            continue
        status = f.get("status") or "modified"
        if status == "added":
            parts.append(f"diff --git a/{f['filename']} b/{f['filename']}\n")
            parts.append(f"new file mode 100644\n")
            parts.append(f"--- /dev/null\n+++ b/{f['filename']}\n")
        elif status == "removed":
            parts.append(f"diff --git a/{f['filename']} b/{f['filename']}\n")
            parts.append(f"deleted file mode 100644\n")
            parts.append(f"--- a/{f['filename']}\n+++ /dev/null\n")
        else:
            parts.append(f"diff --git a/{f['filename']} b/{f['filename']}\n")
            parts.append(f"--- a/{f['filename']}\n+++ b/{f['filename']}\n")
        parts.append(patch)
        if not patch.endswith("\n"):
            parts.append("\n")
    return "".join(parts)


def fetch_raw_at_ref(owner: str, repo: str, path: str, ref: str) -> str | None:
    """Fetch file contents at a commit SHA via the contents API (base64)."""
    import base64

    proc = run_gh(
        [
            "api",
            f"repos/{owner}/{repo}/contents/{path}?ref={ref}",
            "-H",
            "Accept: application/vnd.github+json",
        ],
        check=False,
    )
    if proc.returncode != 0:
        return None
    data = json.loads(proc.stdout)
    if data.get("encoding") == "base64" and data.get("content"):
        return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    if isinstance(data.get("content"), str) and not data.get("encoding"):
        return data["content"]
    return None


def select_prs(
    owner: str,
    repo: str,
    target: int,
    max_changed_lines: int,
) -> list[tuple[dict, list[dict]]]:
    candidates = list_merged(owner, repo)
    selected: list[tuple[dict, list[dict]]] = []
    skipped = {"bot": 0, "size": 0, "docs": 0, "no_py_patch": 0, "other": 0}

    for pr in candidates:
        if len(selected) >= target:
            break
        login = (pr.get("author") or {}).get("login")
        if is_bot(login):
            skipped["bot"] += 1
            continue
        additions = pr.get("additions") or 0
        deletions = pr.get("deletions") or 0
        if additions + deletions == 0 or additions + deletions > max_changed_lines:
            skipped["size"] += 1
            continue
        files = get_files(owner, repo, pr["number"])
        if is_docs_or_deps_only(files, pr.get("title") or ""):
            skipped["docs"] += 1
            continue
        # Need at least one .py file with a usable patch and added lines
        py_files = [
            f
            for f in py_source_files(files)
            if f.get("patch") and "+" in (f.get("patch") or "")
        ]
        # Prefer non-test package files, but accept tests if that's all we have
        package_py = [
            f
            for f in py_files
            if not any(
                part in {"tests", "test", "docs", "examples", "scripts"}
                for part in Path(f["filename"]).parts
            )
        ]
        if not package_py and not py_files:
            skipped["no_py_patch"] += 1
            continue
        selected.append((pr, files))

    print(
        f"  scanned {len(candidates)} merged PRs; selected {len(selected)}; "
        f"skipped bot={skipped['bot']} size={skipped['size']} "
        f"docs/deps={skipped['docs']} no_py_patch={skipped['no_py_patch']}"
    )
    return selected


def save_pr(owner: str, repo: str, pr: dict, files: list[dict], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    head_sha = pr.get("headRefOid")
    base_sha = pr.get("baseRefOid")
    meta = {
        "owner": owner,
        "repo": repo,
        "number": pr["number"],
        "title": pr.get("title"),
        "body": pr.get("body") or "",
        "author": (pr.get("author") or {}).get("login"),
        "url": pr.get("url"),
        "additions": pr.get("additions"),
        "deletions": pr.get("deletions"),
        "changed_files": pr.get("changedFiles"),
        "merged_at": pr.get("mergedAt"),
        "base_sha": base_sha,
        "head_sha": head_sha,
        "merge_commit_sha": (pr.get("mergeCommit") or {}).get("oid"),
        "slug": f"{owner}-{repo}-{pr['number']}",
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    # Keep patches in files.json (needed for seeding)
    slim_files = [
        {
            "filename": f.get("filename"),
            "status": f.get("status"),
            "additions": f.get("additions"),
            "deletions": f.get("deletions"),
            "patch": f.get("patch"),
            "sha": f.get("sha"),
        }
        for f in files
    ]
    (out_dir / "files.json").write_text(json.dumps(slim_files, indent=2) + "\n")
    (out_dir / "diff.patch").write_text(build_diff(files))

    # Download changed .py files at head for seeding / review
    head_dir = out_dir / "head_files"
    head_dir.mkdir(exist_ok=True)
    for f in py_source_files(files):
        if f.get("status") == "removed":
            continue
        path = f["filename"]
        content = fetch_raw_at_ref(owner, repo, path, head_sha)
        if content is None:
            print(f"    warn: could not fetch {path}@{head_sha[:7]}")
            continue
        dest = head_dir / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repos",
        nargs="+",
        default=DEFAULT_REPOS,
        help="owner/repo list (default: encode/httpx pallets/click)",
    )
    parser.add_argument("--per-repo", type=int, default=20, help="PRs to keep per repo")
    parser.add_argument(
        "--max-lines",
        type=int,
        default=400,
        help="max additions+deletions (default 400)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "data" / "prs",
        help="output directory",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="re-fetch even if the PR folder already exists",
    )
    args = parser.parse_args()

    # Sanity: gh auth
    auth = run_gh(["auth", "status"], check=False)
    if auth.returncode != 0:
        print("ERROR: gh is not authenticated. Run: gh auth login", file=sys.stderr)
        return 1
    print(auth.stderr.strip() or auth.stdout.strip())
    print()

    args.out.mkdir(parents=True, exist_ok=True)
    summary = []

    for full in args.repos:
        owner, repo = full.split("/", 1)
        print(f"== {owner}/{repo}")
        selected = select_prs(owner, repo, args.per_repo, args.max_lines)
        saved = 0
        for pr, files in selected:
            slug = f"{owner}-{repo}-{pr['number']}"
            out_dir = args.out / slug
            if out_dir.exists() and not args.force:
                print(f"  skip existing {slug}")
                saved += 1
                continue
            print(
                f"  fetch #{pr['number']} +{pr['additions']}/-{pr['deletions']} "
                f"{pr['title'][:60]!r}"
            )
            save_pr(owner, repo, pr, files, out_dir)
            saved += 1
        summary.append((full, saved, len(selected)))
        print()

    print("Summary:")
    for full, saved, n in summary:
        print(f"  {full}: saved {saved} (selected {n})")
    print(f"Output: {args.out}")
    print()
    print("What good looks like: about 20 folders per repo under data/prs/,")
    print("each with meta.json, files.json, diff.patch, and head_files/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
