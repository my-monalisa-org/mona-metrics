"""Run with python3 -m mona_metrics from the repository root."""

import argparse
import csv
import json
import sys
from pathlib import Path

from .analytics import DataError, analyze, markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mona's synthetic cafe analytics")
    parser.add_argument("command", choices=("report", "check"))
    parser.add_argument("--data", type=Path, default=Path("data/daily.csv"))
    parser.add_argument("--config", type=Path, default=Path("data/cafes.json"))
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args(argv)
    try:
        report = analyze(args.data, args.config)
    except (DataError, OSError, UnicodeError, json.JSONDecodeError, csv.Error) as error:
        print(f"mona-metrics: {error}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    else:
        print(markdown(report), end="")
    return 1 if args.command == "check" and report["warnings"] else 0


if __name__ == "__main__":
    sys.exit(main())
