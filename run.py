"""Drive independent constructive and external warm-start experiments."""

import argparse
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from construct import build
from machine import load_puzzles, load_programs, replay, score, save_verified


def construct_one(p):
    families = {}
    for family, configs in [
        ("binary", [(2, False, False)]),
        (
            "radix",
            [
                (b, s, False)
                for b in (8, 16, 24, 32, 48, 64, 96, 128, 192, 256, 384, 512, 768, 1024)
                for s in (False, True)
            ],
        ),
        ("relations", [(b, True, True) for b in (16, 64, 256)]),
    ]:
        best = None
        for b, s, r in configs:
            program = build(p, b, s, r)
            n = replay(p, program)
            if best is None or n < len(best):
                best = program
        families[family] = best
    name, code = min(families.items(), key=lambda x: len(x[1]))
    return p.id, code, {"winner": name, **{k: len(v) for k, v in families.items()}}


def sha(path):
    with open(path, "rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["construct", "merge", "verify", "improve"])
    parser.add_argument("puzzles")
    parser.add_argument("output", help="For verify, the submission to check")
    parser.add_argument("--sources", nargs="+", default=[])
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--report")
    parser.add_argument("--binary", default="./graph_search")
    parser.add_argument("--rounds", type=int, default=6)
    parser.add_argument("--cut-depth", type=int, choices=[0, 2, 3, 4], default=3)
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Try last-use register allocation and a memory-aware operation order",
    )
    args = parser.parse_args()
    puzzles = load_puzzles(args.puzzles)
    if args.action == "verify":
        print(score(puzzles, load_programs(args.output)))
        return
    paths = [Path(s) for s in args.sources]
    if len({s.stem for s in paths}) != len(paths):
        raise ValueError("Source file stems must be unique")
    sources = {s.stem: load_programs(s, reference=True) for s in paths}
    for codes in sources.values():
        score(puzzles, codes)
    if args.action in ("improve", "merge") and not sources:
        parser.error("At least one source required")
    result = {}
    report = {}
    if args.action == "construct":
        with ProcessPoolExecutor(args.workers) as pool:
            for pid, best, details in pool.map(construct_one, puzzles, chunksize=2):
                result[pid] = best
                report[pid] = details
    else:
        for p in puzzles:
            name = min(sources, key=lambda s: len(sources[s][p.id]))
            result[p.id] = sources[name][p.id]
            report[p.id] = {
                "winner": name,
                **{s: len(g[p.id]) for s, g in sources.items()},
            }
        if args.action == "improve":
            from improve import improve_one

            with ProcessPoolExecutor(args.workers) as pool:
                jobs = (
                    (
                        p,
                        [g[p.id] for g in sources.values()],
                        args.binary,
                        args.rounds,
                        args.cut_depth,
                        args.schedule,
                    )
                    for p in puzzles
                )
                for pid, program in pool.map(improve_one, jobs, chunksize=1):
                    report[pid]["before"] = len(result[pid])
                    result[pid] = program
    total = save_verified(args.output, puzzles, result)
    for p in puzzles:
        report[p.id].update(steps=len(result[p.id]), family=p.family)
    summary = dict(
        puzzles=len(puzzles),
        total=total,
        puzzles_sha256=sha(args.puzzles),
        output_sha256=sha(args.output),
        source_sha256={p.stem: sha(p) for p in paths},
    )
    if args.report:
        Path(args.report).write_text(
            json.dumps(dict(summary=summary, rows=report), indent=2) + "\n"
        )
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
