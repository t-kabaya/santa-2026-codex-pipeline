# Santa 2026 — The Elf Calculator

Santa 2026 の公開解答を収集して実行検証し、問題ごとに最短のプログラムを採用します。合成した CSV は `out/santa-sync/submission.csv` に保存します。

## 実行

Python 3.11 以降、Kaggle CLI、Git、curl が必要です。Kaggle で参加手続きを済ませ、公式データの `puzzles.csv` と `sample_submission.csv` を `data/` に置きます。同期は前回の合成 CSV を引き継ぎます。初回は `out/public.csv` があればそれを使い、なければ公式サンプルから始めます。

| コマンド | 処理 |
| --- | --- |
| `make refresh` | Discussion と公開解答の探索、固定版の復元、合成、全問検証 |
| `make verify` | 現在の合成 CSV の全問検証と命令数の表示 |
| `make submit` | 検証済み CSV を Kaggle に提出して採点を待つ |
| `make pipeline` | 公開解答の探索、復元、合成、検証、提出 |

GitHub Actions は毎日 08:00（日本時間）に `make refresh` を実行します。前回の合成 CSV と取得元の一覧を成果物から読み込み、GitHub の候補があれば Codex が復元手順を報告します。ワークフローは `KAGGLE_API_TOKEN` と `OPENAI_API_KEY` を参照します。

## 取得元

- 初期取得元は [references.json](references.json) に記録しています。探索で追加した取得元は `out/santa-sync/discovered-references.json` に保存します。
- [Hansen0223/Santa_2026](https://github.com/Hansen0223/Santa_2026) の固定版を `make restore-hansen` で復元します。命令の実行検証と CSV の読み書きは、同リポジトリのコミット `03d9682c11b2a4867a1b62cf98ad745fd5951980` に由来します。
- [GoodPJW の公開ノートブック](https://www.kaggle.com/code/goodpjw2008/santa-2026-lns-cp-sat-recombine-lb-132-256) の Output CSV を `make restore-goodpjw` で取得します。
