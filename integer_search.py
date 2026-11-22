"""Select shared recipes jointly with a binary integer program on a fixed value order."""

import argparse
from collections import defaultdict, deque
from concurrent.futures import ProcessPoolExecutor
import warnings

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_array

from construct import compile_dag, InstructionBudgetExceeded
from improve import value_graph
from machine import load_programs, load_puzzles, replay, score, save_verified
from schedule import allocate, pressure_order


def edge(a, op, b):
    return (b, op, a) if op in ("+", "*") and b < a else (a, op, b)


def catalog(p, programs):
    graphs = [value_graph(p, code) for code in programs]
    primary = graphs[0]
    seed = set(p.seeds)
    choices = defaultdict(dict)
    for g in graphs:
        for v, a, op, b in g:
            choices[v][edge(a, op, b)] = None
    # Expand the incumbent's value set by alternative one-operation identities.
    pool = sorted(seed | {row[0] for row in primary})
    for i, a in enumerate(pool):
        for b in pool[: i + 1]:
            values = [(a + b, "+"), (a - b, "-"), (a * b, "*")]
            if a % b == 0:
                values.append((a // b, "/"))
            for v, op in values:
                if v in choices and v != a and v != b:
                    choices[v].setdefault(edge(a, op, b), None)
    # Insert optional values as soon as one recipe becomes computable. Preserve
    # the incumbent's instruction order among its own values so it stays feasible.
    anchored = {row[0] for row in primary}
    listen = defaultdict(list)
    waits = []
    outputs = []
    for v, opts in choices.items():
        if v in anchored:
            continue
        for a, _, b in opts:
            idx = len(waits)
            operands = {a, b}
            waits.append(len(operands))
            outputs.append(v)
            for x in operands:
                listen[x].append(idx)
    rank = {}

    def release(values):
        queue = deque(values)
        while queue:
            v = queue.popleft()
            if v in rank:
                continue
            rank[v] = len(rank)
            for idx in listen[v]:
                waits[idx] -= 1
                if waits[idx] == 0:
                    queue.append(outputs[idx])

    release(p.seeds)
    for v, _, _, _ in primary:
        release([v])
    return {
        v: [
            e
            for e in choices[v]
            if rank.get(e[0], len(rank)) < rank[v]
            and rank.get(e[2], len(rank)) < rank[v]
        ]
        for v in rank
        if v not in seed
    }


def model(p, choices, node_limit):
    # A selected recipe costs one step. Each target must have exactly one
    # producer. Each selected non-seed operand must itself have a producer.
    targets = set(p.targets) - set(p.seeds)
    if not targets:
        return {}
    needed = set(targets)
    pruned = {}
    for v, opts in reversed(choices.items()):
        if v not in needed:
            continue
        pruned[v] = opts
        for a, _, b in opts:
            needed.update((a, b))
    producers = {}
    records = []
    for v, opts in pruned.items():
        producers[v] = list(range(len(records), len(records) + len(opts)))
        records.extend((v, e) for e in opts)
    rr = []
    cc = []
    vv = []
    lo = []
    hi = []

    def constraint(pos, neg, lower, upper):
        row = len(lo)
        rr.extend([row] * (len(pos) + len(neg)))
        cc.extend(pos)
        cc.extend(neg)
        vv.extend([1] * len(pos))
        vv.extend([-1] * len(neg))
        lo.append(lower)
        hi.append(upper)

    for v, indices in producers.items():
        constraint(indices, [], 1 if v in targets else 0, 1)
        require = defaultdict(list)
        for i in indices:
            a, _, b = records[i][1]
            for x in {a, b}:
                if x in producers:
                    require[x].append(i)
        for x, idx in require.items():
            constraint(idx, producers[x], -np.inf, 0)
    n = len(records)
    matrix = coo_array(
        (np.asarray(vv, dtype=float), (rr, cc)), shape=(len(lo), n)
    ).tocsc()
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Unrecognized options detected.*")
        sol = milp(
            np.ones(n),
            integrality=np.ones(n),
            bounds=Bounds(0, 1),
            constraints=LinearConstraint(matrix, lo, hi),
            options={
                "node_limit": node_limit,
                "mip_rel_gap": 0,
                "threads": 1,
                "random_seed": 1,
            },
        )
    if sol.x is None or np.max(np.abs(sol.x - np.round(sol.x))) > 1e-6:
        return None
    chosen = {v: e for i, (v, e) in enumerate(records) if sol.x[i] > 0.5}
    return {v: chosen[v] for v in choices if v in chosen}


def optimize(job):
    p, codes, node_limit = job
    codes = sorted(codes, key=len)
    best = codes[0]
    options = catalog(p, codes)
    expr = model(p, options, node_limit)
    if expr is None or len(expr) >= len(best):
        return p.id, best
    for seq in [list(expr), pressure_order(expr, p.targets)]:
        code = allocate(p, expr, seq)
        if code is None:
            try:
                code = compile_dag(p, expr, seq, max_steps=len(best) - 1)
            except InstructionBudgetExceeded:
                continue
        replay(p, code)
        if len(code) < len(best):
            best = code
    return p.id, best


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("puzzles")
    ap.add_argument("output")
    ap.add_argument("--sources", nargs="+", required=True)
    ap.add_argument(
        "--nodes", type=int, default=64, help="Branch-and-bound node budget per puzzle"
    )
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    ps = load_puzzles(args.puzzles)
    src = [load_programs(f, reference=True) for f in args.sources]
    for s in src:
        score(ps, s)
    with ProcessPoolExecutor(args.workers) as pool:
        result = dict(
            pool.map(
                optimize,
                ((p, [s[p.id] for s in src], args.nodes) for p in ps),
                chunksize=1,
            )
        )
    print(save_verified(args.output, ps, result))


if __name__ == "__main__":
    main()
