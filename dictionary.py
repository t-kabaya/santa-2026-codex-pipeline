"""Run the independent backward-search constructor and replay its generated programs."""

import argparse
import subprocess
from concurrent.futures import ProcessPoolExecutor

from construct import compile_dag
from machine import load_puzzles, replay, save_verified
from tiny import shortest


def solve_one(job):
    p, binary, radix, width = job
    exact = shortest(p)
    if exact is not None:
        return p.id, exact
    line = f"{p.limit} {len(p.seeds)} {len(p.targets)} {radix} {width}\n"
    line += " ".join(map(str, p.seeds)) + "\n" + " ".join(map(str, p.targets)) + "\n"
    output = subprocess.run(
        [binary], input=line, text=True, capture_output=True, check=True
    ).stdout
    expr = {}
    for row in output.splitlines():
        v, a, op, b = row.split()
        expr[int(v)] = (int(a), op, int(b))
    code = compile_dag(p, expr, list(expr))
    replay(p, code)
    return p.id, code


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("puzzles")
    ap.add_argument("output")
    ap.add_argument("--binary", default="./backward")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--radix", type=int, default=256)
    ap.add_argument("--width", type=int, default=14)
    args = ap.parse_args()
    if not 2 <= args.radix <= 4096 or not 1 <= args.width <= 1024:
        ap.error("radix must be 2..4096 and width 1..1024")
    puzzles = load_puzzles(args.puzzles)
    with ProcessPoolExecutor(args.workers) as pool:
        result = dict(
            pool.map(
                solve_one,
                ((p, args.binary, args.radix, args.width) for p in puzzles),
                chunksize=1,
            )
        )
    print(save_verified(args.output, puzzles, result))


if __name__ == "__main__":
    main()
