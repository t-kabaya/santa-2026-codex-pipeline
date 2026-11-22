"""Cross-program graph optimization with independently replayed register scheduling."""

from collections import defaultdict
import hashlib
import heapq
import subprocess

from construct import compile_dag, InstructionBudgetExceeded
from machine import replay


def arithmetic(a, op, b):
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    return a // b


def value_graph(p, code):
    regs = list(p.seeds) + [None] * (p.slots - len(p.seeds))
    seen = set(p.seeds)
    graph = []
    for op, i, j, d in code:
        a, b = regs[i], regs[j]
        v = arithmetic(a, op, b)
        regs[d] = v
        if v not in seen:
            seen.add(v)
            graph.append((v, a, op, b))
    return graph


def ordered(expr, position):
    waiting = {}
    followers = defaultdict(list)
    ready = []
    for v, (a, _, b) in expr.items():
        args = {x for x in (a, b) if x in expr}
        waiting[v] = len(args)
        for x in args:
            followers[x].append(v)
        if not args:
            heapq.heappush(ready, (position.get(v, 10**6), v))
    order = []
    while ready:
        _, v = heapq.heappop(ready)
        order.append(v)
        for nxt in followers[v]:
            waiting[nxt] -= 1
            if not waiting[nxt]:
                heapq.heappush(ready, (position.get(nxt, 10**6), nxt))
    if len(order) != len(expr):
        raise ValueError("Cyclic candidate graph")
    return order


def improve_one(job):
    p, programs, binary, rounds, depth, schedule = job
    programs = sorted(programs, key=len)
    best = programs[0]
    graphs = []
    seen = set()
    for code in programs:
        graph = value_graph(p, code)
        key = tuple(graph)
        if key not in seen:
            seen.add(key)
            graphs.append(graph)
    salt = int.from_bytes(hashlib.sha256(p.id.encode()).digest()[:4], "big")
    lines = [
        f"{p.limit} {len(p.seeds)} {len(p.targets)} {len(graphs)} 1 {rounds} {depth} {salt}",
        " ".join(map(str, p.seeds)),
        " ".join(map(str, p.targets)),
    ]
    for g in graphs:
        lines.append(str(len(g)))
        lines.extend(f"{v} {a} {op} {b}" for v, a, op, b in g)
    proc = subprocess.run(
        [binary],
        input="\n".join(lines) + "\n",
        capture_output=True,
        text=True,
        check=True,
    )
    expr = {}
    for line in proc.stdout.splitlines():
        v, a, op, b = line.split()
        expr[int(v)] = int(a), op, int(b)
    # If the graph needs more registers at a given ordering, compare alternative
    # schedules or recompute evicted values. Keep the incoming program as fallback.
    schedules = [list(expr)]
    for g in graphs:
        schedules.append(ordered(expr, {item[0]: i for i, item in enumerate(g)}))
    if schedule and len(expr) < len(best):
        from schedule import allocate, pressure_order

        schedules.append(pressure_order(expr, p.targets))
        for seq in schedules:
            program = allocate(p, expr, seq)
            if program is not None:
                replay(p, program)
                return p.id, program
    for seq in schedules:
        if len(expr) >= len(best):
            break
        try:
            program = compile_dag(p, expr, seq, max_steps=len(best) - 1)
        except InstructionBudgetExceeded:
            continue
        n = replay(p, program)
        if n < len(best):
            best = program
    return p.id, best
