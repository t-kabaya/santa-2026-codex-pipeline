"""Restore configured Santa answer sources."""

import argparse
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from sync_santa_answers import (
    ROOT, download_notebook, load_programs, load_puzzles, load_restore_sources,
    restore_output, save_verified, score,
)


def restore_notebook(notebook, filenames, output):
    puzzles = load_puzzles(ROOT / "data" / "puzzles.csv")
    best = {}
    with TemporaryDirectory() as directory:
        download_notebook(notebook, Path(directory))
        for filename in filenames:
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
    total = save_verified(output, puzzles, best)
    print(f"{output}: {total:,} verified instructions ({notebook})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sources = load_restore_sources()
    parser.add_argument("--source", choices=sources, help="Restore only this source")
    args = parser.parse_args()
    selected = [args.source] if args.source else sources
    for name in selected:
        source = sources[name]
        if "script" in source:
            subprocess.run([sys.executable, str(ROOT / source["script"])], check=True, cwd=ROOT)
        else:
            notebook = os.environ.get(source.get("notebook_env", "")) or source["notebook"]
            restore_notebook(notebook, source["files"], restore_output(name))
