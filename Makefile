PYTHON ?= $(if $(wildcard /opt/homebrew/bin/python3),/opt/homebrew/bin/python3,python3)
DISCOVER_LIMIT ?= 30
DISCUSSION_LIMIT ?= 20
SUBMISSION := out/santa-sync/submission.csv
PUZZLES := data/puzzles.csv
SUBMIT_MESSAGE ?= Verified Santa 2026 public answer merge

.DEFAULT_GOAL := help
.PHONY: help discover discover-discussion discover-all review-restore restore sync verify submit merge-portfolio merge-and-submit refresh pipeline

help:
	@echo 'make discover  Register verified CSVs from Kaggle Datasets and Code'
	@echo 'make discover-discussion  List Santa 2026 discussion posts and candidate links'
	@echo 'make discover-all  Discover Discussion and public Kaggle answers'
	@echo 'make review-restore  Review GitHub restoration instructions with Codex'
	@echo 'make restore   Restore and verify configured sources (optional: RESTORE_SOURCE=name)'
	@echo 'make sync      Update the local merged submission'
	@echo 'make verify    Validate the merged CSV and print its instruction count'
	@echo 'make submit    Verify and submit the merged CSV to Kaggle'
	@echo 'make merge-and-submit  Restore, merge, verify, and submit the portfolio'
	@echo 'make refresh   Discover, restore, merge, and verify the local CSV'
	@echo 'make pipeline  Review, refresh, and submit the local portfolio to Kaggle'

# Register verified CSVs from public datasets, notebooks, and saved Discussion candidates.
discover:
	"$(PYTHON)" discover_santa_answers.py --limit "$(DISCOVER_LIMIT)"

# List recent Kaggle Discussion posts and links to possible solutions.
discover-discussion:
	"$(PYTHON)" discover_santa_discussion.py --limit "$(DISCUSSION_LIMIT)"

# Refresh the Discussion candidates before discovering public solutions.
discover-all:
	$(MAKE) discover-discussion
	$(MAKE) discover

# Review GitHub restoration instructions referenced by Discussion posts.
review-restore:
	"$(PYTHON)" review_restore.py

# Restore the configured candidates and save their CSVs for merging.
restore:
	"$(PYTHON)" restore_answers.py $(if $(RESTORE_SOURCE),--source "$(RESTORE_SOURCE)")

# Update the local portfolio with the shortest verified program per puzzle.
sync:
	"$(PYTHON)" sync_santa_answers.py

# Verify every program in the merged CSV and print its total instruction count.
verify:
	"$(PYTHON)" run.py verify "$(PUZZLES)" "$(SUBMISSION)"

# Verify the CSV, submit to Kaggle, and wait for scoring.
submit: verify
	kaggle competitions submit santa-2026 -f "$(SUBMISSION)" -m "$(SUBMIT_MESSAGE)" --wait

# Restore and merge the registered candidates.
merge-portfolio:
	$(MAKE) restore
	$(MAKE) sync

# Verify the merged CSV and submit it to Kaggle.
merge-and-submit: merge-portfolio
	$(MAKE) submit

# Discover, restore, merge, and verify the local portfolio.
refresh: discover-all
	$(MAKE) merge-portfolio
	$(MAKE) verify

# Discover public solutions, review restoration instructions, then merge and submit.
pipeline:
	$(MAKE) discover-all
	$(MAKE) review-restore
	$(MAKE) merge-and-submit
