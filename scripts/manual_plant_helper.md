# Manual bug planting (fallback)

When seeding marks a PR as `needs_manual`, plant the bug in the private answers checkout, then rebuild the public `review_input.diff`.

1. Work under `../pr-review-evals-answers/<slug>/` (private).
2. Copy `head_files/` to a temp mutated tree, edit one added line, record `ground_truth.json`.
3. Keep `diff.patch` as the original PR diff.
4. From the public repo root:

```bash
python scripts/make_review_input.py --slug <slug> --answers-dir ../pr-review-evals-answers
# Also copy the mutated tree into data/prs/<slug>/files/
```

5. Confirm the public folder has only `meta.json`, `review_input.diff`, and `files/`.
