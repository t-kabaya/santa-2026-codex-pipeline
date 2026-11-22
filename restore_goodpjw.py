"""Fetch GoodPJW's public notebook outputs and save the shortest verified programs."""

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory

from sync_santa_answers import (
    ROOT, UPSTREAM, download_notebook, load_programs, load_puzzles, save_verified, score,
)

NOTEBOOK = "goodpjw2008/santa-2026-lns-cp-sat-recombine-lb-132-256"
OUTPUT = ROOT / "out" / "goodpjw" / "submission.csv"
FILES = ("submission.csv", "submission_live_merge.csv")


def restore(notebook):
    puzzles = load_puzzles(UPSTREAM / "data" / "puzzles.csv")
    best = {}
    with TemporaryDirectory() as directory:
        download_notebook(notebook, Path(directory))
        for filename in FILES:
            path = Path(directory) / filename
            if not path.is_file():
                continue
            candidate = load_programs(path)
            print(f"{filename}: {score(puzzles, candidate):,} instructions", flush=True)
            for puzzle_id, program in candidate.items():
                if puzzle_id not in best or len(program) < len(best[puzzle_id]):
                    best[puzzle_id] = program
    if not best:
        raise SystemExit(f"No submission CSVs found in the public output of {notebook}")
    total = save_verified(OUTPUT, puzzles, best)
    print(f"{OUTPUT}: {total:,} verified instructions ({notebook})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notebook", default=NOTEBOOK, help="Kaggle notebook ref")
    restore(parser.parse_args().notebook)
