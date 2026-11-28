"""Find complete, valid Santa 2026 answer CSVs on Kaggle."""

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from zipfile import BadZipFile, ZipFile

from discover_santa_discussion import OUTPUT as DISCUSSION_REPORT

from sync_santa_answers import (
    DISCOVERED, OUTPUT, ROOT, KaggleRateLimited, KaggleSourceForbidden, KaggleSourceNotFound,
    download_archive, download_notebook,
    load_puzzles, load_references, merge_archive_csvs, read_valid_csv,
)


def search_results(command):
    for delay in (15, 30, 0):
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        if result.returncode and delay and "429 Client Error" in result.stderr + result.stdout:
            print(f"Kaggle search rate limited; retrying in {delay}s.", file=sys.stderr, flush=True)
            time.sleep(delay)
            continue
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="")
        result.check_returncode()
        return json.JSONDecoder().raw_decode(result.stdout.lstrip())[0]


def search_datasets():
    results = {}
    for phrase in ("Santa 2026", "Elf Calculator"):
        response = search_results(
            ["kaggle", "datasets", "list", "-s", phrase,
             "--sort-by", "updated", "--format", "json"],
        )
        for item in response:
            results[item["ref"]] = item["lastUpdated"]
    return sorted(results, key=results.get, reverse=True)


def search_notebooks(limit, sort_by):
    response = search_results(
        ["kaggle", "kernels", "list", "--competition", "santa-2026",
         "--sort-by", sort_by, "--page-size", str(limit),
         "--format", "json"],
    )
    return {item["ref"]: item.get("lastRunTime") for item in response}


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


def inspect_notebook(notebook, puzzles, scratch):
    with TemporaryDirectory(dir=scratch.parent) as directory:
        path = Path(directory)
        download_notebook(notebook, path)
        candidates = {}
        for file in sorted(path.rglob("*")):
            if not file.is_file() or file.suffix.lower() != ".csv":
                continue
            raw = file.read_bytes()
            programs = read_valid_csv(raw, puzzles, scratch)
            if programs is not None:
                filename = file.relative_to(path).as_posix()
                candidates[f"notebook:{notebook}:{filename}"] = {
                    "notebook": notebook,
                    "file": filename,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "instructions": sum(map(len, programs.values())),
                }
        return candidates


def inspect_dataset(dataset, puzzles, scratch):
    archive_path = download_archive(dataset.replace("/", "--"), dataset)
    try:
        with ZipFile(archive_path) as archive:
            merged = merge_archive_csvs(archive, puzzles, scratch)
    except BadZipFile:
        archive_path.unlink(missing_ok=True)
        raise
    if merged is None:
        return None
    filenames, total = merged
    return {
        "dataset": dataset,
        "file": filenames[0],
        "files": filenames,
        "sha256": hashlib.sha256(scratch.read_bytes()).hexdigest(),
        "instructions": total,
    }


def discover(limit):
    known = {ref["dataset"] for ref in load_references().values() if "dataset" in ref}
    discussion_datasets, discussion_notebooks = discussion_references()
    datasets = [
        dataset for dataset in dict.fromkeys(discussion_datasets + search_datasets())
        if dataset not in known
    ]
    recent = search_notebooks(limit, "dateRun")
    top = search_notebooks(limit, "scoreAscending")
    ordered = [ref for pair in zip(recent, top) for ref in pair]
    notebooks = list(dict.fromkeys(discussion_notebooks + ordered + list(recent) + list(top)))
    notebook_dates = top | recent
    puzzles = load_puzzles(ROOT / "data/puzzles.csv")
    discovered = json.loads(DISCOVERED.read_text()) if DISCOVERED.exists() else {}
    added = failures = 0
    limited = False
    with TemporaryDirectory(dir=OUTPUT) as directory:
        scratch = Path(directory) / "candidate.csv"
        for dataset in datasets[:limit]:
            try:
                candidate = inspect_dataset(dataset, puzzles, scratch)
            except (KaggleSourceForbidden, KaggleSourceNotFound) as error:
                print(f"{dataset}: {error}; skipping source.", file=sys.stderr, flush=True)
                continue
            except KaggleRateLimited as error:
                print(f"{dataset}: {error}; using verified discovery results so far.", file=sys.stderr)
                limited = True
                break
            except (OSError, ValueError, BadZipFile, subprocess.SubprocessError) as error:
                print(f"{dataset}: {error}", file=sys.stderr, flush=True)
                failures += 1
                continue
            if candidate is None:
                print(f"{dataset}: no valid complete answer CSV", flush=True)
                continue
            discovered[dataset] = candidate
            added += 1
            print(f"{dataset}: {len(candidate['files'])} verified CSV(s) ({candidate['instructions']} instructions)", flush=True)
        changed = bool(added)
        for notebook in notebooks[:limit]:
            if limited:
                break
            try:
                candidates = inspect_notebook(notebook, puzzles, scratch)
            except (KaggleSourceForbidden, KaggleSourceNotFound) as error:
                print(f"{notebook}: {error}; skipping source.", file=sys.stderr, flush=True)
                continue
            except KaggleRateLimited as error:
                print(f"{notebook}: {error}; using verified discovery results so far.", file=sys.stderr)
                break
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                print(f"{notebook}: {error}", file=sys.stderr, flush=True)
                failures += 1
                continue
            for name, candidate in candidates.items():
                if notebook_dates.get(notebook):
                    candidate["last_run_at"] = notebook_dates[notebook]
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
