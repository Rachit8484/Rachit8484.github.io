"""Reshape the CSV into normalized JSON.

Output:
  prelims-gs1-2015-2024.json      — consolidated
  by-year/<year>.json             — one file per year
  by-topic/<slug>.json            — one file per subject

"""

from __future__ import annotations

import csv
import io
import json
import re
import sys
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

CSV_URL = "https://raw.githubusercontent.com/rachit8484/upsc/main/public/upscpyqs.csv"
YEARS = range(2015, 2025)
PAPER_FILTER = "GS1"

ROOT = Path(__file__).resolve().parent
CONSOLIDATED = ROOT / "prelims-gs1-2015-2024.json"
BY_YEAR = ROOT / "by-year"
BY_TOPIC = ROOT / "by-topic"


def fetch_csv(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "upsc-pyq-build/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8")


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def reshape(rows: list[dict]) -> list[dict]:
    by_year: dict[int, int] = defaultdict(int)
    out: list[dict] = []
    for r in rows:
        if (r.get("Paper") or "").strip().upper() != PAPER_FILTER:
            continue
        try:
            year = int((r.get("Year") or "").strip())
        except ValueError:
            continue
        if year not in YEARS:
            continue
        by_year[year] += 1
        out.append(
            {
                "id": f"{year}-{by_year[year]:03d}",
                "year": year,
                "paper": "GS1",
                "question": (r.get("Question") or "").strip(),
                "options": {
                    "A": (r.get("Option A") or "").strip(),
                    "B": (r.get("Option B") or "").strip(),
                    "C": (r.get("Option C") or "").strip(),
                    "D": (r.get("Option D") or "").strip(),
                },
                "correct_answer": (r.get("Correct Answer") or "").strip() or None,
                "explanation": (r.get("Explanation") or "").strip() or None,
                "subject": (r.get("Subject") or "").strip() or None,
                "topic": (r.get("Topic") or "").strip() or None,
                "passage": (r.get("Passage") or "").strip() or None,
                "image_url": (r.get("Image Url") or "").strip() or None,
            }
        )
    return out


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main() -> int:
    print(f"Fetching {CSV_URL} ...", file=sys.stderr)
    csv_text = fetch_csv(CSV_URL)
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    print(f"Upstream rows: {len(rows)}", file=sys.stderr)

    questions = reshape(rows)
    print(f"Filtered {PAPER_FILTER} {min(YEARS)}-{max(YEARS)}: {len(questions)}", file=sys.stderr)

    write_json(CONSOLIDATED, questions)

    for path in BY_YEAR.glob("*.json"):
        path.unlink()
    for path in BY_TOPIC.glob("*.json"):
        path.unlink()

    per_year: dict[int, list[dict]] = defaultdict(list)
    per_subject: dict[str, list[dict]] = defaultdict(list)
    for q in questions:
        per_year[q["year"]].append(q)
        subj = q["subject"] or "uncategorized"
        per_subject[subj].append(q)

    for year in sorted(per_year):
        write_json(BY_YEAR / f"{year}.json", per_year[year])
    for subject, qs in per_subject.items():
        write_json(BY_TOPIC / f"{slugify(subject)}.json", qs)

    print("\nPer-year counts:", file=sys.stderr)
    for year, n in sorted(Counter(q["year"] for q in questions).items()):
        print(f"  {year}: {n}", file=sys.stderr)
    print("\nPer-subject counts:", file=sys.stderr)
    for subj, n in Counter(q["subject"] for q in questions).most_common():
        print(f"  {subj}: {n}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
