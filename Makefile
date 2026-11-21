PYTHON ?= $(if $(wildcard /opt/homebrew/bin/python3),/opt/homebrew/bin/python3,python3)
DISCOVER_LIMIT ?= 30
DISCUSSION_LIMIT ?= 10
SUBMISSION := out/santa-sync/submission.csv
PUZZLES := Hansen-Santa_2026/data/puzzles.csv
SUBMIT_MESSAGE ?= Verified Santa 2026 public answer merge

.DEFAULT_GOAL := help
.PHONY: help discover discover-discussion restore-hansen sync verify submit pipeline

help:
	@echo 'make discover  Register verified CSVs from Kaggle Datasets and Code'
	@echo 'make discover-discussion  List Santa 2026 discussion posts and candidate links'
	@echo 'make restore-hansen  Restore and verify the pinned Hansen portfolio'
	@echo 'make sync      Update the local merged submission'
	@echo 'make verify    Validate the merged CSV and print its instruction count'
	@echo 'make submit    Verify and submit the merged CSV to Kaggle'
	@echo 'make pipeline  Run discover, restore-hansen, sync, verify, and submit in order'

# 公開データセット、ノートブック、保存済みの Discussion 候補から検証済みの解答 CSV を登録する。
discover:
	"$(PYTHON)" discover_santa_answers.py --limit "$(DISCOVER_LIMIT)"

# 最近の Kaggle Discussion 投稿と、解答候補のリンクを一覧にする。
discover-discussion:
	"$(PYTHON)" discover_santa_discussion.py --limit "$(DISCUSSION_LIMIT)"

# Hansen の固定版を復元し、全問題の命令数と出力ハッシュを検証する。
restore-hansen:
	"$(PYTHON)" restore_hansen.py

# 登録済みの取得元から最新版を取得・検証し、問題ごとの最短解でローカルの合成 CSV を更新する。
sync:
	"$(PYTHON)" sync_santa_answers.py

# 合成 CSV の全問題を再検証し、総命令数を表示する。
verify:
	"$(PYTHON)" Hansen-Santa_2026/run.py verify "$(PUZZLES)" "$(SUBMISSION)"

# 検証に成功した合成 CSV を Kaggle に提出し、採点結果を待つ。
submit: verify
	kaggle competitions submit santa-2026 -f "$(SUBMISSION)" -m "$(SUBMIT_MESSAGE)" --wait

# 探索、Hansen 版の復元、同期、検証、提出を順に実行する。
pipeline:
	$(MAKE) discover
	$(MAKE) restore-hansen
	$(MAKE) sync
	$(MAKE) submit
