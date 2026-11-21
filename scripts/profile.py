"""Profile data files without reading them whole.

Usage: python profile.py <folder-or-file> [--sample 5]

Per table: file size, row count, columns with type, null % and distinct count
(computed on the first 20,000 rows) and a few sample rows.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (SAMPLE_ROWS, build_tables, duck_connect, find_files, human_size,  # noqa: E402
                     pandas_count, pandas_load, qi, show, use_duckdb, utf8_stdout)


def column_stats(sample, types):
    import pandas as pd
    rows = []
    n = len(sample)
    for i, col in enumerate(sample.columns):
        s = sample.iloc[:, i]
        try:
            distinct = s.nunique(dropna=True)
        except TypeError:  # unhashable values (nested JSON)
            distinct = s.dropna().astype(str).nunique()
        null_pct = 100.0 * s.isna().sum() / n if n else 0.0
        rows.append({"column": col, "type": types[i], "null%": f"{null_pct:.1f}",
                     "distinct": distinct})
    return pd.DataFrame(rows)


def profile_table(t, con, nsample):
    if con is not None:
        name = qi(t["name"])
        total = con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
        types = [r[1] for r in con.execute(f"DESCRIBE {name}").fetchall()]
        sample = con.execute(f"SELECT * FROM {name} LIMIT {SAMPLE_ROWS}").df()
    else:
        sample = pandas_load(t, nrows=SAMPLE_ROWS)
        total = pandas_count(t) if len(sample) >= SAMPLE_ROWS else len(sample)
        types = [str(d) for d in sample.dtypes]

    scope = "all rows" if len(sample) >= total else f"first {len(sample):,} rows"
    print(f"rows: {total:,} | columns: {sample.shape[1]} | stats on {scope}")
    print(show(column_stats(sample, types), width=60))
    print(f"\nsample rows ({min(nsample, len(sample))}):")
    print(show(sample.head(nsample)))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", help="folder or data file")
    ap.add_argument("--sample", type=int, default=5, help="sample rows to show (default 5)")
    args = ap.parse_args()
    utf8_stdout()

    tables = build_tables(find_files(args.target))
    duck = use_duckdb()
    print(f"engine: {'duckdb' if duck else 'pandas'} | {len(tables)} table(s)\n")
    con = duck_connect(tables) if duck else None

    for t in tables:
        src = os.path.basename(t["path"])
        if t["sheet"] is not None:
            src += f", sheet '{t['sheet']}'"
        print(f"== {t['name']}  ({src}, {human_size(os.path.getsize(t['path']))}) ==")
        try:
            profile_table(t, con, args.sample)
        except Exception as e:
            print(f"ERROR: {type(e).__name__}: {str(e)[:500]}")
        print()


if __name__ == "__main__":
    main()
