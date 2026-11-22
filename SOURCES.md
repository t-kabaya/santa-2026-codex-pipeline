# 数据与程序来源

计分、练习、示例 CSV 的 SHA-256 分别如下。此次读取了公开镜像中的这三份 CSV，并与另一份公开数据集逐行核对了计分与练习题。参赛者可从 [Kaggle Data](https://www.kaggle.com/competitions/santa-2026/data) 下载并自行核对。

| 文件 | SHA-256 |
|---|---|
| puzzles.csv | 41ae9beee69a49778a549012a14d2010e7c9d9af36997f1b84a4a8ad4222ad85 |
| practice_puzzles.csv | 13934566fc50cc25b2178d7a35287864127881e0f848f4a4e7b799089e7510bf |
| sample_submission.csv | 8d9e65baff997d5faa15cb654546a296457650436603928de0b07413cfa7e559 |

[赛题镜像与固定版本](https://github.com/Aftahiislam007/Santa-2026-The-Elf-Calculator/tree/d9b94cc61dc9be1d8f830be6ff7fca91ef8bfdd2/datasets) · [交叉核对题目的另一来源](https://www.kaggle.com/datasets/asteriospanoras/santa-2026-elf-programs-and-experiments/versions/6) · [独立复核所用回放器的固定版本](https://github.com/Juan-Severiano/santa-2026/blob/7f5cb0d8fd31de4ae1d1692e863987dde3d65992/src/santa2026/core.py)

## 公开起点

这些程序由下列作者及其引用的上游贡献者发布。各版本的原始归属、逐题来源和 NOTICE 随原始下载包提供。代码仓库只保存复现工具、哈希和统计信息，获取第三方程序请使用各自的发布页面。

| 保存为 | Kaggle 数据集 | 包内文件 | 单独回放 |
|---|---|---|---:|
| konbu.csv | [konbu17 v11](https://www.kaggle.com/datasets/konbu17/santa-2026-elf-calculator-programs/versions/11) | submission.csv | 142,940 |
| exp.csv | [asteriospanoras v6](https://www.kaggle.com/datasets/asteriospanoras/santa-2026-elf-programs-and-experiments/versions/6) | best_programs.csv | 141,308 |
| portfolio.csv | [skagumire v1](https://www.kaggle.com/datasets/skagumire/santa-2026-verified-portfolio-programs/versions/1) | best_programs.csv | 139,089 |
| xray.csv | [lucifer19 v1](https://www.kaggle.com/datasets/lucifer19/elf-calculator-x-ray-programs/versions/1) | xray_anchor_v2.csv | 141,361 |
| peephole.csv | [hanifnoerrofiq v13](https://www.kaggle.com/datasets/hanifnoerrofiq/santa-2026-elf-calculator-peephole-programs/versions/13) | submission.csv | 141,101 |
| elias.csv | [b05204047elias v3](https://www.kaggle.com/datasets/b05204047elias/elf-calculator-verified-best-programs/versions/3) | submission.csv | 142,856 |

先运行 README 中的构造命令。运行 `python fetch_references.py data` 获取六份固定版本的 CSV 并验证散列，或从上表手动下载。以下为 Bash 命令，源文件顺序同时指定平局时的取舍。图搜索使用每个题目 ID 的 SHA-256 派生固定随机种子。原运行环境为 Linux x86-64、Python 3.12、GNU C++。

```bash
sources=(data/portfolio.csv data/exp.csv data/xray.csv data/konbu.csv data/elias.csv data/peephole.csv out/independent.csv)
python run.py merge data/puzzles.csv out/public.csv --sources data/{konbu,exp,portfolio,xray,peephole,elias}.csv --report out/public.json
python run.py improve data/puzzles.csv out/graph.csv --sources "${sources[@]}" --cut-depth 0 --report out/graph.json
python run.py improve data/puzzles.csv out/cut.csv --sources out/graph.csv "${sources[@]}" --cut-depth 3 --report out/cut.json
python run.py verify data/puzzles.csv out/cut.csv
```
