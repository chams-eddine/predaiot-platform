# -*- coding: utf-8 -*-
"""PREDAIOT Knowledge Engineering Workflow (CLI).

Point it at a real dataset; it reports what knowledge is MISSING to recognize the
facility, and an objective recognition score. Author/extend the knowledge pack,
re-run, watch the score climb. Adding an industry becomes a measurable loop.

  python tools/knowledge_workflow.py --file plant.csv
  python tools/knowledge_workflow.py --columns "timestamp,price,kiln_power_mw,clinker_tph" \
                                     --metadata '{"kiln_diameter_m": 5}'
"""
import argparse
import csv
import json

from app.services.facility.gap_analysis import analyze_dataset


def _columns_from_file(path):
    with open(path, encoding="utf-8", errors="replace", newline="") as fh:
        for row in csv.reader(fh):
            return [c.strip() for c in row if c.strip()]
    return []


def main():
    ap = argparse.ArgumentParser(description="PREDAIOT Knowledge Engineering Workflow")
    ap.add_argument("--file", help="dataset CSV (reads the header row for columns)")
    ap.add_argument("--columns", help="comma-separated column names (instead of --file)")
    ap.add_argument("--metadata", help='JSON of nameplate facts, e.g. \'{"transformer_mva":30}\'')
    args = ap.parse_args()

    cols = (_columns_from_file(args.file) if args.file
            else [c.strip() for c in (args.columns or "").split(",") if c.strip()])
    meta = json.loads(args.metadata) if args.metadata else None
    if not cols:
        ap.error("provide --file or --columns")
    print(analyze_dataset(cols, metadata=meta).render())


if __name__ == "__main__":
    main()
