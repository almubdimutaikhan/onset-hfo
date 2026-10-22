"""Several readers' verdict files, merged into one table: Qt-free.

A reader's verdicts are saved as one JSON file per window under the reads
folder (`adjudication.store_dir`). That is right for one person at one desk and
wrong for a study: two readers on two machines each produce a file with the
*same name*, so copying them into one folder overwrites one with the other.

This module is the file-based answer, and nothing more. Put each reader's
files anywhere under one folder (a subfolder per reader is the easy way) and

    python -m onset_review.verdictmerge STUDY_FOLDER -o verdicts.csv

reads every `*.json` under it, keeps one row per verdict, and prints who
judged what and how often they agreed. Nothing is written back to a reader's
file, and nothing is deleted: a file that cannot be read is named and skipped.

**Agreement is only computed on events both readers judged.** Events are
matched on their exact key (`adjudication.event_key`: channel, start and
detector), which is identical across machines only when every reader opened
the same window with the same settings. Give every reader the same command.
Verdicts that match nothing are still in the table; they just do not enter an
agreement figure.

**A reader is a name in a folder.** The name each verdict carries is whatever
the reader typed, which can be blank, or the same login name on two machines.
Taken alone, every blank name would be one reader and two people called
`user` would be one, and their verdicts would agree with themselves. So a
reader with no name is told apart by the subfolder their file is in (by the
file itself when it sits at the top), and a name found in two subfolders is
two readers, `name · folder`. The summary says each time it has done either;
put one person's files in one subfolder and give every reader their own name.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from onset_hfo.review import _kappa
from onset_review import adjudication

__all__ = ["collect", "agreement", "summary", "main"]

COLUMNS = ["window", "scope", "key", "reader", "verdict", "at", "note", "source", "name"]

#: How a reader with no name is shown.
UNNAMED = "unnamed"


def collect(folder: str | Path) -> tuple[pd.DataFrame, list[str]]:
    """Every verdict under `folder`, and the files that could not be read.

    One row per (window, scope, key, reader). A reader who judged the same
    thing in two files -- sent twice, or changed their mind between sends --
    keeps the later verdict (the `at` stamp decides, not the file's age).
    `name` is the name as typed; `reader` is who the merge takes them to be
    (see the module's notes), which is what agreement is computed between.
    """
    root = Path(folder)
    rows: list[dict] = []
    unreadable: list[str] = []
    for path in sorted(root.rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or "events" not in data:
                raise ValueError("not a verdict file")
            read = adjudication.Adjudication.from_json(data)
        except (OSError, ValueError):
            unreadable.append(str(path.relative_to(root)))
            continue
        source = str(path.relative_to(root))
        window = read.window or path.stem
        for scope, judged in (("event", read.events), ("channel", read.channels)):
            for key, judgement in judged.items():
                rows.append({"window": window, "scope": scope, "key": key,
                             "reader": "", "verdict": judgement.verdict,
                             "at": judgement.at, "note": judgement.note, "source": source,
                             "name": judgement.reader.strip()})
    table = pd.DataFrame(rows, columns=COLUMNS)
    if table.empty:
        return table, unreadable
    table["reader"] = reader_ids(table)
    table = (table.sort_values("at", kind="stable")
                  .drop_duplicates(["window", "scope", "key", "reader"], keep="last")
                  .sort_values(["window", "scope", "key", "reader"])
                  .reset_index(drop=True))
    return table, unreadable


def _folder(source: str) -> str:
    """The top subfolder a file is in, or "" for a file at the top."""
    parts = Path(source).parts
    return parts[0] if len(parts) > 1 else ""


def reader_ids(table: pd.DataFrame) -> pd.Series:
    """Who each verdict's reader is taken to be: their name, unless it is
    blank (then the folder, or the file at the top) or found in more than one
    folder (then `name · folder`)."""
    folders = table["source"].map(_folder)
    spread = table.assign(folder=folders).groupby("name")["folder"].nunique()
    ids = []
    for name, folder, source in zip(table["name"], folders, table["source"], strict=True):
        if not name:
            ids.append(f"{UNNAMED} · {folder or source}")
        elif spread.get(name, 1) > 1:
            ids.append(f"{name} · {folder or 'top'}")
        else:
            ids.append(name)
    return pd.Series(ids, index=table.index, dtype=object)


def identity_notes(table: pd.DataFrame) -> list[str]:
    """What the merge had to decide about who is who, in plain words."""
    if table.empty:
        return []
    notes = []
    unnamed = sorted(set(table.loc[table["name"] == "", "reader"]))
    if unnamed:
        notes.append(f"{len(unnamed)} reader(s) left their name blank and are told apart by "
                     f"folder or file: {', '.join(unnamed)}.")
    named = table[table["name"] != ""]
    for name, readers in named.groupby("name")["reader"].unique().items():
        if len(readers) > 1:
            notes.append(f"The name {name!r} is in {len(readers)} folders and is counted as "
                         f"{len(readers)} readers ({', '.join(sorted(readers))}). If it is one "
                         "person, put their files in one folder.")
    return notes


def agreement(table: pd.DataFrame) -> pd.DataFrame:
    """Pairwise agreement between readers, on the events both judged.

    `kappa` is Cohen's, over the three verdicts; it is NaN when the two readers
    between them used a single verdict, because agreement is then undefined and
    not perfect. `n` is the number of shared events: read the kappa of five
    events as what it is.
    """
    columns = ["reader_a", "reader_b", "n", "percent_agree", "kappa"]
    events = table[table["scope"] == "event"] if len(table) else table
    if events.empty:
        return pd.DataFrame(columns=columns)
    wide = events.pivot_table(index=["window", "key"], columns="reader",
                              values="verdict", aggfunc="last")
    out = []
    for a, b in itertools.combinations(sorted(wide.columns), 2):
        both = wide[[a, b]].dropna()
        if both.empty:
            out.append({"reader_a": a, "reader_b": b, "n": 0,
                        "percent_agree": float("nan"), "kappa": float("nan")})
            continue
        x, y = both[a].to_numpy(), both[b].to_numpy()
        out.append({"reader_a": a, "reader_b": b, "n": int(len(both)),
                    "percent_agree": round(100.0 * float(np.mean(x == y)), 1),
                    "kappa": round(_kappa(x, y), 3)})
    return pd.DataFrame(out, columns=columns)


def summary(table: pd.DataFrame, unreadable: list[str]) -> str:
    """The plain-text report `main` prints."""
    lines: list[str] = []
    if table.empty:
        lines.append("No verdicts found.")
    else:
        lines.append(f"{len(table)} verdicts from {table['reader'].nunique()} readers "
                     f"in {table['source'].nunique()} files, over "
                     f"{table['window'].nunique()} windows.")
        counts = (table[table["scope"] == "event"]
                  .pivot_table(index="reader", columns="verdict", values="key",
                               aggfunc="count", fill_value=0))
        for verdict in adjudication.EVENT_VERDICTS:
            if verdict not in counts.columns:
                counts[verdict] = 0
        if len(counts):
            lines += ["", "Event verdicts per reader:",
                      counts[list(adjudication.EVENT_VERDICTS)].to_string()]
        notes = identity_notes(table)
        if notes:
            lines += ["", "Who is who:"] + [f"  {note}" for note in notes]
        pairs = agreement(table)
        if len(pairs):
            lines += ["", "Agreement on events both readers judged:", pairs.to_string(index=False)]
        elif table["reader"].nunique() > 1:
            lines += ["", "No pair of readers judged the same event."]
    if unreadable:
        lines += ["", f"{len(unreadable)} file(s) could not be read and were skipped:"]
        lines += [f"  {name}" for name in unreadable]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m onset_review.verdictmerge",
        description="Merge readers' verdict files into one table and report agreement.")
    parser.add_argument("folder", type=Path,
                        help="a folder holding every reader's *.json verdict files")
    parser.add_argument("-o", "--out", type=Path, default=None,
                        help="write the merged table to this CSV")
    args = parser.parse_args(argv)
    if not args.folder.is_dir():
        print(f"not a folder: {args.folder}", file=sys.stderr)
        return 1
    table, unreadable = collect(args.folder)
    print(summary(table, unreadable))
    if args.out is not None:
        table.to_csv(args.out, index=False)
        print(f"\nwritten to {args.out}")
    return 0


if __name__ == "__main__":      # pragma: no cover
    sys.exit(main())
