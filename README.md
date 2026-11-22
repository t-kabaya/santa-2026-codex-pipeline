# Santa 2026 — The Elf Calculator

Santa 2026 の公開解答を収集して実行検証し、問題ごとに最短のプログラムを採用します。合成した CSV は `out/santa-sync/submission.csv` に保存します。

## 実行

Python 3.11 以降、Kaggle CLI、Git、curl が必要です。Kaggle で参加手続きを済ませ、公式データの `puzzles.csv` と `sample_submission.csv` を `data/` に置きます。同期は前回の合成 CSV を引き継ぎます。初回は `out/public.csv` があればそれを使い、なければ公式サンプルから始めます。

| コマンド | 処理 |
| --- | --- |
| `make refresh` | Discussion と公開解答の探索、固定版の復元、合成、全問検証 |
| `make restore` | 設定済みの候補を取得・復元。個別実行は `RESTORE_SOURCE=hansen` などで指定 |
| `make verify` | 現在の合成 CSV の全問検証と命令数の表示 |
| `make submit` | 検証済み CSV を Kaggle に提出して採点を待つ |
| `make review-restore` | 保存済みの Discussion 候補を Codex CLI で調査し、復元手順を JSON に出力 |
| `make pipeline` | 公開解答の探索、Codex の調査、復元、合成、検証、提出 |

ローカルで Codex の調査を行うには、認証済みの Codex CLI が必要です。結果は `out/restore-review.json` に保存します。調査で見つかった手順を確認し、実行する復元処理は `restore_sources.json` に登録します。

ローカルの `make pipeline` と GitHub Actions は `make discover-all`、`make review-restore`、`make merge-and-submit` を同じ順序で呼びます。GitHub Actions では Codex の API キーと Kaggle トークンを別のジョブに渡します。

GitHub Actions は毎日 08:00（日本時間）に公開解答を探索し、固定版を復元して合成した CSV を全問検証し、Kaggle に一度提出します。前回の合成 CSV と取得元の一覧を成果物から読み込み、今回の命令数と改善幅も保存します。GitHub の候補があれば Codex が復元手順を JSON で報告し、確認済みの復元手順は後続の実行で利用できます。ワークフローは `KAGGLE_API_TOKEN` と `OPENAI_API_KEY` を参照します。

## 取得元

- 初期取得元は [references.json](references.json) に記録しています。探索で追加した取得元は `out/santa-sync/discovered-references.json` に保存します。
- [restore_sources.json](restore_sources.json) に復元対象を登録します。公開ノートブックは `notebook` と `files` を指定します。独自の復元処理は `script` を指定し、`out/<取得元名>/submission.csv` に出力します。`make sync` は同じ設定から復元済み CSV を読み込みます。
- [Hansen0223/Santa_2026](https://github.com/Hansen0223/Santa_2026) の固定版と [GoodPJW の公開ノートブック](https://www.kaggle.com/code/goodpjw2008/santa-2026-lns-cp-sat-recombine-lb-132-256) を登録済みです。命令の実行検証と CSV の読み書きは、Hansen のコミット `03d9682c11b2a4867a1b62cf98ad745fd5951980` に由来します。
