"""Puzzle I/O, strict integer replay and submission validation."""

import csv
import json
from dataclasses import dataclass
from pathlib import Path

MAX_STEPS = 4096
MAX_BYTES = 131072
csv.field_size_limit(2_000_000)


@dataclass(frozen=True)
class Puzzle:
    id: str
    seeds: tuple
    targets: tuple
    limit: int
    slots: int
    family: str = "unlabelled"


def load_puzzles(path):
    puzzles = []
    seen = set()
    with open(path, newline="", encoding="utf-8-sig") as source:
        for row in csv.DictReader(source, strict=True):
            p = Puzzle(
                row["id"],
                tuple(json.loads(row["starting_values"])),
                tuple(json.loads(row["targets"])),
                int(row["value_limit"]),
                int(row["registers"]),
                row.get("family", "unlabelled"),
            )
            if p.id in seen or not p.id or not 1 <= len(p.seeds) <= p.slots <= 48:
                raise ValueError(f"Invalid or duplicate puzzle: {p.id}")
            if not 1 <= p.limit <= 10**18 or any(
                type(n) != int or not 1 <= n <= p.limit for n in p.seeds + p.targets
            ):
                raise ValueError(f"Invalid puzzle values: {p.id}")
            seen.add(p.id)
            puzzles.append(p)
    if not puzzles:
        raise ValueError("Empty puzzle input")
    return puzzles


def load_programs(path, reference=False):
    result = {}
    with open(path, newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source, strict=True)
        if not reference and reader.fieldnames != ["id", "program"]:
            raise ValueError("Expected id,program header")
        for row in reader:
            key, cell = row["id"], row["program"]
            if (
                not key
                or key in result
                or None in row
                or len(cell.encode()) > MAX_BYTES
            ):
                raise ValueError(f"Invalid submission row: {key}")
            result[key] = json.loads(cell)
    return result


def replay(p, code):
    regs = list(p.seeds) + [None] * (p.slots - len(p.seeds))
    seen = set(p.seeds)
    if type(code) is not list or len(code) > MAX_STEPS:
        raise ValueError(f"{p.id}: invalid program length")
    for idx, ins in enumerate(code):
        if type(ins) is not list or len(ins) != 4:
            raise ValueError(f"{p.id}:{idx}: invalid instruction")
        op, i, j, dest = ins
        if any(type(k) != int or not 0 <= k < p.slots for k in (i, j, dest)):
            raise ValueError(f"{p.id}:{idx}: invalid register")
        a, b = regs[i], regs[j]
        if a is None or b is None:
            raise ValueError(f"{p.id}:{idx}: uninitialized register")
        if op == "+":
            v = a + b
        elif op == "-":
            v = a - b
        elif op == "*":
            v = a * b
        elif op == "/" and a % b == 0:
            v = a // b
        else:
            raise ValueError(f"{p.id}:{idx}: invalid operation or inexact division")
        if not 1 <= v <= p.limit:
            raise ValueError(f"{p.id}:{idx}: value outside allowed range")
        regs[dest] = v
        seen.add(v)
    if not seen.issuperset(p.targets):
        raise ValueError(f"{p.id}: uncovered targets")
    return len(code)


def score(puzzles, codes):
    if set(codes) != {p.id for p in puzzles}:
        raise ValueError("Puzzle and submission IDs differ")
    return sum(replay(p, codes[p.id]) for p in puzzles)


def save_verified(path, puzzles, codes):
    from tempfile import NamedTemporaryFile

    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=dest.parent, delete=False
        ) as out:
            tmp = Path(out.name)
            writer = csv.writer(out, lineterminator="\n")
            writer.writerow(["id", "program"])
            for p in puzzles:
                writer.writerow([p.id, json.dumps(codes[p.id], separators=(",", ":"))])
        total = score(puzzles, load_programs(tmp))
        tmp.replace(dest)
        return total
    finally:
        if tmp:
            tmp.unlink(missing_ok=True)
