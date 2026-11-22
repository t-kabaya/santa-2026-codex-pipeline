"""Exact shortest programs when every possible value can stay in a register."""

from collections import deque


def shortest(puzzle):
    if (
        puzzle.limit > 20
        or puzzle.limit + len(puzzle.seeds) - len(set(puzzle.seeds)) > puzzle.slots
    ):
        return None
    seeds = {v: i for i, v in enumerate(puzzle.seeds)}
    start = sum(1 << (v - 1) for v in seeds)
    goal = sum(1 << (v - 1) for v in set(puzzle.targets))
    queue = deque([start])
    parents = {start: None}
    while queue:
        mask = queue.popleft()
        if mask & goal == goal:
            break
        values = [i + 1 for i in range(puzzle.limit) if mask & (1 << i)]
        for i, a in enumerate(values):
            for b in values[: i + 1]:
                choices = [(a + b, "+"), (a * b, "*"), (a - b, "-")]
                if a % b == 0:
                    choices.append((a // b, "/"))
                for v, op in choices:
                    if not 1 <= v <= puzzle.limit:
                        continue
                    nxt = mask | (1 << (v - 1))
                    if nxt not in parents:
                        parents[nxt] = mask, (op, a, b, v)
                        queue.append(nxt)
    else:
        raise ValueError(f"{puzzle.id}: unreachable tiny puzzle")
    steps = []
    while mask != start:
        mask, step = parents[mask]
        steps.append(step)
    code = []
    for op, a, b, v in reversed(steps):
        dest = len(puzzle.seeds) + len(code)
        code.append([op, seeds[a], seeds[b], dest])
        seeds[v] = dest
    return code
