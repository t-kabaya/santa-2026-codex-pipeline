"""Restore Hansen's published 132,513-instruction portfolio from pinned inputs."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent
REPOSITORY = "https://github.com/Hansen0223/Santa_2026.git"
REVISION = "a8338d35791de45e3b225dc6304023cf4b391d7b"
OUTPUT = ROOT / "out" / "hansen"
UPSTREAM = OUTPUT / "upstream"
RELEASE = Path("public-assisted/releases")


def run(*args, cwd=ROOT):
    subprocess.run(args, cwd=cwd, check=True, timeout=300)


def fetch_commit(revision):
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{revision}^{{commit}}"], cwd=UPSTREAM,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if result.returncode:
        run("git", "fetch", "--depth", "1", REPOSITORY, revision, cwd=UPSTREAM)


def fetch_file(destination, digest, command, downloaded_name):
    if destination.is_file() and hashlib.sha256(destination.read_bytes()).hexdigest() == digest:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=destination.parent) as temporary:
        path = Path(temporary)
        run(*command, "-p", str(path))
        downloaded = path / downloaded_name
        if hashlib.sha256(downloaded.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Unexpected SHA-256 for {destination.name}")
        downloaded.replace(destination)


def restore():
    UPSTREAM.mkdir(parents=True, exist_ok=True)
    if not (UPSTREAM / ".git").exists():
        run("git", "init", cwd=UPSTREAM)
    fetch_commit(REVISION)
    run("git", "switch", "--detach", REVISION, cwd=UPSTREAM)
    manifest = json.loads((UPSTREAM / RELEASE / "portfolio.json").read_text())
    archives = OUTPUT / "archives"
    puzzles = OUTPUT / "official" / "puzzles.csv"

    fetch_file(
        puzzles, manifest["puzzles_sha256"],
        ["kaggle", "competitions", "download", "santa-2026", "-f", "puzzles.csv", "-q"],
        "puzzles.csv",
    )
    for source in manifest["sources"]:
        if "revision" in source:
            fetch_commit(source["revision"])
        elif "archive" in source:
            fetch_file(
                archives / source["archive"], source["archive_sha256"],
                ["kaggle", "datasets", "download",
                 "alexchilton/santa-2026-rudolph-programs/126", "-q"],
                "santa-2026-rudolph-programs.zip",
            )
        elif "notebook" in source:
            destination = archives / source["notebook"]
            if destination.is_file() and hashlib.sha256(destination.read_bytes()).hexdigest() == source["notebook_sha256"]:
                continue
            archives.mkdir(parents=True, exist_ok=True)
            with TemporaryDirectory(dir=archives) as temporary:
                download = Path(temporary) / destination.name
                run("curl", "-fLsS", source["download_url"], "-o", str(download))
                if hashlib.sha256(download.read_bytes()).hexdigest() != source["notebook_sha256"]:
                    raise ValueError(f"Unexpected SHA-256 for {destination.name}")
                download.replace(destination)

    # The pinned upstream tool checks the input hashes, replays every program,
    # and publishes the CSV only if the score and output hash match its manifest.
    run(sys.executable, "-B", str(RELEASE / "portfolio.py"),
        "--puzzles", str(puzzles), "--archives", str(archives), "--out", str(OUTPUT),
        cwd=UPSTREAM)


if __name__ == "__main__":
    restore()
