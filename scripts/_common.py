"""Shared helpers for profile.py and query.py.

Engine: DuckDB when installed (streams files, handles multi-GB data), otherwise
pandas + SQLite (loads files into memory). Set LFA_ENGINE=pandas to force the fallback.
"""
import csv
import json
import os
import re
import sys

DATA_EXTS = {
    ".csv": "csv",
    ".tsv": "tsv",
    ".xlsx": "excel",
    ".xls": "excel",
    ".parquet": "parquet",
    ".json": "json",
    ".jsonl": "jsonl",
}
SAMPLE_ROWS = 20000
CELL_WIDTH = 40


def utf8_stdout():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def use_duckdb():
    if os.environ.get("LFA_ENGINE", "").lower() == "pandas":
        return False
    try:
        import duckdb  # noqa: F401
        return True
    except ImportError:
        return False


def find_files(target):
    if not os.path.exists(target):
        sys.exit(f"Not found: {target}")
    if os.path.isfile(target):
        paths = [target]
    else:
        paths = [os.path.join(target, f) for f in sorted(os.listdir(target))]
    files = [p for p in paths
             if os.path.isfile(p) and os.path.splitext(p)[1].lower() in DATA_EXTS]
    if not files:
        sys.exit(f"No data files ({', '.join(sorted(DATA_EXTS))}) in {target}")
    return files


def clean_name(s):
    name = re.sub(r"[^a-z0-9]", "_", s.lower()) or "t_"
    if name[0].isdigit():
        name = "t_" + name
    return name


def build_tables(files):
    """One table per file; for Excel, one per sheet (first sheet gets the file name)."""
    tables, used = [], set()

    def unique(name):
        base, i = name, 2
        while name in used:
            name = f"{base}_{i}"
            i += 1
        used.add(name)
        return name

    for path in files:
        stem, ext = os.path.splitext(os.path.basename(path))
        kind = DATA_EXTS[ext.lower()]
        base = clean_name(stem)
        if kind == "excel":
            import pandas as pd
            sheets = pd.ExcelFile(path).sheet_names
            for i, sheet in enumerate(sheets):
                name = base if i == 0 else f"{base}_{clean_name(sheet)}"
                tables.append(dict(name=unique(name), path=path, kind=kind, sheet=sheet))
        else:
            tables.append(dict(name=unique(base), path=path, kind=kind, sheet=None))
    return tables


def sniff_text(path, kind):
    """Return (encoding, delimiter) for a CSV/TSV, from its first MB."""
    with open(path, "rb") as f:
        head = f.read(1 << 20)
    if head.startswith(b"\xef\xbb\xbf"):
        enc = "utf-8-sig"
    else:
        enc = "utf-8"
        try:
            head.decode("utf-8")
        except UnicodeDecodeError as e:
            if e.start < len(head) - 4:  # not just a character cut at the 1 MB boundary
                enc = "latin-1"
    if kind == "tsv":
        return enc, "\t"
    text = head.decode(enc, errors="replace")[:65536]
    try:
        delim = csv.Sniffer().sniff(text, delimiters=",;\t|").delimiter
    except csv.Error:
        delim = ","
    return enc, delim


def qi(name):
    return '"' + name.replace('"', '""') + '"'


def sq(s):
    return "'" + s.replace("'", "''") + "'"


def duck_connect(tables):
    import duckdb
    con = duckdb.connect()
    for t in tables:
        name, path, kind = qi(t["name"]), sq(t["path"].replace("\\", "/")), t["kind"]
        if kind in ("csv", "tsv"):
            enc, delim = sniff_text(t["path"], kind)
            opts = f", delim={sq(delim)}"
            if enc == "latin-1":
                opts += ", encoding='latin-1'"
            con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_csv_auto({path}{opts})")
        elif kind == "parquet":
            con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet({path})")
        elif kind == "json":
            con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_json_auto({path})")
        elif kind == "jsonl":
            con.execute(f"CREATE VIEW {name} AS SELECT * FROM "
                        f"read_json_auto({path}, format='newline_delimited')")
        elif kind == "excel":
            con.register(t["name"], pandas_load(t))
    return con


def pandas_load(t, nrows=None):
    import pandas as pd
    path, kind = t["path"], t["kind"]
    if kind in ("csv", "tsv"):
        enc, delim = sniff_text(path, kind)
        return pd.read_csv(path, sep=delim, encoding=enc, nrows=nrows, low_memory=False)
    if kind == "excel":
        return pd.read_excel(path, sheet_name=t["sheet"], nrows=nrows)
    if kind == "jsonl":
        return pd.read_json(path, lines=True, nrows=nrows)
    if kind == "json":
        df = pd.read_json(path)
    else:  # parquet
        df = pd.read_parquet(path)
    return df.head(nrows) if nrows else df


def pandas_count(t):
    import pandas as pd
    path, kind = t["path"], t["kind"]
    if kind in ("csv", "tsv"):
        enc, delim = sniff_text(path, kind)
        return sum(len(c) for c in pd.read_csv(path, sep=delim, encoding=enc,
                                               usecols=[0], chunksize=500_000))
    if kind == "jsonl":
        with open(path, "rb") as f:
            return sum(1 for line in f if line.strip())
    if kind == "parquet":
        try:
            import pyarrow.parquet as pq
            return pq.ParquetFile(path).metadata.num_rows
        except ImportError:
            pass
    return len(pandas_load(t))


def sqlite_connect(tables):
    import sqlite3
    con = sqlite3.connect(":memory:")
    for t in tables:
        df = pandas_load(t)
        for c in df.columns:
            if df[c].dtype == object:
                df[c] = df[c].map(lambda v: json.dumps(v, default=str)
                                  if isinstance(v, (dict, list)) else v)
        df.to_sql(t["name"], con, index=False)
    return con


def cell(v, width=CELL_WIDTH):
    import pandas as pd
    try:
        if pd.isna(v):
            return "NULL"
    except (TypeError, ValueError):
        pass
    s = str(v).replace("\n", " ")
    return s if len(s) <= width else s[: width - 1] + "…"


def show(df, width=CELL_WIDTH):
    if df.empty:
        return "(no rows)"
    import pandas as pd
    out = pd.DataFrame(
        [[cell(v, width) for v in row] for row in df.itertuples(index=False, name=None)],
        columns=[cell(c, width) for c in df.columns])
    return out.to_string(index=False)


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def describe_tables(tables, con=None, duck=False):
    """Short 'table(col, col, ...)' list, used to help fix a failing query."""
    lines = []
    for t in tables:
        try:
            if duck:
                cols = [r[0] for r in con.execute(f"DESCRIBE {qi(t['name'])}").fetchall()]
            else:
                cols = [r[1] for r in con.execute(f"PRAGMA table_info({qi(t['name'])})")]
        except Exception:
            cols = ["?"]
        shown = ", ".join(cols[:30]) + (", ..." if len(cols) > 30 else "")
        lines.append(f"  {t['name']}({shown})")
    return "\n".join(lines)
