"""Run SQL over data files and print a small result.

Usage: python query.py <folder-or-file> "SELECT ..." [--limit 50] [--out result.csv]

Each file is a table named after the file (sales_2024.csv -> sales_2024).
Prints at most --limit rows. With --out, the full result is written to a CSV file
and only its path, row count and first rows are printed.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (build_tables, describe_tables, duck_connect, find_files, show,  # noqa: E402
                     sq, sqlite_connect, use_duckdb, utf8_stdout)


def to_df(cursor, rows):
    import pandas as pd
    cols = [d[0] for d in cursor.description] if cursor.description else []
    return pd.DataFrame.from_records(rows, columns=cols)


def write_out(con, duck, sql, out):
    import pandas as pd
    if duck:
        con.execute(f"COPY ({sql}) TO {sq(out.replace(chr(92), '/'))} (HEADER, DELIMITER ',')")
    else:
        cur = con.execute(sql)
        to_df(cur, cur.fetchall()).to_csv(out, index=False)
    with open(out, "rb") as f:
        n = max(sum(1 for _ in f) - 1, 0)  # approximate if values contain newlines
    preview = pd.read_csv(out, nrows=5)
    print(f"saved {n:,} row(s) to {os.path.abspath(out)}")
    print(show(preview))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", help="folder or data file")
    ap.add_argument("sql", help="SQL query; tables are named after the files")
    ap.add_argument("--limit", type=int, default=50, help="max rows printed (default 50)")
    ap.add_argument("--out", help="write the full result to this CSV file")
    args = ap.parse_args()
    utf8_stdout()

    sql = args.sql.strip().rstrip(";").strip()
    tables = build_tables(find_files(args.target))
    duck = use_duckdb()
    start = time.time()
    con = duck_connect(tables) if duck else sqlite_connect(tables)

    try:
        if args.out:
            write_out(con, duck, sql, args.out)
        else:
            cur = con.execute(sql)
            rows = cur.fetchmany(args.limit + 1)
            df = to_df(cur, rows[: args.limit])
            print(show(df))
            if len(rows) > args.limit:
                try:
                    total = con.execute(f"SELECT count(*) FROM ({sql}) AS q").fetchone()[0]
                    more = f"{total:,} rows in total"
                except Exception:
                    more = "more rows exist"
                print(f"\n(showing first {args.limit}; {more}. "
                      f"Aggregate further or use --out to save all.)")
            else:
                print(f"\n({len(df)} row(s))")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {str(e)[:800]}", file=sys.stderr)
        print("Tables:\n" + describe_tables(tables, con, duck), file=sys.stderr)
        sys.exit(1)

    print(f"[{'duckdb' if duck else 'pandas+sqlite'}, {time.time() - start:.2f}s]")


if __name__ == "__main__":
    main()
