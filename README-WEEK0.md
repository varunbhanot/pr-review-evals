# Week 0 guide

Goal: get one PR reviewed end to end, then score it privately.

**Preferred path:** cloud Claude Code. See [CLOUD-CLAUDE-CODE.md](./CLOUD-CLAUDE-CODE.md) (about 20 to 40 min for one review once the repo exists).

This README covers the full local rebuild path (fetch, seed, split answers, local `claude -p`) if you need to regenerate data. About 3 hours the first time.

## Public vs private

| Location | Contents |
|---|---|
| This repo `data/prs/<slug>/` | `meta.json`, `review_input.diff`, `files/` only |
| Sibling dir `../pr-review-evals-answers/<slug>/` (NOT in git) | `ground_truth.json`, `diff.patch`, `mutated.diff`, `head_files/`, `files.json` |

Never commit answer files. `.gitignore` blocks the common names.

## Cloud path (do this first)

1. Open cloud Claude Code on `varunbhanot/pr-review-evals` with your personal account.
2. Paste the session prompt from CLOUD-CLAUDE-CODE.md (start with slug `encode-httpx-2278`).
3. Tell me the branch name. I score it with the private answers dir.

**What good looks like:** a branch `review/<slug>-<run-id>` containing only `traces/<slug>/<run-id>/review.json`.

## Local rebuild path (optional)

### 1. Tools (10 min)

```bash
python3 --version   # 3.11+
gh auth status      # personal account, repo scope
claude --version    # for local alternative only
```

### 2. Fetch PRs (25 to 40 min)

```bash
python scripts/fetch_prs.py --per-repo 20 --max-lines 400
```

Writes raw PR folders under `data/prs/` (includes patches and head files). Those raw artifacts are not reviewer-safe yet.

### 3. Seed bugs (15 to 25 min)

```bash
python scripts/seed_bugs.py --seed 42 --clean-count 20
```

Then move answer keys out and build public diffs:

```bash
# After seeding, keep answers outside git. Example layout:
#   ../pr-review-evals-answers/<slug>/{ground_truth.json,diff.patch,mutated.diff,head_files,files.json}
#   data/prs/<slug>/{meta.json,review_input.diff,files/}
python scripts/make_review_input.py --answers-dir ../pr-review-evals-answers
```

If you are continuing from this kit, answers are already at `/workspace/pr-review-evals-answers` and public inputs are already under `data/prs/`.

**What good looks like:** about 10 seeded + about 20 clean public slugs; each has `review_input.diff` and `files/`; no `ground_truth.json` inside the repo.

### 4. Local headless review (alternative to cloud)

```bash
python scripts/run_review.py --pr encode-httpx-2278 --budget 1.0
```

Flags used (verified against `claude --help`): `-p`, `--output-format json`, `--json-schema`, `--tools Read,Glob,Grep`, `--permission-mode dontAsk`, `--permission-prompts none`, `--system-prompt`, `--max-budget-usd`.

### 5. Score privately

```bash
python scripts/score_one.py \
  --pr encode-httpx-2278 \
  --review traces/encode-httpx-2278/<run-id>/review.json \
  --answers-dir ../pr-review-evals-answers
```

Hit rule: same file, within +/- 3 lines of the private ground truth.

## Safety

- Personal machine / personal cloud account / personal spend.
- No Deutsche Telekom / DTDL content.
- Reviewer must never see answer keys. Grep before every push:
  `git ls-files | grep -E 'ground_truth|mutated.diff|diff.patch|head_files|last_score|files.json'`
- `meta.json` still has the upstream URL and SHAs (known limit). The cloud prompt forbids fetching them.

## Week 4 only

```bash
codex exec --json --sandbox read-only "..."
opencode run --format json "..."
```
