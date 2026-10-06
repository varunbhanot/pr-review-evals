# pr-review-evals

Personal capstone: evaluate a coding-agent PR reviewer with error analysis, a validated LLM judge, CI gates, red-team probes, and a cost vs pass-rate experiment.

**v2 data is ready** under `data/prs-v2/<slug>/` (20 subtle source-only planted bugs + 20 clean controls). v1 under `data/prs/` is saturated at 100% recall; see `reports/baseline-v1.md`.

Public inputs only: each PR has `meta.json`, `review_input.diff`, and `files/`. Answer keys are not in this repo.

## Start here

1. **Cloud (preferred):** [CLOUD-CLAUDE-CODE.md](./CLOUD-CLAUDE-CODE.md) (four ready-to-paste v2 batch prompts)
2. **Local headless alternative:** [README-WEEK0.md](./README-WEEK0.md)
3. **Score a batch:** `python scripts/score_all.py --reviews traces --answers-dir ../pr-review-evals-answers-v2`

Built on public open-source PRs from `encode/httpx` and `pallets/click` only. No employer or customer data.

Personal project. Views are my own.
