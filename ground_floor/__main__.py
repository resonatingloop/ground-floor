from __future__ import annotations

import argparse
import json
from pathlib import Path

from .ledger import Ledger, LedgerError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ground-floor",
        description="validate an event ledger or locate candidate warrant crossings",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("validate", "crossings"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("ledger", type=Path)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        ledger = Ledger.from_jsonl(args.ledger)
    except (OSError, LedgerError) as error:
        print(f"error: {error}")
        return 1

    if args.command == "validate":
        print(
            json.dumps(
                {
                    "status": "valid",
                    "events": len(ledger.events),
                    "episodes": len({event.episode_id for event in ledger.events}),
                    "propositions": len(
                        {event.proposition_id for event in ledger.events}
                    ),
                },
                sort_keys=True,
            )
        )
        return 0

    for crossing in ledger.crossings():
        print(json.dumps(crossing, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
