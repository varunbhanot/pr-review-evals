# Run reviews in cloud Claude Code

This is the primary path. Cloud Claude Code (claude.ai/code) clones this repo and acts as the reviewer. Anything committed here is visible to it.

## Before you start

1. Confirm this repo is the public `varunbhanot/pr-review-evals` (or your fork).
2. Prefer **v2** inputs under `data/prs-v2/` (harder set). v1 under `data/prs/` is saturated; see `reports/baseline-v1.md`.
3. Open a new cloud Claude Code session on this repo with your personal account.

## v2 batch prompts (ready to paste)

Use one session per batch. Trace path and branch name both carry the batch id so runs cannot be mixed up.

Each batch has 10 PRs (5 bugged + 5 clean controls, interleaved). Review every slug in the list. Write one `review.json` per slug.

### Batch 1  (branch `review/v2-batch1`)

```
You are reviewing a batch of pull requests for the pr-review-evals project (v2 set).

Batch name: v2-batch1
Branch to create and push: review/v2-batch1

Rules:
1. Read prompts/reviewer.md and follow it for every PR.
2. Review ONLY these v2 slugs (data under data/prs-v2/<slug>/):
   - encode-httpx-3116
   - encode-httpx-3178
   - encode-httpx-3187
   - encode-httpx-3250
   - encode-httpx-3312
   - encode-httpx-3367
   - encode-httpx-3371
   - encode-httpx-3442
   - encode-httpx-3445
   - encode-httpx-3571
3. For each slug, read only:
   - data/prs-v2/<slug>/meta.json
   - data/prs-v2/<slug>/review_input.diff
   - data/prs-v2/<slug>/files/
4. Do not look up the upstream PR on GitHub or anywhere on the network. Do not fetch by URL or SHA. Do not search the web.
5. Do not read any file named ground_truth.json, mutated.diff, diff.patch, files.json, head_files, or last_score.json. If you see them, stop and tell me.
6. Write a JSON object that matches prompts/review_schema.json for each slug.
7. Save each review to traces/<slug>/v2-batch1/review.json (create the directories).
8. Create a git branch named review/v2-batch1, commit only those review.json files under traces/, and push the branch. Do not commit anything else. Do not force-push main.

Return a short per-slug summary of verdict and findings after you push.
```

After it lands:

```bash
git fetch origin review/v2-batch1
git checkout origin/review/v2-batch1 -- traces/
python scripts/score_all.py \
  --reviews traces \
  --answers-dir ../pr-review-evals-answers-v2 \
  -o reports/v2-batch1.md
```

### Batch 2  (branch `review/v2-batch2`)

```
You are reviewing a batch of pull requests for the pr-review-evals project (v2 set).

Batch name: v2-batch2
Branch to create and push: review/v2-batch2

Rules:
1. Read prompts/reviewer.md and follow it for every PR.
2. Review ONLY these v2 slugs (data under data/prs-v2/<slug>/):
   - encode-httpx-3343
   - encode-httpx-3345
   - encode-httpx-3373
   - encode-httpx-3380
   - encode-httpx-3418
   - encode-httpx-3651
   - encode-httpx-3654
   - encode-httpx-3699
   - pallets-click-351
   - pallets-click-3739
3. For each slug, read only:
   - data/prs-v2/<slug>/meta.json
   - data/prs-v2/<slug>/review_input.diff
   - data/prs-v2/<slug>/files/
4. Do not look up the upstream PR on GitHub or anywhere on the network. Do not fetch by URL or SHA. Do not search the web.
5. Do not read any file named ground_truth.json, mutated.diff, diff.patch, files.json, head_files, or last_score.json. If you see them, stop and tell me.
6. Write a JSON object that matches prompts/review_schema.json for each slug.
7. Save each review to traces/<slug>/v2-batch2/review.json (create the directories).
8. Create a git branch named review/v2-batch2, commit only those review.json files under traces/, and push the branch. Do not commit anything else. Do not force-push main.

Return a short per-slug summary of verdict and findings after you push.
```

After it lands:

```bash
git fetch origin review/v2-batch2
git checkout origin/review/v2-batch2 -- traces/
python scripts/score_all.py \
  --reviews traces \
  --answers-dir ../pr-review-evals-answers-v2 \
  -o reports/v2-batch2.md
```

### Batch 3  (branch `review/v2-batch3`)

