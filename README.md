# Santa_2026

Kaggle [Santa 2026 – The Elf Calculator](https://www.kaggle.com/competitions/santa-2026). 每题从给定的整数出发，写一段四则运算程序，让所有目标值在执行期间至少出现一次。评估指标是 1,000 道计分题的总指令数，越少越好。

**当前本地最佳成绩为 138,921 条指令，覆盖全部 1,000 道计分题。** 两套回放器逐题验证通过。纯自写路线的程序为 [standalone.csv.gz](checkpoints/standalone.csv.gz)，解压后即可回放，合计 207,257 条。

[实验记录](EXPERIMENTS.md) · [逐题成绩](progress.csv) · [文件校验与总分](checkpoint.json)

## 运行入口

准备好 `data/puzzles.csv` 后，在仓库根目录运行以下命令。全流程需要 Python 3.11+、NumPy、SciPy 和支持 C++17 的 g++。程序会核验下载的六份公开参考文件，并生成可提交的 `out/submission.csv`。

```bash
python reproduce.py data out --workers 4
```

运行 `python reproduce.py data own-out --own-only` 可单独复现从零求解，成绩文件为 `own-out/standalone.csv`。

## 本轮进度

| 全量实验 | 总指令数 |
|---|---:|
| 赛事样例 | 1,490,379 |
| 二进制构造 | 1,242,359 |
| 多进制构造 | 303,217 |
| 提取公因子、目标差及整除关系 | 305,083 |
| 自写构造逐题择优 | 300,044 |
| 自写双向字典搜索 | 223,797 |
| 自写构造与字典逐题择优 | 223,309 |
| 在自写候选上联合选择算式（整数规划） | 218,370 |
| 自写路线全部候选逐题择优 | **207,257** |
| 六份公开程序逐题择优 | 138,998 |
| 跨程序重组表达式 | 138,952 |
| 再搜索可替换的短算式 | 138,945 |
| 四步局部搜索分支 | 138,939 |
| 加入独立候选、调整寄存器分配 | 138,925 |
| 最终逐题合并 | **138,921** |

表中成绩均在本地回放，尚未取得 Kaggle 提交回执。独立的 200 道练习题从初始构造的 60,862 条降至 42,948 条。16 道小练习题与 16 道小计分题已用穷举证明各自的最短长度，总计分别为 50 与 57 条。公开程序组合的成绩包含第三方贡献。公开数据集和各版本见 [SOURCES.md](SOURCES.md)。

## 复现

Python 3.11+。整数规划这一个实验需要 SciPy 和 NumPy，实测版本为 SciPy 1.17.0、NumPy 2.3.5。原始题目可从赛事 Data 页面获取。下列命令在仓库根目录运行。前三个命令只用 Python 标准库。

```bash
python run.py verify data/puzzles.csv data/sample_submission.csv
python run.py construct data/puzzles.csv out/independent.csv --report out/independent.json
python run.py construct data/practice_puzzles.csv out/practice.csv --report out/practice.json
g++ -O3 -std=c++17 graph_search.cpp -o graph_search
g++ -O3 -std=c++17 backward.cpp -o backward
python dictionary.py data/puzzles.csv out/dictionary.csv
python integer_search.py data/puzzles.csv out/mip-own.csv --sources out/dictionary.csv out/independent.csv --nodes 16
```

公开解逐题择优、搜索及复查的命令见 [SOURCES.md](SOURCES.md)。每次写入 CSV 都先写临时文件，再从磁盘读回并逐条回放，验证成功后才替换输出。求解器不会向 Kaggle 发起提交。

## 方法

- 每个候选程序单独检查寄存器、输入是否已初始化、精确整除、数值上限及全部目标。已经产生过的目标可以从寄存器中覆盖。
- 从零构造时，同时比较二进制、多个带符号或无符号的进制，以及基于目标差和公因子的构造。编译器按需复用中间数，在寄存器紧张时回收并重新计算。
- 重组阶段使用各程序的实际中间值构建有向图，寻找同一个值的不同计算方法。搜索同时考虑一个中间数被多少个目标复用。局部改写允许用新的中间值替换整段算式。每题保留输入程序作为退路。

双向搜索先用当前数字建立一步可达值字典，再从目标反推并尝试在字典中会合。整数规划联合选择多个目标共享的算式，仅在给定候选和拓扑顺序内求解。对于数值上限不超过 20 且寄存器充足的小题，广度优先搜索遍历可达数字集合，第一次覆盖所有目标即给出最少步数。
