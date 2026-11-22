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

# 公開データセット、ノートブック、保存済みの Discussion 候補から検証済みの解答 CSV を登録する。
discover:
	"$(PYTHON)" discover_santa_answers.py --limit "$(DISCOVER_LIMIT)"

# 最近の Kaggle Discussion 投稿と、解答候補のリンクを一覧にする。
discover-discussion:
	"$(PYTHON)" discover_santa_discussion.py --limit "$(DISCUSSION_LIMIT)"

# Discussion 候補を更新してから公開解答を探す。
discover-all:
	$(MAKE) discover-discussion
	$(MAKE) discover

# Discussion の GitHub 候補から Codex で復元手順を調査する。
review-restore:
	"$(PYTHON)" review_restore.py

# 設定に従って候補を取得・復元し、合成用の CSV を保存する。
restore:
	"$(PYTHON)" restore_answers.py $(if $(RESTORE_SOURCE),--source "$(RESTORE_SOURCE)")

# 登録済みの取得元から最新版を取得・検証し、問題ごとの最短解でローカルの合成 CSV を更新する。
sync:
	"$(PYTHON)" sync_santa_answers.py

# 合成 CSV の全問題を再検証し、総命令数を表示する。
verify:
	"$(PYTHON)" run.py verify "$(PUZZLES)" "$(SUBMISSION)"

# 検証に成功した合成 CSV を Kaggle に提出し、採点結果を待つ。
submit: verify
	kaggle competitions submit santa-2026 -f "$(SUBMISSION)" -m "$(SUBMIT_MESSAGE)" --wait

# 登録済み候補を復元して合成する。
merge-portfolio:
	$(MAKE) restore
	$(MAKE) sync

# 合成 CSV を検証して Kaggle に提出する。
merge-and-submit: merge-portfolio
	$(MAKE) submit

# Discussion と公開解答を探索し、復元・合成結果を検証する。
refresh: discover-all
	$(MAKE) merge-portfolio
	$(MAKE) verify

# 公開解答を探索し、Codex の調査を経て合成・提出する。
pipeline:
	$(MAKE) discover-all
	$(MAKE) review-restore
	$(MAKE) merge-and-submit
