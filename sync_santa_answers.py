"""Refresh the local Santa submission from Kaggle datasets and notebook outputs."""

import fcntl
import hashlib
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory, mkdtemp
from zipfile import BadZipFile, ZipFile

ROOT = Path(__file__).resolve().parent
UPSTREAM = ROOT / "Hansen-Santa_2026"
OUTPUT = ROOT / "out" / "santa-sync"
DISCOVERED = OUTPUT / "discovered-references.json"
sys.path.insert(0, str(UPSTREAM))

from machine import load_programs, load_puzzles, save_verified, score


def load_references():
    refs = json.loads((UPSTREAM / "references.json").read_text())
    if DISCOVERED.exists():
        refs.update(json.loads(DISCOVERED.read_text()))
    return refs


def download_archive(name, dataset):
    cache = OUTPUT / "downloads" / name
    cache.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["kaggle", "datasets", "download", dataset, "-p", str(cache), "-q"],
        check=True, timeout=300,
    )
    return cache / (dataset.split("/")[-1] + ".zip")


def download_notebook(notebook, directory):
    subprocess.run(
        ["kaggle", "kernels", "output", notebook, "-p", str(directory),
         "--file-pattern", r".*\.[cC][sS][vV]$", "-q"],
        check=True, timeout=300,
    )


def download(name, ref, directory, notebooks):
    if "local" in ref:
        return ref["local"].read_bytes()
    if "notebook" in ref:
        notebook = ref["notebook"]
        if notebook not in notebooks:
            path = Path(mkdtemp(prefix="notebook-", dir=directory))
            download_notebook(notebook, path)
            notebooks[notebook] = path
        try:
            return (notebooks[notebook] / ref["file"]).read_bytes()
        except FileNotFoundError:
            return None
    archive_path = download_archive(name.replace("/", "--"), ref["dataset"])
    try:
        with ZipFile(archive_path) as archive:
            return archive.read(ref["file"])
    except BadZipFile:
        archive_path.unlink(missing_ok=True)
        raise


def sync():
    refs = load_references()
    hansen = ROOT / "out" / "hansen" / "submission.csv"
    if hansen.is_file():
        refs["hansen:portfolio"] = {"local": hansen}
    puzzles = load_puzzles(UPSTREAM / "data/puzzles.csv")
    destination = OUTPUT / "submission.csv"
    baseline = destination if destination.exists() else UPSTREAM / "out/public.csv"
    best = load_programs(baseline)
    original_score = score(puzzles, best)
    state = OUTPUT / "hashes.json"
    hashes = json.loads(state.read_text()) if destination.exists() and state.exists() else {}
    failures = 0
    with TemporaryDirectory(dir=OUTPUT) as directory:
        scratch = Path(directory) / "candidate.csv"
        notebooks = {}
        for name, ref in refs.items():
            try:
                raw = download(name, ref, directory, notebooks)
                if raw is None:
                    print(f"{name}: absent from the latest notebook output", flush=True)
                    continue
                digest = hashlib.sha256(raw).hexdigest()
                if digest == hashes.get(name):
                    continue
                scratch.write_bytes(raw)
                candidate = load_programs(scratch, reference=True)
                score(puzzles, candidate)
                improved = 0
                for puzzle_id, program in candidate.items():
                    if len(program) < len(best[puzzle_id]):
                        best[puzzle_id] = program
                        improved += 1
                hashes[name] = digest
                print(f"{name}: verified, {improved} improvements", flush=True)
            except (OSError, ValueError, TypeError, KeyError, csv.Error, BadZipFile, subprocess.SubprocessError) as error:
                failures += 1
                print(f"{name}: {error}", file=sys.stderr, flush=True)
        total = save_verified(destination, puzzles, best)
        scratch.write_text(json.dumps(hashes, indent=2) + "\n")
        os.replace(scratch, state)
    print(f"{destination}: {original_score} -> {total} instructions", flush=True)
    return bool(failures)


if __name__ == "__main__":
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with (OUTPUT / "sync.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            sys.exit("Another sync is running")
        sys.exit(sync())
