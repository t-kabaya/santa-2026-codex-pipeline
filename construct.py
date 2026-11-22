"""Independent arithmetic constructions with value reuse and register recycling."""

from collections import Counter, defaultdict
from bisect import bisect_right
from math import gcd


def plan(p, base, balanced, relations):
    expr = {}
    seeds = set(p.seeds)
    available = set(p.seeds)
    order = []
    targets = set(p.targets)

    def put(v, a, op, b):
        if v not in available:
            expr[v] = (a, op, b)
            available.add(v)
            order.append(v)
        return v

    def radix(v):
        if v in available:
            return v
        if v == 1:
            return put(1, p.seeds[0], "/", p.seeds[0])
        # Divide a small digit recursively, independently of the outer base.
        if v <= base:
            half = radix(v // 2)
            even = put(half * 2, half, "+", half)
            if even == v:
                return even
            return put(v, even, "+", radix(1))
        q, r = divmod(v, base)
        if balanced and 2 * r > base and (q + 1) * base <= p.limit:
            q, r = q + 1, r - base
        a, b = radix(q), radix(base)
        prod = put(q * base, a, "*", b)
        if not r:
            return prod
        return put(v, prod, "+" if r > 0 else "-", radix(abs(r)))

    def digit_cost(v):
        if v in available:
            return 0
        return 2 * ((v.bit_length() - 1) / max(1, base.bit_length() - 1)) + 1

    anchors = set(p.seeds)
    if relations:
        divisors = Counter(gcd(a, b) for a in sorted(targets) for b in targets if a < b)
        for d, freq in sorted(divisors.items(), key=lambda item: (-item[1], -item[0])):
            if (
                d > base
                and (freq >= 2 or d.bit_length() >= 14)
                and len(anchors) < len(seeds) + 16
            ):
                radix(d)
                anchors.add(d)
    pending = set(targets) - available
    while pending:
        if not relations:
            t = min(pending)
            radix(t)
        else:
            # Model the cost of synthesizing an offset/factor from scratch.
            # Also use common divisors across targets as optional anchors.
            best = None
            for t in sorted(pending):
                candidate = (digit_cost(t), t, 0, 0, "", 0)
                for a in anchors:
                    if a == t:
                        candidate = (0, t, 0, 0, "", 0)
                        break
                    d = abs(t - a)
                    if d < t:
                        option = (1 + digit_cost(d), t, 1, a, "+" if t > a else "-", d)
                        candidate = min(candidate, option)
                    if a > 1 and t % a == 0:
                        option = (1 + digit_cost(t // a), t, 1, a, "*", t // a)
                        candidate = min(candidate, option)
                    if a > t and a % t == 0:
                        option = (1 + digit_cost(a // t), t, 1, a, "/", a // t)
                        candidate = min(candidate, option)
                best = candidate if best is None else min(best, candidate)
            _, t, uses_anchor, a, op, d = best
            if uses_anchor:
                radix(d)
                put(t, a, op, d)
            else:
                radix(t)
            anchors.add(t)
        pending.difference_update(available)
    return expr, order


class InstructionBudgetExceeded(Exception):
    """This schedule cannot improve the incumbent program."""


def compile_dag(p, expr, proposed_order, max_steps=None):
    """Emit only reachable values. Evicted intermediate values may be recomputed."""
    roots = set(p.targets)
    needed = set(roots)
    sequence = []
    for v in reversed(proposed_order):
        if v in needed:
            a, _, b = expr[v]
            needed.update((a, b))
            sequence.append(v)
    sequence.reverse()
    uses = defaultdict(list)
    for tick, v in enumerate(sequence):
        a, _, b = expr[v]
        uses[a].append(tick)
        uses[b].append(tick)

    pinned = set(p.seeds) & needed
    loc = {v: i for i, v in enumerate(p.seeds) if v in pinned}
    regs = [None] * p.slots
    for v, idx in loc.items():
        regs[idx] = v
    code = []

    def emit(v, protected):
        if v in loc:
            return loc[v]
        a, op, b = expr[v]
        i = emit(a, protected)
        j = emit(b, protected | {a})
        if None in regs:
            out = regs.index(None)
        else:

            def priority(value):
                times = uses[value]
                k = bisect_right(times, tick)
                return times[k] if k < len(times) else float("inf")

            allowed = [x for x in regs if x not in pinned and x not in protected]
            if not allowed:
                raise ValueError("Register pressure")
            victim = max(allowed, key=priority)
            out = loc.pop(victim)
        if max_steps is not None and len(code) >= max_steps:
            raise InstructionBudgetExceeded
        code.append([op, i, j, out])
        regs[out] = v
        loc[v] = out
        return out

    for tick, v in enumerate(sequence):
        emit(v, set())
    return code


def build(p, base=2, balanced=False, relations=False):
    return compile_dag(p, *plan(p, base, balanced, relations))
