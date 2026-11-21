# large-file-analysis: a Claude skill for big data files

A Claude skill that makes analysis of large CSV, Excel, Parquet and JSON files fast.
Claude first profiles each file (columns, types, null rates, a few sample rows), then answers
your questions with SQL and reads back only small, aggregated results.

## What it does

- **Never opens raw data files.** The skill forbids Claude from printing or reading a data file
  directly, so a big file can't flood the context by accident.
- **Profiles first.** `scripts/profile.py` prints each file's size, row count, columns, types,
  null rates and 5 sample rows.
- **Answers with SQL.** `scripts/query.py` runs SQL on your files (each file is a table),
  prints at most 50 rows, and can save the full result to a CSV.
- **Works on several files at once.** Point it at a folder and join files in one query.

The engine is [DuckDB](https://duckdb.org) when installed (streams multi-GB files). Without it,
the scripts fall back to pandas + SQLite, which is fine up to a few million rows.

## What to expect

We ran the same analysis with and without the skill, on a Windows machine, in two tests with
different sets of files (1.4 to several million rows, up to 600 MB of CSV: joins, data-quality
checks, aggregations).

| | Without the skill | With the skill | Speedup |
|---|---|---|---|
| Test 1 (4 files, about 1.4M rows) | about 3.5 min | 65 s | about 3x |
| Test 2 (larger files, several million rows) | 2 min 19 s | 40 s | about 3.5x |

**The gain is speed, not tokens.** In every run Claude kept the raw files out of its context, so
token usage was about the same (roughly 18k to 25k tokens of messages with or without the
skill). Without the skill, Claude fell back on slower tools such as line-by-line reads in
PowerShell or Python's csv module; with it, queries run on DuckDB.

These are single runs on one machine, so treat the numbers as indicative. The gap will be
smaller if Python or DuckDB is already available and Claude chooses to use it.

## Install

**Claude Code**

```bash
git clone https://github.com/adelguerrot-svg/large-file-analysis ~/.claude/skills/large-file-analysis
pip install pandas openpyxl duckdb   # duckdb recommended, openpyxl for Excel files
```

**Claude app**: zip the folder and upload it in the Skills section of Settings.

## Usage

Put your files in a folder, give Claude access to it, and ask in plain language:

> Analyze the files in `./data`: which countries drive revenue, and how has it changed by month?

Claude will profile the folder, then run queries like:

```bash
python scripts/query.py data "SELECT country, ROUND(SUM(amount)) AS revenue
                              FROM orders GROUP BY 1 ORDER BY 2 DESC"
```

Supported formats: `.csv`, `.tsv`, `.xlsx`, `.xls`, `.parquet`, `.json`, `.jsonl`.

## Want to see the rows yourself?

This skill gives Claude the answers. If you want to **browse, filter, pivot and chart
millions of rows yourself**, try [Big Sheets](https://bigsheets.pro): a spreadsheet in your
browser that opens files beyond Excel's 1,048,576-row limit. Your files stay on your machine,
and Claude can drive it through the Big Sheets MCP connector.

## License

MIT
