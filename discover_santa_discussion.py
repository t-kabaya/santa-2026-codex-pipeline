"""List Santa 2026 Discussion posts and links to potential answer sources."""

import argparse
import html
import json
from pathlib import Path
import re
import subprocess
import sys
from tempfile import NamedTemporaryFile
from urllib.parse import unquote, urlsplit

COMPETITION = "santa-2026"
DISCUSSION = f"https://www.kaggle.com/competitions/{COMPETITION}/discussion"
OUTPUT = Path(__file__).resolve().parent / "out" / "santa-discussion" / "candidates.json"
URL = re.compile(r'https?://[^\s<>"\']+')


def kaggle(*args):
    return subprocess.check_output(
        ["kaggle", "competitions", "topics", *args], text=True, timeout=120
    )


def cli_json(output):
    # The CLI may append a pagination token after the JSON.
    return json.JSONDecoder().raw_decode(output.lstrip())[0]


def candidate_links(content):
    for match in URL.finditer(html.unescape(content)):
        url = match.group().rstrip(".,;:!?")
        while url.endswith(")") and url.count(")") > url.count("("):
            url = url[:-1]
        try:
            parsed = urlsplit(url)
        except ValueError:
            continue
        path = unquote(parsed.path).lower()
        host = parsed.hostname
        if host in {"kaggle.com", "www.kaggle.com"} and path.startswith("/datasets/"):
            kind = "dataset"
        elif host in {"kaggle.com", "www.kaggle.com"} and path.startswith("/code/"):
            kind = "notebook"
        elif path.endswith((".csv", ".csv.gz")):
            kind = "csv"
        elif host in {"github.com", "www.github.com", "raw.githubusercontent.com"}:
            kind = "github"
        else:
            continue
        yield url, kind


def inspect_topic(topic):
    topic_id = str(topic["id"])
    args = ("show", COMPETITION, topic_id)
    result = cli_json(kaggle(*args, "--format", "json"))
    body = result.get("topic", {}).get("content")
    if body is None:
        body = kaggle(*args, "--format", "table").partition("\nComments:\n")[0]
    sources = [("post", body)]
    sources.extend(
        (f"comment:{comment['id']}", comment.get("content") or "")
        for comment in result.get("comments", [])
    )
    links = {}
    for source, content in sources:
        for url, kind in candidate_links(content):
            entry = links.setdefault(url, {"url": url, "kind": kind, "sources": []})
            if source not in entry["sources"]:
                entry["sources"].append(source)
    return list(links.values())


def discover(limit):
    topics = cli_json(kaggle("list", COMPETITION, "--sort-by", "new", "--format", "json"))
    recent = sorted(topics, key=lambda topic: topic.get("postDate") or "", reverse=True)
    report = []
    failures = 0
    for topic in recent[:limit]:
        entry = {**topic, "url": f"{DISCUSSION}/{topic['id']}", "links": []}
        try:
            entry["links"] = inspect_topic(topic)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            entry["error"] = str(error)
            failures += 1
            print(f"{entry['url']}: {error}", file=sys.stderr)
        report.append(entry)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=OUTPUT.parent, delete=False) as file:
        path = Path(file.name)
        json.dump(report, file, ensure_ascii=False, indent=2)
        file.write("\n")
    path.replace(OUTPUT)
    count = sum(len(entry["links"]) for entry in report)
    print(f"{len(report)} topics, {count} candidate links: {OUTPUT}")
    return bool(failures)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=20, help="Maximum recent topics to inspect")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")
    sys.exit(discover(args.limit))
