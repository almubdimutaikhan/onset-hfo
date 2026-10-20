"""`onset-hfo report-problem`: the same report as the window's, from a terminal.

The window's *Help → Report a problem* shows every file before it saves
anything. This is that, for someone running the command line tools: it prints
the exact text that would be saved, and writes the zip only when you say so.

What a command line report holds is deliberately small: the versions of the
software and its libraries, a description of the machine, and the sentence you
write with ``--note``. It holds no signal, no recording name, no log and no
screenshot, because a command line tool has none of those to offer and a
report should not go looking for them. Nothing is sent anywhere; you send the
file.

    onset-hfo report-problem --note "run --synthetic stops at the figures"

Qt-free, so it works on the base install.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from onset_review import applog

__all__ = ["main", "run", "build_parser", "add_arguments"]


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """The options of the report, on any parser: this module's own and the
    `onset-hfo report-problem` subcommand's, so they cannot drift apart."""
    parser.add_argument("--note", default="",
                        help="what you did, what you expected, and what happened instead")
    parser.add_argument("--out", type=Path, default=None, metavar="FILE.zip",
                        help="where to save it (default: ./onset-hfo-report-<time>.zip)")
    parser.add_argument("--yes", action="store_true",
                        help="save without asking; the text is still printed first")


def build_parser(prog: str = "onset-hfo report-problem") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Show a problem report for you to read, and save it as a zip if you "
                    "agree. It holds versions, this machine's description and your note: "
                    "no signal, no recording names, no log. Nothing is sent anywhere.")
    add_arguments(parser)
    return parser


def run(args: argparse.Namespace) -> int:
    """Show the report, then save it if the person agrees (or said `--yes`)."""
    bundle = applog.build_bundle(args.note, with_logs=False)
    out = args.out or Path(f"onset-hfo-report-{time.strftime('%Y%m%d-%H%M')}.zip")

    print("This report would contain:")
    for row in bundle.manifest():
        print(f"  {row['name']}  ({row['lines']} lines, {row['bytes']} bytes)")
    print("\n" + "-" * 60)
    for name, text in bundle.files.items():
        print(f"[{name}]\n{text}")
    print("-" * 60)

    if not args.yes:
        try:
            answer = input(f"Save this to {out}? [y/N] ").strip().lower()
        except EOFError:       # no terminal to ask: the safe answer is no
            answer = ""
        if answer not in ("y", "yes"):
            print("Nothing was saved.")
            return 0
    written = applog.write_bundle(bundle, out)
    print(f"Saved to {written}. Send this file; nothing has been sent.")
    return 0


def main(argv: list[str] | None = None, prog: str = "onset-hfo report-problem") -> int:
    return run(build_parser(prog).parse_args(argv))


if __name__ == "__main__":      # pragma: no cover
    sys.exit(main())
