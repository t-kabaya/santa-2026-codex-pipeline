PYTHON ?= $(if $(wildcard /opt/homebrew/bin/python3),/opt/homebrew/bin/python3,python3)
DISCOVER_LIMIT ?= 30
SUBMISSION := out/santa-sync/submission.csv
PUZZLES := Hansen-Santa_2026/data/puzzles.csv
SUBMIT_MESSAGE ?= Verified Santa 2026 public answer merge

.DEFAULT_GOAL := help
.PHONY: help discover sync verify submit pipeline

help:
	@echo 'make discover  Register verified CSVs from Kaggle Datasets and Code'
	@echo 'make sync      Update the local merged submission'
	@echo 'make verify    Validate the merged CSV and print its instruction count'
	@echo 'make submit    Verify and submit the merged CSV to Kaggle'
	@echo 'make pipeline  Run discover, sync, verify, and submit in order'

# 公開データセットとノートブックの出力を探し、検証済みの解答 CSV を登録する。
discover:
	"$(PYTHON)" discover_santa_answers.py --limit "$(DISCOVER_LIMIT)"

# 登録済みの取得元から最新版を取得・検証し、問題ごとの最短解でローカルの合成 CSV を更新する。
sync:
	"$(PYTHON)" sync_santa_answers.py

# 合成 CSV の全問題を再検証し、総命令数を表示する。
verify:
	"$(PYTHON)" Hansen-Santa_2026/run.py verify "$(PUZZLES)" "$(SUBMISSION)"

# 検証に成功した合成 CSV を Kaggle に提出し、採点結果を待つ。
submit: verify
	kaggle competitions submit santa-2026 -f "$(SUBMISSION)" -m "$(SUBMIT_MESSAGE)" --wait

# 探索、同期、検証、提出を順に実行し、途中で失敗したら停止する。
pipeline:
	$(MAKE) discover
	$(MAKE) sync
	$(MAKE) submit
