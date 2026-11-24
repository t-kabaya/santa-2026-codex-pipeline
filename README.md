# Santa 2026 — Daily Public Solution Collection and Submission with Codex

This pipeline runs daily on GitHub Actions and uses Codex to investigate how to reproduce public Kaggle Santa 2026 solutions.
It verifies the collected solutions, keeps the shortest valid program for each puzzle, and submits the merged result to Kaggle.

## Fork and run

Have your `KAGGLE_API_TOKEN` and `OPENAI_API_KEY` ready to add as GitHub Actions secrets during setup.

```bash
gh auth login
gh repo fork t-kabaya/santa-2026-codex-pipeline --clone=false
repo="$(gh api user --jq .login)/santa-2026-codex-pipeline"

gh secret set KAGGLE_API_TOKEN --repo "$repo"
gh secret set OPENAI_API_KEY --repo "$repo" # Optional Codex review
gh workflow enable santa-refresh.yml --repo "$repo"
```

If GitHub prompts you to enable Actions on the fork, follow the prompt in its **Actions** tab.

**Automatic runs.** Once Actions and the workflow are enabled on the fork, GitHub schedules a run daily at **01:00 UTC** using the default branch. GitHub may start a run later than scheduled.

**Manual runs.** Run this command to start a submission immediately, or select **Actions → Santa daily submission → Run workflow** on GitHub.

```bash
gh workflow run santa-refresh.yml --repo "$repo" --ref main
```

The runner installs the required CLI tools. Each successful run submits once and reports the Kaggle submission ID and score in the **submit** job log. Set `OPENAI_API_KEY` to enable the Codex review.

## About this repository

The pipeline discovers public solutions on Kaggle and verifies every program against the official puzzles. It combines the shortest valid solution for each of the 1,000 puzzles with candidates from [configured sources](restore_sources.json), including [Hansen's portfolio](https://github.com/Hansen0223/Santa_2026) and [GoodPJW's notebook](https://www.kaggle.com/code/goodpjw2008/santa-2026-lns-cp-sat-recombine-lb-132-256). Codex reviews GitHub links from Kaggle Discussions and reports restoration instructions for review.

- **Official competition data** provides `puzzles.csv` for validation and `sample_submission.csv` as the initial baseline. [Santa 2026 Data](https://www.kaggle.com/competitions/santa-2026/data)
- **Kaggle Datasets** provide answer CSVs from konbu17, Asterios Panoras, skagumire, lucifer19, Hanif Noer Rofiq, and Elias T.-H. Shieh. The pipeline also searches for newly published datasets. [Configured datasets and CSV filenames](references.json)
- **Kaggle notebook outputs** provide public answer CSVs, including GoodPJW's `submission.csv` and `submission_live_merge.csv`. [GoodPJW's Output](https://www.kaggle.com/code/goodpjw2008/santa-2026-lns-cp-sat-recombine-lb-132-256/output)
- **Hansen's GitHub portfolio** is restored from a pinned Git commit, a fixed version of Alex Chilton's Rudolph dataset, and a pinned Asterios Panoras notebook. [Restoration instructions](https://github.com/Hansen0223/Santa_2026/blob/a8338d35791de45e3b225dc6304023cf4b391d7b/public-assisted/releases/portfolio.md)
- **Kaggle Discussions** provide links to additional datasets, notebooks, and GitHub repositories that may contain solutions or restoration instructions. [Santa 2026 Discussions](https://www.kaggle.com/competitions/santa-2026/discussion)
