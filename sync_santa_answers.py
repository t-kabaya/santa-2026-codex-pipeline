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
OUTPUT = ROOT / "out" / "santa-sync"
DISCOVERED = OUTPUT / "discovered-references.json"

from machine import load_programs, load_puzzles, save_verified, score


class KaggleRateLimited(Exception):
    pass


def kaggle_download(*args):
    result = subprocess.run(["kaggle", *args], capture_output=True, text=True, timeout=300)
    if result.returncode and "429 Client Error" in result.stderr + result.stdout:
        raise KaggleRateLimited("Kaggle download rate limit reached")
    if result.stdout:
        print(result.stdout, end="", flush=True)
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr, flush=True)
    result.check_returncode()


def load_restore_sources():
    return json.loads((ROOT / "restore_sources.json").read_text(encoding="utf-8"))


def restore_output(name):
    return ROOT / "out" / name / "submission.csv"


def load_references():
    refs = json.loads((ROOT / "references.json").read_text())
    if DISCOVERED.exists():
        refs.update(json.loads(DISCOVERED.read_text()))
    return refs


def download_archive(name, dataset):
    cache = OUTPUT / "downloads" / name
    cache.mkdir(parents=True, exist_ok=True)
    kaggle_download("datasets", "download", dataset, "-p", str(cache), "-q")
    return cache / (dataset.split("/")[-1] + ".zip")


def download_notebook(notebook, directory):
    kaggle_download("kernels", "output", notebook, "-p", str(directory),
                    "--file-pattern", r".*\.[cC][sS][vV]$", "-q")


def read_valid_csv(raw, puzzles, scratch):
    first_line = raw[:4096].splitlines()[:1]
    if not first_line:
        return None
    try:
        fields = next(csv.reader([first_line[0].decode("utf-8-sig")]), [])
        if not {"id", "program"}.issubset(fields):
            return None
        scratch.write_bytes(raw)
        programs = load_programs(scratch, reference=True)
        score(puzzles, programs)
        return programs
    except (ValueError, TypeError, KeyError, csv.Error):
        return None


def merge_archive_csvs(archive, puzzles, scratch, preferred=None):
    best = {}
    filenames = []
    entries = sorted(archive.infolist(), key=lambda entry: entry.filename != preferred)
    for entry in entries:
        if not entry.filename.lower().endswith(".csv"):
            continue
        raw = archive.read(entry)
        programs = read_valid_csv(raw, puzzles, scratch)
        if programs is None:
            continue
        filenames.append(entry.filename)
        for puzzle_id, program in programs.items():
            if puzzle_id not in best or len(program) < len(best[puzzle_id]):
                best[puzzle_id] = program
    if not filenames:
        return None
    total = save_verified(scratch, puzzles, best)
    return filenames, total


def download(name, ref, puzzles, scratch, notebooks):
    if "local" in ref:
        return ref["local"].read_bytes()
    if "notebook" in ref:
        notebook = ref["notebook"]
        if notebook not in notebooks:
            path = Path(mkdtemp(prefix="notebook-", dir=scratch.parent))
            download_notebook(notebook, path)
            notebooks[notebook] = path
        try:
            return (notebooks[notebook] / ref["file"]).read_bytes()
        except FileNotFoundError:
            print(f"{name}: absent from the latest notebook output", flush=True)
            return None
    archive_path = download_archive(name.replace("/", "--"), ref["dataset"])
    try:
        with ZipFile(archive_path) as archive:
            merged = merge_archive_csvs(archive, puzzles, scratch, preferred=ref["file"])
            if merged is None:
                print(f"{name}: no valid answer CSV was found", file=sys.stderr, flush=True)
                return None
            filenames, total = merged
            print(f"{name}: merged {len(filenames)} verified CSV(s) ({total:,} instructions)", flush=True)
            return scratch.read_bytes()
    except BadZipFile:
        archive_path.unlink(missing_ok=True)
        raise


def sync():
    refs = load_references()
    for name in load_restore_sources():
        path = restore_output(name)
        if path.is_file():
            refs[f"{name}:portfolio"] = {"local": path}
    puzzles = load_puzzles(ROOT / "data/puzzles.csv")
    destination = OUTPUT / "submission.csv"
    baseline = destination if destination.exists() else ROOT / "out/public.csv"
    if not baseline.exists():
        baseline = ROOT / "data/sample_submission.csv"
    best = load_programs(baseline)
    original_score = score(puzzles, best)
    state = OUTPUT / "hashes.json"
    hashes = json.loads(state.read_text()) if destination.exists() and state.exists() else {}
    failures = 0
    limited = False
    with TemporaryDirectory(dir=OUTPUT) as directory:
        scratch = Path(directory) / "candidate.csv"
        notebooks = {}
        for name, ref in refs.items():
            if limited and "local" not in ref:
                continue
            try:
                raw = download(name, ref, puzzles, scratch, notebooks)
                if raw is None:
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
            except KaggleRateLimited:
                print(f"{name}: Kaggle rate limit reached; keeping the verified portfolio and checking local candidates.", file=sys.stderr, flush=True)
                limited = True
            except (OSError, ValueError, TypeError, KeyError, csv.Error, BadZipFile, subprocess.SubprocessError) as error:
                failures += 1
                print(f"{name}: {error}", file=sys.stderr, flush=True)
        total = save_verified(destination, puzzles, best)
        scratch.write_text(json.dumps(hashes, indent=2) + "\n")
        os.replace(scratch, state)
        scratch.write_text(json.dumps({
            "previous_instructions": original_score,
            "instructions": total,
            "instructions_saved": original_score - total,
        }, indent=2) + "\n")
        os.replace(scratch, OUTPUT / "scores.json")
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
