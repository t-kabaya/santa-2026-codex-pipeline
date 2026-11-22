"""Find complete, valid Santa 2026 answer CSVs on Kaggle."""

import argparse
import csv
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from zipfile import BadZipFile, ZipFile

from discover_santa_discussion import OUTPUT as DISCUSSION_REPORT

from sync_santa_answers import (
    DISCOVERED, OUTPUT, ROOT, download_archive, download_notebook, load_puzzles,
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


def search_notebooks(limit):
    response = subprocess.check_output(
        ["kaggle", "kernels", "list", "--competition", "santa-2026",
         "--sort-by", "scoreAscending", "--page-size", str(limit),
         "--format", "json"],
        timeout=60,
    )
    return list(dict.fromkeys(item["ref"] for item in json.loads(response)))


def discussion_references():
    datasets, notebooks = [], []
    if not DISCUSSION_REPORT.exists():
        return datasets, notebooks
    for topic in json.loads(DISCUSSION_REPORT.read_text(encoding="utf-8")):
        for link in topic.get("links", []):
            parsed = urlsplit(link["url"])
            if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"www.kaggle.com", "kaggle.com"}:
                continue
            match = re.match(r"^/(datasets|code)/([\w-]+/[\w-]+)(?:/|$)", parsed.path, re.ASCII)
            if match:
                section, ref = match.groups()
                (datasets if section == "datasets" else notebooks).append(ref.lower())
    return datasets, notebooks


def validate_csv(raw, puzzles, scratch):
    header = raw[:4096].splitlines()[0:1]
    if not header:
        return None
    fields = next(csv.reader([header[0].decode("utf-8-sig", errors="replace")]))
    if not {"id", "program"}.issubset(fields):
        return None
    scratch.write_bytes(raw)
    try:
        return score(puzzles, load_programs(scratch, reference=True))
    except (ValueError, TypeError, KeyError, csv.Error):
        return None


def inspect_notebook(notebook, puzzles, scratch):
    with TemporaryDirectory(dir=scratch.parent) as directory:
        path = Path(directory)
        download_notebook(notebook, path)
        candidates = {}
        for file in sorted(path.rglob("*")):
            if not file.is_file() or file.suffix.lower() != ".csv":
                continue
            raw = file.read_bytes()
            total = validate_csv(raw, puzzles, scratch)
            if total is not None:
                filename = file.relative_to(path).as_posix()
                candidates[f"notebook:{notebook}:{filename}"] = {
                    "notebook": notebook,
                    "file": filename,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "instructions": total,
                }
        return candidates


def inspect_dataset(dataset, puzzles, scratch):
    archive_path = download_archive(dataset.replace("/", "--"), dataset)
    best = None
    try:
        with ZipFile(archive_path) as archive:
            for entry in archive.infolist():
                if not entry.filename.lower().endswith(".csv"):
                    continue
                raw = archive.read(entry)
                total = validate_csv(raw, puzzles, scratch)
                if total is None:
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
    known = {ref["dataset"] for ref in load_references().values() if "dataset" in ref}
    discussion_datasets, discussion_notebooks = discussion_references()
    datasets = [
        dataset for dataset in dict.fromkeys(discussion_datasets + search_datasets())
        if dataset not in known
    ]
    notebooks = list(dict.fromkeys(discussion_notebooks + search_notebooks(limit)))
    puzzles = load_puzzles(ROOT / "data/puzzles.csv")
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
        changed = bool(added)
        for notebook in notebooks[:limit]:
            try:
                candidates = inspect_notebook(notebook, puzzles, scratch)
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                print(f"{notebook}: {error}", file=sys.stderr, flush=True)
                failures += 1
                continue
            for name, candidate in candidates.items():
                if discovered.get(name) != candidate:
                    added += name not in discovered
                    discovered[name] = candidate
                    changed = True
                    print(f"{name}: {candidate['instructions']} instructions", flush=True)
        if changed:
            scratch.write_text(json.dumps(discovered, indent=2) + "\n")
            os.replace(scratch, DISCOVERED)
    print(f"{added} references added to {DISCOVERED}", flush=True)
    return bool(failures)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=30, help="Maximum datasets and notebooks to inspect, per source type")
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
