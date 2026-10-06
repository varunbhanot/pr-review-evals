# Run one review in cloud Claude Code

This is the primary Week 0 path. Cloud Claude Code (claude.ai/code) clones this repo and acts as the reviewer. Anything committed here is visible to it.

## Before you start

1. Confirm this repo is the public `varunbhanot/pr-review-evals` (or your fork).
2. Pick a slug under `data/prs/`. Suggested first try: `encode-httpx-2278` (small, good starter).
3. Open a new cloud Claude Code session on this repo with your personal account.

## Copy-paste session prompt

Replace `encode-httpx-2278` if you chose another slug. Replace `RUNID` with something like `20261006-a1b2`.

```
You are reviewing one pull request for the pr-review-evals project.

Rules:
1. Read prompts/reviewer.md and follow it.
2. Review only these paths for slug encode-httpx-2278:
   - data/prs/encode-httpx-2278/meta.json
   - data/prs/encode-httpx-2278/review_input.diff
   - data/prs/encode-httpx-2278/files/
3. Do not look up the upstream PR on GitHub or anywhere on the network. Do not fetch by URL or SHA. Do not search the web.
4. Do not read any file named ground_truth.json, mutated.diff, diff.patch, files.json, head_files, or last_score.json. If you see them, stop and tell me.
5. Write a JSON object that matches prompts/review_schema.json.
6. Save it to traces/encode-httpx-2278/RUNID/review.json (create the directories).
7. Create a git branch named review/encode-httpx-2278-RUNID, commit only that review.json (and the traces path), and push the branch. Do not commit anything else. Do not force-push main.

Return a short summary of your verdict and findings after you push.
```

## After the review lands

Tell me (or run locally if you have the private answers checkout):

- the branch name, e.g. `review/encode-httpx-2278-20261006-a1b2`
- the slug

I will:

```bash
git fetch origin review/encode-httpx-2278-RUNID
git checkout origin/review/encode-httpx-2278-RUNID -- traces/encode-httpx-2278/RUNID/review.json
python scripts/score_one.py \
  --pr encode-httpx-2278 \
  --review traces/encode-httpx-2278/RUNID/review.json \
  --answers-dir ../pr-review-evals-answers
```

The answers directory is private and does not live in this repo. Scoring never runs inside the cloud session.

## Known limit

`meta.json` includes the upstream PR URL and base/head SHAs. A reviewer with network access could fetch the original PR and spot the edit by comparison. The session prompt forbids that. When you read traces in Week 1, check whether the model mentioned fetching the upstream PR. If it did, treat that run as contaminated.

## Local alternative

If you prefer a local headless run instead of cloud:

```bash
python scripts/run_review.py --pr encode-httpx-2278 --budget 1.0
```

That path also scores automatically when `../pr-review-evals-answers` is present. See README-WEEK0.md.