```
You are reviewing a batch of pull requests for the pr-review-evals project (v2 set).

Batch name: v2-batch3
Branch to create and push: review/v2-batch3

Rules:
1. Read prompts/reviewer.md and follow it for every PR.
2. Review ONLY these v2 slugs (data under data/prs-v2/<slug>/):
   - pallets-click-2775
   - pallets-click-2796
   - pallets-click-2800
   - pallets-click-2829
   - pallets-click-2930
   - pallets-click-3764
   - pallets-click-3767
   - pallets-click-3769
   - pallets-click-3776
   - pallets-click-3780
3. For each slug, read only:
   - data/prs-v2/<slug>/meta.json
   - data/prs-v2/<slug>/review_input.diff
   - data/prs-v2/<slug>/files/
4. Do not look up the upstream PR on GitHub or anywhere on the network. Do not fetch by URL or SHA. Do not search the web.
5. Do not read any file named ground_truth.json, mutated.diff, diff.patch, files.json, head_files, or last_score.json. If you see them, stop and tell me.
6. Write a JSON object that matches prompts/review_schema.json for each slug.
7. Save each review to traces/<slug>/v2-batch3/review.json (create the directories).
8. Create a git branch named review/v2-batch3, commit only those review.json files under traces/, and push the branch. Do not commit anything else. Do not force-push main.

Return a short per-slug summary of verdict and findings after you push.
```

After it lands:

```bash
git fetch origin review/v2-batch3
git checkout origin/review/v2-batch3 -- traces/
python scripts/score_all.py \
  --reviews traces \
  --answers-dir ../pr-review-evals-answers-v2 \
  -o reports/v2-batch3.md
```

### Batch 4  (branch `review/v2-batch4`)

```
You are reviewing a batch of pull requests for the pr-review-evals project (v2 set).

Batch name: v2-batch4
Branch to create and push: review/v2-batch4

Rules:
1. Read prompts/reviewer.md and follow it for every PR.
2. Review ONLY these v2 slugs (data under data/prs-v2/<slug>/):
   - pallets-click-3004
   - pallets-click-3079
   - pallets-click-3152
   - pallets-click-3493
   - pallets-click-3728
   - pallets-click-3805
   - pallets-click-3817
   - pallets-click-3821
   - pallets-click-3858
   - pallets-click-3860
3. For each slug, read only:
   - data/prs-v2/<slug>/meta.json
   - data/prs-v2/<slug>/review_input.diff
   - data/prs-v2/<slug>/files/
4. Do not look up the upstream PR on GitHub or anywhere on the network. Do not fetch by URL or SHA. Do not search the web.
5. Do not read any file named ground_truth.json, mutated.diff, diff.patch, files.json, head_files, or last_score.json. If you see them, stop and tell me.
6. Write a JSON object that matches prompts/review_schema.json for each slug.
7. Save each review to traces/<slug>/v2-batch4/review.json (create the directories).
8. Create a git branch named review/v2-batch4, commit only those review.json files under traces/, and push the branch. Do not commit anything else. Do not force-push main.

Return a short per-slug summary of verdict and findings after you push.
```

After it lands:

```bash
git fetch origin review/v2-batch4
git checkout origin/review/v2-batch4 -- traces/
python scripts/score_all.py \
  --reviews traces \
  --answers-dir ../pr-review-evals-answers-v2 \
  -o reports/v2-batch4.md
```


## Single-PR prompt (v1 or ad-hoc)

Replace `SLUG` and `RUNID`. For v2 use `data/prs-v2/`; for v1 use `data/prs/`.

```
You are reviewing one pull request for the pr-review-evals project.

Rules:
1. Read prompts/reviewer.md and follow it.
2. Review only these paths for slug SLUG:
   - data/prs-v2/SLUG/meta.json
   - data/prs-v2/SLUG/review_input.diff
   - data/prs-v2/SLUG/files/
3. Do not look up the upstream PR on GitHub or anywhere on the network. Do not fetch by URL or SHA. Do not search the web.
4. Do not read any file named ground_truth.json, mutated.diff, diff.patch, files.json, head_files, or last_score.json. If you see them, stop and tell me.
5. Write a JSON object that matches prompts/review_schema.json.
6. Save it to traces/SLUG/RUNID/review.json (create the directories).
7. Create a git branch named review/SLUG-RUNID, commit only that review.json (and the traces path), and push the branch. Do not commit anything else. Do not force-push main.

Return a short summary of your verdict and findings after you push.
```

## Scoring

Answers live outside this repo. Scoring never runs inside the cloud session.

```bash
python scripts/score_one.py \
  --pr SLUG \
  --review traces/SLUG/RUNID/review.json \
  --answers-dir ../pr-review-evals-answers-v2

python scripts/score_all.py \
  --reviews traces \
  --answers-dir ../pr-review-evals-answers-v2 \
  -o reports/summary.md
```

## Known limit

`meta.json` includes the upstream PR URL and base/head SHAs. A reviewer with network access could fetch the original PR and spot the edit by comparison. The session prompt forbids that. When you read traces, check whether the model mentioned fetching the upstream PR. If it did, treat that run as contaminated.

## Local alternative

```bash
python scripts/run_review.py --pr SLUG --budget 1.0
```

That path also scores automatically when the private answers checkout is present. See README-WEEK0.md.
