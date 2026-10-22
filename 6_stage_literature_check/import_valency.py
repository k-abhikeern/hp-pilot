"""Merge saved Valency search results into outputs/valency_results.json (the input of  run_stage6.py report).

The agent runs Valency searches; large results are saved as JSON files. This script combines any number
of them, removes duplicate papers (same paper, different versions or sources), and keeps only the fields
the report needs.

    ~/miniconda3/envs/osi/bin/python import_valency.py result1.txt result2.txt ...
"""
import json
import sys
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent / "outputs" / "valency_results.json"


def main(files):
    papers, queries, seen = [], [], set()
    for f in files:
        raw = json.loads(Path(f).read_text())
        queries += raw.get("queries") or [raw.get("query")]
        for p in raw["papers"]:
            key = p.get("base_id") or p["id"]
            title_key = p["title"].lower().strip(" .")
            if key in seen or title_key in seen:  # same paper from arXiv and PubMed counts once
                continue
            seen.update({key, title_key})
            date = (p.get("dates", {}).get("first_available", {}) or {}).get("value") or p.get("datestamp") or ""
            papers.append({"id": key, "title": p["title"], "date": date, "url": p["url"],
                           "citation_count": p.get("citation_count"), "source": p.get("source"),
                           "abstract": p.get("abstract") or ""})
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"source": "Valency (claude.ai MCP connector)",
                               "searched_at": time.strftime("%Y-%m-%d %H:%M"),
                               "queries": [q for q in queries if q], "papers": papers}, indent=2))
    print(f"{len(papers)} unique papers from {len(files)} result file(s) -> {OUT}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Merge saved Valency results.")
    parser.add_argument("files", nargs="+")
    parser.add_argument("--out", help="output file (default: outputs/valency_results.json); "
                                      "for a stage 7 campaign use <campaign>/literature/valency_results.json")
    args = parser.parse_args()
    if args.out:
        OUT = Path(args.out)
    main(args.files)
