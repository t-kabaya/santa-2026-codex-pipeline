"""Validate a Santa 2026 submission and print its total instruction count."""

import argparse

from machine import load_programs, load_puzzles, score


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["verify"])
    parser.add_argument("puzzles")
    parser.add_argument("submission")
    args = parser.parse_args()
    print(score(load_puzzles(args.puzzles), load_programs(args.submission)))


if __name__ == "__main__":
    main()
