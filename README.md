# large-file-analysis: a Claude skill for big data files

Analyze large CSV, Excel, Parquet and JSON files with Claude **without loading them into
context**. Claude reads only the headers and a few sample rows, then answers your questions
with SQL and reads back only the small results.

Fewer tokens, fewer hit limits, and it works on files far bigger than Claude's context window.

## Why

When you point Claude at a folder of data files, it often opens them to "take a look".
On big files, that burns your usage in seconds, or simply fails.

Benchmark on a 1,000,000-row orders CSV (52 MB):

| | Approx. tokens read by Claude |
|---|---|
| Reading the file | ~13,600,000 (doesn't fit in context) |
| With this skill: profile of the file | ~250 |
| With this skill: one aggregated query (revenue by country and channel, 20 rows) | ~230 |

Token counts are estimated at 4 characters per token.

## How it works

1. **Profile**: `scripts/profile.py` prints each file's size, row count, columns, types,
   null rates and 5 sample rows.
2. **Query**: `scripts/query.py` runs SQL on the files (each file is a table) and prints at most
   50 rows. Full results can be saved to a CSV.
3. **Rules**: the skill forbids Claude from opening raw data files directly.

The engine is [DuckDB](https://duckdb.org) when installed (streams multi-GB files in seconds).
Without it, the scripts fall back to pandas + SQLite.

## Install

**Claude Code**

```bash
git clone https://github.com/<you>/large-file-analysis ~/.claude/skills/large-file-analysis
pip install pandas duckdb openpyxl   # duckdb recommended, openpyxl for Excel
```

**Claude app (claude.ai / desktop)**: zip the folder and upload it in
the Skills section of Settings.

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
