"""Find public Kaggle datasets with a complete, valid Santa 2026 answer CSV."""

import argparse
import csv
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import BadZipFile, ZipFile

from sync_santa_answers import (
    DISCOVERED, OUTPUT, UPSTREAM, download_archive, load_puzzles,
    load_programs, load_references, score,
)


def search_datasets():
    results = {}
    for phrase in ("Santa 2026", "Elf Calculator"):
        response = subprocess.check_output(
            ["kaggle", "datasets", "list", "-s", phrase,
             "--sort-by", "updated", "--format", "json"],
            timeout=60,
        )
        for item in json.loads(response):
            results[item["ref"]] = item["lastUpdated"]
    return sorted(results, key=results.get, reverse=True)


def inspect_dataset(dataset, puzzles, scratch):
    archive_path = download_archive(dataset.replace("/", "--"), dataset)
    best = None
    try:
        with ZipFile(archive_path) as archive:
            for entry in archive.infolist():
                if not entry.filename.lower().endswith(".csv"):
                    continue
                with archive.open(entry) as stream:
                    header = stream.readline(4096).decode("utf-8-sig", errors="replace")
                if not {"id", "program"}.issubset(next(csv.reader([header]), [])):
                    continue
                raw = archive.read(entry)
                scratch.write_bytes(raw)
                try:
                    total = score(puzzles, load_programs(scratch, reference=True))
                except (ValueError, TypeError, KeyError, csv.Error):
                    continue
                if best is None or total < best["instructions"]:
                    best = {
                        "dataset": dataset,
                        "file": entry.filename,
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "instructions": total,
                    }
    except BadZipFile:
        archive_path.unlink(missing_ok=True)
        raise
    return best


def discover(limit):
    known = {ref["dataset"] for ref in load_references().values()}
    datasets = [dataset for dataset in search_datasets() if dataset not in known]
    puzzles = load_puzzles(UPSTREAM / "data/puzzles.csv")
    discovered = json.loads(DISCOVERED.read_text()) if DISCOVERED.exists() else {}
    added = failures = 0
    with TemporaryDirectory(dir=OUTPUT) as directory:
        scratch = Path(directory) / "candidate.csv"
        for dataset in datasets[:limit]:
            try:
                candidate = inspect_dataset(dataset, puzzles, scratch)
            except (OSError, ValueError, BadZipFile, subprocess.SubprocessError) as error:
                print(f"{dataset}: {error}", file=sys.stderr, flush=True)
                failures += 1
                continue
            if candidate is None:
                print(f"{dataset}: no valid complete answer CSV", flush=True)
                continue
            discovered[dataset] = candidate
            added += 1
            print(f"{dataset}: {candidate['file']} ({candidate['instructions']} instructions)", flush=True)
        if added:
            scratch.write_text(json.dumps(discovered, indent=2) + "\n")
            os.replace(scratch, DISCOVERED)
    print(f"{added} references added to {DISCOVERED}", flush=True)
    return bool(failures)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=30, help="Maximum new datasets to inspect")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with (OUTPUT / "sync.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            sys.exit("Another discovery or sync is running")
        sys.exit(discover(args.limit))
