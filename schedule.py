"""Topological scheduling and exact last-use allocation for a given expression DAG."""

from collections import Counter, defaultdict


def pressure_order(expr, targets):
    """Prefer ready operations that release operands and finish old working sets."""
    left = Counter(x for a, _, b in expr.values() for x in {a, b})
    fans = defaultdict(list)
    waits = {}
    pri = {}
    for v, (a, _, b) in expr.items():
        parents = {x for x in (a, b) if x in expr}
        waits[v] = len(parents)
        for x in parents:
            fans[x].append(v)
    # Reverse distance to a target provides a tie-breaker.
    for v in reversed(expr):
        pri[v] = 1 + max((pri.get(w, 0) for w in fans[v]), default=0)
    ready = {v for v, n in waits.items() if n == 0}
    order = []
    while ready:

        def key(v):
            a, _, b = expr[v]
            freed = (left[a] == 1) + int(b != a and left[b] == 1)
            return (freed - int(bool(fans[v])), pri[v], -v)

        v = max(ready, key=key)
        ready.remove(v)
        order.append(v)
        a, _, b = expr[v]
        for x in {a, b}:
            left[x] -= 1
        for w in fans[v]:
            waits[w] -= 1
            if waits[w] == 0:
                ready.add(w)
    if len(order) != len(expr):
        raise ValueError("Cyclic graph")
    return order


def allocate(p, expr, order):
    """Return None when the proposed order would exceed the register budget."""
    left = Counter(x for a, _, b in expr.values() for x in {a, b})
    loc = {x: i for i, x in enumerate(p.seeds) if left[x]}
    free = [i for i in range(p.slots) if i not in set(loc.values())]
    code = []
    for v in order:
        a, op, b = expr[v]
        i, j = loc[a], loc[b]
        for x in {a, b}:
            left[x] -= 1
            if not left[x]:
                free.append(loc.pop(x))
        if not free:
            return None
        dest = free.pop()
        code.append([op, i, j, dest])
        if left[v]:
            loc[v] = dest
        else:
            free.append(dest)
    return code
