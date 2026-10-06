# Baseline v1 (cloud Claude Code)

Reviews came from cloud Claude Code on branches `review/batch1`, `review/batch2`, `review/batch3` (folder names inside those branches were all `batch1`; ignore that), and `review/encode-httpx-2278-20261006T053149Z`.

- Reviews dir: collected under `/tmp/v1-reviews` from those branches
- Answers dir: private `pr-review-evals-answers` (public slugs only)
- Seeded scored: 10  |  Clean scored: 20  |  Missing reviews: 0

**Recall (planted bugs caught):** 10/10 = 100%
**False-alarm rate (clean controls):** 1/20 = 5%

## Per-bug-type recall

| Bug type | Caught | Total | Recall |
|---|---:|---:|---:|
| inverted_condition | 4 | 4 | 100% |
| missing_none_check | 1 | 1 | 100% |
| wrong_variable | 5 | 5 | 100% |

## Seeded detail

| Slug | Bug type | Result |
|---|---|---|
| encode-httpx-2278 | wrong_variable | PASS |
| encode-httpx-307 | inverted_condition | PASS |
| encode-httpx-3378 | wrong_variable | PASS |
| encode-httpx-3773 | wrong_variable | PASS |
| pallets-click-2630 | wrong_variable | PASS |
| pallets-click-3777 | missing_none_check | PASS |
| pallets-click-3808 | inverted_condition | PASS |
| pallets-click-3861 | inverted_condition | PASS |
| pallets-click-3865 | inverted_condition | PASS |
| pallets-click-3877 | wrong_variable | PASS |

## Clean false alarms

| Slug | False-alarm findings |
|---|---:|
| encode-httpx-3371 | 1 |

## Notes

- **v1 is saturated.** 5 of 10 planted bugs were in test files, and nearly all were one-token swaps. A competent reviewer (and cloud Claude Code) catches them at 100% recall, so the set no longer discriminates. Use `data/prs-v2/` for the harder set.
- **encode-httpx-3371 false alarm is under review.** The reviewer claims `'%'` in userinfo is no longer escaped. That may be a real upstream bug; do not relabel it. Varun is checking it himself.
